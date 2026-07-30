# BIN-1H-EMAX 局部+趋势选择器移植诊断（2026-07-29）

- 契约：[`bin-1h-emax-local-trend-selector-contract-2026-07-29.md`](../specs/bin-1h-emax-local-trend-selector-contract-2026-07-29.md)；脚本：[`research_local_trend_selector.py`](../scripts/research_local_trend_selector.py)；产物：[`local_trend_selector_report.json`](../artifacts/local_trend_selector/local_trend_selector_report.json)。
- 背景：15m 家族证明局部+多日趋势特征可识别毛优势但过不了成本墙（[15m 双消融诊断](../../15m-ema-cross-lightgbm-event-selector/diagnostics/bin-15m-emax-feature-ablation-2026-07-29.md)）。本诊断把同一选择器移植到 1h 冻结事件（69,877 个 pool 事件，成本均值 0.197 ATR）。

## 结果（B4_2 净 ATR，OOF 2022–2025，purge 5 天）

- 十分位（1→10）：−0.268、−0.211、−0.090、−0.088、−0.086、−0.054、+0.011、−0.019、+0.009、**+0.030**；Spearman 0.964（Gate A 过）。
- 顶桶：净 **+0.030**（毛 +0.219，成本 0.186），5,523 事件，多头占 43%；逐年 2022 **−0.093**、2023 +0.120、2024 **−0.005**、2025 +0.094 → 2/4 年为正，**Gate B 未过**。
- 重要性前列：`qv_rel_30d`、`atr_pos_30d`、`d1_gap_atr`、`ret_30d`、`d1_price_to_slow`（多日趋势族继续领跑）。

## 判定

- 双门未全过，1h 单事件选择器维持不可变现；但相对 15m 是质变：顶桶净第一次转正（15m a2 为 −0.134），可识别毛优势（+0.22）首次追平成本墙（0.19）。
- 结论：优势量级随周期放大、成本随周期收缩的标度关系成立，方向继续指向 4h/1d（见 [4h 移植诊断](../../4h-ema-cross-lightgbm-event-selector/diagnostics/bin-4h-emax-local-trend-selector-2026-07-29.md)）。家族维持 `archived`。
