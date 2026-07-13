# HYPE-EMA-X-V18 Runner 治理记录 2026-07-10

- Kind / mode：`hype_ema_x` / dry-run；live 保持禁用。
- Runner 配置：`configs/dryrun.toml`，notional `10 USDT`，沿用既有 state path。
- 观察范围：仅 source-level / offline governance validation。
- Trades/fills：本次未导出 runtime trade。
- 事件：未观察到 incident；未执行部署。

## 2026-07-12 统一执行架构迁移（仅代码，未部署）

- dry-run/live 现在共用唯一 execution 状态机：稳定 client ID、submit 前持久化、
  `pending/tracked`、实际 fill 数量、保护单、reconcile、fail-closed 与 platform
  ledger。EMA-X live exit 继续不依赖未来 REST K-line open。
- live venue 固定为 Binance REST + User Data Stream；dry-run venue 使用实例独立
  `state/<instance>/simulated_venue.json`，entry/exit 均走订单生命周期。
- 已删除 `platform.execution.enabled` 和 live V1 fallback；不得绕回旧 executor。
- strict replay/parity 路径保持隔离，本次迁移不应改变 replay 结果。Parity 仍为
  `PENDING`；offline baseline 不能替代 Python/Rust 全窗口 trade-path parity。
- 当前 runner workspace `131` 个 unit tests 与 `12` 个 integration tests 全部通过；
  `cargo clippy --workspace --all-targets -- -D warnings` 通过；本 family 未产生新的
  strict parity 结论。
- EMA-X stop-only 存量迁移和迁移中断恢复已有定向测试；execution pause 只能在
  lock + venue/local/protection reconcile clean 后由 `risk-resume` 清除。schema
  切换禁止 binary-only rollback。
- 本次只迁移代码，**未部署、未重启线上**，也未采集新的 runtime trade/fill。
  状态保持 `dry-run / forward-test required / not live-ready`。交接约束见
  [V18 active handoff](../live-specs/hype-ema-x-v18-handoff-not-live-ready.md)。

结论：`keep dry-run / do not enable live`。
