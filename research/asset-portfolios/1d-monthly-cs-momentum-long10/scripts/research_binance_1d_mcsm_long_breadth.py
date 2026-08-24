#!/usr/bin/env python3
"""Compare monthly Binance long-only momentum portfolios from Top10 to Top50."""

from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

import research_binance_1d_mcsm_long10 as long10


ext = long10.ext
base = long10.base
FAMILY_DIR = long10.FAMILY_DIR
ARTIFACT_DIR = long10.ARTIFACT_DIR
FAMILY_NAME = long10.FAMILY_NAME
FAMILY_ALIAS = long10.FAMILY_ALIAS
TOP_NS = (10, 20, 30, 40, 50)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def strategy_variants() -> list[ext.Variant]:
    variants: list[ext.Variant] = []
    for universe, prefix, label in (
        ("all_listed", "all", "全上市"),
        ("adv10m", "adv10m", "ADV≥1000万"),
    ):
        for n_legs in TOP_NS:
            variants.append(
                ext.Variant(
                    f"{prefix}_top{n_legs}_long_only",
                    f"{label} Top{n_legs} long-only",
                    "long_breadth",
                    universe=universe,
                    n_legs=n_legs,
                    long_only=True,
                )
            )
    return variants


def _self_test() -> None:
    ohlcv, funding_long, bases = base.make_synthetic_panel()
    close = base.pivot(ohlcv, "close")
    open_ = base.pivot(ohlcv, "open")
    bars = base.pivot(ohlcv, "bars_15m")
    quote = base.pivot(ohlcv, "quote_volume")
    funding = funding_long.pivot(index="day", columns="sym_key", values="funding_rate")
    variant = ext.Variant(
        "synthetic_top3_long",
        "synthetic",
        "test",
        universe="adv10m",
        n_legs=3,
        long_only=True,
    )
    result = ext._simulate(variant, close, open_, bars, quote, funding, bases)
    march = next(row for row in result["holdings"] if row["rebalance"] == "2021-03-01")
    assert set(march["longs"].split(",")) == {"AAA", "BBB", "CCC"}, march
    assert result["metrics"]["mean_gross_exposure"] == 1.0
    assert [variant.n_legs for variant in strategy_variants()] == [10, 20, 30, 40, 50] * 2
    print("self-test ok")


def _add_dynamic_common_metrics(payloads: list[dict[str, Any]]) -> str:
    common_start = max(pd.Timestamp(payload["metrics"]["start"]) for payload in payloads)
    for payload in payloads:
        net = payload["daily"].set_index("day")["net_return"].loc[common_start:]
        common = ext._performance(net)
        payload["metrics"].update(
            {
                "breadth_common_start": str(common_start.date()),
                "breadth_common_total_return": common["total_return"],
                "breadth_common_cagr": common["cagr"],
                "breadth_common_ann_vol": common["ann_vol"],
                "breadth_common_sharpe": common["sharpe"],
                "breadth_common_max_drawdown": common["max_drawdown"],
                "breadth_common_month_hit_rate": common["month_hit_rate"],
            }
        )
    return str(common_start.date())


def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test()
        return

    close, open_, bars, quote, funding, bases, cache_meta, audit = long10.load_inputs()
    payloads = []
    for variant in strategy_variants():
        print(f"running {variant.id}", flush=True)
        payloads.append(ext._simulate(variant, close, open_, bars, quote, funding, bases))

    breadth_common_start = _add_dynamic_common_metrics(payloads)
    metrics = pd.DataFrame([payload["metrics"] for payload in payloads])
    daily = pd.concat([payload["daily"] for payload in payloads], ignore_index=True)
    holdings = pd.DataFrame([row for payload in payloads for row in payload["holdings"]])
    yearly_rows: list[pd.DataFrame] = []
    for payload in payloads:
        variant_id = payload["metrics"]["variant"]
        net = payload["daily"].set_index("day")["net_return"]
        yearly = ((1.0 + net).resample("YE").prod() - 1.0).rename("net_return").reset_index()
        yearly["year"] = yearly["day"].dt.year
        yearly["variant"] = variant_id
        yearly_rows.append(yearly[["variant", "year", "net_return"]])

    stem = f"binance-1d-mcsm-long-breadth-{args.run_date}"
    summary = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "family": FAMILY_NAME,
        "alias": FAMILY_ALIAS,
        "purpose": "diagnostic Top10/20/30/40/50 long-only breadth sweep",
        "breadth_common_start": breadth_common_start,
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
    base.write_csv(ARTIFACT_DIR / f"{stem}-holdings.csv", holdings, force=args.force)
    base.write_csv(ARTIFACT_DIR / f"{stem}-daily-paths.csv", daily, force=args.force)
    base.write_csv(
        ARTIFACT_DIR / f"{stem}-yearly.csv",
        pd.concat(yearly_rows, ignore_index=True),
        force=args.force,
    )
    print(f"breadth common start: {breadth_common_start}")
    print(
        metrics[
            [
                "variant",
                "start",
                "total_return",
                "cagr",
                "ann_vol",
                "sharpe",
                "max_drawdown",
                "month_hit_rate",
                "breadth_common_total_return",
                "breadth_common_cagr",
                "breadth_common_sharpe",
                "breadth_common_max_drawdown",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
