"""回测 V35.3 空头在极端放量时绕过 ADX36 的入场规则。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_2_short_partial_stop_scan as stop_engine
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_3_short_volume_adx_bypass_2026-07-22"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
FREEZE_DATA_END = pd.Timestamp("2026-06-01T03:00:00Z")
CURRENT_EARLY_SIGNAL_BAR = pd.Timestamp("2026-07-22T06:15:00Z")
CURRENT_STANDARD_SIGNAL_BAR = pd.Timestamp("2026-07-22T06:30:00Z")
PRODUCTION_SNAPSHOT = {
    "source": (
        "Read-only hype-trend SQLite kv_state and latest open_success "
        "event queried on 2026-07-22."
    ),
    "strategy_id": "HYPE-EMA-TB-V35.3",
    "state_updated_at": "2026-07-22T07:00:07.188525+00:00",
    "direction": -1,
    "entry_bar": 1983004,
    "entry_price": 58.6326089,
    "entry_atr": 0.32117708333333345,
    "allocation": 3.0,
    "contracts": 451.35,
    "open_success_at": "2026-07-22T07:00:05.122874+00:00",
}


@dataclass(frozen=True, slots=True)
class BypassSpec:
    name: str
    volume_multiple: float | None
    adx_floor: float | None = None

    @property
    def enabled(self) -> bool:
        return self.volume_multiple is not None


SPECS = (
    BypassSpec("v35_3_base", None),
    BypassSpec("short_vol2x_bypass_no_adx", 2.0),
    BypassSpec("short_vol3x_bypass_no_adx", 3.0),
    BypassSpec("short_vol4x_bypass_no_adx", 4.0),
    BypassSpec("short_vol5x_bypass_no_adx", 5.0),
    BypassSpec("short_vol3x_bypass_adx28", 3.0, 28.0),
    BypassSpec("short_vol3x_bypass_adx32", 3.0, 32.0),
    BypassSpec("short_vol3x_bypass_adx34", 3.0, 34.0),
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


def apply_bypass(
    *,
    features: pd.DataFrame,
    spec: BypassSpec,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    result = features.copy()
    original_short = result["short_signal"].fillna(False).astype(bool)
    if not spec.enabled:
        return result, {
            "bypass_signal_bars": 0,
            "new_short_signal_bars": 0,
            "total_short_signal_bars": int(original_short.sum()),
        }

    # volume_surge = volume / MA192 - 1，所以“成交量为均量 3 倍”
    # 对应 volume_surge >= 2.0。
    bypass = (
        result["ema_spread"].lt(0.0)
        & result["volume_surge"].ge(float(spec.volume_multiple) - 1.0)
    )
    if spec.adx_floor is not None:
        bypass &= result["adx"].ge(spec.adx_floor)
    new_short = bypass & ~original_short
    result["short_signal"] = original_short | bypass
    conflict = (
        result["long_signal"].fillna(False).astype(bool)
        & result["short_signal"].fillna(False).astype(bool)
    )
    result.loc[conflict, ["long_signal", "short_signal"]] = False
    return result, {
        "bypass_signal_bars": int(bypass.sum()),
        "new_short_signal_bars": int(new_short.sum()),
        "total_short_signal_bars": int(result["short_signal"].sum()),
        "conflict_bars_removed": int(conflict.sum()),
    }


def full_trade_return(
    trades: pd.DataFrame,
    trade_cost_rate: float,
) -> pd.Series:
    entry_multiplier = 1.0 - trade_cost_rate * trades["allocation"]
    return (1.0 + trades["trade_return"]) * entry_multiplier - 1.0


def closed_trade_metrics(
    trades: pd.DataFrame,
    trade_cost_rate: float,
) -> dict[str, Any]:
    if trades.empty:
        return {
            "return_pct": 0.0,
            "trades": 0,
            "wins": 0,
            "win_rate_pct": 0.0,
            "exit_counts": {},
        }
    returns = full_trade_return(trades, trade_cost_rate)
    wins = int(returns.gt(0.0).sum())
    return {
        "return_pct": round(
            float((1.0 + returns).prod() - 1.0) * 100.0,
            4,
        ),
        "trades": int(len(trades)),
        "wins": wins,
        "win_rate_pct": round(wins / len(trades) * 100.0, 2),
        "exit_counts": {
            str(key): int(value)
            for key, value in trades["exit_reason"].value_counts().items()
        },
    }


def annotate_trades(
    *,
    run: base.RunResult,
    features: pd.DataFrame,
    baseline_features: pd.DataFrame,
    config: base.V35Config,
    spec: BypassSpec,
) -> pd.DataFrame:
    trades = run.trades.copy()
    if trades.empty:
        return trades
    signal_bars = trades["entry_bar"].astype(int) - config.entry_delay_bars
    signal_rows = features.iloc[signal_bars]
    baseline_rows = baseline_features.iloc[signal_bars]
    trades["signal_ts"] = signal_rows.index.to_numpy()
    trades["signal_adx28"] = signal_rows["adx"].to_numpy()
    trades["signal_volume_surge"] = signal_rows[
        "volume_surge"
    ].to_numpy()
    trades["signal_volume_multiple"] = (
        trades["signal_volume_surge"] + 1.0
    )
    trades["baseline_short_signal"] = baseline_rows[
        "short_signal"
    ].to_numpy()
    trades["bypass_entry"] = (
        trades["direction"].eq(-1)
        & ~trades["baseline_short_signal"].astype(bool)
    )
    trades["variant"] = spec.name
    return trades


def path_comparison(
    candidate: pd.DataFrame,
    baseline: pd.DataFrame,
) -> dict[str, Any]:
    keys = ["entry_ts", "direction"]
    matched = baseline[keys].merge(
        candidate[keys],
        on=keys,
        how="inner",
    )
    baseline_only = baseline.merge(
        candidate[keys],
        on=keys,
        how="left",
        indicator=True,
    ).loc[lambda frame: frame["_merge"].eq("left_only")]
    candidate_only = candidate.merge(
        baseline[keys],
        on=keys,
        how="left",
        indicator=True,
    ).loc[lambda frame: frame["_merge"].eq("left_only")]
    bypass_entries = candidate.loc[candidate["bypass_entry"]].copy()
    return {
        "exact_entry_matches": int(len(matched)),
        "baseline_only_entries": int(len(baseline_only)),
        "candidate_only_entries": int(len(candidate_only)),
        "bypass_entries": int(len(bypass_entries)),
        "bypass_entry_metrics": closed_trade_metrics(
            bypass_entries,
            base.V35Config().trade_cost_rate,
        ),
        "bypass_entry_details": json.loads(
            bypass_entries[
                [
                    "entry_ts",
                    "exit_ts",
                    "direction",
                    "signal_adx28",
                    "signal_volume_multiple",
                    "exit_reason",
                    "trade_return",
                ]
            ].to_json(orient="records", date_format="iso")
        ),
    }


def current_signal_audit(
    *,
    features: pd.DataFrame,
    variants: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    def row(ts: pd.Timestamp) -> dict[str, Any]:
        values = features.loc[ts]
        return {
            "source_bar_ts": ts.isoformat(),
            "ema_spread_pct": round(
                float(values["ema_spread"]) * 100.0,
                4,
            ),
            "adx28": round(float(values["adx"]), 4),
            "volume_surge_pct": round(
                float(values["volume_surge"]) * 100.0,
                2,
            ),
            "volume_multiple": round(
                float(values["volume_surge"]) + 1.0,
                4,
            ),
            "v35_3_short_signal": bool(
                variants["v35_3_base"].loc[ts, "short_signal"]
            ),
            "vol3x_bypass_short_signal": bool(
                variants["short_vol3x_bypass_no_adx"].loc[
                    ts,
                    "short_signal",
                ]
            ),
            "planned_k2_open_ts": (
                ts + pd.Timedelta(minutes=30)
            ).isoformat(),
        }

    base_short = variants["v35_3_base"]["short_signal"].astype(bool)
    primary_short = variants[
        "short_vol3x_bypass_no_adx"
    ]["short_signal"].astype(bool)
    current_window = (
        features.index >= pd.Timestamp("2026-07-22T04:00:00Z")
    )
    new_primary = features.loc[
        current_window & primary_short & ~base_short,
        ["ema_spread", "adx", "volume_surge"],
    ].copy()
    new_primary["ema_spread_pct"] = new_primary["ema_spread"] * 100.0
    new_primary["volume_multiple"] = (
        new_primary["volume_surge"] + 1.0
    )
    new_primary["planned_k2_open_ts"] = (
        new_primary.index + pd.Timedelta(minutes=30)
    )
    return {
        "early_bar": row(CURRENT_EARLY_SIGNAL_BAR),
        "standard_bar": row(CURRENT_STANDARD_SIGNAL_BAR),
        "new_primary_signal_bars_since_04_00_utc": json.loads(
            new_primary[
                [
                    "ema_spread_pct",
                    "adx",
                    "volume_multiple",
                    "planned_k2_open_ts",
                ]
            ].to_json(orient="table", date_format="iso")
        )["data"],
        "timing_note": (
            "Bar timestamps are UTC opens. Beijing 14:15-14:30 is "
            "2026-07-22 06:15 UTC; its K2 open is 06:45 UTC. The "
            "standard 06:30 UTC signal has K2 open at 07:00 UTC."
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)
    config = base.V35Config()
    raw_features = base.build_features(frame, config)
    baseline_features = signal_engine.build_signals(
        raw_features,
        config,
        signal_engine.SignalFlags(short_use_h1_ema=False),
    )

    runs: list[base.RunResult] = []
    audits: dict[str, Any] = {}
    variant_features: dict[str, pd.DataFrame] = {}
    trade_frames: list[pd.DataFrame] = []
    for spec in SPECS:
        features, signal_audit = apply_bypass(
            features=baseline_features,
            spec=spec,
        )
        run, execution_audit = stop_engine.run_backtest(
            spec=v35_3_spec(spec.name),
            frame=frame,
            funding=funding,
            features=features,
            config=config,
        )
        annotated = annotate_trades(
            run=run,
            features=features,
            baseline_features=baseline_features,
            config=config,
            spec=spec,
        )
        run = base.RunResult(
            name=run.name,
            metrics=run.metrics,
            slices=run.slices,
            trades=annotated,
            equity_curve=run.equity_curve,
            period_returns=run.period_returns,
            open_position=run.open_position,
        )
        runs.append(run)
        variant_features[spec.name] = features
        audits[spec.name] = {
            "signals": signal_audit,
            "execution": execution_audit,
        }
        trade_frames.append(annotated)

    baseline = runs[0]
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35.3",
        "run_date": "2026-07-22",
        "status": "diagnostic_only_not_registered_not_promoted",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
        },
        "assumptions": {
            "market": "Binance USD-M HYPEUSDT perpetual 15m",
            "base": (
                "V35.3: V35.1 entry/sizing, long TP5/SL6.75, short "
                "TP5/SL5.7 plus MFE4.4ATR reduce 75%, cooldown0."
            ),
            "primary_rule": (
                "Keep the normal short ADX28>=36 path. Additionally, when "
                "ema_spread<0 and volume/MA192>=3.0, allow short without "
                "checking ADX. volume_surge threshold is therefore 2.0."
            ),
            "execution": (
                "K0 close signal, skip full K1, enter K2 open; entry ATR "
                "comes from completed K1; intrabar stop-first."
            ),
            "costs": (
                "0.00085 per filled allocation on entry/partial/final "
                "exit plus Binance funding."
            ),
            "selection": (
                "3x/no-ADX is user-specified primary. 2x/4x/5x and "
                "ADX floors 28/32/34 are sensitivity diagnostics. "
                "Recent slices are audit-only."
            ),
        },
        "config": asdict(config),
        "variants": [asdict(spec) for spec in SPECS],
        "audits": audits,
        "current_signal": current_signal_audit(
            features=raw_features,
            variants=variant_features,
        ),
        "production_snapshot": PRODUCTION_SNAPSHOT,
        "runs": [],
    }
    for spec, run in zip(SPECS, runs, strict=True):
        post_freeze = run.trades.loc[
            pd.to_datetime(run.trades["entry_ts"], utc=True).gt(
                FREEZE_DATA_END
            )
        ]
        summary["runs"].append(
            {
                "spec": asdict(spec),
                "metrics": run.metrics,
                "standard_slices": run.slices,
                "post_freeze_closed_trade_metrics": closed_trade_metrics(
                    post_freeze,
                    config.trade_cost_rate,
                ),
                "open_position": run.open_position,
                "comparison_to_v35_3": (
                    None
                    if run is baseline
                    else {
                        "return_delta_pp": round(
                            run.metrics["return_pct"]
                            - baseline.metrics["return_pct"],
                            2,
                        ),
                        "max_drawdown_delta_pp": round(
                            run.metrics["max_drawdown_pct"]
                            - baseline.metrics["max_drawdown_pct"],
                            2,
                        ),
                        "sharpe_delta": round(
                            run.metrics["sharpe"]
                            - baseline.metrics["sharpe"],
                            2,
                        ),
                        "trade_delta": int(
                            run.metrics["trades"]
                            - baseline.metrics["trades"]
                        ),
                    }
                ),
                "path_audit": (
                    None
                    if run is baseline
                    else path_comparison(run.trades, baseline.trades)
                ),
            }
        )

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

    print(
        f"data {quality['start']} ~ {quality['end']} "
        f"quality_gate={quality_gate['passed']}"
    )
    for run in runs:
        metrics = run.metrics
        print(
            f"{run.name:>30} ret {metrics['return_pct']:>9.2f}% "
            f"dd {metrics['max_drawdown_pct']:>7.2f}% "
            f"sh {metrics['sharpe']:>5.2f} "
            f"n {metrics['trades']:>3} "
            f"win {metrics['win_rate_pct']:>6.2f}%"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
