# BTC 周 K MA7 V1 零调参迁移合同

## 身份

- 来源版本：[`HYPE-1D-MA7-Asymmetric-Body-Trend-V1`](../../../hype/1d-ma7-asymmetric-body-trend/specs/hype-1d-ma7-abt-v1-spec.md)
- 目标家族：`BTC-1W-MA7-Asymmetric-Body-Trend`
- 市场：Binance USD-M `BTCUSDT` perpetual
- 性质：timeframe direct-transfer diagnostic；不登记 BTC 周线版本
- 仓位：约 `1x`、单仓、非加仓，入场后数量固定

## 数据与周界线

- 输入：accepted normalized `1h` OHLCV；raw/normalized 与 funding 审计通过。
- 主周 K：周一 `00:00 UTC` 开始，必须正好包含 `168` 根 closed `1h` K。
- 相位审计：主锚点后移 `84h`，即周四 `12:00 UTC`。
- 主窗口：`2024-08-05` 至 `2026-07-27 UTC` terminal open，共 `103` 根策略周 K。
- 相位窗口：`2024-08-01 12:00` 至 `2026-07-23 12:00 UTC` terminal open，同为 `103` 根。

## 指标与执行

- `SMA7[t] = mean(close[t-6:t])`，即 7 周简单均线。
- `ATR7` 为周线 true range 的 7 周简单移动平均。
- 周收盘信号最早在下一周 open 成交。
- stop 使用该周真实 `1h` open/high/low；gap 穿越按小时 open，否则按 stop 价加不利滑点。
- funding 按真实 Binance timestamp/rate，仅结算实际持仓覆盖的事件；无 stop 时结算边界由日线引擎的 `1d` 显式改为 `7d`。
- Sharpe 按 `sqrt(365.25/7)` 年化，收益年化按实际日历天数。

## 固定多空规则

SMA/ATR buffer、reclaim、斜率、迟滞、hard stop 与 trailing 倍数全部沿用来源 V1：

| 方向 | 入场 | 退出 / 保护 |
| --- | --- | --- |
| Long | 1 周 reclaim；SMA 1 周斜率至少 `0.02 ATR` | `0.75 ATR` 迟滞；`1.5 ATR` trailing；无首周 hard stop |
| Short | 1 周 reclaim + `0.1 ATR`；SMA 2 周斜率至少 `0.02 ATR` | `0.25 ATR` 迟滞；1 周斜率反转；`1.5 ATR` hard stop；`4 ATR` trailing |

## 两种时间合同

字段名沿用来源引擎的 `max_hold_days/cooldown_days`，但在周线引擎中单位是 strategy bar：

| 合同 | Long max-hold / cooldown | Short max-hold / cooldown | 含义 |
| --- | ---: | ---: | --- |
| `bar_transfer` | `90w / 2w` | `20w / 5w` | 原数字直接解释为周 bar |
| `clock_equivalent` | `13w / 1w` | `3w / 1w` | 原 `90d/2d` 与 `20d/5d` 向上折算 |

若两合同逐笔完全相同，只能说明这些字段在当前样本没有成为约束，不能合并其定义。

## 固定审计

- combined / long-only / short-only；
- `4 bps` 主滑点与 `8 bps` 压力；
- 额外延迟一周；
- 周一 `0h` 与半周偏移 `84h`；
- 最近 `1d/7d/1m/3m/6m/1y`，以数据 terminal open 锚定；
- 滚动 `26w`、每 `13w` 前进；
- buy-and-hold 包含同一手续费、滑点与实际 funding。
