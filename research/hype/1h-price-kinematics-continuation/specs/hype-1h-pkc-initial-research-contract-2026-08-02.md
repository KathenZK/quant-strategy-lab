# HYPE-1H-PKC 初始价格运动学研究合同（2026-08-02）

## 研究问题与禁止项

核心问题：只观察一段时间内价格运动的方向、幅度、速度、加速度和路径形状，能否在当时可见信息下区分未来 `3d/7d/14d` 的趋势延续与失效？

本轮禁止：

- EMA、Donchian、RSI、MACD、ATR、布林带或其他命名技术指标；
- breakout、交叉、超买超卖等交易事件筛选；
- 入场、仓位、杠杆、止损、止盈、PnL 或策略参数搜索；
- 根据历史 Validation 结果增加公式、改变窗口、选择锚点相位或删除失败方向；
- 读取、排名、消融或回填 prospective OOS。

## 数据与冻结时间边界

- 标的：Binance USD-M `HYPE/USDT:USDT` perpetual。
- 原始粒度：完整闭合 `15m` OHLCV，仅价格字段参与特征和标签；成交量、资金费、OI、清算和盘口全部禁用。
- 研究粒度：每四根完整 `15m` 聚合为 `1h`；只有恰好四根且无缺口的小时可用。
- 历史 Train：`[2025-06-03 00:00, 2026-02-01 00:00 UTC)`。
- Embargo：`[2026-02-01 00:00, 2026-02-15 00:00 UTC)`，长于最大未来标签的边界隔离在每个具体样本切分内另行执行。
- 一次性历史 Validation：`[2026-02-15 00:00, 2026-08-02 00:00 UTC)`；每个未来 horizon 只使用能在数据终点前完整观察标签的锚点。
- Prospective OOS 锚点：`[2026-08-02 00:00, 2026-11-02 00:00 UTC)`；`14d` 标签最晚到 `2026-11-16` 才完整，本轮不得读取。
- 主锚点：完整 `1h` K 的可见时间为 UTC `00/04/08/12/16/20`。相位 `01/05/...`、`02/06/...`、`03/07/...` 只作预声明敏感性审计，不用于选择主结论。

## 价格运动学状态

令完整小时收盘的对数价格为：

\[
x_t=\ln P_t,\qquad r_t=x_t-x_{t-1}
\]

过去窗口固定为 `T ∈ {6,24,72}` 小时。对每个 `T` 计算：

\[
D_T=x_t-x_{t-T},\qquad V_T=\frac{D_T}{T}
\]

\[
L_T=\sum_{i=t-T+1}^{t}|r_i|,\qquad S_T=\frac{L_T}{T}
\]

\[
K_T=\frac{D_T}{L_T+\epsilon},\qquad C_T=|K_T|
\]

其中 `K_T` 是带方向路径一致性，`C_T` 是无方向一致性。脉冲集中度和单步噪声为：

\[
B_T=\frac{\max |r_i|}{L_T+\epsilon},\qquad Q_T=\sqrt{\frac{1}{T}\sum r_i^2}
\]

粗糙度以窗口起终点直线为参照：

\[
R_T=\frac{\sqrt{\frac{1}{T+1}\sum_{j=0}^{T}(x_{t-T+j}-\hat{x}_j)^2}}{L_T+\epsilon},
\quad
\hat{x}_j=x_{t-T}+\frac{j}{T}D_T
\]

主方向只由过去 `24h` 位移符号定义，不设幅度阈值：

\[
d_t=\operatorname{sign}(D_{24})
\]

按 `d_t>0` 与 `d_t<0` 分开验证。方向对齐速度和加速度为：

\[
\tilde V_T=d_tV_T,
\quad
A_{6,24}=d_t\frac{V_6-V_{24}}{18},
\quad
A_{24,72}=d_t\frac{V_{24}-V_{72}}{48}
\]

尺度一致数 `G` 为 `V6/V24/V72` 中与 `d_t` 同号的数量，取 `1/2/3`。所有分母固定加机器级 `epsilon=1e-12`，不做截断或结果驱动变换。

## 未来标签

未来 horizon 固定为 `H ∈ {72,168,336}` 小时。主连续标签为：

\[
Y_H=d_t(x_{t+H}-x_t)
\]

使用过去 `72h` 单步噪声构造不含未来信息的扩散尺度：

\[
U_H=Q_{72}\sqrt{H},\qquad Z_H=\frac{Y_H}{U_H+\epsilon}
\]

另计算：

- `continuation_H = 1[Y_H>0]`；
- 未来路径长度与带方向路径一致性；
- `MFE_H=max d_t(x_{t+i}-x_t)`；
- `MAE_H=max -d_t(x_{t+i}-x_t)`；
- `MFE_H/(MFE_H+MAE_H+epsilon)`；
- 首次触及 `+U_H` 与 `-U_H` 的顺序：`+1/-1/0`。

标签只用于结果 `y`，绝不回流到状态特征 `X`。

## 冻结分析

### 单变量分箱

- 使用 Train 主锚点计算每个连续状态量的五分位边界；相同边界原样应用到 Validation。
- 每格报告样本数、`Z_H` 均值/中位数、continuation rate、MFE、MAE 和 first-passage 胜率。
- 预声明方向：`C_T`、方向对齐速度、方向对齐加速度、尺度一致数预期正向；`B_T` 与 `R_T` 预期负向。速度允许出现非单调衰竭区，不因其形状事后改分箱。

### 相空间

- 使用 Train 边界把 `24h` 方向对齐速度和 `A6,24` 各分为五档，形成固定 `5×5` 网格。
- 分别在 Train/Validation、Long/Short、`3d/7d/14d` 报告样本数、平均 `Z_H` 与 continuation rate。
- 空格或样本不足格只标记，不插值、不合并。

### 固定透明模型

每个方向和 horizon 单独训练，不混合长短：

- Baseline Ridge/Logit：仅 `V6/V24/V72` 的方向对齐值；
- Full Ridge/Logit：Baseline 加 `S/C/B/Q/R` 三尺度、两项方向对齐加速度和尺度一致数；
- 标准化只用训练段均值与标准差；Ridge `alpha=10`，Logit `C=0.1`，不搜索超参数；
- Train 内使用带最大 `14d` purge 的 expanding walk-forward；冻结后在历史 Validation 只评估一次。

报告 Ridge Spearman IC、预测顶底五分位实际 `Z_H` 差，Logit AUC、Brier、相对常数概率 Brier 改善；同时报告 Full 相对 Baseline 的增量。

### 稳健性

- 以 `14d=84` 个主 `4h` 锚点为 block，固定种子做 `2,000` 次 block bootstrap；
- 删除 `|Z_H|` 最大 `1%` 样本后重复核心结果；
- 对四个预声明锚点相位重复评估，不以最佳相位替换主相位；
- 分 Long/Short、Train/Validation、三个 horizon 报告，不允许一侧补贴另一侧。

## 研究证据门槛

某一方向只有同时满足以下条件，才称为 `kinematic-evidence-supported`，但仍不构成策略或 promotion：

1. 历史 Validation Full Ridge IC 在至少 `2/3` horizons 为正，且三 horizon 中位数不低于 Baseline；
2. Full Logit AUC 在至少 `2/3` horizons 高于 `0.5`，Brier 至少不差于常数概率基线；
3. 至少两个非速度结构量在预声明方向上，于至少两个 horizon 的 Validation 顶底分箱差具有同号且 block-bootstrap 95% CI 不跨零；
4. 删除极端 `1%` 后，以上 Ridge IC 的 horizon 多数符号不反转；
5. 四个锚点相位中至少三个在 `7d` Full Ridge IC 上与主相位同号；
6. 每个被引用结论至少有 `10` 个非重叠 `14d` block；不足时只能称 `explore / insufficient independent history`。

任一条件失败时，不得据此设计 SEED/CORE/PYRAMID。Prospective OOS 仍保持锁定，只有未来数据完整后才能提供 fresh confirmation。
