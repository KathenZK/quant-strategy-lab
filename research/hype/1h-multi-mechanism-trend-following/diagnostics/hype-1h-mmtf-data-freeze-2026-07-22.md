# HYPE-1H-MMTF 数据冻结与质量报告 — 2026-07-22

本轮在任何候选生成前刷新 Binance FAPI 数据，并由 `scripts/freeze_hype_1h_dataset.py` 独立复核。数据质量门禁通过。

- 市场：Binance USD-M Futures `HYPEUSDT` perpetual `1h`。
- 全量闭合 K：`10,032` 根，`2025-05-30 10:00 UTC` 至 `2026-07-22 09:00 UTC`；terminal exclusive 为 `2026-07-22 10:00 UTC`。
- raw/normalized：missing `0`、duplicate `0`、critical null `0`、OHLC/volume violation `0`、字段 mismatch `0`、unclosed `0`。
- funding：`2,507` 条，`2025-05-30 12:00 UTC` 至 `2026-07-22 08:00 UTC`，null/duplicate `0`，最大间隔 `8h`。
- locked OOS：`[2026-04-22 10:00 UTC, 2026-07-22 10:00 UTC)`，`2,184` 根；selection/prefit 为此前 `7,848` 根。
- 冻结 SHA256：raw `5bc10811...92546`、normalized `dd9741fa...f936f`、funding `e93ff638...abcb84`；完整值见机器证据。
- 合约快照：`TRADING / PERPETUAL`，tick `0.001`、qty step `0.01`、min notional `5 USDT`。
- 机器证据：[hype_1h_mmtf_dataset_freeze_2026-07-22.json](../artifacts/hype_1h_mmtf_dataset_freeze_2026-07-22.json)
