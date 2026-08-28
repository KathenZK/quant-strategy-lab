# NDX100-1D-MA7-RC-Y2：Crypto P2 ATR 路径外部迁移合同

## 身份与目的

- Observation：`NDX100-1D-MA7-RC-Y2`，不是策略版本。
- Parent：股票 `Y0` 的完整 Yahoo 当前成分数据，以及加密 `BIN-1D-MA7-RC-P2` 已揭示的 ATR 路径结论。
- 目的：不根据股票结果调参，直接验证加密 P2 的 ATR 路径定义和两个方向性格子能否迁移到股票。
- 状态：`explore / diagnostic-only / survivorship-biased / not promoted / not live-ready`。

## 为什么使用 Y0 而不是 Y1

Y1 已请求所有历史退出成分，但完整 PIT membership 仅覆盖 `81.18%`，低于事前冻结的 `99.5%` 结果门槛。使用残缺 Y1 做“优化”会让退市/收购缺失与结果纠缠。因此本轮使用价格完整的 Y0 当前 `102` 条证券回填样本，明确保留 survivorship bias 标签；Y2 不替代 historical P0/Y1。

## 从 Crypto 原样迁移的定义

- `ATR20`：20 个完整交易日 True Range 简单均值。
- 突破前 ATR 路径：`ATR20[t-1] / ATR20[t-11] - 1`。
- ATR 路径分位：同股票、同连续 block 最近 60 个因果观测的当前值 percentile，固定五档。
- 突破强度：`TR[t] / ATR20[t-1]`；`<0.8` 为 `WEAK`，`0.8–1.2` 为 `NORMAL`，`>1.2` 为 `BURST`。
- 方向确认：多头要求对应 MA 当日斜率为正，空头要求为负。
- MA7 trigger、MA5/10 邻域、1/3/5/10/20/40 个交易日、raw/ATR return 与 trigger-close 观察口径均不变。

## 在读取股票结果前冻结的两个外部假设

1. 多头：`Q5_FAST_EXPANSION + BURST + MA slope aligned` 优于裸 MA7 多头。
2. 空头：`Q1_FAST_CONTRACTION + BURST + MA slope aligned` 优于裸 MA7 空头。

这两个格子来自 Crypto P2，因而对股票 Y2 属于外部预设假设；不得根据股票结果换成其他 quintile、range 阈值或持有期。全五档和 15 个 ATR×range cells 只用于判断结构是否平滑、是否只是单格偶然。

## 稳健性与裁决边界

- 报告年份、QQQ bull/bear/transition、横截面流动性 Top20/其他、MA5/7/10。
- 在相同 MA7 slope-aligned 样本上比较 ATR-path 60 与旧 RV252 的分离度。
- 统计是突破日收盘到 future close 的事件研究，不含 next-open、仓位、换仓、费用、分红、借券或退出规则。
- 即使某格显著为正，也只能说明外部特征迁移，不能登记或 promotion 为策略。

机器合同：[`../configs/ndx100-1d-ma7-regime-continuation-yahoo-current-y2-atr-path.json`](../configs/ndx100-1d-ma7-regime-continuation-yahoo-current-y2-atr-path.json)。
