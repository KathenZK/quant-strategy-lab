# HYPE-EMA-TB-V35 线上开平仓对账

日期：2026-07-15

## 结论

本次从生产 SQLite 审计库提取最近两笔线上交易，与研究回放逐笔对账：

- 最新 `2026-07-13` 空单与研究回放方向、entry ATR 和 stop-loss 结果基本一致；线上 STOP_MARKET 成交相对配置 stop 额外不利约 `0.079ATR`。
- 上一笔 `2026-07-03` 多单存在明确对账异常：线上配置 TP 为 `72.77105`，实际于 `71.51056` 平仓，低于 TP `2.81ATR`；数据库没有对应的 runner `live_close_submitted` 或 `exit_order`，但 `exchange_exit_synced` 把原因记为 `take_profit`。这个成交不可能是配置中的 reduce-only TP limit 成交。
- 研究回放用 K2 open `70.44` 作为入场基准，线上实际均价 `70.52946`，相差约 `0.20ATR`，从而把线上 `5ATR` TP 推高到研究 TP 之上。研究路径在 `57.75h` 命中 `72.68158`，线上路径最高仅达到相对实际 fill 的 `4.86383ATR`，没有命中 `72.77105`。

因此，用户观察到的“接近 4 天后最后平仓”是真实的，但生产审计证据不支持“最后 15 分钟命中 5ATR TP”。用户已确认该单为人工平仓；runner 随后把 exchange 侧人工平仓错标为 `take_profit`。订单本身原因已澄清，仍应修复 `exchange_exit_synced` 的 reason 归因，避免人工平仓污染线上 TP 统计。

本报告只做只读诊断，不修改线上配置或服务。

## 数据来源与观察范围

- Service：`hype-trend-binance-live`。
- Exchange / market：Binance USD-M perpetual。
- Symbol / timeframe：`HYPE/USDT:USDT`，`15m`。
- Runner：legacy `HYPE-EMA-TB-V35` live runner。
- 观察窗口：`2026-07-03 14:45 UTC` 至 `2026-07-15 03:00 UTC`。
- 生产证据：`/home/admin/hype-trend/state/hype_trend_live.sqlite3` 的 `event_log`。
- 提取方式：SSH 只读 SQLite 查询；读取 `open_success`、`cycle_done`、`exchange_exit_synced` 与相邻订单审计事件。
- 稳定证据：[hype_ema_tb_v35_live_reconciliation_2026-07-15.json](../artifacts/hype_ema_tb_v35_live_reconciliation_2026-07-15.json)。

## Runner 配置口径

- Entry：K0 close 信号，跳过 K1，K2 open 下单。
- Entry ATR：已完成 K1 的 `ATR672`。
- Bracket：固定 entry ATR `5ATR TP / 7ATR SL`。
- Position sizing：long target `0.020`、short target `0.018`、allocation cap `3.0x`。
- Indicator exit：MFE 达到 `1.5ATR` 后禁用。
- Timeout：`384` 根 15m K。
- 实际订单：Binance entry + reduce-only TP + close-position STOP_MARKET。

## 对账一：上一笔多单

### 线上路径

| 项目 | 线上证据 |
| --- | --- |
| Signal bar | `2026-07-03 14:45 UTC` long |
| Entry | `2026-07-03 15:15:05.958 UTC`，均价 `70.5294647` |
| Quantity / allocation | `466.98 HYPE` / `3.0x` |
| Entry ATR | `0.4483169643` |
| 配置 TP / SL | `72.7710495` / `67.3912460` |
| 最大已记录 MFE | `4.8638251ATR` |
| Exchange exit fill | `2026-07-07 13:34:30.040 UTC`，均价 `71.5105606` |
| 持仓时间 | `94.32h` |
| 实际净 PnL | `+230.49 USDT` |
| Runner 记录 trade return | `+2.3087%` |
| Runner 原因 | `take_profit` |

稳定事件与订单 id：

- Entry event `4225`，entry client id `ht-e-1981213`，exchange entry order `10311324550`。
- 最后持仓状态 event `4983`，MFE `4.8638251ATR`。
- Exit reconciliation event `5084`，exchange exit order `10497988226`。
- 配置 TP client id `ht-t-1981213`；对账事件中的 `exit_order = null`。

### 研究预期

| 项目 | 研究回放 |
| --- | --- |
| Entry | `2026-07-03 15:15 UTC @ 70.44` |
| Entry ATR | `0.4483169643` |
| `5ATR` TP | `72.6815848` |
| Exit | `2026-07-06 01:00 UTC` take profit |
| 持仓时间 | `57.75h` |
| 研究净收益 | `+8.60%` |

### 判断

`MISMATCH`：

1. 线上实际 fill 比研究 K2 open 高 `0.08946`，约 `0.20ATR`；线上固定 TP 因而同步高出 `0.08946`。
2. 线上退出价比配置 TP 低 `1.26049`，约 `2.81ATR`。sell limit TP 不可能在配置价以下成交。
3. 平仓前一轮 `cycle_done` 仍记录 position open、`pending_exit=null`；随后 exchange position 消失，runner 只做 reconcile，没有 retained `live_close_submitted`。
4. 用户已确认该笔为人工平仓。最终结论是 `MANUAL CLOSE / REASON MISMATCH`：runner 没有主动平仓，exchange reconcile 正确识别仓位消失，但把人工平仓原因错标为 `take_profit`。

## 对账二：最新空单

### 线上路径

| 项目 | 线上证据 |
| --- | --- |
| Signal bar | `2026-07-13 14:15 UTC` short |
| Entry | `2026-07-13 14:45:05.649 UTC @ 64.146` |
| Quantity / allocation | `531.1 HYPE` / `3.0x` |
| Entry ATR | `0.3422410714` |
| 配置 TP / SL | `62.4347946` / `66.5416875` |
| Exit | `2026-07-15 02:57:34.125 UTC @ 66.5688232` |
| 持仓时间 | `36.21h` |
| 实际净 PnL | `-1321.47 USDT` |
| Runner 记录 trade return | `-11.3559%` |

稳定事件与订单 id：

- Entry event `6254`，entry client id `ht-e-1982171`，exchange entry order `10775310272`。
- Exit event `6562`，stop client id `ht-s-1982171`，exchange exit order `10848899616`。

### 研究预期与判断

- 研究 entry：`2026-07-13 14:45 UTC @ 64.153`。
- 研究 stop：`66.5486875`；研究 exit：`2026-07-15 02:45 UTC`，净收益 `-11.49%`。
- 线上 stop-market 均价比配置 stop 不利 `0.02714`，约 `0.079ATR`。

结论为 `MATCH WITH SLIPPAGE`：状态机结果一致，时间和成交价差异符合真实 STOP_MARKET 与研究 15m stop-price 模型之间的执行差。

## 运行事件与后续

- 本轮未检查服务重启、missing bars 或通知完整性；范围只覆盖两笔 open/close/fill 对账。
- 上一笔多单已由用户确认为人工平仓；应让 `exchange_exit_synced` 区分 runner TP、runner SL 与 external/manual close。
- 研究回放目前把 adverse slippage 计入交易成本，但不把实际 entry fill 偏差传递到固定 TP/SL 价格；上一笔说明这个简化会在接近 TP 时改变是否成交。后续 live parity 应增加“按真实 fill 重算 bracket”的逐笔回放。
