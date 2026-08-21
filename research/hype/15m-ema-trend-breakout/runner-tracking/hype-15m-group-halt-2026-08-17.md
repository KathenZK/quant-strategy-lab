# HYPE 15m 共享行情组 group halt 2026-08-17

## 事件与影响

- 共享行情组 `binance:HYPE/USDT:USDT:15m` 于 `2026-08-17 19:15:05Z` 发出 `group_freshness_stale`，`19:19:12Z` `group_halted`。
- 核查时刻（`2026-08-18 02:09Z`）五条 dry-run 仍 `status=halted`，`last_bar_ts` 停在 `2026-08-17 19:00Z`，实例目录均留有 `FRESHNESS_ISOLATED`。
- 受影响实例：
  - `hype-ema-tb-v35-1-dry-run`（触发 freshness：连续 3 根 NextOpen 取价失败）
  - `hype-tb-mii-ens-dry-run`（后两根同样缺 K）
  - `hype-mii-dry-run` / `hype-ema-x-dry-run` / `hype-candle-count-v35-dry-run`（同组被一起停）
- 不受影响：`hype-pullback-dry-run` / `hype-pullback-live`（5m）、AS6S、1d MA7、six-asset。`quant-runner-dryrun` / `quant-runner-live` systemd 均为 `active`。
- halt 时 `hype-candle-count-v35-dry-run` 留有模拟空仓：`short` @ `58.9004304`，qty `0.509`，入场 `2026-08-17T03:00Z`。组停后该仓不再被维护。

来源：阿里云 `47.80.57.36` platform ledger `state/platform/platform.sqlite3`、dry-run journal、实例 `engine_state.json`。Runner 配置：`configs/dryrun.toml`，`stale_bar_multiple=3`，`dry_run_notional_usdt=10`。

## 时间线（UTC）

1. `18:45:00` — EMA-TB `cycle_error`：`missing Binance kline at 2026-08-17 18:45:00 UTC`。同 tick MII/EMA-X `no_signal`、CC/TB-MII-ENS `holding`。共享 15m 行情本身在。
2. `19:00:05` — EMA-TB 与 TB-MII-ENS 同时 `missing Binance kline at 19:00:00`。
3. `19:15:00` — 两策略再次缺 `19:15:00` K。约 5 秒后组 freshness stale（EMA-TB 距上次成功 bar 超过 3 根 15m）。
4. `19:16:05` — 组重启 1。约 2 秒后 TB-MII-ENS / EMA-TB 用已到达的 NextOpen 价完成 `indicator_exit`（`pending_from_previous_cycle=true`，成交价 `58.855`）。MII/EMA-X/CC 记 `already_processed`。
5. `19:17` / `19:18` — 重启 2、3。理由变为 `hype-mii-dry-run has not processed a successful bar after group restart`（配置列表第一项；重启预算约 3×60s，等不到下一根 15m）。
6. `19:19:12` — `group_halted`，`restart_budget=3`。

EMA-TB / TB-MII-ENS 的模拟多仓已在重启 1 平掉，不是遗留仓问题。真正被卡住的是随后 freshness 清闸条件。

## 根因

两条叠加：

1. **NextOpen 取价竞态。** dry-run 在决策 bar 刚闭合时对下一根 `open_ts` 调 `fetch_kline_at`（`/fapi/v1/klines?startTime=<open>&limit=1`）。K 刚开盘时常返回空数组 → `cycle_error`，该实例本根不算成功 bar。2026-08-01 14:45–15:15Z 已是同一错误打挂 TB-MII-ENS。
2. **15m 组重启窗口短于下一根决策钟。** 隔离后必须有一次 `last_successful_bar_ts > attempt_started_at`。健康实例重启后走 `already_processed`，不会刷新该时间戳；3 次重启在约 4 分钟内耗尽，组 halt。

`group_halted` 的 outbox `dedupe_key` 是固定的 `group_halted:binance:HYPE/USDT:USDT:15m`（2026-07-21 已 `notified`）。本次 halt 写入了 `events`，但 `insert or ignore` 未再进钉钉。用户只收到 `group_freshness_stale`。

这与 [2026-07-21 / 07-30 事件](../../15m-ema-crossover/runner-tracking/hype-ema-x-runner-2026-07-30-group-halt.md) 同类（共享组 freshness → 短窗口重启 → halt），但不是当时的「先撤保护单再取价」状态机损坏。本次保护单路径在重启后正常平仓。

## 结论与待办

- 值守：`keep` 研究身份不变；**dry-run 观察窗口自 `2026-08-17 19:15Z` 起断裂**，恢复前不作 live-readiness 依据。
- 操作：重启 `quant-runner-dryrun` 可让组追上最新已闭合 15m bar 并清隔离（需确认 CC 遗留空仓恢复后的保护单）。未执行前组保持 halted。
- 代码：NextOpen 缺 K 应重试/推迟，而不是把整根打成 `cycle_error`；15m 清闸窗口应能等到下一根决策钟；`group_halted` 去重键需带时间，否则第二次 halt 不会再响。
