from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse
from strategy_lab.data.settings import load_settings


ROOT = Path("research/hype/15m-multi-timeframe-probe-pyramiding")
ARTIFACT_DIR = ROOT / "artifacts"
DATA_SCRIPT = Path(
    "research/hype/15m-multidimensional-trend-pyramiding/scripts/"
    "research_hype_15m_mdtp.py"
)
SYMBOL = "HYPE/USDT:USDT"
RUN_DATE = "2026-08-03"
PROSPECTIVE_START = pd.Timestamp("2026-08-02 00:00:00+00:00")
PROSPECTIVE_END = pd.Timestamp("2026-11-02 00:00:00+00:00")
FEE_RATE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
MAX_LEVERAGE = 3.0
RISK_BUDGETS = (0.01, 0.03, 0.10)
POLICIES = (
    "static_seed",
    "static_full",
    "profit_step",
    "timed_pyramid",
    "trader_full",
)
LAYER_FRACTIONS = (0.25, 0.50, 0.75, 1.00)
LAYER_THRESHOLDS_R = (0.0, 0.5, 1.0, 2.0)
MAX_HOLD_BARS = 14 * 24 * 4
ADD_COOLDOWN_BARS = 4 * 4
MIN_STOP_PCT = 0.015
MAX_STOP_PCT = 0.15
STOP_BUFFER = 0.0025
EPSILON = 1e-12


@dataclass(slots=True)
class Campaign:
    side: int
    entry_ts: pd.Timestamp
    entry_equity: float
    entry_price: float
    initial_stop: float
    stop: float
    r_price: float
    planned_full_qty: float
    quantity: float
    layer: int
    bars_held: int = 0
    last_add_bar: int = -10_000
    add_count: int = 0
    max_mfe_price: float = 0.0
    max_mfe_r: float = 0.0
    max_effective_leverage: float = 0.0


@dataclass(frozen=True, slots=True)
class RunResult:
    metrics: dict[str, Any]
    campaigns: pd.DataFrame
    actions: pd.DataFrame
    equity: pd.Series


def load_data_module() -> Any:
    spec = importlib.util.spec_from_file_location("hype_mtpp_data", DATA_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load data module: {DATA_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_data() -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    module = load_data_module()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    frame, funding, quality = module.load_symbol_data(
        warehouse, SYMBOL, require_raw_parity=True
    )
    if frame.index.max() >= PROSPECTIVE_START:
        raise RuntimeError("prospective OOS is present; refuse to compute")
    return frame, funding, quality


def wilder_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.astype(float).diff()
    gain = delta.clip(lower=0.0).ewm(
        alpha=1.0 / window, adjust=False, min_periods=window
    ).mean()
    loss = (-delta.clip(upper=0.0)).ewm(
        alpha=1.0 / window, adjust=False, min_periods=window
    ).mean()
    relative = gain / loss.replace(0.0, np.nan)
    result = 100.0 - 100.0 / (1.0 + relative)
    result = result.mask(loss.eq(0.0) & gain.gt(0.0), 100.0)
    return result.mask(loss.eq(0.0) & gain.eq(0.0), 50.0)


def kdj(frame: pd.DataFrame, window: int = 9) -> pd.DataFrame:
    low = frame["low"].rolling(window, min_periods=window).min()
    high = frame["high"].rolling(window, min_periods=window).max()
    rsv = 100.0 * (frame["close"] - low) / (high - low).replace(0.0, np.nan)
    k = rsv.ewm(alpha=1.0 / 3.0, adjust=False, min_periods=window).mean()
    d = k.ewm(alpha=1.0 / 3.0, adjust=False, min_periods=3).mean()
    return pd.DataFrame({"k": k, "d": d, "j": 3.0 * k - 2.0 * d})


def resample_complete(
    frame: pd.DataFrame,
    rule: str,
    expected_bars: int,
    duration: pd.Timedelta,
    *,
    origin: str | pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    kwargs: dict[str, Any] = {"label": "left", "closed": "left"}
    if origin is not None:
        kwargs["origin"] = origin
    grouped = frame.resample(rule, **kwargs)
    bars = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        source_bars=("close", "count"),
    )
    incomplete = bars.loc[bars["source_bars"].ne(expected_bars)]
    complete = bars.loc[bars["source_bars"].eq(expected_bars)].copy()
    invalid = complete["high"].lt(
        complete[["open", "close", "low"]].max(axis=1)
    ) | complete["low"].gt(complete[["open", "close", "high"]].min(axis=1))
    complete.index = complete.index + duration
    return complete, {
        "rows": int(len(complete)),
        "start_visible": complete.index.min().isoformat(),
        "end_visible": complete.index.max().isoformat(),
        "incomplete_bins_excluded": int(len(incomplete)),
        "invalid_ohlc_rows": int(invalid.sum()),
        "accepted": bool(not invalid.any()),
    }


def build_signals(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    bars: dict[str, pd.DataFrame] = {}
    quality: dict[str, Any] = {}
    specifications = {
        "15m": ("15min", 1, pd.Timedelta(minutes=15), None),
        "1h": ("1h", 4, pd.Timedelta(hours=1), None),
        "4h": ("4h", 16, pd.Timedelta(hours=4), None),
        "1d": ("1D", 96, pd.Timedelta(days=1), None),
        "1w": (
            "168h",
            672,
            pd.Timedelta(days=7),
            pd.Timestamp("1970-01-05 00:00:00+00:00"),
        ),
    }
    for name, (rule, expected, duration, origin) in specifications.items():
        bars[name], quality[name] = resample_complete(
            frame, rule, expected, duration, origin=origin
        )
        if not quality[name]["accepted"]:
            raise RuntimeError(f"{name} aggregation blocker: {quality[name]}")

    for name in ("15m", "1h", "4h"):
        bars[name]["rsi14"] = wilder_rsi(bars[name]["close"], 14)
        oscillator = kdj(bars[name])
        bars[name]["k"] = oscillator["k"]
        bars[name]["d"] = oscillator["d"]
        bars[name]["cross_up"] = bars[name]["k"].gt(bars[name]["d"]) & bars[
            name
        ]["k"].shift(1).le(bars[name]["d"].shift(1))
        bars[name]["cross_down"] = bars[name]["k"].lt(bars[name]["d"]) & bars[
            name
        ]["k"].shift(1).ge(bars[name]["d"].shift(1))

    bars["4h"]["swing_low_6"] = bars["4h"]["low"].rolling(
        6, min_periods=6
    ).min()
    bars["4h"]["swing_high_6"] = bars["4h"]["high"].rolling(
        6, min_periods=6
    ).max()
    bars["1d"]["direction"] = np.sign(
        bars["1d"]["close"] - bars["1d"]["close"].shift(7)
    )
    bars["1w"]["direction"] = np.sign(
        bars["1w"]["close"] - bars["1w"]["close"].shift(2)
    )

    execution_index = bars["15m"].index
    signals = pd.DataFrame(index=execution_index)
    signals["rsi_15m"] = bars["15m"]["rsi14"]
    signals["k_15m"] = bars["15m"]["k"]
    signals["d_15m"] = bars["15m"]["d"]
    signals["cross_up_15m"] = bars["15m"]["cross_up"].fillna(False)
    signals["cross_down_15m"] = bars["15m"]["cross_down"].fillna(False)

    mappings = {
        "rsi_1h": ("1h", "rsi14"),
        "k_1h": ("1h", "k"),
        "rsi_4h": ("4h", "rsi14"),
        "swing_low_6_4h": ("4h", "swing_low_6"),
        "swing_high_6_4h": ("4h", "swing_high_6"),
        "direction_1d": ("1d", "direction"),
        "direction_1w": ("1w", "direction"),
    }
    for output, (timeframe, column) in mappings.items():
        signals[output] = bars[timeframe][column].reindex(
            execution_index, method="ffill"
        )

    signals["long_bias"] = signals["direction_1d"].eq(1.0) & signals[
        "direction_1w"
    ].eq(1.0)
    signals["short_bias"] = signals["direction_1d"].eq(-1.0) & signals[
        "direction_1w"
    ].eq(-1.0)
    common_location = signals["rsi_1h"].between(40.0, 60.0)
    signals["long_trigger"] = (
        signals["long_bias"]
        & signals["rsi_4h"].ge(50.0)
        & common_location
        & signals["k_1h"].le(55.0)
        & signals["rsi_15m"].le(55.0)
        & signals["cross_up_15m"]
    )
    signals["short_trigger"] = (
        signals["short_bias"]
        & signals["rsi_4h"].le(50.0)
        & common_location
        & signals["k_1h"].ge(45.0)
        & signals["rsi_15m"].ge(45.0)
        & signals["cross_down_15m"]
    )
    signals["long_opposite_bias"] = signals["direction_1d"].eq(
        -1.0
    ) & signals["direction_1w"].eq(-1.0)
    signals["short_opposite_bias"] = signals["direction_1d"].eq(
        1.0
    ) & signals["direction_1w"].eq(1.0)
    quality["availability_semantics"] = (
        "all feature timestamps equal the earliest next-15m-open execution time; "
        "higher timeframes are shifted by their full duration"
    )
    return signals, quality


def adverse_fill(raw_price: float, delta_quantity: float, slippage: float) -> float:
    return raw_price * (1.0 + math.copysign(slippage, delta_quantity))


def initial_stop(signal: pd.Series, entry: float, side: int) -> float | None:
    structure = (
        float(signal["swing_low_6_4h"])
        if side > 0
        else float(signal["swing_high_6_4h"])
    )
    if not np.isfinite(structure):
        return None
    if side > 0:
        raw = structure * (1.0 - STOP_BUFFER)
        stop = min(raw, entry * (1.0 - MIN_STOP_PCT))
        distance_pct = (entry - stop) / entry
    else:
        raw = structure * (1.0 + STOP_BUFFER)
        stop = max(raw, entry * (1.0 + MIN_STOP_PCT))
        distance_pct = (stop - entry) / entry
    if distance_pct <= 0.0 or distance_pct > MAX_STOP_PCT:
        return None
    return float(stop)


def _target_fraction(policy: str, campaign: Campaign, signal: pd.Series, bar_no: int) -> float:
    if policy == "static_seed":
        return LAYER_FRACTIONS[0]
    if policy == "static_full":
        return LAYER_FRACTIONS[-1]
    next_layer = min(campaign.layer + 1, len(LAYER_FRACTIONS) - 1)
    if next_layer == campaign.layer:
        return LAYER_FRACTIONS[campaign.layer]
    if campaign.max_mfe_r + EPSILON < LAYER_THRESHOLDS_R[next_layer]:
        return LAYER_FRACTIONS[campaign.layer]
    if bar_no - campaign.last_add_bar < ADD_COOLDOWN_BARS:
        return LAYER_FRACTIONS[campaign.layer]
    if policy in {"timed_pyramid", "trader_full"}:
        trigger = bool(
            signal["long_trigger"] if campaign.side > 0 else signal["short_trigger"]
        )
        if not trigger:
            return LAYER_FRACTIONS[campaign.layer]
    return LAYER_FRACTIONS[next_layer]


def _updated_stop(
    policy: str,
    campaign: Campaign,
    signal: pd.Series,
    open_price: float,
) -> float:
    if policy != "trader_full" or campaign.max_mfe_r < 1.0:
        return campaign.stop
    side = campaign.side
    if side > 0:
        candidate = max(
            campaign.stop,
            campaign.entry_price - 0.25 * campaign.r_price,
        )
        structure = float(signal["swing_low_6_4h"])
        if np.isfinite(structure):
            candidate = max(candidate, structure * (1.0 - STOP_BUFFER))
        if campaign.max_mfe_r >= 2.0:
            candidate = max(
                candidate,
                campaign.entry_price + 0.5 * campaign.max_mfe_price,
            )
        return min(candidate, open_price) if open_price > campaign.stop else candidate
    candidate = min(
        campaign.stop,
        campaign.entry_price + 0.25 * campaign.r_price,
    )
    structure = float(signal["swing_high_6_4h"])
    if np.isfinite(structure):
        candidate = min(candidate, structure * (1.0 + STOP_BUFFER))
    if campaign.max_mfe_r >= 2.0:
        candidate = min(
            candidate,
            campaign.entry_price - 0.5 * campaign.max_mfe_price,
        )
    return max(candidate, open_price) if open_price < campaign.stop else candidate


def run_backtest(
    frame: pd.DataFrame,
    funding: pd.Series,
    signals: pd.DataFrame,
    *,
    side: int,
    policy: str,
    risk_budget: float,
    fee_rate: float = FEE_RATE,
    slippage: float = BASE_SLIPPAGE,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    forced_entry: pd.Timestamp | None = None,
    stop_after_one: bool = False,
) -> RunResult:
    if side not in (-1, 1):
        raise ValueError("side must be -1 or 1")
    if policy not in POLICIES:
        raise ValueError(f"unknown policy: {policy}")
    selected = frame
    if start is not None:
        selected = selected.loc[selected.index >= start]
    if end is not None:
        selected = selected.loc[selected.index < end]
    if forced_entry is not None:
        selected = selected.loc[selected.index >= forced_entry]
    if selected.empty:
        return RunResult({}, pd.DataFrame(), pd.DataFrame(), pd.Series(dtype=float))

    equity = 1.0
    quantity = 0.0
    campaign: Campaign | None = None
    previous_close = float(selected.iloc[0]["open"])
    equity_points: list[tuple[pd.Timestamp, float]] = []
    campaign_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    turnover = fees = slippage_cost = funding_pnl = 0.0
    max_fill_leverage = max_effective_leverage = 0.0
    forced_consumed = False

    def transact(ts: pd.Timestamp, raw: float, target_qty: float, action: str) -> None:
        nonlocal equity, quantity, turnover, fees, slippage_cost, max_fill_leverage
        delta = target_qty - quantity
        if abs(delta) <= EPSILON:
            return
        fill = adverse_fill(raw, delta, slippage)
        notional = abs(delta) * raw
        fill_fee = notional * fee_rate
        fill_slippage = abs(delta) * abs(fill - raw)
        equity -= fill_fee + fill_slippage
        fees += fill_fee
        slippage_cost += fill_slippage
        turnover += notional
        fill_lev = abs(target_qty) * raw / max(equity, EPSILON)
        max_fill_leverage = max(max_fill_leverage, fill_lev)
        action_rows.append(
            {
                "ts": ts,
                "action": action,
                "raw_price": raw,
                "fill_price": fill,
                "delta_quantity": delta,
                "quantity_after": target_qty,
                "equity_after_cost": equity,
                "fill_leverage": fill_lev,
            }
        )
        quantity = target_qty

    def close_campaign(ts: pd.Timestamp, raw: float, reason: str) -> None:
        nonlocal campaign, quantity
        if campaign is None:
            return
        closed = campaign
        transact(ts, raw, 0.0, f"exit_{reason}")
        pnl = equity - closed.entry_equity
        signed_move = side * (raw - closed.entry_price)
        capture = (
            signed_move / closed.max_mfe_price
            if closed.max_mfe_price > EPSILON
            else math.nan
        )
        campaign_rows.append(
            {
                "entry_ts": closed.entry_ts,
                "exit_ts": ts,
                "side": "long" if side > 0 else "short",
                "policy": policy,
                "risk_budget": risk_budget,
                "entry_price": closed.entry_price,
                "exit_price": raw,
                "initial_stop": closed.initial_stop,
                "r_price": closed.r_price,
                "planned_full_qty": closed.planned_full_qty,
                "pnl": pnl,
                "pnl_pct_entry_equity": pnl / max(closed.entry_equity, EPSILON),
                "hold_hours": (ts - closed.entry_ts).total_seconds() / 3600.0,
                "exit_reason": reason,
                "add_count": closed.add_count,
                "max_layer": closed.layer,
                "max_mfe_r": closed.max_mfe_r,
                "price_capture_ratio": capture,
                "max_effective_leverage": closed.max_effective_leverage,
            }
        )
        campaign = None
        quantity = 0.0

    for bar_no, (ts, bar) in enumerate(selected.iterrows()):
        open_price = float(bar["open"])
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        equity += quantity * (open_price - previous_close)
        signal = signals.loc[ts] if ts in signals.index else None

        if campaign is not None:
            gap_hit = (
                side > 0 and open_price <= campaign.stop
            ) or (side < 0 and open_price >= campaign.stop)
            if gap_hit:
                close_campaign(ts, open_price, "stop_gap")

        if campaign is not None and signal is not None:
            campaign.bars_held += 1
            opposite = bool(
                signal["long_opposite_bias"]
                if side > 0
                else signal["short_opposite_bias"]
            )
            if opposite:
                close_campaign(ts, open_price, "opposite_daily_weekly_bias")
            elif campaign.bars_held >= MAX_HOLD_BARS:
                close_campaign(ts, open_price, "timeout_14d")

        if campaign is not None and signal is not None:
            updated = _updated_stop(policy, campaign, signal, open_price)
            if (side > 0 and updated >= open_price) or (side < 0 and updated <= open_price):
                close_campaign(ts, open_price, "updated_stop_gap")
            else:
                campaign.stop = updated

        if campaign is not None and signal is not None:
            marked_profit = equity - campaign.entry_equity
            target_fraction = _target_fraction(policy, campaign, signal, bar_no)
            current_fraction = LAYER_FRACTIONS[campaign.layer]
            if target_fraction > current_fraction and marked_profit > 0.0:
                next_layer = LAYER_FRACTIONS.index(target_fraction)
                target_qty = side * campaign.planned_full_qty * target_fraction
                transact(ts, open_price, target_qty, f"add_layer_{next_layer}")
                campaign.layer = next_layer
                campaign.last_add_bar = bar_no
                campaign.add_count += 1

        can_enter = campaign is None and signal is not None
        if forced_entry is not None:
            can_enter &= ts == forced_entry and not forced_consumed
        if can_enter:
            trigger = bool(signal["long_trigger"] if side > 0 else signal["short_trigger"])
            if trigger:
                stop = initial_stop(signal, open_price, side)
                if stop is not None:
                    r_price = abs(open_price - stop)
                    roundtrip_unit_cost = open_price * 2.0 * (fee_rate + slippage)
                    risk_qty = risk_budget * equity / (r_price + roundtrip_unit_cost)
                    leverage_qty = (
                        MAX_LEVERAGE
                        * equity
                        / (
                            open_price
                            * (1.0 + MAX_LEVERAGE * (fee_rate + slippage))
                        )
                    )
                    full_qty = min(risk_qty, leverage_qty)
                    initial_fraction = (
                        1.0 if policy == "static_full" else LAYER_FRACTIONS[0]
                    )
                    campaign = Campaign(
                        side=side,
                        entry_ts=ts,
                        entry_equity=equity,
                        entry_price=open_price,
                        initial_stop=stop,
                        stop=stop,
                        r_price=r_price,
                        planned_full_qty=full_qty,
                        quantity=side * full_qty * initial_fraction,
                        layer=(len(LAYER_FRACTIONS) - 1 if policy == "static_full" else 0),
                        last_add_bar=bar_no,
                    )
                    transact(ts, open_price, campaign.quantity, "entry")
                    forced_consumed = True

        stopped = False
        if campaign is not None:
            stop_hit = (side > 0 and low <= campaign.stop) or (
                side < 0 and high >= campaign.stop
            )
            if stop_hit:
                raw_stop = campaign.stop
                equity += quantity * (raw_stop - open_price)
                close_campaign(ts, raw_stop, "stop_intrabar")
                stopped = True

        if campaign is not None and not stopped:
            equity += quantity * (close - open_price)
            favorable = (
                high - campaign.entry_price
                if side > 0
                else campaign.entry_price - low
            )
            campaign.max_mfe_price = max(campaign.max_mfe_price, favorable, 0.0)
            campaign.max_mfe_r = campaign.max_mfe_price / campaign.r_price
            rate = float(funding.reindex([ts]).fillna(0.0).iloc[0])
            payment = -side * abs(quantity) * close * rate
            equity += payment
            funding_pnl += payment
            effective = abs(quantity) * close / max(equity, EPSILON)
            campaign.max_effective_leverage = max(
                campaign.max_effective_leverage, effective
            )
            max_effective_leverage = max(max_effective_leverage, effective)

        equity_points.append((ts, equity))
        previous_close = close
        if stop_after_one and forced_consumed and campaign is None:
            break

    if campaign is not None:
        final_ts = selected.index[-1]
        close_campaign(final_ts, float(selected.iloc[-1]["close"]), "data_end")
        if equity_points:
            equity_points[-1] = (final_ts, equity)

    equity_series = pd.Series(
        [value for _, value in equity_points],
        index=pd.DatetimeIndex([ts for ts, _ in equity_points]),
        name="equity",
        dtype=float,
    )
    campaign_frame = pd.DataFrame(campaign_rows)
    action_frame = pd.DataFrame(action_rows)
    metrics = compute_metrics(
        equity_series,
        campaign_frame,
        turnover=turnover,
        fees=fees,
        slippage_cost=slippage_cost,
        funding_pnl=funding_pnl,
        max_fill_leverage=max_fill_leverage,
        max_effective_leverage=max_effective_leverage,
    )
    metrics.update(
        {
            "side": "long" if side > 0 else "short",
            "policy": policy,
            "risk_budget": risk_budget,
            "fee_rate": fee_rate,
            "slippage": slippage,
        }
    )
    return RunResult(metrics, campaign_frame, action_frame, equity_series)


def compute_metrics(
    equity: pd.Series,
    campaigns: pd.DataFrame,
    *,
    turnover: float,
    fees: float,
    slippage_cost: float,
    funding_pnl: float,
    max_fill_leverage: float,
    max_effective_leverage: float,
) -> dict[str, Any]:
    if equity.empty:
        return {}
    returns = equity.pct_change().fillna(equity.iloc[0] - 1.0)
    volatility = float(returns.std(ddof=0))
    sharpe = (
        0.0
        if volatility <= EPSILON
        else float(returns.mean() / volatility * math.sqrt(365.0 * 96.0))
    )
    drawdown = equity / equity.cummax() - 1.0
    years = max(
        (equity.index[-1] - equity.index[0]).total_seconds() / (365.0 * 86400.0),
        1.0 / 365.0,
    )
    if campaigns.empty:
        wins = avg_hold = median_hold = max_hold = worst = avg_capture = 0.0
        adds = reached_half = reached_one = reached_two = 0
        reasons: dict[str, int] = {}
    else:
        wins = float(campaigns["pnl"].gt(0.0).mean())
        avg_hold = float(campaigns["hold_hours"].mean())
        median_hold = float(campaigns["hold_hours"].median())
        max_hold = float(campaigns["hold_hours"].max())
        worst = float(campaigns["pnl_pct_entry_equity"].min())
        capture = campaigns.loc[
            campaigns["max_mfe_r"].gt(0.0), "price_capture_ratio"
        ].replace([np.inf, -np.inf], np.nan).dropna()
        avg_capture = float(capture.mean()) if not capture.empty else 0.0
        adds = int(campaigns["add_count"].sum())
        reached_half = int(campaigns["max_mfe_r"].ge(0.5).sum())
        reached_one = int(campaigns["max_mfe_r"].ge(1.0).sum())
        reached_two = int(campaigns["max_mfe_r"].ge(2.0).sum())
        reasons = {
            str(key): int(value)
            for key, value in campaigns["exit_reason"].value_counts().items()
        }
    return {
        "net_return": float(equity.iloc[-1] - 1.0),
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
        "campaigns": int(len(campaigns)),
        "win_rate": wins,
        "avg_hold_hours": avg_hold,
        "median_hold_hours": median_hold,
        "max_hold_hours": max_hold,
        "worst_campaign_return": worst,
        "avg_price_capture_ratio": avg_capture,
        "add_count": adds,
        "reached_0_5r": reached_half,
        "reached_1r": reached_one,
        "reached_2r": reached_two,
        "exit_reasons": reasons,
        "annual_turnover_multiple": turnover / years,
        "fees_equity": fees,
        "slippage_equity": slippage_cost,
        "funding_pnl_equity": funding_pnl,
        "max_fill_leverage": max_fill_leverage,
        "max_effective_leverage": max_effective_leverage,
        "fill_leverage_breach": bool(max_fill_leverage > MAX_LEVERAGE + 1e-8),
        "effective_leverage_breach": bool(
            max_effective_leverage > MAX_LEVERAGE + 1e-8
        ),
    }


def recent_slices(equity: pd.Series) -> dict[str, dict[str, float | int]]:
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
    }
    rows: dict[str, dict[str, float | int]] = {}
    if equity.empty:
        return rows
    end = equity.index[-1]
    for name, duration in windows.items():
        part = equity.loc[equity.index >= end - duration]
        if len(part) < 2:
            rows[name] = {"rows": int(len(part)), "return": 0.0}
        else:
            rows[name] = {
                "rows": int(len(part)),
                "return": float(part.iloc[-1] / part.iloc[0] - 1.0),
            }
    return rows


def contiguous_blocks(index: pd.DatetimeIndex, count: int = 5) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    edges = pd.date_range(index.min(), index.max() + pd.Timedelta(minutes=15), periods=count + 1)
    return [(edges[i], edges[i + 1]) for i in range(count)]


def generate_event_entries(
    frame: pd.DataFrame, signals: pd.DataFrame, side: int, minimum_spacing_hours: int = 24
) -> list[pd.Timestamp]:
    trigger_column = "long_trigger" if side > 0 else "short_trigger"
    candidates = signals.index[signals[trigger_column].fillna(False)]
    valid_index = frame.index.intersection(candidates)
    entries: list[pd.Timestamp] = []
    last: pd.Timestamp | None = None
    for ts in valid_index:
        if last is not None and ts < last + pd.Timedelta(hours=minimum_spacing_hours):
            continue
        signal = signals.loc[ts]
        price = float(frame.loc[ts, "open"])
        if initial_stop(signal, price, side) is None:
            continue
        entries.append(ts)
        last = ts
    return entries


def paired_event_study(
    frame: pd.DataFrame,
    funding: pd.Series,
    signals: pd.DataFrame,
    *,
    side: int,
    risk_budget: float = 0.03,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for event_id, ts in enumerate(generate_event_entries(frame, signals, side)):
        for policy in POLICIES:
            run = run_backtest(
                frame,
                funding,
                signals,
                side=side,
                policy=policy,
                risk_budget=risk_budget,
                forced_entry=ts,
                stop_after_one=True,
            )
            if run.campaigns.empty:
                continue
            row = run.campaigns.iloc[0]
            rows.append(
                {
                    "event_id": event_id,
                    "entry_ts": ts,
                    "side": "long" if side > 0 else "short",
                    "policy": policy,
                    "pnl_pct_entry_equity": float(row["pnl_pct_entry_equity"]),
                    "hold_hours": float(row["hold_hours"]),
                    "add_count": int(row["add_count"]),
                    "max_mfe_r": float(row["max_mfe_r"]),
                    "price_capture_ratio": float(row["price_capture_ratio"]),
                    "exit_reason": str(row["exit_reason"]),
                }
            )
    return pd.DataFrame(rows)


def paired_summary(events: pd.DataFrame) -> dict[str, Any]:
    if events.empty:
        return {}
    pivot = events.pivot(index="event_id", columns="policy", values="pnl_pct_entry_equity")
    comparisons = {}
    for left, right in (
        ("trader_full", "static_seed"),
        ("trader_full", "timed_pyramid"),
        ("timed_pyramid", "profit_step"),
    ):
        pair = pivot[[left, right]].dropna()
        delta = pair[left] - pair[right]
        timestamps = (
            events.drop_duplicates("event_id").set_index("event_id")["entry_ts"]
        )
        paired = pd.DataFrame({"delta": delta}).join(timestamps, how="left")
        if not paired.empty:
            elapsed = paired["entry_ts"] - paired["entry_ts"].min()
            paired["block"] = (elapsed.dt.total_seconds() // (14 * 86400)).astype(int)
            grouped = {
                int(block): values["delta"].to_numpy(float)
                for block, values in paired.groupby("block")
            }
            rng = np.random.default_rng(20260803)
            block_keys = np.array(list(grouped), dtype=int)
            draws = np.empty(5_000, dtype=float)
            for draw in range(len(draws)):
                sampled = rng.choice(block_keys, size=len(block_keys), replace=True)
                values = np.concatenate([grouped[int(key)] for key in sampled])
                draws[draw] = float(values.mean())
            ci = np.quantile(draws, [0.025, 0.975])
            ci_low, ci_high = float(ci[0]), float(ci[1])
            independent_blocks = int(len(block_keys))
        else:
            ci_low = ci_high = math.nan
            independent_blocks = 0
        comparisons[f"{left}_minus_{right}"] = {
            "events": int(len(delta)),
            "independent_14d_blocks": independent_blocks,
            "mean_delta": float(delta.mean()) if len(delta) else math.nan,
            "median_delta": float(delta.median()) if len(delta) else math.nan,
            "positive_share": float(delta.gt(0.0).mean()) if len(delta) else math.nan,
            "block_bootstrap_ci_95": [ci_low, ci_high],
        }
    return comparisons


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(f"cannot serialize {type(value)!r}")


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, source_quality = load_data()
    signals, aggregate_quality = build_signals(frame)
    aligned_signals = signals.reindex(frame.index)
    runs: dict[str, RunResult] = {}
    metric_rows: list[dict[str, Any]] = []
    for side in (1, -1):
        side_name = "long" if side > 0 else "short"
        for risk in RISK_BUDGETS:
            for policy in POLICIES:
                key = f"{side_name}_{int(risk * 100)}pct_{policy}"
                run = run_backtest(
                    frame,
                    funding,
                    aligned_signals,
                    side=side,
                    policy=policy,
                    risk_budget=risk,
                )
                runs[key] = run
                metric_rows.append({"run": key, **run.metrics})
                run.campaigns.to_csv(
                    ARTIFACT_DIR / f"hype_15m_mtpp_{key}_{RUN_DATE}_campaigns.csv",
                    index=False,
                )
                run.actions.to_csv(
                    ARTIFACT_DIR / f"hype_15m_mtpp_{key}_{RUN_DATE}_actions.csv",
                    index=False,
                )
                run.equity.rename("equity").to_frame().to_parquet(
                    ARTIFACT_DIR / f"hype_15m_mtpp_{key}_{RUN_DATE}_equity.parquet"
                )

    cost_ladder: dict[str, Any] = {}
    recent: dict[str, Any] = {}
    for side in (1, -1):
        side_name = "long" if side > 0 else "short"
        for risk in RISK_BUDGETS:
            label = f"{side_name}_{int(risk * 100)}pct"
            gross = run_backtest(
                frame,
                funding * 0.0,
                aligned_signals,
                side=side,
                policy="trader_full",
                risk_budget=risk,
                fee_rate=0.0,
                slippage=0.0,
            )
            base = runs[f"{label}_trader_full"]
            stress = run_backtest(
                frame,
                funding,
                aligned_signals,
                side=side,
                policy="trader_full",
                risk_budget=risk,
                slippage=STRESS_SLIPPAGE,
            )
            cost_ladder[label] = {
                "gross": gross.metrics,
                "base": base.metrics,
                "stress": stress.metrics,
            }
            recent[label] = recent_slices(base.equity)

    blocks: list[dict[str, Any]] = []
    for start, end in contiguous_blocks(frame.index, 5):
        for side in (1, -1):
            for risk in RISK_BUDGETS:
                for policy in POLICIES:
                    result = run_backtest(
                        frame,
                        funding,
                        aligned_signals,
                        side=side,
                        policy=policy,
                        risk_budget=risk,
                        start=start,
                        end=end,
                    )
                    blocks.append(
                        {
                            "start": start,
                            "end": end,
                            "side": "long" if side > 0 else "short",
                            "risk_budget": risk,
                            **result.metrics,
                        }
                    )

    event_outputs: dict[str, Any] = {}
    for side in (1, -1):
        side_name = "long" if side > 0 else "short"
        events = paired_event_study(
            frame, funding, aligned_signals, side=side, risk_budget=0.03
        )
        events.to_csv(
            ARTIFACT_DIR / f"hype_15m_mtpp_{side_name}_paired_events_{RUN_DATE}.csv",
            index=False,
        )
        event_outputs[side_name] = {
            "events": int(events["event_id"].nunique()) if not events.empty else 0,
            "comparisons": paired_summary(events),
        }

    metrics_frame = pd.DataFrame(metric_rows)
    metrics_frame.to_csv(
        ARTIFACT_DIR / f"hype_15m_mtpp_policy_metrics_{RUN_DATE}.csv", index=False
    )
    pd.DataFrame(blocks).to_csv(
        ARTIFACT_DIR / f"hype_15m_mtpp_contiguous_blocks_{RUN_DATE}.csv", index=False
    )

    payload = {
        "family": "HYPE-15M-Multi-Timeframe-Probe-Pyramiding",
        "alias": "HYPE-15M-MTPP",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "run_date": RUN_DATE,
        "data_contract": {
            "symbol": SYMBOL,
            "source_quality": source_quality,
            "aggregate_quality": aggregate_quality,
            "execution_rows": int(len(frame)),
            "execution_start": frame.index.min(),
            "execution_end": frame.index.max(),
            "prospective_oos": {
                "start": PROSPECTIVE_START,
                "end": PROSPECTIVE_END,
                "read": False,
            },
        },
        "frozen_rules": {
            "risk_budgets": RISK_BUDGETS,
            "max_leverage": MAX_LEVERAGE,
            "layer_fractions": LAYER_FRACTIONS,
            "layer_thresholds_r": LAYER_THRESHOLDS_R,
            "max_hold_bars": MAX_HOLD_BARS,
            "fee_rate": FEE_RATE,
            "base_slippage": BASE_SLIPPAGE,
            "stress_slippage": STRESS_SLIPPAGE,
        },
        "policy_metrics": metric_rows,
        "cost_ladder": cost_ladder,
        "recent_slices": recent,
        "contiguous_blocks": blocks,
        "paired_event_study_3pct": event_outputs,
        "limitations": [
            "HYPE Binance history is short and was already viewed by adjacent research; this is not untouched OOS.",
            "RSI/KDJ rules are a frozen mechanical proxy for discretionary chart timing, not a claim to reproduce human judgment fully.",
            "The paired event study uses entries spaced by 24h and can retain overlapping 14d forward paths; use it only for within-entry attribution.",
        ],
    }
    with (ARTIFACT_DIR / f"hype_15m_mtpp_research_{RUN_DATE}.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=json_default)
    print(metrics_frame.to_string(index=False))
    print(json.dumps(event_outputs, ensure_ascii=False, indent=2, default=json_default))


if __name__ == "__main__":
    main()
