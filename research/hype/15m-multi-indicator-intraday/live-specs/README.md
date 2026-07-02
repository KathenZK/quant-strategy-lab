# Live / Reproduction Specs

本目录保存 `HYPE-15M-Multi-Indicator-Intraday` 的实盘可行性审计、复现规格和 runner 设计前置文档。

## 当前文件

- `hype-15m-mii-v1-live-feasibility-2026-06-29.md`：`HYPE-15M-MII-V1` 实盘可行性审计，结论 `NO-GO / not live-ready / not paper-live-ready`。
- `hype-15m-mii-v1-2-reproduction-spec-not-live-ready-2026-06-30.md`：`HYPE-15M-MII-V1.2` 完整复现规格，包含数据、指标、参数、执行时序、伪代码、验收指标和实盘前 blockers；用于同事或 AI 复刻策略，不是 live/paper-live handoff。
- `hype-15m-mii-v1-3-live-parameter-spec-not-live-ready-2026-07-01.md`：`HYPE-15M-MII-V1.3` 固定 `2.5x` sizing 的实盘参数规格，包含 runner TOML 参数、指标/信号/bracket 定义、live runner 时序差异和上线前硬性验收；不是 live/paper-live handoff。

## 状态边界

本目录下出现 `spec` 不代表 promotion。`candidate`、`paper-live`、`dry-run`、`handoff` 或 `live` 都必须先完成资金费、盘口级滑点、runner 状态机、重启恢复、交易所对账、missing-bar fail-closed 和 kill switch 审计。
