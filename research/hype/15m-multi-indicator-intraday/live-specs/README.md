# Live Specs

本目录只保存 `HYPE-15M-Multi-Indicator-Intraday` 真正用于 runner、dry-run 或准实盘验证交接的 live specs。

研究侧参数规格放在 `../specs/`；实盘可行性审计放在 `../diagnostics/`。本目录下出现 `spec` 不代表 promotion。

## 当前文件

- `hype-15m-mii-v1-3-live-parameter-spec-not-live-ready-2026-07-01.md`：`HYPE-15M-MII-V1.3` 固定 `2.5x` sizing 的实盘参数规格，包含 runner TOML 参数、指标/信号/bracket 定义、live runner 时序差异和上线前硬性验收。
- `hype-15m-mii-v1-4-live-validation-spec-not-live-ready-2026-07-09.md`：`HYPE-15M-MII-V1.4` 给同事验证/runner 对拍用的 live validation spec，补齐数据质量、指标定义、信号/bracket、执行时序、验收清单和禁止项；不构成 promotion。
- `hype-15m-mii-v1-4a-dry-run-validation-spec-not-live-ready-2026-07-10.md`：`HYPE-15M-MII-V1.4A` 给用户小额 dry-run / shadow validation 用的交接规格，固定 `min_rvol96=0.85`、`TP=1.40*ATR96`、`SL=3.0*ATR96`；不构成 live-ready。

## 状态边界

进入任何 promotion 状态（`live spec`、`dry-run`、`live`）前，必须完成对应门禁；从 dry-run 申请 live 还需完成资金费、盘口级滑点、runner 状态机、重启恢复、交易所对账、missing-bar fail-closed、kill switch 与 online open/close reconciliation（状态词定义见 [strategy-status-glossary.md](../../../../docs/research-governance/strategy-status-glossary.md)）。
