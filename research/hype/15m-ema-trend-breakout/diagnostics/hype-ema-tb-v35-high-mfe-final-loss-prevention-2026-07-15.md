# HYPE-EMA-TB-V35 高浮盈最终转亏防护诊断

日期：2026-07-15

## 结论

围绕“减少高浮盈最终转亏次数”完成 `116` 个状态机变体扫描。结果表明该目标可以在历史样本内实现，但不存在免费方案：

- 极窄保护可以几乎保留 V35 的长期收益，但只能把 `MFE>=4ATR` 最终亏损从 `3` 笔减少到 `2` 笔，而且弱 reset 仍可能在保护退出后同向重入并再次止损。
- 从 `3ATR` 开始保护，并在保护退出后等待新的趋势 cycle，能把样本内 `MFE>=3ATR` 最终亏损从 `9` 笔降为 `0`，同时把 maxDD 从 `-23.46%` 降至约 `-18%`，胜率提高到 `88.73%~94.34%`。
- 代价很大：最终资金只保留 V35 base 的约 `8.69%~12.02%`。这是高胜率、低回撤与趋势尾部收益之间的真实交换。

本轮不修改线上 `HYPE-EMA-TB-V35`，不登记新版本。保留两个研究侧防守观察候选：

1. 平衡防守：`floor_a30_l30_adx_cycle`。
2. 高胜率防守：`floor_a30_l30_core_trend`。

两者都直接使用了本次 `4.83ATR -> stop_loss` 事件参与诊断，属于 post-hoc 样本内候选；至少需要新的未来 OOS 和 live-executable STOP_MARKET/重启恢复审计后，才允许讨论 runner 变更。

## 数据与执行口径

- Exchange：Binance。
- Market：USD-M perpetual。
- Symbol：`HYPE/USDT:USDT`。
- Timeframe：`15m`。
- 数据源：Binance public API。
- UTC 范围：`2025-05-30 10:30` 至 `2026-07-15 03:15`。
- 已闭合 K 线：`39,428` 根；缺口 `0`、重复 `0`、关键空值 `0`、无效 OHLC `0`。
- Funding：Binance funding，按 15m 时间轴对齐。
- 成本：家族 canonical override，`0.00085`/fill，含手续费与 `4 bps` adverse slippage；另计 funding。
- 入场：K0 close 信号，跳过 K1，K2 open 入场；entry ATR 使用已完成 K1 的 `ATR672`。
- 原始 bracket：固定 entry ATR `5ATR TP / 7ATR SL`，同 bar `stop-first`。
- Profit floor：15m 收盘后更新 MFE；达到启动线后上移 stop，下一根 K 起生效。若下一根 open 已穿越 floor，则按 open 成交，否则按 floor stop 成交。
- 原始 `mfe>=1.5ATR` 后关闭 indicator exit、384-bar timeout 与其它 V35 规则保持不变。

## 基线问题

更新至本次最终止损后，V35 base：

| 指标 | 结果 |
| --- | ---: |
| Full 收益 | +7369.23% |
| MaxDD | -23.46% |
| Sharpe | 4.56 |
| 交易数 | 109 |
| 胜率 | 77.98% |
| TP / SL / indicator | 83 / 16 / 10 |

按单笔历史 MFE 统计：

| MFE 门槛 | 达标交易 | 最终亏损 | 转亏率 |
| --- | ---: | ---: | ---: |
| >=1.5ATR | 95 | 14 | 14.74% |
| >=2ATR | 91 | 12 | 13.19% |
| >=3ATR | 85 | 9 | 10.59% |
| >=4ATR | 65 | 3 | 4.62% |
| >=4.5ATR | 42 | 1 | 2.38% |
| >=4.75ATR | 21 | 1 | 4.76% |

最新交易为 `2026-07-13 14:45 UTC` 空单：MFE `4.82993ATR`，最终于 `2026-07-15 02:45 UTC` 按 `7ATR` stop loss 平仓，研究模型净亏 `-11.49%`。

## 扫描定义

Profit floor 启动线与锁定线均使用 entry ATR：

- 启动线：`3.0 / 3.5 / 4.0 / 4.5 / 4.75ATR`。
- 锁定线：按启动线扫描 `0.5~4.25ATR`；`3ATR` 启动线额外细扫 `1.75 / 2.0 / 2.25 / 2.5 / 2.75 / 3.0ATR`。

保护退出后的同向重入状态机：

- `none`：不限制重入。
- `signal_once`：完整同向入场信号至少 false 一次。
- `signal_false4`：完整同向信号连续 false 四根 15m K。
- `adx_cycle`：ADX 至少回落到该方向入场门槛以下一次；多头门槛 `28`，空头门槛 `36`。
- `core_trend`：方向核心失效后才允许开启新 episode。多头要求 EMA spread 或 1h DI 多头核心失效；空头要求 EMA spread 或 1h EMA 空头核心失效。

选择目标按以下顺序：

1. 减少 `MFE>=4ATR` 且最终净亏的交易。
2. 改善 maxDD，并进一步减少 `MFE>=3ATR` 最终亏损。
3. 在前两项接近时尽量保留复利收益。

## 关键结果

| 规则 | Full 收益 | 资金保留率 | MaxDD | Sharpe | 胜率 | 交易数 | MFE>=3 最终亏损 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V35 base | +7369.23% | 100.00% | -23.46% | 4.56 | 77.98% | 109 | 9 |
| `4.75 -> 3.5 + signal_false4` | +7347.03% | 99.70% | -23.46% | 4.70 | 80.58% | 103 | 8 |
| `4.75 -> 4.0 + core_trend` | +4464.10% | 61.11% | -23.46% | 4.62 | 82.14% | 84 | 7 |
| `3.0 -> 3.0 + adx_cycle` | +797.99% | 12.02% | -18.31% | 3.94 | 88.73% | 71 | 0 |
| `3.0 -> 2.25 + core_trend` | +625.71% | 9.72% | -18.17% | 3.92 | 92.98% | 57 | 0 |
| `3.0 -> 3.0 + core_trend` | +549.40% | 8.69% | -17.73% | 3.96 | 94.34% | 53 | 0 |

### 候选 A：平衡防守

`floor_a30_l30_adx_cycle`：

- 收盘确认 MFE 达到 `3ATR` 后，把保护 stop 抬到 `+3ATR`，下一根起生效。
- floor 退出后，同方向必须等 ADX 至少跌回入场门槛以下，才视为完成一次趋势 cycle reset。
- Full `+797.99% / -18.31% / Sharpe 3.94 / 71 笔 / 胜率 88.73%`。
- `MFE>=3ATR` 的 58 笔交易最终亏损 `0`。
- 最近 `1m +46.41% / -14.64%`，`3m +129.26% / -14.64%`，`6m +305.65% / -17.25%`，`1y +590.10% / -18.31%`。
- 最新空单在 `2026-07-13 20:30 UTC` 按 next-open gap 口径于 `63.48` 退出，净收益约 `+2.81%`，之后未在同一空头 episode 重入。

### 候选 B：高胜率防守

`floor_a30_l30_core_trend`：

- floor 同候选 A。
- floor 退出后，必须等待方向核心失效，才允许开启新的同向 episode。
- Full `+549.40% / -17.73% / Sharpe 3.96 / 53 笔 / 胜率 94.34%`。
- 退出结构：profit floor `41`、TP `7`、indicator `5`、stop loss `0`。
- `MFE>=3ATR` 的 45 笔交易最终亏损 `0`。
- 最近 `1m +26.70% / -14.64%`，`3m +97.17% / -14.64%`，`6m +229.29% / -17.25%`，`1y +426.10% / -17.73%`。
- 最新空单同样在 `2026-07-13 20:30 UTC` 退出，之后没有同 episode 重入。

## 为什么极窄 floor 仍不够

`4.75 -> 3.5 + signal_false4` 表面上几乎不损失长期收益，并把最新原始空单转为 `+5.31%`；但四根信号 false 后，它在 `2026-07-14 00:30 UTC` 再次做空，随后止损 `-11.13%`。原始高 MFE 单虽然不再“最终转亏”，整个趋势 episode 仍然亏损。

这说明评价单位不能只看原始 trade ID，必须同时检查保护退出后的占仓链。要真正减少该类线上体验，profit floor 与 episode reset 必须一起定义。

## 判断与后续

1. 历史样本内可以把 `MFE>=3ATR` 最终转亏降为 `0`，也可以把胜率推到 `94.34%`，但无法在保留 V35 大部分复利收益的同时做到。
2. 候选 A/B 是新的防守型机制，不是 V35 的无代价修补；若未来推进，应登记为独立观察版本，而不是静默覆盖 V35。
3. 本轮参数使用最新亏损事件参与选择，存在明显 post-hoc 风险。当前只适合影子计算，不能修改 live runner。
4. 下一道证据门槛：
   - 冻结候选 A/B 参数，不再继续追逐胜率；
   - 等待未来 OOS 新交易；
   - 对 STOP_MARKET 上移、open gap、订单改单、重启恢复和持久化 reset 状态做 live-executable 审计；
   - 若未来 OOS 出现 `MFE>=3ATR` 后最终亏损，直接否决“零高浮盈转亏”的强结论。

## 证据

- 复现脚本：[research_hype_ema_tb_v35_high_mfe_loss_prevention.py](../scripts/research_hype_ema_tb_v35_high_mfe_loss_prevention.py)
- 摘要 JSON：[hype_ema_tb_v35_high_mfe_loss_prevention_2026-07-15.json](../artifacts/hype_ema_tb_v35_high_mfe_loss_prevention_2026-07-15.json)
- 入围逐笔交易：[hype_ema_tb_v35_high_mfe_loss_prevention_2026-07-15_shortlist_trades.csv](../artifacts/hype_ema_tb_v35_high_mfe_loss_prevention_2026-07-15_shortlist_trades.csv)
- 入围权益曲线：[hype_ema_tb_v35_high_mfe_loss_prevention_2026-07-15_shortlist_equity.csv](../artifacts/hype_ema_tb_v35_high_mfe_loss_prevention_2026-07-15_shortlist_equity.csv)
