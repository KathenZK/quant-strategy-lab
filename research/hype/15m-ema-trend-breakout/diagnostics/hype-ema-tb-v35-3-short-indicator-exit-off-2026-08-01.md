# HYPE-EMA-TB-V35.3 空头侧关闭指标退出诊断

日期：2026-08-01  
状态：diagnostic only；V35.3 保持 `registered / not promoted / not live-ready`；不修改冻结版、不修改 runner；本变体最多冻结为 shadow candidate 等时间前推 OOS

## 问题

用户痛点：「明明大趋势就是空，指标退出还反复止损」。触发事件为最近两笔空头 `indicator_exit`：

| 交易 (UTC) | 基线结局 | 事后反事实 |
| --- | --- | --- |
| `2026-07-28 11:30` short | `indicator_exit` `-6.00%` | 不退则 7/29 19:45 分批锁 75%、7/30 11:30 余仓 TP，全程 `+6.16%` |
| `2026-08-01 06:00` short | `indicator_exit` `-3.75%`（14:30） | 不退则数据截止时仍持仓，未决 |

全历史空头 `indicator_exit` 仅 3 笔（含上表 2 笔），第三笔 `2025-12-05 19:15` 基线 `-0.39%`，不退则分批后 TP `+7.98%`。即样本内 3/3 空头指标退出全部是负价值。多头侧此前反事实结论相反：关闭会把多数指标退出变成更深 SL。

## 数据与成本

- 市场：Binance USD-M perpetual，`HYPE/USDT:USDT`，`15m`
- UTC 数据：`2025-05-30 10:30` 至 `2026-08-01 15:15`；`41,108` 根已闭合 K
- 质量门：缺口 / 重复 / 关键空值 / 非法 OHLC / raw-normalized 差异均为 `0`，通过
- 成本：每 fill 手续费 `0.001` × allocation + 滑点 `4 bps`；funding 按 8h 实际费率逐根作用于剩余 allocation
- 分片仅用于审计，不用于选参；但本变体本身由已知近期事件启发，属 post-hoc，结论权重按 shadow 处理

## 口径

三个变体只改 `ADX28<22 delayed3` 指标退出的适用方向，其余 V35.3 规则（TP5、多 SL6.75 / 空 SL5.7、空头 `MFE4.4ATR/75%` 分批、timeout384、`MFE>=1.5ATR` 后禁用指标退出）完全不变：

| 变体 | 指标退出 |
| --- | --- |
| `v35_3_base` | 多空都保留（现行） |
| `v35_3_short_ind_exit_off` | 只对多头保留，空头关闭 |
| `v35_3_all_ind_exit_off` | 多空全关（参照，验证多头侧价值） |

实现：读取 [`research_hype_ema_tb_v35_2_short_partial_stop_scan.py`](../scripts/research_hype_ema_tb_v35_2_short_partial_stop_scan.py) 引擎源码，对唯一 `can_indicator_exit` 代码块做方向门控替换后 exec；引擎源码漂移会触发断言失败。脚本见 [`research_hype_ema_tb_v35_3_short_indicator_exit_off.py`](../scripts/research_hype_ema_tb_v35_3_short_indicator_exit_off.py)。

## 结果

| 变体 | full 收益 | full MaxDD | Sharpe | 笔数 | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `v35_3_base` | `+9053.21%` | `-22.88%` | `4.63` | 117 | `77.78%` |
| `v35_3_short_ind_exit_off` | `+11147.93%` | `-22.88%` | `4.78` | 116* | `80.17%` |
| `v35_3_all_ind_exit_off` | `+8830.01%` | `-27.06%` | `4.46` | 115 | `80.87%` |

*变体第 117 笔（8/1 空单）在数据截止时仍持仓，未计入闭合笔数。

标准分片收益（base | short_off | all_off）：`1d` `-4.00 / -3.64 / -3.64`；`7d` `-9.99 / +2.03 / +2.03`；`1m` `+3.95 / +17.84 / +5.39`；`3m` `+141.18 / +173.41 / +111.03`；`6m` `+513.23 / +595.15 / +398.31`；`1y` `+7585.04 / +9343.76 / +9137.16`。

结构性结论：

- 指标退出的价值高度不对称。多头侧净正贡献：全关后 full 降、MaxDD 恶化 `4.18pp`（多头 9 笔指标退出均值 `-4.01%`，多数不退会变成更深 SL）。空头侧净负贡献：样本内 3/3 关闭后更优。
- 只关空头的变体在全部标准分片、full、Sharpe、胜率上不劣于基线，full MaxDD 完全不变（因为 3 笔改持有的空单样本内都没有打到 SL5.7）。
- 路径污染极小：两版 entry 集合 116/117 完全一致，差异仅为 8/1 空单是否被提前退出，归因干净。

## 风险与诚实性

- **样本只有 3 笔，且本测试由已知事件事后启发。** 这正是本仓库反复否决过的 post-hoc 阈值启发模式，无论数字多好都不构成热改依据。
- **7/28 空单是贴脸滑过 SL 的。** 持有路径 MAE 达 `5.01ATR`（7/28 16:45 最高 `55.859`），距 SL5.7 价 `56.059` 仅约 `0.2 USD / 0.69ATR`；若打到，`3.0x` 下该笔约 `-10.4%`，比指标退出的 `-6.00%` 更差。样本内 MaxDD 不变有幸存者成分。
- **8/1 空单未决。** 数据截止时 MAE 已达 `3.56ATR`（最高 `52.698`，SL `53.293`），浮亏约 `-3.4%`；该笔最终可能劣于基线的 `-3.75%` 退出。
- 关闭空头指标退出后，空单少一层早期认错阀：未来失败空单的成本从 `-4%~-6%` 提前退出变为 `-10%` 量级 SL5.7（历史空头 SL 最差 `-10.19%`）或分批解救，属于尾部风险换期望的交换。

## 决定

1. 不修改 V35.3 冻结定义、不登记新版本、不修改 runner。
2. `short indicator exit off` 冻结为 **shadow candidate**：此后每笔实盘/研究路径空头 `indicator_exit` 事件，须同时记录「若不退」影子路径（含 MAE 与最终结局），累计时间前推样本后再议登记。8/1 空单为影子样本第一笔，结局待记录。
3. 多头指标退出维持不变，全关方向就此关闭（本报告 `all_off` 参照已把上一轮聊天反事实固化为持久证据）。

## 证据

- 汇总 JSON：[`hype_ema_tb_v35_3_short_indicator_exit_off_2026-08-01.json`](../artifacts/hype_ema_tb_v35_3_short_indicator_exit_off_2026-08-01.json)
- 逐笔交易：[`hype_ema_tb_v35_3_short_indicator_exit_off_2026-08-01_trades.csv`](../artifacts/hype_ema_tb_v35_3_short_indicator_exit_off_2026-08-01_trades.csv)
- 逐根权益：[`hype_ema_tb_v35_3_short_indicator_exit_off_2026-08-01_equity.csv`](../artifacts/hype_ema_tb_v35_3_short_indicator_exit_off_2026-08-01_equity.csv)
- 复现脚本：[`research_hype_ema_tb_v35_3_short_indicator_exit_off.py`](../scripts/research_hype_ema_tb_v35_3_short_indicator_exit_off.py)
