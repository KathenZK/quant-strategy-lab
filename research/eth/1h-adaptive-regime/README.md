# ETH-1H-Adaptive-Regime

`ETH-1H-Adaptive-Regime`（短 id：`ETH-1H-AR`）是 Binance USD-M Futures `ETHUSDT` perpetual `1h` 多指标自适应策略研究家族，与 BTC、HYPE 及其他资产 family 无版本继承关系。

## 研究目标

- 数据：运行时最近两年的全部闭合 `1h` K，直接刷新自 Binance FAPI，并保存 raw/normalized 数据湖分区、资金费历史和合约过滤器快照。
- OOS：最后三个月固定为 locked out-of-sample；搜索、排序和参数选择不得读取该区间。
- 硬门槛：年化权益倍率 `>=10.0x`（即年化收益 `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 执行：闭合 K 产生信号，下一根 `1h` open 市价成交；入场后立即具备 stop-market/TP 保护；同 K 双触发按 stop-first；跳空穿越 stop 按 open 成交。
- 成本：`0.001` fee/fill、`4 bps` slippage/fill，并计入 Binance 历史资金费。

## 指标与搜索面

搜索覆盖 EMA/MACD、RSI、Stochastic、CCI、Williams %R、ADX/DI、ATR、Bollinger、Keltner、Donchian、rolling VWAP、成交量、动量、wick/body 结构、`4h/12h/1d` 闭合 regime、固定/风险预算仓位、固定 bracket/trailing exit 及 long/short/both。

## 当前状态

`research in progress / not promoted / not live-ready`。

## 入口

- `eth-1h-ar-core-ledger.md`：家族主账。
- `decision-log.md`：研究决策。
- `scripts/fetch_eth_binance_1h.py`：两年 K 线、资金费、合约快照抓取与质量审计。
- `scripts/research_eth_1h_adaptive_regime_search.py`：locked OOS 多指标宽搜索。
- `diagnostics/eth-binance-1h-data-quality-2026-07-03.md`：本轮两年数据质量审计。
- `artifacts/`：可复现证据；默认由 `.gitignore` 忽略。
