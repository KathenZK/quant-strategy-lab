# HYPE-15M-MII V1.4A dry-run 部署记录 — 2026-07-10

## 状态

`HYPE-15M-MII-V1.4A` 已于 `2026-07-10T07:13:16Z` 部署到既有
`hype-mii-dry-run` 实例。部署后的首个 15m cycle 健康；状态仍为 not live-ready。

## Runner 配置

- Runner：`quant-runner`，`kind=hype_mii`，`mode=dry_run`。
- Instance：`hype-mii-dry-run`（实例名有意不带版本）。
- Identity：`HYPE-15M-MII-V1.4A`。
- Market：Binance USD-M `HYPEUSDT`，`15m`，仅闭合 K。
- Sizing：`dry_run_notional_usdt=10`、`exposure=2.5`、`leverage=3`、
  `margin_mode=isolated`。
- State：沿用 `/home/admin/quant-runner/state/hype-mii-dry-run`，因为此前 V1.3
  实例从未开仓。
- 固定策略参数：`min_rvol96=0.85`、`tp_atr_mult=1.40`、
  `sl_atr_mult=3.0`、`timeout_bars=24`、fee `0.001`/fill、slippage
  `0.0004`/fill。
- Live 边界：runner 在 `live` mode 拒绝此 identity。

## 本地验证

来源 workspace：`/Users/ZK/OpenCode/quant-runner`。

- `cargo fmt --check`：通过。
- `cargo test -p quant-runner`：通过（`63` 个 library tests、`2` 个 integration
  tests）。
- `smoke-test --name hype-mii-dry-run`：通过。
- Binance public closed-Kline smoke replay（`2500` bars）：`11` 个 signals、
  `10` 笔 simulated trades；replay 输出了要求的 V1.4A 参数快照。

同一 recent 2500-bar 窗口也与 Python research engine 对拍：两边选出相同的 `10`
笔交易，entry/exit 时间戳、side 和 exit reason 一致。Rust 在价格层应用配置的 fill
slippage，因此 fill price 有意不等于 raw K+1 open。

## 部署证据

- 初次 V1.4A 部署 commit：
  `a52562ee057c19f28541a5ccc8ff5522d31efefc`
  （implementation commit `7e30d6d` + Linux artifact workflow）。
- 初次 build 来源：GitHub Actions run `29075757922`，native
  `x86_64-unknown-linux-gnu`；交易服务器未执行编译。
- 初次 artifact SHA-256：
  `db7f446b835a9d39d25670d2e510f26f6c2d107bdf3f843c1592e8ce98e6a480`.
- 当前已部署 commit：`61cb32a01944efe9011167cbb9ab0bef6fcfccf2`。
- 当前 build 来源：GitHub Actions run `29076613028`；artifact SHA-256
  `f76cfcffa3908c25d2b29913895937819c313fc34487e1efcf3a665f66bb5380`.
- 当前 dry-run config SHA-256：
  `444cc8407e61e5ba3d23a692d5ed2700795238027042d01d336dace832201a1d`.
- 来源命令/证据：systemd status/journal、platform SQLite
  `strategy_instances`、`strategy_health`、`events`，以及已安装 binary 的
  `replay-dry-run --limit 300` parameter snapshot.
- 仅重启 `quant-runner-dryrun.service`；live service 保持既有 PID active。
- 重启前 MII state：flat，historical/open trades 均为 `0`，无历史 signal；沿用既有
  state path。
- 部署后首个 cycle：runner 于 `2026-07-10T07:13:16Z` 启动，并在
  `2026-07-10T07:15:03Z` 处理 `2026-07-10T07:00:00Z` 闭合 signal bar；
  event 为 `no_signal`，`strategy_health.status=ok`、`position_open=0`。
- 已安装参数快照：internal identity `HYPE-15M-MII-V1.4A`、
  `min_rvol96=0.85`, `tp_atr_mult=1.40`, `sl_atr_mult=3.0`,
  `timeout_bars=24`.
- 重启后 journal 未出现 warning 或更高等级记录；其他 strategy health rows
  均保持 `ok`。
- `2026-07-10T07:31Z` 部署 dry-run 启动通知支持；随后
  `quant-runner-dryrun.service` 重启成功，并通过已配置 DingTalk webhook 发送
  `QuantRunner dry-run 服务启动`。Dry-run trade 通知和 daily-summary scheduler
  仍禁用；live service 保持既有 PID。通知重启后 journal 未出现 warning 或更高等级
  记录。

## 观察门禁

当前尚无 V1.4A runtime open、close、fill、fee、funding-boundary、slippage 或
order ID。首笔实际交易必须用 signal/bar 时间戳、fill proxy、side、
quantity/notional、bracket、exit reason、fees 和稳定 ledger event/trade ID 与
Python K+1/K+2 对账，完成前不得形成 keep/adjust 决策。当前结论：继续小额 dry-run
观察，不做 live promotion。

## 2026-07-12 统一执行架构迁移（仅代码，未部署）

- 当前 `quant-runner` 工作区已让 dry-run/live 共用唯一 execution 状态机：稳定 client
  ID、submit 前持久化、`pending/tracked`、按实际 fill sizing、保护单、reconcile、
  fail-closed 与 platform ledger。
- live venue 固定为 Binance REST + User Data Stream；dry-run venue 为实例独立的
  `state/<instance>/simulated_venue.json`。MII 的模拟 entry、bracket、timeout exit
  也进入与 live 相同的订单生命周期，不再由 runner 直接改 position。
- 已删除 `platform.execution.enabled` 和 live V1 fallback；`hype_mii` 仍为代码级
  dry-run only，不能因为统一状态机存在而启用 live。
- strict replay/parity 路径保持隔离，本次迁移不应改变既有 2500-bar `10/10`
  对比；该证据仍不是标准全窗口 parity gate，manifest parity 继续为 `PENDING`。
- 当前 runner workspace `134` 个 unit tests 与 `12` 个 integration tests 全部通过；
  `cargo clippy --workspace --all-targets -- -D warnings` 通过；本 family 未产生新的
  strict parity 结论。
- 最终执行安全审查保留 timeout open 的 gap-stop/gap-target reason，并补齐
  simulated orphan/emergency flatten 的成交价；无未解决 blocker。
- Runner-wide 发布门禁已补强：execution pause 只能在 lock + venue/local/protection
  reconcile clean 后由 `risk-resume` 清除；schema 切换禁止 binary-only rollback，
  失败时 service 保持停止。
- 这是代码迁移，**未部署、未重启线上**；2026-07-10 已部署实例、状态目录和线上
  进程事实不变，也没有新增 open/close/fill 统计。
- 结论保持 `dry-run validation / not live-ready`，不改变 promotion、parity 或
  live-readiness。执行契约见
  [V1.4A active handoff](../live-specs/hype-15m-mii-v1-4a-dry-run-validation-spec-not-live-ready-2026-07-10.md)。

## 2026-07-13 统一 execution dry-run 已部署

- `main@cd00ef24c8f2c33d17bee19c51d017e264c76356` 与 SHA-256
  `0ce2b5513716cd84cf825abf19db4c65d6509b6386721c438bbc06fc022735a5`
  已随双服务切换安装；本实例启动时 flat、无迁移订单，health=`ok`。
- 跨 watchdog 周期 dry-run service PID 稳定、`NRestarts=0`、无 warning/error；
  未采集到新 MII open/close/fill。状态保持 `dry-run validation / not live-ready`。

## 2026-07-13 shutdown 通知去重已部署

- 双服务切换的 7 条策略级 shutdown 因两个 watchdog 竞态被放大到约 13-14 条。
  Runner `bd3f33d` 已部署：每 service 一条 `service_graceful_shutdown` 汇总，
  SQLite 原子 claim/lease 阻止重复消费；验证重启 outbox 仅 2 条且
  `attempts=1`。
- 仅影响运维通知，不影响本策略状态、订单或 PnL。

## 2026-07-13 service 稳定性修复已部署

- 同组 six-asset transient timeout 曾使整个 dry-run service 退出，暴露出单组故障
  会中断 MII 的错误故障域；历史 watchdog 也可能把正常 `already_processed`
  误判为 stale。
- Runner source 已改为 group 独立 supervisor、transient 原地降级/恢复、
  entry-only 风险闸和 control-plane watchdog。Runner `e69589f` 已于
  `21:02 CST` 部署 dry-run，初检 health=`ok`、flat、无 warning/error；
  MII 配置、状态、订单、PnL 与 live-readiness 不变。

## 2026-07-14 StrategyDriver 迁移（仅代码，未部署）

- `hype_mii` 是首个迁入通用 `StrategyDriver` 执行核的策略。策略层现在声明
  `MarketRequirement`，读取共享 `FeaturedFrame`，输出带符号
  `TargetPosition`；执行核仍复用既有 stable client ID、persist-before-submit、
  simulated/live venue、保护单、reconcile、ledger 和通知链。
- V1.4A 的 RSI/MACD/ATR96/RVOL 信号、`exposure=2.5`、fee/slippage、
  `TP=1.40*ATR96`、`SL=3.0*ATR96`、`timeout=24` 均未改变。Driver 输出相对
  TP/SL 距离，执行核在真实/模拟 entry fill 后解析绝对保护价格，避免参考价与
  成交价偏差改变 bracket。
- 现有 `engine_state.json` 路径不变；新增
  `strategy_state={strategy_id,schema_version,payload}` envelope。MII 当前是
  stateless payload，旧 flat/open position 均继续由原 `PositionState` 和统一
  execution safety 字段恢复。
- 最终架构已删除中心 `RuntimeModel`、legacy adapter、runtime handler 与
  descriptor 数组；MII 在自己的策略模块通过 `inventory` 自注册 Driver factory
  和 replay handler，执行核不再因新增策略增加分支。
- 本地验证：workspace 全量 `cargo test --workspace` 与
  `cargo clippy --workspace --all-targets -- -D warnings` 通过；Driver/legacy
  entry geometry 对拍通过；`smoke-test --name hype-mii-dry-run` 为
  `ok=true`。Binance public closed-Kline `replay-dry-run --limit 2500` 在当前
  窗口输出 `6` signals / `6` trades；这是滚动 smoke，不替代标准窗口 parity。
- 本次没有部署、没有重启 service，也没有采集新的 runtime open/close/fill；
  当前线上仍是 Runner `e69589f`。结论保持
  `dry-run validation / not live-ready`，首个 Driver 版本部署后仍需检查
  no-signal cycle、首笔 fill 后 TP/SL 几何、重启恢复和 ledger 生命周期。

补充：最终 workspace 六条策略均已迁入 Driver；`EngineState` 不再保存策略专属
顶层字段，旧字段只读迁移到 versioned `StrategyStateEnvelope` 后即停止写回。
全量 `162` 个 unit tests、`12` 个 integration tests、strict Clippy、六策略
smoke/replay 与 dry-run/live 配置校验通过；这仍是未部署的代码证据，不提升状态。
执行契约已固定：新仓 target 只能 `NextOpen`，allocation/side/symbol 变化必须
显式 `Replace` 并使用 persisted `AfterFlat`，不提供隐式仓内 resize。

## 2026-07-14 Driver 最终加固（仅代码，未部署）

- Runner 工作树补齐 exact decision clock：实例 `HYPE/USDT:USDT 15m` 缺失时
  cycle 只降级，不再借其他 symbol/timeframe 推进 processed timestamp。
- mark/funding 错误与 closed candles 分开记录；依赖残缺继续禁止新入场和
  Replace，已有仓位维护/平仓不因可选依赖失败被短路。MII 的信号、bracket、
  fee/slippage 与 timeout 未修改。
- 最终来源命令：`cargo test --workspace` 为 `170` 个 unit +
  `12` 个 integration 全通过；strict Clippy、dry-run/live config 校验与六实例
  smoke 均通过。`replay-dry-run --limit 2500` 当前 Binance rolling window 为
  `6` signals / `6` trades。
- 本次未部署、未重启、无新 runtime open/close/fill；状态仍为
  `dry-run validation / not live-ready`，rolling smoke 不替代标准 parity。

## 2026-07-14 Driver 架构收口（仅代码，未部署）

- replay report/handler 已完全归策略模块，策略默认配置由本地 factory 构造；
  `bootstrap/config.rs` 与中心 replay 不再保存 MII 专属 helper。
- `ProtectionPlan.execution -> PositionState.protection_execution` 成为保护执行方式的
  单一事实；旧仓位 fallback 仅做一次性迁移。Driver state schema 升级改为显式
  `N -> N+1` 步进迁移。
- decision clock 缺失时 flat MII 继续禁止开仓；已有 pending replacement/持仓维护
  不得借其他 symbol/timeframe 推进 processed bar。
- 最终验证：`179` 个 unit tests、`12` 个 integration tests、strict Clippy、
  dry-run/live config、六实例 smoke 与六策略 2500-bar replay 全通过。
- 本次未部署、未改 TOML/state path、无新 runtime fill；状态仍为
  `dry-run validation / not live-ready`。
