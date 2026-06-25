from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_ema_cross_strategy import build_features
from research_hype_ema_oscillator_top_exit_v10 import add_oscillator_features
from research_hype_ema_regime_hold_v5 import load_hype_data_lake
from research_hype_ema_volume_exhaustion_v7 import add_volume_features
from research_hype_state_machine_v12 import V12Spec, add_structure_features, run_v12
from research_hype_state_machine_v12_hard_exit import spec as focused_spec
from research_hype_trade_path_diagnostics_v11 import diagnose_trade, summarize, trade_frame_from_result


REPORT_PATH = Path("research/hype/ema-crossover/artifacts/hype_state_machine_v12_age128_ablation.json")
RANKING_PATH = Path("research/hype/ema-crossover/artifacts/hype_state_machine_v12_age128_ablation_ranking.csv")
SENSITIVITY_PATH = Path("research/hype/ema-crossover/artifacts/hype_state_machine_v12_age128_ablation_sensitivity.csv")
DIAG_SUMMARY_PATH = Path("research/hype/ema-crossover/artifacts/hype_state_machine_v12_age128_ablation_diagnostics_summary.csv")
DIAG_DETAIL_PATH = Path("research/hype/ema-crossover/artifacts/hype_state_machine_v12_age128_ablation_diagnostics_detail.csv")


def baseline_spec() -> V12Spec:
    return focused_spec(
        "V12_4_age128_baseline",
        hard_exit_mode="swing96",
        volume_warning_mode="no_mfi_div",
        warning_exit_min_capture=0.35,
        entry_max_regime_age=128,
    )


def candidate_specs(base: V12Spec) -> list[tuple[str, str, V12Spec]]:
    candidates: list[tuple[str, str, V12Spec]] = [("baseline", "baseline", base)]

    def add(parameter: str, value: object, spec: V12Spec) -> None:
        if spec == base:
            return
        candidates.append((parameter, str(value), replace(spec, name=f"V12_4_age128__{parameter}={value}")))

    for value in ("osc", "either"):
        add("warning_source", value, replace(base, warning_source=value))
    for value in ("ema55", "ema96", "donchian", "atr_trail", "ema21_or_donchian", "ema55_or_donchian", "ema55_and_donchian"):
        add("confirm_mode", value, replace(base, confirm_mode=value))
    for value in ("breakout48", "breakout96"):
        add("reentry_mode", value, replace(base, reentry_mode=value))
    for value in (2.0, 3.0, 5.0, 6.0):
        add("min_mfe_atr", value, replace(base, min_mfe_atr=value))
    for value in (48, 96):
        add("confirm_window", value, replace(base, confirm_window=value))
    for value in (7.5, 10.0):
        add("trail_atr", value, replace(base, trail_atr=value))
    for value in (2, 4):
        add("osc_min_score", value, replace(base, osc_min_score=value))
    for value in (18.0, 22.0):
        add("fallback_adx", value, replace(base, fallback_adx=value))
    for value in (2, 4):
        add("fallback_bars", value, replace(base, fallback_bars=value))
    for value in ("none", "ema96", "swing24", "swing48", "ema96_or_swing48", "ema96_or_swing96", "ema96_and_swing96"):
        add("hard_exit_mode", value, replace(base, hard_exit_mode=value))
    for value in (2, 3):
        add("hard_exit_bars", value, replace(base, hard_exit_bars=value))
    for value in ("all", "blowoff_only", "mfi_rvol_exit", "mfi_rvol_exit_wick35"):
        add("volume_warning_mode", value, replace(base, volume_warning_mode=value))
    for value in (0.0, 0.2, 0.5):
        add("warning_exit_min_capture", value, replace(base, warning_exit_min_capture=value))
    for value in (0, 64, 192, 256, 384):
        add("entry_max_regime_age", value, replace(base, entry_max_regime_age=value))
    for value in (1.2, 1.5):
        add("entry_min_rvol96", value, replace(base, entry_min_rvol96=value))
    for value in (0.08, 0.10):
        add("entry_max_dist_ema96", value, replace(base, entry_max_dist_ema96=value))
    for value in (0.10, 0.12):
        add("entry_max_move48", value, replace(base, entry_max_move48=value))
    for value in ("adx18", "adx22", "ema55", "ema55_adx22", "ema21_adx22"):
        if value == "adx18":
            spec = replace(base, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=18.0, segment_bars=3)
        elif value == "adx22":
            spec = replace(base, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=22.0, segment_bars=3)
        elif value == "ema55":
            spec = replace(base, segment_exit_mode="ema55", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.35)
        elif value == "ema55_adx22":
            spec = replace(base, segment_exit_mode="ema55_adx", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.35, segment_adx=22.0)
        else:
            spec = replace(base, segment_exit_mode="ema21_adx", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.35, segment_adx=22.0)
        add("segment_exit_mode", value, spec)
    for value in (2.0, 6.0):
        add("segment_min_mfe_atr", value, replace(base, segment_exit_mode="adx", segment_min_mfe_atr=value, segment_adx=18.0, segment_bars=3))
    for value in (0.2, 0.5):
        add("segment_exit_min_capture", value, replace(base, segment_exit_mode="ema55", segment_min_mfe_atr=4.0, segment_exit_min_capture=value))
    for value in (18.0, 22.0):
        add("segment_adx", value, replace(base, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=value, segment_bars=3))
    for value in (2, 3, 4):
        add("segment_bars", value, replace(base, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=18.0, segment_bars=value))
    for value in (7.0, 8.0, 10.0, 12.0):
        add("stop_atr", value, replace(base, stop_atr=value))
    for value in (1.5, 2.5, 3.0):
        add("exit_rvol", value, replace(base, exit_rvol=value))
    for value in (0.35, 0.45, 0.65):
        add("wick_min", value, replace(base, wick_min=value))

    return candidates


def compact_metric(parameter: str, value: str, result: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    return {
        "parameter": parameter,
        "value": value,
        "name": result["name"],
        "return": result["return"],
        "max_dd": result["max_dd"],
        "sharpe": result["sharpe"],
        "trades": result["trades"],
        "win_rate": result["win_rate"],
        "avg_trade_pct": result["avg_trade_pct"],
        "median_trade_pct": result["median_trade_pct"],
        "best_trade_pct": result["best_trade_pct"],
        "worst_trade_pct": result["worst_trade_pct"],
        "avg_hold_bars": result["avg_hold_bars"],
        "exit_reasons": result["exit_reasons"],
        "fitness": result["fitness"],
        "return_delta": result["return"] - base["return"],
        "max_dd_delta": result["max_dd"] - base["max_dd"],
        "sharpe_delta": result["sharpe"] - base["sharpe"],
        "trades_delta": result["trades"] - base["trades"],
    }


def summarize_sensitivity(ranking: pd.DataFrame, base: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for parameter, group in ranking[ranking.parameter != "baseline"].groupby("parameter", sort=False):
        rows.append(
            {
                "parameter": parameter,
                "candidates": int(len(group)),
                "best_value_by_return": str(group.sort_values("return", ascending=False).iloc[0]["value"]),
                "best_return": float(group["return"].max()),
                "best_return_delta": float(group["return"].max() - base["return"]),
                "best_value_by_dd": str(group.sort_values("max_dd", ascending=False).iloc[0]["value"]),
                "best_max_dd": float(group["max_dd"].max()),
                "best_dd_delta": float(group["max_dd"].max() - base["max_dd"]),
                "return_range": float(group["return"].max() - group["return"].min()),
                "dd_range": float(group["max_dd"].max() - group["max_dd"].min()),
                "sharpe_range": float(group["sharpe"].max() - group["sharpe"].min()),
                "worst_return": float(group["return"].min()),
            }
        )
    return pd.DataFrame(rows).sort_values(["return_range", "dd_range"], ascending=False)


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_structure_features(add_oscillator_features(add_volume_features(build_features(raw))))
    base = baseline_spec()
    candidates = candidate_specs(base)
    results = []
    for parameter, value, item in candidates:
        result = run_v12(frame, item, collect_trades=parameter == "baseline")
        results.append((parameter, value, item, result))

    base_result = next(result for parameter, _, _, result in results if parameter == "baseline")
    ranking = pd.DataFrame([compact_metric(parameter, value, result, base_result) for parameter, value, _, result in results])
    ranking = ranking.sort_values(["fitness", "return", "max_dd"], ascending=[False, False, False])
    sensitivity = summarize_sensitivity(ranking, base_result)

    ts_index = pd.DatetimeIndex(pd.to_datetime(frame.ts, utc=True))
    base_full = run_v12(frame, base, collect_trades=True)
    base_trades = trade_frame_from_result("V12_4_age128_baseline", base_full["trades_detail"])
    detail = pd.DataFrame([diagnose_trade(frame, ts_index, trade) for _, trade in base_trades.iterrows()])
    diag_summary, _ = summarize(detail)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_PATH, index=False)
    sensitivity.to_csv(SENSITIVITY_PATH, index=False)
    detail.to_csv(DIAG_DETAIL_PATH, index=False)
    diag_summary.to_csv(DIAG_SUMMARY_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "baseline_spec": asdict(base),
                "baseline_result": base_result,
                "ranking_top20": ranking.head(20).to_dict(orient="records"),
                "sensitivity": sensitivity.to_dict(orient="records"),
                "diagnostics_summary": diag_summary.to_dict(orient="records"),
                "notes": [
                    "Single-factor ablation around V12.4 age128.",
                    "Inactive modules such as segment exits are tested through sensible activation bundles.",
                    "Data: Binance HYPEUSDT perp 15m normalized data lake, ending 2026-06-01 03:00 UTC.",
                ],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={REPORT_PATH}")
    print(f"ranking={RANKING_PATH}")
    print(f"sensitivity={SENSITIVITY_PATH}")
    print("baseline", {key: base_result[key] for key in ("return", "max_dd", "sharpe", "trades", "win_rate")})
    print(ranking.head(12).to_string(index=False))
    print("\\nsensitivity")
    print(sensitivity.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
