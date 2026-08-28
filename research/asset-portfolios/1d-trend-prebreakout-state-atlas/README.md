# Binance-1D-Trend-Prebreakout-State-Atlas

- Alias：`BIN-1D-TPSA`
- 市场：Binance 全部历史 USDT-M 永续合约
- 周期：完整 UTC 日 K
- 机制：把 MA7/MA30 等均线跨越只当作事件探针，系统统计突破前 60 日的冲击、修复、横盘、回踩、趋势成熟度和波动路径，寻找突破后趋势延续的前置市场状态。
- 当前状态：`P0 data-scope-incomplete`；`P0R terminal-return INSUFFICIENT EVIDENCE`；`P1 long path-label exploratory signal / new OOS required / not promoted / not live-ready`
- 碰撞警告：本家族不优化 MA 参数，不继承 `BIN-1D-MA7-RC-P3` 的固定规则、breadth 或账户结论。

入口：

- [P0 人工合同](specs/binance-1d-trend-prebreakout-state-atlas-p0-contract-2026-08-25.md)
- [P0 机器合同](configs/binance-1d-trend-prebreakout-state-atlas-p0.json)
- [P0R 输入修复合同](specs/binance-1d-trend-prebreakout-state-atlas-p0r-input-repair-2026-08-25.md)
- [P0R 结果](diagnostics/binance-1d-trend-prebreakout-state-atlas-p0r-results-2026-08-25.md)
- [P1 趋势路径标签结果](diagnostics/binance-1d-trend-prebreakout-state-atlas-p1-barrier-ml-2026-08-25.md)
- [Core ledger](binance-1d-tpsa-core-ledger.md)
- [Decision log](decision-log.md)
