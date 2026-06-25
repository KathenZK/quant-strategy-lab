from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SOURCE_PATH = Path(__file__).with_name("research_hype_5m_pbtr_v3-3_full_ablation.py")

REPORT_PATH = Path("reports/hype_5m_pbtr_v33_pullback_buffer_search.json")
SUMMARY_PATH = Path("reports/hype_5m_pbtr_v33_pullback_buffer_search_summary.csv")
ROLLING_PATH = Path("reports/hype_5m_pbtr_v33_pullback_buffer_search_rolling.csv")
WEEKLY_PATH = Path("reports/hype_5m_pbtr_v33_pullback_buffer_search_weekly.csv")
MONTHLY_PATH = Path("reports/hype_5m_pbtr_v33_pullback_buffer_search_monthly.csv")
MARKDOWN_PATH = Path(
    "docs/research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v33-pullback-buffer-search-2026-06-25.md"
)

PULLBACK_VALUES = (0.0, 0.001, 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03)


def load_v33_module() -> Any:
    spec = importlib.util.spec_from_file_location("v33_full_ablation", SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {SOURCE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v33 = load_v33_module()


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def summarize(label: str, signal_count: int, trades: list[Any], frame: pd.DataFrame, cfg: Any) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return {
        "label": label,
        "pullback_buffer": cfg.pullback_buffer,
        "signal_count": signal_count,
        **v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end),
    }


def add_prefixed_slices(strategy: str, frame: pd.DataFrame, trades: list[Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rolling, weekly, monthly = v33.baseline_time_slices(frame, trades)
    rolling.insert(0, "strategy", strategy)
    weekly.insert(0, "strategy", strategy)
    monthly.insert(0, "strategy", strategy)
    return rolling, weekly, monthly


def render_markdown(summary: pd.DataFrame, rolling: pd.DataFrame) -> str:
    by_pf = summary.sort_values(["profit_factor", "total_return"], ascending=False)
    by_return = summary.sort_values("total_return", ascending=False)
    baseline = summary.loc[summary["pullback_buffer"].eq(0.01)].iloc[0]
    best_pf = by_pf.iloc[0]
    best_return = by_return.iloc[0]

    def table(rows: pd.DataFrame) -> list[str]:
        lines = [
            "| pullback_buffer | 信号数 | 交易数 | 年化 | 累计收益 | 胜率 | payoff | PF | 最大回撤 | ΔPF vs 0.01 | Δ交易数 |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in rows.to_dict(orient="records"):
            lines.append(
                f"| `{row['pullback_buffer']}` | `{int(row['signal_count'])}` | `{int(row['trades'])}` | "
                f"`{mult(float(row['annualized_multiple']))}` | `{pct(float(row['total_return']))}` | "
                f"`{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | "
                f"`{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` | "
                f"`{num(float(row['profit_factor'] - baseline['profit_factor']))}` | "
                f"`{int(row['trades'] - baseline['trades'])}` |"
            )
        return lines

    best_label = str(best_pf["label"])
    best_rolling = rolling.loc[rolling["strategy"].eq(best_label)].copy()
    lines = [
        "# HYPE-5M-PBTR-V3.3 pullback_buffer 搜索 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告按 `HYPE-5M-PBTR-V3.3` 旧回测口径，只改变 `pullback_buffer`，其余参数固定为 `EMA21/96 + stop_atr=0.5 + trail_atr=0.75 + min_hold_bars=9`。",
        "",
        "搜索值：`0.0, 0.001, 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03`。",
        "",
        "## PF 排名",
        "",
        *table(by_pf),
        "",
        "## 收益排名",
        "",
        *table(by_return),
        "",
        "## 最佳 PF 时间切片",
        "",
        f"最佳 PF：`pullback_buffer={best_pf['pullback_buffer']}`，PF `{num(float(best_pf['profit_factor']))}`，交易 `{int(best_pf['trades'])}` 笔。",
        "",
        "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in best_rolling.to_dict(orient="records"):
        lines.append(
            f"| `{row['window']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | "
            f"`{mult(float(row['annualized_multiple']))}` | `{pct(float(row['win_rate']))}` | "
            f"`{num(float(row['payoff_ratio']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"`pullback_buffer=0.01` 不是 PF 最优点；本轮最佳 PF 是 `{best_pf['pullback_buffer']}`，PF 从基线 `{num(float(baseline['profit_factor']))}` 到 `{num(float(best_pf['profit_factor']))}`。但收益最高仍是 `{best_return['pullback_buffer']}`，说明更宽 buffer 带来更多样本和更高复利，较小 buffer 主要是筛掉部分频率。",
            "",
            "这仍是旧口径搜索，不解决 V3.3 的 live-realistic stop 穿越问题；若用于实盘，需要重新按可执行状态机评估。",
            "",
            "## 产物",
            "",
            f"- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v33_pullback_buffer_search.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- rolling CSV：`{ROLLING_PATH}`",
            f"- weekly CSV：`{WEEKLY_PATH}`",
            f"- monthly CSV：`{MONTHLY_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v33.load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= v33.END_TS].reset_index(drop=True)
    summary_rows: list[dict[str, Any]] = []
    rolling_parts: list[pd.DataFrame] = []
    weekly_parts: list[pd.DataFrame] = []
    monthly_parts: list[pd.DataFrame] = []
    configs: list[dict[str, Any]] = []

    for value in PULLBACK_VALUES:
        cfg = replace(v33.V33_CONFIG, strategy_name=f"HYPE-5M-PBTR-V3.3-pb-{value:g}", pullback_buffer=value)
        frame = v33.add_minimal_features(raw, cfg)
        signal = v33.build_signal(frame, cfg)
        trades = v33.simulate_trades(frame, signal, cfg)
        summary_rows.append(summarize(cfg.strategy_name, int(np.count_nonzero(signal)), trades, frame, cfg))
        rolling, weekly, monthly = add_prefixed_slices(cfg.strategy_name, frame, trades)
        rolling_parts.append(rolling)
        weekly_parts.append(weekly)
        monthly_parts.append(monthly)
        configs.append(asdict(cfg))

    summary = pd.DataFrame(summary_rows)
    rolling = pd.concat(rolling_parts, ignore_index=True)
    weekly = pd.concat(weekly_parts, ignore_index=True)
    monthly = pd.concat(monthly_parts, ignore_index=True)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    weekly.to_csv(WEEKLY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, rolling), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V3.3 pullback_buffer search",
                "base_definition": asdict(v33.V33_CONFIG),
                "configs": configs,
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
                },
                "summary": summary.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary.sort_values(["profit_factor", "total_return"], ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
