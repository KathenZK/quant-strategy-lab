from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse
from strategy_lab.data.settings import load_settings


ROOT = Path("research/hype/15m-multidimensional-trend-pyramiding")
ARTIFACT_DIR = ROOT / "artifacts"
V1_SCRIPT = ROOT / "scripts/research_hype_15m_mdtp.py"
RUN_DATE = "2026-08-02"
SYMBOL = "HYPE/USDT:USDT"
TRAIN_START = pd.Timestamp("2025-05-30 10:30:00+00:00")
TRAIN_END = pd.Timestamp("2026-02-01 00:00:00+00:00")
VALIDATION_START = pd.Timestamp("2026-02-15 00:00:00+00:00")
VALIDATION_END = pd.Timestamp("2026-08-02 00:00:00+00:00")
PROSPECTIVE_START = pd.Timestamp("2026-08-02 00:00:00+00:00")
PROSPECTIVE_END = pd.Timestamp("2026-11-02 00:00:00+00:00")
TRAIN_FOLDS = (
    (
        pd.Timestamp("2025-06-15 00:00:00+00:00"),
        pd.Timestamp("2025-09-01 00:00:00+00:00"),
    ),
    (
        pd.Timestamp("2025-09-01 00:00:00+00:00"),
        pd.Timestamp("2025-11-15 00:00:00+00:00"),
    ),
    (pd.Timestamp("2025-11-15 00:00:00+00:00"), TRAIN_END),
)
FEE_RATE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
RISK_FRACTION = 0.01
DISASTER_FRACTION = 0.03
MAX_LEVERAGE = 3.0
LAYER_FRACTIONS = (0.35, 0.70, 0.85, 1.00)


@dataclass(frozen=True, slots=True)
class CandidateConfig:
    regime_ema_4h: int
    entry_donchian_1h: int
    stop_atr_1h: float
    exit_donchian_4h: int

    @property
    def label(self) -> str:
        return (
            f"r{self.regime_ema_4h}_e{self.entry_donchian_1h}"
            f"_s{self.stop_atr_1h:g}_x{self.exit_donchian_4h}"
        )


@dataclass(frozen=True, slots=True)
class Variant:
    name: str = "full"
    allow_core: bool = True
    allow_pyramid: bool = True
    use_mfe_floor: bool = True
    use_structural_stop: bool = True


@dataclass(slots=True)
class Campaign:
    side: int
    entry_ts: pd.Timestamp
    entry_equity: float
    r0: float
    entry_boundary: float
    initial_stop: float
    stop: float
    planned_full_qty: float
    quantity: float
    average_entry: float
    layer: int
    peak_net_profit: float = 0.0
    bars_held: int = 0
    add_count: int = 0
    max_open_risk: float = 0.0
    max_effective_leverage: float = 0.0
    state: str = "SEED"


@dataclass(frozen=True, slots=True)
class BacktestResult:
    metrics: dict[str, Any]
    trades: pd.DataFrame
    equity: pd.Series
    actions: pd.DataFrame


def load_v1_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "hype_15m_mdtp_v1_campaign", V1_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {V1_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous = frame["close"].shift(1)
    return pd.concat(
        (
            frame["high"] - frame["low"],
            (frame["high"] - previous).abs(),
            (frame["low"] - previous).abs(),
        ),
        axis=1,
    ).max(axis=1)


def resample_complete(
    frame: pd.DataFrame, rule: str, expected_bars: int
) -> pd.DataFrame:
    grouped = frame.resample(rule, label="left", closed="left")
    bars = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        bar_count=("open", "count"),
    )
    return bars.loc[bars["bar_count"].eq(expected_bars)].dropna(
        subset=["open", "high", "low", "close"]
    )


def build_base_features(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    h1 = resample_complete(frame, "1h", 4)
    h4 = resample_complete(frame, "4h", 16)
    h1["atr24"] = true_range(h1).rolling(24, min_periods=24).mean()
    for window in (24, 48, 72, 96):
        h1[f"prior_high_{window}"] = (
            h1["high"].shift(1).rolling(window, min_periods=window).max()
        )
        h1[f"prior_low_{window}"] = (
            h1["low"].shift(1).rolling(window, min_periods=window).min()
        )
    for window in (30, 42, 60):
        h4[f"ema_{window}"] = (
            h4["close"]
            .ewm(
                span=window,
                adjust=False,
                min_periods=window,
            )
            .mean()
        )
        h4[f"ema_{window}_lag3"] = h4[f"ema_{window}"].shift(3)
    for window in (18, 30, 42):
        h4[f"prior_high_{window}"] = (
            h4["high"].shift(1).rolling(window, min_periods=window).max()
        )
        h4[f"prior_low_{window}"] = (
            h4["low"].shift(1).rolling(window, min_periods=window).min()
        )
    h1.index = h1.index + pd.Timedelta(hours=1)
    h4.index = h4.index + pd.Timedelta(hours=4)
    return {"h1": h1, "h4": h4}


def build_signal_events(
    base: dict[str, pd.DataFrame],
    config: CandidateConfig,
    side: int,
) -> pd.DataFrame:
    h1 = base["h1"].copy().reset_index(names="execution_ts")
    h4_columns = [
        "close",
        f"ema_{config.regime_ema_4h}",
        f"ema_{config.regime_ema_4h}_lag3",
        f"prior_high_{config.exit_donchian_4h}",
        f"prior_low_{config.exit_donchian_4h}",
    ]
    h4 = base["h4"][h4_columns].copy().reset_index(names="h4_execution_ts")
    events = pd.merge_asof(
        h1.sort_values("execution_ts"),
        h4.sort_values("h4_execution_ts"),
        left_on="execution_ts",
        right_on="h4_execution_ts",
        direction="backward",
        suffixes=("_1h", "_4h"),
    ).set_index("execution_ts")
    ema = events[f"ema_{config.regime_ema_4h}"]
    ema_lag = events[f"ema_{config.regime_ema_4h}_lag3"]
    if side > 0:
        events["regime_same"] = events["close_4h"].gt(ema) & ema.gt(ema_lag)
        events["regime_opposite"] = events["close_4h"].lt(ema) & ema.lt(ema_lag)
        events["entry_signal"] = events["close_1h"].gt(
            events[f"prior_high_{config.entry_donchian_1h}"]
        )
        events["entry_boundary"] = events[f"prior_high_{config.entry_donchian_1h}"]
        events["initial_structure"] = events["prior_low_24"] - 0.25 * events["atr24"]
        events["structural_stop"] = events[f"prior_low_{config.exit_donchian_4h}"]
        events["add_1_signal"] = events["close_1h"].gt(events["prior_high_24"])
        events["add_2_signal"] = events["close_1h"].gt(events["prior_high_48"])
    else:
        events["regime_same"] = events["close_4h"].lt(ema) & ema.lt(ema_lag)
        events["regime_opposite"] = events["close_4h"].gt(ema) & ema.gt(ema_lag)
        events["entry_signal"] = events["close_1h"].lt(
            events[f"prior_low_{config.entry_donchian_1h}"]
        )
        events["entry_boundary"] = events[f"prior_low_{config.entry_donchian_1h}"]
        events["initial_structure"] = events["prior_high_24"] + 0.25 * events["atr24"]
        events["structural_stop"] = events[f"prior_high_{config.exit_donchian_4h}"]
        events["add_1_signal"] = events["close_1h"].lt(events["prior_low_24"])
        events["add_2_signal"] = events["close_1h"].lt(events["prior_low_48"])
    events["entry_signal"] &= events["regime_same"]
    return events


def adverse_fill(raw_price: float, delta_quantity: float, slippage: float) -> float:
    return raw_price * (1.0 + math.copysign(slippage, delta_quantity))


def compute_metrics(
    equity: pd.Series,
    trades: pd.DataFrame,
    *,
    conservative_mdd: float,
    turnover_multiple: float,
    fees: float,
    slippage_cost: float,
    funding: float,
    max_fill_leverage: float,
    max_effective_leverage: float,
    max_open_risk_fraction: float,
    risk_breaches: int,
    action_counts: dict[str, int],
) -> dict[str, Any]:
    if equity.empty:
        return {}
    returns = equity.pct_change().fillna(equity.iloc[0] - 1.0)
    years = max(
        (equity.index[-1] - equity.index[0]).total_seconds() / (365.0 * 86400.0),
        1.0 / 365.0,
    )
    total_return = float(equity.iloc[-1] - 1.0)
    cagr = (
        float(equity.iloc[-1] ** (1.0 / years) - 1.0) if equity.iloc[-1] > 0 else -1.0
    )
    volatility = float(returns.std(ddof=0))
    sharpe = (
        0.0
        if volatility == 0.0
        else float(returns.mean() / volatility * math.sqrt(365 * 96))
    )
    if trades.empty:
        win_rate = profit_factor = avg_hold = median_hold = avg_capture = 0.0
        adds = 0
        worst_trade = 0.0
    else:
        pnl = pd.to_numeric(trades["net_pnl"], errors="coerce")
        wins = pnl.loc[pnl.gt(0.0)]
        losses = pnl.loc[pnl.le(0.0)]
        win_rate = float(pnl.gt(0.0).mean())
        profit_factor = (
            float(wins.sum() / abs(losses.sum())) if losses.sum() < 0 else math.inf
        )
        avg_hold = float(trades["hold_hours"].mean())
        median_hold = float(trades["hold_hours"].median())
        avg_capture = float(
            trades.loc[trades["peak_net_profit"].gt(0), "capture_ratio"].mean()
        )
        adds = int(trades["add_count"].sum())
        worst_trade = float(trades["net_return"].min())
    return {
        "start": equity.index[0].isoformat(),
        "end": equity.index[-1].isoformat(),
        "years": round(years, 4),
        "total_return_pct": round(total_return * 100.0, 4),
        "cagr_pct": round(cagr * 100.0, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown_pct": round(conservative_mdd * 100.0, 4),
        "trades": int(len(trades)),
        "win_rate_pct": round(win_rate * 100.0, 4),
        "profit_factor": "inf"
        if not np.isfinite(profit_factor)
        else round(profit_factor, 4),
        "avg_hold_hours": round(avg_hold, 4),
        "median_hold_hours": round(median_hold, 4),
        "avg_capture_ratio": round(avg_capture, 4)
        if np.isfinite(avg_capture)
        else None,
        "add_count": adds,
        "turnover_multiple": round(turnover_multiple, 4),
        "turnover_annualized": round(turnover_multiple / years, 4),
        "fee_pct_initial": round(fees * 100.0, 4),
        "slippage_pct_initial": round(slippage_cost * 100.0, 4),
        "funding_pct_initial": round(funding * 100.0, 4),
        "max_fill_leverage": round(max_fill_leverage, 4),
        "max_effective_leverage": round(max_effective_leverage, 4),
        "max_open_risk_pct": round(max_open_risk_fraction * 100.0, 4),
        "risk_breaches": risk_breaches,
        "worst_trade_return_pct": round(worst_trade * 100.0, 4),
        "action_counts": action_counts,
    }


def backtest(
    frame: pd.DataFrame,
    funding_rates: pd.Series,
    events: pd.DataFrame,
    *,
    side: int,
    config: CandidateConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    fee_rate: float = FEE_RATE,
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
    variant: Variant = Variant(),
    retain: bool = False,
) -> BacktestResult:
    selected = frame.loc[(frame.index >= start) & (frame.index < end)]
    if selected.empty:
        return BacktestResult(
            {}, pd.DataFrame(), pd.Series(dtype=float), pd.DataFrame()
        )
    event_map = {pd.Timestamp(index): row for index, row in events.loc[:end].iterrows()}
    equity = 1.0
    quantity = 0.0
    mark_price = float(selected["open"].iloc[0])
    campaign: Campaign | None = None
    peak_equity = 1.0
    conservative_mdd = 0.0
    max_fill_leverage = 0.0
    max_effective_leverage = 0.0
    max_open_risk_fraction = 0.0
    risk_breaches = 0
    total_turnover_multiple = 0.0
    total_fee = 0.0
    total_slippage = 0.0
    total_funding = 0.0
    trades: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    curve: list[float] = []
    curve_index: list[pd.Timestamp] = []
    action_counts: dict[str, int] = {}

    def count_action(name: str) -> None:
        action_counts[name] = action_counts.get(name, 0) + 1

    def mark_to(raw_price: float) -> None:
        nonlocal equity, mark_price
        equity += quantity * (raw_price - mark_price)
        mark_price = raw_price

    def trade_to(target_quantity: float, raw_price: float, action: str) -> float:
        nonlocal equity, quantity, total_turnover_multiple, total_fee, total_slippage
        nonlocal max_fill_leverage
        mark_to(raw_price)
        delta = target_quantity - quantity
        if abs(delta) <= 1e-14:
            return raw_price
        fill = adverse_fill(raw_price, delta, slippage)
        before = max(equity, 1e-12)
        slip_cost = abs(delta) * abs(fill - raw_price)
        fee = fee_rate * abs(delta) * fill
        equity -= slip_cost + fee
        total_slippage += slip_cost
        total_fee += fee
        total_turnover_multiple += abs(delta) * fill / before
        old_quantity = quantity
        quantity = target_quantity
        leverage = abs(quantity) * raw_price / max(equity, 1e-12)
        max_fill_leverage = max(max_fill_leverage, leverage)
        actions.append(
            {
                "ts": current_ts.isoformat(),
                "action": action,
                "raw_price": raw_price,
                "fill_price": fill,
                "quantity_before": old_quantity,
                "quantity_after": quantity,
                "equity_after": equity,
                "leverage_after": leverage,
            }
        )
        count_action(action)
        return fill

    def projected_exit_equity(
        raw_price: float, qty: float | None = None, base_equity: float | None = None
    ) -> float:
        active_qty = quantity if qty is None else qty
        active_equity = equity if base_equity is None else base_equity
        if active_qty == 0.0:
            return active_equity
        exit_fill = adverse_fill(raw_price, -active_qty, slippage)
        marked = active_equity + active_qty * (exit_fill - mark_price)
        return marked - fee_rate * abs(active_qty) * exit_fill

    def projected_after_add(
        target_abs: float, raw_price: float, stop: float
    ) -> tuple[float, float, float]:
        target = side * target_abs
        delta = target - quantity
        fill = adverse_fill(raw_price, delta, slippage)
        post_equity = (
            equity - abs(delta) * abs(fill - raw_price) - fee_rate * abs(delta) * fill
        )
        stop_fill = adverse_fill(stop, -target, slippage)
        projected = (
            post_equity
            + target * (stop_fill - raw_price)
            - fee_rate * abs(target) * stop_fill
        )
        leverage = abs(target) * raw_price / max(post_equity, 1e-12)
        return post_equity, projected, leverage

    def floor_stop(target_equity: float) -> float:
        if quantity == 0.0:
            return math.nan
        low = max(1e-9, mark_price * 0.05)
        high = mark_price * 5.0
        for _ in range(80):
            middle = (low + high) / 2.0
            projected = projected_exit_equity(middle)
            if side > 0:
                if projected < target_equity:
                    low = middle
                else:
                    high = middle
            elif projected > target_equity:
                low = middle
            else:
                high = middle
        return (low + high) / 2.0

    def current_open_risk(stop: float) -> float:
        if campaign is None:
            return 0.0
        return max(0.0, campaign.entry_equity - projected_exit_equity(stop))

    def close_campaign(raw_price: float, reason: str) -> None:
        nonlocal campaign, quantity
        if campaign is None:
            return
        exit_fill = trade_to(0.0, raw_price, f"exit_{reason}")
        net_pnl = equity - campaign.entry_equity
        peak = campaign.peak_net_profit
        trades.append(
            {
                "entry_ts": campaign.entry_ts.isoformat(),
                "exit_ts": current_ts.isoformat(),
                "side": "long" if side > 0 else "short",
                "entry_equity": campaign.entry_equity,
                "exit_equity": equity,
                "average_entry": campaign.average_entry,
                "exit_fill": exit_fill,
                "exit_reason": reason,
                "hold_hours": campaign.bars_held / 4.0,
                "net_pnl": net_pnl,
                "net_return": net_pnl / campaign.entry_equity,
                "r_multiple": net_pnl / campaign.r0,
                "peak_net_profit": peak,
                "peak_r_multiple": peak / campaign.r0,
                "capture_ratio": net_pnl / peak if peak > 0.0 else 0.0,
                "giveback_fraction": (peak - net_pnl) / peak if peak > 0.0 else 0.0,
                "add_count": campaign.add_count,
                "max_open_risk_pct": campaign.max_open_risk
                / campaign.entry_equity
                * 100.0,
                "max_effective_leverage": campaign.max_effective_leverage,
            }
        )
        campaign = None
        quantity = 0.0

    for current_ts, bar in selected.iterrows():
        current_ts = pd.Timestamp(current_ts)
        raw_open = float(bar["open"])
        raw_high = float(bar["high"])
        raw_low = float(bar["low"])
        raw_close = float(bar["close"])
        mark_to(raw_open)
        if include_funding and quantity != 0.0:
            payment = quantity * raw_open * float(funding_rates.get(current_ts, 0.0))
            equity -= payment
            total_funding += payment

        exited_this_bar = False
        if campaign is not None:
            gap_hit = (side > 0 and raw_open <= campaign.stop) or (
                side < 0 and raw_open >= campaign.stop
            )
            if gap_hit:
                close_campaign(raw_open, "stop_gap")
                exited_this_bar = True

        event = event_map.get(current_ts)
        if campaign is not None and event is not None and not exited_this_bar:
            if bool(event["regime_opposite"]):
                close_campaign(raw_open, "opposite_regime")
                exited_this_bar = True
            else:
                if variant.use_structural_stop and np.isfinite(
                    event["structural_stop"]
                ):
                    candidate = float(event["structural_stop"])
                    campaign.stop = (
                        max(campaign.stop, candidate)
                        if side > 0
                        else min(campaign.stop, candidate)
                    )
                if (
                    variant.use_mfe_floor
                    and campaign.peak_net_profit >= 2.0 * campaign.r0
                ):
                    target = campaign.entry_equity + 0.5 * campaign.peak_net_profit
                    candidate = floor_stop(target)
                    campaign.stop = (
                        max(campaign.stop, candidate)
                        if side > 0
                        else min(campaign.stop, candidate)
                    )
                crossed = (side > 0 and campaign.stop >= raw_open) or (
                    side < 0 and campaign.stop <= raw_open
                )
                if crossed:
                    close_campaign(raw_open, "raised_stop_gap")
                    exited_this_bar = True
                else:
                    same_regime = bool(event["regime_same"])
                    campaign.state = "EXHAUSTING" if not same_regime else campaign.state
                    target_layer: int | None = None
                    if variant.allow_core and campaign.layer == 0 and same_regime:
                        reclaimed = (
                            side * (float(event["close_1h"]) - campaign.entry_boundary)
                            > 0.0
                        )
                        if reclaimed:
                            target_layer = 1
                    net_now = projected_exit_equity(raw_open) - campaign.entry_equity
                    if variant.allow_pyramid and same_regime and net_now > 0.0:
                        if (
                            campaign.layer == 1
                            and campaign.peak_net_profit >= campaign.r0
                            and bool(event["add_1_signal"])
                        ):
                            target_layer = 2
                        elif (
                            campaign.layer == 2
                            and campaign.peak_net_profit >= 2.0 * campaign.r0
                            and bool(event["add_2_signal"])
                        ):
                            target_layer = 3
                    if target_layer is not None:
                        desired_abs = (
                            campaign.planned_full_qty * LAYER_FRACTIONS[target_layer]
                        )
                        _, projected, leverage = projected_after_add(
                            desired_abs, raw_open, campaign.stop
                        )
                        risk_ok = (
                            projected >= campaign.entry_equity - campaign.r0 - 1e-12
                        )
                        leverage_ok = leverage <= MAX_LEVERAGE + 1e-12
                        if risk_ok and leverage_ok:
                            before_abs = abs(quantity)
                            fill = trade_to(
                                side * desired_abs, raw_open, f"layer_{target_layer}"
                            )
                            added = desired_abs - before_abs
                            campaign.average_entry = (
                                campaign.average_entry * before_abs + fill * added
                            ) / desired_abs
                            campaign.quantity = quantity
                            campaign.layer = target_layer
                            campaign.state = ("CORE", "CORE", "PYRAMID_1", "PYRAMID_2")[
                                target_layer
                            ]
                            if target_layer >= 2:
                                campaign.add_count += 1
                        else:
                            count_action("blocked_layer")

        if campaign is None and not exited_this_bar and event is not None:
            if bool(event["entry_signal"]):
                atr = float(event["atr24"])
                structure = float(event["initial_structure"])
                if np.isfinite(atr) and atr > 0.0 and np.isfinite(structure):
                    atr_stop = raw_open - side * config.stop_atr_1h * atr
                    initial_stop = (
                        min(structure, atr_stop)
                        if side > 0
                        else max(structure, atr_stop)
                    )
                    entry_fill_estimate = adverse_fill(raw_open, side, slippage)
                    stop_fill_estimate = adverse_fill(initial_stop, -side, slippage)
                    loss_per_unit = side * (entry_fill_estimate - stop_fill_estimate)
                    loss_per_unit += fee_rate * (
                        entry_fill_estimate + stop_fill_estimate
                    )
                    if loss_per_unit > 0.0:
                        entry_equity = equity
                        r0 = entry_equity * RISK_FRACTION
                        full_abs = r0 / loss_per_unit
                        full_abs = min(
                            full_abs, MAX_LEVERAGE * entry_equity / entry_fill_estimate
                        )
                        seed_abs = full_abs * LAYER_FRACTIONS[0]
                        fill = trade_to(side * seed_abs, raw_open, "entry_seed")
                        campaign = Campaign(
                            side=side,
                            entry_ts=current_ts,
                            entry_equity=entry_equity,
                            r0=r0,
                            entry_boundary=float(event["entry_boundary"]),
                            initial_stop=initial_stop,
                            stop=initial_stop,
                            planned_full_qty=full_abs,
                            quantity=quantity,
                            average_entry=fill,
                            layer=0,
                        )

        if campaign is not None and not exited_this_bar:
            stop_hit = (side > 0 and raw_low <= campaign.stop) or (
                side < 0 and raw_high >= campaign.stop
            )
            if stop_hit:
                close_campaign(campaign.stop, "protective_stop")
                exited_this_bar = True

        if campaign is not None and not exited_this_bar:
            favorable = raw_high if side > 0 else raw_low
            peak_net = projected_exit_equity(favorable) - campaign.entry_equity
            campaign.peak_net_profit = max(campaign.peak_net_profit, peak_net)
            campaign.bars_held += 1
            open_risk = current_open_risk(campaign.stop)
            campaign.max_open_risk = max(campaign.max_open_risk, open_risk)
            max_open_risk_fraction = max(
                max_open_risk_fraction, open_risk / campaign.entry_equity
            )
            if open_risk > campaign.r0 + 1e-9:
                risk_breaches += 1
            adverse = raw_low if side > 0 else raw_high
            adverse_equity = equity + quantity * (adverse - mark_price)
            effective = abs(quantity) * adverse / max(adverse_equity, 1e-12)
            campaign.max_effective_leverage = max(
                campaign.max_effective_leverage, effective
            )
            max_effective_leverage = max(max_effective_leverage, effective)

        close_equity = equity + quantity * (raw_close - mark_price)
        favorable_equity = equity + quantity * (
            (raw_high if side > 0 else raw_low) - mark_price
        )
        adverse_equity = equity + quantity * (
            (raw_low if side > 0 else raw_high) - mark_price
        )
        peak_equity = max(peak_equity, favorable_equity, close_equity)
        conservative_mdd = min(
            conservative_mdd, adverse_equity / max(peak_equity, 1e-12) - 1.0
        )
        curve.append(close_equity)
        curve_index.append(current_ts)
        if equity <= 0.0:
            break

    if campaign is not None:
        current_ts = pd.Timestamp(selected.index[-1])
        terminal = float(selected["close"].iloc[-1])
        close_campaign(terminal, "terminal_flatten")
        if curve:
            curve[-1] = equity
    equity_series = pd.Series(curve, index=pd.DatetimeIndex(curve_index), name="equity")
    trades_frame = pd.DataFrame(trades)
    actions_frame = pd.DataFrame(actions) if retain else pd.DataFrame()
    metrics = compute_metrics(
        equity_series,
        trades_frame,
        conservative_mdd=conservative_mdd,
        turnover_multiple=total_turnover_multiple,
        fees=total_fee,
        slippage_cost=total_slippage,
        funding=total_funding,
        max_fill_leverage=max_fill_leverage,
        max_effective_leverage=max_effective_leverage,
        max_open_risk_fraction=max_open_risk_fraction,
        risk_breaches=risk_breaches,
        action_counts=action_counts,
    )
    return BacktestResult(metrics, trades_frame, equity_series, actions_frame)


def configs() -> list[CandidateConfig]:
    return [
        CandidateConfig(regime, entry, stop, exit_window)
        for regime in (30, 42, 60)
        for entry in (48, 72, 96)
        for stop in (2.5, 3.5)
        for exit_window in (18, 30, 42)
    ]


def candidate_row(
    config: CandidateConfig, full: BacktestResult, folds: list[BacktestResult]
) -> dict[str, Any]:
    returns = [fold.metrics.get("total_return_pct", -100.0) for fold in folds]
    return {
        **asdict(config),
        "label": config.label,
        "train_return_pct": full.metrics.get("total_return_pct", -100.0),
        "train_sharpe": full.metrics.get("sharpe", -100.0),
        "train_mdd_pct": full.metrics.get("max_drawdown_pct", -100.0),
        "train_trades": full.metrics.get("trades", 0),
        "train_avg_hold_hours": full.metrics.get("avg_hold_hours", 0.0),
        "train_turnover_annualized": full.metrics.get("turnover_annualized", math.inf),
        "train_max_fill_leverage": full.metrics.get("max_fill_leverage", math.inf),
        "train_max_effective_leverage": full.metrics.get(
            "max_effective_leverage", math.inf
        ),
        "train_risk_breaches": full.metrics.get("risk_breaches", 1),
        "positive_folds": sum(value > 0.0 for value in returns),
        "worst_fold_return_pct": min(returns),
        "fold_returns_pct": returns,
    }


def choose_candidate(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [
        row
        for row in rows
        if row["train_trades"] >= 5
        and row["train_max_fill_leverage"] <= MAX_LEVERAGE + 1e-9
        and row["train_risk_breaches"] == 0
        and row["train_return_pct"] > -100.0
    ]
    if not eligible:
        return None
    eligible.sort(
        key=lambda row: (
            row["positive_folds"],
            row["worst_fold_return_pct"],
            row["train_sharpe"],
            row["train_return_pct"],
            -row["train_turnover_annualized"],
        ),
        reverse=True,
    )
    return eligible[0]


def config_from_row(row: dict[str, Any]) -> CandidateConfig:
    return CandidateConfig(
        regime_ema_4h=int(row["regime_ema_4h"]),
        entry_donchian_1h=int(row["entry_donchian_1h"]),
        stop_atr_1h=float(row["stop_atr_1h"]),
        exit_donchian_4h=int(row["exit_donchian_4h"]),
    )


def trade_bootstrap(trades: pd.DataFrame, seed: int) -> dict[str, Any]:
    if trades.empty:
        return {"samples": 0, "positive_probability": 0.0, "return_ci_pct": [0.0, 0.0]}
    returns = (
        pd.to_numeric(trades["net_return"], errors="coerce").dropna().to_numpy(float)
    )
    rng = np.random.default_rng(seed)
    sampled = rng.choice(returns, size=(10_000, len(returns)), replace=True)
    totals = np.prod(1.0 + sampled, axis=1) - 1.0
    return {
        "samples": 10_000,
        "trades_per_sample": int(len(returns)),
        "positive_probability": round(float(np.mean(totals > 0.0)), 4),
        "median_return_pct": round(float(np.median(totals) * 100.0), 4),
        "return_ci_pct": [
            round(float(np.quantile(totals, 0.025) * 100.0), 4),
            round(float(np.quantile(totals, 0.975) * 100.0), 4),
        ],
    }


def main() -> None:
    module = load_v1_module()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    frame, funding, quality = module.load_symbol_data(
        warehouse, SYMBOL, require_raw_parity=True
    )
    if frame.index.max() >= PROSPECTIVE_START:
        raise RuntimeError("prospective OOS is present in the input; refuse to reveal")
    base = build_base_features(frame)
    all_search_rows: list[dict[str, Any]] = []
    direction_results: dict[str, Any] = {}
    for side, direction in ((1, "long"), (-1, "short")):
        rows: list[dict[str, Any]] = []
        for config in configs():
            events = build_signal_events(base, config, side)
            full = backtest(
                frame,
                funding,
                events,
                side=side,
                config=config,
                start=TRAIN_START,
                end=TRAIN_END,
            )
            folds = [
                backtest(
                    frame,
                    funding,
                    events,
                    side=side,
                    config=config,
                    start=fold_start,
                    end=fold_end,
                )
                for fold_start, fold_end in TRAIN_FOLDS
            ]
            row = {"direction": direction, **candidate_row(config, full, folds)}
            rows.append(row)
            all_search_rows.append(row)
        selected = choose_candidate(rows)
        if selected is None:
            direction_results[direction] = {
                "selection": "none: no Train-eligible candidate",
                "status": "explore / not promoted / not live-ready",
            }
            continue
        selected_config = config_from_row(selected)
        events = build_signal_events(base, selected_config, side)
        validation_runs = {
            "gross": backtest(
                frame,
                funding,
                events,
                side=side,
                config=selected_config,
                start=VALIDATION_START,
                end=VALIDATION_END,
                fee_rate=0.0,
                slippage=0.0,
                include_funding=False,
            ),
            "base": backtest(
                frame,
                funding,
                events,
                side=side,
                config=selected_config,
                start=VALIDATION_START,
                end=VALIDATION_END,
                retain=True,
            ),
            "stress": backtest(
                frame,
                funding,
                events,
                side=side,
                config=selected_config,
                start=VALIDATION_START,
                end=VALIDATION_END,
                slippage=STRESS_SLIPPAGE,
            ),
        }
        ablations = {
            "no_pyramid": Variant(name="no_pyramid", allow_pyramid=False),
            "no_mfe_floor": Variant(name="no_mfe_floor", use_mfe_floor=False),
            "no_structural_stop": Variant(
                name="no_structural_stop", use_structural_stop=False
            ),
            "seed_only": Variant(
                name="seed_only", allow_core=False, allow_pyramid=False
            ),
        }
        ablation_results = {
            name: backtest(
                frame,
                funding,
                events,
                side=side,
                config=selected_config,
                start=VALIDATION_START,
                end=VALIDATION_END,
                variant=variant,
            )
            for name, variant in ablations.items()
        }
        base_metrics = validation_runs["base"].metrics
        stress_metrics = validation_runs["stress"].metrics
        gate = {
            "train_full_positive": selected["train_return_pct"] > 0.0,
            "train_sharpe_positive": selected["train_sharpe"] > 0.0,
            "positive_base": base_metrics.get("total_return_pct", -1.0) > 0.0,
            "positive_sharpe": base_metrics.get("sharpe", -1.0) > 0.0,
            "mdd_within_20pct": base_metrics.get("max_drawdown_pct", -100.0) >= -20.0,
            "at_least_3_trades": base_metrics.get("trades", 0) >= 3,
            "avg_hold_at_least_24h": base_metrics.get("avg_hold_hours", 0.0) >= 24.0,
            "positive_stress": stress_metrics.get("total_return_pct", -1.0) > 0.0,
            "no_risk_breach": base_metrics.get("risk_breaches", 1) == 0,
            "fill_leverage_cap": base_metrics.get("max_fill_leverage", math.inf)
            <= MAX_LEVERAGE + 1e-9,
            "realized_loss_within_disaster_cap": base_metrics.get(
                "worst_trade_return_pct", -100.0
            )
            >= -DISASTER_FRACTION * 100.0,
        }
        passed = all(gate.values())
        direction_results[direction] = {
            "selected_train_row": selected,
            "selected_config": asdict(selected_config),
            "validation": {
                name: result.metrics for name, result in validation_runs.items()
            },
            "validation_gate": gate,
            "research_pass": passed,
            "validation_trade_bootstrap": trade_bootstrap(
                validation_runs["base"].trades,
                seed=20260802 + (0 if side > 0 else 1),
            ),
            "ablations": {
                name: result.metrics for name, result in ablation_results.items()
            },
            "status": "explore / not promoted / not live-ready",
        }
        prefix = ARTIFACT_DIR / f"hype_15m_mdtp_campaign_{direction}_{RUN_DATE}"
        validation_runs["base"].trades.to_csv(
            f"{prefix}_validation_trades.csv", index=False
        )
        validation_runs["base"].equity.rename("equity").to_csv(
            f"{prefix}_validation_equity.csv"
        )
        validation_runs["base"].actions.to_csv(
            f"{prefix}_validation_actions.csv", index=False
        )

    search_frame = pd.DataFrame(all_search_rows)
    search_path = ARTIFACT_DIR / f"hype_15m_mdtp_campaign_train_search_{RUN_DATE}.csv"
    result_path = ARTIFACT_DIR / f"hype_15m_mdtp_campaign_research_{RUN_DATE}.json"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    search_frame.to_csv(search_path, index=False)
    payload = {
        "family": "HYPE-15M-Multidimensional-Trend-Pyramiding",
        "research_role": "unregistered campaign successor",
        "run_date": RUN_DATE,
        "data_quality": quality,
        "windows": {
            "train": [TRAIN_START.isoformat(), TRAIN_END.isoformat()],
            "embargo": [TRAIN_END.isoformat(), VALIDATION_START.isoformat()],
            "validation": [VALIDATION_START.isoformat(), VALIDATION_END.isoformat()],
            "prospective_oos_locked_not_revealed": [
                PROSPECTIVE_START.isoformat(),
                PROSPECTIVE_END.isoformat(),
            ],
        },
        "search_count_per_direction": len(configs()),
        "fixed_contract": {
            "risk_fraction": RISK_FRACTION,
            "disaster_fraction": DISASTER_FRACTION,
            "max_leverage": MAX_LEVERAGE,
            "layers": LAYER_FRACTIONS,
            "mfe_trigger_r": 2.0,
            "mfe_profit_retained": 0.5,
            "fee_rate": FEE_RATE,
            "base_slippage": BASE_SLIPPAGE,
            "stress_slippage": STRESS_SLIPPAGE,
        },
        "directions": direction_results,
        "post_reveal_governance_note": (
            "The frozen ranking contract did not require the selected full-Train result to be positive. "
            "After Validation reveal, positive full-Train return and Sharpe are added only as stricter "
            "credibility blockers; candidate selection is not rerun and Validation is not reused."
        ),
    }
    result_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
