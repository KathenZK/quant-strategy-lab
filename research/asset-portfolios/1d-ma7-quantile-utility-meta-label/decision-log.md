# BIN-1D-MA7-QUML 决策记录

## 2026-08-10 — 从 Flow Increment 失败转入 Price Utility Quantile Calibration

TFML fresh test 已证伪 flow 增量，但 price-only control 的 aggregate economics 与 ranking 仍为正；决定不在已揭示八资产上调 absolute threshold，改用 BCH/ETC/XLM/ATOM/VET/NEAR/AAVE/FIL 第二组未见资产，检验只由 train predictions 定义的 quantile policy，详见 [P0/P1 合同](specs/binance-1d-ma7-quml-p0-p1-contract-2026-08-10.md) 与 [TFML 失败诊断](../1d-ma7-taker-flow-meta-label/diagnostics/binance-1d-ma7-tfml-p1e-fresh-universe-2026-08-10.md)。

## 2026-08-10 — 原 P1 盲测裁决（后续撤回）

P0 通过后，second-fresh quantile OOF 的 mean `-0.0694%`、PF `0.910`、ranking Spearman `0.0173`，相对 absolute control 的增量通过概率仅 `65.94%`；决定不运行 P2、不补第三组历史资产、不读取 HYPE，并关闭该历史 pooled 选择路线。BCH/ETC/XLM 因 FAPI 明确 IP ban 在 outcome 读取前改用 Binance Vision 官方月包与日包缺口修复，source quality blocker 为零；详见 [P1 诊断](diagnostics/binance-1d-ma7-quml-p1-development-2026-08-10.md)。

## 2026-08-10 — 撤回 P1 盲测裁决

复核确认21资产 market features 在 held split 前预计算，held source history 进入其他训练行，违反冻结的全历史排除；P1 改为 invalidated evidence 并 fail closed。P0/source quality 仍有效，但已揭示 second-fresh 不得修后重称 OOS，且不补第三组历史资产、不读 HYPE继续有效；详见 [P1 复核更正](diagnostics/binance-1d-ma7-quml-p1-development-2026-08-10.md)。
