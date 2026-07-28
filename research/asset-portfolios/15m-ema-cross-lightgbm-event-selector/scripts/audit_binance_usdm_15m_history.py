"""Phase 0 data-quality freeze audit for the BIN-15M-EMAX-LGBM 15m lake.

Checks: union duplicate keys, per-symbol timestamp continuity, OHLC validity,
critical nulls, marker consistency, legacy-vs-archive OHLC parity sample, taker
field coverage, funding coverage. Emits a JSON artifact for the freeze
diagnostic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd

import emax_common as ec


PARITY_SAMPLE = [
    ("BTC", "btc_usdt_usdt", "BTCUSDT", "2021-05"),
    ("BTC", "btc_usdt_usdt", "BTCUSDT", "2024-03"),
    ("ETH", "eth_usdt_usdt", "ETHUSDT", "2022-11"),
    ("SOL", "sol_usdt_usdt", "SOLUSDT", "2025-01"),
    ("HYPE", "hype_usdt_usdt", "HYPEUSDT", "2025-06"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ec.ARTIFACT_DIR / "binance_usdm_15m_quality_audit.json",
    )
    return parser.parse_args()


def union_relation(con) -> str:
    # NULL-symbol rows come from a one-day exploratory dump of tokenized
    # stock/commodity perps with a minimal schema (2026-04-01); they are not
    # part of this family's crypto universe and are counted separately.
    globs = ", ".join(f"'{glob}'" for glob in ec.kline_globs())
    return f"(SELECT * FROM read_parquet([{globs}], union_by_name=true) WHERE symbol IS NOT NULL)"


def legacy_archive_parity(sym_slug: str, archive_symbol: str, month: str) -> dict:
    archive_path = (
        ec.ROOT
        / "data/raw/_archives/binance/futures/um/monthly/klines"
        / f"symbol={archive_symbol.lower()}"
        / "timeframe=15m"
        / f"year={month[:4]}"
        / f"{archive_symbol}-15m-{month}.zip"
    )
    if not archive_path.exists():
        return {"status": "archive_missing", "archive": str(archive_path)}
    with zipfile.ZipFile(BytesIO(archive_path.read_bytes())) as zf:
        member = [n for n in zf.namelist() if n.endswith(".csv")][0]
        with zf.open(member) as handle:
            frame = pd.read_csv(handle, header=None, low_memory=False)
    frame = frame.iloc[:, :7]
    frame.columns = ["open_time", "open", "high", "low", "close", "volume", "close_time"]
    frame["open_time"] = pd.to_numeric(frame["open_time"], errors="coerce")
    frame = frame.loc[frame["open_time"].notna()]
    frame["ts"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)

    legacy_paths = sorted(
        ec.KLINE_15M_ROOT.glob(f"date={month}-*/symbol={sym_slug}.parquet")
    )
    if not legacy_paths:
        return {"status": "no_legacy_files"}
    legacy = pd.concat([pd.read_parquet(p) for p in legacy_paths], ignore_index=True)
    legacy["ts"] = pd.to_datetime(legacy["ts"], utc=True)
    joined = legacy.merge(frame, on="ts", how="inner", suffixes=("_legacy", "_archive"))
    if len(joined) == 0:
        return {"status": "no_overlap"}
    mismatches = {}
    for column in ["open", "high", "low", "close"]:
        left = pd.to_numeric(joined[f"{column}_legacy"], errors="coerce")
        right = pd.to_numeric(joined[f"{column}_archive"], errors="coerce")
        mismatches[column] = int(
            (~np.isclose(left, right, rtol=1e-9, atol=1e-12)).sum()
        )
    return {
        "status": "compared",
        "rows_compared": int(len(joined)),
        "ohlc_mismatches": mismatches,
    }


def main() -> None:
    args = parse_args()
    con = ec.connect()
    rel = union_relation(con)

    totals = con.execute(
        f"""
        SELECT count(*) AS rows,
               count(DISTINCT symbol) AS symbols,
               min(ts) AS min_ts, max(ts) AS max_ts
        FROM {rel}
        """
    ).fetch_df().iloc[0]

    globs = ", ".join(f"'{glob}'" for glob in ec.kline_globs())
    null_symbol_rows = con.execute(
        f"""
        SELECT count(*) FROM read_parquet([{globs}], union_by_name=true)
        WHERE symbol IS NULL
        """
    ).fetchone()[0]

    duplicates = con.execute(
        f"""
        SELECT count(*) FROM (
            SELECT ts, symbol FROM {rel} GROUP BY ts, symbol HAVING count(*) > 1
        )
        """
    ).fetchone()[0]

    ohlc_violations = con.execute(
        f"""
        SELECT count(*) FROM {rel}
        WHERE high < open OR high < close OR low > open OR low > close
           OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
        """
    ).fetchone()[0]

    nulls = con.execute(
        f"""
        SELECT
            sum(CASE WHEN open IS NULL OR high IS NULL OR low IS NULL
                     OR close IS NULL THEN 1 ELSE 0 END) AS null_ohlc,
            sum(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) AS null_volume,
            sum(CASE WHEN quote_volume IS NULL THEN 1 ELSE 0 END) AS null_quote_volume,
            sum(CASE WHEN taker_buy_volume IS NULL THEN 1 ELSE 0 END) AS null_taker
        FROM {rel}
        """
    ).fetch_df().iloc[0]

    continuity = con.execute(
        f"""
        WITH per_symbol AS (
            SELECT symbol, min(ts) AS start_ts, max(ts) AS end_ts, count(*) AS bars
            FROM {rel} GROUP BY symbol
        )
        SELECT symbol, start_ts, end_ts, bars,
               CAST(date_diff('minute', start_ts, end_ts) / 15 + 1 AS BIGINT) AS expected,
               CAST(date_diff('minute', start_ts, end_ts) / 15 + 1 AS BIGINT) - bars AS missing
        FROM per_symbol ORDER BY missing DESC
        """
    ).fetch_df()
    continuity["missing_share"] = continuity["missing"] / continuity["expected"]

    markers = sorted(
        (ec.KLINE_15M_ROOT / "source=binance_vision_monthly").glob(
            "month=*/part-0000.complete.json"
        )
    )
    marker_rows = 0
    marker_overlap = 0
    for marker_path in markers:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker_rows += marker["normalized_rows_written"]
        marker_overlap += marker["legacy_overlap_excluded"]

    parity = {
        f"{sym}_{month}": legacy_archive_parity(slug, archive_symbol, month)
        for sym, slug, archive_symbol, month in PARITY_SAMPLE
    }

    funding_symbols = set(
        con.execute(
            f"""
            SELECT DISTINCT symbol FROM read_parquet(
                ['{ec.FUNDING_ROOT}/date=*/*.parquet',
                 '{ec.FUNDING_ROOT}/source=binance_vision_monthly/month=*/*.parquet'],
                union_by_name=true
            )
            """
        ).fetch_df()["symbol"]
    )
    kline_symbols = set(
        con.execute(f"SELECT DISTINCT symbol FROM {rel}").fetch_df()["symbol"]
    )
    missing_funding = sorted(kline_symbols - funding_symbols)

    worst = continuity.head(15)[
        ["symbol", "start_ts", "end_ts", "bars", "missing", "missing_share"]
    ].to_dict("records")
    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "union_rows": int(totals["rows"]),
        "union_symbols": int(totals["symbols"]),
        "null_symbol_rows_excluded": int(null_symbol_rows),
        "ts_range": [str(totals["min_ts"]), str(totals["max_ts"])],
        "duplicate_ts_symbol_keys": int(duplicates),
        "ohlc_violations": int(ohlc_violations),
        "nulls": {k: int(v) for k, v in nulls.items()},
        "monthly_marker_files": len(markers),
        "monthly_marker_rows": marker_rows,
        "monthly_marker_legacy_overlap_excluded": marker_overlap,
        "continuity": {
            "symbols_no_missing": int((continuity["missing"] == 0).sum()),
            "symbols_missing_share_over_1pct": int(
                (continuity["missing_share"] > 0.01).sum()
            ),
            "median_missing_share": float(continuity["missing_share"].median()),
            "worst_15": worst,
        },
        "legacy_archive_ohlc_parity_sample": parity,
        "symbols_without_funding": missing_funding,
        "taker_note": (
            "legacy daily partitions (7 symbols) have no taker columns by design; "
            "taker features are NaN there and LightGBM handles missing natively"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    compact = {
        k: report[k]
        for k in [
            "union_rows", "union_symbols", "ts_range", "duplicate_ts_symbol_keys",
            "ohlc_violations", "monthly_marker_legacy_overlap_excluded",
        ]
    }
    compact["continuity"] = report["continuity"] | {"worst_15": "see artifact"}
    print(json.dumps(compact, indent=2, default=str))
    print(json.dumps(parity, indent=2))
    print(f"audit -> {args.output}")


if __name__ == "__main__":
    main()
