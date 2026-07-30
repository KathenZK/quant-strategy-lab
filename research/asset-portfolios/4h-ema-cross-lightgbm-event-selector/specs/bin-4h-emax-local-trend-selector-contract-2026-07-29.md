# BIN-4H-EMAX 局部+趋势选择器移植契约

> 跑数前冻结。背景与 [1h 移植契约](../../1h-ema-cross-lightgbm-event-selector/specs/bin-1h-emax-local-trend-selector-contract-2026-07-29.md)相同：15m 证明局部+多日趋势特征可识别 +0.14~0.17 ATR 毛优势但过不了成本墙；1h 移植后顶桶毛 +0.219、净 +0.030（2/4 年为正，Gate B 未过但已追平成本）。本契约继续降一档成本，移植到 4h。与此前失败的 [V2 打分层](bin-4h-emax-v2-scoring-contract-2026-07-24.md)的本质区别：V2 喂的是行情态/市场特征（已证 OOS 漂移），本移植只喂局部形态+本币多日趋势。家族维持 `archived`，诊断性质。

## 数据与事件

- 事件：[`events_dev_4h.parquet`](../artifacts/events_dev_4h.parquet)（1h 重采样 4h、EMA21/96、B4_2、96 根超时、同一成本模型、point-in-time pool），只用 `in_trading_pool` 子集，开发窗口 ≤ 2025-12。
- 特征帧：4h per-symbol 缓存（`data/cache/emax_4h_derived`）。

## 特征与协议（与 1h 移植同构，仅换算窗口）

- 局部 37 个：15m `SYMBOL_FEATURES` 原样（bar-space 几何，`ret_96` 在 4h 代表 16 天）+ 事件级三项 + `cost_atr`。
- 多日趋势 7 个：`ret_7d`（42 根）、`ret_30d`（180 根）、`donchian_pos_30d` / `dist_high_30d` / `dist_low_30d`（180 根）、`d1_gap_atr` / `d1_price_to_slow`（日线重采样，同 1h 定义）。
- 权重：币种×同 UTC 日同侧聚簇降权（聚簇窗口 6 根）。
- LightGBM 同超参；OOF 2022–2025，purge 17 天（覆盖 96 根 = 16 天标签窗）。
- 判定：Gate A（Spearman > 0.8）+ Gate B（顶桶净 > 0 且 ≥3/4 年为正）；报告顶桶毛/净/成本、逐年，与 15m/1h 同表对比。

产物落 `artifacts/local_trend_selector/`。
