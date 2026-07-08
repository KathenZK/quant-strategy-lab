# Live / Reproduction Specs

本目录保存 `HYPE-15M-Multi-Indicator-Intraday` 的实盘可行性审计、复现规格和 runner 设计前置文档。

## 当前文件

- `hype-15m-mii-v1-live-feasibility-2026-06-29.md`：`HYPE-15M-MII-V1` 实盘可行性审计，结论 `not promoted / not live-ready`。
- `hype-15m-mii-v1-2-reproduction-spec-not-live-ready-2026-06-30.md`：`HYPE-15M-MII-V1.2` 完整复现规格，包含数据、指标、参数、执行时序、伪代码、验收指标和实盘前 blockers；用于同事或 AI 复刻策略，不构成 promotion。
- `hype-15m-mii-v1-3-live-parameter-spec-not-live-ready-2026-07-01.md`：`HYPE-15M-MII-V1.3` 固定 `2.5x` sizing 的实盘参数规格，包含 runner TOML 参数、指标/信号/bracket 定义、live runner 时序差异和上线前硬性验收。
- `hype-15m-mii-v1-4-parameter-spec-not-live-ready-2026-07-08.md`：`HYPE-15M-MII-V1.4` 参数规格，记录 `V1.3 + min_rvol96=0.85` 的进取观察版本；尚未实现为 runner dry-run，不构成 promotion。

## 状态边界

本目录下出现 `spec` 不代表 promotion。进入任何 promotion 状态（`live spec`、`dry-run`、`live`）前，必须先完成资金费、盘口级滑点、runner 状态机、重启恢复、交易所对账、missing-bar fail-closed 和 kill switch 审计（状态词定义见 `../../../strategy-status-glossary.md`）。
