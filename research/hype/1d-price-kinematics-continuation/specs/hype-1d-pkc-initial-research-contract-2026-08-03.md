# HYPE-1D-PKC 初始研究合同（2026-08-03）

## 1. 研究问题与禁止项

只回答：按完整日 K 观察时，过去数日的价格运动幅度、速度和路径形状，能否稳定预测未来 `3–14` 日继续沿原方向运行。

- 允许：闭合 `open/high/low/close` 只用于构造完整日 K和未来路径；预测特征只取闭合日线 `close` 的历史。
- 禁止：EMA、MA、Donchian、ATR、RSI、ADX、成交量、资金费率、OI、订单簿、人工形态、止损止盈、收益回测和任何 Validation 后调参。
- Long 与 Short 必须分开，不允许用整体平均掩盖方向差异。

## 2. 数据与可用时序

- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 源：标准数据湖已闭合 `15m` K；每个 UTC 日必须恰有连续 `96` 根源 K。
- 日 K 时间戳是其完成后第一个可用的 UTC 午夜；任何特征只能使用该时刻及以前已闭合价格。
- 必查：源数据来源、UTC、缺口、重复、关键空值、OHLC 合法性、raw/normalized 对账；任一 blocker 停止研究。

## 3. 冻结时间边界

- Train：`[2025-06-15 00:00, 2026-02-01 00:00 UTC)`。
- Embargo：`[2026-02-01 00:00, 2026-02-15 00:00 UTC)`，等于最长未来标签。
- Validation：`[2026-02-15 00:00, 2026-08-03 00:00 UTC)`；每个 horizon 在边界前再 purge 对应未来长度。
- Prospective OOS：`[2026-08-03 00:00, 2026-11-03 00:00 UTC)`，本轮不得读取或生成标签。

## 4. 冻结状态与标签

- 过去窗口：`3/7/14` 根日 K。
- 方向：过去 `7d` 对数位移的符号；正为 Long 状态，负为 Short 状态。
- 每尺度状态：位移、速度、路径速度、方向一致性、最大单日变化占路径比、日收益 RMS、相对直线路径粗糙度。
- 跨尺度状态：`3–7d`、`7–14d` 方向对齐加速度，以及三个尺度与当前方向的一致数。
- 未来 horizon：`3/7/14d`；标签包括方向对齐最终收益、用过去 `14d` 日噪声扩散尺度归一化的 `Z`、是否延续、MFE、MAE、路径一致性和首次触及正负扩散尺度。

## 5. 冻结估计与稳健性

- Baseline：三个方向对齐速度；Full：加入全部预声明路径结构量。
- Ridge：`alpha=10`；Logit：`C=0.1`；所有标准化只拟合 Train；不搜索超参数。
- Train：带 horizon purge 的 expanding OOF；Validation：只揭示一次。
- 单变量：Train 五分位边界原样应用 Validation；预期正向为一致性、方向对齐加速度、尺度一致数，预期负向为脉冲集中度和粗糙度。
- Validation bootstrap：连续 `14d` 时间块、`2000` 次；删除 `|Z|` 最大 `1%` 做极端值敏感性。
- 每七日 stride 分组只作低功效相位诊断，不纳入通过门槛；不得把小组内偶然 IC 当作发现。

## 6. 通过门槛

Long、Short 各自必须同时满足：

1. Validation Full Ridge IC 至少 `2/3` horizon 为正，且中位数不差于 Baseline。
2. Validation Full Logit 至少 `2/3` 同时满足 AUC `>0.5`、Brier 不差于 Train 常数概率。
3. 至少两个预声明结构特征，各自在至少两个 horizon 的 expected-sign block-bootstrap 95% CI 排除零。
4. Train expanding OOF 与 Validation Full IC 至少 `2/3` 同号。
5. 删除极端 `1%` 后至少 `2/3` IC 保号。
6. 所有 horizon 的 Validation 每方向至少 `50` 个日观察。
7. Q1/Q5 效应至少覆盖 `20` 个独立 `14d` block；不足直接判为证据功效失败，即使点估计漂亮也不能支持规律。

本合同的“通过”只允许进入另行冻结的交易机制实验，不产生策略版本、promotion 或 live-readiness。
