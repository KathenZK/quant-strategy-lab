from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-candle-count-reversal"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
ADX_SCRIPT = FAMILY_DIR / "scripts/research_hype_cc_v35_adx_di_trend_block.py"
SELECTION_END = pd.Timestamp("2026-06-01T03:00:00Z")
HOLDOUT_START = SELECTION_END + pd.Timedelta(minutes=15)
SUMMARY_PATH = (
    ARTIFACT_DIR / "hype_cc_v35_replace_24h_with_adx_di_summary_2026-07-15.json"
)
GRID_PATH = (
    ARTIFACT_DIR / "hype_cc_v35_replace_24h_with_adx_di_grid_2026-07-15.csv"
)
ROLLING_PATH = (
    ARTIFACT_DIR / "hype_cc_v35_replace_24h_with_adx_di_rolling_2026-07-15.csv"
)
RECENT_PATH = (
    ARTIFACT_DIR / "hype_cc_v35_replace_24h_with_adx_di_recent_2026-07-15.csv"
)
TRADES_PATH = (
    ARTIFACT_DIR
    / "hype_cc_v35_replace_24h_with_adx_di_selected_trades_2026-07-15.csv"
)


def load_adx_module():
    spec = importlib.util.spec_from_file_location("hype_cc_v35_adx_base", ADX_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load ADX research module: {ADX_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["hype_cc_v35_adx_base"] = module
    spec.loader.exec_module(module)
    return module


def run_variant(
    adx_module,
    base,
    replay,
    frame: pd.DataFrame,
    config,
    *,
    indicators,
    apply_original_trend_filter: bool,
    adx_window: int | None,
    adx_threshold: float | None,
    trade_start: pd.Timestamp | str | None = None,
    trade_end: pd.Timestamp | str | None = None,
):
    direction_filter = None
    if adx_window is not None and adx_threshold is not None:
        adx, plus_di, minus_di = indicators[adx_window]
        direction_filter = adx_module.make_direction_filter(
            adx,
            plus_di,
            minus_di,
            adx_threshold,
        )
    return base.run_next_open(
        replay,
        frame,
        config,
        direction_filter=direction_filter,
        apply_original_trend_filter=apply_original_trend_filter,
        trade_start=trade_start,
        trade_end=trade_end,
    )


def main() -> None:
    adx_module = load_adx_module()
    base = adx_module.load_base_module()
    replay = base._load_replay_module()
    frame, quality = base.load_and_audit_frame()
    config = replay.hype_v35_config()
    if frame.index[-1] < HOLDOUT_START:
        raise RuntimeError("post-selection holdout data is unavailable")

    selection_frame = frame.loc[frame.index <= SELECTION_END]
    canonical_baseline = base.run_canonical(replay, selection_frame, config)
    canonical_metrics = base.compact_metrics(canonical_baseline)
    parity = {
        key: (
            int(canonical_metrics[key]) == int(expected)
            if key == "entries"
            else abs(float(canonical_metrics[key]) - float(expected)) < 0.02
        )
        for key, expected in base.CURRENT_BASELINE.items()
    }
    if not all(parity.values()):
        raise RuntimeError(
            "V35 baseline parity failed: "
            f"actual={canonical_metrics}, expected={base.CURRENT_BASELINE}"
        )

    indicators = {
        window: adx_module.adx_di(frame, window)
        for window in adx_module.ADX_WINDOWS
    }
    rolling_windows = base.build_oos_windows(frame.index[0], SELECTION_END)
    candidates: list[tuple[str, bool, int | None, float | None]] = [
        ("V35 baseline", True, None, None),
        ("no trend filter", False, None, None),
        *[
            (
                f"replace ADX{window}>={threshold:g}",
                False,
                window,
                threshold,
            )
            for window in adx_module.ADX_WINDOWS
            for threshold in adx_module.ADX_THRESHOLDS
        ],
    ]
    rolling_rows: list[dict[str, Any]] = []
    for candidate_name, original_filter, adx_window, adx_threshold in candidates:
        for window_name, start, end in rolling_windows:
            run = run_variant(
                adx_module,
                base,
                replay,
                frame,
                config,
                indicators=indicators,
                apply_original_trend_filter=original_filter,
                adx_window=adx_window,
                adx_threshold=adx_threshold,
                trade_start=start,
                trade_end=end,
            )
            rolling_rows.append(
                {
                    "candidate": candidate_name,
                    "original_24h_filter": original_filter,
                    "adx_window": adx_window,
                    "adx_threshold": adx_threshold,
                    "window": window_name,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    **base.compact_metrics(run),
                }
            )
    rolling = pd.DataFrame(rolling_rows)
    aggregate = adx_module.aggregate_rolling(rolling)
    baseline = aggregate.loc[aggregate["candidate"].eq("V35 baseline")].iloc[0]
    no_filter = aggregate.loc[
        aggregate["candidate"].eq("no trend filter")
    ].iloc[0]
    grid = aggregate.loc[
        aggregate["candidate"].str.startswith("replace ADX")
    ].copy()
    grid["trade_retention"] = (
        grid["median_entries"] / float(baseline["median_entries"])
    )
    grid["pre_pass"] = (
        (grid["positive_window_rate"] >= 0.60)
        & (grid["median_sharpe"] > float(baseline["median_sharpe"]))
        & (
            grid["median_return_pct"]
            >= 0.80 * float(baseline["median_return_pct"])
        )
        & (
            grid["worst_max_drawdown_pct"]
            >= float(baseline["worst_max_drawdown_pct"])
        )
        & (grid["trade_retention"] >= 0.50)
    )
    grid["filter_contribution_pass"] = (
        (grid["median_sharpe"] > float(no_filter["median_sharpe"]))
        & (
            grid["worst_max_drawdown_pct"]
            >= float(no_filter["worst_max_drawdown_pct"])
        )
    )
    grid = grid.sort_values(
        [
            "pre_pass",
            "filter_contribution_pass",
            "median_sharpe",
            "median_return_pct",
        ],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    selected = grid.iloc[0]
    selected_window = int(selected["adx_window"])
    selected_threshold = float(selected["adx_threshold"])

    robust_neighbors = grid.loc[
        grid.apply(
            lambda row: adx_module.is_neighbor(
                selected_window,
                selected_threshold,
                int(row["adx_window"]),
                float(row["adx_threshold"]),
            ),
            axis=1,
        )
        & (
            grid["positive_window_rate"]
            >= float(baseline["positive_window_rate"])
        )
        & (
            grid["median_return_pct"]
            >= 0.80 * float(baseline["median_return_pct"])
        )
        & (grid["median_sharpe"] >= float(baseline["median_sharpe"]))
        & (
            grid["worst_max_drawdown_pct"]
            >= float(baseline["worst_max_drawdown_pct"])
        )
    ]
    plateau_pass = len(robust_neighbors) >= 2

    holdout_end = frame.index[-1]
    holdout_runs = {
        "V35 baseline": run_variant(
            adx_module,
            base,
            replay,
            frame,
            config,
            indicators=indicators,
            apply_original_trend_filter=True,
            adx_window=None,
            adx_threshold=None,
            trade_start=HOLDOUT_START,
            trade_end=holdout_end,
        ),
        "no trend filter": run_variant(
            adx_module,
            base,
            replay,
            frame,
            config,
            indicators=indicators,
            apply_original_trend_filter=False,
            adx_window=None,
            adx_threshold=None,
            trade_start=HOLDOUT_START,
            trade_end=holdout_end,
        ),
        "selected": run_variant(
            adx_module,
            base,
            replay,
            frame,
            config,
            indicators=indicators,
            apply_original_trend_filter=False,
            adx_window=selected_window,
            adx_threshold=selected_threshold,
            trade_start=HOLDOUT_START,
            trade_end=holdout_end,
        ),
    }
    holdout_metrics = {
        name: base.compact_metrics(run)
        for name, run in holdout_runs.items()
    }
    holdout_pass = (
        holdout_metrics["selected"]["return_pct"]
        > holdout_metrics["V35 baseline"]["return_pct"]
        and holdout_metrics["selected"]["max_drawdown_pct"]
        >= holdout_metrics["V35 baseline"]["max_drawdown_pct"]
        and holdout_metrics["selected"]["entries"]
        >= 0.50 * holdout_metrics["V35 baseline"]["entries"]
    )

    recent_windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
    }
    recent_rows: list[dict[str, Any]] = []
    recent_candidates = (
        ("V35 baseline", True, None, None),
        ("no trend filter", False, None, None),
        (
            f"replace ADX{selected_window}>={selected_threshold:g}",
            False,
            selected_window,
            selected_threshold,
        ),
    )
    for window_name, delta in recent_windows.items():
        start = max(frame.index[0], holdout_end - delta)
        for candidate_name, original_filter, adx_window, adx_threshold in (
            recent_candidates
        ):
            run = run_variant(
                adx_module,
                base,
                replay,
                frame,
                config,
                indicators=indicators,
                apply_original_trend_filter=original_filter,
                adx_window=adx_window,
                adx_threshold=adx_threshold,
                trade_start=start,
                trade_end=holdout_end,
            )
            recent_rows.append(
                {
                    "window": window_name,
                    "candidate": candidate_name,
                    "start": start.isoformat(),
                    "end": holdout_end.isoformat(),
                    "fee_rate": config.fee_rate,
                    "slippage_rate": config.slippage_rate,
                    **base.compact_metrics(run),
                }
            )

    full_runs = {
        "V35 baseline": run_variant(
            adx_module,
            base,
            replay,
            frame,
            config,
            indicators=indicators,
            apply_original_trend_filter=True,
            adx_window=None,
            adx_threshold=None,
        ),
        "no trend filter": run_variant(
            adx_module,
            base,
            replay,
            frame,
            config,
            indicators=indicators,
            apply_original_trend_filter=False,
            adx_window=None,
            adx_threshold=None,
        ),
        "selected": run_variant(
            adx_module,
            base,
            replay,
            frame,
            config,
            indicators=indicators,
            apply_original_trend_filter=False,
            adx_window=selected_window,
            adx_threshold=selected_threshold,
        ),
    }
    stress_config = replace(config, fee_rate=0.001, slippage_rate=0.0004)
    stress_runs = {
        "V35 baseline": run_variant(
            adx_module,
            base,
            replay,
            frame,
            stress_config,
            indicators=indicators,
            apply_original_trend_filter=True,
            adx_window=None,
            adx_threshold=None,
        ),
        "no trend filter": run_variant(
            adx_module,
            base,
            replay,
            frame,
            stress_config,
            indicators=indicators,
            apply_original_trend_filter=False,
            adx_window=None,
            adx_threshold=None,
        ),
        "selected": run_variant(
            adx_module,
            base,
            replay,
            frame,
            stress_config,
            indicators=indicators,
            apply_original_trend_filter=False,
            adx_window=selected_window,
            adx_threshold=selected_threshold,
        ),
    }
    final_pass = (
        bool(selected["pre_pass"])
        and bool(selected["filter_contribution_pass"])
        and plateau_pass
        and holdout_pass
    )

    selected_trades = full_runs["selected"].trades.copy()
    if not selected_trades.empty:
        selected_trades.insert(
            0,
            "candidate",
            f"replace ADX{selected_window}>={selected_threshold:g}",
        )
    grid["robust_neighbor_of_selected"] = grid.apply(
        lambda row: adx_module.is_neighbor(
            selected_window,
            selected_threshold,
            int(row["adx_window"]),
            float(row["adx_threshold"]),
        ),
        axis=1,
    )
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategy": (
            "HYPE-Candle-Count-Reversal-V35 with original 24h filter "
            "replaced by ADX/DI"
        ),
        "status": (
            "candidate passed; eligible for V36 registration"
            if final_pass
            else "candidate failed; do not register V36"
        ),
        "data_quality": quality,
        "replacement_contract": {
            "removed": "96-bar return / 5% countertrend entry block",
            "replacement": (
                "ADX below threshold allows both sides; at/above threshold, "
                "+DI>-DI permits long only and -DI>+DI permits short only"
            ),
            "adx_formula": "Wilder-style EWM; alpha=1/window, adjust=False",
            "windows": list(adx_module.ADX_WINDOWS),
            "thresholds": list(adx_module.ADX_THRESHOLDS),
            "no_filter_ablation": True,
        },
        "baseline_parity": {
            "expected": base.CURRENT_BASELINE,
            "actual": canonical_metrics,
            "checks": parity,
        },
        "selection": {
            "selection_data_end": SELECTION_END.isoformat(),
            "holdout_start": HOLDOUT_START.isoformat(),
            "holdout_end": holdout_end.isoformat(),
            "rolling_window_count": len(rolling_windows),
            "selected_adx_window": selected_window,
            "selected_adx_threshold": selected_threshold,
            "selected_pre_holdout": adx_module.json_record(selected),
            "baseline_pre_holdout": adx_module.json_record(baseline),
            "no_filter_pre_holdout": adx_module.json_record(no_filter),
            "robust_neighbor_count": int(len(robust_neighbors)),
            "robust_neighbors": [
                adx_module.json_record(row)
                for _, row in robust_neighbors.iterrows()
            ],
            "plateau_pass": plateau_pass,
            "holdout": holdout_metrics,
            "holdout_pass": holdout_pass,
            "final_pass": final_pass,
        },
        "full_period": {
            name: base.compact_metrics(run)
            for name, run in full_runs.items()
        },
        "binance_cost_stress": {
            name: base.compact_metrics(run)
            for name, run in stress_runs.items()
        },
        "execution": {
            "selection_mode": "signal confirmed on closed bar; next bar open entry",
            "same_entry_bar_stop_take": True,
            "fee_rate_primary": config.fee_rate,
            "slippage_rate_primary": config.slippage_rate,
            "fee_rate_stress": stress_config.fee_rate,
            "slippage_rate_stress": stress_config.slippage_rate,
            "funding": "Binance funding history included",
            "stop_take_trigger": (
                "Binance 15m mark-price high/low; stop first on conflict"
            ),
        },
        "artifacts": {
            "grid": str(GRID_PATH.relative_to(ROOT)),
            "rolling": str(ROLLING_PATH.relative_to(ROOT)),
            "recent": str(RECENT_PATH.relative_to(ROOT)),
            "selected_trades": str(TRADES_PATH.relative_to(ROOT)),
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    grid.to_csv(GRID_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    pd.DataFrame(recent_rows).to_csv(RECENT_PATH, index=False)
    selected_trades.to_csv(TRADES_PATH, index=False)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Wrote {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
