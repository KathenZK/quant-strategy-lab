# HYPE-CANDLE-COUNT-V35 Runner 治理记录 2026-07-10

- Kind / mode：`hype_candle_count` / dry-run；没有获批 live 实例。
- Runner 配置：`configs/dryrun.toml`，notional `10 USDT`，沿用既有 state path。
- 观察范围：仅 source-level / offline governance validation。
- Trades/fills：本次未导出 runtime trade。
- 历史 live underperformance 继续作为 blocker。

## 2026-07-12 统一执行架构迁移（仅代码，未部署）

- dry-run/live 现在共用唯一 execution 状态机：稳定 client ID、submit 前持久化、
  `pending/tracked`、实际 fill 数量、保护单、reconcile、fail-closed 与 platform
  ledger。
- live venue 固定为 Binance REST + User Data Stream；dry-run venue 使用实例独立
  `state/<instance>/simulated_venue.json`，entry/exit 均走订单生命周期。
- 已删除 `platform.execution.enabled` 和 live V1 fallback；不得绕回旧 executor。
- strict replay/parity 保持隔离，本次迁移不应改变 replay 结果。Parity 仍为
  `PENDING`；offline baseline 与既有 strict replay tests 都不能替代
  Lab-vs-Runner 全窗口路径对拍。
- 当前 runner workspace `131` 个 unit tests 与 `12` 个 integration tests 全部通过；
  `cargo clippy --workspace --all-targets -- -D warnings` 通过；另以 Binance 最新
  `2000` 根 15m 数据完成 strict replay smoke（`mark_missing_bars=0`、`12` 笔已
  平仓），但这不是 Lab-vs-Runner 全窗口 parity，状态仍为 `PENDING`。
- 最终执行安全审查修正 simulated venue 字符串 order ID 兼容、orphan/emergency
  flatten 定价和 dry-run `exchange_flat` PnL source；无未解决 blocker。
- exit memo 已改为与 ledger 使用相同的 dry-run 方向滑点口径；execution pause
  只能在 lock + venue/local/protection reconcile clean 后由 `risk-resume` 清除。
  schema 切换禁止 binary-only rollback。
- 本次仅迁移代码，**未部署、未重启线上**，也没有新增 runtime trade/fill。
  历史 underperformance、promotion 与 live-readiness 结论不变。交接约束见
  [V35 active handoff](../live-specs/hype-cc-v35-handoff-not-live-ready.md)。

结论：`keep dry-run / do not enable live`。
