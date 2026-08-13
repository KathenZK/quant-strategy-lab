from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-relative-cycle-rotation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
P0_PATH = FAMILY_DIR / "scripts/search_binance_1d_be_rcr_p0.py"
ANCHORS = {
    "growth": (40, 40, 28, 0.0, 0.25, 3),
    "risk": (90, 60, 56, 1.0, 0.25, 2),
}
CONTROL_EXPECTED = {
    "growth": (21.260522820421354, -69.6600350089438),
    "risk": (8.610855869987917, -30.760725775971544),
}


@dataclass(frozen=True, order=True)
class OverlayConfig:
    anchor: str
    stop_atr: float
    fast_ema: int
    rearm: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Frozen P1 protective-exit search.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_p0() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_be_rcr_p0_engine", P0_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {P0_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def overlay_configs() -> list[OverlayConfig]:
    rows = []
    for anchor, stop_atr, fast_ema, rearm in itertools.product(
        ("growth", "risk"),
        (0.0, 1.5, 2.0, 2.5, 3.0, 4.0),
        (0, 5, 10, 20),
        ("state_change", "cooldown_3", "cooldown_7", "cooldown_14"),
    ):
        if stop_atr == 0.0 and fast_ema == 0:
            continue
        rows.append(OverlayConfig(anchor, stop_atr, fast_ema, rearm))
    return rows


def daily_atr(daily: pd.DataFrame, symbol: str, window: int = 14) -> np.ndarray:
    high = daily[f"{symbol}_high"].astype(float)
    low = daily[f"{symbol}_low"].astype(float)
    previous_close = daily[f"{symbol}_close"].astype(float).shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1
    ).max(axis=1)
    return true_range.rolling(window, min_periods=window).mean().to_numpy(dtype=float)


def fast_exit_arrays(
    daily: pd.DataFrame, span: int, extra_delay_days: int
) -> dict[tuple[str, int], np.ndarray]:
    output: dict[tuple[str, int], np.ndarray] = {}
    lag = 1 + extra_delay_days
    for symbol in ("BTCUSDT", "ETHUSDT"):
        close = daily[f"{symbol}_close"].astype(float)
        if span == 0:
            long_raw = np.zeros(len(daily), dtype=bool)
            short_raw = np.zeros(len(daily), dtype=bool)
        else:
            ema = close.ewm(span=span, adjust=False, min_periods=span).mean()
            long_raw = (close < ema).fillna(False).to_numpy(dtype=bool)
            short_raw = (close > ema).fillna(False).to_numpy(dtype=bool)
        for side, raw in ((1, long_raw), (-1, short_raw)):
            execution = np.zeros(len(raw), dtype=bool)
            execution[lag:] = raw[:-lag]
            output[(symbol, side)] = execution
    return output


def rearm_allows(
    target: int,
    banned_state: int,
    ban_day: pd.Timestamp | None,
    current_day: pd.Timestamp,
    rearm: str,
) -> tuple[bool, int, pd.Timestamp | None]:
    if banned_state == 0:
        return True, 0, None
    if target != banned_state:
        return True, 0, None
    if rearm == "state_change":
        return False, banned_state, ban_day
    cooldown = int(rearm.split("_", maxsplit=1)[1])
    if ban_day is not None and (current_day - ban_day).days >= cooldown:
        return True, 0, None
    return False, banned_state, ban_day


def protective_replay(
    p0: Any,
    hourly: pd.DataFrame,
    daily: pd.DataFrame,
    base_states: np.ndarray,
    config: OverlayConfig,
    *,
    slippage: float,
    extra_delay_days: int = 0,
    retain: bool = True,
) -> Any:
    target_by_day = dict(zip(daily["ts"], base_states, strict=True))
    day_index = {pd.Timestamp(ts): index for index, ts in enumerate(daily["ts"])}
    atr = {
        symbol: daily_atr(daily, symbol)
        for symbol in ("BTCUSDT", "ETHUSDT")
    }
    exits = fast_exit_arrays(daily, config.fast_ema, extra_delay_days)
    cash = 1.0
    quantity = 0.0
    side = 0
    asset = ""
    entry_price = 0.0
    entry_equity = 0.0
    entry_ts: pd.Timestamp | None = None
    stop_level: float | None = None
    banned_state = 0
    ban_day: pd.Timestamp | None = None
    peak = 1.0
    max_drawdown = 0.0
    path: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    holding = {"BTCUSDT": 0, "ETHUSDT": 0}
    long_trades = 0
    short_trades = 0

    def current_state() -> int:
        return side * (1 if asset == "BTCUSDT" else 2) if side else 0

    def close_position(mark: float, timestamp: pd.Timestamp, reason: str) -> None:
        nonlocal cash, quantity, side, asset, entry_price, stop_level
        cash, exit_fill = p0._close_position(
            cash, quantity, side, entry_price, mark, slippage
        )
        trades.append(
            {
                "entry_ts": entry_ts,
                "exit_ts": timestamp,
                "asset": asset,
                "side": side,
                "entry_price": entry_price,
                "exit_price": exit_fill,
                "entry_equity": entry_equity,
                "exit_equity": cash,
                "trade_log_growth": math.log(cash / entry_equity),
                "exit_reason": reason,
            }
        )
        quantity = 0.0
        side = 0
        asset = ""
        entry_price = 0.0
        stop_level = None

    def open_position(target: int, mark: float, timestamp: pd.Timestamp) -> None:
        nonlocal cash, quantity, side, asset, entry_price, entry_equity, entry_ts
        nonlocal stop_level, long_trades, short_trades
        asset = p0.STATE_ASSET[target]
        side = 1 if target > 0 else -1
        entry_equity = cash
        entry_ts = timestamp
        cash, quantity, entry_price = p0._open_position(cash, side, mark, slippage)
        if config.stop_atr > 0:
            index = day_index[timestamp] - 1
            atr_value = atr[asset][index]
            if not np.isfinite(atr_value):
                raise RuntimeError(f"missing prior ATR at {timestamp} for {asset}")
            stop_level = mark - side * config.stop_atr * float(atr_value)
        else:
            stop_level = None
        long_trades += int(side > 0)
        short_trades += int(side < 0)

    for row in hourly.itertuples(index=False):
        timestamp = pd.Timestamp(row.ts)
        day = timestamp.floor("1D")
        if timestamp.hour == 0:
            target = 0 if timestamp == p0.DEVELOPMENT_END else int(target_by_day[timestamp])
            state = current_state()
            if state:
                if target != state:
                    close_position(float(getattr(row, f"{asset}_open")), timestamp, "base_change")
                elif exits[(asset, side)][day_index[timestamp]]:
                    protected_state = state
                    close_position(float(getattr(row, f"{asset}_open")), timestamp, "fast_ema")
                    banned_state = protected_state
                    ban_day = day
            if side == 0 and target and timestamp < p0.DEVELOPMENT_END:
                allowed, banned_state, ban_day = rearm_allows(
                    target, banned_state, ban_day, day, config.rearm
                )
                if allowed:
                    open_position(
                        target,
                        float(getattr(row, f"{p0.STATE_ASSET[target]}_open")),
                        timestamp,
                    )
            elif side == 0 and target != banned_state:
                banned_state = 0
                ban_day = None
        if timestamp == p0.DEVELOPMENT_END:
            equity = cash
            peak = max(peak, equity)
            max_drawdown = min(max_drawdown, equity / peak - 1.0)
            if retain:
                path.append({"ts": timestamp, "equity": equity, "state": 0})
            break

        if side and stop_level is not None:
            open_mark = float(getattr(row, f"{asset}_open"))
            gap_hit = (side > 0 and open_mark <= stop_level) or (
                side < 0 and open_mark >= stop_level
            )
            if gap_hit:
                protected_state = current_state()
                close_position(open_mark, timestamp, "atr_stop_gap")
                banned_state = protected_state
                ban_day = day

        if side:
            holding[asset] += 1
            cash -= side * quantity * float(getattr(row, f"{asset}_unit_funding"))
            high = float(getattr(row, f"{asset}_high"))
            low = float(getattr(row, f"{asset}_low"))
            favorable = high if side > 0 else low
            adverse = low if side > 0 else high
            favorable_equity = cash + side * quantity * (favorable - entry_price)
            peak = max(peak, favorable_equity)
            stop_hit = stop_level is not None and (
                (side > 0 and low <= stop_level) or (side < 0 and high >= stop_level)
            )
            if stop_hit:
                protected_state = current_state()
                close_position(float(stop_level), timestamp, "atr_stop_intrahour")
                banned_state = protected_state
                ban_day = day
                equity = cash
            else:
                adverse_equity = cash + side * quantity * (adverse - entry_price)
                max_drawdown = min(max_drawdown, adverse_equity / peak - 1.0)
                equity = cash + side * quantity * (
                    float(getattr(row, f"{asset}_close")) - entry_price
                )
        else:
            equity = cash
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
        if retain and (timestamp.hour == 23 or timestamp == p0.COMMON_START):
            path.append({"ts": timestamp, "equity": equity, "state": current_state()})

    return p0.ReplayResult(
        equity_multiple=float(cash),
        max_drawdown_pct=float(max_drawdown * 100.0),
        path=path,
        trades=trades if retain else [],
        holding_hours=holding,
        long_trades=long_trades,
        short_trades=short_trades,
    )


def trade_path_hash(trades: list[dict[str, Any]]) -> str:
    identity = [
        (
            str(trade["entry_ts"]),
            str(trade["exit_ts"]),
            trade["asset"],
            int(trade["side"]),
            trade["exit_reason"],
        )
        for trade in trades
    ]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def main() -> None:
    args = parse_args()
    grid = overlay_configs()
    if args.self_test:
        assert len(grid) == 184
        print("self-test: PASS")
        return
    p0 = load_p0()
    hourly, funding, quality = p0.load_frozen_data()
    daily = p0.build_daily(hourly, funding)
    union = p0.build_hourly_union(hourly, funding)
    horizons = sorted(
        {value for values in ANCHORS.values() for value in (values[0], values[1])}
    )
    scores = {}
    for horizon, vol_h, symbol in itertools.product(horizons, (28, 56), p0.ASSETS):
        scores[(horizon, vol_h, symbol)] = p0.normalized_momentum(
            daily[f"{symbol}_close"], horizon, vol_h
        )
    anchor_states = {}
    controls = {}
    for name, values in ANCHORS.items():
        config = p0.Config(*values)
        states = p0.signal_for_config(config, scores)
        anchor_states[name] = states
        replay = p0.ordered_hourly_replay(
            union, daily, states, slippage=p0.BASE_SLIPPAGE
        )
        expected_equity, expected_mdd = CONTROL_EXPECTED[name]
        if not math.isclose(replay.equity_multiple, expected_equity, abs_tol=1e-12):
            raise RuntimeError(f"{name} control equity parity failed")
        if not math.isclose(replay.max_drawdown_pct, expected_mdd, abs_tol=1e-12):
            raise RuntimeError(f"{name} control MDD parity failed")
        controls[name] = {
            "config": asdict(config),
            "equity_multiple": replay.equity_multiple,
            "ordered_mdd_pct": replay.max_drawdown_pct,
            "parity": "PASS",
        }

    rows = []
    retained = {}
    for config in grid:
        base = protective_replay(
            p0,
            union,
            daily,
            anchor_states[config.anchor],
            config,
            slippage=p0.BASE_SLIPPAGE,
            retain=True,
        )
        base_screen = base.equity_multiple >= 20.0 and base.max_drawdown_pct >= -20.0
        row = {
            **asdict(config),
            "base_equity_multiple": base.equity_multiple,
            "base_ordered_mdd_pct": base.max_drawdown_pct,
            "base_screen_pass": base_screen,
            "trade_path_sha256": trade_path_hash(base.trades),
            "trades": len(base.trades),
        }
        if base_screen:
            delayed_config = p0.Config(*ANCHORS[config.anchor])
            delayed_states = p0.signal_for_config(
                delayed_config, scores, extra_delay_days=1
            )
            stress = protective_replay(
                p0,
                union,
                daily,
                anchor_states[config.anchor],
                config,
                slippage=p0.STRESS_SLIPPAGE,
                retain=False,
            )
            delayed = protective_replay(
                p0,
                union,
                daily,
                delayed_states,
                config,
                slippage=p0.BASE_SLIPPAGE,
                extra_delay_days=1,
                retain=False,
            )
            base_log = math.log(base.equity_multiple)
            stress_retention = math.log(stress.equity_multiple) / base_log
            delay_retention = math.log(delayed.equity_multiple) / base_log
            total_hours = sum(base.holding_hours.values())
            gates = {
                "base": True,
                "stress": stress.equity_multiple >= 16.0 and stress.max_drawdown_pct >= -22.0,
                "delay": (
                    delay_retention >= 0.70
                    and delayed.equity_multiple >= 8.0
                    and delayed.max_drawdown_pct >= -25.0
                ),
                "calendar": p0.complete_year_positive_ratio(base.path) >= 0.70,
                "rolling": p0.rolling_positive_ratio(base.path) >= 0.70,
                "participation": (
                    total_hours > 0
                    and all(base.holding_hours[symbol] / total_hours >= 0.10 for symbol in p0.ASSETS)
                    and all(
                        sum(1 for trade in base.trades if trade["asset"] == symbol) >= 5
                        for symbol in p0.ASSETS
                    )
                    and base.long_trades >= 5
                    and base.short_trades >= 5
                ),
                "concentration": p0.trade_concentration(base.trades) <= 0.35,
            }
            row.update(
                {
                    "stress_equity_multiple": stress.equity_multiple,
                    "stress_ordered_mdd_pct": stress.max_drawdown_pct,
                    "stress_log_growth_retention": stress_retention,
                    "delay_equity_multiple": delayed.equity_multiple,
                    "delay_ordered_mdd_pct": delayed.max_drawdown_pct,
                    "delay_log_growth_retention": delay_retention,
                    "complete_year_positive_ratio": p0.complete_year_positive_ratio(base.path),
                    "rolling_365d_positive_ratio": p0.rolling_positive_ratio(base.path),
                    "btc_holding_share": base.holding_hours["BTCUSDT"] / total_hours,
                    "eth_holding_share": base.holding_hours["ETHUSDT"] / total_hours,
                    "btc_trades": sum(1 for trade in base.trades if trade["asset"] == "BTCUSDT"),
                    "eth_trades": sum(1 for trade in base.trades if trade["asset"] == "ETHUSDT"),
                    "long_trades": base.long_trades,
                    "short_trades": base.short_trades,
                    "max_trade_positive_log_share": p0.trade_concentration(base.trades),
                    **{f"gate_{key}": value for key, value in gates.items()},
                    "all_gates_pass": all(gates.values()),
                }
            )
            retained[config] = base
        else:
            row["all_gates_pass"] = False
        rows.append(row)

    frame = pd.DataFrame(rows)
    passing = frame.loc[frame["all_gates_pass"].eq(True)].copy()
    if not passing.empty:
        passing = passing.sort_values(
            [
                "base_ordered_mdd_pct",
                "stress_log_growth_retention",
                "base_equity_multiple",
                "trades",
                "anchor",
                "stop_atr",
                "fast_ema",
                "rearm",
            ],
            ascending=[False, False, False, True, True, True, True, True],
        )
    unique_row = passing.iloc[0].to_dict() if not passing.empty else None
    unique_config = (
        OverlayConfig(
            unique_row["anchor"],
            float(unique_row["stop_atr"]),
            int(unique_row["fast_ema"]),
            unique_row["rearm"],
        )
        if unique_row
        else None
    )
    best_growth = frame.sort_values(
        ["base_equity_multiple", "base_ordered_mdd_pct"], ascending=[False, False]
    ).iloc[0].to_dict()
    best_risk = frame.sort_values(
        ["base_ordered_mdd_pct", "base_equity_multiple"], ascending=[False, False]
    ).iloc[0].to_dict()
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-BTCETH-Relative-Cycle-Rotation",
        "campaign": "P1 frozen protective-exit search",
        "status": (
            "development candidate; audit remains sealed"
            if unique_config
            else "HARD-GATE-FAILED / explore / not promoted / not live-ready"
        ),
        "evidence_role": "development only; researcher-exposed audit and prospective not read",
        "controls": controls,
        "data_quality": quality,
        "counts": {
            "configs": len(frame),
            "base_screen_pass": int(frame["base_screen_pass"].sum()),
            "all_gates_pass": int(frame["all_gates_pass"].sum()),
        },
        "best_growth": best_growth,
        "best_risk": best_risk,
        "unique_candidate": unique_row,
        "audit_revealed": False,
        "prospective_revealed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_be_rcr_p1_protective_exit_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(p0.clean_json(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    frame.to_csv(ARTIFACT_DIR / f"{stem}_grid.csv", index=False)
    if unique_config:
        result = retained[unique_config]
        pd.DataFrame(result.path).to_csv(
            ARTIFACT_DIR / f"{stem}_candidate_path.csv", index=False
        )
        pd.DataFrame(result.trades).to_csv(
            ARTIFACT_DIR / f"{stem}_candidate_trades.csv", index=False
        )
    print(json.dumps(p0.clean_json(payload["counts"]), ensure_ascii=False))
    print(json.dumps(p0.clean_json(best_growth), ensure_ascii=False))
    print(json.dumps(p0.clean_json(best_risk), ensure_ascii=False))
    print(json.dumps(p0.clean_json(unique_row), ensure_ascii=False))


if __name__ == "__main__":
    main()
