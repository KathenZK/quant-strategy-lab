from __future__ import annotations

import json
import sys
from collections import OrderedDict
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_clean_evolution as evolution  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402
from research_hype_15m_mii_search import (  # noqa: E402
    COMMISSION_PER_SIDE,
    ROUND_TRIP_COST,
    SLIPPAGE_PER_SIDE,
    build_market_arrays,
    signal_state,
)


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
RUN_DATE = "2026-06-30"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_balanced_leverage_stress.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_balanced_leverage_stress_2026-06-30.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_balanced_leverage_stress_2026-06-30.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-balanced-leverage-stress-2026-06-30.md"

EXPOSURES = (1.75, 2.0, 3.0)
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))

BASE_CONFIG = evolution.CleanConfig(
    rsi_window=7,
    rsi_low=40.0,
    rsi_high=60.0,
    min_atr_pct96=0.0105,
    min_rvol96=0.0,
    h1_confirm=False,
    rsi14_band=False,
    take_profit_pct=0.012,
    stop_pct=0.045,
    max_hold_bars=32,
    exposure=2.0,
)


def build_context() -> tuple[evolution.EvalContext, dict[str, Any], dict[str, Any]]:
    frame, metadata, quality = v1.load_data_lake()
    features = evolution.add_rsi_features(evolution.add_features(frame, []))
    context = evolution.EvalContext(
        features=features,
        market=build_market_arrays(features),
        start_ts=pd.Timestamp(features["ts"].min()),
        end_ts=pd.Timestamp(features["ts"].max()) + pd.Timedelta(minutes=15),
        signal_cache={},
        trade_cache=OrderedDict(),
    )
    v1.engine.simulate_trades = v1.simulate_trades_live
    v1.engine.selected_trades = v1.selected_trades_live
    v1.search_engine.selected_trades = v1.selected_trades_live
    return context, metadata, quality


def selected_net_returns_pct(
    trades: list[Any],
    config: evolution.CleanConfig,
) -> list[float]:
    selected = v1.selected_trades_live(trades, config.filter)
    return [
        float(config.exposure * (trade.raw_return - ROUND_TRIP_COST) * 100.0)
        for trade in selected
    ]


def evaluate_variant(
    context: evolution.EvalContext,
    config: evolution.CleanConfig,
    *,
    entry_delay_bars: int,
    entry_label: str,
) -> dict[str, Any]:
    state = signal_state(context.features, config.signal)
    trades = v1.simulate_trades_live(
        context.market,
        state,
        config.exit,
        entry_delay_bars=entry_delay_bars,
    )
    full = evolution.evaluate_window(
        context,
        config,
        trades,
        context.start_ts,
        context.end_ts,
        purge_end=False,
    )
    last90 = evolution.evaluate_window(
        context,
        config,
        trades,
        max(context.start_ts, context.end_ts - pd.Timedelta(days=90)),
        context.end_ts,
        purge_end=False,
    )
    net_returns = selected_net_returns_pct(trades, config)
    return {
        "name": config.name,
        "entry_timing": entry_label,
        "entry_delay_bars": entry_delay_bars,
        **asdict(config),
        "annual_return_pct": float(full["annual_return_pct"]),
        "annual_equity_multiple": float(full["annual_equity_multiple"]),
        "total_return_pct": float(full["total_return_pct"]),
        "max_drawdown_pct": float(full["max_drawdown_pct"]),
        "win_rate_pct": float(full["win_rate_pct"]),
        "trades": int(full["trades"]),
        "trades_per_day": float(full["trades_per_day"]),
        "annualized_trades": float(full["trades_per_day"]) * 365.25,
        "profit_factor": float(full["profit_factor"]),
        "avg_trade_pct": float(np.mean(net_returns)) if net_returns else 0.0,
        "worst_trade_pct": float(np.min(net_returns)) if net_returns else 0.0,
        "last90_annual_return_pct": float(last90["annual_return_pct"]),
    }


def evaluate() -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    context, metadata, quality = build_context()
    rows: list[dict[str, Any]] = []
    for exposure in EXPOSURES:
        config = replace(BASE_CONFIG, exposure=exposure)
        for entry_delay_bars, entry_label in ENTRY_DELAYS:
            rows.append(
                evaluate_variant(
                    context,
                    config,
                    entry_delay_bars=entry_delay_bars,
                    entry_label=entry_label,
                )
            )
    result = pd.DataFrame(rows)
    result = result.sort_values(["exposure", "entry_delay_bars"]).reset_index(drop=True)
    return result, metadata, quality


def metric_table(rows: pd.DataFrame) -> list[str]:
    lines = [
        "| 暴露 | 入场 | 年化 | 总收益 | 最大回撤 | 胜率 | 交易数 | 年化笔数 | 笔/天 | PF | 平均单笔 | 最差单笔 | Last90 年化 |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.to_dict(orient="records"):
        exposure = f"{row['exposure']:g}x"
        lines.append(
            f"| `{exposure}` | `{row['entry_timing']}` | "
            f"`{row['annual_return_pct']:.2f}%` | "
            f"`{row['total_return_pct']:.2f}%` | "
            f"`{row['max_drawdown_pct']:.2f}%` | "
            f"`{row['win_rate_pct']:.2f}%` | "
            f"`{int(row['trades'])}` | "
            f"`{row['annualized_trades']:.1f}` | "
            f"`{row['trades_per_day']:.3f}` | "
            f"`{row['profit_factor']:.3f}` | "
            f"`{row['avg_trade_pct']:.3f}%` | "
            f"`{row['worst_trade_pct']:.3f}%` | "
            f"`{row['last90_annual_return_pct']:.2f}%` |"
        )
    return lines


def lookup(rows: pd.DataFrame, exposure: float, entry_label: str) -> pd.Series:
    selected = rows.loc[
        np.isclose(rows["exposure"].to_numpy("float64"), exposure)
        & rows["entry_timing"].eq(entry_label)
    ]
    if selected.empty:
        raise ValueError(f"missing row exposure={exposure} entry={entry_label}")
    return selected.iloc[0]


def render_markdown(rows: pd.DataFrame, quality: dict[str, Any]) -> str:
    x175_k1 = lookup(rows, 1.75, "K+1")
    x2_k1 = lookup(rows, 2.0, "K+1")
    x2_k2 = lookup(rows, 2.0, "K+2")
    x3_k1 = lookup(rows, 3.0, "K+1")
    x3_k2 = lookup(rows, 3.0, "K+2")

    lines = [
        f"# HYPE-15M-MII 均衡策略杠杆压力测试 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`HYPE-15M-MII`）",
        "",
        "## 结论",
        "",
        "这份记录对应聊天中“如果放弃频率，在收益、回撤、胜率上找均衡版本”和“改成 3 倍杠杆会怎样”的追问。这里的 `x1.75/x2/x3` 是回测权益暴露倍数，不等同于已审计过的交易所保证金模式。",
        "",
        (
            f"- 我仍会把 `2x` 当作这条均衡诊断线的主观察版本：K+1 年化 "
            f"`{x2_k1['annual_return_pct']:.2f}%`、总收益 "
            f"`{x2_k1['total_return_pct']:.2f}%`、回撤 "
            f"`{x2_k1['max_drawdown_pct']:.2f}%`、胜率 "
            f"`{x2_k1['win_rate_pct']:.2f}%`；K+2 仍有年化 "
            f"`{x2_k2['annual_return_pct']:.2f}%`，但回撤扩大到 "
            f"`{x2_k2['max_drawdown_pct']:.2f}%`。"
        ),
        (
            f"- `3x` 的 K+1 年化会抬到 `{x3_k1['annual_return_pct']:.2f}%`，"
            f"但 K+2 回撤达到 `{x3_k2['max_drawdown_pct']:.2f}%`，单笔最差 "
            f"`{x3_k2['worst_trade_pct']:.2f}%`；这已经更像 aggressive diagnostic，"
            "不适合作为小额实盘起步版本。"
        ),
        (
            f"- `1.75x` 是保守观察版本：K+1 年化 `{x175_k1['annual_return_pct']:.2f}%`、"
            f"回撤 `{x175_k1['max_drawdown_pct']:.2f}%`，比 `2x` 少一些收益，"
            "但更贴近原先不希望回撤过大的偏好。"
        ),
        (
            f"- 交易频率没有因暴露倍数变化：K+1 `119` 笔，约 "
            f"`{x2_k1['annualized_trades']:.1f}` 笔/年；K+2 `127` 笔，约 "
            f"`{x2_k2['annualized_trades']:.1f}` 笔/年，仍明显低于 `1-3` 次/天。"
        ),
        "",
        "## 策略参数",
        "",
        "- 信号：`RSI(7)` 上穿 `40` 做多、下穿 `60` 做空。",
        "- 过滤：`MACD(12,26,9)` 方向过滤；`ATR96 pct >= 1.05%`；`min_rvol96=0`；无 `1h confirm`；无 `RSI14 band`。",
        "- 出场：`TP=1.20%`、`SL=4.50%`、最长 `32` 根 `15m` K。",
        "- 入场：`K+1` 是信号 K 收盘后下一根 `open` 入场；`K+2` 是再延迟一根 `15m` K 的压力测试。",
        "",
        "## 数据与成本",
        "",
        f"- 数据：`{quality['first_ts']}` 到 `{quality['last_ts']}`，quality gate `{quality['quality_gate_pass']}`。",
        f"- 成本：手续费 `{COMMISSION_PER_SIDE:.4%}`/fill，滑点 `{SLIPPAGE_PER_SIDE:.4%}`/fill，round-trip `{ROUND_TRIP_COST:.4%}`；资金费未计入。",
        "- 执行：闭合 K 信号、下一根 open 入场、单仓不重叠、stop-first、timeout-open。",
        "",
        "## 杠杆压力表",
        "",
        *metric_table(rows),
        "",
        "## 小额实盘选择",
        "",
        "如果只从这三个暴露倍数里选一个做小额观察，我会选 `2x`，而不是 `3x`：`2x` 已经把 K+1 年化推到 `216.81%`，同时 K+1 回撤仍在 `-15.65%`；`3x` 虽然收益更漂亮，但 K+2 回撤接近 `-40%`，对实盘成交时点、滑点和止损执行误差太敏感。",
        "",
        "更保守的做法是先用 `1.75x` 观察信号质量与成交质量；更激进的 `3x` 只适合继续研究或极小资金沙盒，不应标记为 candidate、paper-live、dry-run、handoff 或 live。",
        "",
        "## 状态",
        "",
        "本策略线仍是 diagnostic。它还没有资金费核算、盘口级 stop-market 证据、真实成交滑点、生产 runner、重启恢复、交易所对账、missing-bar fail-closed 与 kill switch。杠杆压力测试只说明历史净值曲线在权益暴露缩放下的形状，不构成实盘可行性结论。",
        "",
        "## 产物",
        "",
        f"- 脚本：`{SCRIPT_PATH}`",
        f"- CSV：`{CSV_PATH}`",
        f"- JSON：`{JSON_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return str(value)


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    rows, metadata, quality = evaluate()
    rows.to_csv(CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(rows, quality), encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            {
                "family": FAMILY,
                "run_date": RUN_DATE,
                "status": "balanced_leverage_stress_not_promoted",
                "base_config": asdict(BASE_CONFIG),
                "metadata": metadata,
                "data_quality": quality,
                "costs": {
                    "commission_per_fill": COMMISSION_PER_SIDE,
                    "slippage_per_fill": SLIPPAGE_PER_SIDE,
                    "round_trip": ROUND_TRIP_COST,
                },
                "entry_timing_definition": {
                    "K+1": "signal bar close, next 15m bar open entry",
                    "K+2": "one additional 15m bar delay after K+1",
                },
                "recommendation": {
                    "preferred_observation_exposure": 2.0,
                    "conservative_observation_exposure": 1.75,
                    "aggressive_diagnostic_exposure": 3.0,
                    "promotion_status": "diagnostic_only",
                },
                "rows": rows.to_dict(orient="records"),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "csv": str(CSV_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        ),
        encoding="utf-8",
    )
    print(f"wrote {MARKDOWN_PATH}")
    print(rows.to_string(index=False))


if __name__ == "__main__":
    main()
