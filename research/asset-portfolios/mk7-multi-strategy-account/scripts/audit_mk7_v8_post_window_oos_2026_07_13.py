"""Audit frozen mk7-v8 parameters after the documented backtest end.

The audit reruns the complete history for warmup/state continuity, verifies that
the pre-2026-07-02 selected identity is unchanged, then reports only the
post-window slice. It does not search or modify parameters.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY = ROOT / "research/asset-portfolios/mk7-multi-strategy-account"
BASE_SCRIPT = FAMILY / "scripts/research_mk7_v8_backtest.py"
ARTIFACTS = FAMILY / "artifacts"

BACKTEST_END = pd.Timestamp("2026-07-02T03:00:00Z")
FORWARD_END = pd.Timestamp("2026-07-13T00:00:00Z")
SPEC_FREEZE_DAY = pd.Timestamp("2026-07-12T00:00:00Z")

EXPECTED_BASELINE_RAW = {
    "TRX": 44,
    "SOL": 82,
    "HYPE": 74,
    "ETH": 89,
    "BTC": 54,
    "BNB": 62,
    "K2FQ": 69,
    "MII": 374,
}
EXPECTED_BASELINE_SELECTED = 747
EXPECTED_BASELINE_HASH = (
    "eb6c1ab659c619a3275f71cc777097203e2610bf6e20ce56508ec08d584c290f"
)


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location("mk7_oos_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.FULL_END = FORWARD_END
    module.ARTIFACT_1H = {
        asset: (
            ROOT
            / "data/cache/mk7_v8_binance/klines"
            / f"{asset.lower()}usdt_1h_extended_to_2026-07-13.parquet"
        )
        for asset in ("TRX", "SOL", "HYPE", "ETH", "BTC", "BNB")
    }
    return module


def selected_frame(selected: list[tuple[Any, float]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for candidate, exposure in selected:
        rows.append(
            {
                "family": candidate.family,
                "asset": candidate.asset,
                "leg": candidate.leg,
                "component": candidate.component,
                "side": candidate.side,
                "entry_ts": candidate.entry_ts.isoformat(),
                "exit_ts": candidate.exit_ts.isoformat(),
                "exposure": exposure,
                "exposure_native": candidate.exposure_native,
                "stop_pct": candidate.stop_pct,
                "net_ret_1x": candidate.net_ret_1x,
                "equity_ret": 0.5 * exposure * candidate.net_ret_1x,
            }
        )
    return pd.DataFrame(rows)


def identity_hash(frame: pd.DataFrame) -> str:
    payload = frame[
        ["asset", "leg", "side", "entry_ts", "exit_ts", "exposure", "equity_ret"]
    ].to_csv(index=False).encode()
    return hashlib.sha256(payload).hexdigest()


def component_counts(
    selected: list[tuple[Any, float]], start: pd.Timestamp, end: pd.Timestamp
) -> dict[str, int]:
    values = Counter(
        candidate.component
        for candidate, _exposure in selected
        if start <= candidate.entry_ts < end
    )
    return {name: int(values.get(name, 0)) for name in ("six", "k2fq", "mii")}


def asset_counts(
    selected: list[tuple[Any, float]], start: pd.Timestamp, end: pd.Timestamp
) -> dict[str, int]:
    values = Counter(
        candidate.asset
        for candidate, _exposure in selected
        if start <= candidate.entry_ts < end
    )
    return {name: int(value) for name, value in sorted(values.items())}


def main() -> None:
    module = load_base()
    six, _extended_six_counts, frames = module.six_coin_candidates()
    funding = pd.read_parquet(
        ROOT
        / "data/normalized/funding/exchange=binance/market_type=perp"
        / "symbol=hype_usdt_usdt/funding.parquet"
    )
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    k2fq = module.k2fq_candidates(funding)
    mii = module.mii_candidates()
    all_candidates = six + k2fq + mii
    selected = module.select_dual_slot(all_candidates)
    curve = module.build_full_equity_curve(selected, frames)

    baseline_candidates = [
        candidate for candidate in all_candidates if candidate.entry_ts < BACKTEST_END
    ]
    baseline_selected = [
        item for item in selected if item[0].entry_ts < BACKTEST_END
    ]
    baseline_raw = dict(Counter(candidate.family for candidate in baseline_candidates))
    baseline_raw["K2FQ"] = baseline_raw.pop("K2FQ", 0)
    baseline_raw["MII"] = baseline_raw.pop("MII", 0)
    baseline_frame = selected_frame(baseline_selected)
    baseline_hash = identity_hash(baseline_frame)
    frozen_reference = pd.read_csv(
        ARTIFACTS / "mk7_v8_selected_trades_2026-07-13.csv"
    )
    keys = ["asset", "leg", "side", "entry_ts"]
    compare_columns = [
        "asset",
        "leg",
        "side",
        "entry_ts",
        "exit_ts",
        "exposure",
        "equity_ret",
    ]
    comparison = frozen_reference[compare_columns].merge(
        baseline_frame[compare_columns],
        on=keys,
        how="outer",
        suffixes=("_frozen", "_extended"),
        indicator=True,
    )
    exact_identity_match = bool(
        comparison["_merge"].eq("both").all()
        and comparison["exit_ts_frozen"].eq(comparison["exit_ts_extended"]).all()
    )
    exposure_max_abs_diff = float(
        (
            comparison["exposure_frozen"] - comparison["exposure_extended"]
        ).abs().max()
    )
    equity_ret_max_abs_diff = float(
        (
            comparison["equity_ret_frozen"] - comparison["equity_ret_extended"]
        ).abs().max()
    )
    frozen_path_match = bool(
        exact_identity_match
        and exposure_max_abs_diff <= 1e-12
        and equity_ret_max_abs_diff <= 1e-12
    )
    baseline_check = {
        "raw_counts": baseline_raw,
        "expected_raw_counts": EXPECTED_BASELINE_RAW,
        "raw_counts_match": baseline_raw == EXPECTED_BASELINE_RAW,
        "selected_trades": len(baseline_selected),
        "expected_selected_trades": EXPECTED_BASELINE_SELECTED,
        "selected_count_match": len(baseline_selected) == EXPECTED_BASELINE_SELECTED,
        "selected_identity_hash": baseline_hash,
        "expected_selected_identity_hash": EXPECTED_BASELINE_HASH,
        "selected_identity_match": baseline_hash == EXPECTED_BASELINE_HASH,
        "frozen_trade_path_match_at_1e_12": frozen_path_match,
        "exposure_max_abs_diff": exposure_max_abs_diff,
        "equity_ret_max_abs_diff": equity_ret_max_abs_diff,
        "hash_note": (
            "The in-memory CSV hash can drift from sub-1e-12 floating-point "
            "differences after funding history is extended; the retained frozen "
            "CSV path is compared row-by-row."
        ),
    }
    if not all(
        [
            baseline_check["raw_counts_match"],
            baseline_check["selected_count_match"],
            baseline_check["frozen_trade_path_match_at_1e_12"],
        ]
    ):
        raise RuntimeError(f"frozen baseline drifted before OOS audit: {baseline_check}")

    forward_metrics = module.equity_metrics(
        selected, BACKTEST_END, FORWARD_END, full_curve=curve
    )
    forward_metrics["total_return"] = forward_metrics["multiple"] - 1.0
    post_freeze_metrics = module.equity_metrics(
        selected, SPEC_FREEZE_DAY, FORWARD_END, full_curve=curve
    )
    post_freeze_metrics["total_return"] = post_freeze_metrics["multiple"] - 1.0

    forward_selected = [
        item for item in selected if BACKTEST_END <= item[0].entry_ts < FORWARD_END
    ]
    forward_only_curve = module.build_full_equity_curve(forward_selected, frames)
    forward_reset_metrics = module.equity_metrics(
        forward_selected, BACKTEST_END, FORWARD_END, full_curve=forward_only_curve
    )
    forward_reset_metrics["total_return"] = (
        forward_reset_metrics["multiple"] - 1.0
    )
    forward_frame = selected_frame(forward_selected)
    forward_path = ARTIFACTS / "mk7_v8_post_window_selected_trades_2026-07-13.csv"
    forward_frame.to_csv(forward_path, index=False)

    raw_forward_counts = Counter(
        candidate.component
        for candidate in all_candidates
        if BACKTEST_END <= candidate.entry_ts < FORWARD_END
    )
    crossing = [
        {
            "asset": candidate.asset,
            "component": candidate.component,
            "entry_ts": candidate.entry_ts,
            "exit_ts": candidate.exit_ts,
            "exposure": exposure,
        }
        for candidate, exposure in selected
        if candidate.entry_ts < BACKTEST_END < candidate.exit_ts
    ]
    data_ranges = {
        asset: {
            "rows": len(frame),
            "first_ts": frame["ts"].iloc[0],
            "last_ts": frame["ts"].iloc[-1],
        }
        for asset, frame in frames.items()
    }

    result = {
        "status": "post_backtest_window_forward_audit_not_pristine_oos",
        "frozen_parameters": "mk7-v8",
        "backtest_end": BACKTEST_END,
        "forward_end": FORWARD_END,
        "duration_days": (FORWARD_END - BACKTEST_END).total_seconds() / 86400.0,
        "selection_or_tuning_on_forward_window": False,
        "pristine_oos_warning": (
            "The external mk7-v8 document was frozen on 2026-07-12, so the "
            "2026-07-02..2026-07-12 portion is post-backtest-window but cannot "
            "be proven unseen by the external author."
        ),
        "baseline_replay_check": baseline_check,
        "forward": {
            "metrics": forward_metrics,
            "new_entry_only_reset_nav_metrics": forward_reset_metrics,
            "raw_candidate_counts": {
                name: int(raw_forward_counts.get(name, 0))
                for name in ("six", "k2fq", "mii")
            },
            "selected_component_counts": component_counts(
                selected, BACKTEST_END, FORWARD_END
            ),
            "selected_asset_counts": asset_counts(
                selected, BACKTEST_END, FORWARD_END
            ),
            "selected_trade_sha256_local": identity_hash(forward_frame),
            "cross_boundary_positions": crossing,
        },
        "post_spec_freeze_day": {
            "start": SPEC_FREEZE_DAY,
            "metrics": post_freeze_metrics,
            "selected_component_counts": component_counts(
                selected, SPEC_FREEZE_DAY, FORWARD_END
            ),
        },
        "data_ranges": data_ranges,
        "artifacts": {
            "forward_selected_trades": str(forward_path.relative_to(ROOT)),
        },
    }
    output = ARTIFACTS / "mk7_v8_post_window_oos_2026-07-13.json"
    output.write_text(
        json.dumps(module.json_safe(result), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(module.json_safe(result), indent=2, ensure_ascii=False))
    print(f"wrote {output}")
    print(f"wrote {forward_path}")


if __name__ == "__main__":
    main()
