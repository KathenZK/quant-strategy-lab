# HYPE-15M-MMTF 数据冻结与质量报告 — 2026-07-22

本轮在任何候选绩效搜索前刷新 Binance FAPI 数据，并由 family-local freeze 脚本独立复核。数据质量门禁通过；本文只记录数据合同，不包含 locked OOS 绩效。

- 市场：Binance USD-M Futures `HYPEUSDT` perpetual `15m`。
- 全量闭合 K：`40,133` 根，`2025-05-30 10:30 UTC` 至 `2026-07-22 11:30 UTC`；terminal exclusive 为 `2026-07-22 11:45 UTC`。
- raw/normalized：missing `0`、duplicate `0`、critical null `0`、OHLC/volume violation `0`、字段 mismatch `0`、unclosed `0`。
- funding：`2,507` 条，`2025-05-30 12:00 UTC` 至 `2026-07-22 08:00 UTC`，null/duplicate `0`，最大间隔 `8h`。
- locked OOS：`[2026-04-22 11:45 UTC, 2026-07-22 11:45 UTC)`，`8,736` 根；selection/prefit 为此前 `31,397` 根。
- 最低样本合同：V1 排名至少需要 prefit `100` 笔、内部 90d validation `20` 笔；揭示后不得放宽。
- 成本合同：fee `0.001/fill`、基础不利滑点 `4 bps/fill`、真实持仓 funding；压力滑点 `8 bps/fill`。
- 成交合同：闭合 15m K 生成信号，下一根 open 入场；同 K stop-first；gap stop 使用 bar open；单净仓不重叠；杠杆 `<=3x`。
- 冻结 SHA256：raw `f8d75ebb...be87`、normalized `b8b1bf91...9760`、funding `e93ff638...cb84`；完整值见机器证据。
- 合约快照：`TRADING / PERPETUAL`，tick `0.001`、qty step `0.01`、min notional `5 USDT`。
- 机器证据：[hype_15m_mmtf_dataset_freeze_2026-07-22.json](../artifacts/hype_15m_mmtf_dataset_freeze_2026-07-22.json)

