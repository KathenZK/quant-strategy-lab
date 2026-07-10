# ETH-1H-Adaptive-Regime

- Full family name：`ETH-1H-Adaptive-Regime`（短 id：`ETH-1H-AR`）
- 市场/周期：Binance USD-M Futures `ETHUSDT` perpetual `1h`
- 机制：两年闭合 `1h` K 多指标自适应 regime 广搜（EMA/MACD/RSI/Stoch/CCI/ADX/ATR/Keltner/Donchian/VWAP/结构 + 高周期 regime），ensemble 组合。
- 当前状态：V1、V2、V2.1、V3 已登记；reused holdout 仍为负；`not promoted / not live-ready`。

## 研究协议（冻结口径）

- 数据：最近两年全部闭合 `1h` K 刷新自 Binance FAPI，raw/normalized 数据湖分区 + 资金费历史 + 合约过滤器快照。
- OOS：最后三个月 locked out-of-sample，搜索和排序不得读取。
- 硬门槛：年化权益倍率 `>=10x`、胜率 `>=50%`、最大回撤 `<20%`。
- 执行：闭合 K 信号、下一根 open 市价成交、入场即挂 stop/TP、同 K stop-first、跳空按 open 成交。
- 成本：fee `0.001`/fill、slippage `4 bps`/fill、真实资金费。
- 搜索引擎：`research/_shared-kernels/1h-adaptive-regime-search/`（SHA pin）。

## 入口

- 主账（V1-V3 版本表、指标与证据链接）：`eth-1h-ar-core-ledger.md`
- 决策记录：`decision-log.md`
- 版本规格：`specs/`（V1 baseline、V2 clean tuned、V2.1 high-win tuned、V3 clean tuned）
- V3 频率与 fresh forward 诊断：`notes/eth-1h-ar-v3-frequency-forward-diagnostic-2026-07-10.md`
- 数据质量报告：`diagnostics/eth-binance-1h-data-quality-2026-07-03.md`

脚本在 `scripts/`（fetch / search / ablation / tune / vN 复现入口），被报告引用的产物在 `artifacts/`。逐版本演进结论以主账和 decision-log 为准。
