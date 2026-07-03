# TRX-1H-Adaptive-Regime

`TRX-1H-Adaptive-Regime`（短 id：`TRX-1H-AR`）是 Binance USD-M Futures `TRXUSDT` perpetual `1h` 多指标自适应策略研究家族，与 BTC、ETH、SOL、HYPE 或其他资产 family 无版本继承关系。

## 研究目标

- 数据：运行时最近两年的全部闭合 `1h` K，直接刷新自 Binance FAPI，并保存 raw/normalized 数据湖分区、资金费历史和合约过滤器快照。
- OOS：最后三个月固定为 locked out-of-sample；搜索、排序、参数微调和 ensemble 冻结不得读取该区间。
- 硬门槛：年化权益倍率 `>=10.0x`（年化收益 `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 执行：闭合 K 产生信号，下一根 `1h` open 市价成交；入场后立即具备 stop-market/TP 保护；同 K 双触发按 stop-first；跳空穿越 stop 按 open 成交。
- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，并计入 Binance 历史资金费。

## 指标与搜索面

搜索覆盖 EMA/MACD、RSI、Stochastic、CCI、Williams %R、ADX/DI、ATR、Bollinger、Keltner、Donchian、rolling VWAP、成交量、动量、wick/body 结构、`4h/12h/1d` 闭合 regime、资金费过滤、固定/风险预算仓位、固定 bracket/trailing exit 及 long/short/both。

## 当前状态

`NO-GO / diagnostic versions registered / not promoted / not live-ready`。

两阶段搜索提出 `480,768` 个结构化/随机/邻域配置，另做 `12,936` 个持续 regime 乐观上界变体；prefit hard-shape、locked OOS hard gate 均为 `0` 命中。领先 prefit-selected ensemble 全样本年化权益倍率 `4.077x`、最大回撤 `-19.84%`、胜率 `86.54%`，但 locked OOS 年化权益倍率 `0.844x`、区间收益 `-4.12%`。

按后续研究指令，该领先观察值已登记为 `TRX-1H-Adaptive-Regime-V1base`，并在全参数消融后把删参干净版登记为 `TRX-1H-Adaptive-Regime-V2`。两者均为 diagnostic only，不生成 canonical live spec。

## 入口

- `trx-1h-ar-core-ledger.md`：家族主账。
- `decision-log.md`：研究决策。
- `scripts/fetch_trx_binance_1h.py`：两年 K 线、资金费、合约快照抓取与质量审计。
- `scripts/research_trx_1h_adaptive_regime_search.py`：locked OOS 多指标宽搜索。
- `scripts/research_trx_1h_adaptive_regime_refine.py`：仅基于 prefit 结果的参数邻域搜索。
- `scripts/audit_trx_1h_persistent_regime_boundary.py`：持续趋势/均值回归持仓机制的偏乐观上界审计。
- `scripts/audit_trx_1h_live_feasibility.py`：领先观察值的精确复现、延迟/成本压力和生产控制审计。
- `scripts/research_trx_1h_ar_v1base_full_ablation.py`：`V1base` 全参数消融与 `V2` clean 参数面登记证据。
- `scripts/audit_trx_1h_ar_v2_strict_ablation_slices.py`：`V2` clean 参数消融、最近 `1d/7d/1m/3m/6m/1y` 分片和逐笔执行重放审计。
- `research-notes/trx-1h-ar-search-conclusion-2026-07-03.md`：本轮总报告。
- `ablations/trx-1h-ar-v1base-full-parameter-ablation-2026-07-03.md`：V1base 全参数消融与 V2 clean 参数面。
- `ablations/trx-1h-ar-v2-strict-ablation-slices-2026-07-03.md`：V2 严格分片、消融和实盘可执行性复核。
- `live-specs/trx-1h-ar-live-feasibility-2026-07-03.md`：实盘可行性 `NO-GO` 证据。
- `artifacts/`：可复现证据；非 Markdown 产物默认由 `.gitignore` 忽略。
