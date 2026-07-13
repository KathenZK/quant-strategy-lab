# BIN-1H-AR-MAE-V1 Runner Tracking

- Date：2026-07-09（同日更新：replay 对拍完成）
- Runner repo：`quant-runner`
- Kind：`six_asset_ensemble`
- Strategy id：`BIN-1H-AR-MAE-V1`
- Mode：`dry_run` only
- Live-ready：`NO`

## Wiring

- Strategy module：`crates/quant-runner/src/runner/strategies/six_asset_ensemble/`
- Runtime：`crates/quant-runner/src/runner/trading/runner/six_asset_ensemble.rs`
- Dry-run instance：`configs/dryrun.toml` → `six-asset-ensemble-dry-run`
- State dir：`/home/admin/quant-runner/state/six-asset-ensemble-dry-run`
- TOML symbol placeholder：`BTC/USDT:USDT`（实际交易合约由 sleeve 决定）

## Runtime semantics

- 六资产并行拉 `1h` 闭合 K + funding 过滤特征。
- 账户级单仓：持仓期间忽略其他资产/腿信号。
- 同小时冲突按冻结 `TIE_PRIORITY`（HYPE > TRX > BTC > ETH > BNB > SOL）。
- 名义：`dry_run_notional_usdt × leg.fixed_leverage`。
- Live 启动校验直接拒绝。

## Status

- `smoke-test`：通过（本地 2026-07-09）。
- 持续 dry-run：**已上线**（2026-07-09 21:55 CST）。quant-runner `main@34b770a` 经本机 cargo-zigbuild 交叉编译 `x86_64-unknown-linux-gnu` 产物部署至 `47.80.57.36`，`quant-runner-dryrun.service` 重启后 `active`；`six-asset-ensemble-dry-run` 首周期 `flat_no_signal`（execution_ts 2026-07-09T13:00Z），`strategy_health.status=ok`、`position_open=0`，journal 无告警。live 服务未动。
- `replay-dry-run`：已接线（2026-07-09）。`replay-dry-run --name six-asset-ensemble-dry-run` 按 lab 数据快照边界拉取六 symbol 闭合 1h K + funding，1:1 复刻单仓 diagnostic backtest（leg 级模拟含 cooldown → sleeve 冻结优先级合并 → 账户级单仓贪心选择）。
- 研究回测冻结交易路径对拍：**完成，零误差**（2026-07-09）。
  - 数据源：Binance 公共 klines + fundingRate API（runner 拉取），数据边界与 lab parquet 快照逐 symbol 一致（首/尾 K、行数校验通过）。
  - 选择统计：candidates `522` / selected `371` / skipped `151` / ties `22`，per-asset candidates/selected 全部与 `binance_1h_ar_mae_single_position_2026-07-07.json` 一致。
  - 逐笔对拍：`371/371` 笔与 `binance_1h_ar_mae_single_position_trades_2026-07-07.csv` 在 asset/style/entry_ts/exit_ts/side/exposure/equity_ret（<1e-9）/exit_reason 全字段一致。
  - 窗口指标：full `+39997.48 / -21.43% DD / 90.30% win / PF 6.862`，reused holdout `+65.31% / -19.79% DD`，`last_7d/1m/3m/6m/1y` 与 spec 期望值一致。
  - Artifact：`artifacts/binance_1h_ar_mae_v1_runner_replay_parity_2026-07-09.json`（runner replay 完整 JSON，含逐笔 trades）。
- 对拍过程中发现并修复 runner 公共指标层 bug：`indicators::rolling_mean` 对前导 NaN 序列会被 NaN 永久污染，导致 `stoch_d` 全 NaN、TRX/HYPE Stoch 腿永不出信号；已修复为 pandas `rolling(min_periods=window)` 语义（quant-runner 提交内）。修复前的任何 dry-run 观察不含 Stoch 腿信号。
- SPEC 修正（runner 与 lab 两份同步）：ETH BB 实为 `side_mode=long`、`max_atr_bps=250`；ETH RSI 实为 `max_atr_bps=600`、`require_body_dir=true`、`max_aligned_funding_bps=2.0`；TRX Stoch 补记 `max_dist_ema_bps=1500`、`max_aligned_funding_bps=4.0`。均为 V1 基线继承字段，代码与冻结路径本来正确，spec 文档此前记错/漏记。

## Runtime vs replay 已知差异（dry-run 联合状态机近似）

- 入场价：runtime 用执行时刻 mark price ± 滑点，replay/lab 用下一根 open ± 滑点。
- cooldown：runtime 施加在整个 asset sleeve 上；lab 是 leg 级 cooldown（例如 HYPE Stoch 36h cooldown 在 lab 中不阻塞 HYPE DI 腿）。
- timeout 检查顺序：runtime 在执行 open 先查 gap-stop/target 再查 timeout；lab 在 timeout bar 无条件按 open 出场。同价、原因标签可能不同；target gap 且 timeout 同时发生时价格可能有差。
- 这些近似只影响 dry-run 逐笔生命周期观察，不影响 replay 对拍结论。

## Decision gate

保持 lab 结论：`registered diagnostic / NO-GO / not promoted / not live-ready`。
dry-run 仅用于观察 runtime 信号与持仓生命周期，不改变 promotion 状态。
replay 对拍零误差证明 runner 引擎实现与 V1 冻结路径一致，但不改变 V1 的 NO-GO 判定（回撤穿破 `<20%` 硬门槛、成分均为 diagnostic NO-GO）。

## 2026-07-10 Runner architecture governance

- `six_asset_ensemble` is now declared `SelfManagedMultiSymbol` in the central
  strategy registry and no longer enters the ordinary BTC placeholder
  market-data group before pulling its six sleeves.
- Platform manual halt, risk observations, critical outbox, graceful shutdown,
  watchdog and manifest lock apply to the self-managed runtime too.
- Source tests pass; no deployment or change to the dry-run/live decision was made.

## 2026-07-11 Platform `trades` ledger wiring

- Issue：dry-run 已有 BNB 持仓（`holding` / `position_open=1`），但 platform `trades` 表无行。根因是 runtime 只写 `events`（`open`/`cycle`）和 `strategy_health`，未调用 `emit_ledger_trade_open`；平仓虽走公共 `close_position`→`emit_ledger_trade_close`，没有 open 行时 update 会静默 0 行。
- Fix（quant-runner，未部署）：`six_asset_ensemble` 开仓补 `emit_ledger_trade_open`；holding 周期 upsert 对账；平仓前先 upsert open，避免历史孤儿持仓关单丢记录。公共 ledger upsert 同时增加终态保护，重复 `TradeOpen` 不得把 `closed` 交易重新改回 `open`。
- Backfill（线上 DB，已做）：从 `state/six-asset-ensemble-dry-run/engine_state.json` 回填当前 open 行 `armae-bnb-1783699210359`（BNB long，entry `2026-07-10T16:00Z` @ `574.369656`）。
- Source validation：`cargo fmt --check`、`cargo clippy --all-targets -- -D warnings`、`cargo test` 通过；新增 `open -> close -> duplicate open` 仍保持 closed 的回归测试。
- Decision gate：不变，仍为 `NO-GO / not promoted / not live-ready`。此修复只补观测完整性。
- 部署前：新开仓/对账逻辑需发布二进制后才生效；当前 open 行已可在 `trades` 查询。

## 2026-07-11 SPEC alignment re-audit

- Strict replay：参数、特征、leg 级 cooldown、sleeve merge、账户级阻塞、费用/滑点/funding 与冻结 SPEC 的逐笔 parity 证据仍有效（371/371 零误差）。
- Continuous dry-run runtime：仍是观测用联合状态机近似，不等同于冻结 diagnostic replay；已知 mark-price 入场、asset 级 cooldown 和 timeout 优先级差异继续成立。
- 已修复差异 1：空仓时任一 sleeve funding 获取失败或返回空集都会阻止新入场；已有持仓退出不受 funding API 故障阻断，但 active sleeve funding 不可得时 net PnL 保持 `null`，不再静默按零 funding。
- 已修复差异 2：runtime 按 strict replay 的 `[entry_ts, exit_ts)` 半开区间累计 `-side × funding_rate`，纳入 `trades.net_pnl_usdt` / `net_ret_1x`，并把 `funding_ret_1x`、`funding_pnl_usdt` 写入 close payload。
- 新确认差异 3：runtime 用六个 sleeve 最新闭合时间的最小值推进 cycle，但选仓仍按各 sleeve 自身最后一根 K 计算；若某个 symbol 数据滞后，候选信号可能不在同一执行小时。
- 文档漂移已修复：Runner SPEC 现明确研究身份仍为 diagnostic NO-GO，Runner 只获准 `dry_run` 观察，并直接列出 strict replay 与持续 runtime 的边界。
- 结论：策略参数/信号引擎及 strict replay 对齐；funding 获取和 PnL 缺口已关闭。持续 dry-run 的三项既有观测差异和跨 symbol 时钟风险仍不改变 `NO-GO / not live-ready`，任何 promotion 前必须统一实现或建立新的正式规格。

## 2026-07-12 dry-run deployment

- Runner source：`main@282bf9c9e5bf482e90eecc67a3f77da842e24ad7`。
- Build：GitHub Actions
  [`Build Linux release #29159239033`](https://github.com/KathenZK/quant-runner/actions/runs/29159239033)
  的 governance、quality、build 全部通过；artifact 为 Linux x86-64 ELF，
  SHA-256 `f53f0c88ab2c5f2157172bbf582c43014375e170535a50188510c7ef2c1e9e67`。
- Deploy：服务器 `/home/admin/quant-runner` fast-forward 到该提交，预编译二进制
  经哈希校验后原子安装；`quant-runner-dryrun.service` 于
  `2026-07-12 00:19:49 CST` 重启并保持 active。
- Verification：重启后 journal 无 warning/error；全部 strategy health 为 `ok`；
  six-asset 当前 `position_open=0`，已有 candle-count dry-run short
  `position_open=1` 正常从本地状态恢复。
- Live：`quant-runner-live.service` 没有 open trade 且持续 active，但因本次只影响
  dry-run、平台仍有未平 dry-run 交易，未主动重启 live 进程；共享磁盘二进制已更新，
  live 下次受控重启会加载该版本。
- Decision gate：保持 `NO-GO / not promoted / not live-ready`。

## 2026-07-12 统一执行架构迁移（后续代码，未部署）

- `six_asset_ensemble` 已改为通过 symbol-explicit simulated venue 执行六个 symbol
  的 entry/exit order lifecycle，不再由 self-managed runner 直接写入持仓。
- dry-run 与 live 共用唯一 execution 状态机能力：稳定 client ID、submit 前持久化、
  `pending/tracked`、按 fill 建仓、保护单、撤单、reconcile、fail-closed 与
  platform ledger；但本 family 仍有代码级 live 拒绝，只允许 dry-run。
- dry-run venue 的独立持久化文件为
  `state/<instance>/simulated_venue.json`；每笔订单必须显式携带真实 sleeve symbol，
  不能使用 TOML 中 `BTC/USDT:USDT` placeholder 代替实际交易合约。
- live venue 的平台实现为 Binance REST + User Data Stream，但 V1 未获 live 权限，
  不得据此创建或启用 live 实例。
- 已删除 `platform.execution.enabled` 和 live V1 fallback。strict replay/parity
  继续走隔离路径，不读取或改写 simulated venue；既有 `371/371` 零误差 parity
  结论应保持不变。
- 当前 runner workspace `134` 个 unit tests 与 `12` 个 integration tests 全部通过；
  `cargo clippy --workspace --all-targets -- -D warnings` 通过；完整 strict replay
  再次得到 `522/371/151/22`，与冻结 Lab reference 一致，既有 `371/371`
  parity PASS 不变。
- six-asset 存量持仓显式 symbol 迁移与 venue/local mismatch 拒绝 resume 已有定向
  测试；execution pause 只能在 lock + 多 symbol reconcile clean 后由
  `risk-resume` 清除。schema 切换禁止 binary-only rollback。
- 本节记录的是 00:19 CST 部署之后的后续代码迁移，**尚未部署、未重启线上**；
  2026-07-12 已部署二进制和服务状态仍是当前线上事实，没有新增成交统计。
- 结论保持 `DryRunOnly / NO-GO / not promoted / not live-ready`。交接约束见
  [V1 active handoff](../live-specs/binance-1h-ar-mae-v1-handoff-not-live-ready.md)。

## 2026-07-13 统一 execution symbol-explicit venue 切换

- Runner `cd00ef24c8f2c33d17bee19c51d017e264c76356` 经
  [GitHub Actions run 29223536186](https://github.com/KathenZK/quant-runner/actions/runs/29223536186)
  构建，artifact SHA-256
  `0ce2b5513716cd84cf825abf19db4c65d6509b6386721c438bbc06fc022735a5`。
- 用户明确批准在两笔 dry-run open trade 存续时切换。服务于
  `2026-07-13T04:25:04Z` 停止并同批更新配置/二进制；跨完整 watchdog 周期
  PID 稳定、`NRestarts=0`、无 warning/error。
- 当前 HYPE long `0.443` 持仓迁入 symbol-explicit `HYPEUSDT` venue，entry
  order `1` 已成交，无其他 symbol 暴露；pending/fail-closed 均为空，
  health=`ok`。本策略继续用逐 bar fixed target/stop/timeout，不创建 resting
  venue TP/SL。完整生命周期快照见
  [迁移 artifact](../artifacts/binance_1h_ar_mae_v1_unified_execution_migration_2026-07-13.json)。
- 该 runtime 迁移不改变 strict replay 的 `522/371/151/22` 与 `371/371`
  parity PASS，也不改变 `DryRunOnly / NO-GO / not live-ready`。

## 2026-07-13 shutdown 通知去重已部署

- 双服务切换的 7 条策略级 shutdown 因两个 watchdog 竞态被放大到约 13-14 条。
  Runner `bd3f33d` 已部署：每 service 一条 `service_graceful_shutdown` 汇总，
  SQLite 原子 claim/lease 阻止重复消费；验证重启 outbox 仅 2 条且
  `attempts=1`。
- 仅影响运维通知，不影响本策略状态、多 symbol venue 或 parity。

## 2026-07-13 SOL timeout 重启事件与恢复交易

- `2026-07-13T10:00:12Z`，six-asset 拉取 SOL OHLCV 时 Binance time 请求超时；
  旧 self-managed 错误路径使整个 dry-run service `exit 1`，systemd 于
  `10:00:43Z` 自动重启。该事件不是 OOM、panic 或主机故障。
- 重启后的 10:00Z cycle 选择 TRX long，并在下一小时按 `stop_market` 关闭：
  quantity `106.008`、notional `34.9998145681 USDT`、entry
  `0.3301620120`、exit `0.3259318533`、总费用 `0.0695511985 USDT`、
  net PnL `-0.5179818656 USDT`。完整 source、时间、mark/fill、滑点、order/client
  ID 和 reconciliation 限制见
  [incident artifact](../artifacts/binance_1h_ar_mae_v1_timeout_restart_trade_2026-07-13.json)。
- Runner workspace 已完成 source-level 修复（**尚未提交、未部署**）：完整 error
  chain 分类、幂等 GET 有界退避、残缺多资产 snapshot 禁止入场、已有仓位继续风险
  维护、group 独立 supervisor，以及策略 freshness 与 control-plane watchdog 分离。
- strict backtest-vs-runtime 对拍未在本事件中独立重算，因此 match 仍 pending；
  本事件不改变 `DryRunOnly / NO-GO / not promoted / not live-ready` 或既有 parity。
