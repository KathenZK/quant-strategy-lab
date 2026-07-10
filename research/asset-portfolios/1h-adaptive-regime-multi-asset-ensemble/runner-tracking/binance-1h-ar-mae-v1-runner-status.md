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
