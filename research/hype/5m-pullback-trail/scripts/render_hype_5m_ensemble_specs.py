from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd


DOC_DIR = Path("research/hype/5m-pullback-trail/ensemble-specs")
SUMMARY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_ensemble_ablation_summary.csv")
DROP_LEG_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_ensemble_ablation_drop_leg.csv")
LEVERAGE_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_ensemble_ablation_leverage.csv")
EXECUTION_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_ensemble_ablation_execution.csv")
LEGS_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_ensemble_combo_legs.csv")

TARGET_COMBOS: tuple[tuple[str, int, float], ...] = (
    ("S01", 8, 4.0),
    ("S02", 16, 2.5),
    ("S03", 8, 3.0),
    ("S04", 12, 2.5),
    ("S05", 5, 3.0),
    ("S06", 16, 2.0),
    ("S07", 8, 2.5),
)

FEATURE_DEFINITIONS = """
## 指标计算定义

所有信号必须只使用已经收盘的 5m K 线。实盘代码至少预热 `800` 根 5m K，低于预热长度时不允许开仓。

- `EMA(span)`: `close.ewm(span=span, adjust=False, min_periods=span).mean()`；本批子腿用到 `12/21/34/55/96/144/192/384`。
- `ATR14/28/96/288`: `TR` 的简单滚动均值；`TR=max(high-low, abs(high-prev_close), abs(low-prev_close))`。
- `atr_ratio_14_96 = ATR14 / ATR96`；`atr_pct_96 = ATR96 / close`。
- `RSI14/28`: Wilder 风格 `ewm(alpha=1/window, adjust=False, min_periods=window)`。
- `MACD histogram`: `EMA12 - EMA26 - signal(EMA9)`。
- `CMF20`: 20 根 K 的 Chaikin Money Flow，分母为 20 根成交量滚动和。
- `OBV slope48`: `OBV.diff(48) / volume.rolling(96).sum()`。
- `Bollinger position`: 中轨 `SMA20`，标准差 `STD20`，`bb_pos20=(close-(mid-2*std))/(4*std)`。
- `bb_width_z192`: `bb_width20=4*std/mid` 后做 192 根滚动 z-score。
- `chop14`: 14 根 Choppiness Index。
- `eff96`: `abs(close.pct_change(96)) / rolling_sum(abs(close.pct_change()), 96)`。
- `rvol96`: `volume / volume.rolling(96).mean()`。
- `htf_spread`: `EMA96 - EMA384`，作为高阶趋势确认，不是真正 1h 重采样。
- `roc24/48/96`: `close.pct_change(window)`。
- `ADX14`: Wilder 风格 `+DI/-DI/DX` 后再 EWM 平滑。
- `regime_age`: 当前非零 EMA 方向已经持续的 5m bar 数。

方向归一化特征：

- `direction = sign(EMAfast - EMAslow)`。
- `side_mode=short` 时只允许 `direction=-1`；`side_mode=both` 时允许 `direction=1/-1`。
- `dir_rocN = direction * rocN`。
- `dir_rsi14 = RSI14` if `direction=1` else `100 - RSI14`。
- `dir_macd = direction * macd_hist`。
- `dir_cmf20 = direction * cmf20`。
- `dir_obv48 = direction * obv_slope48`。
- `dir_htf = direction * htf_spread`。
- `abs_dist_ema = abs(close / EMAfast - 1)`。
- `dir_dist_ema = direction * (close / EMAfast - 1)`。
""".strip()

SIGNAL_AND_EXECUTION_TEMPLATE = """
## 信号生成

### 组合层规则

本策略是一个 one-position ensemble：同一时间全局最多持有一笔仓位。每根 5m K 收盘后，按子腿排名从小到大扫描信号；如果多个子腿同一根 K 同时触发，只接受排名最靠前的子腿。已有仓位未平时，忽略所有新信号。

必须持久化这些状态：

- 当前仓位：`side / leg_rank / entry_ts / entry_price / stop_price / target_price / bars_held`。
- 每条子腿的 cooldown 截止 bar；本批子腿统一 `cooldown_bars=6`。
- 已处理过的 `(signal_ts, side)`，用于防止重启后重复开仓。

### 子腿通用过滤

每条子腿先计算自己的 `EMAfast/EMAslow` 和方向，然后必须满足：

- `direction != 0`。
- `0 <= regime_age <= 768`。
- `abs(close / EMAfast - 1) <= 0.12`。
- 因为本批只保留回归类子腿，所以 `dir_roc24 >= -0.03`。
- `dir_rsi14 <= 80`。
- `ADX14 >= 0`。
- `chop14 <= 100`。
- `atr_ratio_14_96 <= 2.0`。
- `rvol96 >= 0`。
- `dir_cmf20 >= -0.3`。
- `eff96 >= 0`。
- `require_htf=True`，所以 `dir_htf > 0`。

### 入场形态

`ema_deviation_revert`：

- 做多：`direction > 0`，`close / EMAfast - 1 <= -0.005`，且收盘价大于开盘价。
- 做空：`direction < 0`，`close / EMAfast - 1 >= 0.005`，且收盘价小于开盘价。

`bb_reversion`：

- 做多：`direction > 0`，`bb_pos20 <= 0.25`，且收盘价大于开盘价。
- 做空：`direction < 0`，`bb_pos20 >= 0.75`，且收盘价小于开盘价。

通过通用过滤和入场形态后，还必须通过该子腿自己的附加过滤条件。附加过滤条件见下方“子腿逐条规格”。

### 相邻重复信号抑制

单条子腿如果连续两根 bar 给出同方向信号，只保留第一根。实盘实现可以用 `last_leg_signal_side` 和上一根 bar 是否触发来复现。

## 买入/开仓规则

信号在 bar `t` 收盘后确认，回测在下一根 bar `t+1` 的开盘价成交。实盘代码没有“未来开盘价”，所以执行建议是：确认 bar 收盘后立即用市价单或可配置的 aggressive limit 单开仓，并把订单类型做成配置项。

- 做多开仓：买入 HYPE 永续；回测成交价为 `next_open * (1 + 0.0001)`。
- 做空开仓：卖出开空 HYPE 永续；回测成交价为 `next_open * (1 - 0.0001)`。
- 手续费假设：每边 `0.04%`。
- 滑点假设：每边 `0.01%`。
- 名义仓位：`position_notional = account_equity * strategy_leverage`。
- 数量：`quantity = position_notional / entry_price`，再按 Binance 精度和最小名义额截断。
- 建议实盘使用 isolated margin，并额外设置账户级最大亏损、最大名义仓位和熔断阈值；这些不是本回测的一部分。

## 持有规则

开仓后不加仓、不反手、不处理其他子腿的新信号。每根新 5m K 收盘或撮合事件后维护：

- 初始止损距离：`stop_atr * ATR14(signal_bar)`。
- 初始止盈距离：`tp_atr * ATR14(signal_bar)`。
- 本批子腿 `trail_atr=0`，所以没有移动止损。
- 本批子腿 `exit_ema=0`，所以没有 EMA 平仓。
- 持仓时间达到该子腿 `max_hold_bars` 时，按当前 bar 收盘价平仓。

## 卖出/平仓规则

做多：

- 止损价：`entry_price - stop_atr * ATR14(signal_bar)`。
- 止盈价：`entry_price + tp_atr * ATR14(signal_bar)`。
- 平仓方向：卖出 reduce-only。

做空：

- 止损价：`entry_price + stop_atr * ATR14(signal_bar)`。
- 止盈价：`entry_price - tp_atr * ATR14(signal_bar)`。
- 平仓方向：买入 reduce-only。

同一根 K 同时碰到止损和止盈时，回测按“止损优先”。实盘代码应同时挂 reduce-only 止损/止盈保护单；本地账务回放或风控审计也按止损优先对齐研究口径。

平仓后：

- 清空全局仓位。
- 触发该子腿 `cooldown_bars=6` 的冷却期。
- 记录 `exit_reason` 为 `stop / target / time / ema_exit`；本批理论上不会出现 `ema_exit`。
""".strip()

CODEGEN_CHECKLIST = """
## AI 生成实盘代码检查清单

- `compute_features(candles)` 必须完全按本文指标公式实现，并只使用已收盘 K 线。
- `build_leg_signal(leg, frame)` 必须返回 `-1 / 0 / 1`，并实现相邻重复信号抑制。
- `select_ensemble_signal(signals)` 必须按 `leg_rank` 优先级选择第一条信号。
- `open_position()` 必须记录子腿编号、信号时间、入场时间、ATR14、止损价、止盈价和杠杆。
- `manage_position()` 必须优先处理止损，再处理止盈，再处理时间止损。
- 所有订单必须带幂等 key，例如 `combo_id + signal_ts + side + leg_rank`。
- 重启后必须从持久化状态恢复当前仓位、冷却状态和已处理 signal key。
- 不允许在未完成 warmup、指标为 NaN、K 线缺失、交易所时间漂移过大或仓位状态不一致时开新仓。

## 研究风险

这 7 个组合是 2025-06-01 到 2026-06-01 的 Binance HYPE 5m 样本内研究结果。它们满足当前回测目标，但高度依赖精筛过滤、组合选择和 one-position 执行门槛。上线前至少需要独立时间段复核、交易所复制、实盘 dry-run、资金费率和强平风险建模。
""".strip()


def combo_id(legs: int, leverage: float) -> str:
    leverage_text = f"{leverage:g}".replace(".", "p")
    return f"{legs}legs_{leverage_text}x"


def filename_for(strategy_id: str, legs: int, leverage: float) -> str:
    leverage_text = f"{leverage:g}".replace(".", "p")
    return f"hype-5m-ensemble-{strategy_id.lower()}-{legs}l-{leverage_text}x-live-spec.md"


def pct(value: Any) -> str:
    return f"{float(value) * 100:.2f}%"


def multiple(value: Any) -> str:
    return f"{float(value):.2f}x"


def num(value: Any, digits: int = 4) -> str:
    return f"{float(value):.{digits}f}"


def signed_num(value: Any, digits: int = 2) -> str:
    return f"{float(value):+.{digits}f}"


def signed_pct(value: Any) -> str:
    return f"{float(value) * 100:+.2f}%"


def pass_flag(row: pd.Series | dict[str, Any]) -> str:
    return (
        "是"
        if int(row["full_trades"]) >= 20
        and float(row["full_annualized_multiple"]) >= 20
        and float(row["full_win_rate"]) >= 0.80
        and float(row["full_max_dd"]) >= -0.20
        else "否"
    )


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    clean_rows = [["" if pd.isna(cell) else str(cell) for cell in row] for row in rows]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in clean_rows)
    return "\n".join(lines)


def filter_expressions(raw: str) -> list[str]:
    expressions: list[str] = []
    for part in str(raw).split("&"):
        try:
            feature, op, value = part.rsplit("_", 2)
        except ValueError:
            expressions.append(part)
            continue
        symbol = ">=" if op == "ge" else "<=" if op == "le" else op
        expressions.append(f"{feature} {symbol} {value}")
    return expressions


def entry_style_label(value: str) -> str:
    return {
        "ema_deviation_revert": "EMA 偏离回归",
        "bb_reversion": "布林回归",
    }.get(value, value)


def side_label(value: str) -> str:
    return {
        "short": "只做空",
        "long": "只做多",
        "both": "多空都可",
    }.get(value, value)


def metrics_table(row: pd.Series) -> str:
    rows = [
        [
            "全样本",
            "2025-06-01 到 2026-06-01",
            int(row["full_trades"]),
            multiple(row["full_annualized_multiple"]),
            multiple(row["full_equity_multiple"]),
            pct(row["full_max_dd"]),
            pct(row["full_win_rate"]),
            pct(row["full_avg_trade"]),
            pct(row["full_worst_trade"]),
        ],
        [
            "IS",
            "2025-06-01 到 2026-03-01",
            int(row["is_trades"]),
            multiple(row["is_annualized_multiple"]),
            multiple(row["is_equity_multiple"]),
            pct(row["is_max_dd"]),
            pct(row["is_win_rate"]),
            pct(row["is_avg_trade"]),
            pct(row["is_worst_trade"]),
        ],
        [
            "OOS",
            "2026-03-01 到 2026-06-01",
            int(row["oos_trades"]),
            multiple(row["oos_annualized_multiple"]),
            multiple(row["oos_equity_multiple"]),
            pct(row["oos_max_dd"]),
            pct(row["oos_win_rate"]),
            pct(row["oos_avg_trade"]),
            pct(row["oos_worst_trade"]),
        ],
    ]
    return md_table(
        ["区间", "日期", "交易数", "年化倍数", "权益倍数", "最大回撤", "胜率", "均笔收益", "最差单笔"],
        rows,
    )


def leg_table(legs: pd.DataFrame) -> str:
    rows: list[list[Any]] = []
    for _, leg in legs.iterrows():
        filters = "<br>".join(f"`{item}`" for item in filter_expressions(str(leg["filter_name"])))
        rows.append(
            [
                int(leg["leg_rank"]),
                f"`{leg['base_name']}`",
                side_label(str(leg["side_mode"])),
                entry_style_label(str(leg["entry_style"])),
                f"{int(leg['ema_fast'])}/{int(leg['ema_slow'])}",
                f"{num(leg['stop_atr'], 2)} / {num(leg['tp_atr'], 2)}",
                int(leg["max_hold_bars"]),
                filters,
            ]
        )
    return md_table(
        ["排名", "子腿", "方向", "入场形态", "EMA 快/慢", "止损/止盈 ATR", "最长持有", "附加过滤"],
        rows,
    )


def leg_detail_sections(legs: pd.DataFrame) -> str:
    sections: list[str] = []
    for _, leg in legs.iterrows():
        filter_lines = "\n".join(f"  - `{expr}`" for expr in filter_expressions(str(leg["filter_name"])))
        sections.append(
            f"""### L{int(leg["leg_rank"]):02d} `{leg["base_name"]}`

- `refined_name`: `{leg["refined_name"]}`
- 方向：{side_label(str(leg["side_mode"]))}
- 入场形态：{entry_style_label(str(leg["entry_style"]))}
- 趋势 EMA：`EMA{int(leg["ema_fast"])}` vs `EMA{int(leg["ema_slow"])}`。
- 风控参数：`stop_atr={num(leg["stop_atr"], 2)}`，`tp_atr={num(leg["tp_atr"], 2)}`，`trail_atr={num(leg["trail_atr"], 2)}`，`max_hold_bars={int(leg["max_hold_bars"])}`。
- 附加过滤：
{filter_lines}
"""
        )
    return "\n".join(sections).strip()


def leverage_table(rows: pd.DataFrame) -> str:
    body: list[list[Any]] = []
    for _, row in rows.sort_values("test_leverage").iterrows():
        body.append(
            [
                f"{float(row['test_leverage']):g}x",
                pass_flag(row),
                int(row["full_trades"]),
                multiple(row["full_annualized_multiple"]),
                pct(row["full_max_dd"]),
                pct(row["full_win_rate"]),
                signed_num(row["delta_full_annualized_multiple"]),
                signed_pct(row["delta_full_max_dd"]),
                signed_pct(row["delta_full_win_rate"]),
            ]
        )
    return md_table(
        ["测试杠杆", "达标", "交易数", "年化倍数", "最大回撤", "胜率", "年化变化", "回撤变化", "胜率变化"],
        body,
    )


def execution_table(rows: pd.DataFrame) -> str:
    labels = {
        "one_position_only": "单仓执行",
        "allow_overlapping_signals": "取消单仓门槛",
    }
    body: list[list[Any]] = []
    for _, row in rows.iterrows():
        body.append(
            [
                labels.get(str(row["variant"]), str(row["variant"])),
                pass_flag(row),
                int(row["full_trades"]),
                multiple(row["full_annualized_multiple"]),
                pct(row["full_max_dd"]),
                pct(row["full_win_rate"]),
                signed_num(row["delta_full_annualized_multiple"]),
                signed_pct(row["delta_full_max_dd"]),
                signed_pct(row["delta_full_win_rate"]),
            ]
        )
    return md_table(
        ["执行模型", "达标", "交易数", "年化倍数", "最大回撤", "胜率", "年化变化", "回撤变化", "胜率变化"],
        body,
    )


def drop_leg_table(rows: pd.DataFrame) -> str:
    body: list[list[Any]] = []
    for _, row in rows.sort_values("removed_leg_rank").iterrows():
        body.append(
            [
                int(row["removed_leg_rank"]),
                f"`{row['removed_base_name']}`",
                pass_flag(row),
                int(row["full_trades"]),
                multiple(row["full_annualized_multiple"]),
                pct(row["full_max_dd"]),
                pct(row["full_win_rate"]),
                signed_num(row["delta_full_annualized_multiple"]),
                signed_pct(row["delta_full_max_dd"]),
                signed_pct(row["delta_full_win_rate"]),
            ]
        )
    return md_table(
        ["删除腿", "删除对象", "删除后达标", "交易数", "年化倍数", "最大回撤", "胜率", "年化变化", "回撤变化", "胜率变化"],
        body,
    )


def common_parameters(legs: pd.DataFrame) -> str:
    fields = [
        "donchian",
        "roc_window",
        "min_regime_age",
        "max_regime_age",
        "breakout_buffer",
        "pullback_buffer",
        "max_dist_ema",
        "min_dir_roc",
        "min_dir_rsi",
        "max_dir_rsi",
        "min_adx",
        "max_chop",
        "max_atr_ratio",
        "min_rvol",
        "min_dir_cmf",
        "require_macd",
        "require_obv",
        "require_htf",
        "min_efficiency",
        "trail_atr",
        "min_hold_bars",
        "exit_ema",
        "cooldown_bars",
    ]
    rows = [[f"`{field}`", f"`{legs.iloc[0][field]}`"] for field in fields]
    return md_table(["参数", "值"], rows)


def render_doc(
    *,
    strategy_id: str,
    count: int,
    leverage: float,
    baseline: pd.Series,
    legs: pd.DataFrame,
    drop_rows: pd.DataFrame,
    lev_rows: pd.DataFrame,
    exec_rows: pd.DataFrame,
) -> str:
    cid = combo_id(count, leverage)
    title = f"# HYPE-5M-ENS-{strategy_id}: {count} 子腿 / {leverage:g}x 实盘代码规格"
    primary_bias = "只做空为主，含少量多空双向子腿" if (legs["side_mode"] == "both").any() else "只做空"
    return f"""{title}

Family id: `HYPE-5M-PBTR`

状态：研究候选规格，不是已晋升线上版本。本文用于让 AI 直接生成实盘代码骨架和策略逻辑；上线前必须另做 dry-run、风控和交易所复核。

## 策略摘要

- `combo_id`: `{cid}`
- 标的：Binance USDT 永续 `HYPE/USDT:USDT`
- K 线：`5m`
- 回测区间：`2025-06-01 00:00:00 UTC` 到 `2026-06-01 00:00:00 UTC`，右开区间。
- 样本切分：IS 到 `2026-03-01 00:00:00 UTC`，OOS 从 `2026-03-01` 到 `2026-06-01`。
- 策略结构：按排名扫描 `{count}` 条精筛子腿，单仓执行。
- 名义杠杆：`{leverage:g}x`
- 方向偏好：{primary_bias}
- 费用假设：每边 `0.04%`；滑点假设：每边 `0.01%`。

## 回测指标

{metrics_table(baseline)}

## 子腿列表

本策略使用 `research/hype/5m-pullback-trail/artifacts/hype_5m_ensemble_combo_legs.csv` 的前 `{count}` 条子腿。

{leg_table(legs)}

## 子腿共享参数

{common_parameters(legs)}

{FEATURE_DEFINITIONS}

{SIGNAL_AND_EXECUTION_TEMPLATE}

## 子腿逐条规格

{leg_detail_sections(legs)}

## 消融实验

消融使用同一份 `2025-06-01` 到 `2026-06-01` Binance HYPE 5m 数据、同一费用滑点、同一 one-position 组合逻辑；只改变被测试的组件。`年化变化 / 回撤变化 / 胜率变化` 都是相对本策略 baseline 的变化。

### 杠杆消融

{leverage_table(lev_rows)}

### 执行门槛消融

`取消单仓门槛` 是把所有去重后的子腿信号按时间顺序计入权益曲线；它用于观察单仓约束的贡献，不代表真实账户可以无成本无限并发。

{execution_table(exec_rows)}

### 删除单条子腿消融

{drop_leg_table(drop_rows)}

{CODEGEN_CHECKLIST}
"""


def main() -> None:
    for path in [SUMMARY_PATH, DROP_LEG_PATH, LEVERAGE_PATH, EXECUTION_PATH, LEGS_PATH]:
        if not path.exists():
            raise FileNotFoundError(path)

    summary = pd.read_csv(SUMMARY_PATH)
    drop = pd.read_csv(DROP_LEG_PATH)
    leverage = pd.read_csv(LEVERAGE_PATH)
    execution = pd.read_csv(EXECUTION_PATH)
    legs = pd.read_csv(LEGS_PATH)
    legs["leg_rank"] = range(1, len(legs) + 1)

    DOC_DIR.mkdir(parents=True, exist_ok=True)
    index_rows: list[list[Any]] = []
    for strategy_id, count, lev in TARGET_COMBOS:
        cid = combo_id(count, lev)
        baseline = summary.loc[summary["combo_id"] == cid].iloc[0]
        selected_legs = legs.head(count).copy()
        drop_rows = drop.loc[drop["combo_id"] == cid].copy()
        lev_rows = leverage.loc[leverage["combo_id"] == cid].copy()
        exec_rows = execution.loc[execution["combo_id"] == cid].copy()
        filename = filename_for(strategy_id, count, lev)
        path = DOC_DIR / filename
        content = render_doc(
            strategy_id=strategy_id,
            count=count,
            leverage=lev,
            baseline=baseline,
            legs=selected_legs,
            drop_rows=drop_rows,
            lev_rows=lev_rows,
            exec_rows=exec_rows,
        )
        path.write_text(re.sub(r"\n{3,}", "\n\n", content).strip() + "\n")
        index_rows.append(
            [
                f"`HYPE-5M-ENS-{strategy_id}`",
                f"[{filename}]({filename})",
                count,
                f"{lev:g}x",
                multiple(baseline["full_annualized_multiple"]),
                pct(baseline["full_max_dd"]),
                pct(baseline["full_win_rate"]),
                int(baseline["full_trades"]),
            ]
        )

    index = f"""# HYPE-5M-PBTR Ensemble 实盘规格文档索引

这些文档对应当前报告里全部 7 个 `target_pass=True` 的 one-position ensemble 组合。它们不是 7 个互不相关的策略家族，而是同一批精筛子腿在不同子腿数量和杠杆下的 7 个达标配置。

{md_table(["策略编号", "文档", "子腿数", "杠杆", "全样本年化", "最大回撤", "胜率", "交易数"], index_rows)}

复现来源：

- `research/hype/5m-pullback-trail/artifacts/hype_5m_ensemble_combo_ranking.csv`
- `research/hype/5m-pullback-trail/artifacts/hype_5m_ensemble_combo_legs.csv`
- `research/hype/5m-pullback-trail/artifacts/hype_5m_ensemble_ablation_*.csv`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_ensemble_combo.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_ensemble_ablation.py`
"""
    (DOC_DIR / "README.md").write_text(index.strip() + "\n")
    print(f"wrote={DOC_DIR}")
    for strategy_id, count, lev in TARGET_COMBOS:
        print(DOC_DIR / filename_for(strategy_id, count, lev))


if __name__ == "__main__":
    main()
