from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
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
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-dual-horizon-campaign-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ENGINE_PATH = ROOT / "research/asset-portfolios/1d-btceth-cross-breadth-channel-trend/scripts/search_binance_1d_be_cbct_p0.py"


@dataclass(frozen=True, order=True)
class Config:
    regime_ema: int
    slope_days: int
    regime_confirm: int
    breakout_n: int
    cooldown_days: int


@dataclass
class CampaignBook:
    state: np.ndarray
    entry: Any


def load_engine() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_be_dhct_engine", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def configs() -> list[Config]:
    return [
        Config(*values)
        for values in itertools.product((100, 200, 300), (20, 60), (1, 3), (20, 40, 60), (0, 3, 7))
    ]


def confirm_campaign(raw: np.ndarray, days: int) -> np.ndarray:
    output = np.zeros(len(raw), dtype=np.int8)
    state, pending, streak = 0, 0, 0
    for index, value in enumerate(raw):
        target = int(value)
        if target == state:
            pending, streak = state, 0
        elif target == pending:
            streak += 1
        else:
            pending, streak = target, 1
        if target != state and streak >= days:
            state, pending, streak = target, target, 0
        output[index] = state
    return output


def build_campaign_book(engine: Any, daily_frame: pd.DataFrame, daily: Any, config: Config) -> CampaignBook:
    ema = {
        symbol: daily_frame[f"{symbol}_close"].ewm(
            span=config.regime_ema, adjust=False, min_periods=config.regime_ema
        ).mean()
        for symbol in engine.SYMBOLS
    }
    long_ok = np.ones(len(daily.ts), dtype=bool)
    short_ok = np.ones(len(daily.ts), dtype=bool)
    for symbol in engine.SYMBOLS:
        close = daily_frame[f"{symbol}_close"]
        long_ok &= ((close > ema[symbol]) & (ema[symbol] > ema[symbol].shift(config.slope_days))).to_numpy(bool)
        short_ok &= ((close < ema[symbol]) & (ema[symbol] < ema[symbol].shift(config.slope_days))).to_numpy(bool)
    raw = np.where(long_ok, 1, np.where(short_ok, -1, 0)).astype(np.int8)
    state = confirm_campaign(raw, config.regime_confirm)
    code = np.zeros(len(daily.ts), dtype=np.int8)
    selected_score = np.full(len(daily.ts), np.nan)
    candidate_codes, candidate_scores = [], []
    for asset_index, symbol in enumerate(engine.SYMBOLS, start=1):
        prior_high = daily_frame[f"{symbol}_high"].shift(1).rolling(
            config.breakout_n, min_periods=config.breakout_n
        ).max().to_numpy(float)
        prior_low = daily_frame[f"{symbol}_low"].shift(1).rolling(
            config.breakout_n, min_periods=config.breakout_n
        ).min().to_numpy(float)
        long_score = (daily.close[symbol] - prior_high) / daily.atr14[symbol]
        short_score = (prior_low - daily.close[symbol]) / daily.atr14[symbol]
        long_entry = (state == 1) & (long_score > 0)
        short_entry = (state == -1) & (short_score > 0)
        candidate_codes.append(np.where(long_entry, asset_index, np.where(short_entry, -asset_index, 0)))
        candidate_scores.append(np.where(long_entry, long_score, np.where(short_entry, short_score, np.nan)))
    for index in range(len(code)):
        options = [
            (candidate_scores[asset][index], int(candidate_codes[asset][index]), asset)
            for asset in (0, 1)
            if candidate_codes[asset][index] != 0 and np.isfinite(candidate_scores[asset][index])
        ]
        if options:
            options.sort(key=lambda item: (-item[0], item[2]))
            selected_score[index], code[index] = options[0][0], options[0][1]
    return CampaignBook(state, engine.EntryBook(code, selected_score))


def engine_config(engine: Any, config: Config) -> Any:
    return engine.Config(config.breakout_n, 5, config.regime_ema, 5.0, 1, config.cooldown_days, 0)


def never_channels(engine: Any, length: int) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    return (
        {symbol: np.full(length, -np.inf) for symbol in engine.SYMBOLS},
        {symbol: np.full(length, np.inf) for symbol in engine.SYMBOLS},
    )


def simulate(
    engine: Any,
    data: Any,
    daily: Any,
    hourly: Any,
    book: CampaignBook,
    config: Config,
    *,
    slippage: float,
    delay_days: int = 0,
    retain: bool = False,
) -> Any:
    protection = engine.ProfitProtection(1.0, 0.35, 2)
    return engine.simulate(
        data,
        daily,
        hourly,
        book.entry,
        never_channels(engine, len(daily.ts)),
        engine_config(engine, config),
        slippage=slippage,
        delay_days=delay_days,
        retain=retain,
        profit_protection=protection,
        campaign_state=book.state,
    )


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen P0 search for BIN-1D-BE-DHCT.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    grid = configs()
    if args.self_test:
        assert len(grid) == 108 and len(set(grid)) == 108
        print("self-test: PASS")
        return
    engine = load_engine()
    data = engine.load_data_helper()
    hourly_source, funding, quality = data.load_frozen_data()
    daily, hourly, daily_frame = engine.prepare_markets(data, hourly_source, funding)
    books = {config: build_campaign_book(engine, daily_frame, daily, config) for config in grid}
    rows, base_passers = [], []
    for config in grid:
        result = simulate(engine, data, daily, hourly, books[config], config, slippage=engine.BASE_SLIPPAGE)
        base_pass = result.equity_multiple >= 20.0 and result.max_drawdown_pct >= -20.0
        rows.append(
            {
                **asdict(config),
                "equity_multiple": result.equity_multiple,
                "ordered_mdd_pct": result.max_drawdown_pct,
                **result.counts,
                "trade_path_sha256": result.trade_path_sha256,
                "base_screen_pass": base_pass,
                "all_gates_pass": False,
            }
        )
        if base_pass:
            base_passers.append(config)
    frame = pd.DataFrame(rows)
    growth_config = Config(**{key: value for key, value in frame.sort_values(
        ["equity_multiple", "ordered_mdd_pct"], ascending=[False, False]
    ).iloc[0].items() if key in asdict(grid[0])})
    risk_config = Config(**{key: value for key, value in frame.sort_values(
        ["ordered_mdd_pct", "equity_multiple"], ascending=[False, False]
    ).iloc[0].items() if key in asdict(grid[0])})
    retained: dict[Config, Any] = {}
    for config in set(base_passers + [growth_config, risk_config]):
        retained[config] = simulate(
            engine, data, daily, hourly, books[config], config, slippage=engine.BASE_SLIPPAGE, retain=True
        )
    details, seen = [], set()
    for config in sorted(base_passers):
        base = retained[config]
        if base.trade_path_sha256 in seen:
            continue
        seen.add(base.trade_path_sha256)
        stress = simulate(engine, data, daily, hourly, books[config], config, slippage=engine.STRESS_SLIPPAGE)
        delayed = simulate(
            engine, data, daily, hourly, books[config], config, slippage=engine.BASE_SLIPPAGE, delay_days=1
        )
        base_log = math.log(base.equity_multiple)
        stress_retention = math.log(stress.equity_multiple) / base_log if stress.equity_multiple > 0 else -math.inf
        delay_retention = math.log(delayed.equity_multiple) / base_log if delayed.equity_multiple > 0 else -math.inf
        gates = {
            "stress": stress.equity_multiple >= 16.0 and stress.max_drawdown_pct >= -22.0,
            "delay": delay_retention >= 0.70 and delayed.equity_multiple >= 8.0 and delayed.max_drawdown_pct >= -25.0,
            "calendar": engine.complete_year_ratio(base.path) >= 0.70,
            "rolling": engine.rolling_ratio(base.path) >= 0.70,
            "capacity": base.counts["trades"] >= 20 and all(
                base.counts[key] >= 5 for key in ("long", "short", "BTCUSDT", "ETHUSDT")
            ),
            "concentration": engine.concentration(base.trades) <= 0.30,
        }
        details.append(
            {
                **asdict(config),
                "base_equity_multiple": base.equity_multiple,
                "base_ordered_mdd_pct": base.max_drawdown_pct,
                **base.counts,
                "trade_path_sha256": base.trade_path_sha256,
                "stress_equity_multiple": stress.equity_multiple,
                "stress_ordered_mdd_pct": stress.max_drawdown_pct,
                "stress_log_growth_retention": stress_retention,
                "delay_equity_multiple": delayed.equity_multiple,
                "delay_ordered_mdd_pct": delayed.max_drawdown_pct,
                "delay_log_growth_retention": delay_retention,
                "complete_year_positive_ratio": engine.complete_year_ratio(base.path),
                "rolling_365d_positive_ratio": engine.rolling_ratio(base.path),
                "max_trade_positive_log_share": engine.concentration(base.trades),
                **{f"gate_{key}": value for key, value in gates.items()},
                "all_gates_pass": all(gates.values()),
            }
        )
    detail_frame = pd.DataFrame(details)
    passing = detail_frame.loc[detail_frame["all_gates_pass"]].copy() if not detail_frame.empty else detail_frame
    if not passing.empty:
        passing = passing.sort_values(
            ["base_ordered_mdd_pct", "stress_log_growth_retention", "base_equity_multiple", "trades", *asdict(grid[0])],
            ascending=[False, False, False, True, True, True, True, True, True],
        )
    unique = passing.iloc[0].to_dict() if not passing.empty else None
    best_growth = frame.sort_values(["equity_multiple", "ordered_mdd_pct"], ascending=[False, False]).iloc[0].to_dict()
    best_risk = frame.sort_values(["ordered_mdd_pct", "equity_multiple"], ascending=[False, False]).iloc[0].to_dict()
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-BTCETH-Dual-Horizon-Campaign-Trend",
        "campaign": "P0 frozen development search",
        "status": "development candidate; audit sealed" if unique else "HARD-GATE-FAILED / explore / not promoted / not live-ready",
        "evidence_role": "development only; audit/prospective not read",
        "data_quality": quality,
        "contract": {"configs": len(grid), "profit_protection": "1ATR/35%/2d", "initial_leverage": 1.0},
        "counts": {
            "configs": len(frame),
            "base_screen_pass": int(frame["base_screen_pass"].sum()),
            "unique_base_paths": len(detail_frame),
            "all_gates_pass": int(detail_frame["all_gates_pass"].sum()) if not detail_frame.empty else 0,
        },
        "best_growth": best_growth,
        "best_risk": best_risk,
        "unique_candidate": unique,
        "audit_revealed": False,
        "prospective_revealed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_be_dhct_p0_search_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(json.dumps(clean(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    frame.to_csv(ARTIFACT_DIR / f"{stem}_grid.csv", index=False)
    detail_frame.to_csv(ARTIFACT_DIR / f"{stem}_candidates.csv", index=False)
    path_rows, trade_rows = [], []
    for frontier, config in (("growth_frontier", growth_config), ("risk_frontier", risk_config)):
        result = retained[config]
        path_rows.extend({"frontier": frontier, **item} for item in result.path)
        trade_rows.extend({"frontier": frontier, **item} for item in result.trades)
    pd.DataFrame(path_rows).to_csv(ARTIFACT_DIR / f"{stem}_path.csv", index=False)
    pd.DataFrame(trade_rows).to_csv(ARTIFACT_DIR / f"{stem}_trades.csv", index=False)
    print(json.dumps(clean(payload["counts"]), ensure_ascii=False))
    print(json.dumps(clean(best_growth), ensure_ascii=False))
    print(json.dumps(clean(best_risk), ensure_ascii=False))
    print(json.dumps(clean(unique), ensure_ascii=False))


if __name__ == "__main__":
    main()
