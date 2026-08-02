# HYPE 15m 共享行情组 group halt 事件 2026-07-30 落档

## 事件与影响

- **共享行情组 `binance:HYPE/USDT:USDT:15m` 自 `2026-07-21 18:06 UTC` 起 `group_halted`，至本次核查（2026-07-30）已停摆约 9 天无人复位。**
- 受影响实例（全部 `status=halted`，`last_bar_ts` 停在 `2026-07-21 17:00–17:45Z`）：
  - `hype-ema-x-dry-run`（`HYPE-EMA-X-V18`）——**halt 时留有一个未平仓模拟持仓**；
  - `hype-mii-dry-run`（`HYPE-15M-MII-V1.4A`）；
  - `hype-candle-count-v35-dry-run`（`HYPE-CC-V35`）;
  - `hype-tb-mii-ens-dry-run`（`HYPE-15M-TB-MII-ENS-V2`）。
- 不受影响：PBTR 5m 组、AS6S、six-asset（1h）各组均正常。live 服务（`hype-pullback-live`）不在此组。

## 根因链（platform ledger 事件，只读）

1. `2026-07-21 17:30Z`：`hype-ema-x-dry-run` cycle_error：`missing Binance kline at 2026-07-21 17:30:00 UTC`（瞬时数据缺口）。
2. `17:45Z` 起连续 cycle_error：`simulated order 7 is not open`——模拟盘 venue 的挂单状态在缺 K 后进入不一致态，且**跨周期不自愈**。
3. `18:00:30Z`：组 freshness stale（`hype-ema-x-dry-run` 最后成功 bar 超过 3 个 decision-clock bar）。
4. 组重启预算（`restart_budget=3`）耗尽后 `18:06:07Z` `group_halted`，理由：`hype-mii-dry-run` 在组重启后未能处理成功 bar。

判定：freshness → 组重启 → fail-closed 的安全链**按设计工作**。

精确根因（2026-07-30 代码核验）：EMA-X Driver `NextOpen` 平仓路径**先撤止损 / TP，再去 REST 取下一根开盘价**。取价失败时保护单已 `CANCELED`、仓位仍在、`stop_order_id` 仍指向旧单；后续 OHLC/止损触发调用 `fill_simulated_order` → `simulated order 7 is not open`，且不会自愈。冻结态证据：`engine_state` 多仓 + `stop_order_id=7`，`simulated_venue.json` order 7 = `CANCELED`。

## 代码修复（quant-runner，2026-07-30，尚未部署）

1. `driver_runtime`：`NextOpen` / Immediate 平仓先解析模拟价，再撤保护单。
2. `ensure_protection_after_pending`：venue 上非 `NEW` 的止损/止盈视为缺失并重建。
3. dry-run OHLC 触发时若保护单已不在挂，改为按评估价 reduce-only 市价平仓，避免硬失败卡死。
4. 回归测试：`ensure_protection_rearms_canceled_stop_while_position_open`。

**2026-07-30 已部署并恢复：** `origin/main` `d514e65`。新二进制重启后 EMA-X 自动重建保护单并按 stop 平掉遗留模拟仓；组 `group_freshness_recovered`，四实例 `status=recovered`、隔离标记已清。禁止手改 `simulated_venue.json` 的约束仍有效。

## 停摆窗口错过交易（回放估计，2026-07-21 18:06Z → 2026-07-30 08:00Z）

来源：本机 `quant-runner replay-dry-run`，Binance 公共 K 线，`limit=2500`，窗口起止如上。口径是研究/smoke replay，与 runtime next-open 执行有已知差异，用作数量与方向估计，不作实盘 PnL 承诺。四个家族该段 dry-run 观察窗口作废。

| 策略 | 错过新开仓 | 若开了会怎样（回放） |
|------|------------|----------------------|
| EMA-X V18 | **2** 笔空头 | ① 07-22→07-26 `hard_swing96`，1x ≈ **-2.01%**（alloc≈2.8 → 约 **-5.6%** 暴露）② 07-28 开仓至窗口末仍持仓，浮盈 1x ≈ **+3.45%**（alloc≈2.9） |
| MII V1.4A | **0** | 整段无新信号（与线上 `last_signal_ts=2026-07-17` 一致） |
| CC V35 | **7** | 研究 equity **累计约 +17.0%**（4 止盈 / 2 止损 / 1 early）；单笔 net_return 约 +8.2%、+8.4%、+8.2%、-1.6%、+7.4%、-8.0%、-4.2% |
| TB-MII-ENS V2 | **2**（均 V39） | ① 07-22→07-24 target **+5.54%** ② 07-28 indicator_exit **-6.29%**；窗口累计约 **-1.1%** |

合计错过新开约 **11** 笔（2+0+7+2）。方向上 CC 窗口最赚，EMA-X/TB 有赚有亏，MII 空窗。

### EMA-X 遗留多仓（halt 时已开、未维护）

- 入场：`2026-07-21T05:30Z` long @ `63.085527`，qty `0.475`，stop `60.4936`。
- 17:15 周期 Driver 已决定 `NextOpen` 策略平仓；若当时取到 17:30 open=`60.773`，约 **-3.67% 1x**（≈ **-1.10 USDT** 名义）。
- 17:30 这根 low=`60.367` 已触及止损；若保护单仍在，也会在该根按 stop 出场（约 **-4.11% 1x** / ≈ **-1.23 USDT**）。
- 实际：止损被撤掉后组 halt，该仓观察连续性断裂，复位时需单独处置，不能算进正常 dry-run 成绩。

## 后续动作

1. ~~修复 NextOpen 撤单/取价非原子与 canceled-stop 不自愈~~
2. ~~部署 `d514e65` 并恢复组；EMA-X 遗留仓已在重启 cycle 中 stop 平仓作废~~
3. 四个家族 `2026-07-21 → 2026-07-30` dry-run 观察窗口作废；恢复后各自 runner tracking 记断档。
4. 值守：`group_halted` 必须当日响应；日报已含服务状态检查（部署后次日生效）。

## 交叉引用

- 受影响家族 tracking：[MII](../../15m-multi-indicator-intraday/runner-tracking/README.md)、[CC](../../15m-candle-count-reversal/runner-tracking/README.md)、[TB-MII-ENS](../../15m-trend-breakout-multi-indicator-ensemble/runner-tracking/hype-15m-tb-mii-ens-v2-runner-implementation-smoke-2026-07-09.md)（目录内最新报告）。
- 同日 PBTR / AS6S 核查：[PBTR 零开单审计](../../5m-pullback-trail/runner-tracking/hype-5m-pbtr-runner-2026-07-30.md)、[AS6S 中期观察](../../../asset-portfolios/15m-asset-specific-six-strategy-selector/runner-tracking/binance-as6s-v6-dry-run-interim-2026-07-30.md)。
