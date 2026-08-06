# BTC 周 K MA7 V1 零调参迁移诊断

## 结论

把 `HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 原参数换成 BTC 周 K 后，direct transfer **失败**：

- 周一 `00:00 UTC` 主相位 combined `-21.72%`、MDD `-29.61%`、Sharpe `-0.76`，3 笔全部亏损；
- long-only `-30.82%`、short-only `-8.38%`，多空单腿都没有保留正收益；
- `8 bps` 压力为 `-21.91%`，额外延迟一周仍为 `-5.46%`；
- 半周偏移 `84h` 后 combined `-13.48%`，long-only / short-only `-7.14% / -8.23%`，两相位都亏损；
- 两种 max-hold/cooldown 时间合同结果完全相同，因为这些字段在当前逐笔路径没有成为约束；
- 6 个滚动 `26w` combined 窗口仅 1 个为正，中位收益 `-5.07%`。

因此不登记 BTC 周线版本，不晋升，也不在同一段已揭示周线历史上搜索参数。

## 数据质量与周线构建

- 来源：Binance USD-M `BTCUSDT` perpetual accepted `1h` raw/normalized；
- 输入范围：`2024-07-31 00:00` 至 `2026-07-30 09:00 UTC`，`17,506` 根小时 K；
- 缺 K、重复、critical null、非法 OHLC、未闭合 K、raw/normalized mismatch 与 VWAP 公式 mismatch 均为 `0`；
- funding：`2,190` 个事件，重复与 critical null 为 `0`；
- 主相位聚合 `103` 根完整周 K，每根正好 `168` 个小时；
- 半周相位同为 `103` 根；两相位周线质量 blocker 均为 `0`。

完整参数与时间合同见[周线迁移合同](../specs/btc-1w-ma7-v1-transfer-contract-2026-08-05.md)。

## 主相位结果

窗口为 `2024-08-05` 至 `2026-07-27 UTC`：

| Variant | 净收益 | MDD | Sharpe | PF | 交易数 | 暴露 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Combined | `-21.72%` | `-29.61%` | `-0.76` | `0.00` | `3` | `14.56%` |
| Combined + `8 bps` | `-21.91%` | `-29.75%` | `-0.77` | `0.00` | `3` | `14.56%` |
| Combined + 1 week lag | `-5.46%` | `-25.31%` | `-0.13` | `0.52` | `3` | `13.59%` |
| Long-only | `-30.82%` | `-37.79%` | `-1.01` | `0.00` | `3` | `18.45%` |
| Short-only | `-8.38%` | `-10.57%` | `-0.69` | `0.02` | `2` | `0.97%` |
| Perpetual buy-and-hold | `-3.37%` | — | — | — | — | `100%` |

Buy-and-hold 包含约 `15.50%` 初始权益的累计 funding 成本；策略 combined funding 约 `2.09%`。即使以同一 perpetual 持有基线比较，combined 仍落后 `18.34` 个百分点。

## 交易路径

Combined 只有 3 笔：

1. `2025-01-06` 多头，`2025-02-25` protective stop，约 `-12.66%`；
2. `2025-06-30` 多头，`2025-08-29` protective stop，约 `-1.99%`；
3. `2025-09-29` 空头，`2025-10-03` protective stop，约 `-8.54%`。

多头首周仍没有固定 hard stop；当前三笔 combined 又全部亏损，不能用低频作为样本质量的替代。

## 时间合同

| Contract | Combined | Long-only | Short-only |
| --- | ---: | ---: | ---: |
| 数字按周 bar 原样迁移 | `-21.72%` | `-30.82%` | `-8.38%` |
| 按原日历时长折算 | `-21.72%` | `-30.82%` | `-8.38%` |

Bar-transfer 的 long/short max-hold 为 `90w/20w`，clock-equivalent 为 `13w/3w`；所有实际持仓都更早被 trailing、hard stop 或信号退出，因此两合同逐笔相同。

## 相位审计

| Phase | Combined | MDD | Long-only | Short-only |
| --- | ---: | ---: | ---: | ---: |
| 周一 `00:00 UTC` | `-21.72%` | `-29.61%` | `-30.82%` | `-8.38%` |
| 周四 `12:00 UTC` | `-13.48%` | `-24.01%` | `-7.14%` | `-8.23%` |

偏移相位改善了亏损幅度，但没有改变任何方向的失败符号。

## 近期切片与滚动窗口

- 最近 `1d/7d/1m/3m/6m` 均为 `0.00%`，原因是最近半年没有持仓，不是风险消失；
- 最近 `1y` combined / long-only / short-only 为 `-18.10% / -27.62% / -8.54%`；
- 6 个滚动 `26w` combined 窗口仅 1 个为正，中位 `-5.07%`、最差 `-12.66%`；
- long-only 仅 1 个窗口为正，中位 `-7.13%`、最差 `-19.18%`；
- short-only 仅 2 个窗口为正，且大量窗口没有交易。

近期切片只用于 audit，不参与参数选择。

## 未完成门禁

- combined、多空单腿、超额和滚动稳定性全部失败；
- 全窗口只有 3 笔 combined，最近半年无交易；
- 多头首持仓周无 hard stop；
- 当前只有约两年 accepted 数据，无法评价多个 BTC 大周期；
- 无 clean prospective OOS、CPCV、完整极端执行审计、runner parity 或线上对账。

## 决策

1. 将 BTC 周 K MA7 原参数迁移记录为失败 observation。
2. 不登记版本，不推进 promotion 或 runner。
3. 若继续研究 BTC 周线，应设计新的预先冻结周线机制；不得把本次已揭示结果用于事后改 MA 长度、周界线或保护参数后再称 OOS。

## 证据

- [机器摘要](../artifacts/btc_1w_ma7_v1_transfer_summary_2026-08-05.json)
- [指标表](../artifacts/btc_1w_ma7_v1_transfer_metrics_2026-08-05.csv)
- [近期切片](../artifacts/btc_1w_ma7_v1_transfer_recent_2026-08-05.csv)
- [相位审计](../artifacts/btc_1w_ma7_v1_transfer_phase_2026-08-05.csv)
- [滚动 26 周](../artifacts/btc_1w_ma7_v1_transfer_rolling_26w_2026-08-05.csv)
- [交易明细](../artifacts/btc_1w_ma7_v1_transfer_trades_2026-08-05.csv)
- [Bar-transfer 路径](../artifacts/btc_1w_ma7_v1_transfer_bar_transfer_path_2026-08-05.csv)
- [Clock-equivalent 路径](../artifacts/btc_1w_ma7_v1_transfer_clock_equivalent_path_2026-08-05.csv)
- [复现脚本](../scripts/research_btc_1w_ma7_v1_transfer.py)
