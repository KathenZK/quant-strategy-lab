# BNB-15M-Adaptive-Regime

`BNB-15M-Adaptive-Regime`（短 id：`BNB-15M-AR`）是 Binance USD-M Futures `BNBUSDT` perpetual `15m` 的 BNB 专属多机制策略研究家族，与 `BNB-1H-Adaptive-Regime` 及其他资产 family 没有版本继承关系。

当前状态：`explore / not promoted / not live-ready`。

## 研究目标

- 数据：运行时最近两年的全部闭合 `15m` K，直接刷新自 Binance FAPI；同步保存 raw/normalized 分区、资金费和合约过滤器快照。
- OOS：最近三个月固定为 locked OOS；特征筛选、参数搜索、组合与 primary 冻结均不得读取该区间。
- 硬门槛：年化权益倍率 `>=10.0x`（annual return `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 实盘口径：闭合 `15m` K 产生信号，下一根 open 市价成交；保护性止损立即生效；同 K 双触发 stop-first；跳空穿 stop 按 open 成交。
- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，并逐笔计入真实 Binance funding。

## BNB 专属研究重点

- 低波动压缩后的趋势延续与成交量脉冲；
- 急跌/急涨后的结构修复，而非无条件 RSI 抄底；
- `1h/4h/1d` 闭合状态对 `15m` 入场的过滤；
- BNB 的亚洲/欧美时段差异、资金费方向和波动率分位；
- 趋势与均值回归机制分离搜索后再做单仓优先级组合。

## 当前状态

`active diagnostic research / not promoted / not live-ready`。

## 入口

- `bnb-15m-ar-core-ledger.md`：家族主账。
- `decision-log.md`：研究决策。
- `scripts/fetch_bnb_binance_15m.py`：两年数据抓取与质量审计。
- `scripts/research_bnb_15m_market_character.py`：BNB 行情结构诊断。
- `scripts/research_bnb_15m_adaptive_regime_search.py`：locked OOS 策略搜索。
