# HYPE-1D-MA7-MLT P1 严格穿越事件与动态退出冻结合同

## 1. 身份与目的

- Family：`HYPE-1D-MA7-Machine-Learning-Trend`（`HYPE-1D-MA7-MLT`）。
- 实验：`P1 Cross-Event Dynamic Exit`，仅为独立诊断，不修改 P0，也不修改 `HYPE-1D-MA7-ABT V7.1`。
- 问题：机器学习能否在严格 MA7 穿越事件中识别趋势成败，并在入场后按每日新状态动态退出，而不是预测所有交易日的固定持有期收益。
- 状态固定为：`explore / diagnostic-only / not promoted / not live-ready`。

## 2. 数据、封存窗口与成本

- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 决策周期：UTC 完整 `1d` K；成交仅使用下一 UTC 日开盘。
- 数据与 P0 同源：从经审计的连续 `1h` OHLCV 聚合完整日 K，并使用同源 funding。
- 固定全窗：`2025-05-31` 至 `2026-08-19` 共 446 个完整 UTC 日，另保留 `2026-08-20 00:00 UTC` terminal open。
- 训练集：前 365 日，`2025-05-31` 至 `2026-05-30`。
- 一次性验证集：后 81 日，`2026-05-31` 至 `2026-08-19`；验证交易的首次可成交开盘为 `2026-05-31 00:00 UTC`。
- 每次成交默认 fee `0.10%`、adverse slippage `0.04%`；每个完整 round trip 为 `0.28%`，另计真实 funding。
- 固定 `1x`、不加仓、同一时刻最多一笔仓位；持仓时出现的新入场事件忽略。

## 3. 严格 MA7 穿越事件

在完整日 K 的收盘时点 `t` 计算 `SMA7_t`、Wilder `ATR7_t` 和：

```text
slope1_t = (SMA7_t - SMA7_{t-1}) / ATR7_t
```

做多候选：

```text
close_{t-1} <= SMA7_{t-1}
close_t     >  SMA7_t
slope1_t    >= 0.02
```

做空候选完全镜像：

```text
close_{t-1} >= SMA7_{t-1}
close_t     <  SMA7_t
slope1_t    <= -0.02
```

事件在 `t` 收盘后才成立；任何交易只能在 `t+1` 开盘成交。不得用验证集改变 `0.02`、MA 周期、ATR 周期或穿越定义。

## 4. 趋势成败标签

- 候选事件的 entry reference 为 `t+1` 开盘，entry ATR 为信号日 `ATR7_t`。
- 从 entry open 起观察未来最多 21 个 UTC 日开盘。
- 方向对齐的开盘位移首次达到 `+2.0 × entry ATR`，且此前未达到 `-1.5 × entry ATR`，标记 `trend_success=1`。
- 首先达到 `-1.5 × entry ATR`、21 日内未达到目标、或到窗口末仍未完成，均标记 `trend_success=0`。
- 若训练标签的完整 21 日路径越过训练边界，该事件不得进入训练。
- 额外保留 MFE、MAE、首次命中、固定 `1/3/5/7/14/21d` 成本后收益作为描述性事件研究，不用于改变标签。

## 5. 入场模型

- 单一模型：`StandardScaler + LogisticRegression(C=0.10, L2, class_weight=balanced, random_state=20260827)`。
- 所有多空变量先按方向对齐，由一个共享模型学习，禁止分别给 long/short 搜索参数。
- 固定入场阈值：`P(trend_success) >= 0.50`。
- 固定输入共 11 项：方向对齐的 MA7 1 日斜率、3 日平均斜率、穿越后距离、穿越前距离、K 线实体、收盘位置、RSI6，及 range/ATR、ER7、volume z7、ATR7/close。
- 训练前不得加入 P0 的全量 36 特征；验证揭示后不得更换模型、正则强度、阈值或特征。

## 6. 动态退出模型

- 每个训练事件从真实 entry open 后的第一根完整日 K 开始，最多生成 20 个持仓日状态；状态行按原始 event id 分组。
- 决策发生在持仓日 `d` 收盘，只能在 `d+1` 开盘退出。
- `continue_value=1` 当且仅当：相对 `d+1` 立即退出，未来 `2–6` 个开盘中最好的方向对齐增量收益大于 `0.14%`；否则为 `0`。`0.14%` 是一次 adverse fill 的 fee+slippage 缓冲，退出成本在“现在退出/以后退出”两边共同存在。
- 单一模型：`StandardScaler + LogisticRegression(C=0.10, L2, class_weight=balanced, random_state=20260827)`。
- 固定继续持有阈值：`P(continue_value) >= 0.50`；低于阈值则下一日开盘退出。
- 固定最大持有 21 日；terminal open 强制退出。本轮不使用盘中 stop，避免把另一个保护状态机混入“是否学会动态退出”的问题；因此不具备 live-ready 含义。
- 固定状态特征：当前方向对齐的 MA7 距离、1/3 日斜率、1/3 日收益、RSI6、ER7、ATR7/close、持仓年龄、方向对齐未实现收益、MFE、MAE、MFE giveback、是否反向穿回 MA7。

## 7. 对照与裁决

在同一验证窗报告：

1. `ML_ENTRY_DYNAMIC_EXIT`：入场模型筛选 + 每日动态退出。
2. `ALL_CROSS_DYNAMIC_EXIT`：所有合格穿越均入场，仅动态退出模型决定平仓，用于拆分入场学习贡献。
3. `ALL_CROSS_MA7_EXIT`：所有合格穿越均入场；收盘反向穿回 MA7 后下一开盘退出，最长 21 日。
4. `ALL_CROSS_H7`：所有合格穿越均入场，固定持有 7 日。
5. `HYPE-1D-MA7-ABT V7.1`：只作已看过该历史的 descriptive reference，不是 clean OOS 对手。

必须报告候选事件数、标签正负数、模型训练行数、验证入场概率、动态退出概率、逐笔收益、总收益、MDD、PF、胜率、long/short、暴露天数、成本、funding、最近 `1d/7d/1m/3m/6m/1y` 可用切片。

裁决：

- 验证期 ML 少于 3 笔已平仓交易，直接 `INSUFFICIENT_OOS_TRADES`。
- ML 净收益 `<= 0` 或 PF `< 1`，为 `ML_NO_EDGE`。
- ML 净收益高于 `ALL_CROSS_MA7_EXIT` 与 `ALL_CROSS_H7`，且 MDD 不比二者较优者恶化超过 5 个百分点，才记为 `ML_BEATS_SIMPLE_CROSS_OOS`。
- 其他情况为 `MIXED`。
- 无论结果如何，本轮都不 promotion、不写 live spec，也不得在该 81 日验证结果上补调参数。V7.1 只能描述，不能用于 clean-OOS 胜负判定。

