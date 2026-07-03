# HYPE Cross-Strategy Account

本目录记录 HYPE 多策略共享子账户、全局仓位约束、跨策略优先级和账户级风控相关的组合诊断。

它不是一个新的 alpha family，也不改变各策略原本的 promotion 状态。被组合的策略仍必须回到各自 family 文档判断：

- `HYPE-5M-Pullback-Trail`：`../5m-pullback-trail/README.md`
- `HYPE-15M-Multi-Indicator-Intraday`：`../15m-multi-indicator-intraday/README.md`

## 当前诊断

- `diagnostics/hype-pbtr-v6-2-1-mii-v1-3-shared-account-2026-07-02.md`：`HYPE-5M-PBTR-V6.2.1` 与 `HYPE-15M-MII-V1.3` 在同一 HYPEUSDT 子账户、全局单仓约束下的组合回放。

## 结论口径

- 组合收益不能简单等于两个策略独立收益相加；必须按实际 entry 时间排序并阻塞重叠持仓。
- 账户级回撤、全局 notional cap、跨策略 kill switch、挂单对账和重启恢复是组合运行的新增风险。
- 若任一子策略仍为 `not-live-ready`，组合也不得被提升为 `paper-live`、`dry-run handoff` 或 `live`。

## 产物规则

- 一次性组合回放脚本放在 `scripts/`。
- 被 Markdown 报告引用的 CSV/JSON 放在 `artifacts/`。
- 长期结论放在 `diagnostics/` 或 `decision-log.md`。
