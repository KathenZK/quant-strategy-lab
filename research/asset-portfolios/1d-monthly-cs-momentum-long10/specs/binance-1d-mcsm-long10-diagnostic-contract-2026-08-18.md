# BIN-1D-MCSM-L10 诊断契约（2026-08-18）

## 研究身份

- Family：`Binance-1D-Monthly-Cross-Sectional-Momentum-Long10`（`BIN-1D-MCSM-L10`）
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 目标：零调参回测“每月只做多上月涨幅最高 10 个 Binance USDT 永续”，不做空、不登记版本。

## 数据与时间

- 继承 [`BIN-1D-MCSM-LS3` 数据合同](../../1d-monthly-cs-momentum-ls3/specs/binance-1d-mcsm-ls3-diagnostic-contract-2026-08-18.md)：Binance Vision `15m` 全市场月档按 UTC 日聚合，月档 `2020-01`–`2026-06`，主力 `date=*` 只补重叠缺口。
- 评估：`2020-03-01`–`2026-06-30`，共 76 次月度换仓。`2026-07` 后没有全市场月档，不延伸。
- 上月覆盖至少 80%，形成期端点与换仓日开盘存在，端点日各至少 48 根 `15m`。
- 排除稳定币、法币本位与历史指数篮子，具体集合继承原合同。

## 冻结规则

- 形成期：上一个完整日历月末收盘 / 再上一个月末收盘 - 1。
- 排序：形成期收益降序，平手时 30 日 ADV 高者优先；换仓日无开盘则顺延。
- 每月 UTC 1 日开盘买入 Top10，各 `10%` 权益；持有至下月 1 日开盘。
- 末月在 `2026-06-30` 收盘平仓；无止损、无波动目标、无杠杆。
- 两个非搜索宇宙：`all_listed` 与截至上月末 30 日 ADV ≥1000 万 USDT。
- 对照：同口径 Top3、全市场合资格合约月度等权、BTC/ETH 永续 long-only，以及 BTC/ETH 价格 buy-and-hold。

## 成本与资金费

- 换手 `sum(abs(w_new-w_old))`；手续费 `0.001/边`，不利滑点 `0.0004/边`。
- 当日持仓逐日计入 Binance 实际资金费；期初建仓与期末平仓都计成本。
- 日收益在换仓日拆为旧仓隔夜与新仓日内，避免把月初开盘前收益归给新组合。

## 固定输出与限制

- 净收益、CAGR、Sharpe、最大回撤、月胜率、年化波动、逐年与最近切片。
- Price PnL、Funding、Fees、Slippage 与 Total attribution；完整换仓清单与日路径。
- 线性 PnL，不模拟组合保证金与逐合约强平；历史全样本已揭示，只能诊断。
- 不按资产类别排除 Binance 原生 USD-M 合约；因此 Binance 上市的股票/TradFi 永续在满足形成期、覆盖和成交资格后会自然进入排序。外部现货美股全市场不属于本合同；若另做跨市场版本，必须先有退市股在内的点时股票宇宙、公司行动和交易日历数据。
