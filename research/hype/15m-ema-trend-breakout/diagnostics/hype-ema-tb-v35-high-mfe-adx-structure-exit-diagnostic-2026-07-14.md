# HYPE-EMA-TB-V35 高 MFE 后 ADX 弱化 + 价格结构退出版诊断

日期：2026-07-14

## 结论

本轮不修改 `HYPE-EMA-TB-V35` 的正式退出规则。

达到约 `4ATR` 后再要求“ADX 弱化 + 15m 价格结构反转”确实能覆盖当前 `4.83ATR` 临门回吐案例，但所有已测定义都显著弱于 V35 基线：

- 截止当前事件前，V35 base 为 `+8360.80% / -23.46% / Sharpe 4.71`。
- 结构退出版最高 full 收益为 `+6329.63%`，最大回撤为 `-26.69%`；没有同时改善收益、回撤与 Sharpe 的变体。
- 较有代表性的 `MFE>=4ATR + ADX 从峰值回落 5 点 + 2-bar swing break + episode reset` 为 `+6203.53% / -26.03% / Sharpe 4.61`，仍明显弱于 base。
- 当前空单上，最快且相对合理的动态 ADX 变体在 `2026-07-14 04:00 UTC` 退出，净收益约 `+3.74%`；但价格层面只保留约 `2.63ATR`，仍从 `4.83ATR` 峰值回吐约 `2.20ATR`。

因此，“ADX 弱化 + 价格结构反转”比全程保留 `ADX<22` 更有针对性，但仍不是足够好的高浮盈保护机制。它既没有锁住接近 `5ATR` 的大部分利润，也会在历史趋势单中提前退出并改变后续占仓路径。

## 数据与执行口径

- Exchange：Binance。
- Market：USD-M perpetual。
- Symbol：`HYPE/USDT:USDT`。
- Timeframe：`15m`。
- 数据源：Binance public API。
- UTC 范围：`2025-05-30 10:30` 至 `2026-07-14 12:45`。
- 已闭合 K 线：`39,370` 根；缺口 `0`、重复 `0`、关键空值 `0`、无效 OHLC `0`。
- Funding：Binance funding，按 15m 时间轴对齐。
- 成本：家族 canonical override，`0.00085`/fill，含手续费与 `4 bps` adverse slippage；另计 funding。
- 入场：K0 close 信号，跳过 K1，K2 open 入场；entry ATR 使用已完成 K1 的 `ATR672`。
- 原始 bracket：固定 entry ATR `5ATR TP / 7ATR SL`，同 bar `stop-first`。
- 条件退出：15m 收盘确认，下一根 open 成交；结构水平只使用当前 K 之前的已完成 K，不含当前 K，无 lookahead。

为了避免当前仍未按 base 平仓的仓位造成 mark-to-market 干扰，主比较截断在本次入场前的 `2026-07-13 14:30 UTC`。

## 变体定义

共同条件：只有本笔历史 MFE 达到指定启动线后，才开启高 MFE 条件退出；原始 `5ATR TP / 7ATR SL / 384-bar timeout` 始终保留。

价格结构反转：

- 多单：当前 close 跌破前 `L` 根已完成 15m K 的最低 low。
- 空单：当前 close 突破前 `L` 根已完成 15m K 的最高 high。
- 扫描 `L=2/4/8`；主假设使用 `L=4`。

ADX 弱化扫描三种定义：

1. `below_threshold`：`ADX28<22` 连续 `2/3` 根。
2. `falling`：MFE 启动后 ADX 连续下降 `2` 根。
3. `peak_drop`：MFE 启动后 ADX 相对该阶段峰值回落至少 `5` 点。

`episode reset` 变体在条件退出后禁止同向重入，直到该方向的延迟入场信号至少完整变为 false 一次；反向信号不被禁止。

## 事件前 full-window 结果

| 规则 | Full 收益 | MaxDD | Sharpe | 交易数 | 胜率 | TP / 结构退出 / SL / 早期指标退出 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| V35 base | +8360.80% | -23.46% | 4.71 | 108 | 78.70% | 83 / 0 / 15 / 10 |
| 全程保留 `ADX<22 delayed3` | +1884.26% | -29.73% | 3.77 | 109 | 68.81% | 57 / 0 / 8 / 44 |
| `MFE4 + ADX<22×3 + swing2` | +6194.83% | -26.04% | 4.59 | 108 | 77.78% | 75 / 8 / 15 / 10 |
| `MFE4 + ADX<22×3 + swing4 + reset` | +5772.48% | -26.69% | 4.52 | 108 | 76.85% | 73 / 10 / 15 / 10 |
| `MFE4 + ADX falling×2 + swing2 + reset` | +5823.88% | -25.63% | 4.53 | 115 | 74.78% | 73 / 19 / 13 / 10 |
| `MFE4 + ADX peak-drop5 + swing2 + reset` | +6203.53% | -26.03% | 4.61 | 110 | 76.36% | 75 / 12 / 13 / 10 |
| `MFE4.5 + ADX<22×3 + swing4 + reset` | +6329.63% | -26.69% | 4.47 | 108 | 76.85% | 75 / 8 / 15 / 10 |

主要归因：

- 条件退出减少了一部分最终硬止损，但同时把 V35 的 TP 从 `83` 次降到 `73~75` 次。
- V35 的复利主要依赖这些完整跑到 `5ATR` 的趋势尾部；少数止损改善不足以补偿 TP 减少。
- `episode reset` 对 `ADX<22` 变体没有产生差异，说明这些历史退出后入场信号通常已经自然 reset。
- 对更敏感的 ADX 连续下降定义，episode reset 能把 full 从 `+5142.26% / -28.04%` 修复到 `+5823.88% / -25.63%`，但仍明显弱于 base。

## 当前 `4.83ATR` 空单反事实路径

共同入场：

- Entry：`2026-07-13 14:45 UTC @ 64.153`。
- Entry ATR672：`0.3422410714`。
- MFE：`4.82993ATR`。

| 规则 | 退出时间 UTC | 退出价 | 单笔净收益 | 价格层面保留 |
| --- | --- | ---: | ---: | ---: |
| V35 base | 截至 `2026-07-14 12:45` 仍 open | - | mark-to-market | - |
| 全程保留 `ADX<22 delayed3` | `10:00` | 63.487 | +2.52% | 约 1.95ATR |
| `ADX<22×3 + swing2` | `10:15` | 63.830 | +0.86% | 约 0.94ATR |
| `ADX<22×3 + swing4` | `10:45` | 63.881 | +0.62% | 约 0.79ATR |
| `ADX falling×2 + swing2 + reset` | `04:00` | 63.254 | +3.74% | 约 2.63ATR |
| `ADX peak-drop5 + swing2 + reset` | `04:00` | 63.254 | +3.74% | 约 2.63ATR |
| `ADX falling×2 + swing4 + reset` | `05:15` | 63.755 | +1.28% | 约 1.16ATR |

这说明当前案例里，`ADX<22` 是明显滞后信号；改用 ADX 连续下降或峰值回落可以提前约 6 小时，但与价格结构确认叠加后，仍要吐掉接近一半的 MFE 才退出。

## 决定

1. V35 保持 `mfe>=1.5ATR` 后关闭 indicator exit，以及原始 `5ATR TP / 7ATR SL`。
2. 不采用全程 `ADX<22`、高 MFE 后恢复 `ADX<22` 或本轮 ADX+结构退出版。
3. 不登记新版本，不修改 live runner。
4. 若继续研究，优先方向不是继续细调 ADX/swing 窗口，而是把“利润保护价”和“是否允许同向重入”拆开：
   - 退出价需要显式限制最大允许 giveback，而不是等待滞后指标；
   - 同向重入需要等待完整 trend episode reset，避免 floor/保护退出后立刻重新占仓；
   - 两者必须作为完整状态机一起回放。

## 证据

- 复现脚本：[research_hype_ema_tb_v35_high_mfe_structure_exit.py](../scripts/research_hype_ema_tb_v35_high_mfe_structure_exit.py)
- 摘要 JSON：[hype_ema_tb_v35_high_mfe_structure_exit_2026-07-14.json](../artifacts/hype_ema_tb_v35_high_mfe_structure_exit_2026-07-14.json)
- 逐笔交易：[hype_ema_tb_v35_high_mfe_structure_exit_2026-07-14_trades.csv](../artifacts/hype_ema_tb_v35_high_mfe_structure_exit_2026-07-14_trades.csv)
- 权益曲线：[hype_ema_tb_v35_high_mfe_structure_exit_2026-07-14_equity.csv](../artifacts/hype_ema_tb_v35_high_mfe_structure_exit_2026-07-14_equity.csv)
