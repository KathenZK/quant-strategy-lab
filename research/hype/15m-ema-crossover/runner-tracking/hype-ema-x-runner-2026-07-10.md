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

## 2026-07-13 service 稳定性修复已部署

- 同组 six-asset transient timeout 曾使整个 dry-run service 退出，暴露出单组故障
  会中断 EMA-X 的错误故障域；历史 watchdog 也可能把正常
  `already_processed` 误判为 stale。
- Runner source 已改为 group 独立 supervisor、transient 原地降级/恢复、
  entry-only 风险闸和 control-plane watchdog；EMA-X 持仓维护不得被 transient
  entry gate 阻断。Runner `e69589f` 已于 `21:02 CST` 部署 dry-run，初检
  health=`ok`、flat、无 warning/error；策略状态与 live-readiness 不变。

## 2026-07-14 StrategyDriver 最终迁移（仅代码，未部署）

- `hype_ema_x` 已从 legacy runtime adapter 迁入通用 `StrategyDriver`。EMA-X 的
  动态 allocation、normal/late entry、hard stop、warning-confirm、MFE 与
  exit memo 仍是策略本地纯状态机；订单、副作用、reconcile 和 ledger 统一由
  execution kernel 处理。
- 策略私有状态已进入 versioned `StrategyStateEnvelope`；旧扁平 exit memo
  仅允许一次性读取迁移，下次保存不再写回 `EngineState` 顶层。持仓期仍计算并
  记录当前 signal，不因 Driver `Hold` 丢失信号审计。
- EMA-X 显式声明 touch-only stop bar 口径，避免误套 bracket gap priority。
  replay handler 与 Driver factory 在策略模块通过 `inventory` 自注册。
- Runner workspace `152` 个 unit tests、`12` 个 integration tests、strict
  Clippy、六策略 smoke/replay 及两份配置校验通过。本次未部署、未采集新
  runtime trade/fill；结论继续为 `keep dry-run / do not enable live`。

## 2026-07-14 Driver 收尾验证（仅代码，未部署）

- execution kernel 已固定 target timing：新开仓只能 `NextOpen`，仓位替换必须
  persisted `AfterFlat`；同仓位 target 只更新保护，不把 allocation 变化静默当作
  resize。
- 旧 EMA-X exit memo 会在任何平台状态保存前先恢复进
  `StrategyStateEnvelope`；legacy JSON 定向测试覆盖方向、regime、index、reason、
  PnL 与 MFE。
- 最终验证为 `162` 个 unit tests、`12` 个 integration tests、strict Clippy、
  dry-run/live 配置校验和六策略 Binance smoke replay 全通过。本次未部署且无新
  trade/fill；`keep dry-run / do not enable live` 不变。

## 2026-07-14 Driver 最终加固（仅代码，未部署）

- EMA-X `last_exit_pnl` 明确恢复为旧 adapter/replay 使用的
  `allocation * side * (exit / entry - 1)` 毛价格收益，避免把手续费后的 net
  return 带入 late re-entry 门禁。
- mark-price stop 订单类型与 dry-run bar 价格源已拆成显式 descriptor 能力；
  EMA-X 保持 mark touch-only。Driver envelope、warning-confirm、MFE 与
  normal/late entry 状态机不变。
- 最终来源命令：`cargo test --workspace` 为 `170` 个 unit +
  `12` 个 integration 全通过；strict Clippy、两份 config 与六实例 smoke
  通过。`replay-dry-run --limit 2500` 当前 rolling window 为 `2` trades，
  其中 `1` 笔 late entry。
- 本次未部署、未重启、无新 runtime trade/fill；结论仍是
  `keep dry-run / do not enable live`。

## 2026-07-14 Driver state 与 mark 降级收口（仅代码，未部署）

- `high_water/low_water/mfe_atr/hard_bad_bars/warning_*` 已从平台
  `PositionState/PositionView` 移除，只保存在 EMA-X versioned envelope。
  历史 `entry_atr14` 一次性迁为通用 `entry_risk_value`，legacy open-state fixture
  覆盖 warning、MFE、水位、bad-bar counter 与 entry kind。
- mark-price touch-only 策略若对应 mark K 线暂不可得，不再用 trade OHLC 伪造
  stop；该 bar 不推进 decision clock，保留重试，同时仍允许策略软出场/timeout。
- state schema 升级改为逐步 `migrate_state_step`；保护执行方式只信
  `ProtectionPlan` 解析后持久化的 `PositionState.protection_execution`。
- 最终验证：`179` 个 unit tests、`12` 个 integration tests、strict Clippy、
  dry-run/live config、六实例 smoke 与六策略 2500-bar replay 全通过。
- 本次未部署、无新 runtime trade/fill；结论仍是
  `keep dry-run / do not enable live`。
