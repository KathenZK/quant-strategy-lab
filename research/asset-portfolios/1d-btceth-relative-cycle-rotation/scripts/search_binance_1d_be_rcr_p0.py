from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-relative-cycle-rotation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
P0_DIR = ROOT / "data/features/binance_1d_ma7_rsi6_dapml_p0"
P0_MANIFEST = (
    ROOT
    / "research/asset-portfolios/1d-ma7-rsi6-direction-aligned-pooled-ml/"
    "artifacts/p0_data_2026-08-10/p0_data_quality_manifest.json"
)
COMMON_START = pd.Timestamp("2019-12-24T00:00:00Z")
DEVELOPMENT_END = pd.Timestamp("2025-08-07T00:00:00Z")
FEE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
ASSETS = {"BTCUSDT": "btcusdt", "ETHUSDT": "ethusdt"}
STATE_ASSET = {1: "BTCUSDT", -1: "BTCUSDT", 2: "ETHUSDT", -2: "ETHUSDT"}
EXPECTED_FRAME_HASHES = {
    "BTCUSDT": {
        "hourly": "3e18066005c9747c040c2686e0b535769f293911e660ad8f923d81b0e2bee1cb",
        "funding": "83e4043d905274dd11d3f7874605cbe05bfea927d80853dd96959d1effd45aca",
    },
    "ETHUSDT": {
        "hourly": "29a5c7ba22831240629d48899b34c7cbfe9f411c139f7dd5220979958a416561",
        "funding": "f16a71928dad18e930db63bfe70d1d949ce79f7061b83717de9c2b50ea7cdb54",
    },
}


@dataclass(frozen=True, order=True)
class Config:
    regime_h: int
    relative_h: int
    vol_h: int
    deadzone: float
    switch_margin: float
    confirm_days: int


@dataclass
class ReplayResult:
    equity_multiple: float
    max_drawdown_pct: float
    path: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    holding_hours: dict[str, int]
    long_trades: int
    short_trades: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Frozen P0 search for BIN-1D-BE-RCR.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def frame_sha256(
    frame: pd.DataFrame, *, numeric_columns: list[str] | None = None
) -> str:
    digest = hashlib.sha256()
    timestamps = (
        pd.to_datetime(frame["ts"], utc=True)
        .to_numpy(dtype="datetime64[ns]")
        .astype("int64")
    )
    digest.update(np.ascontiguousarray(timestamps, dtype="int64").tobytes())
    columns = numeric_columns or [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "vwap",
    ]
    for column in columns:
        values = pd.to_numeric(frame[column], errors="raise").to_numpy(dtype="float64")
        digest.update(np.ascontiguousarray(values, dtype="float64").tobytes())
    if "trade_count" in frame.columns:
        counts = pd.to_numeric(frame["trade_count"], errors="raise").to_numpy(
            dtype="int64"
        )
        digest.update(np.ascontiguousarray(counts, dtype="int64").tobytes())
    return digest.hexdigest()


def load_frozen_data() -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, Any]]:
    manifest = json.loads(P0_MANIFEST.read_text(encoding="utf-8"))
    if manifest["blocker_count"] != 0:
        raise RuntimeError("P0 source manifest has blockers")
    hourly: dict[str, pd.DataFrame] = {}
    funding: dict[str, pd.DataFrame] = {}
    quality: dict[str, Any] = {"manifest": str(P0_MANIFEST.relative_to(ROOT)), "assets": {}}
    for symbol, slug in ASSETS.items():
        source = manifest["results"][symbol]
        if (
            source["hourly_quality"]["blocker_count"] != 0
            or source["funding_quality"]["blocker_count"] != 0
            or not source["hourly_quality"]["audit"]["trusted"]
        ):
            raise RuntimeError(f"{symbol}: frozen source is not trusted")
        bars = pd.read_parquet(P0_DIR / f"{slug}_perp_1h.parquet")
        funds = pd.read_parquet(P0_DIR / f"{slug}_perp_funding_mark.parquet")
        bars["ts"] = pd.to_datetime(bars["ts"], utc=True)
        funds["ts"] = pd.to_datetime(funds["ts"], utc=True)
        bars = bars.sort_values("ts").reset_index(drop=True)
        funds = funds.sort_values("ts").reset_index(drop=True)
        hashes = {
            "hourly": frame_sha256(bars),
            "funding": frame_sha256(
                funds, numeric_columns=["funding_rate", "mark_price"]
            ),
        }
        if hashes != EXPECTED_FRAME_HASHES[symbol]:
            raise RuntimeError(f"{symbol}: frozen hash mismatch: {hashes}")
        hourly[symbol] = bars[["ts", "open", "high", "low", "close"]].copy()
        funding[symbol] = funds[["ts", "funding_rate", "mark_price"]].copy()
        quality["assets"][symbol] = {
            "hourly_rows": len(bars),
            "funding_rows": len(funds),
            "hourly_start": bars["ts"].iloc[0].isoformat(),
            "hourly_end": bars["ts"].iloc[-1].isoformat(),
            "funding_start": funds["ts"].iloc[0].isoformat(),
            "funding_end": funds["ts"].iloc[-1].isoformat(),
            "hashes": hashes,
            "blocker_count": 0,
        }
    return hourly, funding, quality


def build_daily(
    hourly: dict[str, pd.DataFrame], funding: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    assets: list[pd.DataFrame] = []
    for symbol in ASSETS:
        source = hourly[symbol].set_index("ts")
        daily = source.resample("1D", label="left", closed="left").agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            hours=("close", "count"),
        )
        unit_funding = funding[symbol].copy()
        unit_funding["day"] = unit_funding["ts"].dt.floor("1D")
        unit_funding["unit_funding"] = (
            unit_funding["funding_rate"].astype(float)
            * unit_funding["mark_price"].astype(float)
        )
        per_day = unit_funding.groupby("day")["unit_funding"].sum()
        daily["unit_funding"] = per_day.reindex(daily.index, fill_value=0.0)
        daily = daily.add_prefix(f"{symbol}_").reset_index()
        assets.append(daily)
    merged = assets[0].merge(assets[1], on="ts", how="inner", validate="one_to_one")
    full_day = (
        merged["BTCUSDT_hours"].eq(24) & merged["ETHUSDT_hours"].eq(24)
    )
    terminal = merged["ts"].eq(DEVELOPMENT_END)
    usable = merged.loc[full_day | terminal].copy().sort_values("ts").reset_index(drop=True)
    if not usable["ts"].eq(COMMON_START).any() or not usable["ts"].eq(DEVELOPMENT_END).any():
        raise RuntimeError("missing exact development boundary in daily data")
    return usable


def normalized_momentum(close: pd.Series, horizon: int, vol_h: int) -> np.ndarray:
    log_close = np.log(close.astype(float))
    daily_return = log_close.diff()
    volatility = daily_return.rolling(vol_h, min_periods=vol_h).std(ddof=1)
    score = (log_close - log_close.shift(horizon)) / (
        volatility * math.sqrt(horizon)
    )
    return score.to_numpy(dtype=float)


def raw_states(market: np.ndarray, relative: np.ndarray, deadzone: float, margin: float) -> np.ndarray:
    raw = np.zeros(len(market), dtype=np.int8)
    valid = np.isfinite(market) & np.isfinite(relative)
    bull = valid & (market > deadzone)
    bear = valid & (market < -deadzone)
    raw[bull & (relative > margin)] = 1
    raw[bull & (relative < -margin)] = 2
    raw[bear & (relative > margin)] = -2
    raw[bear & (relative < -margin)] = -1
    return raw


def confirmed_states(raw: np.ndarray, confirm_days: int) -> np.ndarray:
    if confirm_days < 1:
        raise ValueError("confirm_days must be positive")
    output = np.zeros(len(raw), dtype=np.int8)
    candidate = 0
    streak = 0
    current = 0
    for index, value in enumerate(raw):
        state = int(value)
        if state == candidate:
            streak += 1
        else:
            candidate = state
            streak = 1
        if streak >= confirm_days:
            current = candidate
        output[index] = current
    return output


def execution_states(decisions: np.ndarray, extra_delay_days: int = 0) -> np.ndarray:
    lag = 1 + extra_delay_days
    output = np.zeros(len(decisions), dtype=np.int8)
    if lag < len(decisions):
        output[lag:] = decisions[:-lag]
    return output


def _fill_price(mark: float, side: int, slippage: float, *, entry: bool) -> float:
    direction = side if entry else -side
    return mark * (1.0 + direction * slippage)


def _close_position(
    cash: float,
    quantity: float,
    side: int,
    entry_price: float,
    mark: float,
    slippage: float,
) -> tuple[float, float]:
    fill = _fill_price(mark, side, slippage, entry=False)
    cash += side * quantity * (fill - entry_price)
    cash -= quantity * fill * FEE
    return cash, fill


def _open_position(cash: float, side: int, mark: float, slippage: float) -> tuple[float, float, float]:
    fill = _fill_price(mark, side, slippage, entry=True)
    quantity = cash / (fill * (1.0 + FEE))
    cash -= quantity * fill * FEE
    return cash, quantity, fill


def simulate_daily(
    daily: pd.DataFrame,
    states: np.ndarray,
    *,
    slippage: float,
    retain: bool = False,
) -> ReplayResult:
    mask = daily["ts"].ge(COMMON_START) & daily["ts"].le(DEVELOPMENT_END)
    work = daily.loc[mask].reset_index(drop=True)
    source_index = daily.index[mask].to_numpy()
    state_path = states[source_index]
    cash = 1.0
    quantity = 0.0
    side = 0
    asset = ""
    entry_price = 0.0
    entry_equity = 0.0
    entry_ts: pd.Timestamp | None = None
    peak = 1.0
    max_drawdown = 0.0
    path: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    holding = {symbol: 0 for symbol in ASSETS}
    long_trades = 0
    short_trades = 0

    for row_index, row in work.iterrows():
        timestamp = pd.Timestamp(row["ts"])
        if timestamp == DEVELOPMENT_END:
            target = 0
        else:
            target = int(state_path[row_index])
        current_state = side * (1 if asset == "BTCUSDT" else 2) if side else 0
        if target != current_state:
            if side:
                cash, exit_fill = _close_position(
                    cash,
                    quantity,
                    side,
                    entry_price,
                    float(row[f"{asset}_open"]),
                    slippage,
                )
                if retain:
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
                        }
                    )
                quantity = 0.0
                side = 0
                asset = ""
            if target and timestamp < DEVELOPMENT_END:
                asset = STATE_ASSET[target]
                side = 1 if target > 0 else -1
                entry_equity = cash
                entry_ts = timestamp
                cash, quantity, entry_price = _open_position(
                    cash, side, float(row[f"{asset}_open"]), slippage
                )
                long_trades += int(side > 0)
                short_trades += int(side < 0)
        if timestamp == DEVELOPMENT_END:
            equity = cash
        elif side:
            cash -= side * quantity * float(row[f"{asset}_unit_funding"])
            equity = cash + side * quantity * (
                float(row[f"{asset}_close"]) - entry_price
            )
            holding[asset] += 24
        else:
            equity = cash
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
        if retain:
            path.append(
                {
                    "ts": timestamp,
                    "equity": equity,
                    "state": int(target),
                    "asset": asset or None,
                    "side": side,
                }
            )
    return ReplayResult(
        equity_multiple=float(cash),
        max_drawdown_pct=float(max_drawdown * 100.0),
        path=path,
        trades=trades,
        holding_hours=holding,
        long_trades=long_trades,
        short_trades=short_trades,
    )


def build_hourly_union(
    hourly: dict[str, pd.DataFrame], funding: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    frames = []
    for symbol in ASSETS:
        frame = hourly[symbol].rename(
            columns={column: f"{symbol}_{column}" for column in ("open", "high", "low", "close")}
        )
        frames.append(frame)
    merged = frames[0].merge(frames[1], on="ts", how="inner", validate="one_to_one")
    merged = merged.loc[
        merged["ts"].ge(COMMON_START) & merged["ts"].le(DEVELOPMENT_END)
    ].copy()
    for symbol in ASSETS:
        funds = funding[symbol].copy()
        funds["hour"] = funds["ts"].dt.floor("1h")
        funds["unit_funding"] = funds["funding_rate"] * funds["mark_price"]
        by_hour = funds.groupby("hour")["unit_funding"].sum()
        merged[f"{symbol}_unit_funding"] = merged["ts"].map(by_hour).fillna(0.0)
    expected = pd.date_range(COMMON_START, DEVELOPMENT_END, freq="1h", tz="UTC")
    if not pd.DatetimeIndex(merged["ts"]).equals(expected):
        raise RuntimeError("BTC/ETH hourly union is not contiguous on development")
    return merged.reset_index(drop=True)


def ordered_hourly_replay(
    hourly: pd.DataFrame,
    daily: pd.DataFrame,
    states: np.ndarray,
    *,
    slippage: float,
    retain: bool = False,
) -> ReplayResult:
    target_by_day = dict(zip(daily["ts"], states, strict=True))
    cash = 1.0
    quantity = 0.0
    side = 0
    asset = ""
    entry_price = 0.0
    entry_equity = 0.0
    entry_ts: pd.Timestamp | None = None
    peak = 1.0
    max_drawdown = 0.0
    path: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    holding = {symbol: 0 for symbol in ASSETS}
    long_trades = 0
    short_trades = 0

    for _, row in hourly.iterrows():
        timestamp = pd.Timestamp(row["ts"])
        if timestamp.hour == 0:
            target = 0 if timestamp == DEVELOPMENT_END else int(target_by_day[timestamp])
            current_state = side * (1 if asset == "BTCUSDT" else 2) if side else 0
            if target != current_state:
                if side:
                    cash, exit_fill = _close_position(
                        cash,
                        quantity,
                        side,
                        entry_price,
                        float(row[f"{asset}_open"]),
                        slippage,
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
                        }
                    )
                    quantity = 0.0
                    side = 0
                    asset = ""
                if target and timestamp < DEVELOPMENT_END:
                    asset = STATE_ASSET[target]
                    side = 1 if target > 0 else -1
                    entry_equity = cash
                    entry_ts = timestamp
                    cash, quantity, entry_price = _open_position(
                        cash, side, float(row[f"{asset}_open"]), slippage
                    )
                    long_trades += int(side > 0)
                    short_trades += int(side < 0)
        if timestamp == DEVELOPMENT_END:
            equity = cash
            peak = max(peak, equity)
            max_drawdown = min(max_drawdown, equity / peak - 1.0)
            if retain:
                path.append({"ts": timestamp, "equity": equity, "state": 0})
            break
        if side:
            holding[asset] += 1
            adverse = float(row[f"{asset}_{'low' if side > 0 else 'high'}"])
            favorable = float(row[f"{asset}_{'high' if side > 0 else 'low'}"])
            favorable_equity = cash + side * quantity * (favorable - entry_price)
            peak = max(peak, favorable_equity)
            adverse_before = cash + side * quantity * (adverse - entry_price)
            max_drawdown = min(max_drawdown, adverse_before / peak - 1.0)
            cash -= side * quantity * float(row[f"{asset}_unit_funding"])
            adverse_after = cash + side * quantity * (adverse - entry_price)
            max_drawdown = min(max_drawdown, adverse_after / peak - 1.0)
            equity = cash + side * quantity * (
                float(row[f"{asset}_close"]) - entry_price
            )
        else:
            equity = cash
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
        if retain and (timestamp.hour == 23 or timestamp == COMMON_START):
            state = side * (1 if asset == "BTCUSDT" else 2) if side else 0
            path.append({"ts": timestamp, "equity": equity, "state": state})
    return ReplayResult(
        equity_multiple=float(cash),
        max_drawdown_pct=float(max_drawdown * 100.0),
        path=path,
        trades=trades if retain else [],
        holding_hours=holding,
        long_trades=long_trades,
        short_trades=short_trades,
    )


def configs() -> list[Config]:
    return [
        Config(*values)
        for values in itertools.product(
            (20, 40, 60, 90, 120, 180, 270),
            (10, 20, 40, 60, 90, 120),
            (14, 28, 56),
            (0.0, 0.25, 0.5, 0.75, 1.0),
            (0.0, 0.25, 0.5),
            (1, 2, 3, 5),
        )
    ]


def signal_for_config(
    config: Config,
    scores: dict[tuple[int, int, str], np.ndarray],
    *,
    extra_delay_days: int = 0,
) -> np.ndarray:
    market = (
        scores[(config.regime_h, config.vol_h, "BTCUSDT")]
        + scores[(config.regime_h, config.vol_h, "ETHUSDT")]
    ) / 2.0
    relative = (
        scores[(config.relative_h, config.vol_h, "BTCUSDT")]
        - scores[(config.relative_h, config.vol_h, "ETHUSDT")]
    )
    raw = raw_states(market, relative, config.deadzone, config.switch_margin)
    decisions = confirmed_states(raw, config.confirm_days)
    return execution_states(decisions, extra_delay_days)


def complete_year_positive_ratio(path: list[dict[str, Any]]) -> float:
    frame = pd.DataFrame(path)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.set_index("ts")["equity"].sort_index()
    results = []
    for year in range(2020, 2025):
        prior = frame.loc[frame.index < pd.Timestamp(f"{year}-01-01", tz="UTC")]
        current = frame.loc[
            (frame.index >= pd.Timestamp(f"{year}-01-01", tz="UTC"))
            & (frame.index < pd.Timestamp(f"{year + 1}-01-01", tz="UTC"))
        ]
        if prior.empty or current.empty:
            continue
        results.append(float(current.iloc[-1] / prior.iloc[-1] - 1.0))
    return float(np.mean(np.asarray(results) > 0.0)) if results else 0.0


def rolling_positive_ratio(path: list[dict[str, Any]]) -> float:
    equity = pd.Series(
        [float(row["equity"]) for row in path],
        index=pd.DatetimeIndex([row["ts"] for row in path]),
    ).sort_index()
    rolling = equity / equity.shift(365) - 1.0
    valid = rolling.dropna()
    return float((valid > 0.0).mean()) if not valid.empty else 0.0


def trade_concentration(trades: list[dict[str, Any]]) -> float:
    positive = [max(0.0, float(trade["trade_log_growth"])) for trade in trades]
    total = sum(positive)
    return max(positive, default=0.0) / total if total > 0.0 else 1.0


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    grid = configs()
    if args.self_test:
        assert len(grid) == 7560
        assert confirmed_states(np.array([1, 1, 2, 2], dtype=np.int8), 2).tolist() == [0, 1, 1, 2]
        print("self-test: PASS")
        return

    hourly, funding, quality = load_frozen_data()
    daily = build_daily(hourly, funding)
    hourly_union = build_hourly_union(hourly, funding)
    scores: dict[tuple[int, int, str], np.ndarray] = {}
    horizons = sorted({value for config in grid for value in (config.regime_h, config.relative_h)})
    for horizon, vol_h, symbol in itertools.product(horizons, (14, 28, 56), ASSETS):
        scores[(horizon, vol_h, symbol)] = normalized_momentum(
            daily[f"{symbol}_close"], horizon, vol_h
        )

    rows: list[dict[str, Any]] = []
    daily_screen: list[tuple[Config, np.ndarray, ReplayResult]] = []
    for config in grid:
        states = signal_for_config(config, scores)
        result = simulate_daily(daily, states, slippage=BASE_SLIPPAGE)
        row = {
            **asdict(config),
            "equity_multiple": result.equity_multiple,
            "daily_close_mdd_pct": result.max_drawdown_pct,
            "daily_screen_pass": (
                result.equity_multiple >= 20.0 and result.max_drawdown_pct >= -20.0
            ),
            "state_path_sha256": hashlib.sha256(states.tobytes()).hexdigest(),
        }
        rows.append(row)
        if row["daily_screen_pass"]:
            daily_screen.append((config, states, result))

    detailed: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    retained_by_config: dict[Config, ReplayResult] = {}
    for config, states, daily_result in sorted(daily_screen, key=lambda item: item[0]):
        path_hash = hashlib.sha256(states.tobytes()).hexdigest()
        if path_hash in seen_paths:
            continue
        seen_paths.add(path_hash)
        base = ordered_hourly_replay(
            hourly_union, daily, states, slippage=BASE_SLIPPAGE, retain=True
        )
        stress = ordered_hourly_replay(
            hourly_union, daily, states, slippage=STRESS_SLIPPAGE
        )
        delayed_states = signal_for_config(config, scores, extra_delay_days=1)
        delayed = ordered_hourly_replay(
            hourly_union, daily, delayed_states, slippage=BASE_SLIPPAGE
        )
        base_log = math.log(base.equity_multiple) if base.equity_multiple > 0 else -math.inf
        stress_retention = (
            math.log(stress.equity_multiple) / base_log
            if stress.equity_multiple > 0 and base_log > 0
            else -math.inf
        )
        delay_retention = (
            math.log(delayed.equity_multiple) / base_log
            if delayed.equity_multiple > 0 and base_log > 0
            else -math.inf
        )
        total_hours = sum(base.holding_hours.values())
        full_gate = {
            "base_target": base.equity_multiple >= 20.0 and base.max_drawdown_pct >= -20.0,
            "stress": stress.equity_multiple >= 16.0 and stress.max_drawdown_pct >= -22.0,
            "delay": (
                delay_retention >= 0.70
                and delayed.equity_multiple >= 8.0
                and delayed.max_drawdown_pct >= -25.0
            ),
            "calendar": complete_year_positive_ratio(base.path) >= 0.70,
            "rolling": rolling_positive_ratio(base.path) >= 0.70,
            "participation": (
                total_hours > 0
                and all(base.holding_hours[symbol] / total_hours >= 0.10 for symbol in ASSETS)
                and all(
                    sum(1 for trade in base.trades if trade["asset"] == symbol) >= 5
                    for symbol in ASSETS
                )
                and base.long_trades >= 5
                and base.short_trades >= 5
            ),
            "concentration": trade_concentration(base.trades) <= 0.35,
        }
        detail = {
            **asdict(config),
            "state_path_sha256": path_hash,
            "daily_equity_multiple": daily_result.equity_multiple,
            "daily_close_mdd_pct": daily_result.max_drawdown_pct,
            "base_equity_multiple": base.equity_multiple,
            "base_ordered_mdd_pct": base.max_drawdown_pct,
            "stress_equity_multiple": stress.equity_multiple,
            "stress_ordered_mdd_pct": stress.max_drawdown_pct,
            "stress_log_growth_retention": stress_retention,
            "delay_equity_multiple": delayed.equity_multiple,
            "delay_ordered_mdd_pct": delayed.max_drawdown_pct,
            "delay_log_growth_retention": delay_retention,
            "complete_year_positive_ratio": complete_year_positive_ratio(base.path),
            "rolling_365d_positive_ratio": rolling_positive_ratio(base.path),
            "btc_holding_share": base.holding_hours["BTCUSDT"] / total_hours,
            "eth_holding_share": base.holding_hours["ETHUSDT"] / total_hours,
            "btc_trades": sum(1 for trade in base.trades if trade["asset"] == "BTCUSDT"),
            "eth_trades": sum(1 for trade in base.trades if trade["asset"] == "ETHUSDT"),
            "long_trades": base.long_trades,
            "short_trades": base.short_trades,
            "max_trade_positive_log_share": trade_concentration(base.trades),
            **{f"gate_{key}": value for key, value in full_gate.items()},
            "all_gates_pass": all(full_gate.values()),
        }
        detailed.append(detail)
        retained_by_config[config] = base

    passing = [row for row in detailed if row["all_gates_pass"]]
    passing.sort(
        key=lambda row: (
            -row["base_ordered_mdd_pct"],
            -row["stress_log_growth_retention"],
            -row["base_equity_multiple"],
            row["long_trades"] + row["short_trades"],
            tuple(asdict(Config(**{key: row[key] for key in asdict(grid[0])})).values()),
        )
    )
    unique = Config(**{key: passing[0][key] for key in asdict(grid[0])}) if passing else None
    retained = retained_by_config.get(unique) if unique else None
    best_growth = max(rows, key=lambda row: row["equity_multiple"])
    mdd_safe = [row for row in rows if row["daily_close_mdd_pct"] >= -20.0]
    best_mdd_safe_growth = max(mdd_safe, key=lambda row: row["equity_multiple"]) if mdd_safe else None
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-BTCETH-Relative-Cycle-Rotation",
        "campaign": "P0 frozen development search",
        "status": (
            "development candidate; audit remains sealed"
            if unique
            else "HARD-GATE-FAILED / explore / not promoted / not live-ready"
        ),
        "evidence_role": "development only; researcher-exposed audit and prospective not read",
        "contract": {
            "development": f"[{COMMON_START.isoformat()}, {DEVELOPMENT_END.isoformat()})",
            "config_count": len(grid),
            "fee_per_fill": FEE,
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "gross_leverage_cap": 1.0,
        },
        "data_quality": quality,
        "counts": {
            "configs": len(rows),
            "daily_screen_pass": len(daily_screen),
            "unique_daily_screen_paths": len(detailed),
            "all_gates_pass": len(passing),
        },
        "best_growth": best_growth,
        "best_mdd_safe_growth": best_mdd_safe_growth,
        "unique_candidate": passing[0] if passing else None,
        "audit_revealed": False,
        "prospective_revealed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_be_rcr_p0_search_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(clean_json(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    pd.DataFrame(rows).to_csv(ARTIFACT_DIR / f"{stem}_grid.csv", index=False)
    pd.DataFrame(detailed).to_csv(ARTIFACT_DIR / f"{stem}_ordered_candidates.csv", index=False)
    if unique and retained:
        pd.DataFrame(retained.path).to_csv(
            ARTIFACT_DIR / f"{stem}_candidate_path.csv", index=False
        )
        pd.DataFrame(retained.trades).to_csv(
            ARTIFACT_DIR / f"{stem}_candidate_trades.csv", index=False
        )
    print(json.dumps(clean_json(payload["counts"]), ensure_ascii=False))
    print(json.dumps(clean_json(payload["best_growth"]), ensure_ascii=False))
    print(json.dumps(clean_json(payload["best_mdd_safe_growth"]), ensure_ascii=False))
    print(json.dumps(clean_json(payload["unique_candidate"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
