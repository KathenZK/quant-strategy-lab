from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_btc_1h_ar_v1_scaled_frontier as scaled  # noqa: E402
import btc_1h_ar_v1 as v1  # noqa: E402
import btc_1h_ar_v1_clean as clean  # noqa: E402
import research_btc_1h_ar_v1_clean_tune as tune  # noqa: E402
import research_btc_1h_ar_v2_full_ablation as v2_ablation  # noqa: E402


FAMILY_DIR = ROOT / "research/btc/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
DATE_TAG = "2026-07-06"
SUMMARY_JSON = ARTIFACT_DIR / f"btc_1h_ar_v2_micro_tune_{DATE_TAG}.json"
GRID_CSV = ARTIFACT_DIR / f"btc_1h_ar_v2_micro_tune_grid_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"btc_1h_ar_v2_micro_tune_selected_trades_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"btc-1h-ar-v2-micro-tune-{DATE_TAG}.md"


def flatten_metrics(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    return {
        f"{window}_{key}": value
        for window, values in metrics.items()
        for key, value in values.items()
    }


def simulate(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    keltner: clean.KeltnerCleanConfig,
    cci: clean.CCICleanConfig,
) -> tuple[list[Any], dict[str, dict[str, float]], tuple[float, float]]:
    k_cfg = replace(clean.keltner_to_base(engine, keltner), name="BTC_1H_AR_V2T_KELTNER")
    c_cfg = replace(clean.cci_to_base(engine, cci), name="BTC_1H_AR_V2T_CCI")
    trades, _k_trades, _c_trades, priorities = v2_ablation.simulate_pair(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        keltner=k_cfg,
        cci=c_cfg,
    )
    return trades, v1.metrics(engine, trades), priorities


def selection_gate(
    metrics: dict[str, dict[str, float]],
    reference: dict[str, dict[str, float]],
) -> bool:
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    return bool(
        prefit["annual_multiple"] > reference["prefit"]["annual_multiple"]
        and prefit["win_rate"] >= 0.80
        and prefit["max_dd"] > -0.20
        and train["total_return"] > 0
        and validation["total_return"] > 0
        and train["win_rate"] >= 0.80
        and validation["win_rate"] >= 0.80
        and train["max_dd"] > -0.20
        and validation["max_dd"] > -0.20
    )


def score(metrics: dict[str, dict[str, float]], reference: dict[str, dict[str, float]]) -> float:
    train = metrics["train"]
    validation = metrics["validation"]
    prefit = metrics["prefit"]
    min_win = min(train["win_rate"], validation["win_rate"], prefit["win_rate"])
    worst_dd = min(train["max_dd"], validation["max_dd"], prefit["max_dd"])
    if not selection_gate(metrics, reference):
        return -1e9
    return float(
        prefit["annual_multiple"]
        + 0.35 * min(train["annual_multiple"], validation["annual_multiple"])
        + 0.20 * min(prefit["profit_factor"], 8.0)
        + 0.80 * min_win
        + 2.0 * (worst_dd + 0.20)
    )


def metric_line(metric: dict[str, float]) -> str:
    return (
        f"`{metric['annual_multiple']:.4f}x` / `{metric['total_return']:.2%}` / "
        f"`{metric['max_dd']:.2%}` / `{metric['win_rate']:.2%}` / "
        f"`{int(metric['trades'])}`"
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    baseline_trades, baseline_metrics, baseline_priorities = simulate(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        keltner=scaled.KELTNER,
        cci=scaled.CCI,
    )

    keltner_space = {
        "htf_mode": ["h4", "none"],
        "fixed_leverage": [1.6, 1.8, 2.0, 2.2, 2.4],
        "max_atr_bps": [200.0, 250.0],
        "min_dir_roc_bps": [-200.0, -100.0, -10000.0],
    }
    cci_space = {
        "tp_atr": [4.5, 5.0, 5.5, 6.0],
        "cooldown_bars": [0, 24, 48],
        "max_adx": [40.0, 45.0],
        "fixed_leverage": [2.4, 2.7, 3.0, 3.3, 3.5],
    }

    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for k_values in product(*keltner_space.values()):
        k_updates = dict(zip(keltner_space.keys(), k_values, strict=True))
        for c_values in product(*cci_space.values()):
            c_updates = dict(zip(cci_space.keys(), c_values, strict=True))
            keltner = replace(scaled.KELTNER, **k_updates)
            cci = replace(scaled.CCI, **c_updates)
            key = tuple(asdict(keltner).values()) + tuple(asdict(cci).values())
            if key in seen:
                continue
            seen.add(key)
            trades, metrics, priorities = simulate(
                engine,
                frame,
                funding_times,
                funding_cumulative,
                keltner=keltner,
                cci=cci,
            )
            row = {
                "label": f"V2_micro_{len(rows):05d}",
                "passes_selection_gate": selection_gate(metrics, baseline_metrics),
                "score": score(metrics, baseline_metrics),
                "keltner": asdict(keltner),
                "cci": asdict(cci),
                "keltner_priority": priorities[0],
                "cci_priority": priorities[1],
                **{f"keltner_{key}": value for key, value in asdict(keltner).items()},
                **{f"cci_{key}": value for key, value in asdict(cci).items()},
                **flatten_metrics(metrics),
            }
            rows.append(row)

    grid = pd.DataFrame(rows).sort_values(
        ["passes_selection_gate", "score", "prefit_annual_multiple", "prefit_max_dd"],
        ascending=[False, False, False, False],
    )
    grid.to_csv(GRID_CSV, index=False)
    passed = grid.loc[grid["passes_selection_gate"]].copy()
    if passed.empty:
        selected_row = grid.iloc[0].to_dict()
    else:
        selected_row = (
            passed.sort_values(
                [
                    "prefit_annual_multiple",
                    "current_full_annual_multiple",
                    "validation_annual_multiple",
                    "prefit_max_dd",
                ],
                ascending=[False, False, False, False],
            )
            .iloc[0]
            .to_dict()
        )
    selected_keltner = clean.KeltnerCleanConfig(
        **{
            key.removeprefix("keltner_"): selected_row[key]
            for key in selected_row
            if key.startswith("keltner_")
            and key.removeprefix("keltner_") in asdict(scaled.KELTNER)
        }
    )
    selected_cci = clean.CCICleanConfig(
        **{
            key.removeprefix("cci_"): selected_row[key]
            for key in selected_row
            if key.startswith("cci_") and key.removeprefix("cci_") in asdict(scaled.CCI)
        }
    )
    selected_trades, selected_metrics, selected_priorities = simulate(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        keltner=selected_keltner,
        cci=selected_cci,
    )
    pd.DataFrame(
        [
            {
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": trade.side,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "exit_reason": trade.exit_reason,
                "bars_held": trade.bars_held,
                "exposure": trade.exposure,
                "equity_ret": trade.equity_ret,
                "equity_mae": trade.equity_mae,
            }
            for trade in selected_trades
        ]
    ).to_csv(TRADES_CSV, index=False)

    payload = {
        "family": "BTC-1H-Adaptive-Regime",
        "base_version": "BTC-1H-Adaptive-Regime-V2",
        "observation_id": "BTC-1H-AR-V2-MICRO-TUNE-2026-07-06",
        "status": "diagnostic_micro_tune_not_registered_not_live_ready",
        "selection_rule": (
            "prefit annual > V2, train/validation/prefit win >= 80pct, "
            "train/validation/prefit DD < 20pct; maximize prefit annual among "
            "gate passes; reused holdout not used"
        ),
        "grid_size": len(grid),
        "selection_gate_passes": int(passed.shape[0]),
        "baseline": {
            "keltner": asdict(scaled.KELTNER),
            "cci": asdict(scaled.CCI),
            "metrics": baseline_metrics,
            "priorities": baseline_priorities,
        },
        "selected": {
            "label": selected_row["label"],
            "keltner": asdict(selected_keltner),
            "cci": asdict(selected_cci),
            "metrics": selected_metrics,
            "priorities": selected_priorities,
        },
        "top_30": grid.head(30).to_dict(orient="records"),
        "data_quality": quality,
    }
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    lines = [
        "# BTC-1H-Adaptive-Regime-V2 微调观察 - 2026-07-06",
        "",
        "## 结论",
        "",
        (
            "基于 V2 全参数消融的前沿方向，执行受约束 micro-tune。选参只读取 "
            "train/validation/prefit；reused holdout 已解锁，只作冻结后复用审计。"
        ),
        "",
        (
            f"网格共 `{len(grid)}` 组，满足“prefit 年化高于 V2、train/validation/prefit "
            f"胜率均 >=80%、回撤均 <20%”的组合 `{int(passed.shape[0])}` 组。"
        ),
        "",
        "当前首选观察为 `BTC-1H-AR-V2-MICRO-TUNE-2026-07-06`，不登记 V2.1，不标记 live-ready。",
        "",
        "## V2 基线 vs 微调观察",
        "",
        "| Window | V2 annual / return / DD / win / trades | Micro-tune annual / return / DD / win / trades |",
        "| --- | --- | --- |",
    ]
    for window in ("train", "validation", "prefit", "reused_holdout", "current_full"):
        lines.append(
            f"| `{window}` | {metric_line(baseline_metrics[window])} | "
            f"{metric_line(selected_metrics[window])} |"
        )
    lines.extend(
        [
            "",
            "## 冻结参数",
            "",
            "### Keltner leg",
            "",
            *[
                f"- `{key}` = `{value}`"
                for key, value in asdict(selected_keltner).items()
            ],
            "",
            "### CCI leg",
            "",
            *[f"- `{key}` = `{value}`" for key, value in asdict(selected_cci).items()],
            "",
            "## 选择边界",
            "",
            "- 本轮不改变 `style`、`side_mode`、`entry_delay_bars`、`exit_kind` 或 `sizing_kind` 等合同字段。",
            "- 本轮没有新增 forward trades，也没有 production runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 或真实 stop-market 滑点证据。",
            "- 若要登记为新版本，需要另行确认；当前只是 diagnostic micro-tune observation。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{GRID_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v2_micro_tune.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
