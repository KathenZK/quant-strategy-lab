# BIN-1D-BE-DASE Decision Log

## 2026-08-12 — P0 家族与合同冻结

- CBCT P1 growth `21.2707x/-37.20%`；RCR P0 growth `21.2605x/-69.66%`，终值几乎相同但机制和交易路径不同。
- 冻结独立资本 sleeve 合并，权重只取 `25/75、50/50、75/25`；两个单 sleeve 只作 controls。
- 不再平衡、不在 sleeve 间转移损益、不做风险目标或杠杆；组合终值不能靠缩放恢复。
- ordered MDD 必须逐小时重放两 sleeve 的 favorable/adverse，不接受日末净值相关性的近似。

## 2026-08-12 — P0 HARD-GATE-FAILED；research line closed

- `75% CBCT + 25% RCR` 同为 growth/risk frontier：base `21.2681x/-34.34%`，stress `20.6032x/-34.35%`，delay `7.8895x/-34.48%`。
- 两 sleeve 同时 underwater 小时占 `96.64%`；静态分散只能改善约 `2.86pp` MDD。
- state disagreement 样本稀少且 same-direction 跨年份符号不稳，不冻结动态 consensus gate。
- 按合同关闭，不增权重、不读取 audit/prospective。[P0 裁决](diagnostics/binance-1d-be-dase-p0-2026-08-12.md)
