from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

from research_hype_v17_hybrid_ablation import (
    REPORT_PATH as _V17_REPORT_PATH,
    ATTRIBUTION_PATH as _V17_ATTRIBUTION_PATH,
    DIAG_BASE_PATH as _V17_DIAG_BASE_PATH,
    DIAG_BEST_PATH as _V17_DIAG_BEST_PATH,
    DIAG_DETAIL_PATH as _V17_DIAG_DETAIL_PATH,
    RANKING_PATH as _V17_RANKING_PATH,
    SENSITIVITY_PATH as _V17_SENSITIVITY_PATH,
    WINDOWS_PATH as _V17_WINDOWS_PATH,
)
from research_hype_v17_hybrid_ablation import (
    HybridCandidate,
    HybridSignalConfig,
    base_late_spec,
    candidate_specs,
    compact_metric,
    diagnostic_summary,
    load_frame,
    run_candidate,
    run_windows,
    safe_name,
    summarize_sensitivity,
    trade_attribution,
)
from research_hype_v17_trend_state_search import SignalPlan, build_signal


REPORT_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v17_1_full_ablation.json")
RANKING_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v17_1_full_ablation_ranking.csv")
SENSITIVITY_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v17_1_full_ablation_sensitivity.csv")
WINDOWS_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v17_1_full_ablation_top_windows.csv")
ATTRIBUTION_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v17_1_full_ablation_trade_attribution.csv")
DIAG_BASE_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v17_1_full_ablation_base_diagnostics_summary.csv")
DIAG_BEST_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v17_1_full_ablation_best_diagnostics_summary.csv")
DIAG_DETAIL_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_v17_1_full_ablation_best_diagnostics_detail.csv")


def _keep_imported_paths_referenced() -> tuple[Path, ...]:
    # Keeps lint tools from pruning the source-path imports above when this file
    # is used as a standalone research artifact beside the V17 script.
    return (
        _V17_REPORT_PATH,
        _V17_RANKING_PATH,
        _V17_SENSITIVITY_PATH,
        _V17_WINDOWS_PATH,
        _V17_ATTRIBUTION_PATH,
        _V17_DIAG_BASE_PATH,
        _V17_DIAG_BEST_PATH,
        _V17_DIAG_DETAIL_PATH,
    )


def base_candidate_v17_1() -> HybridCandidate:
    return HybridCandidate(
        "baseline",
        "baseline",
        "HYPE_EMA_X_V17_1",
        HybridSignalConfig(),
        base_late_spec("HYPE_EMA_X_V17_1"),
        hq_scale=1.1,
        lq_scale=1.0,
    )


def candidate_specs_v17_1(base: HybridCandidate) -> list[HybridCandidate]:
    candidates: list[HybridCandidate] = []
    seen: set[tuple[str, str, float, float]] = set()

    for candidate in candidate_specs(base):
        if candidate.parameter == "hq_scale" and candidate.value == "1.1":
            continue
        name = candidate.name
        if candidate.parameter != "baseline":
            name = f"HYPE_EMA_X_V17_1__{candidate.parameter}={safe_name(candidate.value)}"
        item = replace(candidate, name=name)
        key = (item.parameter, item.value, item.hq_scale, item.lq_scale)
        if key not in seen:
            seen.add(key)
            candidates.append(item)

    for value in (1.0, 1.2, 1.25):
        item = HybridCandidate(
            "hq_scale",
            str(value),
            f"HYPE_EMA_X_V17_1__hq_scale={safe_name(value)}",
            base.signal,
            base.spec,
            hq_scale=value,
            lq_scale=base.lq_scale,
        )
        key = (item.parameter, item.value, item.hq_scale, item.lq_scale)
        if key not in seen:
            seen.add(key)
            candidates.append(item)

    return candidates


def _top_candidate_names(ranking: pd.DataFrame, base: HybridCandidate) -> list[str]:
    return list(
        dict.fromkeys(
            [
                base.name,
                *ranking.head(8)["name"].tolist(),
                *ranking.sort_values(["return"], ascending=False).head(5)["name"].tolist(),
                *ranking.sort_values(["max_dd", "return"], ascending=[False, False]).head(5)["name"].tolist(),
            ]
        )
    )


def _write_outputs(payload: dict[str, Any], tables: dict[Path, pd.DataFrame]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    for path, table in tables.items():
        table.to_csv(path, index=False)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    _keep_imported_paths_referenced()
    frame = load_frame()
    end_ts = pd.Timestamp(frame.ts.iloc[-1])
    start_ts = end_ts - pd.Timedelta(days=365)
    base_signal, _kind, _counts = build_signal(frame, SignalPlan("atr18_base", "atr18"))
    base = base_candidate_v17_1()
    candidates = candidate_specs_v17_1(base)

    raw_results = []
    for candidate in candidates:
        result, counts = run_candidate(frame, candidate, start_ts, base_signal)
        raw_results.append((candidate, result, counts))

    base_result = next(result for candidate, result, _ in raw_results if candidate.parameter == "baseline")
    ranking = pd.DataFrame([compact_metric(candidate, result, counts, base_result) for candidate, result, counts in raw_results])
    ranking = ranking.sort_values(["passes_dd20", "return", "max_dd"], ascending=[False, False, False])
    sensitivity = summarize_sensitivity(ranking, base_result)

    candidate_by_name = {candidate.name: candidate for candidate, _, _ in raw_results}
    top_candidates = [candidate_by_name[name] for name in _top_candidate_names(ranking, base) if name in candidate_by_name]
    windows = run_windows(frame, top_candidates, base_signal)

    best_name = str(ranking.iloc[0]["name"])
    best_candidate = candidate_by_name[best_name]
    base_full, _ = run_candidate(frame, base, start_ts, base_signal, collect_trades=True)
    best_full, _ = run_candidate(frame, best_candidate, start_ts, base_signal, collect_trades=True)
    attribution = pd.concat([trade_attribution(base_full), trade_attribution(best_full)], ignore_index=True, sort=False)
    base_diag, _ = diagnostic_summary(frame, base_full)
    best_diag, best_detail = diagnostic_summary(frame, best_full)

    _write_outputs(
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
                "Single-parameter ablation around HYPE-EMA-X-V17.1.",
                "V17.1 baseline keeps the V17 signal unchanged and sets hq_scale=1.1, lq_scale=1.0.",
                "Each row changes one active parameter, or activates one inactive module through a conservative single-module bundle.",
                "Backtest window starts flat at latest 365 days, matching the HYPE-EMA-X main ledger.",
            ],
        },
        {
            RANKING_PATH: ranking,
            SENSITIVITY_PATH: sensitivity,
            WINDOWS_PATH: windows,
            ATTRIBUTION_PATH: attribution,
            DIAG_BASE_PATH: base_diag,
            DIAG_BEST_PATH: best_diag,
            DIAG_DETAIL_PATH: best_detail,
        },
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
