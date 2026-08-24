# Binance BTC/ETH 1D Dual-Alpha Sleeve Ensemble

- family：`Binance-1D-BTCETH-Dual-Alpha-Sleeve-Ensemble`
- short id：`BIN-1D-BE-DASE`
- 状态：`research line closed / HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 当前版本：无
- 机制：冻结 CBCT-P1 growth 与 RCR-P0 growth 作为两个独立固定资本 sleeve，无跨 sleeve 再平衡
- 目标：development 成本后 `>=20x`、保守 ordered `1h` MDD `<=20%`

本 family 检验两个约 `21.26x` 的独立 development alpha 路径能否通过时间错位降低组合回撤。它不是把低收益风险臂混入后再用杠杆恢复收益，也不是 MA7 V2。

P0 最佳固定权重 `75% CBCT + 25% RCR` 为 `21.2681x/-34.34%`；收益保持但 MDD与delay失败，`0/3` hard-pass，audit/prospective未读取。

阅读顺序：[P0 冻结合同](specs/binance-1d-be-dase-p0-contract-2026-08-12.md) → [P0 裁决](diagnostics/binance-1d-be-dase-p0-2026-08-12.md) → [主账](binance-1d-be-dase-core-ledger.md) → [决策日志](decision-log.md)。
