# Decision Log

## 2026-08-18 — 建立月度最强3/最弱3字面规则诊断

按用户给定规则新建独立家族，零调参回测全上市与 `ADV≥1000万` 两个冻结宇宙，并加反转对照。不登记版本。证据见[契约](specs/binance-1d-mcsm-ls3-diagnostic-contract-2026-08-18.md)与[诊断](diagnostics/binance-1d-mcsm-ls3-diagnostic-2026-08-18.md)。

## 2026-08-18 — 扩展机制诊断仍不晋升

按用户指定范围比较 long-only、广度、尾部裁剪、形成期、inverse-vol、组合风险缩放与 short 约束；Top10 和 short 波动过滤出现历史改善，但回撤、short 腿毁损与年度集中仍不通过，且全部历史已揭示。证据见[扩展诊断](diagnostics/binance-1d-mcsm-extensions-2026-08-18.md)。
