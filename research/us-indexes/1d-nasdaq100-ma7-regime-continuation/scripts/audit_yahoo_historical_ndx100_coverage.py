from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONFIG_PATH = (
    FAMILY_DIR
    / "configs/ndx100-1d-ma7-regime-continuation-yahoo-historical-y1.json"
)
MEMBERSHIP_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_p0_membership_daily.parquet"
INTERVAL_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_p0_membership_intervals.csv"
PRICE_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_yahoo_ticker_prices.parquet"
FETCH_AUDIT_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_yahoo_fetch_audit.json"

MAPPING_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_member_price_mapping.parquet"
COVERAGE_BY_TICKER_PATH = (
    ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_coverage_by_membership_ticker.csv"
)
COVERAGE_BY_YEAR_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_coverage_by_year.csv"
FALLBACK_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_lineage_fallback.csv"
MISSING_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_missing_member_stock_days.csv"
AUDIT_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_coverage_audit.json"
BLOCKER_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_coverage_blocker.json"
MANIFEST_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y1_coverage_manifest.json"

STUDY_ID = "NDX100-1D-MA7-RC-Y1"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_price_mapping(
    membership: pd.DataFrame,
    prices: pd.DataFrame,
    intervals: pd.DataFrame,
) -> pd.DataFrame:
    """Map each point-in-time member-day to a Yahoo ticker without guessing.

    The frozen membership ticker is always preferred.  A renamed ticker may be
    used only when exactly one ticker from the same frozen entity lineage has a
    bar on that session.  Zero or multiple candidates remain missing.
    """
    membership = membership[
        ["session_date", "ticker", "entity_key"]
    ].copy()
    membership["session_date"] = pd.to_datetime(membership["session_date"])
    membership["ticker"] = membership["ticker"].astype(str)
    membership["entity_key"] = membership["entity_key"].astype(str)

    available = prices[["session_date", "ticker"]].drop_duplicates().copy()
    available["session_date"] = pd.to_datetime(available["session_date"])
    available["ticker"] = available["ticker"].astype(str)
    available["has_direct_price"] = True

    mapped = membership.merge(
        available,
        on=["session_date", "ticker"],
        how="left",
        validate="one_to_one",
    )
    mapped["source_ticker"] = mapped["ticker"].where(
        mapped["has_direct_price"].fillna(False)
    )
    mapped["mapping_method"] = pd.Series(
        pd.NA, index=mapped.index, dtype="string"
    )
    mapped.loc[mapped["source_ticker"].notna(), "mapping_method"] = "direct"

    lineage_pairs = intervals[["entity_key", "ticker"]].drop_duplicates().copy()
    lineage_pairs["entity_key"] = lineage_pairs["entity_key"].astype(str)
    lineage_pairs["ticker"] = lineage_pairs["ticker"].astype(str)
    candidates = lineage_pairs.merge(available, on="ticker", how="inner")
    candidates = candidates.rename(columns={"ticker": "candidate_ticker"})
    candidate_summary = (
        candidates.groupby(["entity_key", "session_date"], as_index=False)
        .agg(
            lineage_candidate_count=("candidate_ticker", "nunique"),
            lineage_source_ticker=("candidate_ticker", "first"),
        )
    )
    mapped = mapped.merge(
        candidate_summary,
        on=["entity_key", "session_date"],
        how="left",
        validate="many_to_one",
    )
    use_fallback = mapped["source_ticker"].isna() & mapped[
        "lineage_candidate_count"
    ].eq(1)
    mapped.loc[use_fallback, "source_ticker"] = mapped.loc[
        use_fallback, "lineage_source_ticker"
    ]
    mapped.loc[use_fallback, "mapping_method"] = "unique_entity_lineage"
    mapped.loc[mapped["source_ticker"].isna(), "mapping_method"] = "missing"
    mapped["lineage_candidate_count"] = (
        mapped["lineage_candidate_count"].fillna(0).astype(int)
    )
    return mapped[
        [
            "session_date",
            "ticker",
            "entity_key",
            "source_ticker",
            "mapping_method",
            "lineage_candidate_count",
        ]
    ].sort_values(["session_date", "ticker", "entity_key"])


def coverage_table(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    work = frame.copy()
    work["covered"] = work["mapping_method"].ne("missing")
    work["direct"] = work["mapping_method"].eq("direct")
    work["fallback"] = work["mapping_method"].eq("unique_entity_lineage")
    result = (
        work.groupby(keys, dropna=False, as_index=False)
        .agg(
            member_stock_days=("covered", "size"),
            covered_member_stock_days=("covered", "sum"),
            direct_member_stock_days=("direct", "sum"),
            lineage_fallback_member_stock_days=("fallback", "sum"),
        )
    )
    result["missing_member_stock_days"] = (
        result["member_stock_days"] - result["covered_member_stock_days"]
    )
    result["coverage_ratio"] = (
        result["covered_member_stock_days"] / result["member_stock_days"]
    )
    return result


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("study_id") != STUDY_ID:
        raise RuntimeError("unexpected Y1 config identity")
    threshold = float(
        config["research_contract"][
            "minimum_member_stock_day_coverage_for_results"
        ]
    )

    membership = pd.read_parquet(MEMBERSHIP_PATH)
    intervals = pd.read_csv(INTERVAL_PATH, dtype=str)
    prices = pd.read_parquet(PRICE_PATH)
    fetch_audit = json.loads(FETCH_AUDIT_PATH.read_text(encoding="utf-8"))
    mapping = build_price_mapping(membership, prices, intervals)

    terminal_date = pd.to_datetime(membership["session_date"]).max()
    terminal_tickers = set(
        membership.loc[
            pd.to_datetime(membership["session_date"]).eq(terminal_date), "ticker"
        ].astype(str)
    )
    mapping["terminal_constituent"] = mapping["ticker"].isin(terminal_tickers)
    mapping["historical_exit_ticker"] = ~mapping["terminal_constituent"]
    mapping.to_parquet(MAPPING_PATH, index=False)

    by_ticker = coverage_table(
        mapping,
        ["ticker", "entity_key", "terminal_constituent", "historical_exit_ticker"],
    ).sort_values(
        ["historical_exit_ticker", "missing_member_stock_days", "ticker"],
        ascending=[False, False, True],
    )
    raw_ticker_rows = prices.groupby("ticker").size().rename("raw_yahoo_rows")
    by_ticker = by_ticker.merge(
        raw_ticker_rows, left_on="ticker", right_index=True, how="left"
    )
    by_ticker["raw_yahoo_rows"] = by_ticker["raw_yahoo_rows"].fillna(0).astype(int)
    by_ticker["has_any_direct_membership_overlap"] = by_ticker[
        "direct_member_stock_days"
    ].gt(0)
    by_ticker.to_csv(COVERAGE_BY_TICKER_PATH, index=False)

    mapping["calendar_year"] = pd.to_datetime(mapping["session_date"]).dt.year
    by_year = coverage_table(mapping, ["calendar_year"])
    by_year.to_csv(COVERAGE_BY_YEAR_PATH, index=False)

    fallback = mapping.loc[
        mapping["mapping_method"].eq("unique_entity_lineage")
    ].copy()
    fallback.to_csv(FALLBACK_PATH, index=False)
    missing = mapping.loc[mapping["mapping_method"].eq("missing")].copy()
    missing.to_csv(MISSING_PATH, index=False)

    counts = mapping["mapping_method"].value_counts()
    total = int(len(mapping))
    direct = int(counts.get("direct", 0))
    lineage_fallback = int(counts.get("unique_entity_lineage", 0))
    missing_count = int(counts.get("missing", 0))
    covered = direct + lineage_fallback
    coverage_ratio = covered / total
    gate_pass = coverage_ratio >= threshold

    exited = by_ticker.loc[by_ticker["historical_exit_ticker"]]
    historical_exit_with_direct_data = int(
        exited["has_any_direct_membership_overlap"].sum()
    )
    historical_exit_with_any_coverage = int(
        exited["covered_member_stock_days"].gt(0).sum()
    )
    raw_but_no_overlap = by_ticker.loc[
        by_ticker["raw_yahoo_rows"].gt(0)
        & by_ticker["direct_member_stock_days"].eq(0),
        "ticker",
    ].astype(str).tolist()

    top_missing = (
        by_ticker.loc[by_ticker["missing_member_stock_days"].gt(0)]
        .sort_values("missing_member_stock_days", ascending=False)
        .head(25)[["ticker", "entity_key", "missing_member_stock_days", "coverage_ratio"]]
        .to_dict(orient="records")
    )
    audit = {
        "study_id": STUDY_ID,
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "COVERAGE_GATE_PASS" if gate_pass else "BLOCKED_INCOMPLETE_YAHOO_HISTORY",
        "gate": {
            "minimum_member_stock_day_coverage_for_results": threshold,
            "actual_coverage_ratio": coverage_ratio,
            "pass": gate_pass,
            "outcome_statistics_allowed": gate_pass,
        },
        "point_in_time_membership": {
            "first_session": pd.to_datetime(mapping["session_date"]).min(),
            "last_session": pd.to_datetime(mapping["session_date"]).max(),
            "sessions": int(mapping["session_date"].nunique()),
            "membership_tickers": int(mapping["ticker"].nunique()),
            "entities": int(mapping["entity_key"].nunique()),
            "member_stock_days": total,
        },
        "coverage": {
            "direct_member_stock_days": direct,
            "unique_entity_lineage_fallback_member_stock_days": lineage_fallback,
            "covered_member_stock_days": covered,
            "missing_member_stock_days": missing_count,
            "coverage_ratio": coverage_ratio,
            "ambiguous_lineage_member_stock_days": int(
                (
                    mapping["mapping_method"].eq("missing")
                    & mapping["lineage_candidate_count"].gt(1)
                ).sum()
            ),
        },
        "historical_exit_tickers": {
            "count": int(len(exited)),
            "with_direct_membership_price_data": historical_exit_with_direct_data,
            "with_any_price_coverage_after_lineage_fallback": historical_exit_with_any_coverage,
            "without_any_price_coverage_after_lineage_fallback": int(
                len(exited) - historical_exit_with_any_coverage
            ),
        },
        "fetch": {
            "historical_tickers_requested": fetch_audit["historical_ticker_count"],
            "historical_tickers_without_usable_yahoo_data": fetch_audit[
                "historical_tickers_without_usable_data"
            ],
            "request_failure_count": len(fetch_audit["request_failures"]),
            "raw_series_present_but_no_membership_date_overlap": raw_but_no_overlap,
        },
        "top_missing_membership_tickers": top_missing,
        "decision": (
            "Run frozen Y1 outcome statistics."
            if gate_pass
            else "Do not run Y1 MA7/regime outcomes; the partial Yahoo panel would reintroduce material survivorship and identifier bias."
        ),
    }
    write_json(AUDIT_PATH, audit)
    if not gate_pass:
        write_json(
            BLOCKER_PATH,
            {
                "study_id": STUDY_ID,
                "status": audit["status"],
                "blocked_stage": "event and regime outcome statistics",
                "coverage_ratio": coverage_ratio,
                "required_coverage_ratio": threshold,
                "missing_member_stock_days": missing_count,
                "reason": (
                    "Yahoo did not return a usable historical series for enough acquired, delisted, renamed, or ticker-reused constituents."
                ),
                "safe_completed_scope": (
                    "Historical ticker union fetch, point-in-time mapping, unique-lineage fallback, and coverage diagnostics."
                ),
            },
        )

    evidence_paths = [
        CONFIG_PATH,
        MAPPING_PATH,
        COVERAGE_BY_TICKER_PATH,
        COVERAGE_BY_YEAR_PATH,
        FALLBACK_PATH,
        MISSING_PATH,
        AUDIT_PATH,
    ]
    if BLOCKER_PATH.exists():
        evidence_paths.append(BLOCKER_PATH)
    manifest = {
        "study_id": STUDY_ID,
        "generated_at_utc": audit["generated_at_utc"],
        "files": {
            str(path.relative_to(FAMILY_DIR)): sha256_file(path)
            for path in evidence_paths
        },
    }
    write_json(MANIFEST_PATH, manifest)
    print(json.dumps(audit, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
