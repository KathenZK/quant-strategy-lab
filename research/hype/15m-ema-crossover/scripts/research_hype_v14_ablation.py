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
from research_hype_state_machine_v12 import V12Spec, add_structure_features
from research_hype_trade_path_diagnostics_v11 import diagnose_trade, summarize, trade_frame_from_result
from research_hype_v13_late_reentry import LateReentrySpec, run_late_reentry
from research_hype_v14_main_backfill import v14_spec


REPORT_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v14_ablation.json")
RANKING_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v14_ablation_ranking.csv")
SENSITIVITY_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v14_ablation_sensitivity.csv")
WINDOWS_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v14_ablation_top_windows.csv")
DIAG_BASE_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v14_ablation_base_diagnostics_summary.csv")
DIAG_BEST_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v14_ablation_best_diagnostics_summary.csv")
DIAG_DETAIL_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v14_ablation_best_diagnostics_detail.csv")

WINDOWS = {
    "1W": pd.Timedelta(days=7),
    "1M": pd.Timedelta(days=30),
    "3M": pd.Timedelta(days=90),
    "6M": pd.Timedelta(days=180),
    "1Y": pd.Timedelta(days=365),
}


def load_frame() -> pd.DataFrame:
    raw = load_hype_data_lake()
    return add_structure_features(add_oscillator_features(add_volume_features(build_features(raw))))


def base_spec() -> LateReentrySpec:
    return v14_spec()


def candidate_specs(base: LateReentrySpec) -> list[tuple[str, str, LateReentrySpec]]:
    candidates: list[tuple[str, str, LateReentrySpec]] = [("baseline", "baseline", base)]

    def add(parameter: str, value: object, spec: LateReentrySpec) -> None:
        if spec == base:
            return
        safe = str(value).replace(" ", "").replace("/", "_")
        candidates.append((parameter, str(value), replace(spec, name=f"V14__{parameter}={safe}")))

    def add_v12(parameter: str, value: object, v12: V12Spec) -> None:
        add(parameter, value, replace(base, v12=replace(v12, name=f"V14_base__{parameter}={value}")))

    # V14 outer late re-entry layer.
    for value in (0, 128, 192, 384, 512):
        add("late_max_age", value, replace(base, late_max_age=value))
    for value in (0.04, 0.05, 0.08, 0.10, 0.12):
        add("late_dist_ema96", value, replace(base, late_dist_ema96=value))
    for value in (0, 8, 24, 32, 48):
        add("cooldown_bars", value, replace(base, cooldown_bars=value))
    for value in (-0.03, -0.01, 0.01, 0.03):
        add("min_prev_pnl", value, replace(base, min_prev_pnl=value))
    for value in (2.0, 3.0, 5.0, 6.0, 8.0, 10.0):
        add("min_prev_mfe_atr", value, replace(base, min_prev_mfe_atr=value))
    add("require_pullback", True, replace(base, require_pullback=True, pullback_buffer=0.0))
    for value in (0.005, 0.01, 0.02):
        add("pullback_buffer", value, replace(base, require_pullback=True, pullback_buffer=value))

    v12 = base.v12
    # Active V12 state-machine parameters.
    for value in ("osc", "either"):
        add_v12("warning_source", value, replace(v12, warning_source=value))
    for value in ("ema55", "ema96", "donchian", "atr_trail", "ema21_or_donchian", "ema55_or_donchian", "ema55_and_donchian"):
        add_v12("confirm_mode", value, replace(v12, confirm_mode=value))
    for value in ("breakout48", "breakout96"):
        add_v12("reentry_mode", value, replace(v12, reentry_mode=value))
    for value in (2.0, 3.0, 5.0, 6.0, 8.0):
        add_v12("min_mfe_atr", value, replace(v12, min_mfe_atr=value))
    for value in (48, 96):
        add_v12("confirm_window", value, replace(v12, confirm_window=value))
    for value in (18.0, 22.0):
        add_v12("fallback_adx", value, replace(v12, fallback_adx=value))
    for value in (2, 4):
        add_v12("fallback_bars", value, replace(v12, fallback_adx=18.0, fallback_bars=value))
    for value in ("none", "ema96", "swing24", "swing48", "ema96_or_swing48", "ema96_or_swing96", "ema96_and_swing96"):
        add_v12("hard_exit_mode", value, replace(v12, hard_exit_mode=value))
    for value in (2, 3):
        add_v12("hard_exit_bars", value, replace(v12, hard_exit_bars=value))
    for value in ("all", "blowoff_only", "mfi_rvol_exit", "mfi_rvol_exit_wick35"):
        add_v12("volume_warning_mode", value, replace(v12, volume_warning_mode=value))
    for value in (0.0, 0.20, 0.50, 0.65):
        add_v12("warning_exit_min_capture", value, replace(v12, warning_exit_min_capture=value))
    for value in (0, 64, 192, 256, 384):
        add_v12("entry_max_regime_age", value, replace(v12, entry_max_regime_age=value))
    for value in (1.1, 1.2, 1.5):
        add_v12("entry_min_rvol96", value, replace(v12, entry_min_rvol96=value))
    for value in (0.04, 0.06, 0.10, 0.12):
        add_v12("entry_max_dist_ema96", value, replace(v12, entry_max_dist_ema96=value))
    for value in (0.08, 0.10, 0.12, 0.16):
        add_v12("entry_max_move48", value, replace(v12, entry_max_move48=value))
    for value in (7.0, 8.0, 10.0, 12.0):
        add_v12("stop_atr", value, replace(v12, stop_atr=value))
    for value in (1.5, 2.5, 3.0):
        add_v12("exit_rvol", value, replace(v12, exit_rvol=value))
    for value in (0.35, 0.45, 0.65):
        add_v12("wick_min", value, replace(v12, wick_min=value))

    # Activation bundles for parameters that are inactive in the V14 baseline.
    for value in (7.5, 10.0, 12.5):
        add_v12("trail_atr", value, replace(v12, confirm_mode="atr_trail", trail_atr=value))
    for value in (2, 4):
        add_v12("osc_min_score", value, replace(v12, warning_source="osc", osc_min_score=value))
    for value in ("adx18", "adx22", "ema21", "ema55", "ema55_adx22", "ema21_adx22"):
        if value == "adx18":
            item = replace(v12, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=18.0, segment_bars=3)
        elif value == "adx22":
            item = replace(v12, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=22.0, segment_bars=3)
        elif value == "ema21":
            item = replace(v12, segment_exit_mode="ema21", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.35)
        elif value == "ema55":
            item = replace(v12, segment_exit_mode="ema55", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.35)
        elif value == "ema55_adx22":
            item = replace(v12, segment_exit_mode="ema55_adx", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.35, segment_adx=22.0)
        else:
            item = replace(v12, segment_exit_mode="ema21_adx", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.35, segment_adx=22.0)
        add_v12("segment_exit_mode", value, item)
    for value in (2.0, 6.0, 8.0):
        add_v12("segment_min_mfe_atr", value, replace(v12, segment_exit_mode="adx", segment_min_mfe_atr=value, segment_adx=18.0, segment_bars=3))
    for value in (0.20, 0.50, 0.65):
        add_v12("segment_exit_min_capture", value, replace(v12, segment_exit_mode="ema55", segment_min_mfe_atr=4.0, segment_exit_min_capture=value))
    for value in (16.0, 18.0, 22.0, 26.0):
        add_v12("segment_adx", value, replace(v12, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=value, segment_bars=3))
    for value in (1, 2, 4):
        add_v12("segment_bars", value, replace(v12, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=18.0, segment_bars=value))

    return candidates


def risk_score(result: dict[str, Any]) -> float:
    return float(result["return"] + result["max_dd"] * 2.0)


def compact_metric(parameter: str, value: str, result: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    dd = abs(float(result["max_dd"]))
    return {
        "parameter": parameter,
        "value": value,
        "name": result["name"],
        "return": result["return"],
        "max_dd": result["max_dd"],
        "calmar": 0.0 if dd == 0 else float(result["return"] / dd),
        "risk_score": risk_score(result),
        "sharpe": result["sharpe"],
        "trades": result["trades"],
        "late_trades": result["late_trades"],
        "win_rate": result["win_rate"],
        "avg_trade_pct": result["avg_trade_pct"],
        "median_trade_pct": result["median_trade_pct"],
        "best_trade_pct": result["best_trade_pct"],
        "worst_trade_pct": result["worst_trade_pct"],
        "avg_hold_bars": result["avg_hold_bars"],
        "exit_reasons": result["exit_reasons"],
        "return_delta": result["return"] - base["return"],
        "max_dd_delta": result["max_dd"] - base["max_dd"],
        "sharpe_delta": result["sharpe"] - base["sharpe"],
        "trades_delta": result["trades"] - base["trades"],
        "win_rate_delta": result["win_rate"] - base["win_rate"],
    }


def summarize_sensitivity(ranking: pd.DataFrame, base: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for parameter, group in ranking[ranking.parameter != "baseline"].groupby("parameter", sort=False):
        best_return = group.sort_values("return", ascending=False).iloc[0]
        best_dd = group.sort_values("max_dd", ascending=False).iloc[0]
        best_risk = group.sort_values("risk_score", ascending=False).iloc[0]
        rows.append(
            {
                "parameter": parameter,
                "candidates": int(len(group)),
                "best_value_by_return": str(best_return["value"]),
                "best_return": float(best_return["return"]),
                "best_return_delta": float(best_return["return"] - base["return"]),
                "best_value_by_dd": str(best_dd["value"]),
                "best_max_dd": float(best_dd["max_dd"]),
                "best_dd_delta": float(best_dd["max_dd"] - base["max_dd"]),
                "best_value_by_risk_score": str(best_risk["value"]),
                "best_risk_score": float(best_risk["risk_score"]),
                "return_range": float(group["return"].max() - group["return"].min()),
                "dd_range": float(group["max_dd"].max() - group["max_dd"].min()),
                "win_rate_range": float(group["win_rate"].max() - group["win_rate"].min()),
                "worst_return": float(group["return"].min()),
            }
        )
    return pd.DataFrame(rows).sort_values(["return_range", "dd_range"], ascending=False)


def run_windows(frame: pd.DataFrame, specs: list[LateReentrySpec]) -> pd.DataFrame:
    end_ts = pd.Timestamp(frame.ts.iloc[-1])
    rows = []
    for spec in specs:
        for label, delta in WINDOWS.items():
            result = run_late_reentry(frame, spec, start_ts=end_ts - delta)
            rows.append(
                {
                    "name": spec.name,
                    "window": label,
                    "return": result["return"],
                    "max_dd": result["max_dd"],
                    "sharpe": result["sharpe"],
                    "trades": result["trades"],
                    "late_trades": result["late_trades"],
                    "win_rate": result["win_rate"],
                    "avg_trade_pct": result["avg_trade_pct"],
                    "median_trade_pct": result["median_trade_pct"],
                    "exit_reasons": result["exit_reasons"],
                }
            )
    return pd.DataFrame(rows)


def diagnostic_summary(frame: pd.DataFrame, name: str, result: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    trades = trade_frame_from_result(name, result["trades_detail"])
    if trades.empty:
        empty = pd.DataFrame()
        return empty, empty
    ts_index = pd.DatetimeIndex(pd.to_datetime(frame.ts, utc=True))
    detail = pd.DataFrame([diagnose_trade(frame, ts_index, trade) for _, trade in trades.iterrows()])
    summary, _ = summarize(detail)
    return summary, detail


def main() -> None:
    frame = load_frame()
    end_ts = pd.Timestamp(frame.ts.iloc[-1])
    start_ts = end_ts - pd.Timedelta(days=365)
    base = base_spec()
    candidates = candidate_specs(base)

    raw_results = []
    for parameter, value, spec in candidates:
        result = run_late_reentry(frame, spec, start_ts=start_ts)
        raw_results.append((parameter, value, spec, result))

    base_result = next(result for parameter, _, _, result in raw_results if parameter == "baseline")
    ranking = pd.DataFrame([compact_metric(parameter, value, result, base_result) for parameter, value, _, result in raw_results])
    ranking = ranking.sort_values(["return", "risk_score", "max_dd"], ascending=[False, False, False])
    sensitivity = summarize_sensitivity(ranking, base_result)

    top_names = list(dict.fromkeys(["V14_age256_dist06_cd16", *ranking.head(6)["name"].tolist(), *ranking.sort_values("risk_score", ascending=False).head(4)["name"].tolist()]))
    spec_by_name = {spec.name: spec for _, _, spec, _ in raw_results}
    top_specs = [spec_by_name[name] for name in top_names if name in spec_by_name]
    windows = run_windows(frame, top_specs)

    best_name = str(ranking.iloc[0]["name"])
    best_spec = spec_by_name[best_name]
    base_full = run_late_reentry(frame, base, start_ts=start_ts, collect_trades=True)
    best_full = run_late_reentry(frame, best_spec, start_ts=start_ts, collect_trades=True)
    base_diag, _ = diagnostic_summary(frame, base.name, base_full)
    best_diag, best_detail = diagnostic_summary(frame, best_name, best_full)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_PATH, index=False)
    sensitivity.to_csv(SENSITIVITY_PATH, index=False)
    windows.to_csv(WINDOWS_PATH, index=False)
    base_diag.to_csv(DIAG_BASE_PATH, index=False)
    best_diag.to_csv(DIAG_BEST_PATH, index=False)
    best_detail.to_csv(DIAG_DETAIL_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "data": {"start": str(start_ts), "end": str(end_ts), "rows": int(len(frame))},
                "baseline_spec": asdict(base),
                "baseline_result": base_result,
                "ranking_top20": ranking.head(20).to_dict(orient="records"),
                "sensitivity": sensitivity.to_dict(orient="records"),
                "top_windows": windows.to_dict(orient="records"),
                "base_diagnostics_summary": base_diag.to_dict(orient="records"),
                "best_diagnostics_summary": best_diag.to_dict(orient="records"),
                "notes": [
                    "Single-factor ablation around V14. Each candidate changes one active parameter or one inactive parameter through a sensible activation bundle.",
                    "Backtest range is the latest 365 days to match V14 main ledger.",
                    "No multi-parameter grid search is included here; this is sensitivity discovery, not final optimization.",
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
    print(f"windows={WINDOWS_PATH}")
    print("baseline", {key: base_result[key] for key in ("return", "max_dd", "sharpe", "trades", "late_trades", "win_rate")})
    print("\\nranking top12")
    print(ranking.head(12).to_string(index=False))
    print("\\nsensitivity top12")
    print(sensitivity.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
