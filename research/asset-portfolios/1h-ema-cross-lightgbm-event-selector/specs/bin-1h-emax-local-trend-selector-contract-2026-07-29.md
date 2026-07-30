# BIN-1H-EMAX 局部+趋势选择器移植契约

> 跑数前冻结。背景：15m 家族的特征/标签双消融与 a2/F 增补证明——局部+多日趋势特征可稳定识别 +0.14~0.17 ATR 的毛优势，但 15m 成本墙（均值 ~0.42 ATR）不可逾越（见 [15m 双消融诊断](../../15m-ema-cross-lightgbm-event-selector/diagnostics/bin-15m-emax-feature-ablation-2026-07-29.md)）。本契约把同一选择器框架移植到 1h（成本墙约为 15m 的 1/3），检验同量级的可识别优势在低成本刻度是否可变现。家族维持 `archived`，本实验是诊断，不构成 promotion。

## 数据与事件（复用冻结产物）

- 事件：[`events_dev_1h.parquet`](../artifacts/events_dev_1h.parquet)（EMA21/96 交叉、B4_2=TP4/SL2、96 根超时、保守同根先止损、成本 0.0028+实际资金费、point-in-time pool），只用 `in_trading_pool` 子集，开发窗口 ≤ 2025-12（2026H1 不使用）。
- 特征帧：1h per-symbol 缓存（`data/cache/emax_1h`），`signal_idx` 与缓存行号对齐。

## 特征（与 15m a2 变体同构）

- 局部 37 个：直接复用 15m `emax_features.SYMBOL_FEATURES`（EMA21/96 同参）+ 事件级 `gap_pre_atr`/`bars_since_prev_cross`/`crosses_384` + `cost_atr`。**窗口按根数保持不变**（如 `ret_96` 在 1h 代表 96 小时），即移植的是"交叉的 bar-space 几何"，予以申明。
- 多日趋势 7 个：按墙钟时间换算根数——`ret_7d`（168 根）、`ret_30d`（720 根）、`donchian_pos_30d`、`dist_high_30d`、`dist_low_30d`（720 根窗口）、`d1_gap_atr`、`d1_price_to_slow`（1h 重采样日线 EMA21/96，上一完整 UTC 日，日线历史 <96 天缺失）。
- 权重：币种×同 4 小时同侧聚簇降权（同一算法，聚簇窗口 4 根）。

## 协议与判定

- LightGBM 回归 `b4_2_net_atr`，超参与 15m 完全一致；扩窗 purged 年度 OOF 2022–2025，purge 5 天（覆盖 96 根标签窗）。
- 判定沿用 Gate A（十分位 Spearman > 0.8）+ Gate B（顶桶合并净 ATR > 0 且 ≥3/4 年为正）。
- 报告义务：顶桶毛/净、逐年、成本均值、与 15m a2（净 −0.134 / 毛 +0.167）同表对比。

产物落 `artifacts/local_trend_selector/`。
