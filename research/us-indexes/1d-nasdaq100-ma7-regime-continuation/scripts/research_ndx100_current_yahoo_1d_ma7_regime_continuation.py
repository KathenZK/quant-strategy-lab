from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import numpy as np
import pandas as pd


FAMILY_DIR = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[4]
BASE_SCRIPT = FAMILY_DIR / "scripts/research_ndx100_1d_ma7_regime_continuation.py"
BASE_CONFIG = FAMILY_DIR / "configs/ndx100-1d-ma7-regime-continuation-p0.json"
YAHOO_CONFIG = (
    FAMILY_DIR
    / "configs/ndx100-1d-ma7-regime-continuation-yahoo-current-y0.json"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PRICE_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y0_yahoo_prices.parquet"
PRICE_AUDIT_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y0_yahoo_price_audit.json"
UNIVERSE_PATH = ARTIFACT_DIR / "ndx100_1d_ma7_rc_y0_current_universe.csv"

PREFIX = "ndx100_1d_ma7_rc_y0"
STUDY_ID = "NDX100-1D-MA7-RC-Y0"
EVENT_PATH = ARTIFACT_DIR / f"{PREFIX}_events.parquet"
EDGE_PATH = ARTIFACT_DIR / f"{PREFIX}_regime_edges.json"
SINGLE_PATH = ARTIFACT_DIR / f"{PREFIX}_single_variable_stats.csv"
THREE_WAY_PATH = ARTIFACT_DIR / f"{PREFIX}_three_way_stats.csv"
ROBUSTNESS_PATH = ARTIFACT_DIR / f"{PREFIX}_robustness_stats.csv"
GAP_PATH = ARTIFACT_DIR / f"{PREFIX}_gap_diagnostic.csv"
MONOTONICITY_PATH = ARTIFACT_DIR / f"{PREFIX}_monotonicity.csv"
SURFACE_PATH = ARTIFACT_DIR / f"{PREFIX}_surface_diagnostics.csv"
UNCONDITIONAL_PATH = ARTIFACT_DIR / f"{PREFIX}_unconditional_stats.csv"
SUMMARY_PATH = ARTIFACT_DIR / f"{PREFIX}_summary.json"
CROSS_STATUS_PATH = ARTIFACT_DIR / f"{PREFIX}_cross_market_status.json"
CROSS_SINGLE_LONG_PATH = ARTIFACT_DIR / f"{PREFIX}_cross_market_single_variable_long.csv"
CROSS_SINGLE_WIDE_PATH = ARTIFACT_DIR / f"{PREFIX}_cross_market_single_variable_wide.csv"
CROSS_THREE_LONG_PATH = ARTIFACT_DIR / f"{PREFIX}_cross_market_three_way_long.csv"
CROSS_THREE_WIDE_PATH = ARTIFACT_DIR / f"{PREFIX}_cross_market_three_way_wide.csv"
CROSS_SINGLE_COMMON_PATH = ARTIFACT_DIR / f"{PREFIX}_cross_market_common_window_single_variable_wide.csv"
CROSS_THREE_COMMON_PATH = ARTIFACT_DIR / f"{PREFIX}_cross_market_common_window_three_way_wide.csv"

BINANCE_DIR = ROOT / "research/asset-portfolios/1d-ma7-regime-continuation/artifacts"
BINANCE_SINGLE = BINANCE_DIR / "binance_1d_ma7_rc_p0_single_variable_stats.csv"
BINANCE_THREE = BINANCE_DIR / "binance_1d_ma7_rc_p0_three_way_stats.csv"
BINANCE_EVENTS = BINANCE_DIR / "binance_1d_ma7_rc_p0_events.parquet"


def load_base_module() -> Any:
    spec = importlib.util.spec_from_file_location("ndx100_p0_kernel", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen Nasdaq-100 P0 kernel")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


KERNEL = load_base_module()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the survivorship-biased Yahoo current-NDX diagnostic."
    )
    parser.add_argument("--force", action="store_true", help="Replace Y0 results.")
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(KERNEL.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_configs() -> tuple[dict[str, Any], dict[str, Any]]:
    base = json.loads(BASE_CONFIG.read_text(encoding="utf-8"))
    yahoo = json.loads(YAHOO_CONFIG.read_text(encoding="utf-8"))
    if yahoo.get("study_id") != STUDY_ID:
        raise RuntimeError("unexpected Yahoo diagnostic identity")
    if yahoo["research_contract"].get("parameter_search") is not False:
        raise RuntimeError("parameter search must remain disabled")
    base["study_id"] = STUDY_ID
    base["data"]["study_start_session"] = yahoo["data"]["study_start_inclusive"]
    base["data"]["study_end_session_inclusive"] = yahoo["data"]["study_end_inclusive"]
    base["data"]["provider"] = yahoo["data"]["provider"]
    base["data"]["universe"] = yahoo["universe"]["definition"]
    return base, yahoo


def load_yahoo_panel_inputs(
    config: dict[str, Any], yahoo_config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if not PRICE_PATH.exists() or not UNIVERSE_PATH.exists() or not PRICE_AUDIT_PATH.exists():
        raise RuntimeError("run fetch_yahoo_current_ndx100_daily.py first")
    price_audit = json.loads(PRICE_AUDIT_PATH.read_text(encoding="utf-8"))
    if price_audit.get("universe_security_count") != 102:
        raise RuntimeError("Yahoo price artifact is not the complete frozen current snapshot")
    if price_audit.get("blockers_for_full_current_universe_study"):
        raise RuntimeError(
            "Yahoo price audit blockers: "
            f"{price_audit['blockers_for_full_current_universe_study']}"
        )
    universe = pd.read_csv(UNIVERSE_PATH, dtype={"ticker": str, "entity_key": str})
    prices = pd.read_parquet(PRICE_PATH)
    prices["session_date"] = pd.to_datetime(prices["session_date"])
    core = prices[
        ["session_date", "ticker", "open", "high", "low", "close", "volume"]
    ].copy()
    qqq = core.loc[core["ticker"].eq("QQQ")].copy()
    bars = core.loc[~core["ticker"].eq("QQQ")].merge(
        universe[["ticker", "entity_key"]], on="ticker", how="inner", validate="many_to_one"
    )
    if bars["ticker"].nunique() != len(universe):
        raise RuntimeError("not every frozen current security has a Yahoo price series")

    start = pd.Timestamp(config["data"]["study_start_session"])
    end = pd.Timestamp(config["data"]["study_end_session_inclusive"])
    calendar = xcals.get_calendar("XNAS")
    sessions = pd.DatetimeIndex(calendar.sessions_in_range(start, end)).tz_localize(None)
    membership = pd.MultiIndex.from_product(
        [universe["ticker"].astype(str), sessions], names=["ticker", "session_date"]
    ).to_frame(index=False)
    membership = membership.merge(
        universe[["ticker", "entity_key"]], on="ticker", validate="many_to_one"
    )
    first_observed = (
        bars.groupby("ticker", as_index=False)["session_date"]
        .min()
        .rename(columns={"session_date": "first_observed_session"})
    )
    membership = membership.merge(first_observed, on="ticker", validate="many_to_one")
    membership["membership_interval_start"] = membership[
        "first_observed_session"
    ].clip(lower=start)
    membership = membership.drop(columns="first_observed_session")

    qqq["entity_key"] = "QQQ"
    return bars, qqq, membership, price_audit


def cross_market(
    single: pd.DataFrame, three: pd.DataFrame, events: pd.DataFrame
) -> dict[str, Any]:
    missing = [
        str(path)
        for path in (BINANCE_SINGLE, BINANCE_THREE, BINANCE_EVENTS)
        if not path.exists()
    ]
    if missing:
        status = {
            "study_id": STUDY_ID,
            "status": "BLOCKED_COMPARISON_INPUT",
            "missing_binance_artifacts": missing,
        }
        write_json(CROSS_STATUS_PATH, status)
        return status
    crypto_single = pd.read_csv(BINANCE_SINGLE)
    crypto_three = pd.read_csv(BINANCE_THREE)
    combined_single = pd.concat(
        [
            KERNEL._market_frame(crypto_single, "Crypto"),
            KERNEL._market_frame(single, "Nasdaq100CurrentYahoo"),
        ],
        ignore_index=True,
        sort=False,
    )
    combined_three = pd.concat(
        [
            KERNEL._market_frame(crypto_three, "Crypto"),
            KERNEL._market_frame(three, "Nasdaq100CurrentYahoo"),
        ],
        ignore_index=True,
        sort=False,
    )
    combined_single.to_csv(CROSS_SINGLE_LONG_PATH, index=False)
    combined_three.to_csv(CROSS_THREE_LONG_PATH, index=False)
    KERNEL._wide_cross_market(
        combined_single, ["variable", "quintile", "horizon_days", "return_metric"]
    ).to_csv(CROSS_SINGLE_WIDE_PATH, index=False)
    KERNEL._wide_cross_market(
        combined_three,
        ["slope_q", "er_q", "rv_q", "horizon_days", "return_metric"],
    ).to_csv(CROSS_THREE_WIDE_PATH, index=False)

    crypto_dates = pd.to_datetime(
        pd.read_parquet(BINANCE_EVENTS, columns=["event_date"])["event_date"], utc=True
    ).dt.tz_localize(None)
    common_start = crypto_dates.min().normalize()
    common_end = crypto_dates.max().normalize()
    common_events = events.loc[events["session_date"].between(common_start, common_end)]
    common_single = pd.concat(
        [
            KERNEL._market_frame(crypto_single, "Crypto"),
            KERNEL._market_frame(
                KERNEL.build_single_variable_stats(common_events),
                "Nasdaq100CurrentYahoo",
            ),
        ],
        ignore_index=True,
        sort=False,
    )
    common_three = pd.concat(
        [
            KERNEL._market_frame(crypto_three, "Crypto"),
            KERNEL._market_frame(
                KERNEL.build_three_way_stats(common_events),
                "Nasdaq100CurrentYahoo",
            ),
        ],
        ignore_index=True,
        sort=False,
    )
    KERNEL._wide_cross_market(
        common_single, ["variable", "quintile", "horizon_days", "return_metric"]
    ).to_csv(CROSS_SINGLE_COMMON_PATH, index=False)
    KERNEL._wide_cross_market(
        common_three,
        ["slope_q", "er_q", "rv_q", "horizon_days", "return_metric"],
    ).to_csv(CROSS_THREE_COMMON_PATH, index=False)
    status = {
        "study_id": STUDY_ID,
        "status": "COMPARISON_WRITTEN_SURVIVORSHIP_BIASED_STOCK_ARM",
        "common_window_start": common_start,
        "common_window_end": common_end,
        "stock_regime_edges_refit": False,
    }
    write_json(CROSS_STATUS_PATH, status)
    return status


def main() -> int:
    args = parse_args()
    if SUMMARY_PATH.exists() and not args.force:
        raise RuntimeError("Y0 summary exists; pass --force to reproduce")
    config, yahoo_config = load_configs()
    bars, qqq, membership, price_audit = load_yahoo_panel_inputs(config, yahoo_config)
    panel = KERNEL.prepare_feature_panel(bars, membership, qqq, config)
    edges = KERNEL.freeze_regime_bins(panel)
    write_json(
        EDGE_PATH,
        {
            "study_id": STUDY_ID,
            "selection_uses_outcomes": False,
            "survivorship_bias": True,
            "eligible_current_universe_sessions": int(panel["eligible_regime"].sum()),
            "edges": edges,
        },
    )
    events = KERNEL.build_events(panel)
    events.to_parquet(EVENT_PATH, index=False)
    single = KERNEL.build_single_variable_stats(events)
    three = KERNEL.build_three_way_stats(events)
    robustness = KERNEL.build_robustness_stats(events)
    robustness["slice_type"] = robustness["slice_type"].replace(
        {"membership_tenure_segment": "available_history_tenure_segment"}
    )
    gap = KERNEL.build_gap_diagnostic(events)
    monotonicity = KERNEL.build_monotonicity_stats(single)
    surface = KERNEL.build_surface_diagnostics(events, three)
    unconditional = KERNEL.summarize_groups(
        events.loc[events["ma_period"].eq(7)], ["direction"]
    )
    outputs = (
        (SINGLE_PATH, single),
        (THREE_WAY_PATH, three),
        (ROBUSTNESS_PATH, robustness),
        (GAP_PATH, gap),
        (MONOTONICITY_PATH, monotonicity),
        (SURFACE_PATH, surface),
        (UNCONDITIONAL_PATH, unconditional),
    )
    for path, frame in outputs:
        frame.to_csv(path, index=False)
    cross_status = cross_market(single, three, events)
    output_paths = [
        EVENT_PATH,
        EDGE_PATH,
        *(path for path, _ in outputs),
        CROSS_STATUS_PATH,
        CROSS_SINGLE_LONG_PATH,
        CROSS_SINGLE_WIDE_PATH,
        CROSS_THREE_LONG_PATH,
        CROSS_THREE_WIDE_PATH,
        CROSS_SINGLE_COMMON_PATH,
        CROSS_THREE_COMMON_PATH,
    ]
    summary = {
        "study_id": STUDY_ID,
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "DIAGNOSTIC_COMPLETE_SURVIVORSHIP_BIASED_NOT_PROMOTED",
        "provider": "Yahoo Finance chart endpoint",
        "universe": "2026-08-21 current Nasdaq-100 terminal snapshot applied retrospectively",
        "survivorship_bias": True,
        "current_security_count": int(pd.read_csv(UNIVERSE_PATH)["ticker"].nunique()),
        "price_rows_including_qqq": int(price_audit["rows"]),
        "price_audit_status": price_audit["status"],
        "eligible_feature_sessions": int(panel["eligible_regime"].sum()),
        "event_rows_all_ma_periods": int(len(events)),
        "ma7_event_rows": int(events["ma_period"].eq(7).sum()),
        "ma7_long_events": int(
            (events["ma_period"].eq(7) & events["direction"].eq("long")).sum()
        ),
        "ma7_short_events": int(
            (events["ma_period"].eq(7) & events["direction"].eq("short")).sum()
        ),
        "cross_market_status": cross_status,
        "limitations": [
            "current constituents are applied retrospectively",
            "Yahoo is an unofficial no-SLA source",
            "ticker and corporate-action continuity is not point-in-time reference audited",
            "available-history tenure is not historical index-membership tenure",
        ],
        "artifact_sha256": KERNEL.artifact_hashes(output_paths),
    }
    write_json(SUMMARY_PATH, summary)
    print(json.dumps(KERNEL.json_safe(summary), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
