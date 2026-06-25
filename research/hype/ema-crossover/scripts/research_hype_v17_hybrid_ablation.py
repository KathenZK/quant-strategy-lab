from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_ema_cross_strategy import build_features
from research_hype_ema_oscillator_top_exit_v10 import add_oscillator_features
from research_hype_ema_regime_hold_v5 import load_hype_data_lake
from research_hype_ema_volume_exhaustion_v7 import add_volume_features
from research_hype_state_machine_v12 import V12Spec, add_structure_features
from research_hype_state_machine_v12_hard_exit import spec as focused_spec
from research_hype_trade_path_diagnostics_v11 import diagnose_trade, summarize, trade_frame_from_result
from research_hype_v13_late_reentry import LateReentrySpec, run_late_reentry
from research_hype_v17_trend_state_search import SignalPlan, add_v17_indicators, build_signal


REPORT_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v17_hybrid_ablation.json")
RANKING_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v17_hybrid_ablation_ranking.csv")
SENSITIVITY_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v17_hybrid_ablation_sensitivity.csv")
WINDOWS_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v17_hybrid_ablation_top_windows.csv")
ATTRIBUTION_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v17_hybrid_ablation_trade_attribution.csv")
DIAG_BASE_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v17_hybrid_ablation_base_diagnostics_summary.csv")
DIAG_BEST_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v17_hybrid_ablation_best_diagnostics_summary.csv")
DIAG_DETAIL_PATH = Path("research/hype/families/ema-crossover/artifacts/hype_v17_hybrid_ablation_best_diagnostics_detail.csv")

WINDOWS = {
    "1W": pd.Timedelta(days=7),
    "1M": pd.Timedelta(days=30),
    "3M": pd.Timedelta(days=90),
    "6M": pd.Timedelta(days=180),
    "1Y": pd.Timedelta(days=365),
}

TARGET_DD = -0.20
V16_RETURN = 32.02922252923522


@dataclass(frozen=True, slots=True)
class HybridSignalConfig:
    hq_enabled: bool = True
    hq_min_score: int = 7
    lq_enabled: bool = True
    lq_min_score: int = 5
    lq_max_score: int = 6
    lq_max_dist_ema96: float = 0.04
    lq_max_atr_ratio: float = 1.1
    lq_require_not_hot_edge: bool = False
    lq_require_obv: bool = False
    lq_require_cmf: bool = False


@dataclass(frozen=True, slots=True)
class HybridCandidate:
    parameter: str
    value: str
    name: str
    signal: HybridSignalConfig
    spec: LateReentrySpec
    hq_scale: float = 1.0
    lq_scale: float = 1.0


def pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def load_frame() -> pd.DataFrame:
    raw = load_hype_data_lake()
    return add_v17_indicators(add_structure_features(add_oscillator_features(add_volume_features(build_features(raw)))))


def base_late_spec(name: str = "HYPE_EMA_X_V17") -> LateReentrySpec:
    v12 = focused_spec(
        f"{name}_v12",
        hard_exit_mode="swing96",
        volume_warning_mode="no_mfi_div",
        warning_exit_min_capture=0.35,
        entry_max_regime_age=128,
        entry_max_dist_ema96=0.08,
        segment_exit_mode="none",
        segment_min_mfe_atr=0.0,
        segment_exit_min_capture=0.0,
        segment_adx=0.0,
        segment_bars=1,
    )
    v12 = replace(v12, warning_source="either", osc_min_score=2, stop_atr=8.0)
    return LateReentrySpec(
        name,
        v12,
        late_max_age=384,
        late_dist_ema96=0.075,
        cooldown_bars=12,
        min_prev_pnl=-0.03,
        min_prev_mfe_atr=3.0,
        require_pullback=False,
        pullback_buffer=0.0,
    )


def base_candidate() -> HybridCandidate:
    return HybridCandidate("baseline", "baseline", "HYPE_EMA_X_V17", HybridSignalConfig(), base_late_spec())


def safe_name(value: object) -> str:
    return str(value).replace(" ", "").replace("/", "_").replace(".", "p").replace("-", "m")


def candidate_specs(base: HybridCandidate) -> list[HybridCandidate]:
    candidates = [base]

    def add(parameter: str, value: object, *, signal: HybridSignalConfig | None = None, spec: LateReentrySpec | None = None, hq_scale: float | None = None, lq_scale: float | None = None) -> None:
        item = HybridCandidate(
            parameter,
            str(value),
            f"HYPE_EMA_X_V17__{parameter}={safe_name(value)}",
            signal or base.signal,
            spec or base.spec,
            base.hq_scale if hq_scale is None else hq_scale,
            base.lq_scale if lq_scale is None else lq_scale,
        )
        if item == base:
            return
        candidates.append(item)

    def add_v12(parameter: str, value: object, v12: V12Spec) -> None:
        add(parameter, value, spec=replace(base.spec, name=f"HYPE_EMA_X_V17__{parameter}={safe_name(value)}", v12=replace(v12, name=f"V17_v12__{parameter}={safe_name(value)}")))

    def add_late(parameter: str, value: object, spec: LateReentrySpec) -> None:
        add(parameter, value, spec=replace(spec, name=f"HYPE_EMA_X_V17__{parameter}={safe_name(value)}"))

    signal = base.signal
    for value in (False,):
        add("hq_enabled", value, signal=replace(signal, hq_enabled=value))
    for value in (6, 8, 9):
        add("hq_min_score", value, signal=replace(signal, hq_min_score=value))
    for value in (False,):
        add("lq_enabled", value, signal=replace(signal, lq_enabled=value))
    for value in (4, 6):
        add("lq_min_score", value, signal=replace(signal, lq_min_score=value))
    for value in (5, 7):
        add("lq_max_score", value, signal=replace(signal, lq_max_score=value))
    for value in (0.03, 0.05, 0.06, 0.08):
        add("lq_max_dist_ema96", value, signal=replace(signal, lq_max_dist_ema96=value))
    for value in (1.0, 1.2, 1.4, 1.6, 1.8):
        add("lq_max_atr_ratio", value, signal=replace(signal, lq_max_atr_ratio=value))
    for value in (True,):
        add("lq_require_not_hot_edge", value, signal=replace(signal, lq_require_not_hot_edge=value))
        add("lq_require_obv", value, signal=replace(signal, lq_require_obv=value))
        add("lq_require_cmf", value, signal=replace(signal, lq_require_cmf=value))
    for value in (0.0, 0.25, 0.5, 0.75, 1.25):
        add("lq_scale", value, lq_scale=value)
    for value in (0.75, 0.9, 1.1):
        add("hq_scale", value, hq_scale=value)

    spec = base.spec
    for value in (0, 256, 512):
        add_late("late_max_age", value, replace(spec, late_max_age=value))
    for value in (0.05, 0.06, 0.10, 0.12):
        add_late("late_dist_ema96", value, replace(spec, late_dist_ema96=value))
    for value in (0, 8, 16, 24, 32):
        add_late("cooldown_bars", value, replace(spec, cooldown_bars=value))
    for value in (-0.05, -0.01, 0.0, 0.03):
        add_late("min_prev_pnl", value, replace(spec, min_prev_pnl=value))
    for value in (2.0, 4.0, 5.0, 6.0, 8.0):
        add_late("min_prev_mfe_atr", value, replace(spec, min_prev_mfe_atr=value))
    add_late("require_pullback", True, replace(spec, require_pullback=True, pullback_buffer=0.0))
    for value in (0.005, 0.01, 0.02):
        add_late("pullback_buffer", value, replace(spec, require_pullback=True, pullback_buffer=value))

    v12 = base.spec.v12
    for value in ("volume", "osc"):
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
    for value in (0.0, 0.2, 0.5, 0.65):
        add_v12("warning_exit_min_capture", value, replace(v12, warning_exit_min_capture=value))
    for value in (0, 64, 192, 256):
        add_v12("entry_max_regime_age", value, replace(v12, entry_max_regime_age=value))
    for value in (1.1, 1.2, 1.5):
        add_v12("entry_min_rvol96", value, replace(v12, entry_min_rvol96=value))
    for value in (0.04, 0.06, 0.10, 0.12):
        add_v12("entry_max_dist_ema96", value, replace(v12, entry_max_dist_ema96=value))
    for value in (0.08, 0.10, 0.12, 0.16):
        add_v12("entry_max_move48", value, replace(v12, entry_max_move48=value))
    for value in (7.0, 9.0, 10.0, 12.0):
        add_v12("stop_atr", value, replace(v12, stop_atr=value))
    for value in (1.5, 2.5, 3.0):
        add_v12("exit_rvol", value, replace(v12, exit_rvol=value))
    for value in (0.35, 0.45, 0.65):
        add_v12("wick_min", value, replace(v12, wick_min=value))
    for value in (7.5, 10.0, 12.5):
        add_v12("trail_atr", value, replace(v12, confirm_mode="atr_trail", trail_atr=value))
    for value in (1, 3, 4):
        add_v12("osc_min_score", value, replace(v12, warning_source="either", osc_min_score=value))
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
    for value in (0.2, 0.5, 0.65):
        add_v12("segment_exit_min_capture", value, replace(v12, segment_exit_mode="ema55", segment_min_mfe_atr=4.0, segment_exit_min_capture=value))
    for value in (16.0, 18.0, 22.0, 26.0):
        add_v12("segment_adx", value, replace(v12, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=value, segment_bars=3))
    for value in (1, 2, 4):
        add_v12("segment_bars", value, replace(v12, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=18.0, segment_bars=value))

    return candidates


def hybrid_signal(frame: pd.DataFrame, config: HybridSignalConfig, base_signal: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    score = frame.trend_score.to_numpy("float64")
    dist = frame.dir_dist_ema96.to_numpy("float64")
    atr = frame.atr_ratio96_672.to_numpy("float64")
    donchian = frame.dir_donchian96.to_numpy("float64")
    vol = frame.vol_surge192.to_numpy("float64")
    obv = frame.dir_obv_slope48.to_numpy("float64")
    cmf = frame.dir_cmf20.to_numpy("float64")
    base_mask = base_signal != 0

    hq = base_mask & config.hq_enabled & (score >= config.hq_min_score)
    lq = (
        base_mask
        & config.lq_enabled
        & (score >= config.lq_min_score)
        & (score <= config.lq_max_score)
        & (dist <= config.lq_max_dist_ema96)
        & (atr <= config.lq_max_atr_ratio)
    )
    if config.lq_require_not_hot_edge:
        hot = (donchian >= 0.96) & (dist > 0.04) & (vol < 1.0)
        lq &= ~hot
    if config.lq_require_obv:
        lq &= obv > 0
    if config.lq_require_cmf:
        lq &= cmf > 0

    overlap = hq & lq
    lq &= ~overlap
    signal = np.where(hq | lq, base_signal, 0).astype(base_signal.dtype)
    kind = np.array([""] * len(frame), dtype=object)
    kind[hq & (signal != 0)] = "hq"
    kind[lq & (signal != 0)] = "lq"
    return signal, kind, {
        "base_bars": int(np.count_nonzero(base_mask)),
        "hq_bars": int(np.count_nonzero(hq)),
        "lq_bars": int(np.count_nonzero(lq)),
        "signal_bars": int(np.count_nonzero(signal)),
    }


def run_candidate(frame: pd.DataFrame, candidate: HybridCandidate, start_ts: pd.Timestamp, base_signal: np.ndarray, *, collect_trades: bool = False) -> tuple[dict[str, Any], dict[str, int]]:
    signal, kind, counts = hybrid_signal(frame, candidate.signal, base_signal)
    result = run_late_reentry(
        frame,
        candidate.spec,
        start_ts=start_ts,
        collect_trades=collect_trades,
        signal_override=signal,
        signal_kind_override=kind,
        entry_allocation_scale={"hq": candidate.hq_scale, "lq": candidate.lq_scale},
    )
    result["name"] = candidate.name
    return result, counts


def compact_metric(candidate: HybridCandidate, result: dict[str, Any], counts: dict[str, int], base: dict[str, Any]) -> dict[str, Any]:
    dd = abs(float(result["max_dd"]))
    return {
        "parameter": candidate.parameter,
        "value": candidate.value,
        "name": result["name"],
        "return": result["return"],
        "max_dd": result["max_dd"],
        "calmar": 0.0 if dd == 0 else float(result["return"] / dd),
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
        "hq_scale": candidate.hq_scale,
        "lq_scale": candidate.lq_scale,
        **counts,
        "passes_dd20": bool(result["max_dd"] >= TARGET_DD),
        "v16_return_capture": float(result["return"] / V16_RETURN),
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
        best_low_dd = group[group.max_dd >= TARGET_DD].sort_values("return", ascending=False)
        low_dd_row = best_low_dd.iloc[0] if not best_low_dd.empty else best_return
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
                "best_low_dd_value": str(low_dd_row["value"]),
                "best_low_dd_return": float(low_dd_row["return"]),
                "return_range": float(group["return"].max() - group["return"].min()),
                "dd_range": float(group["max_dd"].max() - group["max_dd"].min()),
                "win_rate_range": float(group["win_rate"].max() - group["win_rate"].min()),
                "worst_return": float(group["return"].min()),
            }
        )
    return pd.DataFrame(rows).sort_values(["return_range", "dd_range"], ascending=False)


def run_windows(frame: pd.DataFrame, candidates: list[HybridCandidate], base_signal: np.ndarray) -> pd.DataFrame:
    end_ts = pd.Timestamp(frame.ts.iloc[-1])
    rows = []
    for candidate in candidates:
        for label, delta in WINDOWS.items():
            result, counts = run_candidate(frame, candidate, end_ts - delta, base_signal)
            rows.append(
                {
                    "name": candidate.name,
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
                    **counts,
                }
            )
    return pd.DataFrame(rows)


def trade_attribution(result: dict[str, Any]) -> pd.DataFrame:
    trades = pd.DataFrame(result.get("trades_detail", []))
    if trades.empty:
        return pd.DataFrame()
    trades["kind_bucket"] = trades.entry_kind.astype(str).str.extract(r"^(hq|lq)", expand=False).fillna("unknown")
    rows = []
    for bucket, group in trades.groupby("kind_bucket"):
        rows.append(
            {
                "name": result["name"],
                "kind_bucket": bucket,
                "trades": int(len(group)),
                "wins": int((group.pnl_pct > 0).sum()),
                "win_rate": float((group.pnl_pct > 0).mean()),
                "sum_pnl_pct": float(group.pnl_pct.sum()),
                "avg_pnl_pct": float(group.pnl_pct.mean()),
                "median_pnl_pct": float(group.pnl_pct.median()),
                "worst_pnl_pct": float(group.pnl_pct.min()),
                "exit_reasons": {str(reason): int(count) for reason, count in group.exit_reason.value_counts().items()},
            }
        )
    return pd.DataFrame(rows)


def diagnostic_summary(frame: pd.DataFrame, result: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    trades = trade_frame_from_result(result["name"], result.get("trades_detail", []))
    if trades.empty:
        return pd.DataFrame(), pd.DataFrame()
    ts_index = pd.DatetimeIndex(pd.to_datetime(frame.ts, utc=True))
    detail = pd.DataFrame([diagnose_trade(frame, ts_index, trade) for _, trade in trades.iterrows()])
    summary, _ = summarize(detail)
    return summary, detail


def main() -> None:
    frame = load_frame()
    end_ts = pd.Timestamp(frame.ts.iloc[-1])
    start_ts = end_ts - pd.Timedelta(days=365)
    base_signal, _kind, _counts = build_signal(frame, SignalPlan("atr18_base", "atr18"))
    base = base_candidate()
    candidates = candidate_specs(base)

    raw_results = []
    for candidate in candidates:
        result, counts = run_candidate(frame, candidate, start_ts, base_signal)
        raw_results.append((candidate, result, counts))

    base_result = next(result for candidate, result, _ in raw_results if candidate.parameter == "baseline")
    ranking = pd.DataFrame([compact_metric(candidate, result, counts, base_result) for candidate, result, counts in raw_results])
    ranking = ranking.sort_values(["passes_dd20", "return", "max_dd"], ascending=[False, False, False])
    sensitivity = summarize_sensitivity(ranking, base_result)

    candidate_by_name = {candidate.name: candidate for candidate, _, _ in raw_results}
    top_names = list(
        dict.fromkeys(
            [
                base.name,
                *ranking.head(8)["name"].tolist(),
                *ranking.sort_values(["return"], ascending=False).head(5)["name"].tolist(),
                *ranking.sort_values(["max_dd", "return"], ascending=[False, False]).head(5)["name"].tolist(),
            ]
        )
    )
    top_candidates = [candidate_by_name[name] for name in top_names if name in candidate_by_name]
    windows = run_windows(frame, top_candidates, base_signal)

    best_name = str(ranking.iloc[0]["name"])
    best_candidate = candidate_by_name[best_name]
    base_full, _ = run_candidate(frame, base, start_ts, base_signal, collect_trades=True)
    best_full, _ = run_candidate(frame, best_candidate, start_ts, base_signal, collect_trades=True)
    base_attr = trade_attribution(base_full)
    best_attr = trade_attribution(best_full)
    attribution = pd.concat([base_attr, best_attr], ignore_index=True, sort=False)
    base_diag, _ = diagnostic_summary(frame, base_full)
    best_diag, best_detail = diagnostic_summary(frame, best_full)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_PATH, index=False)
    sensitivity.to_csv(SENSITIVITY_PATH, index=False)
    windows.to_csv(WINDOWS_PATH, index=False)
    attribution.to_csv(ATTRIBUTION_PATH, index=False)
    base_diag.to_csv(DIAG_BASE_PATH, index=False)
    best_diag.to_csv(DIAG_BEST_PATH, index=False)
    best_detail.to_csv(DIAG_DETAIL_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "data": {"start": str(start_ts), "end": str(end_ts), "bars": int(len(frame))},
                "candidate_count": len(candidates),
                "baseline_candidate": {
                    "signal": asdict(base.signal),
                    "late_spec": asdict(base.spec),
                    "hq_scale": base.hq_scale,
                    "lq_scale": base.lq_scale,
                },
                "baseline_result": base_result,
                "best_candidate": {
                    "name": best_candidate.name,
                    "parameter": best_candidate.parameter,
                    "value": best_candidate.value,
                    "signal": asdict(best_candidate.signal),
                    "late_spec": asdict(best_candidate.spec),
                    "hq_scale": best_candidate.hq_scale,
                    "lq_scale": best_candidate.lq_scale,
                },
                "best_result": best_full,
                "ranking_top20": ranking.head(20).to_dict(orient="records"),
                "sensitivity": sensitivity.to_dict(orient="records"),
                "top_windows": windows.to_dict(orient="records"),
                "trade_attribution": attribution.to_dict(orient="records"),
                "base_diagnostics_summary": base_diag.to_dict(orient="records"),
                "best_diagnostics_summary": best_diag.to_dict(orient="records"),
                "notes": [
                    "Single-parameter ablation around HYPE-EMA-X-V17 hybrid.",
                    "V17 signal = V15 high-quality ATR18/trend_score>=7 signal plus V16 satellite signal when trend_score is 5-6, dir_dist_ema96 <= 0.04, and atr_ratio96_672 <= 1.1.",
                    "Each row changes one active parameter, or activates one inactive module through a conservative single-module bundle.",
                    "Backtest window starts flat at latest 365 days, matching the HYPE-EMA-X main ledger.",
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
    print("\nranking top16")
    print(ranking.head(16).to_string(index=False))
    print("\nsensitivity top16")
    print(sensitivity.head(16).to_string(index=False))


if __name__ == "__main__":
    main()
