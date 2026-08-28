# HYPE-1D-MA7-MLT P3 Purged Cross Survival 冻结合同

## 1. 身份与目的

- Family：`HYPE-1D-MA7-Machine-Learning-Trend`（`HYPE-1D-MA7-MLT`）。
- 实验：`P3 Purged Cross Survival`；不修改 P0/P1/P2 或 `HYPE-1D-MA7-ABT V7.1`。
- 目的：严格回答“MA7 原始穿越当日的状态能否预测趋势成败，以及入场后何时趋势已经死亡”。
- 状态固定为 `explore / diagnostic-only / not promoted / not live-ready`。
- P0–P2 已揭示后 81 日，因此该窗口只能是 `reused holdout`；本轮禁止用它选择特征、模型、阈值或停止条件。

## 2. 数据隔离与运行阶段

- Binance USD-M `HYPEUSDT` perpetual；可信连续 `1h` OHLCV 聚合完整 UTC `1d` K，真实 funding。
- 全窗仍为 446 个完整日；前 365 日是唯一开发集，后 81 日只由冻结后的验证阶段读取。
- `develop` 阶段在任何特征计算前把市场截断到前 365 日，并断言最大日线时间为 `2026-05-30 00:00 UTC`。
- 开发集内部：前 285 日用于特征块 expanding OOF 与模型拟合；其后时间只作一次内部确认，不参与特征块选择。
- 所有 entry 标签需要未来 21 个 open，训练事件标签必须在对应训练截止前完整结束；每个 OOF fold 前执行 21 日 purge。
- `develop` 输出冻结 manifest 及 SHA256；`validate` 必须校验 manifest 哈希，按 manifest 重训前 365 日后才可读取后 81 日，并且不得根据结果重跑选择。

## 3. 精确 raw-cross 事件与 entry 标签

每次原始穿越只生成一行、只在穿越日收盘决策：

```text
long : close[t-1] <= SMA7[t-1] and close[t] > SMA7[t]
short: close[t-1] >= SMA7[t-1] and close[t] < SMA7[t]
```

- 不设斜率硬门槛；斜率只作为输入。
- 下一 UTC open 才能成交。
- entry 标签固定为：从下一 open 起 21 个 open 内，方向对齐 `+2.0 ATR7` 是否先于 `-1.5 ATR7` 被命中；未命中目标为 0。
- 多空特征统一方向对齐，由一个共享模型学习。

## 4. Entry 特征块与选择

固定四个累积块：

1. `GEOMETRY_4`：穿越前/后 MA7 距离、方向实体、方向收盘位置。
2. `GEOMETRY_SLOPE_8`：上块 + MA7 1日/3日斜率、斜率加速度、斜率是否在穿越日转向。
3. `GEOMETRY_SLOPE_PATH_12`：上块 + 穿越前同侧连续天数、穿越前3日方向收益、ER7、14日 raw-cross 次数。
4. `ALL_16`：上块 + range/ATR、volume z7、ATR7/close、ATR7 相对14日均值。

- 固定模型：`StandardScaler + LogisticRegression(C=0.05, L2, class_weight=balanced, random_state=20260827)`。
- OOF：事件按时间排序；至少 24 个初始训练事件，剩余事件分成 3 个连续测试折；训练标签结束日必须早于测试折首个决策日。
- 选择规则：aggregate OOF AUC 最高；若与最高值相差不超过 `0.01`，选特征更少者。Brier、accuracy、fold AUC 同时报告但不改变选择。
- 固定 entry threshold `0.50`。

## 5. Canonical survival 数据与特征块

- 每个 raw-cross 仅假设在穿越后的下一 open 入场一次；不再为 episode 内不同入场日复制 campaign。
- 每条 canonical campaign 最长生成 30 个持仓日状态；未来 14 日标签不得越过训练或 fold 边界。
- survival 标签：从决策后下一 open 起，未来 14 个 open 内方向对齐 `+1.0 ATR7` 是否先于 `-1.0 ATR7` 命中；未命中为 0。
- 同一 cross 的全部状态进入同一 fold；每个 cross 的所有状态权重之和固定为 1，避免长 episode 垄断训练。

固定三个累积块：

1. `SURVIVAL_CORE_6`：当前 MA7 距离、MA7 1/3 日斜率、持仓年龄、未实现收益、MFE giveback。
2. `SURVIVAL_PATH_11`：上块 + 斜率加速度、3日收益、MFE、MAE、是否反穿 MA7。
3. `SURVIVAL_ALL_15`：上块 + RSI6、ER7、ATR7/close、14日 raw-cross 次数。

- 模型与选择规则同 entry；指标按 cross 等权。
- 固定 survival threshold `0.50`。

## 6. P3 策略动作

- 空仓：精确 raw-cross 的 entry probability `>=0.50`，下一 open 入场。
- 持仓：每日收盘计算 survival probability。
- 反向 raw-cross 同时满足 `opposite entry >=0.50` 且 `opposite entry >= current survival +0.10`，下一 open 直接反手。
- 否则 survival `<0.50`，下一 open 平仓；否则继续持有。
- 最长持有 30 日；terminal open 强平。
- 固定 `1x`、单仓、不加仓；fee `0.10%/fill`、adverse slippage `0.04%/fill`，另计真实 funding。

固定对照：

1. `P3_FULL_POLICY`。
2. `P3_NO_REVERSAL`：反向信号只能平仓。
3. `RAW_CROSS_H7`：所有 raw-cross 下一 open 入场，固定持有 7 日。

## 7. 报告与裁决

必须分别报告：

- 四个 entry 和三个 survival 特征块的 OOF AUC/Brier/accuracy/fold 结果与被选块；
- 365日内部确认的账户指标；
- 最终前365日训练样本数、正类率、训练集内指标；
- 后81日一次性验证的收益、MDD、PF、胜率、交易数、方向、反手、暴露、成本、funding及最近 `1d/7d/1m/3m/6m/1y`；
- 逐笔交易、每日权益、每日概率决策、模型系数和所有产物 SHA256。

训练门禁：selected entry 与 survival aggregate OOF AUC 均须 `>0.50`，且各自至少 2/3 可计算 fold AUC `>0.50`，否则为 `TRAINING_GENERALIZATION_FAILED`。

验证只作一次观察：

- 训练门禁失败时，无论81日结果如何，最终结论不得高于 `TRAINING_GENERALIZATION_FAILED`。
- 训练门禁通过但验证净收益 `<=0`、PF `<1` 或不胜 `RAW_CROSS_H7`，为 `VALIDATION_FAILED`。
- 只有训练门禁通过、验证净收益/PF通过且胜过 raw-cross H7，才可记 `EDUCATIONAL_VALIDATION_PASS`；仍然不得 promotion，因为81日是 reused holdout 且交易样本预计很少。
- 本轮验证结果揭示后不得修改任何设置；下一次变更必须另立 P4 合同。
