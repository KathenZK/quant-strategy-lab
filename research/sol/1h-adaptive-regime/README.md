# SOL-1H-Adaptive-Regime

- Full family name：`SOL-1H-Adaptive-Regime`（短 id：`SOL-1H-AR`）
- 市场/周期：Binance USD-M Futures `SOLUSDT` perpetual `1h`
- 机制：两年闭合 `1h` K 多指标自适应 regime 广搜（EMA/MACD/RSI/Stoch/CCI/ADX/ATR/Keltner/Donchian/VWAP/结构 + 高周期 regime + 资金费过滤），ensemble 组合。
- 当前状态：V1、V2 已登记；高胜率硬目标复搜 `0` 命中；`not promoted / not live-ready`。

## 研究协议（冻结口径）

- 数据：最近两年全部闭合 `1h` K 刷新自 Binance FAPI，raw/normalized 数据湖分区 + 资金费历史 + 合约过滤器快照。
- OOS：最后三个月 locked out-of-sample，参数生成、搜索、排序和 ensemble 冻结不得读取。
- 硬门槛：年化权益倍率 `>=10x`、胜率 `>=50%`、最大回撤 `<20%`（高胜率复搜为 `10x / 80% / <20% DD`）。
- 执行：闭合 K 信号、下一根 open 市价成交、入场即挂 bracket、同 K stop-first、跳空按 open 成交、trailing 闭合后更新次 K 生效。
- 成本：fee `0.001`/fill、slippage `4 bps`/fill、真实资金费。
- 搜索引擎：`research/_shared-kernels/1h-adaptive-regime-search/`（SHA pin）。

## 入口

- 主账（V1/V2 版本表、指标与证据链接）：`sol-1h-ar-core-ledger.md`
- 决策记录：`decision-log.md`
- V2 参数规格：`specs/sol-1h-ar-v2-parameter-spec-2026-07-07.md`
- 高胜率硬目标搜索 not-promoted 证据：`diagnostics/sol-1h-ar-high-win-target-search-2026-07-07.md`

脚本在 `scripts/`（fetch / search / audit / ablation / tune / vN 复现入口），被报告引用的产物在 `artifacts/`。逐版本演进结论以主账和 decision-log 为准。
