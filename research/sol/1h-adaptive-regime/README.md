# SOL-1H-Adaptive-Regime

`SOL-1H-Adaptive-Regime`（短 id：`SOL-1H-AR`）是 Binance USD-M Futures `SOLUSDT` perpetual `1h` 多指标自适应 regime 策略研究家族，与 BTC、HYPE 或其他资产的同类研究没有版本继承关系。

## 研究目标

- 数据：运行时最近两年的全部闭合 `1h` K，直接刷新自 Binance FAPI，并保存 raw/normalized 数据湖分区、资金费历史和合约过滤器快照。
- OOS：最后三个月固定为 locked out-of-sample；参数生成、搜索、排序和 ensemble 冻结不得读取该区间。
- 硬门槛：年化权益倍率 `>=10.0x`（即年化收益 `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，并逐笔计入 Binance 历史资金费。
- 执行：闭合 K 产生信号，下一根 `1h` open 市价成交；入场后保护性 bracket 立即生效；同 K 双触发 stop-first；跳空穿越 stop 按 open 成交；trailing 只在完整 K 闭合后更新并从下一根 K 生效。

## 指标与搜索面

搜索覆盖 EMA/MACD、RSI、Stochastic、CCI、Williams %R、ADX/DI、ATR、Bollinger、Keltner、Donchian、rolling VWAP、成交量、动量、wick/body 结构、`4h/12h/1d` 闭合 regime、资金费过滤、固定/风险预算仓位、固定 bracket/trailing exit 及 long/short/both。

## 当前状态

`active diagnostic search / not promoted / not live-ready`。

策略研究结果在 locked OOS 揭盲和 live-executable 审计完成前不形成 promotion 结论。本家族目前没有登记版本，也没有生产 runner。

## 入口

- `sol-1h-ar-core-ledger.md`：家族主账。
- `decision-log.md`：研究决策与状态变化。
- `scripts/fetch_sol_binance_1h.py`：最近两年 K 线、资金费、合约快照抓取与质量审计。
- `scripts/research_sol_1h_adaptive_regime_search.py`：locked OOS 多指标宽搜索。
- `scripts/research_sol_1h_adaptive_regime_refine.py`：按预先定义的 prefit Pareto 邻域做高密度精调；seed 和排序不读取 OOS。
- `scripts/audit_sol_1h_adaptive_regime_boundary.py`：成交延迟、成本、仓位缩放、单腿、参数邻域、月度、bootstrap 和实盘缺口审计。
- `artifacts/`：Parquet、JSON、CSV 等可复现证据；默认由 `.gitignore` 忽略。
