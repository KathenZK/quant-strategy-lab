# HYPE-15M-Riptide Decision Log

## 2026-06-30：V13 缓存口径复现审计

- 输入：`/Users/ZK/Downloads/SPEC-v13-RIPTIDE.md`，本地 `data/cache/hypeusdt_15m_fapi.csv`。
- 数据覆盖：`2025-05-30T10:30:00Z` 至 `2026-06-25T13:45:00Z`，`15m` 缺口 `0`，OHLCV 硬违规 `0`。
- 限制：未使用标准 raw/normalized parquet；未纳入真实 funding；1h RV 由 15m 聚合，不是交易所原生 1h 数据。
- 固定 `cut_hi=104.7`：本地复现 `+207.52%`、MDD `-25.76%`、`419` 笔、胜率 `29.36%`、PF `1.46`、单笔 `29.0bp`；未达到规格验收 `+252.7% / 431 笔 / 单笔 +31.5bp`。
- Walk-forward：`train150/test21/step21` 拼接 OOS `+108.49%`、MDD `-13.21%`、正窗 `11/11`，接近规格锚。
- Binance 默认成本重算：按每次成交手续费 `0.001` + 滑点 `4bp`（单边 `14bp`、往返 `28bp`），固定 `cut_hi=104.7` 降至 `+57.47%`、MDD `-34.56%`、PF `1.17`；150d rolling 为 `+47.99%`、MDD `-15.82%`；walk-forward 为 `+38.75%`、MDD `-15.82%`。收益仍为正，但安全垫明显变薄。
- 决策：维持 `diagnostic / reproduction-pending`。在标准 data lake、funding 和逐笔对账完成前，不得进入 live、paper-live、sim-paper 计时或 handoff。

证据：`diagnostics/hype-15m-riptide-v13-cache-audit-2026-06-30.md`。
