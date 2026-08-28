# HYPE 1D MA7 MLT P6：V7.1 锚定三模型生命周期合同

## 1. 研究问题

P6 是 P5 之后的新诊断实验，不修改 P5，也不修改冻结的 `HYPE-1D-MA7-ABT-V7.1`。P5 已证明单一 `trend_active` 概率能够识别更多趋势，却不能同时承担入场、继续持有和反手三个决策。P6 因此冻结为 V7.1 锚定的三模型残差策略：

1. `ENTRY_VALUE`：V7.1 空仓时，MA7 穿越后的当前候选是否值得补入；
2. `SURVIVAL_3D`：当前 root 趋势是否至少还能存活约 3 日；
3. `REVERSAL_VALUE`：反向穿越是否强到足以支付平仓和反手成本。

V7.1 原始交易是优先级最高的 core schedule。ML 只允许延长非保护性 core 退出，或在 core 空档加入 supplemental trade。V7.1 的小时级保护止损不得被模型取消或延长。

## 2. 数据隔离

- 前 365 日固定为训练期：`2025-05-31 00:00 UTC` 至 `2026-05-30 00:00 UTC`，终点开盘 `2026-05-31 00:00 UTC`。
- 后 81 日固定为 reused holdout：`2026-05-31 00:00 UTC` 至 `2026-08-20 00:00 UTC`。
- `develop` 只允许调用物理截断的 365 日上下文；小时线和资金费率读取终点不得晚于训练终点。
- 所有未来路径只能进入标签 `y`；特征 `X` 只能使用当日收盘及更早数据。需要未来 3/14/21 日的样本在边界处必须 censor/purge。
- 开发选择区固定为前 285 日；最后 80 日是内部确认，不重训、不调阈值。
- 只有开发门禁通过并写入带哈希 manifest，独立 `validate` 才允许一次性读取后 81 日。
- 后 81 日永远不得用于 P6 或后续版本的特征、标签、阈值、模型、状态机和停止规则选择。

## 3. 候选与标签

### 3.1 ENTRY_VALUE

- 候选只来自 raw MA7 cross root 的 `age=0..6`，且下一开盘不在 V7.1 core 持仓区间内。
- 入场价为候选日下一 UTC open。
- 在同方向 hindsight stable-trend episode 内，或最多提前 2 日，使用该 episode 结束后的下一 UTC open 作为标签退出价。
- 计算入场后至标签退出的净方向收益、MFE/ATR 和 MAE/ATR。
- `entry_value=1` 同时要求：净方向收益扣除 `0.28%` 双边手续费/滑点后 `>=3%`、MFE `>=1.5 ATR`、MAE 不差于 `-1.5 ATR`；否则为 0。
- 该标签只用于训练，不是实时退出规则。

### 3.2 SURVIVAL_3D

- 对每个当前 root 非零且未来 3 日标签完整的日决策构造样本。
- 当前日 stable direction 必须与 root 相同，且未来 3 日至少 2 日继续与 root 相同，`survival_3d=1`；否则为 0。
- 这是离散趋势死亡/hazard 标签，专门用于继续持有，不得与 ENTRY_VALUE 概率混用。

### 3.3 REVERSAL_VALUE

- 候选只在 raw MA7 cross 当日产生。
- 以新 root 方向在下一 UTC open 假设反手，观察未来最多 14 日。
- `reversal_value=1` 同时要求：未来最佳方向收益扣除 `0.42%` 平仓、反手和最终退出成本后 `>=4%`、MAE 不差于 `-1.5 ATR`，且 stable direction 在未来 2 日内确认新方向；否则为 0。

## 4. 因果特征

### ENTRY_VALUE / REVERSAL_VALUE

使用 P5 的 23 个 `B1_ROOT_PATH` 特征，并增加：

- 穿越前一日相对新方向的 MA7 距离；
- 穿越产生的 gap jump/ATR；
- 穿越前三日方向收益；
- 穿越前在反侧持续的日数；
- 当前 root 的 peak gap 与 gap giveback。

### SURVIVAL_3D

使用上述 entry 特征，并增加 root 生命周期路径：

- root 起点以来的方向浮盈、MFE、MAE、giveback；
- root 起点以来的 peak MA7 gap 与当前 gap 回吐；
- 距最近有利收盘极值的日数；
- 连续处于 root 同侧的日数；
- MA7 一日斜率相对三日前的衰减。

不重新加入 P5 已在 OOF 中失败的 MA30、30 日压缩、成交量和 funding 扩展块。

## 5. 模型与 OOF

- 三个头均固定为 ExtraTrees；600 棵树，`max_depth=5`，`min_samples_leaf=6`，`max_features=0.75`，`class_weight=balanced`，随机种子 `20260828`。
- 固定扩展窗 OOF：测试区间 `[120,160)`、`[160,200)`、`[200,240)`、`[240,285)`；训练集在每个测试起点前额外 purge 3 日。
- 如果某折训练目标只有一个类别，只允许使用训练正例率的常数概率，不得删除该折或回看结果修改切分。
- 不搜索模型、特征块、阈值、EMA 或持有天数。

## 6. 冻结交易策略

### 6.1 V7.1 core

- exact V7.1 每笔原始入场、方向、1.0x 和小时级 protective stop 保持不变。
- 只有 `long_mfe_fraction_trail_exit`、`ma7_slope_exit`、`short_rsi_take_profit`、`max_hold` 且退出发生在 UTC 00:00 的交易可由 survival 模型考虑延长。
- 原退出前一日 `P(survival_3d) >=0.60` 才启动延长。
- 延长后，连续两日概率 `<0.35`、出现反向 root、到达下一笔 V7.1 core 入场或样本终点时退出；不设固定三日延长。

### 6.2 supplemental entry

- 只在 core schedule 的空档交易。
- raw-cross root `age<=6` 且 `P(entry_value)>=0.65` 时，下一 UTC open 以 1.0x 补入。
- 入场后不再读取 entry probability；只读取 survival/reversal。
- 连续两日 `P(survival_3d)<0.35` 才退出。
- 反向 raw cross 时，`P(reversal_value)>=0.70` 才在同一下一开盘直接反手，否则只平仓。
- 下一笔 V7.1 core 入场拥有优先权；supplemental position 必须在该时间退出。

## 7. 成本与回放

- P6 与 V7.1 均使用 1.0x、单仓、Binance `0.001` 手续费/每次成交、`4 bps/fill` 不利滑点和实际 funding。
- 使用 1 小时顺序回放，报告净收益、1h MDD、交易数、多空数、胜率、PF、成本、funding、持有天数、趋势段任意覆盖和按天覆盖。
- 完整 365 日重拟合必须单独标记为 resubstitution；OOF、内部确认和验证不得混报。

## 8. 开发门禁

只有以下条件全部满足，才允许读取后 81 日：

1. ENTRY_VALUE OOF AUC `>=0.60`；
2. SURVIVAL_3D OOF AUC `>=0.60`；
3. 最后 80 日内部确认 P6 净收益严格高于同期 V7.1；
4. 内部确认按天趋势覆盖不低于 V7.1；
5. 内部确认 1h MDD 不比 V7.1 恶化超过 2 个百分点；
6. 内部确认 P6 交易数不超过 V7.1 加 4 笔。

门禁失败状态为 `DEVELOPMENT_FAILED_HOLDOUT_LOCKED`，禁止验证。门禁通过后若 reused holdout 未同时提高净收益和趋势覆盖，裁决 `V7_1_NOT_BEATEN`；若同时提高且 MDD 不恶化超过 2 个百分点，裁决 `EDUCATIONAL_REUSED_HOLDOUT_WIN`。

无论结果如何，P6 都是 `diagnostic-only / not promoted / not live-ready`。ML 延长仓位没有重放 counterfactual 小时级保护止损，因此不得交接 runner。
