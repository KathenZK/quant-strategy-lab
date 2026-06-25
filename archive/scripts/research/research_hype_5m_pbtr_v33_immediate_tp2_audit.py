from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import research_hype_5m_pbtr_live_realistic_trailing as live_trailing
import research_hype_5m_pbtr_v33_immediate_tp_audit as tp_audit
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import ENTRY_SLIPPAGE_RATE, EXIT_SLIPPAGE_RATE, FEE_RATE_PER_FILL
from research_hype_5m_positive_payoff_search import load_all_hype_5m


v33 = tp_audit.v33

REPORT_PATH = Path("reports/hype_5m_pbtr_v33_immediate_tp2_audit.json")
SUMMARY_PATH = Path("reports/hype_5m_pbtr_v33_immediate_tp2_audit_summary.csv")
MARKDOWN_PATH = Path(
    "docs/research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v33-immediate-tp2-audit-2026-06-25.md"
)


def pct(value: float, digits: int = 2) -> str:
    if np.isnan(value):
        return "n/a"
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    if np.isnan(value):
        return "n/a"
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    if np.isnan(value):
        return "n/a"
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def render_markdown(summary: pd.DataFrame, old_reasons: dict[str, int], live_reasons: dict[str, int]) -> str:
    rows = {row["label"]: row for row in summary.to_dict(orient="records")}

    def row(label: str, display: str) -> str:
        item = rows[label]
        lockout_target = item.get("target_lockout_rate", np.nan)
        total_target = item.get("target_total_rate", np.nan)
        return (
            f"| `{display}` | `{int(item['trades'])}` | `{mult(float(item['annualized_multiple']))}` | "
            f"`{pct(float(item['total_return']))}` | `{pct(float(item['win_rate']))}` | "
            f"`{num(float(item['profit_factor']))}` | `{num(float(item['payoff_ratio']))}` | "
            f"`{pct(float(item['max_dd']))}` | `{pct(float(lockout_target))}` | `{pct(float(total_target))}` |"
        )

    return "\n".join(
        [
            "# HYPE-5M-PBTR-V3.3 immediate 2ATR TP 审计 2026-06-25",
            "",
            "Family id：`HYPE-5M-PBTR`",
            "",
            "本报告测试 `HYPE-5M-PBTR-V3.3` 的开仓即时 `2 * ATR14` 固定止盈：锁仓期 `min_hold_bars=9` 内只允许止盈，不挂策略止损；解锁后再启用原 ATR trailing stop。",
            "",
            "## 结果",
            "",
            "| 口径 | 交易数 | 年化 | 总收益 | 胜率 | PF | payoff | 最大回撤 | 锁仓期止盈率 | 总止盈率 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            row("original_old_no_tp", "V3.3 原始旧口径，无即时 TP"),
            row("live_realistic_no_tp", "V3.3 live-realistic，无即时 TP"),
            row("tp2_old_stop_price", "即时 2ATR TP + 旧 stop 价成交"),
            row("tp2_live_realistic", "即时 2ATR TP + live-realistic stop"),
            "",
            "## 退出原因",
            "",
            f"- 旧 stop 价成交口径：`{old_reasons}`",
            f"- live-realistic 口径：`{live_reasons}`",
            "",
            "## 结论",
            "",
            "即时 `2 * ATR14` 止盈比 `1 * ATR14` 更远，锁仓期止盈率降至约 `25.76%`。它保留了更多交易进入解锁后的 trailing stop 阶段。",
            "",
            "旧 stop 价成交口径仍然非常赚钱，PF `3.40`；但 live-realistic 口径 PF 只有 `0.60`，总收益仍约 `-100%`。这说明扩大即时止盈到 2ATR 没有修复 V3.3 的可执行性问题，只是把一部分早期止盈换成更多解锁后市价退出/stop-market 亏损。",
            "",
            "## 产物",
            "",
            "- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v33_immediate_tp2_audit.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
        ]
    ) + "\n"


def main() -> None:
    cfg = v33.V33_CONFIG
    raw = load_all_hype_5m()
    frame = v33.add_minimal_features(raw, cfg)
    signal = v33.build_signal(frame, cfg)

    original = v33.simulate_trades(frame, signal, cfg)
    live_no_tp, live_no_tp_diag = live_trailing.simulate_live_realistic_trailing(
        frame,
        signal,
        cfg,
        label="HYPE-5M-PBTR-V3.3-live-realistic",
        entry_slippage_rate=ENTRY_SLIPPAGE_RATE,
        exit_slippage_rate=EXIT_SLIPPAGE_RATE,
        fee_rate_per_fill=FEE_RATE_PER_FILL,
    )
    old_tp, old_tp_diag = tp_audit.simulate_immediate_tp_old_stop(frame, signal, cfg, tp_atr=2.0)
    live_tp, live_tp_diag = tp_audit.simulate_immediate_tp_live_realistic(frame, signal, cfg, tp_atr=2.0)

    summary = pd.DataFrame(
        [
            tp_audit.summarize("original_old_no_tp", original, frame),
            tp_audit.summarize("live_realistic_no_tp", live_no_tp, frame, live_no_tp_diag),
            tp_audit.summarize("tp2_old_stop_price", old_tp, frame, old_tp_diag),
            tp_audit.summarize("tp2_live_realistic", live_tp, frame, live_tp_diag),
        ]
    )
    old_reasons = {str(k): int(v) for k, v in old_tp_diag["reason"].value_counts().to_dict().items()}
    live_reasons = {str(k): int(v) for k, v in live_tp_diag["reason"].value_counts().to_dict().items()}

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, old_reasons, live_reasons), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V3.3",
                "audit": "immediate_2atr_take_profit_with_delayed_stop",
                "summary": summary.to_dict(orient="records"),
                "old_reasons": old_reasons,
                "live_reasons": live_reasons,
                "outputs": {"markdown": str(MARKDOWN_PATH), "summary": str(SUMMARY_PATH)},
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(
        summary[
            [
                "label",
                "trades",
                "annualized_multiple",
                "total_return",
                "win_rate",
                "profit_factor",
                "payoff_ratio",
                "max_dd",
                "target_lockout_rate",
                "target_total_rate",
            ]
        ].to_string(index=False)
    )
    print(f"markdown={MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
