# BIN-15M-TSM scripts

本目录存放本家族的一次性研究脚本（P1 段级裸基线、敏感性集、P2 组合基线等）。

- 数据装载必须复用 [`BIN-15M-EMAX-LGBM` P0 冻结数据湖](../../15m-ema-cross-lightgbm-event-selector/diagnostics/bin-15m-emax-lgbm-p0-data-freeze-2026-07-24.md)口径（含 `date=*` 遗留日分区 union 与 `symbol IS NOT NULL` 排除规则），不得新增同步。
- 开发期脚本不得读取锁定 OOS 窗口（`2026-01-01`–`2026-06-30`）的策略表现。
- 参数以[冻结契约](../specs/bin-15m-tsm-research-contract-2026-07-28.md)为准，脚本内不得引入契约之外的可调项。
