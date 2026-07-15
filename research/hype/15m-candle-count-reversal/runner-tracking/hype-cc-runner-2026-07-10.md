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
- 当前 runner workspace `134` 个 unit tests 与 `12` 个 integration tests 全部通过；
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

## 2026-07-13 统一 execution 生产 dry-run 切换

- Runner `cd00ef24c8f2c33d17bee19c51d017e264c76356` 经
  [GitHub Actions run 29223536186](https://github.com/KathenZK/quant-runner/actions/runs/29223536186)
  构建，artifact SHA-256
  `0ce2b5513716cd84cf825abf19db4c65d6509b6386721c438bbc06fc022735a5`。
- 用户明确批准在两笔 dry-run open trade 存续时切换。服务于
  `2026-07-13T04:25:04Z` 停止，配置与二进制同批更新，dry-run/live 均恢复
  active；跨完整 watchdog 周期 PID 稳定、`NRestarts=0`、无 warning/error。
- 本策略原 short `0.44` 持仓迁入 `HYPEUSDT` simulated venue：entry order
  `1` 已成交，TP `2` 与 SL `3` 为 NEW reduce-only，pending 为空、
  fail-closed 为空、health=`ok`。完整来源、时间、价格、费用/滑点和 stable client
  ID 见 [迁移 artifact](../artifacts/hype_cc_v35_unified_execution_migration_2026-07-13.json)。
- 这是执行状态迁移，不是新的 replay parity 或 live 批准；状态保持
  `dry-run / forward-test required / not live-ready`。

## 2026-07-13 shutdown 通知去重已部署

- 双服务切换的 7 条策略级 shutdown 因两个 watchdog 竞态被放大到约 13-14 条。
  Runner `bd3f33d` 已部署：每 service 一条 `service_graceful_shutdown` 汇总，
  SQLite 原子 claim/lease 阻止重复消费；验证重启 outbox 仅 2 条且
  `attempts=1`。
- 仅影响运维通知，不影响本策略状态、订单生命周期或 PnL。

## 2026-07-13 service 稳定性修复已部署

- 同组 six-asset transient timeout 曾使整个 dry-run service 退出，暴露出单组故障
  会中断 candle-count 持仓维护的错误故障域。
- Runner source 已改为 group 独立 supervisor；transient 只关闭新入场，已有仓位
  的 simulated venue reconcile、保护、撤单和平仓必须继续。control-plane
  watchdog 不再因单策略 stale 重启兄弟策略。Runner `e69589f` 已于
  `21:02 CST` 部署 dry-run，初检 health=`ok`、flat、无 warning/error；
  策略状态、PnL 与 live-readiness 不变。

## 2026-07-14 StrategyDriver 最终迁移（仅代码，未部署）

- `hype_candle_count` 已从 legacy runtime adapter 迁入通用 `StrategyDriver`。
  entry filter、early exits、risk multiplier 与 cooldown 保持在策略模块；
  open/close/protection/reconcile 统一由 execution kernel 执行。
- risk multiplier/cooldown 已进入 versioned `StrategyStateEnvelope`；旧扁平字段
  只读迁移后停止写回。`ExecutionEvent::Closed` 定向测试覆盖 stop 后
  `risk_multiplier=0.5`、`cooldown=8`，持仓期 signal 继续写 ledger。
- mark-price stop/take 显式声明 touch-only bar 口径；funding/mark 由
  `MarketRequirement` 驱动 dispatcher 快照，不再由策略自行拉取。
- Runner workspace `152` 个 unit tests、`12` 个 integration tests、strict
  Clippy、六策略 smoke/replay 及配置校验通过。本次未部署、未采集新 fill；
  历史 underperformance blocker 和 `do not enable live` 结论不变。

## 2026-07-14 Driver 收尾验证（仅代码，未部署）

- execution kernel 已明确 target 语义：同仓位 target 只更新保护，symbol/side/
  allocation 变化必须显式 `Replace` 并按 persisted `AfterFlat` 先平后开；不提供
  隐式仓内 resize。
- 旧 `risk_multiplier` / `cooldown_remaining` 会在任何平台状态保存前先恢复进
  `StrategyStateEnvelope`，并有 legacy JSON 定向测试，避免 early-save 丢状态。
- 最终验证为 `162` 个 unit tests、`12` 个 integration tests、strict Clippy、
  dry-run/live 配置校验和六策略 Binance smoke replay 全通过。本次未部署且无新
  trade/fill；`keep dry-run / do not enable live` 不变。

## 2026-07-14 Driver 最终加固（仅代码，未部署）

- Runner 将 mark/funding 可选依赖错误与成功取得的 closed candles 分开保存；
  残缺依赖禁止 risk-increasing target，但已持仓的 early exit、保护维护和关账
  仍可继续。
- Candle-Count 保持 mark-price touch-only stop/take、risk multiplier、cooldown
  与 legacy envelope 迁移口径；没有 TOML、state path 或 allocation 变更。
- 最终来源命令：`cargo test --workspace` 为 `170` 个 unit +
  `12` 个 integration 全通过；strict Clippy、两份 config 与六实例 smoke
  通过。2500-bar strict replay 为 `16` entries / `15` exits，当前窗口
  `mark_missing_bars=0`。
- 本次未部署、未重启、无新 runtime fill；历史 underperformance blocker 与
  `keep dry-run / do not enable live` 不变。

## 2026-07-14 mark K 线降级与插件边界收口（仅代码，未部署）

- Candle-Count 的 mark touch-only stop/take 在 mark K 线暂不可得时不再回退
  trade OHLC；当前 bar 保持未处理并重试，避免永久漏判或伪造保护成交。
  early exit、timeout、risk multiplier 与 cooldown 状态机仍可按可用输入维护。
- replay report/handler 和严格 replay 包装已归策略模块；默认配置由本地 factory
  构造，中心 bootstrap/replay 不再保存 Candle-Count 专属入口。
- 保护 execution 从 plan 解析并持久化，schema 升级采用显式逐步 migration；
  现有 risk/cooldown envelope 与策略参数未变。
- 最终验证：`179` 个 unit tests、`12` 个 integration tests、strict Clippy、
  dry-run/live config、六实例 smoke 与六策略 2500-bar replay 全通过。
- 本次未部署、无新 runtime fill；历史 underperformance blocker 与
  `keep dry-run / do not enable live` 不变。
