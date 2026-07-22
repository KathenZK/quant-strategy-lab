"""回测 V35.3 的 4h RSI6 方向极值禁入规则。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_2_short_partial_stop_scan as stop_engine
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as rsi_engine
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_3_h4_rsi6_directional_filter_2026-07-22"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
LATEST_LOSS_ENTRY_TS = pd.Timestamp("2026-07-21T05:45:00Z")


@dataclass(frozen=True, slots=True)
class FilterSpec:
    name: str
    long_upper: float | None = None
    short_lower: float | None = None


FILTERS = (
    FilterSpec("v35_3_base"),
    FilterSpec("long_block_gt80", long_upper=80.0),
    FilterSpec("short_block_lt20", short_lower=20.0),
    FilterSpec(
        "directional_20_80",
        long_upper=80.0,
        short_lower=20.0,
    ),
    FilterSpec(
        "directional_10_90",
        long_upper=90.0,
        short_lower=10.0,
    ),
    FilterSpec(
        "directional_30_70",
        long_upper=70.0,
        short_lower=30.0,
    ),
)


def filtered_features(
    *,
    features: pd.DataFrame,
    entry_rsi6: pd.Series,
    config: base.V35Config,
    spec: FilterSpec,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    result = features.copy()
    entry_rsi_at_signal = entry_rsi6.shift(-config.entry_delay_bars)
    original_long = result["long_signal"].fillna(False).astype(bool)
    original_short = result["short_signal"].fillna(False).astype(bool)
    long_allowed = pd.Series(True, index=result.index)
    short_allowed = pd.Series(True, index=result.index)

    if spec.long_upper is not None:
        # 用户规则是 RSI6 > 80 禁多，因此边界 80 本身仍允许。
        long_allowed = entry_rsi_at_signal.le(spec.long_upper)
    if spec.short_lower is not None:
        # 用户规则是 RSI6 < 20 禁空，因此边界 20 本身仍允许。
        short_allowed = entry_rsi_at_signal.ge(spec.short_lower)

    result["long_signal"] = original_long & long_allowed.fillna(False)
    result["short_signal"] = original_short & short_allowed.fillna(False)
    return result, {
        "raw_long_signal_bars": int(original_long.sum()),
        "raw_short_signal_bars": int(original_short.sum()),
        "blocked_long_signal_bars": int(
            (original_long & ~long_allowed.fillna(False)).sum()
        ),
        "blocked_short_signal_bars": int(
            (original_short & ~short_allowed.fillna(False)).sum()
        ),
        "remaining_long_signal_bars": int(
            result["long_signal"].sum()
        ),
        "remaining_short_signal_bars": int(
            result["short_signal"].sum()
        ),
    }


def v35_3_spec(name: str) -> stop_engine.StopPartialSpec:
    return stop_engine.StopPartialSpec(
        name=name,
        trigger_atr=None,
        fraction_of_remaining=1.0,
        long_trigger_atr=6.75,
        short_trigger_atr=5.70,
        directional_stop_replaces_hard_stop=True,
    )


def annotate_trades(
    run: base.RunResult,
    entry_rsi6: pd.Series,
) -> pd.DataFrame:
    trades = run.trades.copy()
    if trades.empty:
        trades["entry_h4_rsi6"] = pd.Series(dtype="float64")
        return trades
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["entry_h4_rsi6"] = entry_rsi6.reindex(
        pd.DatetimeIndex(entry_ts)
    ).to_numpy()
    return trades


def comparison(
    run: base.RunResult,
    baseline: base.RunResult,
) -> dict[str, Any]:
    candidate_equity = 1.0 + run.metrics["return_pct"] / 100.0
    baseline_equity = 1.0 + baseline.metrics["return_pct"] / 100.0
    baseline_slices = {
        row["window"]: row for row in baseline.slices
    }
    return {
        "final_equity_retained_pct": round(
            candidate_equity / baseline_equity * 100.0,
            2,
        ),
        "return_delta_pp": round(
            run.metrics["return_pct"] - baseline.metrics["return_pct"],
            2,
        ),
        "max_drawdown_delta_pp": round(
            run.metrics["max_drawdown_pct"]
            - baseline.metrics["max_drawdown_pct"],
            2,
        ),
        "sharpe_delta": round(
            run.metrics["sharpe"] - baseline.metrics["sharpe"],
            2,
        ),
        "trade_delta": int(
            run.metrics["trades"] - baseline.metrics["trades"]
        ),
        "slice_return_delta_pp": {
            row["window"]: round(
                row["return_pct"]
                - baseline_slices[row["window"]]["return_pct"],
                2,
            )
            for row in run.slices
        },
    }


def matched_entry_audit(
    run: base.RunResult,
    baseline: base.RunResult,
) -> dict[str, Any]:
    keys = ["entry_ts", "direction"]
    left = baseline.trades[keys + ["exit_reason", "trade_return"]].rename(
        columns={
            "exit_reason": "baseline_exit_reason",
            "trade_return": "baseline_trade_return",
        }
    )
    right = run.trades[keys + ["exit_reason", "trade_return"]].rename(
        columns={
            "exit_reason": "candidate_exit_reason",
            "trade_return": "candidate_trade_return",
        }
    )
    matched = left.merge(right, on=keys, how="inner")
    return {
        "exact_entry_matches": int(len(matched)),
        "baseline_only_entries": int(
            len(baseline.trades) - len(matched)
        ),
        "candidate_only_entries": int(len(run.trades) - len(matched)),
        "same_exit_reason": int(
            matched["baseline_exit_reason"]
            .eq(matched["candidate_exit_reason"])
            .sum()
        ),
        "sum_matched_trade_return_delta_pp": round(
            float(
                (
                    matched["candidate_trade_return"]
                    - matched["baseline_trade_return"]
                ).sum()
            )
            * 100.0,
            4,
        ),
    }


def blocked_baseline_trade_audit(
    baseline: base.RunResult,
    entry_rsi6: pd.Series,
) -> dict[str, Any]:
    trades = annotate_trades(baseline, entry_rsi6)
    blocked = trades.loc[
        (
            trades["direction"].eq(1)
            & trades["entry_h4_rsi6"].gt(80.0)
        )
        | (
            trades["direction"].eq(-1)
            & trades["entry_h4_rsi6"].lt(20.0)
        )
    ].copy()
    if blocked.empty:
        return {
            "count": 0,
            "long": 0,
            "short": 0,
            "wins": 0,
            "exit_counts": {},
            "sum_trade_return_pct": 0.0,
            "side_stats": {},
            "details": [],
        }

    side_stats: dict[str, Any] = {}
    for label, direction in (("long", 1), ("short", -1)):
        side = blocked.loc[blocked["direction"].eq(direction)]
        side_stats[label] = {
            "count": int(len(side)),
            "wins": int(side["trade_return"].gt(0.0).sum()),
            "exit_counts": {
                str(key): int(value)
                for key, value in side["exit_reason"].value_counts().items()
            },
            "sum_trade_return_pct": round(
                float(side["trade_return"].sum()) * 100.0,
                4,
            ),
        }
    fields = [
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_h4_rsi6",
        "exit_reason",
        "mfe_atr",
        "trade_return",
        "profit_partial_taken",
    ]
    details = blocked[fields].copy()
    details["trade_return_pct"] = details["trade_return"] * 100.0
    details = details.drop(columns="trade_return")
    return {
        "count": int(len(blocked)),
        "long": int(blocked["direction"].eq(1).sum()),
        "short": int(blocked["direction"].eq(-1).sum()),
        "wins": int(blocked["trade_return"].gt(0.0).sum()),
        "exit_counts": {
            str(key): int(value)
            for key, value in blocked["exit_reason"].value_counts().items()
        },
        "sum_trade_return_pct": round(
            float(blocked["trade_return"].sum()) * 100.0,
            4,
        ),
        "side_stats": side_stats,
        "details": details.to_dict(orient="records"),
    }


def latest_loss_trade(run: base.RunResult) -> dict[str, Any] | None:
    if run.trades.empty:
        return None
    entries = pd.to_datetime(run.trades["entry_ts"], utc=True)
    rows = run.trades.loc[
        entries.eq(LATEST_LOSS_ENTRY_TS)
        & run.trades["direction"].eq(1)
    ]
    if rows.empty:
        return None
    row = rows.iloc[0]
    return {
        "entry_ts": row["entry_ts"],
        "exit_ts": row["exit_ts"],
        "entry_price": float(row["entry_price"]),
        "exit_price": float(row["exit_price"]),
        "entry_h4_rsi6": float(row["entry_h4_rsi6"]),
        "exit_reason": row["exit_reason"],
        "trade_return_pct": round(
            float(row["trade_return"]) * 100.0,
            4,
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = rsi_engine.load_data(warehouse)
    quality_gate = rsi_engine.quality_gate(quality)
    config = base.V35Config()
    flags = signal_engine.SignalFlags(short_use_h1_ema=False)
    features = signal_engine.build_signals(
        base.build_features(frame, config),
        config,
        flags,
    )
    entry_rsi6 = rsi_engine.entry_time_h4_rsi6(frame)

    runs: list[base.RunResult] = []
    audits: dict[str, Any] = {}
    trade_frames: list[pd.DataFrame] = []
    for filter_spec in FILTERS:
        candidate_features, signal_audit = filtered_features(
            features=features,
            entry_rsi6=entry_rsi6,
            config=config,
            spec=filter_spec,
        )
        run, execution_audit = stop_engine.run_backtest(
            spec=v35_3_spec(filter_spec.name),
            frame=frame,
            funding=funding,
            features=candidate_features,
            config=config,
        )
        annotated = annotate_trades(run, entry_rsi6)
        run = replace(run, trades=annotated)
        runs.append(run)
        audits[filter_spec.name] = {
            "signals": signal_audit,
            "execution": execution_audit,
        }
        trade_frames.append(
            annotated.assign(variant=filter_spec.name)
        )

    baseline = runs[0]
    canonical, _ = stop_engine.run_backtest(
        spec=v35_3_spec("canonical_v35_3"),
        frame=frame,
        funding=funding,
        features=features,
        config=config,
    )
    parity_diff = float(
        (baseline.equity_curve - canonical.equity_curve).abs().max()
    )
    if parity_diff > 1e-12:
        raise RuntimeError(f"V35.3 baseline parity failed: {parity_diff}")

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35.3",
        "audit_id": "4h RSI6 directional extreme entry filter",
        "run_date": "2026-07-22",
        "status": "diagnostic_only_not_registered_not_promoted",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "canonical_v35_3_max_equity_diff": parity_diff,
        },
        "assumptions": {
            "market": "Binance USD-M Futures HYPEUSDT perpetual 15m",
            "v35_3": (
                "V35.1 entries and sizing; long TP5/SL6.75; short "
                "TP5/SL5.7 plus MFE4.4ATR reduce 75%; cooldown0."
            ),
            "filter": (
                "At K2 open, block long only when latest fully closed "
                "4h Wilder RSI6 > upper; block short only when RSI6 < lower."
            ),
            "alignment": (
                "4h resample label=left/closed=left, RSI shift(1), then "
                "forward-fill to 15m; no incomplete 4h candle is used."
            ),
            "costs": (
                "0.00085 per filled allocation on entry, partial and "
                "final exit; Binance funding applies."
            ),
            "selection": (
                "20/80 is the user-specified primary rule; 10/90 and "
                "30/70 are sensitivity diagnostics. Standard recent "
                "slices are audit-only, not independent OOS."
            ),
        },
        "config": asdict(config),
        "signal_flags": asdict(flags),
        "filters": [asdict(spec) for spec in FILTERS],
        "audits": audits,
        "blocked_v35_3_baseline_trades_20_80": (
            blocked_baseline_trade_audit(baseline, entry_rsi6)
        ),
        "runs": [
            {
                "filter": asdict(filter_spec),
                "metrics": run.metrics,
                "standard_slices": run.slices,
                "open_position": run.open_position,
                "comparison_to_v35_3": (
                    None
                    if run is baseline
                    else comparison(run, baseline)
                ),
                "matched_entry_audit": (
                    None
                    if run is baseline
                    else matched_entry_audit(run, baseline)
                ),
                "latest_loss_trade": latest_loss_trade(run),
            }
            for filter_spec, run in zip(FILTERS, runs, strict=True)
        ],
    }
    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    pd.concat(trade_frames, ignore_index=True).to_csv(
        TRADES_PATH,
        index=False,
    )
    pd.concat(
        [run.equity_curve.rename(run.name) for run in runs],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(
        f"data: {quality['start']} ~ {quality['end']} "
        f"rows={quality['rows']} quality_gate={quality_gate['passed']} "
        f"parity={parity_diff:.2e}"
    )
    for run in runs:
        metrics = run.metrics
        latest = latest_loss_trade(run)
        print(
            f"{run.name:>22} ret {metrics['return_pct']:>9.2f}% "
            f"dd {metrics['max_drawdown_pct']:>7.2f}% "
            f"sh {metrics['sharpe']:>5.2f} "
            f"n {metrics['trades']:>3} "
            f"win {metrics['win_rate_pct']:>6.2f}% "
            f"latest={'blocked' if latest is None else latest['trade_return_pct']}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
