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
- 当前 runner workspace `134` 个 unit tests 与 `12` 个 integration tests 全部通过；
  `cargo clippy --workspace --all-targets -- -D warnings` 通过；本 family 未产生新的
  strict parity 结论。
- EMA-X stop-only 存量迁移和迁移中断恢复已有定向测试；execution pause 只能在
  lock + venue/local/protection reconcile clean 后由 `risk-resume` 清除。schema
  切换禁止 binary-only rollback。
- 本次只迁移代码，**未部署、未重启线上**，也未采集新的 runtime trade/fill。
  状态保持 `dry-run / forward-test required / not live-ready`。交接约束见
  [V18 active handoff](../live-specs/hype-ema-x-v18-handoff-not-live-ready.md)。

结论：`keep dry-run / do not enable live`。

## 2026-07-13 统一 execution dry-run 已部署

- `main@cd00ef24c8f2c33d17bee19c51d017e264c76356` 与 SHA-256
  `0ce2b5513716cd84cf825abf19db4c65d6509b6386721c438bbc06fc022735a5`
  已随双服务切换安装；本实例启动时 flat、无迁移订单，health=`ok`。
- 跨 watchdog 周期 dry-run service PID 稳定、`NRestarts=0`、无 warning/error；
  未采集到新 EMA-X open/close/fill。状态保持
  `dry-run / forward-test required / not live-ready`。

## 2026-07-13 shutdown 通知去重已部署

- 双服务切换的 7 条策略级 shutdown 因两个 watchdog 竞态被放大到约 13-14 条。
  Runner `bd3f33d` 已部署：每 service 一条 `service_graceful_shutdown` 汇总，
  SQLite 原子 claim/lease 阻止重复消费；验证重启 outbox 仅 2 条且
  `attempts=1`。
- 仅影响运维通知，不影响本策略状态、订单或 PnL。

## 2026-07-13 service 稳定性修复（source，未部署）

- 同组 six-asset transient timeout 曾使整个 dry-run service 退出，暴露出单组故障
  会中断 EMA-X 的错误故障域；历史 watchdog 也可能把正常
  `already_processed` 误判为 stale。
- Runner source 已改为 group 独立 supervisor、transient 原地降级/恢复、
  entry-only 风险闸和 control-plane watchdog；EMA-X 持仓维护不得被 transient
  entry gate 阻断。当前生产仍为 `bd3f33d`，策略状态与 live-readiness 不变。
