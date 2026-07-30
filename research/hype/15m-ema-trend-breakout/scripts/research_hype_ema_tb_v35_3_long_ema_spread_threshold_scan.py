"""扫描 V35.3 多头 ema_spread 最低门槛（弱多过滤敏感性）。

只提高多头 `ema_spread >= threshold`；空头、sizing、非对称止损、
空头 4.4ATR/75% 分批与退出状态机全部保持 V35.3。
同时标注实盘弱多候选（7/15、7/21）是否会被各门槛挡住。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_2_short_partial_stop_scan as stop_engine
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_3_long_ema_spread_threshold_scan_2026-07-29"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
FILTERED_PATH = ARTIFACT_DIR / f"{OUT_STEM}_filtered_longs.csv"

# 0.0 = V35.3 baseline (ema_spread > 0)
THRESHOLDS = (0.0, 0.005, 0.008, 0.010, 0.012, 0.015, 0.020)

# Live weak-long candidates from the post-freeze diagnosis.
LIVE_WEAK_LONG_SIGNAL_BARS = (
    {
        "label": "2026-07-15_long",
        "signal_ts": "2026-07-15 12:30:00+00:00",
        "note": "research K0 for 13:00 entry; ema_spread~0.00648 vol~0.65 MFE0.30",
    },
    {
        "label": "2026-07-21_long",
        "signal_ts": "2026-07-21 05:15:00+00:00",
        "note": "live loss review signal bar; ema_spread~0.00584 vol~1.53 MFE1.27",
    },
)


def v35_3_spec(name: str) -> stop_engine.StopPartialSpec:
    return stop_engine.StopPartialSpec(
        name=name,
        trigger_atr=None,
        fraction_of_remaining=1.0,
        long_trigger_atr=6.75,
        short_trigger_atr=5.70,
        directional_stop_replaces_hard_stop=True,
    )


def apply_long_ema_spread_min(
    features: pd.DataFrame,
    min_spread: float,
) -> pd.DataFrame:
    out = features.copy()
    if min_spread <= 0.0:
        return out
    long_signal = out["long_signal"] & out["ema_spread"].ge(min_spread)
    short_signal = out["short_signal"]
    conflict = long_signal & short_signal
    out["long_signal"] = long_signal & ~conflict
    out["short_signal"] = short_signal & ~conflict
    return out


def baseline_long_entries(
    features: pd.DataFrame,
    frame: pd.DataFrame,
    config: base.V35Config,
) -> pd.DataFrame:
    """Approximate K2 entries implied by baseline long signals (ignores occupancy)."""
    rows: list[dict[str, Any]] = []
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    for i in range(start, len(frame)):
        signal_i = i - config.entry_delay_bars
        if not bool(features["long_signal"].iloc[signal_i]):
            continue
        if bool(features["short_signal"].iloc[signal_i]):
            continue
        rows.append(
            {
                "entry_ts": str(frame.index[i]),
                "signal_ts": str(frame.index[signal_i]),
                "ema_spread": float(features["ema_spread"].iloc[signal_i]),
                "adx28": float(features["adx"].iloc[signal_i]),
                "volume_surge": float(features["volume_surge"].iloc[signal_i]),
            }
        )
    return pd.DataFrame(rows)


def resolve_live_candidates(
    features: pd.DataFrame,
    frame: pd.DataFrame,
    config: base.V35Config,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in LIVE_WEAK_LONG_SIGNAL_BARS:
        target = pd.Timestamp(item["signal_ts"])
        if target in frame.index:
            signal_i = int(frame.index.get_loc(target))
        else:
            # nearest prior bar
            idx = frame.index.get_indexer([target], method="pad")[0]
            signal_i = int(idx)
        entry_i = signal_i + config.entry_delay_bars
        out.append(
            {
                "label": item["label"],
                "requested_signal_ts": item["signal_ts"],
                "resolved_signal_ts": str(frame.index[signal_i]),
                "implied_entry_ts": (
                    str(frame.index[entry_i])
                    if entry_i < len(frame)
                    else None
                ),
                "ema_spread": float(features["ema_spread"].iloc[signal_i]),
                "adx28": float(features["adx"].iloc[signal_i]),
                "volume_surge": float(features["volume_surge"].iloc[signal_i]),
                "baseline_long_signal": bool(
                    features["long_signal"].iloc[signal_i]
                ),
                "note": item["note"],
            }
        )
    return out


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)
    config = base.V35Config()
    flags = signal_engine.SignalFlags(short_use_h1_ema=False)
    base_features = signal_engine.build_signals(
        base.build_features(frame, config),
        config,
        flags,
    )
    live_candidates = resolve_live_candidates(base_features, frame, config)
    signal_universe = baseline_long_entries(base_features, frame, config)

    outputs: list[tuple[float, Any, dict[str, Any]]] = []
    filtered_rows: list[dict[str, Any]] = []

    for threshold in THRESHOLDS:
        features = apply_long_ema_spread_min(base_features, threshold)
        run, audit = stop_engine.run_backtest(
            spec=v35_3_spec(f"long_spread_{threshold:g}"),
            frame=frame,
            funding=funding,
            features=features,
            config=config,
        )
        # Which baseline long signals disappear at this threshold?
        if threshold > 0 and not signal_universe.empty:
            blocked = signal_universe[
                signal_universe["ema_spread"] < threshold
            ]
            for _, row in blocked.iterrows():
                filtered_rows.append(
                    {
                        "threshold": threshold,
                        **row.to_dict(),
                    }
                )
        live_hit = []
        for cand in live_candidates:
            blocked = threshold > 0 and cand["ema_spread"] < threshold
            live_hit.append(
                {
                    "label": cand["label"],
                    "ema_spread": cand["ema_spread"],
                    "blocked_by_threshold": blocked,
                    "would_remain_long_signal": (
                        cand["baseline_long_signal"] and not blocked
                    ),
                }
            )
        outputs.append(
            (
                threshold,
                run,
                {
                    "audit": audit,
                    "live_candidate_hits": live_hit,
                    "baseline_long_signals_blocked": int(
                        (signal_universe["ema_spread"] < threshold).sum()
                        if threshold > 0 and not signal_universe.empty
                        else 0
                    ),
                    "baseline_long_signals_total": int(len(signal_universe)),
                },
            )
        )

    baseline = next(run for threshold, run, _ in outputs if threshold == 0.0)
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35.3",
        "audit_id": "V35.3 long ema_spread minimum threshold scan",
        "run_date": "2026-07-29",
        "status": "diagnostic_only_v35_3_unchanged",
        "data_quality": quality,
        "gates": {"data_quality": quality_gate},
        "assumptions": {
            "only_change": (
                "Long entry requires ema_spread >= threshold "
                "(baseline threshold 0.0 keeps ema_spread > 0)."
            ),
            "thresholds": list(THRESHOLDS),
            "unchanged": (
                "V35.3 shorts, sizing, long SL6.75, short SL5.7, "
                "short MFE4.4 reduce 75%, ADX/vol/1h filters, exits."
            ),
            "costs": (
                "0.00085 per filled allocation; Binance funding on "
                "remaining allocation."
            ),
            "selection": (
                "Full window in-sample sensitivity; standard slices "
                "are audit-only."
            ),
            "live_candidates": live_candidates,
        },
        "runs": [
            {
                "threshold": threshold,
                "metrics": run.metrics,
                "standard_slices": run.slices,
                "open_position": run.open_position,
                "extra": extra,
                "comparison_to_baseline": (
                    None
                    if threshold == 0.0
                    else stop_engine.comparison(run, baseline)
                ),
            }
            for threshold, run, extra in outputs
        ],
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    pd.concat(
        [
            run.trades.assign(long_ema_spread_min=threshold)
            for threshold, run, _ in outputs
        ],
        ignore_index=True,
    ).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [run.equity_curve.rename(run.name) for _, run, _ in outputs],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")
    pd.DataFrame(filtered_rows).to_csv(FILTERED_PATH, index=False)

    print(
        f"data: {quality['start']} ~ {quality['end']} "
        f"rows={quality['rows']} quality_gate={quality_gate['passed']}"
    )
    print("live weak-long candidates:")
    for cand in live_candidates:
        print(
            f"  {cand['label']}: spread={cand['ema_spread']:.6f} "
            f"adx={cand['adx28']:.2f} vol={cand['volume_surge']:.3f} "
            f"long_signal={cand['baseline_long_signal']} "
            f"signal={cand['resolved_signal_ts']}"
        )
    print(
        f"{'thr':>8} {'return%':>10} {'maxDD%':>8} {'sharpe':>7} "
        f"{'n':>5} {'win%':>7} {'longs':>6} {'blocked':>8}"
    )
    for threshold, run, extra in outputs:
        m = run.metrics
        print(
            f"{threshold:>8.3f} {m['return_pct']:>10.2f} "
            f"{m['max_drawdown_pct']:>8.2f} {m['sharpe']:>7.2f} "
            f"{m['trades']:>5} {m['win_rate_pct']:>7.2f} "
            f"{m['long_trades']:>6} "
            f"{extra['baseline_long_signals_blocked']:>8}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
