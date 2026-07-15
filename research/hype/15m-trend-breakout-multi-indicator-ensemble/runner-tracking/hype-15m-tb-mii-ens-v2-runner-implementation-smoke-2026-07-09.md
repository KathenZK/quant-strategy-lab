# HYPE-15M-TB-MII-ENS-V2 Runner 实现 Smoke 2026-07-09

状态：

```text
runner kind implemented / replay parity pass / continuous dry-run runtime implemented / disabled live pilot code path implemented / live not enabled
```

## 2026-07-12 统一执行架构迁移（仅代码，未部署）

- `hype_tb_mii_ensemble` 的 dry-run/live 已接入唯一 execution 状态机：稳定 client
  ID、submit 前持久化、`pending/tracked`、按 fill 建仓、保护单、兄弟单撤销、
  reconcile、fail-closed 与 platform ledger。
- V39 entry、MII entry/exit、保护单、timeout，以及 `preempted_by_v39` 的
  close-confirm-open 都必须走同一订单生命周期；preempt close 未确认时仍禁止开
  V39。
- live venue 固定为 Binance REST + User Data Stream；dry-run venue 使用实例独立
  `state/<instance>/simulated_venue.json`。
- 已删除 `platform.execution.enabled` 和 live V1 fallback；不存在绕过统一状态机的
  legacy executor。
- strict replay/parity 路径继续隔离，不读写任何 venue state；既有 `291/291`
  trade-path replay parity PASS 应保持不变，本次迁移不产生新的 parity 结论。
- 当前 runner workspace `134` 个 unit tests 与 `12` 个 integration tests 全部通过；
  `cargo clippy --workspace --all-targets -- -D warnings` 通过；另完成最新
  `400` 根 15m 的 combo replay smoke（该短窗口 `0` 笔交易），既有全窗口
  `291/291` parity 证据和状态均不变。
- 最终执行安全审查修正 simulated 字符串 order ID 的保护单 reconcile、
  orphan/emergency flatten 定价和 dry-run `exchange_flat` PnL source，并新增
  string/numeric order ID 回归测试；无未解决 blocker。
- execution/TB-MII pause 只能在 lock + venue/local/protection reconcile clean 且
  `preempt_in_progress=false` 后由 `risk-resume` 清除；schema 切换禁止
  binary-only rollback。
- crash 后由 reconcile/resume 关仓时，按 active leg 补写
  `mii_available_*` / `trend_last_exit_*`，避免跳过原有再入场门禁；已有定向测试。
- 这是代码迁移，**未部署、未重启线上**；现有 production dry-run 与 live disabled
  事实不变，也没有新增 runtime fill 证据。
- 状态保持 `V2 dry-run active / replay parity PASS / live disabled / not
  live-ready`。交接契约见
  [V2 active validation spec](../live-specs/hype-15m-tb-mii-ens-v2-live-validation-spec-not-live-ready-2026-07-09.md)。

## 2026-07-14 StrategyDriver 最终迁移（仅代码，未部署）

- `hype_tb_mii_ensemble` 已从 legacy runtime adapter 迁入通用
  `StrategyDriver`。V39/MII pending signal、active leg、warning state 和
  preempt gate 均保存到 versioned `StrategyStateEnvelope`。
- preempt 由声明式 `StrategyDecision::Replace` 表达，execution kernel 强制
  close-confirm-open；未确认平仓时不允许增加风险。trend/MII 的 fee、slippage
  和 bar 出场口径仍按 entry kind 区分。
- `MarketRequirement` 统一提供 featured/mark 数据；持仓期 trend 与 MII signal
  仍被计算并写入 cycle/signal ledger。策略模块通过 `inventory` 自注册 Driver
  factory 与 replay handler，不再存在 adapter 或中心 runtime match。
- Runner workspace `152` 个 unit tests、`12` 个 integration tests、strict
  Clippy、六策略 smoke/replay 及配置校验通过。本次未部署，也不替代既有
  `291/291` parity；状态保持不变。

## 来源

- Runner repo：`/Users/ZK/OpenCode/quant-runner`
- Runner strategy kind：`hype_tb_mii_ensemble`
- Runner strategy id：`HYPE-15M-TB-MII-ENS-V2`
- Runner-side spec：`crates/quant-runner/src/runner/strategies/hype_tb_mii_ensemble/HYPE-15M-TB-MII-ENS-V2-SPEC.md`
- Validation spec：
  [V2 active validation spec](../live-specs/hype-15m-tb-mii-ens-v2-live-validation-spec-not-live-ready-2026-07-09.md)

## 已实现边界

- 新增 `hype_tb_mii_ensemble` strategy module，代码内固定 V2、V39 与 MII V1.4
  默认值。
- 新增 `replay-dry-run` 组合 replay：V39 优先、MII V1.4 为 secondary、全局单仓
  loop，并支持 replay-level `preempted_by_v39`。
- 2026-07-09 已应用 Bugbot review 修复：V39 warmup 从 `1600` bars 后开始；只有
  存在有效 V39 open candidate 时才 preempt MII；V39 退出后禁止 MII 同 bar 重入；
  V39 `indicator_exit` 不再被同 bar timeout 覆盖。
- 2026-07-09 第二轮对齐修复：
  - MII open-type exit（timeout + gap）在 V39 entry 检查前按当前 bar open 结算，
    与状态机 step 2 一致；open-type exit 后允许 MII 同 bar 重入。
  - Replay equity 改为逐 bar mark：V39 腿按 `1 + pnl - cost` 的 exit 组合做
    close-to-close 复利（精确对齐 engine `close_position`）；MII 腿锚定 entry
    equity，预扣完整 round-trip `0.0028` 并设 zero floor（精确对齐 engine
    `close_mii_record`）。Binance public-kline smoke 路径仍不含 funding。
  - `h1_adx21/pdi/mdi` 投影特征与 ratio-style `ema_spread` 已提升到共享
    `indicators/` 层（`htf_adx_di`、`ema_spread`），由 `hype_ema_x` 与
    `hype_tb_mii_ensemble` 复用，并有共享层测试。
  - 按 validation spec preload 要求，该 kind 默认 `warmup_bars` 提高到 `2500`。
  - 删除 runner strategy 目录中重复的完整 validation spec；runner-side SPEC
    现在声明 loop-order/mark 对齐与剩余已知差异（不含 funding；gap-through-stop
    经共享 `trading/bracket.rs` 按 bar open 入账，runner exit-reason 与研究标签
    1:1 映射）。
- 新增 disabled validation TOML 实例：`configs/dryrun.toml` /
  `hype-tb-mii-ens-v2-validation`。
- 2026-07-09 runtime/live-pilot pass：已实现 continuous dry-run；disabled live
  pilot 路径实现 V39 K+2、MII K+1、live 保护单、原子 preempt
  close-confirm-open、重启状态、保护恢复、交易所对账和 fail-closed gates。详见
  [runtime/live-pilot tracking](hype-15m-tb-mii-ens-v2-runtime-live-pilot-2026-07-09.md)。

## Smoke 命令

```bash
cargo run -- replay-dry-run --config configs/dryrun.toml --name hype-tb-mii-ens-v2-validation --limit 2500
```

命令输出的观察窗口（2026-07-09 第二轮，对齐修复后）：

```text
replay_start_ts = 2026-06-29T23:45:00+00:00
replay_end_ts   = 2026-07-09T08:30:00+00:00
bars_replayed   = 900
```

Runner 配置摘要：

```text
symbol = HYPE/USDT:USDT
timeframe = 15m
trend = ema_tb_v39
mii = mii_v14
preempt_secondary = true
global_position_limit = 1
```

Smoke 输出摘要：

```text
trade_count = 3
trend_trades = 3
mii_trades = 0
preempts = 0
win_rate = 0.6666666666666666
cumulative_return = 0.10203493281320153
max_drawdown = -0.14520172126190045
```

相较第一轮 smoke（交易相同，cumulative_return `0.1044`，max_drawdown
`-0.0750`），trade path 不变；cumulative return 因 exit cost 现按 engine 公式做
加法合并而小幅变化，max_drawdown 因 equity 改为逐 bar mark、能捕捉持仓内回撤而
加深，不再只统计 trade-close equity。

该小窗口 smoke 只证明 runner branch 可执行并输出合理结构化结果；它不是标准数据湖
parity gate，也不满足全样本目标 `291` 笔 / V39 `107` / MII V1.4 `184` /
preempt `3`。

## 检查

```bash
cargo fmt
cargo clippy --all-targets --all-features
cargo test
cargo run -- smoke-test --config configs/dryrun.toml --name hype-tb-mii-ens-v2-validation
```

结果：

```text
cargo clippy --all-targets --all-features: pass
cargo test: pass, 59 library tests + 2 integration tests (2026-07-09 second pass)
smoke-test: ok = true, issues = []
```

## 结论

实现已移除此前“strategy kind 不存在”的 blocker。后续 runtime/live-pilot pass
在代码层移除了 continuous runtime blocker，但 live 保持禁用；设置
`enabled = true` 前仍需 operator 明确批准、专用 subaccount credentials 和余额规模
确认。

下一 gate 是与
`research_hype_15m_tb_mii_ensemble_backtest.py --trend v39 --mii v14`
做标准数据湖全量 parity，覆盖逐 K state、全部 trades、preempt count 和 equity
curve tolerance。

## 2026-07-13 统一 execution dry-run 已部署

- `main@cd00ef24c8f2c33d17bee19c51d017e264c76356` 与 SHA-256
  `0ce2b5513716cd84cf825abf19db4c65d6509b6386721c438bbc06fc022735a5`
  已随双服务切换安装；本实例启动时 flat、无迁移订单，health=`ok`。
- 跨 watchdog 周期 dry-run service PID 稳定、`NRestarts=0`、无 warning/error；
  未采集到新 TB-MII open/close/fill。既有 parity PASS、live disabled 与
  not live-ready 状态不变。

## 2026-07-13 shutdown 通知去重已部署

- 双服务切换的 7 条策略级 shutdown 因两个 watchdog 竞态被放大到约 13-14 条。
  Runner `bd3f33d` 已部署：每 service 一条 `service_graceful_shutdown` 汇总，
  SQLite 原子 claim/lease 阻止重复消费；验证重启 outbox 仅 2 条且
  `attempts=1`。
- 仅影响运维通知，不影响 parity、preempt 或 live-readiness。

## 2026-07-13 service 稳定性修复已部署

- 同组 six-asset transient timeout 曾使整个 dry-run service 退出，暴露出单组故障
  会中断 TB-MII 的错误故障域。
- Runner source 已改为 group 独立 supervisor、transient entry-only gate 和
  control-plane watchdog；confirmed mismatch/preempt fail-closed 仍保持持久化且
  只能经 clean `risk-resume` 清除。Runner `e69589f` 已于 `21:02 CST`
  部署 dry-run，初检 health=`ok`、flat、无 warning/error；既有 parity、
  live disabled 与 not live-ready 结论不变。

## 2026-07-14 StrategyDriver 迁移与收尾（仅代码，未部署）

- `hype_tb_mii_ensemble` 已迁入通用 `StrategyDriver`。V39/MII 信号、leg
  fee/slippage、保护和 preempt 决策留在策略目录；订单、reconcile、ledger
  和 fail-closed 由 execution kernel 统一处理。
- preempt 现在显式输出 `StrategyDecision::Replace`，目标必须使用 persisted
  `AfterFlat`。执行核先保存 replacement target，再平旧仓、确认 flat 后开新仓；
  重启时从 `pending_replacement` 续做，不允许 close 未确认时开新 leg。
- `trend_last_exit_ts` / `mii_available_ts` 等私有状态进入 versioned
  `StrategyStateEnvelope`。历史 `preempt_in_progress=true` 不能安全自动推断，
  因此启动时继续 fail-closed，要求 operator reconciliation。
- Driver/replay 通过策略模块 `inventory` 自注册；legacy adapter 和中心
  runtime/replay kind match 已删除。该迁移不替代既有 parity，也不改变
  `dry-run active / live disabled / not live-ready`。
- 最终本地验证为 `162` 个 unit tests、`12` 个 integration tests、strict
  Clippy、dry-run/live 配置校验和六策略 2500-bar Binance smoke replay 全通过。

## 2026-07-14 Driver 最终加固（仅代码，未部署）

- TB-MII dry-run 恢复旧 runtime 的 MII current-open gap/timeout 判定；普通
  intrabar bracket 继续使用 trade-candle OHLC，而 live 保护单仍是
  mark-price-market。订单类型与 dry-run bar 价格源现为两个显式 capability。
- `pending_replacement` 会在 legacy dry-run venue migration 前短路旧仓补建，
  flat/position Replace 均 persist-before-submit；`risk-resume` 在 replacement
  未完成时拒绝解除 pause。
- 最终来源命令：`cargo test --workspace` 为 `170` 个 unit +
  `12` 个 integration 全通过；strict Clippy、两份 config 与六实例 smoke
  通过。`replay-dry-run --limit 2500` 的 handler 当前回放 `900` bars，
  输出 `1` V39 trade / `0` MII trade / `0` preempt。
- 本次未部署、未重启、无新 runtime trade/fill；既有 parity PASS、
  live disabled 与 not live-ready 状态不变。

## 2026-07-14 Driver state/replay 最终收口（仅代码，未部署）

- Trend leg 的 `high_water/low_water/mfe_atr` 只保存在 TB-MII envelope；
  历史 position 迁移按 `entry_kind=ema_tb_v39` 显式识别，并且不再把 EMA-X
  `hard_bad_bars` 错当作 V39 `weak_bars`。定向 fixture 覆盖该兼容边界。
- `StrategyStateEnvelope` 使用逐步 `N -> N+1` migration hook；缺迁移步骤时
  fail-closed。`pending_replacement` 的 persisted close-confirm-open 恢复语义不变。
- replay report/handler 已归 TB-MII 模块；中心 replay 不再包含策略命名函数，
  bootstrap 也不再提供 per-kind config factory。
- 最终验证：`179` 个 unit tests、`12` 个 integration tests、strict Clippy、
  dry-run/live config、六实例 smoke 与六策略 2500-bar replay 全通过。
- 本次未部署、无新 runtime trade/fill；既有 parity PASS、live disabled 与
  not live-ready 状态不变。
