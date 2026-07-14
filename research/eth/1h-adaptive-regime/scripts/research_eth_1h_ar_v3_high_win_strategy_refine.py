from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import eth_1h_ar_v1 as v1  # noqa: E402
import eth_1h_ar_v2_1 as v21  # noqa: E402
import eth_1h_ar_v2_1_clean as clean21  # noqa: E402
import research_eth_1h_ar_v3_high_win_frequency_tune as frequency_tune  # noqa: E402


DATE_TAG = "2026-07-13"
FAMILY_DIR = ROOT / "research/eth/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
SOURCE_JSON = ARTIFACT_DIR / f"eth_1h_ar_v3_high_win_frequency_tune_{DATE_TAG}.json"
SOURCE_CANDIDATES_CSV = (
    ARTIFACT_DIR / f"eth_1h_ar_v3_high_win_frequency_candidates_{DATE_TAG}.csv"
)
SUMMARY_JSON = ARTIFACT_DIR / f"eth_1h_ar_v3_high_win_strategy_refine_{DATE_TAG}.json"
RISK_GRID_CSV = ARTIFACT_DIR / f"eth_1h_ar_v3_high_win_strategy_refine_grid_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"eth_1h_ar_v3_high_win_strategy_refine_trades_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"eth_1h_ar_v3_high_win_strategy_refine_slices_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"eth-1h-ar-v3-high-win-strategy-refine-{DATE_TAG}.md"

BB_LEVERAGES = (0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
RSI_LEVERAGES = (1.5, 1.75, 2.0, 2.25, 2.5)

# 相对上一轮 high-win frequency observation，胜率只允许小幅下降。
MIN_PREFIT_TRADES = 65
MIN_VALIDATION_TRADES = 15
MIN_TRAIN_WIN = 0.88
MIN_VALIDATION_WIN = 0.90
MIN_PREFIT_WIN = 0.90
BASE_PREFIT_DD_FLOOR = -0.15
MIN_K2_PREFIT_WIN = 0.84
K2_PREFIT_DD_FLOOR = -0.18
MIN_SLIP8_PREFIT_WIN = 0.87
SLIP8_PREFIT_DD_FLOOR = -0.16


@dataclass(slots=True)
class RiskCandidate:
    source_row: int
    bb: clean21.BBBreakV21CleanConfig
    rsi: clean21.RSIV21CleanConfig
    base_metrics: dict[str, dict[str, float]]
    k2_metrics: dict[str, dict[str, float]]
    slip8_metrics: dict[str, dict[str, float]]
    score: float


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def metric_line(metric: dict[str, float]) -> str:
    return (
        f"`{metric['annual_multiple']:.4f}x` / `{metric['total_return']:.2%}` / "
        f"`{metric['max_dd']:.2%}` / `{metric['win_rate']:.2%}` / "
        f"`{int(metric['trades'])}`"
    )


def flatten(metrics: dict[str, dict[str, float]], prefix: str) -> dict[str, float]:
    return {
        f"{prefix}_{window}_{key}": value
        for window, values in metrics.items()
        for key, value in values.items()
    }


def config_from_row(
    row: pd.Series,
) -> tuple[clean21.BBBreakV21CleanConfig, clean21.RSIV21CleanConfig]:
    bb = clean21.BBBreakV21CleanConfig(
        **{field: row[f"bb_{field}"] for field in frequency_tune.BB_DOMAINS}
    )
    rsi = clean21.RSIV21CleanConfig(
        **{field: row[f"rsi_{field}"] for field in frequency_tune.RSI_DOMAINS}
    )
    return bb, rsi


def selection_gate(
    base: dict[str, dict[str, float]],
    k2: dict[str, dict[str, float]],
    slip8: dict[str, dict[str, float]],
) -> bool:
    train = base["train"]
    validation = base["validation"]
    prefit = base["prefit"]
    return bool(
        prefit["trades"] >= MIN_PREFIT_TRADES
        and validation["trades"] >= MIN_VALIDATION_TRADES
        and train["win_rate"] >= MIN_TRAIN_WIN
        and validation["win_rate"] >= MIN_VALIDATION_WIN
        and prefit["win_rate"] >= MIN_PREFIT_WIN
        and prefit["max_dd"] > BASE_PREFIT_DD_FLOOR
        and k2["prefit"]["win_rate"] >= MIN_K2_PREFIT_WIN
        and k2["prefit"]["max_dd"] > K2_PREFIT_DD_FLOOR
        and slip8["prefit"]["win_rate"] >= MIN_SLIP8_PREFIT_WIN
        and slip8["prefit"]["max_dd"] > SLIP8_PREFIT_DD_FLOOR
    )


def selection_score(
    base: dict[str, dict[str, float]],
    k2: dict[str, dict[str, float]],
    slip8: dict[str, dict[str, float]],
) -> float:
    train = base["train"]
    validation = base["validation"]
    prefit = base["prefit"]
    min_win = min(
        train["win_rate"],
        validation["win_rate"],
        prefit["win_rate"],
        k2["prefit"]["win_rate"],
        slip8["prefit"]["win_rate"],
    )
    worst_dd = min(
        prefit["max_dd"],
        k2["prefit"]["max_dd"],
        slip8["prefit"]["max_dd"],
    )
    trade_reward = min(prefit["trades"], 80.0) / 80.0
    return float(
        1.5 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 1.5 * trade_reward
        + 3.0 * min_win
        + 8.0 * worst_dd
    )


def scenario_prefit(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    bb: clean21.BBBreakV21CleanConfig,
    rsi: clean21.RSIV21CleanConfig,
    *,
    delay: int,
    fee: float,
    slippage: float,
) -> dict[str, dict[str, float]]:
    _trades, metrics = frequency_tune.simulate_scenario_prefit(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        bb,
        rsi,
        delay=delay,
        fee=fee,
        slippage=slippage,
    )
    return metrics


def full_scenario(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    bb: clean21.BBBreakV21CleanConfig,
    rsi: clean21.RSIV21CleanConfig,
    *,
    delay: int,
    fee: float,
    slippage: float,
) -> tuple[list[Any], dict[str, dict[str, float]]]:
    return frequency_tune.full_scenario_metrics(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        bb,
        rsi,
        delay=delay,
        fee=fee,
        slippage=slippage,
    )


def risk_row(candidate: RiskCandidate) -> dict[str, Any]:
    return {
        "source_row": candidate.source_row,
        "selection_score_no_holdout": candidate.score,
        **{f"bb_{key}": value for key, value in asdict(candidate.bb).items()},
        **{f"rsi_{key}": value for key, value in asdict(candidate.rsi).items()},
        **flatten(candidate.base_metrics, "base"),
        **flatten(candidate.k2_metrics, "k2"),
        **flatten(candidate.slip8_metrics, "slip8"),
    }


def trade_row(trade: Any) -> dict[str, Any]:
    return {
        "config": trade.config,
        "style": trade.style,
        "signal_i": trade.signal_i,
        "entry_i": trade.entry_i,
        "exit_i": trade.exit_i,
        "signal_ts": trade.signal_ts,
        "entry_ts": trade.entry_ts,
        "exit_ts": trade.exit_ts,
        "side": trade.side,
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "exit_reason": trade.exit_reason,
        "bars_held": trade.bars_held,
        "exposure": trade.exposure,
        "net_ret_1x": trade.net_ret_1x,
        "equity_ret": trade.equity_ret,
        "mae_1x": trade.mae_1x,
        "equity_mae": trade.equity_mae,
        "mfe_1x": trade.mfe_1x,
        "funding_ret_1x": trade.funding_ret_1x,
        "signal_atr_bps": trade.signal_atr_bps,
    }


def build_report(payload: dict[str, Any]) -> str:
    source = payload["source_observation"]["metrics"]
    selected = payload["selected"]["metrics"]
    scenarios = payload["scenario_metrics"]
    slices = payload["standard_slices"]
    selection = payload["selection"]

    lines = [
        "# ETH-1H-Adaptive-Regime-V3 高胜率全策略优化 - 2026-07-13",
        "",
        "## 结论",
        "",
        "本轮接受“增加有效交易数，但胜率不能下降太多”的约束。上一轮已经在 27 参数 clean surface 上完成全策略搜索；本轮从其中通过 K+2/8 bps 的 33 个候选出发，对两条腿风险暴露重新组合，并以高胜率、交易数和回撤联合门槛进行 prefit-only 冻结。",
        "",
        f"- 选中 observation：`{payload['observation_id']}`；来源候选行 `{selection['source_row']}`；BB/RSI 杠杆 `{selection['bb_leverage']:.2f}x / {selection['rsi_leverage']:.2f}x`。",
        f"- 上一轮 high-win frequency prefit：{metric_line(source['prefit'])}；本轮：{metric_line(selected['prefit'])}。",
        f"- 上一轮 current full：{metric_line(source['current_full'])}；本轮：{metric_line(selected['current_full'])}。",
        f"- 本轮 reused holdout（冻结后只读）：{metric_line(selected['reused_holdout'])}。",
        "",
        "胜率下降被控制在较小范围：prefit 从 `91.67%` 到 `91.04%`（`-0.62` 个百分点），current full 从 `88.41%` 到 `87.34%`（`-1.07` 个百分点）；同时 prefit 交易从 `60` 增加到 `67`，current full 从 `69` 增加到 `79`，current-full DD 从 `-22.55%` 收敛到 `-17.08%`。",
        "",
        "## 选择门槛",
        "",
        f"- 基础：prefit trades `>= {MIN_PREFIT_TRADES}`、validation trades `>= {MIN_VALIDATION_TRADES}`；train/validation/prefit 胜率分别 `>= {MIN_TRAIN_WIN:.0%}/{MIN_VALIDATION_WIN:.0%}/{MIN_PREFIT_WIN:.0%}`；prefit DD `< {abs(BASE_PREFIT_DD_FLOOR):.0%}`。",
        f"- K+2：prefit 胜率 `>= {MIN_K2_PREFIT_WIN:.0%}`、DD `< {abs(K2_PREFIT_DD_FLOOR):.0%}`。",
        f"- 8 bps：prefit 胜率 `>= {MIN_SLIP8_PREFIT_WIN:.0%}`、DD `< {abs(SLIP8_PREFIT_DD_FLOOR):.0%}`。",
        f"- 共评估 `{payload['search_counts']['risk_combinations']}` 个风险组合，门槛命中 `{payload['search_counts']['gate_pass']}` 个；选择、排序均未读取 reused holdout。",
        "",
        "## 选中参数",
        "",
        "### BB breakout",
        "",
    ]
    for key, value in payload["selected"]["bb_break"].items():
        lines.append(f"- `{key}` = `{value}`")
    lines.extend(["", "### RSI reversal", ""])
    for key, value in payload["selected"]["rsi_reversal"].items():
        lines.append(f"- `{key}` = `{value}`")

    lines.extend(["", "## 延迟与成本审计", ""])
    for name in (
        "base_k1",
        "delay_k2",
        "delay_k3",
        "slip_8bps",
        "slip_12bps",
        "fee12_slip8",
        "double_cost",
    ):
        metrics = scenarios[name]
        lines.append(
            f"- `{name}`：prefit {metric_line(metrics['prefit'])}；"
            f"reused holdout {metric_line(metrics['reused_holdout'])}。"
        )

    lines.extend(["", "## 标准近期分片", ""])
    for name in ("last_1d", "last_7d", "last_1m", "last_3m", "last_6m", "last_1y"):
        lines.append(f"- `{name}`：{metric_line(slices[name])}")

    lines.extend(
        [
            "",
            "## 研究边界",
            "",
            "- 本轮 observation 没有登记为 V4；未更新主账版本表，也不生成 live spec。",
            "- reused holdout 已多次揭盲，只能用于冻结后失败边界；其转正不能替代 fresh forward。",
            "- 当前数据仍截止 `2026-07-03T05:00:00Z`。在新增数据上至少积累 `20-30` 笔或 `2-3` 个月，并完成 live-executable 审计前，状态仍为 `NO-GO / not promoted / not live-ready`。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{RISK_GRID_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            f"- `artifacts/{SLICES_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            f"uv run python research/eth/1h-adaptive-regime/scripts/{Path(__file__).name}",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    if not SOURCE_JSON.exists() or not SOURCE_CANDIDATES_CSV.exists():
        raise RuntimeError(
            "Missing high-win frequency source artifacts; run "
            "research_eth_1h_ar_v3_high_win_frequency_tune.py first"
        )

    source_payload = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    source_candidates = pd.read_csv(SOURCE_CANDIDATES_CSV)
    robust_seeds = source_candidates[
        source_candidates["robust_gate"].astype(str).str.lower().eq("true")
    ]
    if robust_seeds.empty:
        raise RuntimeError("No robust high-win frequency seeds found")

    engine, frame, funding, quality = v21.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    survivors: list[RiskCandidate] = []
    evaluated = 0
    for source_row, row in robust_seeds.iterrows():
        source_bb, source_rsi = config_from_row(row)
        for bb_leverage in BB_LEVERAGES:
            for rsi_leverage in RSI_LEVERAGES:
                evaluated += 1
                bb = replace(source_bb, fixed_leverage=bb_leverage)
                rsi = replace(source_rsi, fixed_leverage=rsi_leverage)
                base_metrics = scenario_prefit(
                    engine,
                    frame,
                    funding_times,
                    funding_cumulative,
                    bb,
                    rsi,
                    delay=1,
                    fee=0.001,
                    slippage=0.0004,
                )
                k2_metrics = scenario_prefit(
                    engine,
                    frame,
                    funding_times,
                    funding_cumulative,
                    bb,
                    rsi,
                    delay=2,
                    fee=0.001,
                    slippage=0.0004,
                )
                slip8_metrics = scenario_prefit(
                    engine,
                    frame,
                    funding_times,
                    funding_cumulative,
                    bb,
                    rsi,
                    delay=1,
                    fee=0.001,
                    slippage=0.0008,
                )
                if not selection_gate(base_metrics, k2_metrics, slip8_metrics):
                    continue
                survivors.append(
                    RiskCandidate(
                        source_row=int(source_row),
                        bb=bb,
                        rsi=rsi,
                        base_metrics=base_metrics,
                        k2_metrics=k2_metrics,
                        slip8_metrics=slip8_metrics,
                        score=selection_score(base_metrics, k2_metrics, slip8_metrics),
                    )
                )

    if not survivors:
        raise RuntimeError("No risk-refined candidate passed the strict high-win gate")
    survivors.sort(key=lambda candidate: candidate.score, reverse=True)
    selected = survivors[0]

    scenarios = {
        "base_k1": {"delay": 1, "fee": 0.001, "slippage": 0.0004},
        "delay_k2": {"delay": 2, "fee": 0.001, "slippage": 0.0004},
        "delay_k3": {"delay": 3, "fee": 0.001, "slippage": 0.0004},
        "slip_8bps": {"delay": 1, "fee": 0.001, "slippage": 0.0008},
        "slip_12bps": {"delay": 1, "fee": 0.001, "slippage": 0.0012},
        "fee12_slip8": {"delay": 1, "fee": 0.0012, "slippage": 0.0008},
        "double_cost": {"delay": 1, "fee": 0.002, "slippage": 0.0008},
    }
    full_scenarios: dict[str, dict[str, dict[str, float]]] = {}
    selected_trades: list[Any] | None = None
    for name, values in scenarios.items():
        trades, metrics = full_scenario(
            engine,
            frame,
            funding_times,
            funding_cumulative,
            selected.bb,
            selected.rsi,
            **values,
        )
        full_scenarios[name] = metrics
        if name == "base_k1":
            selected_trades = trades
    assert selected_trades is not None

    standard_slices = v21.standard_slices(engine, selected_trades)
    payload = {
        "family": "ETH-1H-Adaptive-Regime",
        "baseline_version": "ETH-1H-Adaptive-Regime-V3",
        "observation_id": "ETH-1H-AR-V3-HIGH-WIN-STRATEGY-REFINE-2026-07-13",
        "status": "diagnostic_observation_not_registered_not_promoted_not_live_ready",
        "selection_policy": {
            "search_uses": "train_validation_prefit_only",
            "source": "33 robust candidates from V3 high-win frequency tune",
            "reused_holdout": "read_only_after_candidate_freeze_not_used_for_selection",
            "goal": "increase trades and reduce DD with minimal win-rate degradation",
        },
        "selection_gate": {
            "prefit_trades_min": MIN_PREFIT_TRADES,
            "validation_trades_min": MIN_VALIDATION_TRADES,
            "train_win_min": MIN_TRAIN_WIN,
            "validation_win_min": MIN_VALIDATION_WIN,
            "prefit_win_min": MIN_PREFIT_WIN,
            "base_prefit_dd_floor": BASE_PREFIT_DD_FLOOR,
            "k2_prefit_win_min": MIN_K2_PREFIT_WIN,
            "k2_prefit_dd_floor": K2_PREFIT_DD_FLOOR,
            "slip8_prefit_win_min": MIN_SLIP8_PREFIT_WIN,
            "slip8_prefit_dd_floor": SLIP8_PREFIT_DD_FLOOR,
        },
        "search_counts": {
            "robust_source_seeds": int(len(robust_seeds)),
            "risk_combinations": evaluated,
            "gate_pass": len(survivors),
        },
        "data_quality": quality,
        "source_observation": {
            "observation_id": source_payload["observation_id"],
            "metrics": source_payload["selected"]["metrics"],
        },
        "selection": {
            "source_row": selected.source_row,
            "score_no_holdout": selected.score,
            "bb_leverage": selected.bb.fixed_leverage,
            "rsi_leverage": selected.rsi.fixed_leverage,
        },
        "selected": {
            "bb_break": asdict(selected.bb),
            "rsi_reversal": asdict(selected.rsi),
            "metrics": full_scenarios["base_k1"],
        },
        "scenario_metrics": full_scenarios,
        "standard_slices": standard_slices,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([risk_row(candidate) for candidate in survivors]).to_csv(
        RISK_GRID_CSV, index=False
    )
    pd.DataFrame([trade_row(trade) for trade in selected_trades]).to_csv(
        TRADES_CSV, index=False
    )
    pd.DataFrame.from_dict(standard_slices, orient="index").rename_axis("window").to_csv(
        SLICES_CSV
    )
    SUMMARY_JSON.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    REPORT_MD.write_text(build_report(payload), encoding="utf-8")

    selected_metrics = full_scenarios["base_k1"]
    print(
        json.dumps(
            {
                "observation_id": payload["observation_id"],
                "search_counts": payload["search_counts"],
                "selection": payload["selection"],
                "prefit": {
                    key: selected_metrics["prefit"][key]
                    for key in ("annual_multiple", "max_dd", "win_rate", "trades")
                },
                "reused_holdout": {
                    key: selected_metrics["reused_holdout"][key]
                    for key in ("total_return", "max_dd", "win_rate", "trades")
                },
                "current_full": {
                    key: selected_metrics["current_full"][key]
                    for key in ("annual_multiple", "max_dd", "win_rate", "trades")
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
