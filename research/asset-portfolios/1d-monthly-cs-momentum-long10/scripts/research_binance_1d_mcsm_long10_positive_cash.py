#!/usr/bin/env python3
"""Run the frozen positive-formation-only Top10 cash-residual diagnostic."""

from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

import research_binance_1d_mcsm_long10 as long10
import research_binance_1d_mcsm_long10_risk_buffer as risk


ext = long10.ext
base = long10.base
ARTIFACT_DIR = long10.ARTIFACT_DIR
FAMILY_NAME = long10.FAMILY_NAME
FAMILY_ALIAS = long10.FAMILY_ALIAS
ENTRY_RANK = 10
SLOT_WEIGHT = 0.10
TARGET_VOL = 0.20
SPEC = "specs/binance-1d-mcsm-long10-positive-cash-diagnostic-contract-2026-08-19.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def strategy_variants() -> list[ext.Variant]:
    variants: list[ext.Variant] = []
    for universe, prefix, universe_label in (
        ("all_listed", "all", "全上市"),
        ("adv10m", "adv10m", "ADV≥1000万"),
    ):
        variants.extend(
            [
                ext.Variant(
                    f"{prefix}_top10_baseline",
                    f"{universe_label} Top10 baseline",
                    "positive_cash",
                    universe=universe,
                    n_legs=ENTRY_RANK,
                    long_only=True,
                ),
                ext.Variant(
                    f"{prefix}_top10_positive_cash",
                    f"{universe_label} Top10 正收益限定 + 现金缺口",
                    "positive_cash",
                    universe=universe,
                    selection="top_n_positive_cash",
                    n_legs=ENTRY_RANK,
                    long_only=True,
                ),
                ext.Variant(
                    f"{prefix}_top10_target20_noleverage",
                    f"{universe_label} Top10 + 20%目标波动",
                    "positive_cash",
                    universe=universe,
                    n_legs=ENTRY_RANK,
                    long_only=True,
                    portfolio_vol_target=TARGET_VOL,
                ),
                ext.Variant(
                    f"{prefix}_top10_positive_cash_target20_noleverage",
                    f"{universe_label} Top10 正收益限定 + 现金缺口 + 20%目标波动",
                    "positive_cash",
                    universe=universe,
                    selection="top_n_positive_cash",
                    n_legs=ENTRY_RANK,
                    long_only=True,
                    portfolio_vol_target=TARGET_VOL,
                ),
            ]
        )
    return variants


def _positive_picker() -> Callable[..., tuple[list[str], list[str]] | None]:
    def pick(
        variant: ext.Variant,
        formation: pd.Series,
        long_eligible: pd.Series,
        short_eligible: pd.Series,
        adv: pd.Series,
        has_open: pd.Series,
    ) -> tuple[list[str], list[str]] | None:
        del short_eligible
        finite = formation.notna() & np.isfinite(formation)
        pool = formation.loc[finite & long_eligible]
        ordered_all = (
            pd.DataFrame({"signal": pool, "adv": adv.reindex(pool.index).fillna(-1.0)})
            .sort_values(["signal", "adv"], ascending=[False, False])
            .index.astype(str)
            .tolist()
        )
        ordered = [symbol for symbol in ordered_all if bool(has_open.get(symbol, False))]
        top = ordered[: int(variant.n_legs or ENTRY_RANK)]
        if len(top) < int(variant.n_legs or ENTRY_RANK):
            return None
        positive = [symbol for symbol in top if float(formation.loc[symbol]) > 0.0]
        return (positive, []) if positive else None

    return pick


def _positive_leg_weights(
    symbols: list[str],
    gross: float,
    vol: pd.Series | None,
) -> pd.Series:
    del gross
    if vol is not None:
        raise ValueError("positive-cash contract does not use inverse-vol leg weights")
    return pd.Series(SLOT_WEIGHT, index=symbols, dtype="float64")


def _simulate_positive_cash(
    variant: ext.Variant,
    close: pd.DataFrame,
    open_: pd.DataFrame,
    bars: pd.DataFrame,
    quote: pd.DataFrame,
    funding: pd.DataFrame,
    bases: dict[str, str],
) -> dict[str, Any]:
    original_pick = ext._pick
    original_leg_weights = ext._leg_weights
    original_scale_min = ext.PORTFOLIO_SCALE_MIN
    original_scale_max = ext.PORTFOLIO_SCALE_MAX
    try:
        ext._pick = _positive_picker()
        ext._leg_weights = _positive_leg_weights
        ext.PORTFOLIO_SCALE_MIN = 0.0
        ext.PORTFOLIO_SCALE_MAX = 1.0
        return ext._simulate(variant, close, open_, bars, quote, funding, bases)
    finally:
        ext._pick = original_pick
        ext._leg_weights = original_leg_weights
        ext.PORTFOLIO_SCALE_MIN = original_scale_min
        ext.PORTFOLIO_SCALE_MAX = original_scale_max


def _positive_count_audit(
    universe: str,
    close: pd.DataFrame,
    open_: pd.DataFrame,
    bars: pd.DataFrame,
    quote: pd.DataFrame,
    bases: dict[str, str],
) -> pd.DataFrame:
    excluded = base.excluded_mask(close.columns, bases)
    adv = quote.rolling(base.ADV_WINDOW, min_periods=base.ADV_WINDOW).mean()
    variant = ext.Variant(
        "audit",
        "audit",
        "audit",
        universe=universe,
        n_legs=ENTRY_RANK,
        long_only=True,
    )
    rows: list[dict[str, Any]] = []
    for month_start in base.month_starts(close.index):
        if month_start < long10.EVALUATION_START or month_start not in close.index:
            continue
        signal_meta = ext._signal(close, month_start, 1, 0)
        if signal_meta is None:
            continue
        formation, _, end_month, start_day, signal_end_day = signal_meta
        coverage = base.coverage_in_month(bars, end_month)
        endpoint_ok = (
            close.loc[start_day].notna()
            & close.loc[signal_end_day].notna()
            & bars.loc[start_day].ge(base.MIN_ENDPOINT_BARS)
            & bars.loc[signal_end_day].ge(base.MIN_ENDPOINT_BARS)
        )
        eligible = (~excluded) & endpoint_ok & coverage.ge(base.MIN_COVERAGE) & formation.notna()
        if universe == "adv10m":
            eligible &= adv.loc[signal_end_day].ge(base.MIN_ADV_USDT)
        picked = ext._pick(
            variant,
            formation,
            eligible,
            eligible,
            adv.loc[signal_end_day],
            open_.loc[month_start].notna(),
        )
        if picked is None:
            continue
        top10 = picked[0]
        positive = [symbol for symbol in top10 if float(formation.loc[symbol]) > 0.0]
        rows.append(
            {
                "universe": universe,
                "rebalance": str(month_start.date()),
                "eligible": int(eligible.sum()),
                "positive_count": len(positive),
                "cash_weight": 1.0 - SLOT_WEIGHT * len(positive),
                "all_nonpositive": len(positive) == 0,
                "all_positive": len(positive) == ENTRY_RANK,
                "top10": ",".join(top10),
                "positive_names": ",".join(positive),
                "max_formation": float(formation.reindex(top10).max()),
                "min_formation": float(formation.reindex(top10).min()),
            }
        )
    return pd.DataFrame(rows)


def _self_test() -> None:
    symbols = list("ABCDE")
    eligible = pd.Series(True, index=symbols)
    adv = pd.Series(1.0, index=symbols)
    has_open = pd.Series(True, index=symbols)
    variant = ext.Variant(
        "positive_test",
        "positive test",
        "test",
        selection="top_n_positive_cash",
        n_legs=3,
        long_only=True,
    )
    picker = _positive_picker()
    formation = pd.Series({"A": 0.30, "B": 0.20, "C": -0.01, "D": -0.10, "E": -0.20})
    picked = picker(variant, formation, eligible, eligible, adv, has_open)
    assert picked == (["A", "B"], []), picked
    weights = _positive_leg_weights(picked[0], 1.0, None)
    assert np.isclose(weights.sum(), 0.20)
    all_negative = pd.Series({symbol: -idx - 0.01 for idx, symbol in enumerate(symbols)})
    assert picker(variant, all_negative, eligible, eligible, adv, has_open) is None
    print("self-test ok")


def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test()
        return

    close, open_, bars, quote, funding, bases, cache_meta, audit = long10.load_inputs()
    positive_audits = pd.concat(
        [
            _positive_count_audit("all_listed", close, open_, bars, quote, bases),
            _positive_count_audit("adv10m", close, open_, bars, quote, bases),
        ],
        ignore_index=True,
    )
    payloads: list[dict[str, Any]] = []
    for variant in strategy_variants():
        print(f"running {variant.id}", flush=True)
        if variant.selection == "top_n_positive_cash":
            payload = _simulate_positive_cash(variant, close, open_, bars, quote, funding, bases)
        else:
            payload = risk._simulate_frozen(variant, close, open_, bars, quote, funding, bases)
        payload["metrics"].update(risk._path_diagnostics(payload["daily"]))
        payload["metrics"].update(risk._holding_diagnostics(payload["holdings"]))
        universe_audit = positive_audits.loc[positive_audits["universe"] == variant.universe]
        payload["metrics"].update(
            {
                "all_nonpositive_months": int(universe_audit["all_nonpositive"].sum()),
                "partial_positive_months": int(
                    ((universe_audit["positive_count"] > 0) & (universe_audit["positive_count"] < ENTRY_RANK)).sum()
                ),
                "all_positive_months": int(universe_audit["all_positive"].sum()),
                "mean_positive_count": float(universe_audit["positive_count"].mean()),
            }
        )
        payloads.append(payload)

    metrics = pd.DataFrame([payload["metrics"] for payload in payloads])
    daily = pd.concat([payload["daily"] for payload in payloads], ignore_index=True)
    holdings = pd.DataFrame([row for payload in payloads for row in payload["holdings"]])
    yearly_rows: list[pd.DataFrame] = []
    recent_rows: list[dict[str, Any]] = []
    for payload in payloads:
        variant_id = payload["metrics"]["variant"]
        net = payload["daily"].set_index("day")["net_return"]
        yearly = ((1.0 + net).resample("YE").prod() - 1.0).rename("net_return").reset_index()
        yearly["year"] = yearly["day"].dt.year
        yearly["variant"] = variant_id
        yearly_rows.append(yearly[["variant", "year", "net_return"]])
        recent_rows.extend({"variant": variant_id, **row} for row in base.recent_slices(net))

    attribution = metrics[
        [
            "variant",
            "label",
            "price_pnl_sum",
            "funding_pnl_sum",
            "fee_pnl_sum",
            "slippage_pnl_sum",
            "arithmetic_total_pnl_sum",
            "total_return",
        ]
    ].copy()
    stem = f"binance-1d-mcsm-long10-positive-cash-{args.run_date}"
    summary = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "family": FAMILY_NAME,
        "alias": FAMILY_ALIAS,
        "contract": SPEC,
        "frozen_parameters": {
            "positive_threshold": 0.0,
            "slot_weight": SLOT_WEIGHT,
            "cash_return": 0.0,
            "target_vol": TARGET_VOL,
            "scale_min": 0.0,
            "scale_max": 1.0,
        },
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "engine_sha256": hashlib.sha256(Path(ext.__file__).read_bytes()).hexdigest(),
        "baseline_engine_sha256": hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest(),
        "risk_wrapper_sha256": hashlib.sha256(Path(risk.__file__).read_bytes()).hexdigest(),
        "cache": cache_meta,
        "audit": audit,
        "positive_month_summary": (
            positive_audits.groupby("universe")["positive_count"]
            .agg(["count", "mean", "min", "max"])
            .reset_index()
            .to_dict(orient="records")
        ),
        "metrics": metrics.to_dict(orient="records"),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    base.write_json(ARTIFACT_DIR / f"{stem}-summary.json", summary, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-metrics.csv", metrics, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-attribution.csv", attribution, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-positive-months.csv", positive_audits, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-holdings.csv", holdings, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-daily-paths.csv", daily, force=args.force)
    base.write_csv(
        ARTIFACT_DIR / f"{stem}-yearly.csv",
        pd.concat(yearly_rows, ignore_index=True),
        force=args.force,
    )
    base.write_csv(
        ARTIFACT_DIR / f"{stem}-recent-slices.csv",
        pd.DataFrame(recent_rows),
        force=args.force,
    )
    print("positive-count audit")
    print(
        positive_audits.groupby(["universe", "positive_count"])
        .size()
        .rename("months")
        .reset_index()
        .to_string(index=False)
    )
    print("\nmetrics")
    print(
        metrics[
            [
                "variant",
                "total_return",
                "cagr",
                "ann_vol",
                "sharpe",
                "max_drawdown",
                "month_hit_rate",
                "ann_turnover",
                "mean_gross_exposure",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
