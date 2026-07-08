# BNB-1H-Adaptive-Regime

- Full family name：`BNB-1H-Adaptive-Regime`（短 id：`BNB-1H-AR`）
- 市场/周期：Binance USD-M Futures `BNBUSDT` perpetual `1h`
- 机制：两年闭合 `1h` K 多指标自适应 regime 广搜（EMA/MACD/RSI/Stoch/CCI/ADX/ATR/Keltner/Donchian/VWAP/结构 + 高周期 regime + 资金费过滤），ensemble 组合。
- 当前状态：V1-V3 已登记（V3 实际最大杠杆 `2.5x`）；reused OOS 属二次读取；`not promoted / not live-ready`。

## 边界

- 后续 BNB `15m` 研究在独立家族 `../15m-adaptive-regime/`；不得把 15m 结果写回本家族版本线。

## 研究协议（冻结口径）

- 数据：最近两年全部闭合 `1h` K 刷新自 Binance FAPI，raw/normalized 数据湖分区 + 资金费历史 + 合约过滤器快照。
- OOS：最后三个月 locked out-of-sample，参数生成、搜索、排序和组合冻结不得读取。
- 硬门槛：年化权益倍率 `>=10x`、胜率 `>=50%`、最大回撤 `<20%`。
- 执行：闭合 K 信号、下一根 open 市价成交、入场即挂 bracket、同 K stop-first、跳空按 open 成交、trailing 闭合后更新次 K 生效。
- 成本：fee `0.001`/fill、slippage `4 bps`/fill、真实资金费。
- 搜索引擎：`research/_shared-kernels/1h-adaptive-regime-search/`（SHA pin）。

## 入口

- 主账（V1-V3 版本表、指标与证据链接）：`bnb-1h-ar-core-ledger.md`
- 决策记录：`decision-log.md`
- 版本规格：`canonical-specs/`（V1 原始/clean、V2 clean-equivalent、V3 微调）
- 搜索 not-promoted 证据：`diagnostics/bnb-1h-adaptive-regime-search-2026-07-03.md`、`diagnostics/bnb-1h-ar-cap3-highwin-search-2026-07-06-cap3-highwin.md`

脚本在 `scripts/`（fetch / search / ablation / tune / vN 复现入口），被报告引用的产物在 `artifacts/`。逐版本演进结论以主账和 decision-log 为准。
