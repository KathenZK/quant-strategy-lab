# BNB-1H-Adaptive-Regime

`BNB-1H-Adaptive-Regime`（短 id：`BNB-1H-AR`）是 Binance USD-M Futures `BNBUSDT` perpetual `1h` 多指标自适应策略研究家族，与 BTC、ETH、SOL、HYPE 或其他资产 family 没有版本继承关系。

## 研究目标

- 数据：运行时最近两年的全部闭合 `1h` K，直接刷新自 Binance FAPI，并保存 raw/normalized 数据湖分区、资金费历史和合约过滤器快照。
- OOS：最后三个月固定为 locked out-of-sample；参数生成、搜索、排序和组合冻结不得读取该区间。
- 硬门槛：年化权益倍率 `>=10.0x`（即年化收益 `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，并逐笔计入 Binance 历史资金费。
- 执行：闭合 K 产生信号，下一根 `1h` open 市价成交；入场后保护性 bracket 立即生效；同 K 双触发 stop-first；跳空穿越 stop 按 open 成交；trailing 只在完整 K 闭合后更新并从下一根 K 生效。

## 指标与搜索面

搜索覆盖 EMA/MACD、RSI、Stochastic、CCI、Williams %R、ADX/DI、ATR、Bollinger、Keltner、Donchian、rolling VWAP、成交量、动量、wick/body 结构、`4h/12h/1d` 闭合 regime、资金费过滤、固定/风险预算仓位、固定 bracket/trailing exit 及 long/short/both。

## 当前状态

`NO-GO / not promoted / not live-ready`。

完整搜索没有 prefit hard-gate 命中；唯一冻结 primary 在最近三个月 locked OOS 明显失效。本家族没有登记版本，也没有生产 runner。后续 BNB 研究已拆分到独立的 `../15m-adaptive-regime/`，不得把 15m 结果写回本家族版本线。

## 入口

- `bnb-1h-ar-core-ledger.md`：家族主账。
- `decision-log.md`：研究决策与状态变化。
- `scripts/fetch_bnb_binance_1h.py`：最近两年 K 线、资金费、合约快照抓取与质量审计。
- `scripts/research_bnb_1h_adaptive_regime_search.py`：locked OOS 多指标宽搜索。
- `diagnostics/bnb-1h-adaptive-regime-search-2026-07-03.md`：完整搜索与 locked OOS NO-GO 证据。
- `artifacts/`：Parquet、JSON、CSV 等可复现证据；默认由 `.gitignore` 忽略。
