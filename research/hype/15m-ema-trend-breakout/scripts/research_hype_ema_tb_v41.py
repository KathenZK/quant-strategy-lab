"""登记 HYPE-EMA-TB-V41：V40 空头风险预算回退到 V35。

V41 = V40 with short_target_atr_pct 0.022 -> 0.018。
保留 cooldown1 与移除空头 1h EMA 确认，其余规则不变。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as ab
import research_hype_ema_tb_v35_cooldown4 as cooldown
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v41_2026-07-20"
FLAGS = ab.SignalFlags(short_use_h1_ema=False)


@dataclass(frozen=True, slots=True)
class V41Spec:
    name: str
    config: base.V35Config
    flags: ab.SignalFlags
    cooldown_bars: int
    note: str


def specs() -> tuple[V41Spec, ...]:
    v35 = base.V35Config()
    return (
        V41Spec(
            name="v35_reference",
            config=v35,
            flags=ab.SignalFlags(),
            cooldown_bars=0,
            note="V35 reference: no cooldown, short h1 EMA confirmation retained.",
        ),
        V41Spec(
            name="v40_reference",
            config=replace(v35, short_target_atr_pct=0.022),
            flags=FLAGS,
            cooldown_bars=1,
            note="V40: short target 0.022, cooldown1, short h1 EMA confirmation removed.",
        ),
        V41Spec(
            name="v41",
            config=replace(v35, short_target_atr_pct=0.018),
            flags=FLAGS,
            cooldown_bars=1,
            note="V41: V40 short target reverted to V35 0.018.",
        ),
    )


def trade_signature(run: base.RunResult) -> list[tuple[Any, ...]]:
    if run.trades.empty:
        return []
    columns = ("entry_ts", "exit_ts", "direction", "exit_reason")
    return [
        tuple(row[column] for column in columns)
        for row in run.trades.to_dict(orient="records")
    ]


def summarize(run: base.RunResult) -> dict[str, Any]:
    return {
        "name": run.name,
        "metrics": run.metrics,
        "slices": run.slices,
        "d90": ab.window_stats(run, 90),
        "long_side": ab.side_stats(run, 1),
        "short_side": ab.side_stats(run, -1),
        "risk": risk_stats(run.trades),
        "open_position": run.open_position,
    }


def risk_stats(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {"n": 0}
    atr_pct = trades["entry_atr"] / trades["entry_price"]
    sl_risk = trades["allocation"] * 7.0 * atr_pct
    tp_gain = trades["allocation"] * 5.0 * atr_pct
    return {
        "n": int(len(trades)),
        "alloc_median": float(trades["allocation"].median()),
        "alloc_p90": float(trades["allocation"].quantile(0.9)),
        "alloc_max": float(trades["allocation"].max()),
        "alloc_ge_3_share": float((trades["allocation"] >= 2.999).mean()),
        "sl_risk_pct_median": float(sl_risk.median() * 100.0),
        "sl_risk_pct_p90": float(sl_risk.quantile(0.9) * 100.0),
        "sl_risk_pct_max": float(sl_risk.max() * 100.0),
        "tp_gain_pct_median": float(tp_gain.median() * 100.0),
        "sl_over_tp_median": float((sl_risk / tp_gain).median()),
    }


def print_row(row: dict[str, Any]) -> None:
    metrics = row["metrics"]
    risk = row["risk"]
    print(
        f"{row['name']:>22} | full {metrics['return_pct']:>9.2f}% "
        f"dd {metrics['max_drawdown_pct']:>7.2f}% "
        f"sh {metrics['sharpe']:>5.2f} n {metrics['trades']:>3} "
        f"win {metrics['win_rate_pct']:>6.2f}% "
        f"| SL risk med/p90 {risk['sl_risk_pct_median']:>5.2f}/"
        f"{risk['sl_risk_pct_p90']:>5.2f}% "
        f"| exits {metrics['exit_counts']}"
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = base.load_data(warehouse)

    runs: list[base.RunResult] = []
    spec_rows = specs()
    for spec in spec_rows:
        features = ab.build_signals(
            base.build_features(frame, spec.config),
            spec.config,
            spec.flags,
        )
        run = cooldown.run_backtest(
            cooldown.RunSpec(
                name=spec.name,
                cooldown_bars=spec.cooldown_bars,
                use_rsi10_90=False,
            ),
            frame,
            funding,
            features,
            spec.config,
        )
        runs.append(run)
        print_row(summarize(run))

    v35_run, v40_run, v41_run = runs
    signatures_equal = trade_signature(v40_run) == trade_signature(v41_run)
    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "strategy_id": "HYPE-EMA-TB-V41",
        "status": "registered / not promoted / not live-ready",
        "definition": {
            "base": "HYPE-EMA-TB-V40",
            "only_change": "short_target_atr_pct 0.022 -> 0.018",
            "retained": [
                "cooldown_bars=1",
                "short h1 EMA confirmation removed",
                "long_target_atr_pct=0.020",
                "max_allocation=3.0",
                "TP5/SL7",
                "ADX22 delayed3",
                "disable indicator exit after MFE1.5",
                "max_hold_bars=384",
            ],
        },
        "data_quality": quality,
        "cost_model": (
            "Binance USD-M perp, 0.00085 per fill "
            "(fee + 4bps adverse slippage combined), funding included."
        ),
        "execution": (
            "K0 close signal, skip K1, K2 open entry; entry ATR from completed K1; "
            "cooldown1; TP/SL intrabar stop-first."
        ),
        "trade_path_audit": {
            "v40_v41_signatures_equal": signatures_equal,
            "signature_fields": [
                "entry_ts",
                "exit_ts",
                "direction",
                "exit_reason",
            ],
            "interpretation": (
                "Expected true because the only change is short allocation sizing."
            ),
        },
        "specs": [asdict(item) for item in spec_rows],
        "rows": [summarize(run) for run in runs],
        "deltas": {
            "v41_vs_v40": {
                "return_pct": round(
                    v41_run.metrics["return_pct"] - v40_run.metrics["return_pct"], 2
                ),
                "max_drawdown_pct": round(
                    v41_run.metrics["max_drawdown_pct"]
                    - v40_run.metrics["max_drawdown_pct"],
                    2,
                ),
                "sharpe": round(
                    v41_run.metrics["sharpe"] - v40_run.metrics["sharpe"], 4
                ),
                "win_rate_pct": round(
                    v41_run.metrics["win_rate_pct"]
                    - v40_run.metrics["win_rate_pct"],
                    2,
                ),
            },
            "v41_vs_v35": {
                "return_pct": round(
                    v41_run.metrics["return_pct"] - v35_run.metrics["return_pct"], 2
                ),
                "max_drawdown_pct": round(
                    v41_run.metrics["max_drawdown_pct"]
                    - v35_run.metrics["max_drawdown_pct"],
                    2,
                ),
                "sharpe": round(
                    v41_run.metrics["sharpe"] - v35_run.metrics["sharpe"], 4
                ),
            },
        },
    }

    summary_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    base.write_artifacts(
        runs,
        trades_path=ARTIFACT_DIR / f"{OUT_STEM}_trades.csv",
        equity_path=ARTIFACT_DIR / f"{OUT_STEM}_equity.csv",
    )
    print(f"\nsummary -> {summary_path}")


if __name__ == "__main__":
    main()
