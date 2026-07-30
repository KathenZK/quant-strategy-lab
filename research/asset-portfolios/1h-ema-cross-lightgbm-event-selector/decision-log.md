# Decision Log — Binance-1H-EMA-Cross-LightGBM-Event-Selector

## 2026-07-24 家族立项（诊断线）

- 决策：在 15m 家族 [`BIN-15M-EMAX-LGBM`](../15m-ema-cross-lightgbm-event-selector/README.md) HARD-GATE-FAILED 归档后，按"换周期"方向立 `1h` 独立诊断线。改变的假设：成本折 ATR 单位约减半（名义成本固定、`1h` ATR 更大），且毛期望随价格尺度有微弱上升迹象。不继承 15m 线证据；`2026-01`–`2026-06` 视为污染 holdout，干净 OOS 只能取 `2026-07` 之后的前瞻窗口。首个 kill test 为 P1 基线：若毛期望仍钉在零附近且高分原料不足，线止于诊断。
- 证据：[15m P5 揭示诊断](../15m-ema-cross-lightgbm-event-selector/diagnostics/bin-15m-emax-lgbm-p5-locked-oos-reveal-2026-07-24.md)、[15m 栅栏几何对照](../15m-ema-cross-lightgbm-event-selector/artifacts/custom_bracket_tp5_sl7.json)

## 2026-07-24 P1 基线完成：成本减半假设成立，研究对象收窄为死叉空头

- 决策：`1h` 交叉成本折 ATR 中位 0.172（15m 的一半），三组栅栏毛期望全部为正且随宽度走强；但多头侧 2021 后结构性死亡（2025 毛期望 −0.079 ATR），净期望负号全部由多头贡献。死叉空头原始基线六年四正（含 2024/2025），统计强度约 1.3–2.3 SE，值得继续但未证实。本线放弃双侧设计，后续仅研究死叉空头；`2026H1` 为污染 holdout，裁决只能用前瞻窗口。
- 证据：[P1 基线诊断](diagnostics/bin-1h-emax-lgbm-p1-baseline-2026-07-24.md)、[baseline_1h_report.json](artifacts/baseline_1h_report.json)

## 2026-07-24 2026H1 复用窗口审计：空头结构延续但净期望翻负

- 决策：对死叉空头做 2026H1 一次性复用窗口审计（非干净 OOS，不用于调参）。多头死亡与空头毛期望为正（+0.153）的结构性结论延续，但空头净期望 −0.062：四正两负的月度里被 2026-04 单月 −1.04 ATR 逼空月拖垮。结论：空头原料真实但薄且脆，裸做不成立，推进必须带状态门控/选择器与挤仓尾部防护。
- 证据：[2026H1 复用窗口审计](diagnostics/bin-1h-emax-lgbm-2026h1-reused-audit-2026-07-24.md)、[audit_2026h1_reused_window.json](artifacts/audit_2026h1_reused_window.json)

## 2026-07-24 数据修复：基线与 2026H1 审计漏读 legacy 分区，补齐主流币后重跑

- 决策：装载 glob 漏读 1h 湖 `date=*` 旧版按日分区（BTC/ETH/SOL/BNB/TRX/HYPE 的主存储），基线与 2026H1 审计全量重跑：基线结论方向全部不变（b4_2 池内净 −0.057、空头全体 +0.024）；2026H1 空头净 −0.062 → −0.030，2026-04 逼空月 −1.05 与"裸做不成立"结论不变。首版产物留档 `*_v1_missing_majors.*`；根因与修复详见 4h 家族同日修复条目。
- 证据：[P1 修正记录](diagnostics/bin-1h-emax-lgbm-p1-baseline-2026-07-24.md)、[审计修正记录](diagnostics/bin-1h-emax-lgbm-2026h1-reused-audit-2026-07-24.md)

## 2026-07-29 局部+趋势选择器移植：顶桶净首次转正但 2/4 年为正，Gate B 未过

- 决策：按预注册契约把 15m 家族的局部+多日趋势 LightGBM 选择器（a2 特征集）移植到 1h 冻结事件。顶桶净 +0.030（毛 +0.219 vs 成本 0.186）、Spearman 0.964，但逐年 2/4 为正，Gate B 未过。判定：1h 单事件选择器不可变现，维持 `archived`；但可识别毛优势首次追平成本墙，标度关系（优势随周期升、成本随周期降）成立，指向 4h。
- 证据：[移植契约](specs/bin-1h-emax-local-trend-selector-contract-2026-07-29.md)、[移植诊断](diagnostics/bin-1h-emax-local-trend-selector-2026-07-29.md)、[local_trend_selector_report.json](artifacts/local_trend_selector/local_trend_selector_report.json)
