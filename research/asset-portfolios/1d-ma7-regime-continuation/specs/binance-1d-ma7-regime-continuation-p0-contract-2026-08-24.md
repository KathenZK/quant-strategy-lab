# BIN-1D-MA7-RC P0 冻结研究合同（2026-08-24）

## 研究问题与边界

- Family：`Binance-1D-MA7-Regime-Continuation`，alias `BIN-1D-MA7-RC`。
- 唯一问题：`Normalized Slope + ER20 + RV20 percentile` 是否能在全历史动态 Binance USD-M 永续合约池中，把 MA7 上下突破后的延续、随机与假突破环境稳定地区分开。
- 本线是事件研究，不是可执行策略，不优化 MA 周期，不搜索阈值，不加止盈止损，不使用事件结果反向改写分桶。
- MA7 只负责产生事件；三个 regime 变量完全不引用 MA7。

## 数据合同

- 输入读取标准数据湖已审计 union 中 `source in {binance_vision_kline_monthly, binance_futures_kline_api}` 的 Binance USD-M perpetual `15m` 已闭合 K 线，按 UTC 因果聚合为 `1d`。仓库保留 7 币不可改写 legacy API 日分区；对 ETH 的受控跨源重叠，按 `(symbol, ts)` 固定优先 Vision、仅在 Vision 缺失时使用 API。任一来源内部重复必须 fail closed，priority 后 union 必须唯一。
- 研究截止为 `< 2026-07-01 00:00:00 UTC`，对应本地完整全市场 Binance Vision 月归档的最后一个 UTC 日。
- 每个日 K 必须恰有 `96` 根合法 `15m` K；缺失日不填充。指标回看和 forward path 必须处于连续 UTC 日网格中。
- 历史合约池取官方归档中真实出现过的全部 canonical USDT-style perpetual symbols，不以今天的 `exchangeInfo` 回填历史成分，退市合约保留。
- 上市时点取每个合约官方归档第一根真实成交 K 的时间。信号至少距该时点 `120` 个自然日；由于 RV percentile 要求完整 `252` 个 RV20 观测，实际 warm-up 更长。
- 对 `2020-01-01` 已存在的合约，Binance Vision 月归档存在左截断；它们的第一根归档 K 是保守的 available-history 起点，不宣称等同于交易所最初上市公告时间。

## 事件与收益

- 多头：`Close[t-1] <= SMAp[t-1] and Close[t] > SMAp[t]`。
- 空头：`Close[t-1] >= SMAp[t-1] and Close[t] < SMAp[t]`。
- 主研究 `p=7`；稳健性固定复算 `p in {5, 10}`，不从三者中选优。
- 固定 horizons：`1 / 3 / 5 / 10 / 20 / 40` 个连续 UTC 日。
- 多头 raw return：`Close[t+h] / Close[t] - 1`；空头 raw return：`1 - Close[t+h] / Close[t]`。
- ATR return：`direction * (Close[t+h] - Close[t]) / ATR14[t]`。
- 这是 close-to-close conditional expectancy，不模拟成交，因此不扣手续费、滑点、funding；结论不得表述为可交易净 alpha。

## Regime 定义

- `ATR14`：14 日 true range 的算术均值。
- `Normalized Slope = (SMA30[t] - SMA30[t-1]) / ATR14[t]`。
- `ER20 = abs(Close[t] - Close[t-20]) / sum(abs(diff(Close)), 20 days)`；零路径时为缺失。
- `RV20`：20 个日对数收益的样本标准差乘 `sqrt(365)`。
- `RV percentile`：同一合约截至 `t` 的最近 252 个 RV20 中，当前值的百分位秩；必须满 252 个观测。

## 分桶与统计

- Slope、ER 的 5 桶边界只由所有 eligible 日状态的指标分布决定，不读取 forward outcome；RV percentile 使用固定 `[0,.2,.4,.6,.8,1]`。
- MA7 的边界冻结后原样用于 MA5/MA10。
- 单变量表和 `5 × 5 × 5` 三维表分别对 long/short、6 个 horizons、raw/ATR return 输出：样本数、symbol 数、事件日数、均值、中位数、胜率、双向聚类标准误、t-stat、95% CI、p-value。
- 双向聚类按 `symbol + event UTC date`，覆盖同币重叠 horizon 与同日跨币共同冲击。
- 三维 125 cells 在每个 `direction × horizon × return metric` 内做 Benjamini-Hochberg FDR；只有 `n>=100`、`symbols>=10`、`dates>=30` 的 cell 可进入可靠性叙述。

## 冻结稳健性

- 年份：逐事件年复算单变量结构。
- 市场阶段：BTC `Close>SMA200 and 30D return>0` 为 bull；两者均反向为 bear；其余为 transition。
- 主要币种 vs 长尾：事件日用此前 30 日 quote-volume 中位数排序，Top 20 为 major，其余为 long-tail；不使用今天市值。
- MA 邻域：MA5/7/10 只比较结论结构，不选参数。
- 三维平滑与稳定：报告相邻 cell roughness、`<2024` vs `>=2024`、MA5 vs MA7、MA10 vs MA7 的 cell rank correlation。

## 决策规则

- 只有同时满足经济差异、边际关系大体单调或三维表平滑、时间与 MA 邻域可复现，才称为“可识别 regime”。
- 只在某个稀疏 cell 显著、FDR 后消失、表面不平滑或跨期符号翻转，均归类为不稳定/选择偏差风险。
- 本轮无论结果如何都保持 `explore / diagnostic-only / not promoted / not live-ready`；若结果支持，也只能冻结为后续 prospective filter 假设。

机器可读合同见 [frozen config](../configs/binance-1d-ma7-regime-continuation-p0.json)。最初单选 Vision 的 SHA256 `13d1afb76b289c32f05a70a2572939f171174fcad0e6924f53a9c87747c6c98f` 因漏币作废；P0R union SHA256 `3995406f0bc9da5e7798830dacc558f0eee4c7a78e8fd83c42fa69fdee46f2ab` 又在 outcome 前因 ETH 跨源重叠 fail closed。最终 P0R2 priority-union SHA256 为 `15bc78f14bf3f7026440d778d849252e8ff0d1af1aa80d3d064bd569e850a84b`。
