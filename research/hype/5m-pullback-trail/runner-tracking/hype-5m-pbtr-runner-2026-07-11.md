# HYPE-5M-PBTR-V6.2.1 执行治理跟踪 2026-07-11

## 范围

- Runner kind / mode：`hype_pullback` / `live tiny-live-pilot`
- 来源配置：`configs/live.toml`
- 部署：2026-07-11 16:14 CST 完成仅 live 的生产切换
- Runtime trade/fill 导出：未采集

## 2026-07-12 统一执行架构迁移（仅代码，未部署）

- `quant-runner` 的 dry-run 与 live 已在当前代码工作区收敛到唯一 execution
  状态机：稳定 client ID、submit 前持久化、`pending/tracked` 订单、入场后保护单、
  REST/User Data Stream 对账、异常 fail-closed，以及 platform ledger 记录。
- live venue 固定为 Binance REST + User Data Stream；dry-run venue 改为独立、
  可持久化的 `state/<instance>/simulated_venue.json`。两种 venue 复用同一套
  entry/exit/protection/reconcile 生命周期，不再由策略 runner 各自模拟成交。
- 已删除 `platform.execution.enabled` 和 live V1 fallback。配置不再允许绕过统一
  execution；V6.2.1 的 alpha、固定 bracket、timeout 和 sizing 边界没有变化。
- strict replay/parity 路径继续与 venue/runtime 隔离，本次迁移不应改变既有 replay
  结果。当前 runner workspace `131` 个 unit tests 与 `12` 个 integration tests 全部通过；
  `cargo clippy --workspace --all-targets -- -D warnings` 通过；本 family 未产生新的
  strict parity 结论。
- 最终执行安全审查保留 timeout open 的 gap-stop/gap-target reason，并补齐
  simulated orphan/emergency flatten 的成交价；无未解决 blocker。
- 后续发布门禁补强：`risk-resume` 只有在 runner lock + venue/local/protection
  reconcile clean 后才能清 pause；配置 schema 切换禁止 binary-only rollback，
  安装失败必须保持 service 停止。
- 存量 dry-run 持仓首 cycle 会写 `simulated_venue_migrated` 并补建模拟仓位/保护单；
  该迁移、中断恢复、EMA-X stop-only 与 six-asset 显式 symbol 已有定向测试。
- 本节只记录代码迁移：**未部署、未重启任何线上服务**，2026-07-11 已部署版本仍是
  当前线上事实；没有采集新的真实订单或 fill 证据。
- 状态保持 `tiny-live-pilot / forward-test required`，不得据此扩大资金、提升
  promotion、宣告 parity 新结论或改变 live-readiness。交接约束见
  [V6.2.1 active live spec](../live-specs/hype-5m-pbtr-v6-2-1-live-spec.md)。

## 已完成的保护措施

- `live_execution_sim.rs` 已覆盖 accepted-timeout 幂等、保护单部分成交、兄弟单撤销、
  保护/紧急平仓失败、entry 与 arm 之间进程终止、未成交孤儿单撤销和 user stream
  丢失等故障场景。
- Entry pending 会持续保留，直到 `PositionState` 已持久化。
- 启动时会自动撤销未成交孤儿 entry，或用 reduce-only 平掉交易所孤儿仓位；随后保持
  fail-closed 等待复核。
- Fallback critical JSONL 会自动排入 central outbox；已实现 outbox 投递状态、重试和
  backlog 告警。
- TB-MII fail-closed、manual halt、stale health 与 shared-group graceful shutdown
  已输出持久化/通知证据。
- 已定义 `connect_timeout` 和 binary-before-systemd-unit 的原子安装顺序。
- 来源 `configs/live.toml` 已启用 execution v2 与 private user stream。

## 部署证据

- 本地 Rust fmt、strict Clippy 与全部 unit/integration tests：通过。
- Lab main：`bb8586a`；Runner main：`712b3e9`。
- GitHub Actions run：`29145511766`；artifact：
  `quant-runner-linux-x86_64-712b3e96e630983bbc1e72c6d31f3a78788726bb`.
- Artifact / 已安装 binary SHA-256：
  `3cf36d61dfdb1cb8930a924614b00108323b9d00a49d05c42cb3a5c3c04f8487`.
- Preflight：live 本地/交易所状态 flat，无 open orders、无 open live ledger trade；
  旧服务 smoke-test `ok=true`。
- 原子安装顺序：先安装新 ELF binary，再安装 live unit，daemon reload 后只重启
  `quant-runner-live.service`。
- Dry-run 未重启，PID/unit 保持不变。
- 切换后：live `Type=notify`、`WatchdogSec=120`、PID `763218`、
  `NRestarts=0`、health `ok`、`position_open=0`。
- Ledger 依次输出 `runner_started`、`binance_user_stream_connected` 和健康 cycle；
  journal 未出现 warning 或更高等级记录。
- 完整 watchdog 周期后同一 PID 仍 active，`NRestarts=0`。
- 因信号窗口保持 flat，没有提交真实 Binance 订单。

## 结论

`keep tiny-live-pilot / execution v2 deployed and healthy`，不得增加资金。下一项强制
证据是首个真实 signal/order/fill 对账，需包含稳定 client ID、保护单、手续费、滑点
和 user-stream 时间戳。
