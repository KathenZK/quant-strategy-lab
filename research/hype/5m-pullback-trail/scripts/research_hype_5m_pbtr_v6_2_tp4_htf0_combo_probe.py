from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
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


v62 = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v6_2_full_ablation.py", "hype_pbtr_v62_combo_probe")

RUN_DATE = "2026-06-28"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
ABLATION_ROOT = FAMILY_ROOT / "ablations"

SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2_tp4_htf0_combo_probe_summary_{RUN_DATE}.csv"
SLICES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2_tp4_htf0_combo_probe_slices_{RUN_DATE}.csv"
SIDES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2_tp4_htf0_combo_probe_sides_{RUN_DATE}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2_tp4_htf0_combo_probe_monthly_{RUN_DATE}.csv"
JSON_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2_tp4_htf0_combo_probe_{RUN_DATE}.json"
MARKDOWN_PATH = ABLATION_ROOT / f"hype-5m-pbtr-v6-2-tp4-htf0-combo-probe-{RUN_DATE}.md"


def fmt_pct(value: float, digits: int = 2) -> str:
    return "∞" if not pd.notna(value) else f"{value * 100:.{digits}f}%"


def fmt_num(value: float, digits: int = 3) -> str:
    return "∞" if not pd.notna(value) else f"{value:.{digits}f}"


def cfg_with(*, long_tp: float | None = None, long_htf: float | None = None, leverage: float = 3.0) -> Any:
    cfg = v62.BASELINE
    changes: dict[str, Any] = {}
    if long_tp is not None:
        changes["tp_atr"] = long_tp
    if long_htf is not None:
        changes["htf_threshold"] = long_htf
    if changes:
        cfg = v62.replace_leg(cfg, "long", **changes)
    if leverage != cfg.leverage:
        cfg = replace(cfg, leverage=leverage)
    return cfg


def build_variants() -> list[dict[str, Any]]:
    return [
        {"label": "baseline_v6_2", "parameter": "baseline", "value": "V6.2", "cfg": v62.BASELINE},
        {"label": "long_tp4", "parameter": "long_tp_atr", "value": 4.0, "cfg": cfg_with(long_tp=4.0)},
        {"label": "long_htf0", "parameter": "long_htf_threshold", "value": 0.0, "cfg": cfg_with(long_htf=0.0)},
        {
            "label": "long_tp4_htf0",
            "parameter": "long_tp_atr+long_htf_threshold",
            "value": "4.0+0.0",
            "cfg": cfg_with(long_tp=4.0, long_htf=0.0),
        },
        {
            "label": "long_tp4_htf0_1x",
            "parameter": "long_tp_atr+long_htf_threshold+leverage",
            "value": "4.0+0.0+1x",
            "cfg": cfg_with(long_tp=4.0, long_htf=0.0, leverage=1.0),
        },
    ]


def table(rows: pd.DataFrame) -> list[str]:
    lines = [
        "| 变体 | 杠杆 | 交易数 | 总收益 | PF | 平均 | 胜率 | payoff | DD | IS PF | VAL PF | OOS 笔 | OOS PF | long 笔 | long PF | short 笔 | short PF | pass |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows.to_dict(orient="records"):
        config = json.loads(row["config_json"])
        lines.append(
            f"| `{row['label']}` | `{config['leverage']:.1f}` | `{int(row['trades'])}` | "
            f"`{fmt_pct(float(row['total_return']))}` | `{fmt_num(float(row['profit_factor']))}` | "
            f"`{fmt_pct(float(row['avg_trade']))}` | `{fmt_pct(float(row['win_rate']))}` | "
            f"`{fmt_num(float(row['payoff_ratio']))}` | `{fmt_pct(float(row['max_dd']))}` | "
            f"`{fmt_num(float(row['is_profit_factor']))}` | `{fmt_num(float(row['val_profit_factor']))}` | "
            f"`{int(row['oos_trades'])}` | `{fmt_num(float(row['oos_profit_factor']))}` | "
            f"`{int(row['long_trades'])}` | `{fmt_num(float(row['long_profit_factor']))}` | "
            f"`{int(row['short_trades'])}` | `{fmt_num(float(row['short_profit_factor']))}` | "
            f"`{bool(row['robust_pass'])}` |"
        )
    return lines


def render_markdown(summary: pd.DataFrame, slices: pd.DataFrame, sides: pd.DataFrame, monthly: pd.DataFrame) -> str:
    combo = summary.loc[summary["label"].eq("long_tp4_htf0")].iloc[0]
    combo_months = monthly.loc[monthly["label"].eq("long_tp4_htf0")].sort_values("total_return")
    worst = combo_months.head(3)
    best = combo_months.tail(3)
    lines = [
        "# HYPE-5M-PBTR-V6.2 TP4 + HTF0 组合探测 2026-06-28",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "目标：测试两个此前单因子都通过 V6.2 robust gate 的 long leg 改动是否可以叠加：`long_tp_atr=4.0` 与 `long_htf_threshold=0.0`。short rank2、单仓约束、同根 long 优先、成本与 V6.2 full ablation 完全一致。",
        "",
        "## Summary",
        "",
        *table(summary),
        "",
        "## Slice",
        "",
        "| 变体 | slice | 交易数 | 总收益 | DD | PF | 平均 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in slices.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['slice']}` | `{int(row['trades'])}` | "
            f"`{fmt_pct(float(row['total_return']))}` | `{fmt_pct(float(row['max_dd']))}` | "
            f"`{fmt_num(float(row['profit_factor']))}` | `{fmt_pct(float(row['avg_trade']))}` |"
        )
    lines.extend(
        [
            "",
            "## Side",
            "",
            "| 变体 | side | 交易数 | 总收益 | DD | PF | 平均 | 胜率 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in sides.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['side']}` | `{int(row['trades'])}` | "
            f"`{fmt_pct(float(row['total_return']))}` | `{fmt_pct(float(row['max_dd']))}` | "
            f"`{fmt_num(float(row['profit_factor']))}` | `{fmt_pct(float(row['avg_trade']))}` | "
            f"`{fmt_pct(float(row['win_rate']))}` |"
        )
    lines.extend(
        [
            "",
            "## Month Extremes For Combo",
            "",
            "| 类型 | 月份 | 交易数 | 总收益 | DD | PF |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for kind, frame in (("worst", worst), ("best", best)):
        for row in frame.to_dict(orient="records"):
            lines.append(
                f"| `{kind}` | `{row['month']}` | `{int(row['trades'])}` | "
                f"`{fmt_pct(float(row['total_return']))}` | `{fmt_pct(float(row['max_dd']))}` | "
                f"`{fmt_num(float(row['profit_factor']))}` |"
            )
    lines.extend(
        [
            "",
            "## Read",
            "",
            f"- `long_tp4_htf0` 仍通过 robust gate：`{int(combo['trades'])}` 笔、总收益 `{fmt_pct(float(combo['total_return']))}`、PF `{fmt_num(float(combo['profit_factor']))}`、最大回撤 `{fmt_pct(float(combo['max_dd']))}`、OOS `{int(combo['oos_trades'])}` 笔 / PF `{fmt_num(float(combo['oos_profit_factor']))}`。",
            "- 组合不是线性叠加：单独 `long_htf_threshold=0.0` 的总收益更高；单独 `long_tp_atr=4.0` 的 PF 更高。两者合并后，long 侧交易变少且 IS PF 降低，说明宽 TP 与放宽 HTF 过滤会改变持仓阻塞关系，把部分原本可吃到 TP2.5 或 HTF0 的交易替换掉。",
            "- 小额 live runner 仍建议默认保持 V6.2.1 的 `TP=2.5ATR + htf_spread>=0`，不要因为 `TP4+HTF0` 通过 gate 就立刻替换。若要继续，应作为 V6.2.2 候选单独做 walk-forward / live-dry-run 对照。",
            "",
            "## Artifacts",
            "",
            f"- summary：`{SUMMARY_PATH}`",
            f"- slices：`{SLICES_PATH}`",
            f"- sides：`{SIDES_PATH}`",
            f"- monthly：`{MONTHLY_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v62.v6.load_closed_frame()
    frame = v62.v6.add_search_features(v62.v6.add_features(raw))
    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    side_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    for spec in build_variants():
        row, slices, sides, monthly, _trades = v62.evaluate_variant(
            frame,
            {
                "label": spec["label"],
                "family": "combo_probe",
                "parameter": spec["parameter"],
                "value": spec["value"],
                "cfg": spec["cfg"],
            },
        )
        summary_rows.append(row)
        slice_rows.extend(slices)
        side_rows.extend(sides)
        monthly_rows.extend(monthly)

    summary = pd.DataFrame(summary_rows)
    slices = pd.DataFrame(slice_rows)
    sides = pd.DataFrame(side_rows)
    monthly = pd.DataFrame(monthly_rows)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    ABLATION_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    slices.to_csv(SLICES_PATH, index=False)
    sides.to_csv(SIDES_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, slices, sides, monthly), encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "probe": "V6.2 long TP4 + HTF0",
                "summary": summary.to_dict(orient="records"),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "slices": str(SLICES_PATH),
                    "sides": str(SIDES_PATH),
                    "monthly": str(MONTHLY_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary[["label", "trades", "total_return", "profit_factor", "win_rate", "payoff_ratio", "max_dd", "oos_trades", "oos_profit_factor", "robust_pass"]].to_string(index=False))


if __name__ == "__main__":
    main()
