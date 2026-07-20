from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import _btc_15m_v40_common as common


SUMMARY_PATH = common.ARTIFACT_DIR / "btc_15m_v40_holdout_reveal_2026-07-17.json"
TRADES_PATH = common.ARTIFACT_DIR / "btc_15m_v40_holdout_trades_2026-07-17.csv"
EQUITY_PATH = common.ARTIFACT_DIR / "btc_15m_v40_holdout_equity_2026-07-17.csv"
WALK_FORWARD_PATH = common.ARTIFACT_DIR / "btc_15m_v40_dev_walk_forward_2026-07-17.csv"
CANDIDATE_METRICS_PATH = (
    common.ARTIFACT_DIR / "btc_15m_v40_candidate_metrics_2026-07-17.csv"
)
SEARCH_SUMMARY_PATH = common.ARTIFACT_DIR / "btc_15m_v40_search_summary_2026-07-17.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reveal the frozen BTC-15M-EMA-TB V40 holdout exactly once, "
            "without parameter reselection."
        )
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Validate kernel and universe identity without loading selection/data.",
    )
    return parser.parse_args()


def verify_file_sha(path: Path, expected: str, label: str) -> None:
    actual = common.sha256_bytes(path.read_bytes())
    if actual != expected:
        raise RuntimeError(f"{label} SHA mismatch: expected {expected}, got {actual}")


def verify_inputs() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, pd.Timestamp],
]:
    splits_payload = common.read_verified_payload(
        common.SPLITS_PATH,
        "frozen splits",
    )
    selection_payload = common.read_verified_payload(
        common.SELECTION_PATH,
        "frozen selection",
    )
    if splits_payload["kernel_sha256"] != common.KERNEL_SHA256:
        raise RuntimeError("frozen splits kernel SHA mismatch")
    if selection_payload["kernel_sha256"] != common.KERNEL_SHA256:
        raise RuntimeError("frozen selection kernel SHA mismatch")
    if (
        selection_payload["frozen_splits_payload_sha256"]
        != splits_payload["payload_sha256"]
    ):
        raise RuntimeError("selection was not frozen against these splits")
    if selection_payload["config_universe_sha256"] != common.config_universe_sha256():
        raise RuntimeError("selection config-universe SHA mismatch")
    audit_sha = common.sha256_bytes(common.AUDIT_PATH.read_bytes())
    if audit_sha != splits_payload["data_quality_sha256"]:
        raise RuntimeError("data-quality artifact changed after split freeze")
    if audit_sha != selection_payload["data_quality_sha256"]:
        raise RuntimeError("selection data-quality SHA mismatch")
    verify_file_sha(
        CANDIDATE_METRICS_PATH,
        selection_payload["candidate_metrics_sha256"],
        "candidate metrics",
    )
    verify_file_sha(
        SEARCH_SUMMARY_PATH,
        selection_payload["search_summary_sha256"],
        "search summary",
    )
    search_summary = common.read_verified_payload(
        SEARCH_SUMMARY_PATH,
        "search summary",
    )
    if search_summary["holdout_accessed"]:
        raise RuntimeError("search summary claims holdout access")
    if (
        search_summary["config_universe_sha256"]
        != selection_payload["config_universe_sha256"]
    ):
        raise RuntimeError("search-summary config-universe SHA mismatch")
    return selection_payload, splits_payload, common.parse_splits(splits_payload)


def check_existing_reveal(selection_payload: dict[str, Any]) -> bool:
    if not SUMMARY_PATH.exists():
        partial = [
            path
            for path in [TRADES_PATH, EQUITY_PATH, WALK_FORWARD_PATH]
            if path.exists()
        ]
        if partial:
            names = ", ".join(str(path) for path in partial)
            raise RuntimeError(
                "partial reveal artifacts exist without summary; refusing reveal: "
                f"{names}"
            )
        return False
    existing = common.read_verified_payload(SUMMARY_PATH, "holdout reveal")
    if (
        existing.get("frozen_selection_payload_sha256")
        != selection_payload["payload_sha256"]
    ):
        raise RuntimeError("a reveal exists for a different frozen selection")
    outputs = existing.get("output_sha256", {})
    for path, key in [
        (TRADES_PATH, "trades_csv"),
        (EQUITY_PATH, "equity_csv"),
        (WALK_FORWARD_PATH, "walk_forward_csv"),
    ]:
        if not path.exists():
            raise RuntimeError(f"existing reveal output is missing: {path}")
        verify_file_sha(path, outputs[key], key)
    print(
        json.dumps(existing, ensure_ascii=False, indent=2, sort_keys=True),
        flush=True,
    )
    print("holdout already revealed; existing artifacts left unchanged", flush=True)
    return True


def selected_trade_frame(
    run: Any,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    trades = run.trades.copy()
    if trades.empty:
        return trades
    entries = pd.to_datetime(trades["entry_ts"], utc=True)
    return trades.loc[(entries >= start) & (entries < end)].copy()


def recent_metrics(
    kernel: Any,
    *,
    selection: dict[str, Any],
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    features: pd.DataFrame,
    data_end: pd.Timestamp,
) -> list[dict[str, Any]]:
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "30d": pd.Timedelta(days=30),
        "90d": pd.Timedelta(days=90),
        "182d": pd.Timedelta(days=182),
        "365d": pd.Timedelta(days=365),
    }
    config, _flags, signals = common.build_signals_for_selection(
        kernel,
        features,
        selection,
    )
    rows: list[dict[str, Any]] = []
    for label, delta in windows.items():
        start = data_end - delta
        metrics, _run = common.evaluate_period(
            kernel,
            name=f"recent_{label}_flat_reset",
            frame=frame,
            funding=funding,
            signals=signals,
            config=config,
            start=start,
            end=data_end,
        )
        rows.append({"window": label, "flat_reset": True, **metrics})
        print(f"recent flat-reset {label}: {start} -> {data_end}", flush=True)
    return rows


def direction_contribution(trades: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label, direction in [("long", 1), ("short", -1)]:
        selected = trades.loc[trades["direction"].eq(direction)]
        returns = pd.to_numeric(selected["trade_return"], errors="coerce")
        result[label] = {
            "trades": int(len(selected)),
            "wins": int(returns.gt(0.0).sum()),
            "sum_trade_return_pct": float(returns.sum() * 100.0),
            "compounded_trade_return_pct": float(
                ((1.0 + returns).prod() - 1.0) * 100.0
            ),
            "profit_factor": common.profit_factor(selected),
        }
    return result


def side_ablation(
    kernel: Any,
    *,
    side: str,
    selection: dict[str, Any],
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    features: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    side_selection = json.loads(json.dumps(selection))
    side_selection["flags"]["allow_long"] = side == "long"
    side_selection["flags"]["allow_short"] = side == "short"
    config, _flags, signals = common.build_signals_for_selection(
        kernel,
        features,
        side_selection,
    )
    metrics, _run = common.evaluate_period(
        kernel,
        name=f"holdout_{side}_only",
        frame=frame,
        funding=funding,
        signals=signals,
        config=config,
        start=start,
        end=end,
    )
    return metrics


def walk_forward_rows(
    kernel: Any,
    *,
    selection: dict[str, Any],
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    features: pd.DataFrame,
    dev_start: pd.Timestamp,
    dev_end: pd.Timestamp,
) -> list[dict[str, Any]]:
    config, _flags, signals = common.build_signals_for_selection(
        kernel,
        features,
        selection,
    )
    rows: list[dict[str, Any]] = []
    is_start = dev_start
    fold = 1
    while True:
        is_end = is_start + pd.Timedelta(days=60)
        oos_start = is_end + pd.Timedelta(days=10)
        oos_end = oos_start + pd.Timedelta(days=30)
        if oos_end > dev_end:
            break
        is_metrics, _ = common.evaluate_period(
            kernel,
            name=f"walk_forward_{fold:02d}_is",
            frame=frame,
            funding=funding,
            signals=signals,
            config=config,
            start=is_start,
            end=is_end,
        )
        oos_metrics, _ = common.evaluate_period(
            kernel,
            name=f"walk_forward_{fold:02d}_oos",
            frame=frame,
            funding=funding,
            signals=signals,
            config=config,
            start=oos_start,
            end=oos_end,
        )
        row: dict[str, Any] = {
            "fold": fold,
            "is_start": is_start.isoformat(),
            "is_end_exclusive": is_end.isoformat(),
            "gap_days": 10,
            "oos_start": oos_start.isoformat(),
            "oos_end_exclusive": oos_end.isoformat(),
        }
        row.update({f"is_{key}": value for key, value in is_metrics.items()})
        row.update({f"oos_{key}": value for key, value in oos_metrics.items()})
        rows.append(row)
        print(f"walk-forward fold {fold}: OOS through {oos_end}", flush=True)
        is_start += pd.Timedelta(days=30)
        fold += 1
    return rows


def post_reveal_gate(
    *,
    selection_payload: dict[str, Any],
    holdout: dict[str, Any],
    stress: dict[str, Any],
    walk_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    positive_folds = sum(float(row["oos_return_pct"]) > 0.0 for row in walk_rows)
    positive_fold_ratio = 0.0 if not walk_rows else positive_folds / len(walk_rows)
    checks = {
        "holdout_costed_return_positive": {
            "passed": holdout["return_pct"] > 0.0,
            "value_pct": holdout["return_pct"],
            "threshold": "> 0",
        },
        "holdout_sample": {
            "passed": holdout["trades"] >= 30,
            "value_trades": holdout["trades"],
            "threshold": ">= 30",
            "failure_reason": (
                None if holdout["trades"] >= 30 else "sample_insufficient"
            ),
        },
        "holdout_max_drawdown": {
            "passed": abs(holdout["max_drawdown_pct"]) <= 25.0,
            "value_pct": holdout["max_drawdown_pct"],
            "threshold": "absolute <= 25%",
        },
        "holdout_double_cost_return_positive": {
            "passed": stress["return_pct"] > 0.0,
            "value_pct": stress["return_pct"],
            "threshold": "> 0",
        },
        "dev_wfo_positive_fold_ratio": {
            "passed": positive_fold_ratio > 0.50,
            "positive_folds": positive_folds,
            "folds": len(walk_rows),
            "value": positive_fold_ratio,
            "threshold": "> 0.50",
        },
    }
    performance_passed = all(check["passed"] for check in checks.values())
    role_eligible = bool(
        selection_payload["role"] == "candidate"
        and selection_payload["qualified_candidate"]
    )
    passed = performance_passed and role_eligible
    failures = [name for name, check in checks.items() if not check["passed"]]
    if not checks["holdout_sample"]["passed"]:
        failures.append("sample_insufficient")
    if not role_eligible:
        failures.append("pre_reveal_role_not_candidate")
    if not role_eligible:
        decision = "remain_diagnostic_near_miss_not_candidate"
    elif passed:
        decision = "candidate_passed_post_reveal_gate"
    else:
        decision = "candidate_failed_post_reveal_gate"
    return {
        "passed": passed,
        "performance_checks_passed": performance_passed,
        "pre_reveal_role_eligible": role_eligible,
        "near_miss_upgrade_forbidden": True,
        "checks": checks,
        "failures": failures,
        "decision": decision,
    }


def worst_trades(trades: pd.DataFrame, count: int = 10) -> list[dict[str, Any]]:
    if trades.empty:
        return []
    columns = [
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_price",
        "exit_price",
        "exit_reason",
        "hold_bars",
        "trade_return",
        "mfe_atr",
    ]
    records = (
        trades.nsmallest(count, "trade_return")[columns]
        .assign(
            entry_ts=lambda data: pd.to_datetime(
                data["entry_ts"],
                utc=True,
            ).astype(str),
            exit_ts=lambda data: pd.to_datetime(
                data["exit_ts"],
                utc=True,
            ).astype(str),
        )
        .to_dict(orient="records")
    )
    return common.finite_json_value(records)


def main() -> None:
    args = parse_args()
    kernel = common.load_kernel()
    if args.smoke:
        common.config_universe_sha256()
        synthetic_holdout = {
            "return_pct": 1.0,
            "trades": 30,
            "max_drawdown_pct": -10.0,
        }
        synthetic_stress = {"return_pct": 0.5}
        synthetic_walk = [
            {"oos_return_pct": 1.0},
            {"oos_return_pct": 1.0},
            {"oos_return_pct": -1.0},
        ]
        near_miss_gate = post_reveal_gate(
            selection_payload={
                "role": "diagnostic_near_miss",
                "qualified_candidate": False,
            },
            holdout=synthetic_holdout,
            stress=synthetic_stress,
            walk_rows=synthetic_walk,
        )
        assert not near_miss_gate["passed"]
        assert near_miss_gate["decision"] == "remain_diagnostic_near_miss_not_candidate"
        insufficient_gate = post_reveal_gate(
            selection_payload={
                "role": "candidate",
                "qualified_candidate": True,
            },
            holdout={**synthetic_holdout, "trades": 29},
            stress=synthetic_stress,
            walk_rows=synthetic_walk,
        )
        assert (
            insufficient_gate["checks"]["holdout_sample"]["failure_reason"]
            == "sample_insufficient"
        )
        print(
            "smoke PASS: kernel/config-universe SHA and near-miss no-upgrade gate",
            flush=True,
        )
        return

    selection_payload, splits_payload, splits = verify_inputs()
    if check_existing_reveal(selection_payload):
        return
    selection = selection_payload["selection"]
    data_start = pd.Timestamp(
        json.loads(common.AUDIT_PATH.read_bytes())["ohlcv_quality"]["first_ts"]
    )
    print(
        "all frozen SHAs verified; revealing holdout without reselection",
        flush=True,
    )
    frame, funding = common.load_market(data_start, splits["holdout_end"])
    features = common.build_feature_base(kernel, frame)
    config, _flags, signals = common.build_signals_for_selection(
        kernel,
        features,
        selection,
    )
    holdout, run = common.evaluate_period(
        kernel,
        name="btc_15m_v40_holdout",
        frame=frame,
        funding=funding,
        signals=signals,
        config=config,
        start=splits["holdout_start"],
        end=splits["holdout_end"],
    )
    stress_config = replace(
        config,
        fee_multiplier=2.0,
        slippage_multiplier=2.0,
    )
    stress, _stress_run = common.evaluate_period(
        kernel,
        name="btc_15m_v40_holdout_stress_2x",
        frame=frame,
        funding=funding,
        signals=signals,
        config=stress_config,
        start=splits["holdout_start"],
        end=splits["holdout_end"],
    )

    trades = selected_trade_frame(
        run,
        splits["holdout_start"],
        splits["holdout_end"],
    )
    trade_output = trades.copy()
    for column in ["entry_ts", "exit_ts"]:
        if column in trade_output:
            trade_output[column] = pd.to_datetime(
                trade_output[column],
                utc=True,
            ).astype(str)
    common.atomic_write_csv(TRADES_PATH, trade_output)

    equity = run.equity_curve.loc[
        (run.equity_curve.index >= splits["holdout_start"])
        & (run.equity_curve.index < splits["holdout_end"])
    ]
    returns = run.period_returns.reindex(equity.index)
    path = np.concatenate(([1.0], equity.to_numpy(dtype=float)))
    drawdown = path / np.maximum.accumulate(path) - 1.0
    equity_output = pd.DataFrame(
        {
            "ts": equity.index.astype(str),
            "equity": equity.to_numpy(dtype=float),
            "period_return": returns.to_numpy(dtype=float),
            "drawdown": drawdown[1:],
        }
    )
    common.atomic_write_csv(EQUITY_PATH, equity_output)

    walk_rows = walk_forward_rows(
        kernel,
        selection=selection,
        frame=frame.loc[frame.index < splits["holdout_start"]],
        funding=funding.loc[funding["ts"] < splits["holdout_start"]],
        features=features.loc[features.index < splits["holdout_start"]],
        dev_start=splits["train_start"],
        dev_end=splits["holdout_start"],
    )
    common.atomic_write_csv(WALK_FORWARD_PATH, pd.DataFrame(walk_rows))
    reveal_gate = post_reveal_gate(
        selection_payload=selection_payload,
        holdout=holdout,
        stress=stress,
        walk_rows=walk_rows,
    )

    exit_counts = (
        {
            str(key): int(value)
            for key, value in trades["exit_reason"].value_counts().items()
        }
        if not trades.empty
        else {}
    )
    summary: dict[str, Any] = {
        "schema_version": 1,
        "revealed_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "BTC-15M-EMA-Trend-Breakout",
        "research_identity": "BTC-15M-EMA-TB-V40-transfer-search",
        "reveal_number": 1,
        "parameters_reselected": False,
        "frozen_selection_payload_sha256": selection_payload["payload_sha256"],
        "frozen_splits_payload_sha256": splits_payload["payload_sha256"],
        "kernel_sha256": common.KERNEL_SHA256,
        "data_quality_sha256": splits_payload["data_quality_sha256"],
        "config_universe_sha256": common.config_universe_sha256(),
        "selection_role": selection_payload["role"],
        "qualified_candidate_before_reveal": selection_payload["qualified_candidate"],
        "status": reveal_gate["decision"],
        "selection": selection,
        "holdout": holdout,
        "holdout_stress_2x_cost": stress,
        "post_reveal_gate": reveal_gate,
        "direction_contribution_from_realized_trades": direction_contribution(trades),
        "direction_independent_flat_reset_ablation": {
            "long_only": side_ablation(
                kernel,
                side="long",
                selection=selection,
                frame=frame,
                funding=funding,
                features=features,
                start=splits["holdout_start"],
                end=splits["holdout_end"],
            ),
            "short_only": side_ablation(
                kernel,
                side="short",
                selection=selection,
                frame=frame,
                funding=funding,
                features=features,
                start=splits["holdout_start"],
                end=splits["holdout_end"],
            ),
        },
        "benchmarks": {
            "cash": {
                "return_pct": 0.0,
                "max_drawdown_pct": 0.0,
            },
            "btc_buyhold": common.buyhold_metrics(
                frame,
                splits["holdout_start"],
                splits["holdout_end"],
            ),
        },
        "recent_slices": recent_metrics(
            kernel,
            selection=selection,
            frame=frame,
            funding=funding,
            features=features,
            data_end=splits["holdout_end"],
        ),
        "walk_forward": {
            "contract": "rolling IS 60d, gap 10d, OOS 30d, step 30d",
            "scope": "development only; fixed frozen parameters; no reselection",
            "folds": len(walk_rows),
            "oos_positive_folds": sum(
                float(row["oos_return_pct"]) > 0.0 for row in walk_rows
            ),
            "oos_worst_return_pct": min(
                float(row["oos_return_pct"]) for row in walk_rows
            ),
            "oos_worst_max_drawdown_pct": min(
                float(row["oos_max_drawdown_pct"]) for row in walk_rows
            ),
        },
        "path_audit": {
            "closed_trades": int(len(trades)),
            "exit_counts": exit_counts,
            "worst_trade_return_pct": (
                None if trades.empty else float(trades["trade_return"].min() * 100.0)
            ),
            "best_trade_return_pct": (
                None if trades.empty else float(trades["trade_return"].max() * 100.0)
            ),
            "median_hold_bars": (
                None if trades.empty else float(trades["hold_bars"].median())
            ),
            "worst_trades": worst_trades(trades),
            "open_position_at_end": run.open_position,
        },
        "output_paths": {
            "trades_csv": str(TRADES_PATH.relative_to(common.ROOT)),
            "equity_csv": str(EQUITY_PATH.relative_to(common.ROOT)),
            "walk_forward_csv": str(WALK_FORWARD_PATH.relative_to(common.ROOT)),
        },
        "output_sha256": {
            "trades_csv": common.sha256_bytes(TRADES_PATH.read_bytes()),
            "equity_csv": common.sha256_bytes(EQUITY_PATH.read_bytes()),
            "walk_forward_csv": common.sha256_bytes(WALK_FORWARD_PATH.read_bytes()),
        },
    }
    summary = common.finite_json_value(summary)
    summary["payload_sha256"] = common.payload_sha256(summary)
    common.atomic_write_json(SUMMARY_PATH, summary)
    print(f"wrote one-time reveal summary: {SUMMARY_PATH}", flush=True)
    print(f"wrote trades: {TRADES_PATH}", flush=True)
    print(f"wrote equity: {EQUITY_PATH}", flush=True)
    print(f"wrote walk-forward: {WALK_FORWARD_PATH}", flush=True)


if __name__ == "__main__":
    main()
