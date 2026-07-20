# Live Specs

本目录保存 `HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble` 的 runner / dry-run / live validation 规格。

这里出现 `live spec` 不代表 live 批准；当前 V2 为
`dry-run active / replay parity PASS / live disabled / not live-ready`。

## 当前文件

- [hype-15m-tb-mii-ens-v2-live-validation-spec-not-live-ready-2026-07-09.md](hype-15m-tb-mii-ens-v2-live-validation-spec-not-live-ready-2026-07-09.md)：`V2 = HYPE-EMA-TB-V39 + HYPE-15M-MII-V1.4` 单账户组合的 live validation spec，包含 V35 live 切换边界、组合状态机、preempt 强平让位、保护单、重启恢复、风控和验收门禁；不构成实盘批准。

## 状态边界

进入任何 promotion 状态（`live spec`、`dry-run`、`live`）前，必须完成对应门禁；从 dry-run 申请 live 还需完成 replay 对拍、preempt 换仓审计、missing-bar fail-closed、交易所对账、重启恢复、kill switch、online open/close reconciliation 和 tiny-live-pilot 审批。
