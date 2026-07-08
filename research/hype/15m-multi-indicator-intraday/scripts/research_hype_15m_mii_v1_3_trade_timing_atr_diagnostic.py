from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_v1_2_atr_bracket_exit as v12  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402
from research_hype_15m_mii_search import ROUND_TRIP_COST  # noqa: E402


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.3"
RUN_DATE = "2026-07-06"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_3_trade_timing_atr_diagnostic.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
MONTHLY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_trade_timing_monthly_2026-07-06.csv"
QUARTER_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_trade_timing_quarter_2026-07-06.csv"
TRADES_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_trade_timing_trades_2026-07-06.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_trade_timing_atr_2026-07-06.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-3-trade-timing-atr-2026-07-06.md"

ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))
V13_EXPOSURE = 2.5
V13_CANDIDATE = v12.AtrBracketCandidate(
    label="atr96_tp1p25x_sl5x_hold24",
    family="atr_bracket",
    atr_window=96,
    tp_atr_mult=1.25,
    sl_atr_mult=5.0,
    max_hold_bars=24,
)


def net_return_decimal(trade: Any) -> float:
    return float(V13_EXPOSURE * (trade.raw_return - ROUND_TRIP_COST))


def compound_pct(values: list[float]) -> float:
    if not values:
        return 0.0
    return float((np.prod([1.0 + value for value in values]) - 1.0) * 100.0)


def trade_rows_for_entry(context: v12.evolution.EvalContext, entry_delay_bars: int, entry_label: str) -> pd.DataFrame:
    raw_trades = v12.simulate_atr_bracket_trades(
        context,
        V13_CANDIDATE,
        entry_delay_bars=entry_delay_bars,
    )
    selected = v1.selected_trades_live(raw_trades, v12.BASE_CONFIG.filter)
    rows: list[dict[str, Any]] = []
    for trade in selected:
        net_return = net_return_decimal(trade)
        rows.append(
            {
                "entry_timing": entry_label,
                "signal_ts": pd.Timestamp(context.features["ts"].iloc[trade.signal_i]).isoformat(),
                "entry_ts": pd.Timestamp(trade.entry_ts).isoformat(),
                "exit_ts": pd.Timestamp(trade.exit_ts).isoformat(),
                "month": pd.Timestamp(trade.entry_ts).strftime("%Y-%m"),
                "quarter": f"{pd.Timestamp(trade.entry_ts).year}Q{pd.Timestamp(trade.entry_ts).quarter}",
                "direction": "long" if trade.direction == 1 else "short",
                "atr_pct96": float(trade.atr_pct96),
                "rvol96": float(trade.rvol96),
                "dir_macd": float(trade.dir_macd),
                "raw_return_pct": float(trade.raw_return * 100.0),
                "net_return_pct": float(net_return * 100.0),
                "bars_held": int(trade.bars_held),
                "exit_reason": trade.exit_reason,
            }
        )
    return pd.DataFrame(rows)


def summarize_group(trades: pd.DataFrame, group_col: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if trades.empty:
        return pd.DataFrame(rows)
    for (entry_timing, group_value), group in trades.groupby(["entry_timing", group_col], sort=True):
        net_values = (group["net_return_pct"].astype(float) / 100.0).tolist()
        atr_values = group["atr_pct96"].astype(float)
        rows.append(
            {
                "entry_timing": entry_timing,
                group_col: group_value,
                "trades": int(len(group)),
                "total_return_pct_compounded": compound_pct(net_values),
                "avg_trade_pct": float(group["net_return_pct"].mean()),
                "win_rate_pct": float((group["net_return_pct"] > 0).mean() * 100.0),
                "atr_pct96_median": float(atr_values.median()),
                "atr_pct96_p25": float(atr_values.quantile(0.25)),
                "atr_pct96_p75": float(atr_values.quantile(0.75)),
                "min_entry_ts": str(group["entry_ts"].min()),
                "max_entry_ts": str(group["entry_ts"].max()),
            }
        )
    return pd.DataFrame(rows)


def feature_monthly_atr(context: v12.evolution.EvalContext) -> pd.DataFrame:
    features = context.features.copy()
    features["month"] = features["ts"].dt.strftime("%Y-%m")
    rows: list[dict[str, Any]] = []
    for month, group in features.groupby("month", sort=True):
        atr = group["atr_pct96"].dropna().astype(float)
        if atr.empty:
            continue
        rows.append(
            {
                "month": month,
                "bars": int(len(group)),
                "atr_pct96_median_all_bars": float(atr.median()),
                "atr_pct96_p25_all_bars": float(atr.quantile(0.25)),
                "atr_pct96_p75_all_bars": float(atr.quantile(0.75)),
                "atr_ok_rate_pct_all_bars": float((atr >= 0.0075).mean() * 100.0),
            }
        )
    return pd.DataFrame(rows)


def merge_monthly(monthly_trades: pd.DataFrame, monthly_atr: pd.DataFrame) -> pd.DataFrame:
    if monthly_trades.empty:
        return monthly_trades
    return monthly_trades.merge(monthly_atr, on="month", how="left")


def fmt_pct(value: Any, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "-"
    return f"{float(value) * 100.0:.{digits}f}%"


def fmt_plain_pct(value: Any, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "-"
    return f"{float(value):.{digits}f}%"


def markdown_table(frame: pd.DataFrame, columns: list[str], labels: list[str]) -> list[str]:
    lines = [
        "| " + " | ".join(labels) + " |",
        "| " + " | ".join(["---"] + ["---:"] * (len(labels) - 1)) + " |",
    ]
    for row in frame.to_dict(orient="records"):
        cells: list[str] = []
        for column in columns:
            value = row.get(column)
            if column.startswith("atr_pct96_"):
                cells.append(f"`{fmt_pct(value, 3)}`")
            elif column == "atr_ok_rate_pct_all_bars":
                cells.append(f"`{fmt_plain_pct(value, 2)}`")
            elif column.endswith("_pct") or column.endswith("_pct_compounded"):
                cells.append(f"`{fmt_plain_pct(value, 2)}`")
            elif isinstance(value, (int, np.integer)):
                cells.append(f"`{int(value)}`")
            elif isinstance(value, (float, np.floating)):
                cells.append(f"`{float(value):.3f}`")
            else:
                cells.append(f"`{value}`")
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def render_markdown(
    monthly: pd.DataFrame,
    quarterly: pd.DataFrame,
    trades: pd.DataFrame,
    quality: dict[str, Any],
) -> str:
    k1_monthly = monthly.loc[monthly["entry_timing"].eq("K+1")].copy()
    k1_quarterly = quarterly.loc[quarterly["entry_timing"].eq("K+1")].copy()
    k1_trades = trades.loc[trades["entry_timing"].eq("K+1")].copy()
    first_entry = k1_trades["entry_ts"].min()
    last_entry = k1_trades["entry_ts"].max()
    last_90_start = pd.Timestamp(quality["last_ts"]) - pd.Timedelta(days=90)
    recent_trades = k1_trades.loc[pd.to_datetime(k1_trades["entry_ts"]) >= last_90_start]
    last_months = k1_monthly.tail(5)
    lines = [
        f"# HYPE-15M-MII V1.3 开单时间与 ATR96 诊断 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`{ALIAS}`）",
        "",
        "## 结论",
        "",
        "`ATR96` 不是小时 K，也不是 96 小时窗口；它是在 Binance HYPEUSDT 永续 `15m` K 上，用最近 `96` 根 `15m` true range 的简单均值除以 close，约等于最近 `24h` 的平均单根 15m 波动比例。",
        "",
        (
            f"`V1.3` K+1 回测并不是只在很早以前开单：标准数据湖样本从 `{quality['first_ts']}` 到 "
            f"`{quality['last_ts']}`，K+1 首笔入场 `{first_entry}`，最后一笔入场 `{last_entry}`；"
            f"最近 90 天仍有 `{len(recent_trades)}` 笔。"
        ),
        "",
        "不过，开单质量和频率确实跟 `ATR96%` regime 强相关：高开单/高收益月份大多发生在月内 `ATR96%` 过线率更高的阶段；6 月底以后当前行情进入低波动区，才出现近期信号枯竭。",
        "",
        "因此不应把 `0.75%` 理解成 HYPE “最近 96 小时波动不超过 0.75%”。它的意思是：过去 24 小时内，平均每根 15m K 的 true range 低于价格的 `0.75%` 时，当前 `V1.3` 不愿意交易。",
        "",
        "## K+1 月度开单",
        "",
        *markdown_table(
            k1_monthly,
            [
                "month",
                "trades",
                "total_return_pct_compounded",
                "win_rate_pct",
                "atr_pct96_median",
                "atr_ok_rate_pct_all_bars",
                "min_entry_ts",
                "max_entry_ts",
            ],
            ["月份", "交易数", "复利收益", "胜率", "入场 ATR96% 中位", "全月 ATR 过线率", "首笔", "末笔"],
        ),
        "",
        "## K+1 季度开单",
        "",
        *markdown_table(
            k1_quarterly,
            [
                "quarter",
                "trades",
                "total_return_pct_compounded",
                "win_rate_pct",
                "atr_pct96_median",
                "min_entry_ts",
                "max_entry_ts",
            ],
            ["季度", "交易数", "复利收益", "胜率", "入场 ATR96% 中位", "首笔", "末笔"],
        ),
        "",
        "## 最近几个月",
        "",
        *markdown_table(
            last_months,
            [
                "month",
                "trades",
                "total_return_pct_compounded",
                "win_rate_pct",
                "atr_pct96_median",
                "atr_ok_rate_pct_all_bars",
            ],
            ["月份", "交易数", "复利收益", "胜率", "入场 ATR96% 中位", "全月 ATR 过线率"],
        ),
        "",
        "## 状态",
        "",
        "本诊断解释 `V1.3` 的历史开单时间与 ATR regime，不改变 `NO-GO / not live-ready`。如果调整 `min_atr_pct96`，应重新做参数网格、K+1/K+2、滚动窗口、资金费和 live-executable 审计，而不是直接把门槛降到当前行情。",
        "",
        "## 产物",
        "",
        f"- 脚本：`{SCRIPT_PATH}`",
        f"- 月度 CSV：`{MONTHLY_CSV_PATH}`",
        f"- 季度 CSV：`{QUARTER_CSV_PATH}`",
        f"- 逐笔 CSV：`{TRADES_CSV_PATH}`",
        f"- JSON：`{JSON_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(child) for key, child in value.items()}
    if isinstance(value, list):
        return [json_safe(child) for child in value]
    if isinstance(value, tuple):
        return [json_safe(child) for child in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def main() -> None:
    context, metadata, quality = v12.build_context()
    trades = pd.concat(
        [
            trade_rows_for_entry(context, entry_delay_bars, entry_label)
            for entry_delay_bars, entry_label in ENTRY_DELAYS
        ],
        ignore_index=True,
    )
    monthly = merge_monthly(summarize_group(trades, "month"), feature_monthly_atr(context))
    quarterly = summarize_group(trades, "quarter")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(MONTHLY_CSV_PATH, index=False)
    quarterly.to_csv(QUARTER_CSV_PATH, index=False)
    trades.to_csv(TRADES_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(monthly, quarterly, trades, quality), encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            json_safe(
                {
                    "family": FAMILY,
                    "alias": ALIAS,
                    "version": VERSION,
                    "run_date": RUN_DATE,
                    "status": "trade_timing_atr_diagnostic_not_promoted",
                    "metadata": metadata,
                    "data_quality": quality,
                    "base_config": asdict(v12.BASE_CONFIG),
                    "v13_exposure": V13_EXPOSURE,
                    "atr_definition": "SMA(true_range, 96) / close on 15m candles; about 24h lookback",
                    "monthly": monthly.to_dict(orient="records"),
                    "quarterly": quarterly.to_dict(orient="records"),
                    "outputs": {
                        "markdown": str(MARKDOWN_PATH),
                        "monthly_csv": str(MONTHLY_CSV_PATH),
                        "quarter_csv": str(QUARTER_CSV_PATH),
                        "trades_csv": str(TRADES_CSV_PATH),
                    },
                }
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Monthly K+1")
    print(monthly.loc[monthly["entry_timing"].eq("K+1")].to_string(index=False))
    print("Quarterly K+1")
    print(quarterly.loc[quarterly["entry_timing"].eq("K+1")].to_string(index=False))
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
