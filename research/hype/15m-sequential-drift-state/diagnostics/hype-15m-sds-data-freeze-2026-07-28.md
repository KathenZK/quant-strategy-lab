# HYPE-15M-SDS 数据冻结与质量报告 — 2026-07-28

本家族在运行任何绩效结果前刷新 Binance FAPI 数据，并冻结输入、基线参数和代码哈希。数据质量门禁通过。

- 市场：Binance USD-M Futures `HYPEUSDT` perpetual `15m`。
- 闭合 K：`40,694` 根，`2025-05-30 10:30 UTC` 至 `2026-07-28 07:45 UTC`；terminal exclusive 为 `2026-07-28 08:00 UTC`。
- raw/normalized：missing `0`、duplicate `0`、critical null `0`、OHLC/volume violation `0`、逐字段 mismatch `0`、unclosed `0`。
- funding：`2,542` 条；null/duplicate `0`。
- family-local locked OOS：`[2026-04-28 08:00, 2026-07-28 08:00 UTC)`，`8,736` 根；prefit 为此前 `31,958` 根。
- OOS 诚实口径：该市场日期与其他 HYPE 家族先前研究重叠，因此不是 pristine OOS；本家族只允许冻结基线揭示一次，揭示后不得把结果回流调参。
- 成本：每次 fill fee `0.001` + adverse slippage `4 bps`，另计 Binance 历史 funding。
- 执行：闭合 K 决策、下一根 open 执行、单净仓、gap-aware 紧急止损；止损后必须先离开原趋势状态才允许同向重入。
- 冻结哈希：raw `16660eb8...b6539`、normalized `b82367fe...b872a`、engine `02b6cd3d...d80e`、baseline config `2dcc2d47...b682`。

机器证据：[hype_15m_sds_dataset_freeze.json](../artifacts/hype_15m_sds_dataset_freeze.json)
