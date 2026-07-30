# HYPE-EMA-TB-V35.3 空头 giveaway 分批精确回放

日期：2026-07-29  
状态：diagnostic only；V35.3 保持 `registered / not promoted / not live-ready`；不修改 runner

## 问题

实盘满仓段诊断指出：最大伤口不是“没信号”，而是 **接近 TP 后全仓回吐**。本报告只验证两笔空头 episode：

| 交易 | 实盘结局 | 诊断假设 |
| --- | --- | --- |
| `2026-07-13 14:45 UTC` short | SL，净约 `-1321 USDT / -11.36%` | V35.3 的 `4.4ATR/75%` 分批可把大亏翻成小赚 |
| `2026-07-17 02:00 UTC` short | `manual_exit`，约 `-4.13%` | 若交给策略，研究路径本可 TP；分批再略增收益 |

## 数据与成本

- 市场：Binance USD-M perpetual，`HYPE/USDT:USDT`，`15m`
- UTC 数据：`2025-05-30 10:30` 至 `2026-07-29 02:45`；`40,770` 根已闭合 K
- 数据质量：缺口 / 重复 / 关键空值 / 非法 OHLC / raw-normalized 最大差均为 `0`
- 成本：每 fill allocation `0.00085`；funding 作用于当时剩余 allocation
- 孤立回放：用 V35.3 全路径该笔的研究 entry / ATR / allocation，忽略组合路径依赖，只比较同一 episode 的退出规则

## 口径

| 变体 | 规则 |
| --- | --- |
| 全进全出 | 无分批；硬止损 `7ATR`；TP `5ATR` |
| V35.3 分批 | 空头 MFE `4.4ATR` 一次减仓 `75%`；余仓 `TP5 / SL5.7` |

## 逐笔成交（孤立回放）

### 7/13 short giveaway

| 事件 | 时间 (UTC) | 价格 | 平掉仓位 | 累计权益 | MFE |
| --- | --- | ---: | ---: | ---: | ---: |
| entry | 07-13 14:45 | 64.153 | — | 0.9975 | 0 |
| 分批 75% | 07-13 21:30 | 62.647 | 2.25 | **1.0668** | 4.830 |
| 余仓 SL5.7 | 07-14 22:15 | 66.104 | 0.75 | **1.0236** | 4.830 |

对照：

| 口径 | 最终收益 | vs 全进全出 |
| --- | ---: | ---: |
| 全进全出 → SL7 | **-11.72%** | — |
| V35.3 分批 → 余仓 SL | **+2.36%** | **+14.08pp** |
| 实盘 V35.1 路径 | **-11.36%** | 与全进全出同量级 |
| 峰值浮盈（mark） | 约 **+6.63%** @ 21:30 | 全进全出从峰值吐回 **18.35pp**；分批后吐回仅 **4.26pp** |

结论：这不是“差一点 TP”的执行事故，而是 **缺锁利**。V35.3 分批正好打在伤口上。

### 7/17 short（实盘 manual）

| 事件 | 时间 (UTC) | 价格 | 平掉仓位 | 累计权益 | MFE |
| --- | --- | ---: | ---: | ---: | ---: |
| entry | 07-17 02:00 | 60.043 | — | 0.9975 | 0 |
| 分批 75% | 07-17 07:30 | 58.628 | 2.25 | 1.0656 | 4.991 |
| 余仓 TP5 | 07-18 13:15 | 58.435 | 0.75 | **1.0661** | 5.846 |

对照：

| 口径 | 最终收益 |
| --- | ---: |
| 全进全出 → TP5 | **+6.18%** |
| V35.3 分批 → 余仓 TP | **+6.61%**（Δ +0.44pp） |
| 实盘 manual_exit | **-4.13%** |
| 研究 vs 实盘偏差 | 约 **-10.3pp**（与定稿后对账一致） |

结论：**7/17 的主伤是人工平仓**，不是策略 SL 逻辑。若当时已是 V35.3 且不 manual，分批后仍会走到 TP。

## 判断

1. 保持 V35.3 空头分批；下一笔空头继续吃 `4.4/75%`。
2. 收紧硬 SL **不能**替代分批：7/13 在峰值后仍会从高 MFE 回吐到深亏。
3. 实盘尽量避免非紧急 manual；7/17 是本样本最贵的一次人工干预。
4. 本报告不登记新版本、不修改 runner、不把孤立回放当作 promotion 证据。

## 证据

- 复现脚本：[research_hype_ema_tb_v35_3_giveaway_partial_replay.py](../scripts/research_hype_ema_tb_v35_3_giveaway_partial_replay.py)
- 汇总 JSON：[hype_ema_tb_v35_3_giveaway_partial_replay_2026-07-29.json](../artifacts/hype_ema_tb_v35_3_giveaway_partial_replay_2026-07-29.json)
- 逐笔 fills：[hype_ema_tb_v35_3_giveaway_partial_replay_2026-07-29_fills.csv](../artifacts/hype_ema_tb_v35_3_giveaway_partial_replay_2026-07-29_fills.csv)
- 分批路径逐根 bars：[hype_ema_tb_v35_3_giveaway_partial_replay_2026-07-29_bars.csv](../artifacts/hype_ema_tb_v35_3_giveaway_partial_replay_2026-07-29_bars.csv)
- 全路径 trades：[hype_ema_tb_v35_3_giveaway_partial_replay_2026-07-29_trades.csv](../artifacts/hype_ema_tb_v35_3_giveaway_partial_replay_2026-07-29_trades.csv)
- 相关线上对账：[hype-ema-tb-v35-runner-2026-07-15.md](../runner-tracking/hype-ema-tb-v35-runner-2026-07-15.md) · [hype-ema-tb-v35-post-freeze-live-parity-2026-07-22.md](../runner-tracking/hype-ema-tb-v35-post-freeze-live-parity-2026-07-22.md)
