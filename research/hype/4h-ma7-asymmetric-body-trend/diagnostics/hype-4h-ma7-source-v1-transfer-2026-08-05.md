# HYPE 4H MA7 源 V1 迁移诊断

## 结论

把 `HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 的状态机迁移到 `4h SMA7` 后，两种合理时间解释均失败：

- bar-transfer combined：`-67.72%`，MDD `-77.47%`，105 笔；
- clock-equivalent combined：`-2.61%`，MDD `-34.21%`，63 笔；
- clock-equivalent long-only / short-only 分别为 `+17.07% / -23.54%`；
- clock-equivalent 加 `8 bps/fill` 为 `-7.41%`，额外延迟一根 `4h` 为 `-28.18%`；
- clock-equivalent 的 `2h` 相位为 `-25.09%`，long-only 从 `+17.07%` 翻为 `-8.65%`；
- 同期计成本和 funding 的 `1x` buy-and-hold 为 `+50.58%`。

4 小时 MA7 没有复制日线 V1 的历史表现。较合理的 clock-equivalent 仅接近盈亏平衡，依然没有绝对收益、超额收益或相位稳定性；本家族保持 `explore / not promoted / not live-ready`，不登记版本。

## 数据与执行

- Binance USD-M `HYPEUSDT` perpetual。
- `1h` 数据范围：`2025-05-30 10:00` 至 `2026-07-30 04:00 UTC`，共 `10,219` 根；缺口、重复、OHLC、关键空值、raw/normalized 对齐 blocker 均为 `0`。
- 基准相位形成 `2,554` 根完整 `4h`，策略窗口为 `2025-05-30 12:00` 至 `2026-07-30 04:00 UTC`。
- 信号在完整 `4h` 收盘产生，下一 `4h` open 成交；stop 使用组成 bar 的 `1h` 顺序；funding 按真实事件时间结算。
- 手续费 `0.001/fill`，基准滑点 `4 bps/fill`。

## 两种时间解释

状态机价格参数和 `SMA7/ATR7` 完全相同，只改变最长持仓与冷却：

| 合同 | 多头 max / cooldown | 空头 max / cooldown | 含义 |
| --- | --- | --- | --- |
| Bar-transfer | `90 / 2 bars` | `20 / 5 bars` | 数字直接转为 4 小时 bar |
| Clock-equivalent | `540 / 12 bars` | `120 / 30 bars` | 近似保持源 V1 的日历时间 |

## 全窗口结果

| 合同/方向 | 净收益 | MDD | Sharpe | PF | 交易数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bar combined | `-67.72%` | `-77.47%` | `-1.69` | `0.55` | `105` |
| Bar long-only | `-3.67%` | `-38.90%` | `0.18` | `0.98` | `77` |
| Bar short-only | `-49.15%` | `-54.15%` | `-1.78` | `0.35` | `48` |
| Clock combined | `-2.61%` | `-34.21%` | `0.15` | `0.98` | `63` |
| Clock long-only | `+17.07%` | `-31.33%` | `0.53` | `1.15` | `55` |
| Clock short-only | `-23.54%` | `-31.06%` | `-0.82` | `0.44` | `32` |
| Buy-and-hold | `+50.58%` | — | — | — | — |

Bar-transfer 把日线时间参数压缩了六倍，导致高换手和严重亏损。Clock-equivalent 降低了换手，但 short leg 仍持续侵蚀 long leg。

## 时间切分

| 合同/方向 | `2026-05-01` 前 | 最后约 `90d` flat-start | 全期 |
| --- | ---: | ---: | ---: |
| Bar combined | `-70.91%` | `+10.95%` | `-67.72%` |
| Bar long-only | `-22.40%` | `+24.13%` | `-3.67%` |
| Bar short-only | `-40.28%` | `-14.85%` | `-49.15%` |
| Clock combined | `-14.01%` | `+17.56%` | `-2.61%` |
| Clock long-only | `-5.63%` | `+24.05%` | `+17.07%` |
| Clock short-only | `-19.50%` | `-5.01%` | `-23.54%` |

最后 90 日改善来自 long leg；short leg 在前后两段都亏损。最后窗口已被揭示，不能据此选择 long-only 作为新版本。

## 成本与延迟

| 合同 | 基准 `4 bps` | `8 bps` | 额外延迟一根 `4h` |
| --- | ---: | ---: | ---: |
| Bar-transfer | `-67.72%` | `-70.33%` | `-74.46%` |
| Clock-equivalent | `-2.61%` | `-7.41%` | `-28.18%` |

Clock-equivalent 对一根 bar 的额外延迟非常敏感，不能视为接近通过。

## 相位

| 合同/方向 | `0h` | `2h` | 判断 |
| --- | ---: | ---: | --- |
| Bar combined | `-67.72%` | `-40.94%` | 两相位均失败 |
| Bar long-only | `-3.67%` | `-28.01%` | 两相位均失败 |
| Bar short-only | `-49.15%` | `+8.49%` | 符号翻转 |
| Clock combined | `-2.61%` | `-25.09%` | 两相位均失败 |
| Clock long-only | `+17.07%` | `-8.65%` | 符号翻转 |
| Clock short-only | `-23.54%` | `-4.96%` | 两相位均失败 |

## 近期切片

| Clock-equivalent | `1d` | `7d` | `1m` | `3m` | `6m` | `1y` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Combined | `0.00%` | `0.00%` | `-3.88%` | `+13.25%` | `-11.35%` | `+5.77%` |
| Long-only | `0.00%` | `0.00%` | `-0.11%` | `+24.05%` | `+24.95%` | `+44.77%` |
| Short-only | `0.00%` | `-1.40%` | `-3.90%` | `-5.01%` | `-12.63%` | `-25.37%` |

## 90 日滚动窗口

共 12 个窗口，步长 30 日：

- Bar combined：`2/12` 为正，中位 `-26.18%`，最差 `-47.77%`；
- Clock combined：`5/12` 为正，中位 `-0.48%`，最差 `-19.43%`；
- Clock long-only：`9/12` 为正，中位 `+10.08%`，最差 `-23.21%`；
- Clock short-only：`0/12` 为正，中位 `-5.46%`。

## 决策

1. 不登记 HYPE 4H MA7 版本，不推进 promotion。
2. 不把最后 90 日或 clock long-only 的事后改善写成 OOS 结论。
3. 若继续研究 4 小时趋势，应重新定义独立的 4H 机制和预先冻结的搜索/OOS 合同，而不是继续挪用日线 V1 参数。

## 证据

- [迁移合同](../specs/hype-4h-ma7-source-v1-transfer-contract-2026-08-05.md)
- [机器摘要](../artifacts/hype_4h_ma7_v1_transfer_summary_2026-08-05.json)
- [指标表](../artifacts/hype_4h_ma7_v1_transfer_metrics_2026-08-05.csv)
- [近期切片](../artifacts/hype_4h_ma7_v1_transfer_recent_2026-08-05.csv)
- [相位审计](../artifacts/hype_4h_ma7_v1_transfer_phase_2026-08-05.csv)
- [滚动窗口](../artifacts/hype_4h_ma7_v1_transfer_rolling_90d_2026-08-05.csv)
- [交易记录](../artifacts/hype_4h_ma7_v1_transfer_trades_2026-08-05.csv)
- [Bar-transfer 路径](../artifacts/hype_4h_ma7_v1_transfer_bar_transfer_path_2026-08-05.csv)
- [Clock-equivalent 路径](../artifacts/hype_4h_ma7_v1_transfer_clock_equivalent_path_2026-08-05.csv)
- [复现脚本](../scripts/research_hype_4h_ma7_v1_transfer.py)
