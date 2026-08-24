#!/usr/bin/env python3
"""Evaluate a preregistered liveability overlay for monthly Binance Top10."""

from __future__ import annotations

import argparse
import hashlib
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_binance_1d_mcsm_long10 as long10


ext = long10.ext
base = long10.base
FAMILY_DIR = long10.FAMILY_DIR
ARTIFACT_DIR = long10.ARTIFACT_DIR
FAMILY_NAME = long10.FAMILY_NAME
FAMILY_ALIAS = long10.FAMILY_ALIAS
SPEC = "specs/binance-1d-mcsm-long10-liveability-candidate-contract-2026-08-20.md"
EVALUATION_START = pd.Timestamp("2020-08-01")
HOLDOUT_START = pd.Timestamp("2024-01-01")
TARGET_VOL = 0.15
TARGET_VOL_WINDOW = 90
TARGET_VOL_MIN_PERIODS = 60
BTC_SMA_DAYS = 200
FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0004
MC_PATHS = 5_000
MC_SEED = 20_260_820
PARTICIPATION_RATES = (0.005, 0.01, 0.02)


@dataclass(frozen=True)
class OverlayConfig:
    id: str
    label: str
    group: str
    universe: str = "adv10m"
    target_vol: float | None = None
    sma_days: int | None = None
    monthly_gate: bool = False
    intramonth_exit: bool = False
    cost_multiplier: float = 1.0
    delay_days: int = 0
    selection: str = "top_n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def configs() -> list[OverlayConfig]:
    items = [
        OverlayConfig("adv_top10_baseline", "ADV Top10 baseline（同起点）", "control"),
        OverlayConfig("adv_top10_target20", "ADV Top10 target20（同起点）", "control", target_vol=0.20),
        OverlayConfig("adv_top10_target15", "ADV Top10 target15", "control", target_vol=TARGET_VOL),
        OverlayConfig("adv_top10_target12", "ADV Top10 target12 运营风险预算", "risk_budget", target_vol=0.12),
        OverlayConfig(
            "all_top10_target12",
            "全上市 Top10 target12 控制",
            "risk_budget_control",
            universe="all_listed",
            target_vol=0.12,
        ),
        OverlayConfig(
            "adv_top10_btc200_gate_only",
            "ADV Top10 + BTC SMA200 gate-only",
            "ablation",
            sma_days=BTC_SMA_DAYS,
            monthly_gate=True,
            intramonth_exit=True,
        ),
        OverlayConfig(
            "adv_candidate",
            "ADV Top10 + target15 + BTC SMA200",
            "candidate",
            target_vol=TARGET_VOL,
            sma_days=BTC_SMA_DAYS,
            monthly_gate=True,
            intramonth_exit=True,
        ),
        OverlayConfig(
            "adv_candidate_no_intramonth_exit",
            "候选消融：删除月中退出",
            "ablation",
            target_vol=TARGET_VOL,
            sma_days=BTC_SMA_DAYS,
            monthly_gate=True,
        ),
        OverlayConfig(
            "adv_candidate_no_monthly_gate",
            "候选消融：删除月初 gate",
            "ablation",
            target_vol=TARGET_VOL,
            sma_days=BTC_SMA_DAYS,
            intramonth_exit=True,
        ),
        OverlayConfig(
            "all_candidate",
            "全上市 Top10 + target15 + BTC SMA200",
            "universe_control",
            universe="all_listed",
            target_vol=TARGET_VOL,
            sma_days=BTC_SMA_DAYS,
            monthly_gate=True,
            intramonth_exit=True,
        ),
        OverlayConfig(
            "adv_equal_market_candidate_overlay",
            "ADV 全市场等权 + 相同风险层",
            "benchmark",
            target_vol=TARGET_VOL,
            sma_days=BTC_SMA_DAYS,
            monthly_gate=True,
            intramonth_exit=True,
            selection="all_equal",
        ),
        OverlayConfig(
            "adv_equal_market_target12",
            "ADV 全市场等权 target12",
            "benchmark",
            target_vol=0.12,
            selection="all_equal",
        ),
    ]
    for sma_days in (150, 200, 250):
        for target_vol in (0.12, 0.15, 0.18):
            if sma_days == BTC_SMA_DAYS and math.isclose(target_vol, TARGET_VOL):
                continue
            items.append(
                OverlayConfig(
                    f"mc4_sma{sma_days}_tv{int(target_vol * 100):02d}",
                    f"MC4 SMA{sma_days} / target{target_vol:.0%}",
                    "mc4",
                    target_vol=target_vol,
                    sma_days=sma_days,
                    monthly_gate=True,
                    intramonth_exit=True,
                )
            )
    items.extend(
        [
            OverlayConfig(
                "stress_cost_1_5x",
                "候选成本 1.5x",
                "stress",
                target_vol=TARGET_VOL,
                sma_days=BTC_SMA_DAYS,
                monthly_gate=True,
                intramonth_exit=True,
                cost_multiplier=1.5,
            ),
            OverlayConfig(
                "stress_cost_2x",
                "候选成本 2x",
                "stress",
                target_vol=TARGET_VOL,
                sma_days=BTC_SMA_DAYS,
                monthly_gate=True,
                intramonth_exit=True,
                cost_multiplier=2.0,
            ),
            OverlayConfig(
                "stress_delay_1d",
                "候选换仓延迟 1d",
                "stress",
                target_vol=TARGET_VOL,
                sma_days=BTC_SMA_DAYS,
                monthly_gate=True,
                intramonth_exit=True,
                delay_days=1,
            ),
            OverlayConfig(
                "stress_top10_target12_cost2x",
                "Top10 target12 成本 2x",
                "risk_budget_stress",
                target_vol=0.12,
                cost_multiplier=2.0,
            ),
            OverlayConfig(
                "stress_top10_target12_delay1d",
                "Top10 target12 换仓延迟 1d",
                "risk_budget_stress",
                target_vol=0.12,
                delay_days=1,
            ),
        ]
    )
    return items


def _baseline_payload(
    universe: str,
    selection: str,
    close: pd.DataFrame,
    open_: pd.DataFrame,
    bars: pd.DataFrame,
    quote: pd.DataFrame,
    funding: pd.DataFrame,
    bases: dict[str, str],
) -> dict[str, Any]:
    variant = ext.Variant(
        f"source_{universe}_{selection}",
        "source holdings",
        "source",
        universe=universe,
        n_legs=10,
        long_only=True,
        selection=selection,
        forced_start=str(EVALUATION_START.date()) if selection == "all_equal" else None,
    )
    return ext._simulate(variant, close, open_, bars, quote, funding, bases)


def _holdings_by_month(payload: dict[str, Any]) -> dict[pd.Timestamp, dict[str, Any]]:
    return {
        pd.Timestamp(row["rebalance"]): row
        for row in payload["holdings"]
    }


def _month_target(
    row: dict[str, Any] | None,
    columns: pd.Index,
    selection: str,
) -> pd.Series:
    target = pd.Series(0.0, index=columns)
    if row is None or row.get("status") != "traded":
        return target
    longs = [symbol for symbol in str(row.get("longs", "")).split(",") if symbol]
    if not longs:
        return target
    weight = 1.0 / len(longs) if selection == "all_equal" else 0.1
    target.loc[longs] = weight
    return target


def _price_returns(weights: pd.DataFrame, close: pd.DataFrame, open_: pd.DataFrame) -> pd.Series:
    prior = weights.shift(1).fillna(0.0)
    changed = (weights - prior).abs().sum(axis=1).gt(1e-14)
    regular = (prior * (close / close.shift(1) - 1.0).fillna(0.0)).sum(axis=1)
    split = (
        prior * (open_ / close.shift(1) - 1.0).fillna(0.0)
        + weights * (close / open_ - 1.0).fillna(0.0)
    ).sum(axis=1)
    return regular.where(~changed, split)


def _risk_scale(
    month_start: pd.Timestamp,
    target: pd.Series,
    unscaled_price: pd.Series,
    asset_vol: pd.DataFrame,
    target_vol: float | None,
) -> float:
    if target_vol is None:
        return 1.0
    realized = (
        unscaled_price.shift(1)
        .rolling(TARGET_VOL_WINDOW, min_periods=TARGET_VOL_MIN_PERIODS)
        .std(ddof=0)
        * math.sqrt(base.ANNUALIZER)
    )
    prior_days = realized.index[realized.index < month_start]
    observed = realized.loc[prior_days.max()] if len(prior_days) else np.nan
    if pd.notna(observed) and float(observed) > 0:
        return float(np.clip(target_vol / float(observed), 0.0, 1.0))
    signal_days = asset_vol.index[asset_vol.index < month_start]
    if not len(signal_days):
        return 0.0
    proxy = float((target.abs() * asset_vol.loc[signal_days.max()].fillna(0.0)).sum())
    return float(np.clip(target_vol / proxy, 0.0, 1.0)) if proxy > 0 else 0.0


def _build_weights(
    config: OverlayConfig,
    source_payload: dict[str, Any],
    close: pd.DataFrame,
    open_: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]], pd.Series]:
    columns = close.columns
    source_rows = _holdings_by_month(source_payload)
    unscaled = pd.DataFrame(0.0, index=close.index, columns=columns)
    for month_start, row in source_rows.items():
        if month_start not in unscaled.index:
            continue
        end = min(month_start + pd.offsets.MonthEnd(0), unscaled.index.max())
        unscaled.loc[month_start:end] = _month_target(row, columns, config.selection).to_numpy()
    unscaled_price = _price_returns(unscaled, close, open_)
    asset_vol = (
        close.pct_change(fill_method=None)
        .rolling(ext.ASSET_VOL_WINDOW, min_periods=ext.ASSET_VOL_MIN_PERIODS)
        .std(ddof=0)
        * math.sqrt(base.ANNUALIZER)
    )
    if "BTC" not in close.columns:
        raise KeyError("BTC is required for the market-state overlay")
    btc_sma = (
        close["BTC"].rolling(config.sma_days, min_periods=config.sma_days).mean()
        if config.sma_days is not None
        else pd.Series(np.nan, index=close.index)
    )
    trend = close["BTC"].ge(btc_sma) if config.sma_days is not None else pd.Series(True, index=close.index)

    changes: dict[pd.Timestamp, pd.Series] = {}
    holdings: list[dict[str, Any]] = []
    for month_start in sorted(source_rows):
        if month_start < EVALUATION_START or month_start not in close.index:
            continue
        row = source_rows[month_start]
        month_end = min(month_start + pd.offsets.MonthEnd(0), close.index.max())
        prior_days = close.index[close.index < month_start]
        signal_day = prior_days.max() if len(prior_days) else None
        target = _month_target(row, columns, config.selection)
        scale = _risk_scale(month_start, target, unscaled_price, asset_vol, config.target_vol)
        state_known = signal_day is not None and bool(pd.notna(trend.loc[signal_day]))
        market_on = bool(trend.loc[signal_day]) if state_known else config.sma_days is None
        gate_on = market_on if config.monthly_gate else True
        desired = target * scale if gate_on else target * 0.0
        effective = month_start + pd.Timedelta(days=config.delay_days)
        if effective in close.index and effective <= month_end:
            changes[effective] = desired.copy()
        exit_signal_day: pd.Timestamp | None = None
        exit_effective_day: pd.Timestamp | None = None
        if config.intramonth_exit and desired.abs().sum() > 0:
            month_days = close.index[(close.index >= month_start) & (close.index <= month_end)]
            broken = [day for day in month_days if pd.isna(trend.loc[day]) or not bool(trend.loc[day])]
            if broken:
                exit_signal_day = pd.Timestamp(broken[0])
                candidates = close.index[close.index > exit_signal_day]
                if len(candidates) and candidates.min() <= month_end:
                    exit_effective_day = pd.Timestamp(candidates.min())
                    changes[exit_effective_day] = pd.Series(0.0, index=columns)
        holdings.append(
            {
                "variant": config.id,
                "rebalance": str(month_start.date()),
                "source_status": row.get("status"),
                "status": "traded" if desired.abs().sum() > 0 else "cash",
                "eligible": row.get("eligible"),
                "longs": row.get("longs", ""),
                "market_signal_day": str(signal_day.date()) if signal_day is not None else None,
                "btc_close": float(close.at[signal_day, "BTC"]) if signal_day is not None and pd.notna(close.at[signal_day, "BTC"]) else None,
                "btc_sma": float(btc_sma.loc[signal_day]) if signal_day is not None and pd.notna(btc_sma.loc[signal_day]) else None,
                "market_on": market_on,
                "monthly_gate_on": gate_on,
                "portfolio_scale": scale,
                "target_gross": float(desired.abs().sum()),
                "effective_day": str(effective.date()) if effective in close.index and effective <= month_end else None,
                "exit_signal_day": str(exit_signal_day.date()) if exit_signal_day is not None else None,
                "exit_effective_day": str(exit_effective_day.date()) if exit_effective_day is not None else None,
            }
        )

    weights = pd.DataFrame(0.0, index=close.index, columns=columns)
    current = pd.Series(0.0, index=columns)
    for day in close.index:
        if day in changes:
            current = changes[day]
        weights.loc[day] = current.to_numpy()
    weights.loc[weights.index < EVALUATION_START] = 0.0
    return weights, holdings, btc_sma


def _path_diagnostics(net: pd.Series) -> dict[str, Any]:
    equity = (1.0 + net.fillna(0.0)).cumprod()
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    trough_day = drawdown.idxmin()
    peak_day = equity.loc[:trough_day].idxmax()
    recovered = equity.loc[trough_day:][equity.loc[trough_day:] >= equity.loc[peak_day]]
    recovery_day = recovered.index.min() if len(recovered) else None
    longest = 0
    start: pd.Timestamp | None = None
    for day, value in drawdown.items():
        if value < -1e-14 and start is None:
            start = pd.Timestamp(day)
        elif value >= -1e-14 and start is not None:
            longest = max(longest, (pd.Timestamp(day) - start).days)
            start = None
    if start is not None:
        longest = max(longest, (pd.Timestamp(drawdown.index[-1]) - start).days + 1)
    return {
        "max_drawdown_peak": str(pd.Timestamp(peak_day).date()),
        "max_drawdown_trough": str(pd.Timestamp(trough_day).date()),
        "max_drawdown_recovery": str(pd.Timestamp(recovery_day).date()) if recovery_day is not None else None,
        "longest_underwater_days": int(longest),
        "final_vs_hwm": float(equity.iloc[-1] / peak.iloc[-1] - 1.0),
    }


def _simulate_overlay(
    config: OverlayConfig,
    source_payload: dict[str, Any],
    close: pd.DataFrame,
    open_: pd.DataFrame,
    quote: pd.DataFrame,
    funding: pd.DataFrame,
) -> dict[str, Any]:
    weights, holdings, btc_sma = _build_weights(config, source_payload, close, open_)
    weights = weights.loc[EVALUATION_START:].copy()
    close_eval = close.loc[weights.index]
    open_eval = open_.loc[weights.index]
    funding_eval = funding.reindex_like(weights)
    price = _price_returns(weights, close_eval, open_eval)
    prior = weights.shift(1).fillna(0.0)
    turnover = (weights - prior).abs().sum(axis=1)
    turnover.iloc[-1] += weights.iloc[-1].abs().sum()
    funding_pnl = -(weights * funding_eval.fillna(0.0)).sum(axis=1)
    fee = turnover * FEE_RATE * config.cost_multiplier
    slippage = turnover * SLIPPAGE_RATE * config.cost_multiplier
    net = price + funding_pnl - fee - slippage
    metrics = base.performance(net)
    equity = (1.0 + net).cumprod()
    held = weights.abs().gt(0.0)
    metrics.update(
        {
            "variant": config.id,
            "label": config.label,
            "group": config.group,
            "universe": config.universe,
            "target_vol": config.target_vol,
            "sma_days": config.sma_days,
            "monthly_gate": config.monthly_gate,
            "intramonth_exit": config.intramonth_exit,
            "cost_multiplier": config.cost_multiplier,
            "delay_days": config.delay_days,
            "n_rebalances": len(holdings),
            "risk_on_months": sum(row["status"] == "traded" for row in holdings),
            "intramonth_exits": sum(row["exit_effective_day"] is not None for row in holdings),
            "mean_gross_exposure": float(weights.abs().sum(axis=1).mean()),
            "max_gross_exposure": float(weights.abs().sum(axis=1).max()),
            "ann_turnover": float(turnover.sum() * base.ANNUALIZER / len(net)),
            "price_pnl_sum": float(price.sum()),
            "funding_pnl_sum": float(funding_pnl.sum()),
            "fee_pnl_sum": -float(fee.sum()),
            "slippage_pnl_sum": -float(slippage.sum()),
            "arithmetic_total_pnl_sum": float(net.sum()),
            "funding_coverage": float((held & funding_eval.notna()).to_numpy().sum() / max(int(held.to_numpy().sum()), 1)),
            "min_daily_return": float(net.min()),
            "nonpositive_equity_days": int((equity <= 0).sum()),
        }
    )
    metrics.update(_path_diagnostics(net))
    daily = pd.DataFrame(
        {
            "variant": config.id,
            "day": net.index,
            "net_return": net.to_numpy(),
            "price_pnl": price.to_numpy(),
            "funding_pnl": funding_pnl.to_numpy(),
            "fee": fee.to_numpy(),
            "slippage": slippage.to_numpy(),
            "turnover": turnover.to_numpy(),
            "gross_exposure": weights.abs().sum(axis=1).to_numpy(),
            "equity": equity.to_numpy(),
            "btc_close": close_eval["BTC"].to_numpy(),
            "btc_sma": btc_sma.reindex(net.index).to_numpy(),
        }
    )
    return {"config": config, "metrics": metrics, "daily": daily, "holdings": holdings, "weights": weights, "quote": quote}


def _slice_metrics(payload: dict[str, Any], start: pd.Timestamp, end: pd.Timestamp | None = None) -> dict[str, Any]:
    net = payload["daily"].set_index("day")["net_return"]
    sliced = net.loc[start:end]
    result = base.performance(sliced)
    result.update({"variant": payload["metrics"]["variant"], "slice_start": str(start.date()), "slice_end": str((end or sliced.index.max()).date())})
    return result


def _cohort_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    net = payload["daily"].set_index("day")["net_return"]
    rows: list[dict[str, Any]] = []
    start = EVALUATION_START
    cohort = 0
    while start <= net.index.max():
        end = min(start + pd.DateOffset(months=12) - pd.Timedelta(days=1), net.index.max())
        sliced = net.loc[start:end]
        metrics = base.performance(sliced)
        rows.append(
            {
                "variant": payload["metrics"]["variant"],
                "cohort": cohort,
                "start": str(start.date()),
                "end": str(end.date()),
                "months": int(sliced.index.to_period("M").nunique()),
                "complete_12m": int(sliced.index.to_period("M").nunique()) == 12,
                **metrics,
            }
        )
        cohort += 1
        start += pd.DateOffset(months=12)
    return rows


def _bootstrap_months(payload: dict[str, Any]) -> pd.DataFrame:
    net = payload["daily"].set_index("day")["net_return"]
    monthly = ((1.0 + net).resample("ME").prod() - 1.0).to_numpy()
    rng = np.random.default_rng(MC_SEED)
    sampled = rng.choice(monthly, size=(MC_PATHS, len(monthly)), replace=True)
    equity = np.cumprod(1.0 + sampled, axis=1)
    running_peak = np.maximum.accumulate(equity, axis=1)
    drawdown = equity / running_peak - 1.0
    terminal = equity[:, -1] - 1.0
    mean = sampled.mean(axis=1)
    std = sampled.std(axis=1, ddof=0)
    sharpe = np.divide(mean, std, out=np.full_like(mean, np.nan), where=std > 0) * math.sqrt(12)
    frame = pd.DataFrame({"terminal_return": terminal, "sharpe": sharpe, "max_drawdown": drawdown.min(axis=1)})
    quantiles = frame.quantile([0.05, 0.10, 0.50, 0.90, 0.95]).reset_index(names="quantile")
    quantiles.insert(0, "variant", payload["metrics"]["variant"])
    return quantiles


def _capacity_rows(payload: dict[str, Any], quote: pd.DataFrame) -> pd.DataFrame:
    weights = payload["weights"]
    adv = quote.rolling(base.ADV_WINDOW, min_periods=base.ADV_WINDOW).mean()
    delta = weights - weights.shift(1).fillna(0.0)
    rows: list[dict[str, Any]] = []
    for day in delta.index[delta.abs().sum(axis=1) > 1e-14]:
        prior_days = adv.index[adv.index < day]
        if not len(prior_days):
            continue
        known_day = prior_days.max()
        for symbol, weight_change in delta.loc[day].items():
            if abs(float(weight_change)) <= 1e-14:
                continue
            known_adv = adv.at[known_day, symbol]
            row = {
                "variant": payload["metrics"]["variant"],
                "execution_day": str(pd.Timestamp(day).date()),
                "adv_day": str(pd.Timestamp(known_day).date()),
                "symbol": symbol,
                "delta_weight": float(weight_change),
                "adv_30d_usdt": float(known_adv) if pd.notna(known_adv) else None,
            }
            for participation in PARTICIPATION_RATES:
                key = f"max_aum_{participation * 100:g}pct_adv"
                row[key] = float(participation * known_adv / abs(weight_change)) if pd.notna(known_adv) and known_adv > 0 else None
            rows.append(row)
    return pd.DataFrame(rows)


def _excess_summary(candidate: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
    left = candidate["daily"].set_index("day")["net_return"]
    right = benchmark["daily"].set_index("day")["net_return"]
    excess = left.sub(right, fill_value=0.0)
    monthly = excess.resample("ME").sum().to_numpy()
    ir = float(excess.mean() / excess.std(ddof=0) * math.sqrt(base.ANNUALIZER)) if excess.std(ddof=0) > 0 else None
    rng = np.random.default_rng(MC_SEED + 1)
    boot = rng.choice(monthly, size=(10_000, len(monthly)), replace=True).mean(axis=1) * 12
    return {
        "candidate": candidate["metrics"]["variant"],
        "benchmark": benchmark["metrics"]["variant"],
        "annualized_arithmetic_excess": float(excess.mean() * base.ANNUALIZER),
        "information_ratio": ir,
        "monthly_excess_positive_rate": float((monthly > 0).mean()),
        "bootstrap_annual_excess_p05": float(np.quantile(boot, 0.05)),
        "bootstrap_annual_excess_median": float(np.quantile(boot, 0.50)),
        "bootstrap_annual_excess_p95": float(np.quantile(boot, 0.95)),
    }


def _acceptance(
    payloads: dict[str, dict[str, Any]],
    cohort_frame: pd.DataFrame,
) -> dict[str, Any]:
    candidate = payloads["adv_candidate"]["metrics"]
    holdout = _slice_metrics(payloads["adv_candidate"], HOLDOUT_START)
    complete = cohort_frame[(cohort_frame["variant"] == "adv_candidate") & cohort_frame["complete_12m"]]
    positive_rate = float((complete["total_return"] > 0).mean()) if len(complete) else 0.0
    mc4 = [payload["metrics"] for key, payload in payloads.items() if key.startswith("mc4_")]
    mc4_positive_rate = float(np.mean([row["total_return"] > 0 for row in mc4])) if mc4 else 0.0
    checks = {
        "full_sharpe_gte_0_8": candidate["sharpe"] >= 0.8,
        "full_mdd_gte_minus_25pct": candidate["max_drawdown"] >= -0.25,
        "full_cagr_gte_10pct": candidate["cagr"] >= 0.10,
        "holdout_total_return_gt_0": holdout["total_return"] > 0,
        "holdout_mdd_gte_minus_20pct": holdout["max_drawdown"] >= -0.20,
        "complete_12m_positive_rate_gte_60pct": positive_rate >= 0.60,
        "stress_2x_total_return_gt_0": payloads["stress_cost_2x"]["metrics"]["total_return"] > 0,
        "mc4_positive_rate_gte_80pct": mc4_positive_rate >= 0.80,
        "all_listed_control_positive": payloads["all_candidate"]["metrics"]["total_return"] > 0,
        "no_leverage": candidate["max_gross_exposure"] <= 1.0 + 1e-12,
        "no_nonpositive_equity": candidate["nonpositive_equity_days"] == 0,
    }
    return {
        "checks": {key: bool(value) for key, value in checks.items()},
        "all_reference_lines_pass": bool(all(checks.values())),
        "complete_12m_positive_rate": positive_rate,
        "mc4_positive_rate": mc4_positive_rate,
        "holdout": holdout,
    }


def _self_test() -> None:
    index = pd.date_range("2020-01-01", periods=320, freq="D")
    btc = pd.Series(np.r_[np.linspace(100, 200, 250), np.linspace(199, 80, 70)], index=index)
    close = pd.DataFrame({"BTC": btc, "AAA": 100.0, "BBB": 100.0}, index=index)
    open_ = close.copy()
    rows = []
    for month_start in pd.date_range("2020-08-01", "2020-11-01", freq="MS"):
        rows.append({"rebalance": str(month_start.date()), "status": "traded", "eligible": 2, "longs": "AAA,BBB"})
    source = {"holdings": rows}
    config = OverlayConfig(
        "test",
        "test",
        "test",
        target_vol=None,
        sma_days=20,
        monthly_gate=True,
        intramonth_exit=True,
    )
    weights, holdings, _ = _build_weights(config, source, close, open_)
    exits = [row for row in holdings if row["exit_effective_day"]]
    assert exits, holdings
    first_exit = pd.Timestamp(exits[0]["exit_effective_day"])
    assert weights.loc[first_exit].abs().sum() == 0.0
    assert weights.max().max() <= 0.1 + 1e-12
    regular = _price_returns(weights.loc[EVALUATION_START:], close.loc[EVALUATION_START:], open_.loc[EVALUATION_START:])
    assert np.isfinite(regular).all()
    print("self-test ok")


def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test()
        return

    close, open_, bars, quote, funding, bases, cache_meta, audit = long10.load_inputs()
    source_payloads: dict[tuple[str, str], dict[str, Any]] = {}
    payloads: dict[str, dict[str, Any]] = {}
    for config in configs():
        source_key = (config.universe, config.selection)
        if source_key not in source_payloads:
            print(f"building source {source_key}", flush=True)
            source_payloads[source_key] = _baseline_payload(
                config.universe,
                config.selection,
                close,
                open_,
                bars,
                quote,
                funding,
                bases,
            )
        print(f"running {config.id}", flush=True)
        payloads[config.id] = _simulate_overlay(
            config,
            source_payloads[source_key],
            close,
            open_,
            quote,
            funding,
        )

    metrics = pd.DataFrame([payload["metrics"] for payload in payloads.values()])
    daily = pd.concat([payload["daily"] for payload in payloads.values()], ignore_index=True)
    holdings = pd.DataFrame([row for payload in payloads.values() for row in payload["holdings"]])
    yearly_rows: list[pd.DataFrame] = []
    recent_rows: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []
    cohort_rows: list[dict[str, Any]] = []
    for payload in payloads.values():
        variant_id = payload["metrics"]["variant"]
        net = payload["daily"].set_index("day")["net_return"]
        yearly = ((1.0 + net).resample("YE").prod() - 1.0).rename("net_return").reset_index()
        yearly["year"] = yearly["day"].dt.year
        yearly["variant"] = variant_id
        yearly_rows.append(yearly[["variant", "year", "net_return"]])
        recent_rows.extend({"variant": variant_id, **row} for row in base.recent_slices(net))
        split_rows.append({"slice": "development", **_slice_metrics(payload, EVALUATION_START, HOLDOUT_START - pd.Timedelta(days=1))})
        split_rows.append({"slice": "holdout_exposed_regime", **_slice_metrics(payload, HOLDOUT_START)})
        cohort_rows.extend(_cohort_rows(payload))
    cohort_frame = pd.DataFrame(cohort_rows)

    capacity = pd.concat(
        [
            _capacity_rows(payloads["adv_candidate"], quote),
            _capacity_rows(payloads["adv_top10_target12"], quote),
        ],
        ignore_index=True,
    )
    bootstrap = pd.concat(
        [
            _bootstrap_months(payloads["adv_candidate"]),
            _bootstrap_months(payloads["adv_top10_target12"]),
        ],
        ignore_index=True,
    )
    excess = {
        "market_gate_candidate": _excess_summary(
            payloads["adv_candidate"], payloads["adv_equal_market_candidate_overlay"]
        ),
        "target12_risk_budget": _excess_summary(
            payloads["adv_top10_target12"], payloads["adv_equal_market_target12"]
        ),
    }
    acceptance = _acceptance(payloads, cohort_frame)
    candidate_monthly = payloads["adv_candidate"]["daily"].set_index("day")["net_return"]
    target15_monthly = payloads["adv_top10_target15"]["daily"].set_index("day")["net_return"]
    monthly_attribution = pd.DataFrame(
        {
            "candidate": (1.0 + candidate_monthly).resample("ME").prod() - 1.0,
            "target15_no_market_overlay": (1.0 + target15_monthly).resample("ME").prod() - 1.0,
        }
    ).reset_index()
    monthly_attribution["overlay_difference"] = monthly_attribution["candidate"] - monthly_attribution["target15_no_market_overlay"]

    capacity_summary: list[dict[str, Any]] = []
    for variant, variant_capacity in capacity.groupby("variant"):
        for participation in PARTICIPATION_RATES:
            column = f"max_aum_{participation * 100:g}pct_adv"
            values = variant_capacity[column].dropna()
            capacity_summary.append(
                {
                    "variant": variant,
                    "participation_rate": participation,
                    "orders": int(len(values)),
                    "min_aum": float(values.min()) if len(values) else None,
                    "p05_aum": float(values.quantile(0.05)) if len(values) else None,
                    "p10_aum": float(values.quantile(0.10)) if len(values) else None,
                    "median_aum": float(values.median()) if len(values) else None,
                }
            )

    stem = f"binance-1d-mcsm-long10-liveability-{args.run_date}"
    summary = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "family": FAMILY_NAME,
        "alias": FAMILY_ALIAS,
        "contract": SPEC,
        "candidate": asdict(next(config for config in configs() if config.id == "adv_candidate")),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "engine_sha256": hashlib.sha256(Path(ext.__file__).read_bytes()).hexdigest(),
        "baseline_engine_sha256": hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest(),
        "cache": cache_meta,
        "audit": audit,
        "excess": excess,
        "capacity_summary": capacity_summary,
        "acceptance": acceptance,
        "metrics": metrics.to_dict(orient="records"),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    base.write_json(ARTIFACT_DIR / f"{stem}-summary.json", summary, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-metrics.csv", metrics, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-daily-paths.csv", daily, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-holdings.csv", holdings, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-yearly.csv", pd.concat(yearly_rows, ignore_index=True), force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-recent-slices.csv", pd.DataFrame(recent_rows), force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-splits.csv", pd.DataFrame(split_rows), force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-12m-cohorts.csv", cohort_frame, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-bootstrap.csv", bootstrap, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-capacity.csv", capacity, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-monthly-attribution.csv", monthly_attribution, force=args.force)
    print(
        metrics[
            [
                "variant",
                "group",
                "total_return",
                "cagr",
                "ann_vol",
                "sharpe",
                "max_drawdown",
                "ann_turnover",
                "mean_gross_exposure",
            ]
        ].to_string(index=False)
    )
    print("acceptance", acceptance)


if __name__ == "__main__":
    main()
