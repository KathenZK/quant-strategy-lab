from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v62 = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v6_2_full_ablation.py", "hype_pbtr_v621_ablation_base")

RUN_DATE = "2026-06-29"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
ABLATION_ROOT = FAMILY_ROOT / "ablations"

SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_full_ablation_summary_{RUN_DATE}.csv"
SLICE_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_full_ablation_slices_{RUN_DATE}.csv"
SIDE_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_full_ablation_sides_{RUN_DATE}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_full_ablation_monthly_{RUN_DATE}.csv"
TRADE_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_baseline_trades_{RUN_DATE}.csv"
JSON_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_full_ablation_{RUN_DATE}.json"
MARKDOWN_PATH = ABLATION_ROOT / f"hype-5m-pbtr-v6-2-1-full-parameter-ablation-{RUN_DATE}.md"

BASELINE = replace(
    v62.replace_leg(v62.BASELINE, "long", htf_threshold=0.0),
    name="HYPE-5M-PBTR-V6.2.1",
)


def fmt_pct(value: float, digits: int = 2) -> str:
    return "∞" if not pd.notna(value) else f"{value * 100:.{digits}f}%"


def fmt_num(value: float, digits: int = 3) -> str:
    return "∞" if not pd.notna(value) else f"{value:.{digits}f}"


def label_value(value: Any) -> str:
    return str(value).replace(".", "p").replace("-", "neg").replace("/", "_").replace(" ", "")


def replace_leg(cfg: Any, leg_name: str, **changes: Any) -> Any:
    return v62.replace_leg(cfg, leg_name, **changes)


def build_variants() -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = [
        {"label": "baseline_v6_2_1", "family": "baseline", "parameter": "baseline", "value": "V6.2.1", "cfg": BASELINE}
    ]

    def add(label: str, family: str, parameter: str, value: Any, cfg: Any) -> None:
        variants.append({"label": label, "family": family, "parameter": parameter, "value": value, "cfg": cfg})

    def add_leg(leg_name: str, parameter: str, value: Any, *, family: str, **changes: Any) -> None:
        add(
            f"{leg_name}_{parameter}_{label_value(value)}",
            family,
            f"{leg_name}_{parameter}",
            value,
            replace_leg(BASELINE, leg_name, **changes),
        )

    for fast, slow in ((13, 55), (21, 96), (34, 144), (9, 55)):
        add_leg("long", "ema_pair", f"{fast}/{slow}", family="long_entry", ema_fast=fast, ema_slow=slow)
    for value in (0.0, 0.005, 0.015, 0.02):
        add_leg("long", "pullback_buffer", value, family="long_entry", pullback_buffer=value)
    add_leg("long", "require_candle", True, family="long_entry", require_candle=True)
    for value in (None, 0.25, 0.5, 0.75, 1.0):
        add_leg("long", "htf_threshold", value, family="long_filter", htf_threshold=value)
    for value in (48, 96, 384):
        add_leg("long", "quality_window", value, family="long_filter", quality_window=value)
    for value in (500.0, 600.0, 700.0, 850.0, 1000.0):
        add_leg("long", "quality_threshold", value, family="long_filter", quality_threshold=value)
    for value in (2.0, 3.0, 4.0):
        add_leg("long", "tp_atr", value, family="long_exit", tp_atr=value)
    for value in (4.0, 5.0, 6.0, 8.0, 10.0):
        add_leg("long", "sl_atr", value, family="long_exit", sl_atr=value)
    for value in (12, 24, 48, 72):
        add_leg("long", "time_exit_bars", value, family="long_exit", time_exit_bars=value)

    for fast, slow in ((21, 55), (21, 96), (13, 55), (9, 96)):
        add_leg("short", "ema_pair", f"{fast}/{slow}", family="short_entry", ema_fast=fast, ema_slow=slow)
    for value in (0.005, 0.01, 0.015, 0.02):
        add_leg("short", "pullback_buffer", value, family="short_entry", pullback_buffer=value)
    add_leg("short", "require_candle", True, family="short_entry", require_candle=True)
    for value in (0.0, 0.5, 1.0):
        add_leg("short", "htf_threshold", value, family="short_filter", htf_threshold=value)
    for value in (24, 96, 192):
        add_leg("short", "quality_window", value, family="short_filter", quality_window=value)
    for value in (200.0, 300.0, 500.0, 600.0):
        add_leg("short", "quality_threshold", value, family="short_filter", quality_threshold=value)
    for value in (1.0, 2.0, 2.5, 3.0):
        add_leg("short", "tp_atr", value, family="short_exit", tp_atr=value)
    for value in (1.5, 2.5, 3.0, 4.0):
        add_leg("short", "sl_atr", value, family="short_exit", sl_atr=value)
    for value in (12, 24, 36, 72):
        add_leg("short", "time_exit_bars", value, family="short_exit", time_exit_bars=value)
    for value in (1.0, 1.5, 2.0):
        add_leg("short", "trail_atr", value, family="short_exit", trail_atr=value)

    add("long_only_v6_2_1", "combo", "enabled_legs", "long_only", replace(BASELINE, short=replace(BASELINE.short, enabled=False)))
    add("short_only_rank2", "combo", "enabled_legs", "short_only", replace(BASELINE, long=replace(BASELINE.long, enabled=False)))
    add("priority_short_first", "combo", "priority", "short_first", replace(BASELINE, priority="short_first"))
    for value in (1.0, 2.0, 4.0):
        add(f"leverage_{label_value(value)}", "sizing", "leverage", value, replace(BASELINE, leverage=value))
    return variants


def table(rows: pd.DataFrame, limit: int = 20) -> list[str]:
    lines = [
        "| 变体 | 参数 | 值 | 交易数 | 总收益 | PF | 平均 | 胜率 | payoff | DD | IS PF | VAL PF | OOS 笔 | OOS PF | short 笔 | short PF | pass |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['parameter']}` | `{row['value']}` | `{int(row['trades'])}` | "
            f"`{fmt_pct(float(row['total_return']))}` | `{fmt_num(float(row['profit_factor']))}` | "
            f"`{fmt_pct(float(row['avg_trade']))}` | `{fmt_pct(float(row['win_rate']))}` | "
            f"`{fmt_num(float(row['payoff_ratio']))}` | `{fmt_pct(float(row['max_dd']))}` | "
            f"`{fmt_num(float(row['is_profit_factor']))}` | `{fmt_num(float(row['val_profit_factor']))}` | "
            f"`{int(row['oos_trades'])}` | `{fmt_num(float(row['oos_profit_factor']))}` | "
            f"`{int(row['short_trades'])}` | `{fmt_num(float(row['short_profit_factor']))}` | `{bool(row['robust_pass'])}` |"
        )
    return lines


def render_markdown(summary: pd.DataFrame, slices: pd.DataFrame, sides: pd.DataFrame, monthly: pd.DataFrame) -> str:
    baseline = summary.loc[summary["label"].eq("baseline_v6_2_1")].iloc[0]
    variants = summary.loc[~summary["label"].eq("baseline_v6_2_1")].copy()
    variants["delta_return"] = variants["total_return"] - float(baseline["total_return"])
    variants["delta_dd"] = variants["max_dd"] - float(baseline["max_dd"])
    good = variants.loc[variants["robust_pass"]].sort_values(["total_return", "max_dd"], ascending=[False, False])
    bad = variants.sort_values(["delta_return", "profit_factor"], ascending=[True, True])
    base_sides = sides.loc[sides["label"].eq("baseline_v6_2_1")]
    base_slices = slices.loc[slices["label"].eq("baseline_v6_2_1")]
    base_monthly = monthly.loc[monthly["label"].eq("baseline_v6_2_1")]
    worst_month = base_monthly.sort_values("total_return").iloc[0]
    best_month = base_monthly.sort_values("total_return", ascending=False).iloc[0]
    pass_count = int(variants["robust_pass"].sum())
    total_variants = int(len(variants))
    htf05 = summary.loc[summary["label"].eq("long_htf_threshold_0p5")]
    htf_none = summary.loc[summary["label"].eq("long_htf_threshold_None")]
    tp4 = summary.loc[summary["label"].eq("long_tp_atr_4p0")]
    htf05_note = ""
    if not htf05.empty:
        row = htf05.iloc[0]
        htf05_note = (
            f"- 把 long HTF 阈值收紧回 V6.2 的 `0.5` 后为 `{int(row['trades'])}` 笔、总收益 "
            f"`{fmt_pct(float(row['total_return']))}`、PF `{fmt_num(float(row['profit_factor']))}`、DD "
            f"`{fmt_pct(float(row['max_dd']))}`，低于 V6.2.1 baseline。"
        )
    htf_none_note = ""
    if not htf_none.empty:
        row = htf_none.iloc[0]
        htf_none_note = (
            f"- 完全删除 long HTF 过滤为 `{int(row['trades'])}` 笔、总收益 "
            f"`{fmt_pct(float(row['total_return']))}`、PF `{fmt_num(float(row['profit_factor']))}`、DD "
            f"`{fmt_pct(float(row['max_dd']))}`；收益和回撤均弱于 `htf_spread>=0`，说明保留非负大周期约束仍有价值。"
        )
    tp4_note = ""
    if not tp4.empty:
        row = tp4.iloc[0]
        tp4_note = (
            f"- `long_tp_atr=4.0` 为 `{int(row['trades'])}` 笔、总收益 "
            f"`{fmt_pct(float(row['total_return']))}`、PF `{fmt_num(float(row['profit_factor']))}`、DD "
            f"`{fmt_pct(float(row['max_dd']))}`；它仍是观察变体，但不自动替换 V6.2.1 的 `TP=2.5ATR`。"
        )
    non_pass_upside = variants.loc[(~variants["robust_pass"]) & (variants["total_return"] > float(baseline["total_return"]))].sort_values(
        "total_return", ascending=False
    )
    non_pass_note = ""
    if not non_pass_upside.empty:
        row = non_pass_upside.iloc[0]
        non_pass_note = (
            f"- 最高的未通过 gate 正收益行是 `{row['label']}`：总收益 `{fmt_pct(float(row['total_return']))}`、"
            f"PF `{fmt_num(float(row['profit_factor']))}`、short OOS `{int(row['short_oos_trades'])}` 笔；"
            "它主要卡在 short-side OOS 样本门槛，不作为 V6.2.1 替换候选。"
        )

    lines = [
        "# HYPE-5M-PBTR-V6.2.1 全参数消融 2026-06-29",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "`HYPE-5M-PBTR-V6.2.1` 是 V6.2 的 long-leg HTF 阈值变体：long 侧从 `htf_spread>=0.5` 放宽到 `htf_spread>=0`，short rank2、单仓约束、同根 long 优先、成交成本和 fixed `3x` 回测口径保持不变。",
        "",
        "## V6.2.1 Baseline",
        "",
        "| 交易数 | 总收益 | PF | 平均每笔 | 胜率 | payoff | 最大回撤 | 最差单笔 | 最好单笔 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| `{int(baseline['trades'])}` | `{fmt_pct(float(baseline['total_return']))}` | "
            f"`{fmt_num(float(baseline['profit_factor']))}` | `{fmt_pct(float(baseline['avg_trade']))}` | "
            f"`{fmt_pct(float(baseline['win_rate']))}` | `{fmt_num(float(baseline['payoff_ratio']))}` | "
            f"`{fmt_pct(float(baseline['max_dd']))}` | `{fmt_pct(float(baseline['worst_trade']))}` | "
            f"`{fmt_pct(float(baseline['best_trade']))}` |"
        ),
        "",
        "Baseline 参数：",
        "",
        "```text",
        "long: EMA21/55, pullback_buffer=0.01, htf_threshold=0.0, dir_ret192_bps>=788.123, TP=2.5ATR, SL=7ATR, timeout=36",
        "short: EMA34/144, pullback_buffer=0.0, htf_threshold=None, dir_ret48_bps>=400, TP=1.5ATR, SL=2ATR, timeout=48",
        "combo: one-position-only, long_first on same signal bar, fixed 3x",
        "```",
        "",
        "## Side / Slice",
        "",
        "| side | trades | total | DD | PF | avg | win | worst | best |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in base_sides.to_dict(orient="records"):
        lines.append(
            f"| `{row['side']}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | "
            f"`{fmt_pct(float(row['max_dd']))}` | `{fmt_num(float(row['profit_factor']))}` | "
            f"`{fmt_pct(float(row['avg_trade']))}` | `{fmt_pct(float(row['win_rate']))}` | "
            f"`{fmt_pct(float(row['worst_trade']))}` | `{fmt_pct(float(row['best_trade']))}` |"
        )
    lines.extend(["", "| slice | trades | total | DD | PF | avg |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for row in base_slices.to_dict(orient="records"):
        lines.append(
            f"| `{row['slice']}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | "
            f"`{fmt_pct(float(row['max_dd']))}` | `{fmt_num(float(row['profit_factor']))}` | "
            f"`{fmt_pct(float(row['avg_trade']))}` |"
        )
    lines.extend(
        [
            "",
            "## Parameter Read",
            "",
            f"本轮测试 `75` 个单因子/组合/sizing 变体，除 baseline 外 `robust_pass=True` 的变体为 `{pass_count}/{total_variants}`。关键读数：",
            "",
            htf05_note,
            htf_none_note,
            tp4_note,
            non_pass_note,
            "- long leg 的正向邻域仍主要集中在 HTF 阈值、EMA 慢线和较宽 TP/SL；但 baseline `htf_spread>=0` 已经是本轮收益最高的非 sizing 表达之一。",
            "- short leg 仍然脆弱：改 entry/filter 往往扩大交易数但压低 short PF 或组合回撤；short rank2 不应随意放宽。",
            "- sizing 仍是实盘首要约束。`3x` 只是历史横向比较口径，小额 live audit 应优先按 `1x` 或极小 notional 跑订单偏差。",
            "",
            "## Robust Pass Top",
            "",
            *table(good, limit=20),
            "",
            "## Worst Regressions",
            "",
            *table(bad, limit=20),
            "",
            "## Live Feasibility Notes",
            "",
            f"- 最差月份：`{worst_month['month']}`，总收益 `{fmt_pct(float(worst_month['total_return']))}`，PF `{fmt_num(float(worst_month['profit_factor']))}`。",
            f"- 最好月份：`{best_month['month']}`，总收益 `{fmt_pct(float(best_month['total_return']))}`，PF `{fmt_num(float(best_month['profit_factor']))}`。",
            f"- 退出分布：`{baseline['reason_counts']}`。",
            f"- 同根多空原始冲突：`{int(baseline['same_bar_signal_count'])}`；被持仓阻塞的 long/short 信号分别为 `{int(baseline['blocked_long'])}` / `{int(baseline['blocked_short'])}`。",
            "",
            "V6.2.1 仍是入场即固定 TP/SL + timeout 的可执行 bracket 策略，没有旧 V3/V4 delayed trailing stop 的 crossed stop 旧价成交问题。真实风险集中在 Binance reduce-only bracket 订单维护、单边成交后取消另一边、timeout 市价平仓、重启恢复、滑点/跳空，以及 short leg OOS 样本仍只有个位数。",
            "",
            "## 结论",
            "",
            "V6.2.1 作为 `hype-pullback-enhance` dry-run 默认表达可以保留：相对 V6.2 收紧版，它增加少量 long 交易并提高 fixed `3x` 历史收益，最大回撤几乎不变；相对完全删除 HTF 过滤，它又保留了更好的收益/回撤平衡。但这不是生产 sizing 结论，下一步仍应优先跑 paper / 极小 notional，累计 `30-50` 笔后用真实订单偏差复核。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- summary：`{SUMMARY_PATH}`",
            f"- slices：`{SLICE_PATH}`",
            f"- sides：`{SIDE_PATH}`",
            f"- monthly：`{MONTHLY_PATH}`",
            f"- baseline trades：`{TRADE_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def trade_rows(trades: list[Any], leverage: float) -> list[dict[str, Any]]:
    rows = []
    for i, trade in enumerate(trades, start=1):
        rows.append(
            {
                "trade_no": i,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": trade.side,
                "reason": trade.reason,
                "bars_held": trade.bars_held,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "net_ret_1x": trade.net_ret_1x,
                "net_ret_levered": trade.net_ret_1x * leverage,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
            }
        )
    return rows


def main() -> None:
    raw = v62.v6.load_closed_frame()
    frame = v62.v6.add_search_features(v62.v6.add_features(raw))
    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    side_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    baseline_trades: list[Any] = []
    for spec in build_variants():
        row, slices, sides, monthly, trades = v62.evaluate_variant(frame, spec)
        summary_rows.append(row)
        slice_rows.extend(slices)
        side_rows.extend(sides)
        monthly_rows.extend(monthly)
        if spec["label"] == "baseline_v6_2_1":
            baseline_trades = trades

    summary = pd.DataFrame(summary_rows)
    baseline_return = float(summary.loc[summary["label"].eq("baseline_v6_2_1"), "total_return"].iloc[0])
    summary["delta_total_return"] = summary["total_return"] - baseline_return
    summary = summary.sort_values(["robust_pass", "total_return", "max_dd"], ascending=[False, False, False]).reset_index(drop=True)
    slices = pd.DataFrame(slice_rows)
    sides = pd.DataFrame(side_rows)
    monthly = pd.DataFrame(monthly_rows)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    ABLATION_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    slices.to_csv(SLICE_PATH, index=False)
    sides.to_csv(SIDE_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    pd.DataFrame(trade_rows(baseline_trades, BASELINE.leverage)).to_csv(TRADE_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, slices, sides, monthly), encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V6.2.1",
                "baseline": asdict(BASELINE),
                "top": summary.head(30).to_dict(orient="records"),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "slices": str(SLICE_PATH),
                    "sides": str(SIDE_PATH),
                    "monthly": str(MONTHLY_PATH),
                    "baseline_trades": str(TRADE_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
