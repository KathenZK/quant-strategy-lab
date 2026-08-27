# BIN-1D-MA7-RC P1 可读市场状态与信号频率合同（2026-08-24）

## 为什么需要 P1

P0R2 回答了 Slope、ER、RV 分桶后的条件收益，但没有把它们组织成用户可以直接识别的市场状态，也漏掉了信号经过过滤后的日、周、月频率。P1 在读取任何新增的 compression/expansion outcome 前冻结，用来回答三个问题：

1. MA5/7/10 突破后固定持有 `1/3/5/10/20/40D` 的完整事件统计是什么；
2. 当前是上涨趋势、下跌趋势、震荡还是转换期，以及同一状态是低、中还是高波动；
3. MA7 原始事件和预先声明的过滤层分别有多少次，日、周、月出现多频繁，样本是否足够。

P1 仍是事件研究，不进行资金账户、换仓、止损、成本或年化回测。只有 P1 结果被审阅后，才允许另立策略合同。

## 数据与事件

- 沿用 P0R2 已审计的 Binance USD-M perpetual、完整 UTC 日 K、历史动态合约池和 `<2026-07-01` 全市场 cutoff。
- 主事件为 SMA7 close cross；SMA5/10 只做邻域对照。
- 多头：`Close[t-1] <= SMAp[t-1] and Close[t] > SMAp[t]`。
- 空头：`Close[t-1] >= SMAp[t-1] and Close[t] < SMAp[t]`。
- 固定观察 `1/3/5/10/20/40D` raw 与 ATR 标准化收益，仍从 trigger close 到 future close，不模拟成交。

## 四状态市场风格

所有特征只使用同一合约截至 `t` 的信息。Slope 与 ER 新增各自 trailing-252 percentile，使“当前强弱”相对于该合约自己的过去一年判断，而不是用全历史边界冒充实盘规则。

- `UP_TREND`：`Close>SMA30`、Normalized Slope 为正、Slope trailing-252 percentile 位于顶部 40%、ER trailing-252 percentile 位于顶部 40%。
- `DOWN_TREND`：`Close<SMA30`、Normalized Slope 为负、Slope trailing-252 percentile 位于底部 40%、ER trailing-252 percentile 位于顶部 40%。
- `CHOP`：ER trailing-252 percentile 位于底部 40%，且不属于上述趋势状态。强斜率但低 ER 的 noisy directional 也放在 CHOP，因为它对 MA crossover 同样意味着路径噪声大。
- `TRANSITION`：其余状态，包括方向、价格位置或效率尚未形成一致确认的阶段。

这四类互斥且穷尽。顺序固定为 `UP_TREND → DOWN_TREND → CHOP → TRANSITION`。

## 高低波动怎么判断

`RV20 percentile` 的定义保持不变：当前 20 日年化 realized volatility 在该合约最近 252 个有效观测中的百分位。

| RV 桶 | 定义 | 可读标签 |
| --- | --- | --- |
| Q1 | `<=20%` | 极低波动 |
| Q2 | `(20%,40%]` | 低波动 |
| Q3 | `(40%,60%]` | 中等波动 |
| Q4 | `(60%,80%]` | 高波动 |
| Q5 | `>80%` | 极高波动 |

P1 不预先断言低波动或高波动更好；每个市场状态都按五档 RV 完整报告，寻找稳定、平滑、可解释的差异。

## Compression → Expansion

这一轴来自用户重新提供的原始研究假设，而不是根据 P0 的盈亏 cell 临时添加：

- `Compression ratio = ATR5 / ATR20`；只使用 `t-1` 的 trailing-252 percentile，底部 20% 定义为突破前压缩。
- `Expansion ratio = TrueRange[t] / ATR20[t-1]`；当日 trailing-252 percentile 顶部 20% 定义为突破日扩张。
- `compression → expansion` 必须同时满足前一日压缩与突破日扩张。

该定义在收盘后可知，但仍需下一阶段使用 next-open 才能转成可执行策略。

## 预先声明的过滤层

P1 只比较以下层级，不根据结果另增阈值：

1. `ALL_MA7`：所有 eligible MA7 事件；
2. `ALIGNED_STATE`：多头只取 `UP_TREND`，空头只取 `DOWN_TREND`；
3. `ALIGNED_LOW_VOL`：方向一致且 RV 为 Q1/Q2；
4. `ALIGNED_MID_VOL`：方向一致且 RV 为 Q3；
5. `ALIGNED_HIGH_VOL`：方向一致且 RV 为 Q4/Q5；
6. `ALIGNED_COMPRESSION_EXPANSION`：方向一致、前一日 compression percentile 底部 20%、突破日 expansion percentile 顶部 20%。

低、中、高波动三组是完整切片，不从中选取历史最好者直接写成策略。

## 频率与样本统计

- 对每个过滤层、long/short 分别输出总事件数、symbol 数、事件日数及占全部事件比例。
- 在共同 P1 eligible UTC 日历上补零，统计每天、每周、每月事件数的均值、中位数、P90、最大值、零信号比例与有信号比例。
- 同时输出每 1,000 个 eligible symbol-days 的事件率，避免历史合约数量逐年增加造成“后来信号更多”的错觉。
- 收益推断继续按 symbol 与 event date 双向聚类；样本多不等于独立样本多。

## 决策边界

- P1 只允许形成“哪些市场状态值得进入下一阶段策略回测”的候选，不产生年化、回撤或 live-ready 结论。
- P0 outcome 已经揭示，因此 P1 不能自称 clean OOS；compression/expansion 是预注册的新轴，但最终仍需未来数据或另行锁定的未见样本确认。
- 若方向一致状态仍无正 expectancy，或者频率低到无法形成分散样本，则停止写策略。
- 若存在跨 MA 邻域、年份与波动桶大体稳定的结构，才另立可执行策略合同，冻结 next-open、持仓/退出、仓位、换仓、手续费、滑点和 funding。

机器合同见 [P1 config](../configs/binance-1d-ma7-regime-continuation-p1.json)，冻结 SHA256 为 `77236cad969fbccfb0c907514e3d7f3898160a1b0a777dcd60511f6bcc6ceb42`。
