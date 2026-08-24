# Artifacts

本目录保留 `2026-08-18` Long10 诊断，`2026-08-19` 宽度、固定20%波动目标/10-20缓冲、正收益限定/现金缺口诊断，以及 `2026-08-20` 可实盘化、MH136、target12 执行时序和赚钱效应/领涨延续诊断的汇总 JSON、全指标、成本归因、换仓清单、风险系数、日/月路径、状态标签、延续衰减、分年、时间切片、bootstrap、容量与 blocker 明细。

`2026-08-20` 执行审计裁决为 `HARD_BLOCKER / PERFORMANCE_INVALIDATED`：旧路径有 41 个不可成交或持仓缺价事件；按 `00:15 UTC` 可成交条件重选后仍有 15 个退出/估值 blocker。因此本目录中的历史绩效只能作方向性诊断，不能作为 promotion、runner handoff 或资金配置证据。

所有产物可由[脚本目录](../scripts/README.md)中的对应回测脚本按冻结口径重建；日级派生缓存位于 `data/cache/binance_perp_1d_from_15m/`，不构成独立研究证据。
