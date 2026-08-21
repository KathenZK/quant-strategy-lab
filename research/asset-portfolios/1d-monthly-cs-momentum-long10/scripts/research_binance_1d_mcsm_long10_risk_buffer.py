#!/usr/bin/env python3
"""Run the frozen Top10 20% volatility-target and 10/20 buffer diagnostic."""

from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

import research_binance_1d_mcsm_long10 as long10


ext = long10.ext
base = long10.base
FAMILY_DIR = long10.FAMILY_DIR
ARTIFACT_DIR = long10.ARTIFACT_DIR
FAMILY_NAME = long10.FAMILY_NAME
FAMILY_ALIAS = long10.FAMILY_ALIAS
TARGET_VOL = 0.20
SCALE_MIN = 0.0
SCALE_MAX = 1.0
ENTRY_RANK = 10
EXIT_RANK = 20
SPEC = "specs/binance-1d-mcsm-long10-risk-buffer-diagnostic-contract-2026-08-19.md"


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
                    "risk_buffer",
                    universe=universe,
                    n_legs=ENTRY_RANK,
                    long_only=True,
                ),
                ext.Variant(
                    f"{prefix}_top10_target20_noleverage",
                    f"{universe_label} Top10 + 20%目标波动 + 无杠杆",
                    "risk_buffer",
                    universe=universe,
                    n_legs=ENTRY_RANK,
                    long_only=True,
                    portfolio_vol_target=TARGET_VOL,
                ),
                ext.Variant(
                    f"{prefix}_top10_buffer10_20_target20_noleverage",
                    f"{universe_label} Top10 + 10/20缓冲 + 20%目标波动 + 无杠杆",
                    "risk_buffer",
                    universe=universe,
                    selection="top_n_buffer",
                    n_legs=ENTRY_RANK,
                    long_only=True,
                    portfolio_vol_target=TARGET_VOL,
                ),
            ]
        )
    return variants


def _buffer_picker() -> Callable[..., tuple[list[str], list[str]] | None]:
    previous_longs: list[str] = []

    def pick(
        variant: ext.Variant,
        formation: pd.Series,
        long_eligible: pd.Series,
        short_eligible: pd.Series,
        adv: pd.Series,
        has_open: pd.Series,
    ) -> tuple[list[str], list[str]] | None:
        del short_eligible
        nonlocal previous_longs
        finite = formation.notna() & np.isfinite(formation)
        pool = formation.loc[finite & long_eligible]
        ordered_all = (
            pd.DataFrame({"signal": pool, "adv": adv.reindex(pool.index).fillna(-1.0)})
            .sort_values(["signal", "adv"], ascending=[False, False])
            .index.astype(str)
            .tolist()
        )
        ordered = [symbol for symbol in ordered_all if bool(has_open.get(symbol, False))]
        entry_rank = int(variant.n_legs or ENTRY_RANK)
        exit_rank = 2 * entry_rank
        if len(ordered) < entry_rank:
            previous_longs = []
            return None
        exit_set = set(ordered[:exit_rank])
        retained = [symbol for symbol in previous_longs if symbol in exit_set]
        entrants = [symbol for symbol in ordered[:entry_rank] if symbol not in retained]
        longs = (retained + entrants)[:entry_rank]
        if len(longs) < entry_rank:
            previous_longs = []
            return None
        previous_longs = longs.copy()
        return longs, []

    return pick


def _simulate_frozen(
    variant: ext.Variant,
    close: pd.DataFrame,
    open_: pd.DataFrame,
    bars: pd.DataFrame,
    quote: pd.DataFrame,
    funding: pd.DataFrame,
    bases: dict[str, str],
) -> dict[str, Any]:
    original_pick = ext._pick
    original_scale_min = ext.PORTFOLIO_SCALE_MIN
    original_scale_max = ext.PORTFOLIO_SCALE_MAX
    try:
        ext.PORTFOLIO_SCALE_MIN = SCALE_MIN
        ext.PORTFOLIO_SCALE_MAX = SCALE_MAX
        if variant.selection == "top_n_buffer":
            ext._pick = _buffer_picker()
        return ext._simulate(variant, close, open_, bars, quote, funding, bases)
    finally:
        ext._pick = original_pick
        ext.PORTFOLIO_SCALE_MIN = original_scale_min
        ext.PORTFOLIO_SCALE_MAX = original_scale_max


def _path_diagnostics(daily: pd.DataFrame) -> dict[str, Any]:
    frame = daily.set_index("day").sort_index()
    equity = (1.0 + frame["net_return"]).cumprod()
    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1.0
    trough = drawdown.idxmin()
    peak = equity.loc[:trough].idxmax()
    after_trough = equity.loc[trough:]
    recovered = after_trough.loc[after_trough >= equity.loc[peak]]
    recovery = recovered.index.min() if len(recovered) else None

    longest = 0
    underwater_start: pd.Timestamp | None = None
    for day, value in drawdown.items():
        if value < -1e-14 and underwater_start is None:
            underwater_start = pd.Timestamp(day)
        elif value >= -1e-14 and underwater_start is not None:
            longest = max(longest, (pd.Timestamp(day) - underwater_start).days)
            underwater_start = None
    if underwater_start is not None:
        longest = max(longest, (pd.Timestamp(drawdown.index[-1]) - underwater_start).days + 1)
    return {
        "max_drawdown_peak": str(pd.Timestamp(peak).date()),
        "max_drawdown_trough": str(pd.Timestamp(trough).date()),
        "max_drawdown_recovery": str(pd.Timestamp(recovery).date()) if recovery is not None else None,
        "longest_underwater_days": int(longest),
        "final_vs_hwm": float(equity.iloc[-1] / running_peak.iloc[-1] - 1.0),
    }


def _holding_diagnostics(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    traded = [row for row in holdings if row.get("status") == "traded"]
    overlaps: list[int] = []
    for prior, current in zip(traded, traded[1:]):
        prior_set = set(str(prior.get("longs", "")).split(","))
        current_set = set(str(current.get("longs", "")).split(","))
        overlaps.append(len(prior_set & current_set))
    scales = [float(row.get("portfolio_scale", 1.0)) for row in traded]
    return {
        "mean_monthly_name_overlap": float(np.mean(overlaps)) if overlaps else None,
        "median_monthly_name_overlap": float(np.median(overlaps)) if overlaps else None,
        "zero_replacement_month_rate": float(np.mean(np.asarray(overlaps) == ENTRY_RANK)) if overlaps else None,
        "mean_monthly_scale": float(np.mean(scales)) if scales else None,
        "median_monthly_scale": float(np.median(scales)) if scales else None,
        "min_monthly_scale": float(np.min(scales)) if scales else None,
        "max_monthly_scale": float(np.max(scales)) if scales else None,
    }


def _self_test() -> None:
    picker = _buffer_picker()
    variant = ext.Variant(
        "buffer_test",
        "buffer test",
        "test",
        selection="top_n_buffer",
        n_legs=3,
        long_only=True,
    )
    symbols = list("ABCDEFG")
    eligible = pd.Series(True, index=symbols)
    adv = pd.Series(1.0, index=symbols)
    has_open = pd.Series(True, index=symbols)
    first = pd.Series({symbol: 7 - idx for idx, symbol in enumerate(symbols)})
    picked = picker(variant, first, eligible, eligible, adv, has_open)
    assert picked == (["A", "B", "C"], []), picked
    second = pd.Series({"C": 7, "D": 6, "E": 5, "A": 4, "F": 3, "B": 2, "G": 1})
    picked = picker(variant, second, eligible, eligible, adv, has_open)
    assert picked == (["A", "B", "C"], []), picked
    third = pd.Series({"C": 7, "D": 6, "E": 5, "A": 4, "F": 3, "G": 2, "B": 1})
    picked = picker(variant, third, eligible, eligible, adv, has_open)
    assert picked == (["A", "C", "D"], []), picked
    assert SCALE_MAX == 1.0
    print("self-test ok")


def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test()
        return

    close, open_, bars, quote, funding, bases, cache_meta, audit = long10.load_inputs()
    payloads: list[dict[str, Any]] = []
    for variant in strategy_variants():
        print(f"running {variant.id}", flush=True)
        payload = _simulate_frozen(variant, close, open_, bars, quote, funding, bases)
        payload["metrics"].update(_path_diagnostics(payload["daily"]))
        payload["metrics"].update(_holding_diagnostics(payload["holdings"]))
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
    scale_rows = []
    for payload in payloads:
        for row in payload["holdings"]:
            if row.get("status") == "traded":
                scale_rows.append(
                    {
                        "variant": payload["metrics"]["variant"],
                        "rebalance": row["rebalance"],
                        "eligible": row["eligible"],
                        "portfolio_scale": row.get("portfolio_scale", 1.0),
                        "longs": row.get("longs", ""),
                    }
                )

    stem = f"binance-1d-mcsm-long10-risk-buffer-{args.run_date}"
    summary = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "family": FAMILY_NAME,
        "alias": FAMILY_ALIAS,
        "contract": SPEC,
        "frozen_parameters": {
            "target_vol": TARGET_VOL,
            "portfolio_vol_window": ext.PORTFOLIO_VOL_WINDOW,
            "portfolio_vol_min_periods": ext.PORTFOLIO_VOL_MIN_PERIODS,
            "scale_min": SCALE_MIN,
            "scale_max": SCALE_MAX,
            "entry_rank": ENTRY_RANK,
            "exit_rank": EXIT_RANK,
        },
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "engine_sha256": hashlib.sha256(Path(ext.__file__).read_bytes()).hexdigest(),
        "baseline_engine_sha256": hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest(),
        "cache": cache_meta,
        "audit": audit,
        "metrics": metrics.to_dict(orient="records"),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    base.write_json(ARTIFACT_DIR / f"{stem}-summary.json", summary, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-metrics.csv", metrics, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-attribution.csv", attribution, force=args.force)
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
    base.write_csv(
        ARTIFACT_DIR / f"{stem}-monthly-scales.csv",
        pd.DataFrame(scale_rows),
        force=args.force,
    )
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
                "mean_monthly_name_overlap",
                "median_monthly_scale",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
