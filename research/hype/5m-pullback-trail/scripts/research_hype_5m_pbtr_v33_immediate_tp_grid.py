from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_5m_pbtr_v33_immediate_tp_audit as tp_audit
from research_hype_5m_positive_payoff_search import load_all_hype_5m


v33 = tp_audit.v33

REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_immediate_tp_grid.json")
GRID_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_immediate_tp_grid.csv")
MARKDOWN_PATH = Path(
    "research/hype/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v33-immediate-tp-grid-2026-06-25.md"
)


def pct(value: float, digits: int = 2) -> str:
    if np.isnan(value):
        return "n/a"
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    if np.isnan(value):
        return "n/a"
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 3) -> str:
    if np.isnan(value):
        return "n/a"
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def grid_values() -> list[float]:
    return [round(float(value), 2) for value in np.arange(0.25, 8.0001, 0.25)] + [10.0, 12.0]


def search_grid(frame: pd.DataFrame, signal: np.ndarray, cfg: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for tp_atr in grid_values():
        live_trades, live_diag = tp_audit.simulate_immediate_tp_live_realistic(frame, signal, cfg, tp_atr=tp_atr)
        old_trades, old_diag = tp_audit.simulate_immediate_tp_old_stop(frame, signal, cfg, tp_atr=tp_atr)
        live = tp_audit.summarize("live", live_trades, frame, live_diag)
        old = tp_audit.summarize("old", old_trades, frame, old_diag)
        rows.append(
            {
                "tp_atr": tp_atr,
                "live_trades": live["trades"],
                "live_total_return": live["total_return"],
                "live_win_rate": live["win_rate"],
                "live_profit_factor": live["profit_factor"],
                "live_payoff_ratio": live["payoff_ratio"],
                "live_max_dd": live["max_dd"],
                "live_target_lockout_rate": live.get("target_lockout_rate"),
                "live_target_total_rate": live.get("target_total_rate"),
                "old_trades": old["trades"],
                "old_total_return": old["total_return"],
                "old_win_rate": old["win_rate"],
                "old_profit_factor": old["profit_factor"],
                "old_payoff_ratio": old["payoff_ratio"],
                "old_max_dd": old["max_dd"],
                "old_target_lockout_rate": old.get("target_lockout_rate"),
                "old_target_total_rate": old.get("target_total_rate"),
            }
        )
    return pd.DataFrame(rows)


def render_markdown(grid: pd.DataFrame) -> str:
    best_live = grid.sort_values(["live_profit_factor", "live_total_return"], ascending=False).iloc[0]
    best_old = grid.sort_values(["old_profit_factor", "old_total_return"], ascending=False).iloc[0]
    top_live = grid.sort_values(["live_profit_factor", "live_total_return"], ascending=False).head(10)

    lines = [
        "# HYPE-5M-PBTR-V3.3 immediate TP ATR 网格 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "`HYPE-5M-PBTR-V3.3` 即时止盈网格：开仓后立即挂固定 `tp_atr * ATR14` 止盈，锁仓期 `min_hold_bars=9` 内只允许止盈，不挂策略止损；解锁后启用原 ATR trailing stop。",
        "",
        "## 网格",
        "",
        "- `tp_atr` 从 `0.25` 到 `8.00`，步长 `0.25`；附加 `10.00` 和 `12.00`。",
        "- 排名主口径是 `live-realistic`：解锁后 stop 已被开盘价穿越则按开盘市价退出，否则按 stop-market 管理。",
        "- `old stop price` 仅作为对照，不作为实盘可执行排名依据。",
        "",
        "## 最佳结果",
        "",
        f"- live-realistic PF 最佳：`tp_atr={best_live['tp_atr']:.2f}`，PF `{num(float(best_live['live_profit_factor']))}`，总收益 `{pct(float(best_live['live_total_return']))}`，最大回撤 `{pct(float(best_live['live_max_dd']))}`，锁仓期止盈率 `{pct(float(best_live['live_target_lockout_rate']))}`。",
        f"- 旧 stop 价成交 PF 最佳：`tp_atr={best_old['tp_atr']:.2f}`，PF `{num(float(best_old['old_profit_factor']))}`，总收益 `{pct(float(best_old['old_total_return']))}`，最大回撤 `{pct(float(best_old['old_max_dd']))}`。",
        "",
        "## Live-Realistic Top 10",
        "",
        "| tp_atr | 交易数 | PF | 胜率 | payoff | 总收益 | 最大回撤 | 锁仓期止盈率 | 总止盈率 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in top_live.to_dict(orient="records"):
        lines.append(
            f"| `{float(row['tp_atr']):.2f}` | `{int(row['live_trades'])}` | `{num(float(row['live_profit_factor']))}` | "
            f"`{pct(float(row['live_win_rate']))}` | `{num(float(row['live_payoff_ratio']))}` | "
            f"`{pct(float(row['live_total_return']))}` | `{pct(float(row['live_max_dd']))}` | "
            f"`{pct(float(row['live_target_lockout_rate']))}` | `{pct(float(row['live_target_total_rate']))}` |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "如果只问这组网格里哪个 ATR 最好，答案是 `2.5ATR`，但它的 live-realistic PF 只有约 `0.615`，仍远低于 `1`。",
            "",
            "小止盈如 `0.25ATR/0.5ATR` 虽然锁仓期止盈率高，但 payoff 太差；大止盈逐渐退化回原始策略，仍受解锁后 crossed stop 市价退出拖累。整个 `0.25ATR` 到 `12ATR` 网格没有任何 live-realistic 可用点。",
            "",
            "因此，V3.3 的问题不是即时止盈倍数没调准，而是剩余未止盈交易的解锁后退出状态机本身是负期望。",
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_immediate_tp_grid.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 网格 CSV：`{GRID_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    cfg = v33.V33_CONFIG
    raw = load_all_hype_5m()
    frame = v33.add_minimal_features(raw, cfg)
    signal = v33.build_signal(frame, cfg)
    grid = search_grid(frame, signal, cfg)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    grid.to_csv(GRID_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(grid), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V3.3",
                "audit": "immediate_tp_atr_grid",
                "grid": grid.to_dict(orient="records"),
                "outputs": {"markdown": str(MARKDOWN_PATH), "grid_csv": str(GRID_PATH)},
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    best_live = grid.sort_values(["live_profit_factor", "live_total_return"], ascending=False).head(10)
    print(best_live.to_string(index=False))
    print(f"markdown={MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
