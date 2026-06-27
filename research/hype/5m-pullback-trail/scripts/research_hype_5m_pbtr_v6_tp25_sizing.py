from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v6 = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v6_full_ablation.py", "hype_pbtr_v6_full_for_sizing")

RUN_DATE = "2026-06-27"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6_tp25_sizing_summary_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6_tp25_sizing_trades_{RUN_DATE}.csv"
REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6_tp25_sizing_{RUN_DATE}.json"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v6-tp25-sizing-{RUN_DATE}.md"


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


def fmt_mult(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.2f}x"


def equity_metrics(returns: np.ndarray, leverages: np.ndarray) -> dict[str, float]:
    leveraged = returns * leverages
    equity = np.cumprod(1.0 + leveraged)
    equity_with_start = np.r_[1.0, equity]
    peak = np.maximum.accumulate(equity_with_start)
    dd = equity_with_start / peak - 1.0
    wins = leveraged[leveraged > 0]
    losses = leveraged[leveraged < 0]
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    return {
        "trades": float(len(leveraged)),
        "total_return": float(equity[-1] - 1.0) if len(equity) else 0.0,
        "max_dd": float(dd.min()) if len(dd) else 0.0,
        "avg_trade": float(leveraged.mean()) if len(leveraged) else 0.0,
        "win_rate": float((leveraged > 0).mean()) if len(leveraged) else 0.0,
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else np.inf,
        "payoff_ratio": float(wins.mean() / -losses.mean()) if len(wins) and len(losses) else np.inf,
        "worst_trade": float(leveraged.min()) if len(leveraged) else 0.0,
        "best_trade": float(leveraged.max()) if len(leveraged) else 0.0,
        "avg_leverage": float(leverages.mean()) if len(leverages) else 0.0,
        "min_leverage": float(leverages.min()) if len(leverages) else 0.0,
        "max_leverage": float(leverages.max()) if len(leverages) else 0.0,
        "ruin_trades": float((leveraged <= -1.0).sum()),
    }


def leverage_for_scheme(scheme: str, atr_ratio: np.ndarray) -> np.ndarray:
    if scheme == "fixed_1x":
        return np.ones(len(atr_ratio), dtype="float64")
    if scheme == "fixed_3x":
        return np.full(len(atr_ratio), 3.0, dtype="float64")
    if scheme == "vol_target1_floor0p5_cap3":
        return np.clip(3.0 / atr_ratio, 0.5, 3.0)
    if scheme == "vol_target1_floor1_cap3":
        return np.clip(3.0 / atr_ratio, 1.0, 3.0)
    if scheme == "vol_target0p8_floor0p5_cap3":
        return np.clip(3.0 * 0.8 / atr_ratio, 0.5, 3.0)
    if scheme == "vol_target0p8_floor1_cap3":
        return np.clip(3.0 * 0.8 / atr_ratio, 1.0, 3.0)
    raise ValueError(f"unknown scheme {scheme}")


def build_trade_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    cfg = replace(v6.BASELINE, tp_atr=2.5)
    signal, raw_signal_count = v6.build_filtered_signal(frame, cfg)
    trades = v6.simulate_live_orders(frame, signal, v6.signal_spec(cfg), v6.exit_spec(cfg), label="V6_tp25")
    features = frame.set_index(pd.to_datetime(frame["ts"], utc=True))
    rows: list[dict[str, Any]] = []
    for trade in trades:
        signal_ts = pd.Timestamp(trade.signal_ts)
        feature_row = features.loc[signal_ts]
        rows.append(
            {
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "reason": trade.reason,
                "bars_held": trade.bars_held,
                "net_ret_1x": trade.net_ret_1x,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                "atr_ratio_14_96": float(feature_row["atr_ratio_14_96"]),
                "atr_bps": float(feature_row["atr_bps"]),
                "dir_ret192_bps": float(feature_row["dir_ret192_bps"]) if "dir_ret192_bps" in feature_row else np.nan,
            }
        )
    return pd.DataFrame(rows), {"cfg": asdict(cfg), "raw_signal_count": raw_signal_count, "filtered_signal_count": int(np.count_nonzero(signal))}


def render_markdown(summary: pd.DataFrame, trade_frame: pd.DataFrame, metadata: dict[str, Any]) -> str:
    lines = [
        "# HYPE-5M-PBTR-V6 TP2.5 sizing 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告测试用户提出的 sizing 方向：在 V6 上采用 `tp_atr=2.5`，再比较固定 `1x`、固定 `3x`，以及以 `3x` 为上限的波动率动态仓位。",
        "",
        "## 口径",
        "",
        "- 策略：V6 long-only，`EMA21/55`、`pullback_buffer=0.01`、`dir_ret192_bps>=788.123`。",
        "- 出口：`TP=2.5ATR14`、`SL=7ATR14`、不 trailing、`36` 根 5m K 超时。",
        "- 动态仓位：使用信号 K 的 `atr_ratio_14_96 = ATR14 / mean(ATR14, 96)`；波动越高，杠杆越低。",
        "- 这是逐笔收益的 sizing replay，不额外模拟高杠杆下的滑点恶化、保证金约束或强平机制。",
        "",
        f"原始信号数：`{metadata['raw_signal_count']}`；过滤后信号数：`{metadata['filtered_signal_count']}`；实际交易数：`{len(trade_frame)}`。",
        "",
        "## 结果",
        "",
        "| sizing | total | max DD | avg/trade | win | PF | payoff | worst | best | avg lev | lev range |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary.to_dict(orient="records"):
        lines.append(
            f"| `{row['scheme']}` | `{fmt_pct(float(row['total_return']))}` | `{fmt_pct(float(row['max_dd']))}` | "
            f"`{fmt_pct(float(row['avg_trade']))}` | `{fmt_pct(float(row['win_rate']))}` | `{fmt_num(float(row['profit_factor']))}` | "
            f"`{fmt_num(float(row['payoff_ratio']))}` | `{fmt_pct(float(row['worst_trade']))}` | `{fmt_pct(float(row['best_trade']))}` | "
            f"`{fmt_mult(float(row['avg_leverage']))}` | `{fmt_mult(float(row['min_leverage']))}-{fmt_mult(float(row['max_leverage']))}` |"
        )
    best_dd = summary.loc[summary["scheme"].eq("fixed_1x"), "max_dd"].iloc[0]
    fixed3 = summary.loc[summary["scheme"].eq("fixed_3x")].iloc[0]
    best_dyn = summary.loc[summary["scheme"].str.startswith("vol_")].sort_values(["total_return", "max_dd"], ascending=[False, False]).iloc[0]
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"`tp_atr=2.5` 的 1x 回撤约 `{fmt_pct(float(best_dd))}`，比 V6 原始 `TP=3ATR` 的主账回撤更低；固定 `3x` 将总收益放大到 `{fmt_pct(float(fixed3['total_return']))}`，但最大回撤也扩大到 `{fmt_pct(float(fixed3['max_dd']))}`。",
            "",
            f"本轮动态仓位里收益最高的是 `{best_dyn['scheme']}`，总收益 `{fmt_pct(float(best_dyn['total_return']))}`、最大回撤 `{fmt_pct(float(best_dyn['max_dd']))}`、平均杠杆 `{fmt_mult(float(best_dyn['avg_leverage']))}`。它相比固定 `3x` 主要是稍微降低高波动入场的仓位，但没有把回撤压回 1x 级别。",
            "",
            "因此，`tp_atr=2.5 + 3x` 在回测里收益很漂亮，但已是高风险 sizing；波动率动态仓位能改善一点风险形态，却不是免费午餐。实盘前仍应先 paper audit 30-50 笔，确认滑点和 bracket 维护没有偏差。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- summary CSV：`{SUMMARY_PATH}`",
            f"- trades CSV：`{TRADES_PATH}`",
            f"- JSON：`{REPORT_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v6.load_closed_frame()
    frame = v6.add_required_features(raw)
    trade_frame, metadata = build_trade_frame(frame)
    returns = trade_frame["net_ret_1x"].to_numpy("float64")
    atr_ratio = trade_frame["atr_ratio_14_96"].to_numpy("float64")

    rows: list[dict[str, Any]] = []
    for scheme in (
        "fixed_1x",
        "fixed_3x",
        "vol_target1_floor0p5_cap3",
        "vol_target1_floor1_cap3",
        "vol_target0p8_floor0p5_cap3",
        "vol_target0p8_floor1_cap3",
    ):
        leverages = leverage_for_scheme(scheme, atr_ratio)
        row = {"scheme": scheme, **equity_metrics(returns, leverages)}
        rows.append(row)
        trade_frame[f"leverage_{scheme}"] = leverages
        trade_frame[f"net_ret_{scheme}"] = returns * leverages

    summary = pd.DataFrame(rows)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    trade_frame.to_csv(TRADES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, trade_frame, metadata), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V6",
                "audit": "tp25_sizing",
                "metadata": metadata,
                "summary": summary.to_dict(orient="records"),
                "outputs": {"markdown": str(MARKDOWN_PATH), "summary": str(SUMMARY_PATH), "trades": str(TRADES_PATH)},
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
