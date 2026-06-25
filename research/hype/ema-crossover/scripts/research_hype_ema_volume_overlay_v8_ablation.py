from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_ema_cross_strategy import build_features
from research_hype_ema_regime_hold_v5 import load_hype_data_lake, run_variant_dynamic_3x
from research_hype_ema_volume_exhaustion_v7 import add_volume_features
from research_hype_ema_volume_overlay_v8 import V8Spec, run_v8, v6_variant


REPORT_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_ema_volume_overlay_v8_ablation.json")
DETAIL_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_ema_volume_overlay_v8_ablation_detail.csv")
SUMMARY_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_ema_volume_overlay_v8_ablation_summary.csv")


def baseline_spec() -> V8Spec:
    return V8Spec(
        name="V8_full_exit_xrv2_mfe4_fb1_cd0",
        action="full_exit",
        exit_rvol=2.0,
        min_mfe_atr=4.0,
        fail_bars=1,
        cooldown_bars=0,
        reduce_fraction=0.5,
        wick_min=0.35,
        stop_atr=9.0,
        adx_exit=22.0,
        adx_exit_bars=3,
    )


def with_name(spec: V8Spec) -> V8Spec:
    return replace(
        spec,
        name=(
            f"Ablation_{spec.action}_xrv{spec.exit_rvol:g}_mfe{spec.min_mfe_atr:g}"
            f"_fb{spec.fail_bars}_cd{spec.cooldown_bars}_rf{spec.reduce_fraction:g}"
            f"_wick{spec.wick_min:g}_stop{spec.stop_atr:g}_adx{spec.adx_exit:g}"
            f"_adxb{spec.adx_exit_bars}"
        ),
    )


def candidate_specs() -> list[tuple[str, Any, V8Spec]]:
    base = baseline_spec()
    candidates: list[tuple[str, Any, V8Spec]] = [("baseline", "baseline", base)]
    grids: dict[str, list[Any]] = {
        "action": ["full_exit", "half_reduce"],
        "exit_rvol": [1.2, 1.5, 2.0, 2.5, 3.0],
        "min_mfe_atr": [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0],
        "fail_bars": [1, 2, 3, 4],
        "cooldown_bars": [0, 16, 32, 64, 96],
        "wick_min": [0.25, 0.35, 0.45, 0.55, 0.65],
        "stop_atr": [6.0, 7.5, 9.0, 10.5, 12.0],
        "adx_exit": [18.0, 20.0, 22.0, 24.0, 26.0, 28.0],
        "adx_exit_bars": [1, 2, 3, 4, 5],
    }
    for parameter, values in grids.items():
        for value in values:
            candidates.append((parameter, value, with_name(replace(base, **{parameter: value}))))

    # reduce_fraction only affects half_reduce; evaluate it in the half-reduce branch.
    half_reduce_base = replace(base, action="half_reduce")
    for value in [0.25, 0.33, 0.5, 0.67, 0.75, 1.0]:
        candidates.append(
            (
                "reduce_fraction",
                value,
                with_name(replace(half_reduce_base, reduce_fraction=value)),
            )
        )
    return candidates


def compact_metric(row: dict[str, object]) -> dict[str, object]:
    keys = [
        "name",
        "action",
        "exit_rvol",
        "min_mfe_atr",
        "fail_bars",
        "cooldown_bars",
        "reduce_fraction",
        "wick_min",
        "stop_atr",
        "adx_exit",
        "adx_exit_bars",
        "return",
        "max_dd",
        "sharpe",
        "trades",
        "win_rate",
        "avg_trade_pct",
        "median_trade_pct",
        "best_trade_pct",
        "worst_trade_pct",
        "avg_hold_bars",
        "reduce_events",
        "exit_reasons",
        "fitness",
    ]
    return {key: row.get(key) for key in keys if key in row}


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for parameter, group in detail.groupby("parameter", sort=False):
        if parameter == "baseline":
            continue
        best = group.sort_values(["fitness", "return", "sharpe"], ascending=False).iloc[0]
        worst = group.sort_values(["fitness", "return", "sharpe"], ascending=True).iloc[0]
        rows.append(
            {
                "parameter": parameter,
                "tested_values": ", ".join(map(str, group["value"].tolist())),
                "best_value": best["value"],
                "best_return": best["return"],
                "best_max_dd": best["max_dd"],
                "best_sharpe": best["sharpe"],
                "best_fitness": best["fitness"],
                "worst_value": worst["value"],
                "worst_return": worst["return"],
                "worst_max_dd": worst["max_dd"],
                "worst_sharpe": worst["sharpe"],
                "worst_fitness": worst["fitness"],
                "return_range": float(group["return"].max() - group["return"].min()),
                "max_dd_range": float(group["max_dd"].max() - group["max_dd"].min()),
                "sharpe_range": float(group["sharpe"].max() - group["sharpe"].min()),
                "fitness_range": float(group["fitness"].max() - group["fitness"].min()),
            }
        )
    return pd.DataFrame(rows).sort_values("fitness_range", ascending=False)


def add_deltas(detail: pd.DataFrame) -> pd.DataFrame:
    baseline = detail[detail.parameter == "baseline"].iloc[0]
    detail = detail.copy()
    detail["delta_return"] = detail["return"] - baseline["return"]
    detail["delta_max_dd"] = detail["max_dd"] - baseline["max_dd"]
    detail["delta_sharpe"] = detail["sharpe"] - baseline["sharpe"]
    detail["delta_fitness"] = detail["fitness"] - baseline["fitness"]
    return detail


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_volume_features(build_features(raw))
    base = baseline_spec()
    rows = []
    for parameter, value, spec in candidate_specs():
        result = run_v8(frame, spec)
        rows.append(
            {
                "parameter": parameter,
                "value": value,
                **compact_metric(result),
            }
        )
    v6 = run_variant_dynamic_3x(frame, v6_variant())
    rows.append(
        {
            "parameter": "overlay",
            "value": "no_overlay_v6",
            **compact_metric(
                {
                    **asdict(base),
                    "name": "V6_no_volume_overlay",
                    "return": v6["return"],
                    "max_dd": v6["max_dd"],
                    "sharpe": v6["sharpe"],
                    "trades": v6["trades"],
                    "win_rate": v6["win_rate"],
                    "avg_trade_pct": v6["avg_trade_pct"],
                    "median_trade_pct": v6["median_trade_pct"],
                    "best_trade_pct": v6["best_trade_pct"],
                    "worst_trade_pct": v6["worst_trade_pct"],
                    "avg_hold_bars": np.nan,
                    "reduce_events": 0,
                    "exit_reasons": v6["exit_reasons"],
                    "fitness": float(v6["return"] + v6["max_dd"] * 1.5),
                }
            ),
        }
    )
    detail = add_deltas(pd.DataFrame(rows))
    summary = summarize(detail)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)
    report = {
        "data": {
            "start": str(pd.Timestamp(frame.ts.iloc[0])),
            "end": str(pd.Timestamp(frame.ts.iloc[-1])),
            "bars": int(len(frame)),
        },
        "baseline": detail[detail.parameter == "baseline"].iloc[0].to_dict(),
        "v6_no_overlay": detail[detail.value == "no_overlay_v6"].iloc[0].to_dict(),
        "parameter_sensitivity": summary.to_dict(orient="records"),
        "top_overall": detail.sort_values(
            ["fitness", "return", "sharpe"],
            ascending=False,
        )
        .head(15)
        .to_dict(orient="records"),
        "notes": [
            "Single-factor ablation: keep the current V8 best fixed and vary one parameter at a time.",
            "reduce_fraction is evaluated in the half_reduce branch because it has no effect under full_exit.",
            "no_overlay_v6 removes the V8 volume exhaustion overlay and uses V6 dynamic 3x as baseline comparison.",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"wrote={REPORT_PATH}")
    print(f"detail={DETAIL_PATH}")
    print(f"summary={SUMMARY_PATH}")
    print("baseline_return={:.4f} baseline_dd={:.4f}".format(report["baseline"]["return"], report["baseline"]["max_dd"]))
    print("top_sensitivity")
    print(summary.head(8).to_string(index=False))


if __name__ == "__main__":
    main()
