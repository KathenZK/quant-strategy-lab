# HYPE-1D-MA7-MLT P2 Episode Policy Learning 教学合同

## 1. 身份与证据边界

- Family：`HYPE-1D-MA7-Machine-Learning-Trend`（`HYPE-1D-MA7-MLT`）。
- 实验：`P2 Episode Policy Learning`，不修改 P0/P1 或 `HYPE-1D-MA7-ABT V7.1`。
- 目的：教学演示如何通过修改候选空间、标签、特征和动作空间，让模型更接近“识别 MA7 穿越、持有趋势、退出或反手”的策略意图。
- P0/P1 已揭示同一 81 日路径；P2 明确是 `post-reveal educational replay`，不是 clean OOS、不是 promotion 证据、不是可交易模型。
- 状态固定为 `explore / diagnostic-only / not promoted / not live-ready`。

## 2. 数据、切分与执行

- Binance USD-M `HYPEUSDT` perpetual；经审计的连续 `1h` OHLCV 聚合完整 UTC `1d` K，另计同源 funding。
- 全窗 446 日：`2025-05-31` 至 `2026-08-19`；terminal open 为 `2026-08-20 00:00 UTC`。
- 模型训练只用前 365 日；后 81 日只作已揭示教学回放。
- 日收盘决策，下一 UTC 日开盘成交；`1x`、单仓、不加仓。
- 单边 fee `0.10%` + adverse slippage `0.04%`；完整 round trip `0.28%`。

## 3. Raw-cross episode

原始穿越不再预先要求 MA7 斜率同步转向：

```text
long raw cross : close[t-1] <= SMA7[t-1] and close[t] > SMA7[t]
short raw cross: close[t-1] >= SMA7[t-1] and close[t] < SMA7[t]
```

- raw cross 当日为 episode age `0`。
- 只要收盘仍在穿越后的 MA7 一侧，episode 可延续至 age `6`，即最多观察 7 个完整日。
- 发生反向 raw cross 时，旧 episode 结束并启动反向 episode。
- episode 每日均可成为下一开盘的入场候选；同一 episode 最多实际入场一次。
- MA7 斜率由硬门槛改为模型特征，使“价格先穿越、斜率随后成熟”进入可学习空间。

## 4. Episode 入场模型

- 标签仍为：从候选日下一开盘起，未来 21 日开盘路径先达到方向对齐 `+2.0 entry ATR7`，而不是先达到 `-1.5 entry ATR7`；未命中目标或先命中 adverse barrier 为 `0`。
- 标签路径不得跨训练边界；同一 episode 的所有行在 OOF 中必须作为同一 group。
- 模型固定为 `StandardScaler + LogisticRegression(C=0.05, L2, class_weight=balanced, random_state=20260827)`。
- 固定入场阈值 `0.55`。
- 固定输入 16 项：episode age、当前/初始方向对齐 MA7 距离、MA7 1/3 日斜率、斜率加速度、1/3 日收益、实体、收盘位置、range/ATR、RSI6、ER7、volume z7、ATR7/close、最近 7 日 raw-cross 次数。

## 5. 趋势存活模型

- 对每个训练 episode 的每个可入场日建立假想 campaign；从该 entry open 后每日生成持仓状态，最长 30 日。
- 每个持仓日收盘 `d` 的标签为：相对 `d+1` 开盘，未来最多 14 个开盘中是否先达到方向对齐 `+1.0 × 当前 ATR7`，而不是先达到 `-1.0 × 当前 ATR7`；未命中为 `0`。
- 该标签回答“趋势是否仍有至少 1 ATR 的剩余延续空间”，不再使用 P1 的局部“未来 5 日最好收益超过 0.14%”。
- 模型固定为同一低容量逻辑回归 `C=0.05`。
- 固定输入 16 项：当前 MA7 距离、MA7 1/3 日斜率、斜率加速度、1/3 日收益、RSI6、ER7、ATR7/close、持仓年龄、未实现收益、MFE、MAE、MFE giveback、是否反穿 MA7、最近 7 日 raw-cross 次数。
- 所有 MFE/MAE/收益只使用截至决策日已观察路径；未来价格只进入标签。

## 6. LONG / FLAT / SHORT 策略动作

### `P2_FULL_POLICY`

- 空仓：当前有效 episode 的入场概率 `>=0.55` 时，下一开盘进入 episode 方向。
- 持仓：每日计算当前方向的 survival probability。
- 若存在有效反方向 episode，且：

```text
opposite_entry_probability >= 0.55
opposite_entry_probability >= current_survival_probability + 0.10
```

则下一开盘直接完成 `LONG -> SHORT` 或 `SHORT -> LONG`，计平仓和新开仓两次成本。
- 否则 survival probability `<0.45` 时，下一开盘退出为空仓。
- 否则继续持有；最长 30 日后强制下一开盘退出。

### 固定消融

1. `P2_NO_REVERSAL`：入场与存活模型完全相同，但反方向 episode 只能促使当前仓退出，不能同开盘反手。
2. `RAW_CROSS_H7`：每个 raw cross 下一开盘直接入场，固定持有 7 日；持仓期新信号忽略。
3. P1 和 exact V7.1 只引用已保留结果作描述性对照。

## 7. 评价指标

- 模型：按 episode 分组的 expanding OOF AUC、Brier、0.5 accuracy、正类率。
- 策略：净收益、MDD、PF、胜率、交易数、long/short、反手次数、暴露日、成本、funding。
- 趋势教学指标：每笔 MFE/MAE、退出时已捕获收益、`realized positive return / MFE`、提前退出后 14 日剩余 MFE、反向 raw cross 到实际反手的延迟。
- 最近 `1d/7d/1m/3m/6m/1y` 切片仅作审计，不参与选择。

## 8. 裁决

- P2 只允许报告 `EDUCATIONAL_IMPROVEMENT`、`EDUCATIONAL_MIXED` 或 `EDUCATIONAL_FAILURE`。
- 若 P2 比 P1 同窗收益/回撤或趋势捕获更好，也不得写为 OOS 胜出。
- 本轮结果揭示后不得改阈值、episode age、label barrier、特征或逻辑回归强度；后续修改必须另立 P3 教学合同。
