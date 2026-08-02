# HYPE-5M-PBTR-V6.2.1 零开单审计 2026-07-30

## 范围与结论

- Runner kind / mode：`hype_pullback`；`hype-pullback-live`（tiny-live-pilot）与 `hype-pullback-dry-run` 并行。
- 观察窗口：live 生产切换 `2026-07-11 08:14 UTC` → 本次核查 `2026-07-30 07:50 UTC`；dry-run 自 `2026-07-01 13:07 UTC` 起。
- 用户观察：小额实盘至今一直未开单。
- **结论：零开单是合法的信号空窗，不是执行故障。** runner 健康、K 线处理从未中断，独立信号重算确认同窗口本就应当是 0 信号。状态保持 `live / tiny-live-pilot / forward-test required`，keep。

## 执行侧核查（platform ledger，只读）

- `strategy_health`：live 与 dry-run 均 `ok`，`last_bar_ts=2026-07-30T07:45Z`（新鲜），`position_open=0`。
- 事件流：dry-run `cycle` 8,290 次（自 07-01 起无中断）、live `cycle` 8,025 次；两实例均无 `halt`、`freshness`、`isolation`、`pause`、`cycle_error` 类事件；无任何 signal/order/fill/trade 记录。
- 近 24h journal 无 warning 及以上日志；同服务器上 HYPE 15m 组的 group halt（见 [group halt 报告](../../15m-ema-crossover/runner-tracking/hype-ema-x-runner-2026-07-30-group-halt.md)）不影响 PBTR 的 5m 独立行情组。

## 独立信号重算（对拍"零信号"）

方法：按 [V6.2.1 live spec](../live-specs/hype-5m-pbtr-v6-2-1-live-spec.md) 逐字复现双腿信号规则（EMA `adjust=False, min_periods=span`、ATR14、双重相邻抑制、quality gate），数据用 Binance fapi 公开 `HYPEUSDT 5m` K 线 `2026-06-20 → 2026-07-30 07:55 UTC`（11,616 根，无缺口，warmup 充足）。

| 窗口 | K 线数 | long 信号 | short 信号 |
| --- | --- | --- | --- |
| dry-run 窗口（≥07-01 13:07） | 8,290（与 runner cycle 数一致） | 0 | 0 |
| live 窗口（≥07-11 08:14） | 5,469 | 0 | 0 |

与 runner 行为完全一致。零信号的市场归因：

- **多头腿**：quality gate 要求 16h 动量 ≥`788.123` bps；窗口内最大仅 `552` bps（p99.9 为 `531`），从未达标。HYPE 在窗口内从 `68.98` 阴跌到 `53.13`（约 −23%），完全没有多头腿要求的强动量上行段。
- **空头腿**：`49` 根 K 过了动量门（4h 跌幅 ≥`400` bps，且全部处于 `EMA34<EMA144` 下行趋势），但**没有一根同时满足"high 反抽触及 EMA34"**；结构上满足"触及+收回"的 `553` 根 K 中，4h 动量最高只有 `302` bps。急跌时价格远离 EMA34、反抽回 EMA34 时动量已衰减——两个条件在本月的阴跌行情里从未重叠。这与回测中空头信号稀疏聚簇（全样本 `53` 笔集中在剧烈行情段）的形态一致。

## 对 tiny-live-pilot 的含义

- 回测全样本频率约 `0.55` 笔/天是聚簇均值；当前 regime 下连续数周零信号属于该策略的正常形态。
- pilot 的目的（真实成交生命周期证据：fill、保护单、OCO 撤销、timeout、重启恢复）在无信号期间**无法积累**；授权复核（2026-09-24）时若仍零成交，选项是延长观察或停止 pilot，**不得**以放宽 quality/结构门槛的方式"制造"成交（属于调参，需新版本登记）。
- 本次核查满足主账"结合最新 runner tracking 复核 tiny-live-pilot"的要求，结论 keep：执行面无异常、无未保护持仓、无对账缺口。

## 复现说明

信号重算脚本为本次一次性核查（约 60 行 pandas，规则逐字来自 live spec 第"Leg 参数/相邻信号抑制"节），未保留为脚本文件；如需复跑，按 live spec 规则对公开 5m K 线重算即可。ledger 查询命令见 quant-runner 运维技能文档口径（只读 sqlite 查询）。
