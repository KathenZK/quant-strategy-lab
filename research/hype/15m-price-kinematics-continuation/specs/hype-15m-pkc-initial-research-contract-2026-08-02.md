# HYPE-15M-PKC 初始短周期价格运动学研究合同（2026-08-02）

## 问题与禁止项

核心问题：HYPE 是否存在持续数小时的短周期价格惯性，即过去 `1h/3h/6h` 的方向、速度、加速度和路径形状能够稳定区分未来 `1h/3h/6h/12h` 的延续与反转？

本轮禁止传统技术指标、breakout/交叉事件、成交量与衍生品变量、订单、仓位、止损、PnL、结果驱动窗口搜索，以及对 prospective OOS 的读取。

## 数据、时序与窗口

- Binance USD-M `HYPE/USDT:USDT` perpetual 闭合 `15m` 价格；raw/normalized 必须逐行对拍。
- 数据表 timestamp 为 bar open；研究可见时间统一加 `15m`，任何状态只能使用该时点及以前已闭合价格。
- Train：`[2025-06-03 00:00, 2026-02-01 00:00 UTC)`。
- Embargo：`[2026-02-01 00:00, 2026-02-15 00:00 UTC)`。
- 一次性历史 Validation：`[2026-02-15 00:00, 2026-08-02 00:00 UTC)`；每个标签必须在边界和数据终点前完整结束。
- Prospective OOS 锚点：`[2026-08-02 00:00, 2026-11-02 00:00 UTC)`，本轮禁止读取。
- 主锚点为可见时间 minute `00`；`15/30/45` 分钟为预声明相位敏感性，不选择最佳相位。

过去窗口按15分钟 bar 固定为 `T ∈ {4,12,24}`，即 `1h/3h/6h`；未来固定为 `H ∈ {4,12,24,48}`，即 `1h/3h/6h/12h`。主方向为过去 `12` bars 位移符号，不设最小幅度。

## 状态与标签

沿用价格运动学的纯路径定义：

\[
x_t=\ln P_t,\quad r_t=x_t-x_{t-1},\quad
D_T=x_t-x_{t-T},\quad V_T=D_T/T
\]

\[
L_T=\sum|r_i|,\quad S_T=L_T/T,\quad
K_T=D_T/(L_T+\epsilon),\quad C_T=|K_T|
\]

\[
B_T=\max|r_i|/(L_T+\epsilon),\quad
Q_T=\sqrt{T^{-1}\sum r_i^2}
\]

粗糙度 `R_T` 仍为轨迹相对窗口起终点直线的 RMS 偏离除以 `L_T+epsilon`。方向 `d=sign(D12)`；方向对齐速度为 `dV4/dV12/dV24`，加速度为：

\[
A_{4,12}=d(V_4-V_{12})/8,\qquad
A_{12,24}=d(V_{12}-V_{24})/12
\]

未来主标签：

\[
Y_H=d(x_{t+H}-x_t),\quad
U_H=Q_{24}\sqrt{H},\quad Z_H=Y_H/(U_H+\epsilon)
\]

同时冻结 continuation、未来路径一致性、MFE、MAE、MFE share，以及先触及 `+U_H/-U_H` 的顺序。未来标签永不进入状态特征。

## 冻结分析

- Train 五分位边界原样应用 Validation；报告 `Z`、continuation 和首次触及结果。
- 速度与 `A4,12` 构成固定 `5×5` 相空间，分 Long/Short 和四个 future horizon。
- Baseline Ridge/Logit 只用三尺度方向对齐速度；Full 加 `S/C/B/Q/R`、两项加速度和尺度一致数。
- 标准化只拟合 Train；Ridge `alpha=10`、Logit `C=0.1`，不搜索。
- Train 内 expanding walk-forward 对每个 horizon 使用等长 purge；Validation 揭示一次。
- 使用 `12h=12` 个主小时锚点作为 block，固定种子 `2,000` 次 block bootstrap。
- 删除 `|Z|` 最大 `1%` 后重复 IC；四个分钟相位在 `6h` horizon 做敏感性。
- Long/Short 完全分开；不允许一侧或某个 horizon 补贴另一侧。

## 证据门槛

某一方向只有同时满足以下条件，才称 `short-horizon-kinematic-evidence-supported`：

1. Validation Full Ridge IC 至少 `3/4` horizons 为正，且中位数不低于 Baseline；
2. Full Logit AUC `>0.5` 且 Brier 不差于常数概率，至少通过 `3/4` horizons；
3. 至少两个非速度结构量在预声明方向上，于至少三个 horizons 的 Validation 顶底分箱 block-bootstrap 95% CI 不跨零；
4. Train expanding OOF 与 Validation Full Ridge IC 至少 `3/4` horizons 同号；
5. 删除极端 `1%` 后至少 `3/4` IC 符号保留；
6. 四个分钟相位中至少三个在 `6h` Full Ridge IC 上与主相位同号；
7. 每个引用结论至少有 `30` 个非重叠 `12h` block。

任一门槛失败都不得进入策略设计。既有 `HYPE-1H-PKC` 结果只作尺度对照，不参与窗口或模型选择。
