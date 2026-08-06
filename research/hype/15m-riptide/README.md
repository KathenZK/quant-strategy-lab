# HYPE-15M-Riptide

`HYPE-15M-Riptide` 是 Binance HYPEUSDT 永续 `15m` 趋势背景下顺势回调研究线：EMA20/60 只判定方向背景，RSI14 捕捉趋势内回调，1h realized-volatility regime 过滤高波动，入场即使用 ATR bracket、保本和 12h 时停。

当前状态：`explore / not promoted / not live-ready`（复现对账未完成）。`HYPE-15M-Riptide-V13` 的机制和 walk-forward 结果在本地 cache 复现中大体成立，但固定 `cut_hi=104.7` 第一验收未完全对齐外部规格，且本轮未完成标准 raw/normalized data lake、真实 1h K 线和 funding 序列对账。因此不得进入任何 promotion 状态。

## 当前证据

- 主账：[hype-15m-riptide-core-ledger.md](hype-15m-riptide-core-ledger.md)。
- 外部规格来源：本地下载文件（非仓库复现依赖）。
- 缓存口径复现审计：[hype-15m-riptide-v13-cache-audit-2026-06-30.md](diagnostics/hype-15m-riptide-v13-cache-audit-2026-06-30.md)。
- 复现脚本：[research_hype_15m_riptide_v13_cache_audit.py](scripts/research_hype_15m_riptide_v13_cache_audit.py)。

## 关键结论

- 固定 `cut_hi=104.7` 对照：本地 cache 口径为 `+207.52%`、最大回撤 `-25.76%`、`419` 笔、胜率 `29.36%`、PF `1.46`、单笔 `29.0bp`；外部规格验收为 `+252.7%`、`431` 笔、单笔 `31.5bp`。
- `train150/test21/step21` walk-forward：本地 cache 口径为 `+108.49%`、最大回撤 `-13.21%`、`255` 笔、正窗 `11/11`，接近规格锚 `+100.4% / MDD -12.6%`。
- 按 Binance 默认成本（每次成交手续费 `0.001` + 滑点 `4bp`，往返 `28bp`）重算：固定切点 `+57.47%`、MDD `-34.56%`、PF `1.17`；150d rolling `+47.99%`、MDD `-15.82%`；WF `+38.75%`、MDD `-15.82%`。
- 数据限制：当前只用 `data/cache/hypeusdt_15m_fapi.csv`，无标准 raw/normalized parquet 对齐、无真实 funding，1h RV 由 15m 聚合得到。

## 下一步

1. 补齐标准 Binance HYPEUSDT `15m`、`1h` OHLCV 与 funding data lake，并完成 raw/normalized 数据质量门。
2. 用真实 1h RV 与 funding 重跑固定切点和 walk-forward。
3. 与外部规格逐笔对账 signal/entry/exit 时间戳、方向、ATR、exit reason。
4. 只有逐笔对齐后，才讨论 dry-run 监控或 live-runner 状态机实现。
