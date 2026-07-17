from __future__ import annotations

import argparse
from pathlib import Path
import json

import numpy as np
import pandas as pd

from hype_ml_common import ARTIFACTS_DIR, load_hype_market_frame, write_json
from strategy_lab.data.factors.engine import compute_factor_bundle
from strategy_lab.data.factors.hype_15m import hype_15m_registry


TRAIN_END_EXCLUSIVE = pd.Timestamp("2026-01-01T00:00:00Z")
VALIDATION_END_EXCLUSIVE = pd.Timestamp("2026-04-17T00:00:00Z")
OOS_END_EXCLUSIVE = pd.Timestamp("2026-07-16T15:45:00Z")
FORWARD_HORIZON_BARS = 12
MIN_COVERAGE = 0.95
CORRELATION_PRUNE_THRESHOLD = 0.97


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit HYPE 15m factors without using the locked OOS target."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ARTIFACTS_DIR / "hype_15m_factor_dataset.parquet",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ARTIFACTS_DIR / "hype_15m_factor_dataset_manifest.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACTS_DIR / "factor_audit_round2",
    )
    return parser.parse_args()


def split_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "train": frame["ts"] < TRAIN_END_EXCLUSIVE,
        "validation": (frame["ts"] >= TRAIN_END_EXCLUSIVE)
        & (frame["ts"] < VALIDATION_END_EXCLUSIVE),
        "oos_locked": (frame["ts"] >= VALIDATION_END_EXCLUSIVE)
        & (frame["ts"] < OOS_END_EXCLUSIVE),
    }


def factor_statistics(
    frame: pd.DataFrame,
    factor_names: list[str],
) -> pd.DataFrame:
    train = frame.loc[frame["ts"] < TRAIN_END_EXCLUSIVE].copy()
    train["future_return_12"] = (
        train["close"].shift(-FORWARD_HORIZON_BARS)
        / train["open"].shift(-1)
        - 1.0
    )
    rows: list[dict[str, object]] = []
    for name in factor_names:
        values = pd.to_numeric(train[name], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        )
        valid = values.notna() & train["future_return_12"].notna()
        usable_values = values.loc[valid]
        target = train.loc[valid, "future_return_12"]
        ic = float(usable_values.corr(target, method="spearman")) if valid.sum() >= 50 else np.nan
        if usable_values.nunique() >= 5:
            buckets = pd.qcut(
                usable_values.rank(method="first"), 5, labels=False, duplicates="drop"
            )
            grouped = target.groupby(buckets).mean()
            quintile_spread = (
                float(grouped.iloc[-1] - grouped.iloc[0]) if len(grouped) >= 2 else np.nan
            )
        else:
            quintile_spread = np.nan
        rows.append(
            {
                "factor": name,
                "full_coverage": float(frame[name].notna().mean()),
                "train_coverage": float(values.notna().mean()),
                "train_finite_rows": int(valid.sum()),
                "train_unique_values": int(usable_values.nunique()),
                "train_std": float(usable_values.std(ddof=0)) if len(usable_values) else np.nan,
                "train_spearman_ic_12": ic,
                "train_abs_ic_12": abs(ic) if np.isfinite(ic) else np.nan,
                "train_quintile_spread_12": quintile_spread,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["train_abs_ic_12", "full_coverage"], ascending=False, na_position="last"
    )


def causal_prefix_audit(
    dataset: pd.DataFrame,
    factor_names: list[str],
) -> dict[str, object]:
    market, _ = load_hype_market_frame()
    registry = hype_15m_registry()
    checkpoints = [4096, 12000, 24000, 35000, len(market)]
    checkpoints = sorted({point for point in checkpoints if 1000 <= point <= len(market)})
    mismatches: list[dict[str, object]] = []
    for length in checkpoints:
        recomputed = compute_factor_bundle(market.iloc[:length].copy(), registry)
        expected = dataset.iloc[length - 1]
        actual = recomputed.iloc[-1]
        for name in factor_names:
            left = float(expected[name])
            right = float(actual[name])
            if not np.isclose(left, right, rtol=0.0, atol=1e-12, equal_nan=True):
                mismatches.append(
                    {
                        "checkpoint_rows": length,
                        "factor": name,
                        "full_value": left,
                        "prefix_value": right,
                    }
                )
    return {
        "checkpoints": checkpoints,
        "comparisons": len(checkpoints) * len(factor_names),
        "mismatch_count": len(mismatches),
        "mismatch_examples": mismatches[:20],
        "pass": not mismatches,
    }


def correlation_prune(
    train: pd.DataFrame,
    eligible: list[str],
    stats: pd.DataFrame,
) -> tuple[list[str], list[dict[str, object]], pd.DataFrame]:
    correlation = train[eligible].corr(method="spearman")
    priority = stats.loc[stats["factor"].isin(eligible)].copy()
    priority["mandatory"] = priority["factor"].eq("atr_pct_14")
    priority = priority.sort_values(
        ["mandatory", "train_abs_ic_12", "full_coverage"],
        ascending=False,
        na_position="last",
    )
    selected: list[str] = []
    removed: list[dict[str, object]] = []
    for name in priority["factor"]:
        conflicts = [
            kept
            for kept in selected
            if np.isfinite(correlation.loc[name, kept])
            and abs(float(correlation.loc[name, kept])) >= CORRELATION_PRUNE_THRESHOLD
        ]
        if conflicts:
            strongest = max(conflicts, key=lambda kept: abs(float(correlation.loc[name, kept])))
            removed.append(
                {
                    "factor": name,
                    "kept_factor": strongest,
                    "spearman_correlation": float(correlation.loc[name, strongest]),
                }
            )
        else:
            selected.append(name)
    return selected, removed, correlation


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(args.input).sort_values("ts").reset_index(drop=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    factor_names = [name for name in manifest["factor_names"] if name in frame.columns]
    if len(factor_names) != int(manifest["factor_count"]):
        raise RuntimeError("factor dataset columns do not match the manifest")
    if frame["ts"].max() >= OOS_END_EXCLUSIVE:
        raise RuntimeError("dataset contains rows beyond the frozen OOS end")
    if frame["ts"].max() != OOS_END_EXCLUSIVE - pd.Timedelta(minutes=15):
        raise RuntimeError("dataset end does not match the frozen OOS end")

    masks = split_masks(frame)
    split_lock = {
        "family": "HYPE-15M-Factor-ML",
        "round": 2,
        "policy": "train and validation may be used for research; OOS target is sealed until final candidate freeze",
        "train": {
            "start": frame.loc[masks["train"], "ts"].min().isoformat(),
            "end_exclusive": TRAIN_END_EXCLUSIVE.isoformat(),
            "rows": int(masks["train"].sum()),
        },
        "validation": {
            "start": TRAIN_END_EXCLUSIVE.isoformat(),
            "end_exclusive": VALIDATION_END_EXCLUSIVE.isoformat(),
            "rows": int(masks["validation"].sum()),
        },
        "oos_locked": {
            "start": VALIDATION_END_EXCLUSIVE.isoformat(),
            "end_exclusive": OOS_END_EXCLUSIVE.isoformat(),
            "rows": int(masks["oos_locked"].sum()),
            "target_used_for_selection": False,
        },
    }
    write_json(args.output_dir / "split_lock_round2.json", split_lock)

    stats = factor_statistics(frame, factor_names)
    stats.to_csv(args.output_dir / "single_factor_train_audit.csv", index=False)
    eligible = stats.loc[
        (stats["full_coverage"] >= MIN_COVERAGE)
        & (stats["train_unique_values"] >= 20)
        & stats["train_std"].gt(1e-12),
        "factor",
    ].tolist()
    train = frame.loc[masks["train"]].copy()
    selected, removed, correlation = correlation_prune(train, eligible, stats)
    correlation.to_parquet(args.output_dir / "train_spearman_correlation.parquet")
    pd.DataFrame(removed).to_csv(args.output_dir / "correlation_pruned.csv", index=False)

    causal = causal_prefix_audit(frame, factor_names)
    if not causal["pass"]:
        raise RuntimeError(f"factor causal-prefix audit failed: {causal}")

    metadata = manifest["factor_specs"]
    factor_catalog = []
    for name in factor_names:
        spec = metadata[name]
        factor_catalog.append(
            {
                "factor": name,
                "version": manifest["factor_versions"][name],
                **spec["metadata"],
                "parameters": spec["parameters"],
            }
        )
    pd.DataFrame(factor_catalog).to_json(
        args.output_dir / "factor_catalog.json",
        orient="records",
        indent=2,
        force_ascii=False,
    )

    payload = {
        "family": "HYPE-15M-Factor-ML",
        "round": 2,
        "candidate_factor_count": len(factor_names),
        "eligible_factor_count": len(eligible),
        "correlation_pruned_feature_count": len(selected),
        "eligible_features": eligible,
        "correlation_pruned_features": selected,
        "coverage_threshold": MIN_COVERAGE,
        "correlation_prune_threshold": CORRELATION_PRUNE_THRESHOLD,
        "selection_target_scope": "training only",
        "causal_prefix_audit": causal,
        "split_lock_path": str(args.output_dir / "split_lock_round2.json"),
        "single_factor_audit_path": str(args.output_dir / "single_factor_train_audit.csv"),
        "correlation_path": str(args.output_dir / "train_spearman_correlation.parquet"),
        "oos_target_revealed": False,
    }
    write_json(args.output_dir / "factor_audit_summary.json", payload)
    print(
        json.dumps(
            {
                "candidate_factors": len(factor_names),
                "eligible_factors": len(eligible),
                "correlation_pruned_features": len(selected),
                "causal_prefix_mismatches": causal["mismatch_count"],
                "split_rows": {
                    name: int(mask.sum()) for name, mask in masks.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
