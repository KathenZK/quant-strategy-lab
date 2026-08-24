#!/usr/bin/env python3
"""Evaluate the preregistered 1M/3M/6M Top10 sleeve ensemble."""

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
import research_binance_1d_mcsm_long10_liveability as live


ext = long10.ext
base = long10.base
ARTIFACT_DIR = long10.ARTIFACT_DIR
SPEC = "specs/binance-1d-mcsm-mh136-liveability-contract-2026-08-20.md"
EVALUATION_START = live.EVALUATION_START
HOLDOUT_START = live.HOLDOUT_START
TARGET_VOL = 0.15


@dataclass(frozen=True)
class EnsembleConfig:
    id: str
    label: str
    group: str
    horizons: tuple[int, ...]
    universe: str = "adv10m"
    target_vol: float | None = TARGET_VOL
    cost_multiplier: float = 1.0
    delay_days: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def configs() -> list[EnsembleConfig]:
    return [
        EnsembleConfig("adv_1m_tv15", "ADV 1M Top10 target15", "single_sleeve", (1,)),
        EnsembleConfig("adv_3m_tv15", "ADV 3M Top10 target15", "single_sleeve", (3,)),
        EnsembleConfig("adv_6m_tv15", "ADV 6M Top10 target15", "single_sleeve", (6,)),
        EnsembleConfig("adv_mh136_tv15", "ADV MH136 Top10 target15", "candidate", (1, 3, 6)),
        EnsembleConfig("ablate_6m_mh13", "消融 6M：1M+3M", "ablation", (1, 3)),
        EnsembleConfig("ablate_3m_mh16", "消融 3M：1M+6M", "ablation", (1, 6)),
        EnsembleConfig("ablate_1m_mh36", "消融 1M：3M+6M", "ablation", (3, 6)),
        EnsembleConfig("mc4_mh136_tv12", "MH136 target12", "mc4", (1, 3, 6), target_vol=0.12),
        EnsembleConfig("mc4_mh136_tv18", "MH136 target18", "mc4", (1, 3, 6), target_vol=0.18),
        EnsembleConfig("all_mh136_tv15", "全上市 MH136 target15", "universe_control", (1, 3, 6), universe="all_listed"),
        EnsembleConfig("stress_mh136_cost2x", "MH136 成本 2x", "stress", (1, 3, 6), cost_multiplier=2.0),
        EnsembleConfig("stress_mh136_delay1d", "MH136 延迟 1d", "stress", (1, 3, 6), delay_days=1),
    ]


def _source_payload(
    universe: str,
    horizon: int,
    close: pd.DataFrame,
    open_: pd.DataFrame,
    bars: pd.DataFrame,
    quote: pd.DataFrame,
    funding: pd.DataFrame,
    bases: dict[str, str],
) -> dict[str, Any]:
    variant = ext.Variant(
        f"source_{universe}_{horizon}m",
        f"source {horizon}m",
        "source",
        universe=universe,
        formation_months=horizon,
        n_legs=10,
        long_only=True,
    )
    return ext._simulate(variant, close, open_, bars, quote, funding, bases)


def _unscaled_sleeve_weights(
    payload: dict[str, Any],
    close: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[pd.Timestamp, dict[str, Any]]]:
    rows = live._holdings_by_month(payload)
    weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for month_start, row in rows.items():
        if month_start not in weights.index:
            continue
        end = min(month_start + pd.offsets.MonthEnd(0), weights.index.max())
        weights.loc[month_start:end] = live._month_target(row, close.columns, "top_n").to_numpy()
    return weights, rows


def _build_ensemble_weights(
    config: EnsembleConfig,
    sources: dict[tuple[str, int], dict[str, Any]],
    close: pd.DataFrame,
    open_: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    sleeve_weights: dict[int, pd.DataFrame] = {}
    sleeve_rows: dict[int, dict[pd.Timestamp, dict[str, Any]]] = {}
    for horizon in config.horizons:
        weights, rows = _unscaled_sleeve_weights(sources[(config.universe, horizon)], close)
        sleeve_weights[horizon] = weights
        sleeve_rows[horizon] = rows
    unscaled = sum(sleeve_weights.values()) / len(sleeve_weights)
    unscaled_price = live._price_returns(unscaled, close, open_)
    asset_vol = (
        close.pct_change(fill_method=None)
        .rolling(ext.ASSET_VOL_WINDOW, min_periods=ext.ASSET_VOL_MIN_PERIODS)
        .std(ddof=0)
        * math.sqrt(base.ANNUALIZER)
    )
    month_starts = sorted(set.intersection(*(set(rows) for rows in sleeve_rows.values())))
    changes: dict[pd.Timestamp, pd.Series] = {}
    holdings: list[dict[str, Any]] = []
    for month_start in month_starts:
        if month_start < EVALUATION_START or month_start not in close.index:
            continue
        targets = [live._month_target(sleeve_rows[h][month_start], close.columns, "top_n") for h in config.horizons]
        combined = sum(targets) / len(targets)
        all_traded = all(sleeve_rows[h][month_start].get("status") == "traded" for h in config.horizons)
        if not all_traded:
            combined[:] = 0.0
        scale = live._risk_scale(month_start, combined, unscaled_price, asset_vol, config.target_vol)
        desired = combined * scale
        effective = month_start + pd.Timedelta(days=config.delay_days)
        month_end = min(month_start + pd.offsets.MonthEnd(0), close.index.max())
        if effective in close.index and effective <= month_end:
            changes[effective] = desired.copy()
        holding_row: dict[str, Any] = {
            "variant": config.id,
            "rebalance": str(month_start.date()),
            "status": "traded" if desired.abs().sum() > 0 else "cash",
            "portfolio_scale": scale,
            "target_gross": float(desired.abs().sum()),
            "effective_day": str(effective.date()) if effective in close.index and effective <= month_end else None,
            "unique_names": int(combined.gt(0).sum()),
            "max_unscaled_name_weight": float(combined.max()),
        }
        for horizon in config.horizons:
            holding_row[f"longs_{horizon}m"] = sleeve_rows[horizon][month_start].get("longs", "")
            holding_row[f"eligible_{horizon}m"] = sleeve_rows[horizon][month_start].get("eligible")
        holdings.append(holding_row)
    weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    current = pd.Series(0.0, index=close.columns)
    for day in close.index:
        if day in changes:
            current = changes[day]
        weights.loc[day] = current.to_numpy()
    weights.loc[weights.index < EVALUATION_START] = 0.0
    return weights, holdings


def _simulate(
    config: EnsembleConfig,
    sources: dict[tuple[str, int], dict[str, Any]],
    close: pd.DataFrame,
    open_: pd.DataFrame,
    quote: pd.DataFrame,
    funding: pd.DataFrame,
) -> dict[str, Any]:
    weights, holdings = _build_ensemble_weights(config, sources, close, open_)
    weights = weights.loc[EVALUATION_START:].copy()
    close_eval = close.loc[weights.index]
    open_eval = open_.loc[weights.index]
    funding_eval = funding.reindex_like(weights)
    price = live._price_returns(weights, close_eval, open_eval)
    prior = weights.shift(1).fillna(0.0)
    turnover = (weights - prior).abs().sum(axis=1)
    turnover.iloc[-1] += weights.iloc[-1].abs().sum()
    funding_pnl = -(weights * funding_eval.fillna(0.0)).sum(axis=1)
    fee = turnover * live.FEE_RATE * config.cost_multiplier
    slippage = turnover * live.SLIPPAGE_RATE * config.cost_multiplier
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
            "horizons": ",".join(map(str, config.horizons)),
            "target_vol": config.target_vol,
            "cost_multiplier": config.cost_multiplier,
            "delay_days": config.delay_days,
            "n_rebalances": len(holdings),
            "mean_unique_names": float(np.mean([row["unique_names"] for row in holdings])),
            "mean_gross_exposure": float(weights.abs().sum(axis=1).mean()),
            "max_gross_exposure": float(weights.abs().sum(axis=1).max()),
            "max_name_weight": float(weights.max().max()),
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
    metrics.update(live._path_diagnostics(net))
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
        }
    )
    return {"config": config, "metrics": metrics, "daily": daily, "holdings": holdings, "weights": weights, "quote": quote}


def _acceptance(payloads: dict[str, dict[str, Any]], cohort_frame: pd.DataFrame) -> dict[str, Any]:
    main = payloads["adv_mh136_tv15"]["metrics"]
    holdout = live._slice_metrics(payloads["adv_mh136_tv15"], HOLDOUT_START)
    complete = cohort_frame[(cohort_frame.variant == "adv_mh136_tv15") & cohort_frame.complete_12m]
    positive_rate = float((complete.total_return > 0).mean()) if len(complete) else 0.0
    ablations = [payloads[key]["metrics"] for key in ("ablate_6m_mh13", "ablate_3m_mh16", "ablate_1m_mh36")]
    dominated = [
        row["variant"]
        for row in ablations
        if row["cagr"] > main["cagr"] and row["sharpe"] > main["sharpe"] and row["max_drawdown"] > main["max_drawdown"]
    ]
    checks = {
        "full_sharpe_gte_0_8": main["sharpe"] >= 0.8,
        "full_mdd_gte_minus_25pct": main["max_drawdown"] >= -0.25,
        "full_cagr_gte_10pct": main["cagr"] >= 0.10,
        "holdout_total_return_gt_0": holdout["total_return"] > 0,
        "holdout_mdd_gte_minus_20pct": holdout["max_drawdown"] >= -0.20,
        "complete_12m_positive_rate_gte_60pct": positive_rate >= 0.60,
        "stress_2x_positive": payloads["stress_mh136_cost2x"]["metrics"]["total_return"] > 0,
        "target12_and_18_positive": payloads["mc4_mh136_tv12"]["metrics"]["total_return"] > 0 and payloads["mc4_mh136_tv18"]["metrics"]["total_return"] > 0,
        "all_listed_control_positive": payloads["all_mh136_tv15"]["metrics"]["total_return"] > 0,
        "not_dominated_by_single_sleeve_ablation": not dominated,
        "no_leverage": main["max_gross_exposure"] <= 1.0 + 1e-12,
        "no_nonpositive_equity": main["nonpositive_equity_days"] == 0,
    }
    return {
        "checks": {key: bool(value) for key, value in checks.items()},
        "all_reference_lines_pass": bool(all(checks.values())),
        "complete_12m_positive_rate": positive_rate,
        "dominating_ablations": dominated,
        "holdout": holdout,
    }


def _self_test() -> None:
    index = pd.date_range("2020-01-01", periods=320, freq="D")
    close = pd.DataFrame({"A": 100.0, "B": 100.0, "C": 100.0}, index=index)
    open_ = close.copy()
    sources: dict[tuple[str, int], dict[str, Any]] = {}
    names = {1: "A", 3: "B", 6: "C"}
    for horizon, symbol in names.items():
        sources[("adv10m", horizon)] = {
            "holdings": [
                {"rebalance": str(day.date()), "status": "traded", "eligible": 10, "longs": symbol}
                for day in pd.date_range("2020-08-01", "2020-11-01", freq="MS")
            ]
        }
    config = EnsembleConfig("test", "test", "test", (1, 3, 6), target_vol=None)
    weights, holdings = _build_ensemble_weights(config, sources, close, open_)
    first = weights.loc[pd.Timestamp("2020-08-01")]
    assert np.isclose(first.loc[["A", "B", "C"]].sum(), 0.1)
    assert all(np.isclose(first.loc[symbol], 1 / 30) for symbol in "ABC")
    assert holdings[0]["unique_names"] == 3
    print("self-test ok")


def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test()
        return
    close, open_, bars, quote, funding, bases, cache_meta, audit = long10.load_inputs()
    required = {(config.universe, horizon) for config in configs() for horizon in config.horizons}
    sources: dict[tuple[str, int], dict[str, Any]] = {}
    for universe, horizon in sorted(required):
        print(f"building source {universe} {horizon}m", flush=True)
        sources[(universe, horizon)] = _source_payload(universe, horizon, close, open_, bars, quote, funding, bases)
    payloads: dict[str, dict[str, Any]] = {}
    for config in configs():
        print(f"running {config.id}", flush=True)
        payloads[config.id] = _simulate(config, sources, close, open_, quote, funding)
    benchmark_source = live._baseline_payload("adv10m", "all_equal", close, open_, bars, quote, funding, bases)
    benchmark_config = live.OverlayConfig(
        "adv_equal_market_tv15",
        "ADV 全市场等权 target15",
        "benchmark",
        target_vol=TARGET_VOL,
        selection="all_equal",
    )
    payloads[benchmark_config.id] = live._simulate_overlay(benchmark_config, benchmark_source, close, open_, quote, funding)

    metrics = pd.DataFrame([payload["metrics"] for payload in payloads.values()])
    daily = pd.concat([payload["daily"] for payload in payloads.values()], ignore_index=True)
    holdings = pd.DataFrame([row for payload in payloads.values() for row in payload["holdings"]])
    yearly_rows: list[pd.DataFrame] = []
    recent_rows: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []
    cohort_rows: list[dict[str, Any]] = []
    for payload in payloads.values():
        variant = payload["metrics"]["variant"]
        net = payload["daily"].set_index("day")["net_return"]
        yearly = ((1.0 + net).resample("YE").prod() - 1.0).rename("net_return").reset_index()
        yearly["year"] = yearly.day.dt.year
        yearly["variant"] = variant
        yearly_rows.append(yearly[["variant", "year", "net_return"]])
        recent_rows.extend({"variant": variant, **row} for row in base.recent_slices(net))
        split_rows.append({"slice": "development", **live._slice_metrics(payload, EVALUATION_START, HOLDOUT_START - pd.Timedelta(days=1))})
        split_rows.append({"slice": "holdout_exposed_regime", **live._slice_metrics(payload, HOLDOUT_START)})
        cohort_rows.extend(live._cohort_rows(payload))
    cohort_frame = pd.DataFrame(cohort_rows)
    candidate = payloads["adv_mh136_tv15"]
    capacity = live._capacity_rows(candidate, quote)
    bootstrap = live._bootstrap_months(candidate)
    excess = live._excess_summary(candidate, payloads["adv_equal_market_tv15"])
    acceptance = _acceptance(payloads, cohort_frame)
    monthly_compare = []
    for variant in ("adv_1m_tv15", "adv_3m_tv15", "adv_6m_tv15", "adv_mh136_tv15"):
        net = payloads[variant]["daily"].set_index("day")["net_return"]
        monthly = ((1.0 + net).resample("ME").prod() - 1.0).rename(variant)
        monthly_compare.append(monthly)
    monthly_frame = pd.concat(monthly_compare, axis=1).reset_index()

    capacity_summary = []
    for participation in live.PARTICIPATION_RATES:
        column = f"max_aum_{participation * 100:g}pct_adv"
        values = capacity[column].dropna()
        capacity_summary.append(
            {
                "participation_rate": participation,
                "orders": int(len(values)),
                "min_aum": float(values.min()) if len(values) else None,
                "p05_aum": float(values.quantile(0.05)) if len(values) else None,
                "p10_aum": float(values.quantile(0.10)) if len(values) else None,
                "median_aum": float(values.median()) if len(values) else None,
            }
        )
    stem = f"binance-1d-mcsm-mh136-liveability-{args.run_date}"
    summary = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "family": long10.FAMILY_NAME,
        "alias": long10.FAMILY_ALIAS,
        "contract": SPEC,
        "candidate": asdict(next(config for config in configs() if config.id == "adv_mh136_tv15")),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "engine_sha256": hashlib.sha256(Path(ext.__file__).read_bytes()).hexdigest(),
        "cache": cache_meta,
        "audit": audit,
        "excess": excess,
        "capacity_summary": capacity_summary,
        "acceptance": acceptance,
        "metrics": metrics.to_dict(orient="records"),
    }
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
    base.write_csv(ARTIFACT_DIR / f"{stem}-monthly-comparison.csv", monthly_frame, force=args.force)
    print(
        metrics[["variant", "group", "total_return", "cagr", "ann_vol", "sharpe", "max_drawdown", "ann_turnover", "mean_gross_exposure"]].to_string(index=False)
    )
    print("acceptance", acceptance)


if __name__ == "__main__":
    main()
