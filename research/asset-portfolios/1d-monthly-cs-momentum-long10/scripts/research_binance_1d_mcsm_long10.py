#!/usr/bin/env python3
"""Run the independent Binance monthly cross-sectional long-only Top10 diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LS3_SCRIPTS = ROOT / "research/asset-portfolios/1d-monthly-cs-momentum-ls3/scripts"
sys.path.insert(0, str(LS3_SCRIPTS))

import research_binance_1d_mcsm_extensions as ext  # noqa: E402
import research_binance_1d_mcsm_ls3 as base  # noqa: E402


FAMILY_DIR = ROOT / "research/asset-portfolios/1d-monthly-cs-momentum-long10"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
FAMILY_NAME = "Binance-1D-Monthly-Cross-Sectional-Momentum-Long10"
FAMILY_ALIAS = "BIN-1D-MCSM-L10"
EVALUATION_START = pd.Timestamp("2020-03-01")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def strategy_variants() -> list[ext.Variant]:
    return [
        ext.Variant(
            "all_top10_long_only",
            "全上市 Top10 long-only",
            "strategy",
            n_legs=10,
            long_only=True,
        ),
        ext.Variant(
            "adv10m_top10_long_only",
            "ADV≥1000万 Top10 long-only",
            "strategy",
            universe="adv10m",
            n_legs=10,
            long_only=True,
        ),
        ext.Variant(
            "all_top3_long_only_control",
            "全上市 Top3 long-only control",
            "control",
            n_legs=3,
            long_only=True,
        ),
        ext.Variant(
            "adv10m_top3_long_only_control",
            "ADV≥1000万 Top3 long-only control",
            "control",
            universe="adv10m",
            n_legs=3,
            long_only=True,
        ),
        ext.Variant(
            "all_market_equal_weight",
            "全上市合资格合约月度等权",
            "benchmark",
            selection="all_equal",
            long_only=True,
            forced_start=str(EVALUATION_START.date()),
        ),
        ext.Variant(
            "btc_perp_long",
            "BTC 永续 long-only",
            "benchmark",
            selection="fixed",
            fixed_symbol="BTC",
            long_only=True,
            forced_start=str(EVALUATION_START.date()),
        ),
        ext.Variant(
            "eth_perp_long",
            "ETH 永续 long-only",
            "benchmark",
            selection="fixed",
            fixed_symbol="ETH",
            long_only=True,
            forced_start=str(EVALUATION_START.date()),
        ),
    ]


def load_inputs() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, str],
    dict[str, Any],
    dict[str, Any],
]:
    cache_meta = base.ensure_daily_cache(rebuild=False)
    ohlcv, funding_long, bases = base.load_panel()
    audit = base.audit_panel(ohlcv, bases)
    audit["funding_rows"] = int(len(funding_long))
    close = base.pivot(ohlcv, "close")
    open_ = base.pivot(ohlcv, "open")
    bars = base.pivot(ohlcv, "bars_15m")
    quote = base.pivot(ohlcv, "quote_volume")
    full_index = pd.date_range(close.index.min(), close.index.max(), freq="D")
    close = close.reindex(full_index)
    open_ = open_.reindex(full_index)
    bars = bars.reindex(full_index)
    quote = quote.reindex(full_index)
    funding = funding_long.pivot(index="day", columns="sym_key", values="funding_rate")
    funding = funding.reindex(index=close.index, columns=close.columns)
    return close, open_, bars, quote, funding, bases, cache_meta, audit


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
    assert not march["shorts"], march
    assert result["metrics"]["mean_gross_exposure"] == 1.0
    print("self-test ok")


def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test()
        return

    close, open_, bars, quote, funding, bases, cache_meta, audit = load_inputs()
    payloads = []
    for variant in strategy_variants():
        print(f"running {variant.id}", flush=True)
        payloads.append(ext._simulate(variant, close, open_, bars, quote, funding, bases))
    payloads.extend(
        [
            ext._price_only_benchmark("BTC", close),
            ext._price_only_benchmark("ETH", close),
        ]
    )

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

    attribution = metrics.loc[
        metrics["variant"].isin(["all_top10_long_only", "adv10m_top10_long_only"]),
        [
            "variant",
            "label",
            "price_pnl_sum",
            "funding_pnl_sum",
            "fee_pnl_sum",
            "slippage_pnl_sum",
            "arithmetic_total_pnl_sum",
            "total_return",
        ],
    ].copy()
    stem = f"binance-1d-mcsm-long10-diagnostic-{args.run_date}"
    summary = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "family": FAMILY_NAME,
        "alias": FAMILY_ALIAS,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "engine_sha256": hashlib.sha256(Path(ext.__file__).read_bytes()).hexdigest(),
        "baseline_engine_sha256": hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest(),
        "cache": cache_meta,
        "audit": audit,
        "contract": "specs/binance-1d-mcsm-long10-diagnostic-contract-2026-08-18.md",
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
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
