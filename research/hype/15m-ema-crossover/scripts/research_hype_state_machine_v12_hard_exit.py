from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from research_hype_ema_cross_strategy import build_features
from research_hype_ema_oscillator_top_exit_v10 import add_oscillator_features
from research_hype_ema_regime_hold_v5 import load_hype_data_lake, run_variant_dynamic_3x
from research_hype_ema_volume_exhaustion_v7 import add_volume_features
from research_hype_ema_volume_overlay_v8 import v6_variant
from research_hype_state_machine_v12 import V12Spec, add_structure_features, run_v12
from research_hype_trade_path_diagnostics_v11 import diagnose_trade, summarize, trade_frame_from_result


REPORT_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_state_machine_v12_hard_exit.json")
RANKING_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_state_machine_v12_hard_exit_ranking.csv")
SUMMARY_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_state_machine_v12_hard_exit_diagnostics_summary.csv")
CATEGORY_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_state_machine_v12_hard_exit_diagnostics_categories.csv")
DETAIL_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_state_machine_v12_hard_exit_diagnostics_detail.csv")


def spec(
    name: str,
    *,
    hard_exit_mode: str = "none",
    hard_exit_bars: int = 1,
    fallback_adx: float = 0.0,
    volume_warning_mode: str = "all",
    warning_exit_min_capture: float = 0.0,
    entry_max_regime_age: int = 0,
    entry_min_rvol96: float = 0.0,
    entry_max_dist_ema96: float = 0.0,
    entry_max_move48: float = 0.0,
    segment_exit_mode: str = "none",
    segment_min_mfe_atr: float = 0.0,
    segment_exit_min_capture: float = 0.0,
    segment_adx: float = 0.0,
    segment_bars: int = 1,
) -> V12Spec:
    return V12Spec(
        name=name,
        warning_source="volume",
        confirm_mode="ema21",
        reentry_mode="none",
        min_mfe_atr=4.0,
        confirm_window=24,
        trail_atr=5.0,
        osc_min_score=3,
        fallback_adx=fallback_adx,
        fallback_bars=3,
        hard_exit_mode=hard_exit_mode,
        hard_exit_bars=hard_exit_bars,
        volume_warning_mode=volume_warning_mode,
        warning_exit_min_capture=warning_exit_min_capture,
        entry_max_regime_age=entry_max_regime_age,
        entry_min_rvol96=entry_min_rvol96,
        entry_max_dist_ema96=entry_max_dist_ema96,
        entry_max_move48=entry_max_move48,
        segment_exit_mode=segment_exit_mode,
        segment_min_mfe_atr=segment_min_mfe_atr,
        segment_exit_min_capture=segment_exit_min_capture,
        segment_adx=segment_adx,
        segment_bars=segment_bars,
    )


def build_specs() -> list[V12Spec]:
    return [
        spec("V12_high_no_hard"),
        spec("V12_high_adx18", fallback_adx=18.0),
        spec("V12_high_adx22", fallback_adx=22.0),
        spec("V12_high_ema96_b1", hard_exit_mode="ema96"),
        spec("V12_high_ema96_b2", hard_exit_mode="ema96", hard_exit_bars=2),
        spec("V12_high_swing24_b1", hard_exit_mode="swing24"),
        spec("V12_high_swing48_b1", hard_exit_mode="swing48"),
        spec("V12_high_swing96_b1", hard_exit_mode="swing96"),
        spec("V12_high_swing96_b2", hard_exit_mode="swing96", hard_exit_bars=2),
        spec("V12_high_ema96_or_swing24_b1", hard_exit_mode="ema96_or_swing24"),
        spec("V12_high_ema96_or_swing48_b1", hard_exit_mode="ema96_or_swing48"),
        spec("V12_high_ema96_or_swing96_b1", hard_exit_mode="ema96_or_swing96"),
        spec("V12_high_ema96_and_swing24_b1", hard_exit_mode="ema96_and_swing24"),
        spec("V12_high_ema96_and_swing96_b1", hard_exit_mode="ema96_and_swing96"),
        spec("V12_high_ema96_b1_adx22", hard_exit_mode="ema96", fallback_adx=22.0),
        spec("V12_high_swing24_b1_adx22", hard_exit_mode="swing24", fallback_adx=22.0),
        spec("V12_high_swing48_b1_adx22", hard_exit_mode="swing48", fallback_adx=22.0),
        spec("V12_high_swing96_b1_adx18", hard_exit_mode="swing96", fallback_adx=18.0),
        spec("V12_high_swing96_b1_adx22", hard_exit_mode="swing96", fallback_adx=22.0),
        spec("V12_high_ema96_or_swing24_b1_adx22", hard_exit_mode="ema96_or_swing24", fallback_adx=22.0),
        spec("V12_high_ema96_or_swing96_b1_adx22", hard_exit_mode="ema96_or_swing96", fallback_adx=22.0),
        spec("V12_2_swing96_no_mfi_div", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div"),
        spec("V12_2_swing96_blowoff_only", hard_exit_mode="swing96", volume_warning_mode="blowoff_only"),
        spec("V12_2_swing96_mfi_rvol2", hard_exit_mode="swing96", volume_warning_mode="mfi_rvol_exit"),
        spec("V12_2_swing96_mfi_rvol2_wick35", hard_exit_mode="swing96", volume_warning_mode="mfi_rvol_exit_wick35"),
        spec("V12_2_swing96_mfi_rvol2_adx18", hard_exit_mode="swing96", fallback_adx=18.0, volume_warning_mode="mfi_rvol_exit"),
        spec("V12_3_no_mfi_cap20", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.20),
        spec("V12_3_no_mfi_cap35", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35),
        spec("V12_3_no_mfi_cap50", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.50),
        spec("V12_3_blowoff_cap35", hard_exit_mode="swing96", volume_warning_mode="blowoff_only", warning_exit_min_capture=0.35),
        spec("V12_4_cap35_age256", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=256),
        spec("V12_4_cap35_age128", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=128),
        spec("V12_4_cap35_age192", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=192),
        spec("V12_4_cap35_age384", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=384),
        spec("V12_4_cap35_rvol12", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_min_rvol96=1.2),
        spec("V12_4_cap35_rvol15", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_min_rvol96=1.5),
        spec("V12_4_cap35_dist08", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_dist_ema96=0.08),
        spec("V12_4_cap35_dist10", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_dist_ema96=0.10),
        spec("V12_4_cap35_move48_10", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_move48=0.10),
        spec("V12_4_cap35_move48_12", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_move48=0.12),
        spec("V12_4_cap35_age384_dist10", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=384, entry_max_dist_ema96=0.10),
        spec("V12_4_cap35_age384_move12", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=384, entry_max_move48=0.12),
        spec("V12_4_cap35_age256_move12", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=256, entry_max_move48=0.12),
        spec("V12_4_cap35_age192_move12", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=192, entry_max_move48=0.12),
        spec("V12_4_cap35_age256_rvol12", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=256, entry_min_rvol96=1.2),
        spec("V12_4_cap35_age256_dist08", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=256, entry_max_dist_ema96=0.08),
        spec("V12_4_cap35_dist10_move12", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_dist_ema96=0.10, entry_max_move48=0.12),
        spec("V12_4_cap35_age384_dist10_move12", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=384, entry_max_dist_ema96=0.10, entry_max_move48=0.12),
        spec("V12_5_segment_adx18_mfe4", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=18.0, segment_bars=3),
        spec("V12_5_segment_adx22_mfe4", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=22.0, segment_bars=3),
        spec("V12_5_segment_ema55_mfe4_cap35", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, segment_exit_mode="ema55", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.35, segment_bars=1),
        spec("V12_5_segment_ema55_mfe6_cap35", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, segment_exit_mode="ema55", segment_min_mfe_atr=6.0, segment_exit_min_capture=0.35, segment_bars=1),
        spec("V12_5_segment_ema55_adx22_mfe4_cap35", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, segment_exit_mode="ema55_adx", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.35, segment_adx=22.0, segment_bars=1),
        spec("V12_5_segment_ema21_adx22_mfe4_cap35", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, segment_exit_mode="ema21_adx", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.35, segment_adx=22.0, segment_bars=1),
        spec("V12_5_segment_ema55_mfe4_cap50", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, segment_exit_mode="ema55", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.50, segment_bars=1),
        spec("V12_5_move12_segment_ema55_mfe4_cap35", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_move48=0.12, segment_exit_mode="ema55", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.35, segment_bars=1),
        spec("V12_5_age128_segment_ema55_mfe4_cap35", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=128, segment_exit_mode="ema55", segment_min_mfe_atr=4.0, segment_exit_min_capture=0.35, segment_bars=1),
        spec("V12_6_age128_segment_adx18_mfe4", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=128, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=18.0, segment_bars=3),
        spec("V12_6_age128_segment_adx22_mfe4", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=128, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=22.0, segment_bars=3),
        spec("V12_6_age192_segment_adx18_mfe4", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=192, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=18.0, segment_bars=3),
        spec("V12_6_age192_segment_adx22_mfe4", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=192, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=22.0, segment_bars=3),
        spec("V12_6_age256_segment_adx18_mfe4", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=256, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=18.0, segment_bars=3),
        spec("V12_6_age256_segment_adx22_mfe4", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=256, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=22.0, segment_bars=3),
        spec("V12_6_age128_move12_segment_adx18_mfe4", hard_exit_mode="swing96", volume_warning_mode="no_mfi_div", warning_exit_min_capture=0.35, entry_max_regime_age=128, entry_max_move48=0.12, segment_exit_mode="adx", segment_min_mfe_atr=4.0, segment_adx=18.0, segment_bars=3),
    ]


def compact_metric(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "name",
        "hard_exit_mode",
        "hard_exit_bars",
        "volume_warning_mode",
        "warning_exit_min_capture",
        "entry_max_regime_age",
        "entry_min_rvol96",
        "entry_max_dist_ema96",
        "entry_max_move48",
        "segment_exit_mode",
        "segment_min_mfe_atr",
        "segment_exit_min_capture",
        "segment_adx",
        "segment_bars",
        "fallback_adx",
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
        "exit_reasons",
        "fitness",
    ]
    return {key: result[key] for key in keys}


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_structure_features(add_oscillator_features(add_volume_features(build_features(raw))))
    specs = build_specs()

    results = [run_v12(frame, item, collect_trades=True) for item in specs]
    ranking = pd.DataFrame([compact_metric(result) for result in results]).sort_values(
        ["fitness", "return", "max_dd"], ascending=[False, False, False]
    )

    trades = pd.concat(
        [
            trade_frame_from_result(result["name"], result["trades_detail"])
            for result in results
        ],
        ignore_index=True,
        sort=False,
    )
    ts_index = pd.DatetimeIndex(pd.to_datetime(frame.ts, utc=True))
    detail = pd.DataFrame([diagnose_trade(frame, ts_index, trade) for _, trade in trades.iterrows()])
    summary, categories = summarize(detail)
    v6 = run_variant_dynamic_3x(frame, v6_variant())

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_PATH, index=False)
    detail.to_csv(DETAIL_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)
    categories.to_csv(CATEGORY_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "v6_baseline": v6,
                "specs": [asdict(item) for item in specs],
                "ranking": ranking.to_dict(orient="records"),
                "diagnostics_summary": summary.to_dict(orient="records"),
                "diagnostics_categories": categories.to_dict(orient="records"),
                "notes": [
                    "Focused V12.1 test: keep V12 high-return warning/EMA21-confirm logic.",
                    "Add hard trend invalidation that can exit without waiting for warning.",
                    "Hard exits tested: EMA96 break, 24/48/96-bar swing break, and ADX fallback combinations.",
                ],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={REPORT_PATH}")
    print(f"ranking={RANKING_PATH}")
    print(ranking.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
