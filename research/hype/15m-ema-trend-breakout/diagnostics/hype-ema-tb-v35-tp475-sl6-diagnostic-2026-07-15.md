# HYPE-EMA-TB-V35 `TP 4.75 / SL 6` 诊断

日期：2026-07-15

## 结论

不建议把 `HYPE-EMA-TB-V35` 从 `5ATR TP / 7ATR SL` 改为 `4.75ATR TP / 6ATR SL`。

组合调整确实会让最新 `4.83ATR -> stop_loss` 空单先在 `4.75ATR` 止盈，但全样本结果显著劣化：

- Full 收益从 `+7369.23%` 降至 `+3786.96%`，最终资金只保留基线的 `52.04%`。
- MaxDD 从 `-23.46%` 恶化至 `-32.62%`。
- Sharpe 从 `4.56` 降至 `4.04`。
- 胜率从 `77.98%` 降至 `74.17%`，并没有因缩短 TP、收紧 SL 而提高。
- 交易数从 `109` 增至 `120`，stop loss 从 `16` 笔增至 `25` 笔。

主要问题不是单笔 `SL` 少亏 `1ATR`，而是更早退出改变了持仓占用链，产生更多重入和后续止损。`SL 6` 本身是主要负贡献项；`TP 4.75` 也显著损失趋势尾部复利。

本轮不修改 V35、不登记新版本、不修改 live runner。

## 数据与执行口径

- Exchange：Binance。
- Market：USD-M perpetual。
- Symbol：`HYPE/USDT:USDT`。
- Timeframe：`15m`。
- 数据源：Binance public API。
- UTC 范围：`2025-05-30 10:30` 至 `2026-07-15 03:15`。
- 已闭合 K 线：`39,428` 根；缺口 `0`、重复 `0`、关键空值 `0`、无效 OHLC `0`。
- Funding：Binance funding，按 15m 时间轴对齐。
- 成本：家族 canonical override，`0.00085`/fill，包含手续费与 `4 bps` adverse slippage；另计 funding。
- 入场：K0 close 信号，跳过 K1，K2 open 入场；entry ATR 使用已完成 K1 的 `ATR672`。
- TP/SL：固定 entry ATR；同一根 15m K 同时触及 TP 与 SL 时按 `stop-first`。
- 其余 V35 信号、`mfe>=1.5ATR` 后关闭 indicator exit、仓位和 timeout 规则不变。
- 选择披露：本组参数由最新临近 TP 后止损事件触发，属于 post-hoc 样本内诊断；标准分片只作审计。

## 分项对照

| 规则 | Full 收益 | 资金保留率 | MaxDD | Sharpe | 胜率 | 交易数 | TP / SL / indicator |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `TP5 / SL7` 基线 | +7369.23% | 100.00% | -23.46% | 4.56 | 77.98% | 109 | 83 / 16 / 10 |
| `TP4.75 / SL7` | +5062.64% | 69.12% | -23.46% | 4.19 | 78.38% | 111 | 85 / 17 / 9 |
| `TP5 / SL6` | +4871.27% | 66.56% | -26.82% | 4.25 | 73.50% | 117 | 84 / 25 / 8 |
| `TP4.75 / SL6` | +3786.96% | 52.04% | -32.62% | 4.04 | 74.17% | 120 | 87 / 25 / 8 |

分项结果说明：

1. 只缩 TP 可以覆盖最新事件，但最终资金损失约 `30.88%`，full maxDD 没有改善。
2. 只把 SL 从 `7ATR` 收到 `6ATR` 反而增加 `9` 次 stop loss，胜率下降 `4.48pp`，maxDD 恶化 `3.36pp`。
3. 两项叠加不是风险折中，而是把两种路径损失叠加，最终资金接近减半，maxDD 恶化 `9.16pp`。

## 标准近期分片

| 窗口 | `TP5 / SL7` 收益 / MaxDD | `TP4.75 / SL6` 收益 / MaxDD |
| --- | ---: | ---: |
| 1d | -16.26% / -16.26% | -3.00% / -5.27% |
| 7d | -11.72% / -17.21% | +3.60% / -5.63% |
| 1m | +8.94% / -21.85% | +23.92% / -17.75% |
| 3m | +135.14% / -21.90% | +82.42% / -32.62% |
| 6m | +1634.34% / -21.90% | +762.97% / -32.62% |
| 1y | +6851.92% / -21.90% | +3262.07% / -32.62% |

组合调整只在最新 `1d/7d/1m` 因直接针对该事件而显得更好；从 `3m` 开始收益和回撤均落后，符合 post-hoc 保护的典型特征。

## 最新事件反事实

`TP4.75 / SL6` 与只改 `TP4.75` 的最新路径相同，因为 TP 先于新 SL 被触发：

1. `2026-07-13 14:45 UTC` 空单在 `21:30 UTC` 按 `4.75ATR` 止盈，研究模型净收益 `+7.49%`。
2. `22:00 UTC` 同向重新开空，`2026-07-14 10:00 UTC` indicator exit，净亏 `-3.13%`。
3. 两笔复利合计约 `+4.13%`，优于原 V35 该单最终 `-11.49%`。

这证明固定 TP 能修复当前事件，但不能证明它改善长期策略；全样本中其代价远大于这一笔被挽回的损失。

## 证据

- 复现脚本：[research_hype_ema_tb_v35_tp_sl_adjustment.py](../scripts/research_hype_ema_tb_v35_tp_sl_adjustment.py)
- 摘要 JSON：[hype_ema_tb_v35_tp475_sl6_diagnostic_2026-07-15.json](../artifacts/hype_ema_tb_v35_tp475_sl6_diagnostic_2026-07-15.json)
- 逐笔交易：[hype_ema_tb_v35_tp475_sl6_diagnostic_2026-07-15_trades.csv](../artifacts/hype_ema_tb_v35_tp475_sl6_diagnostic_2026-07-15_trades.csv)
- 权益曲线：[hype_ema_tb_v35_tp475_sl6_diagnostic_2026-07-15_equity.csv](../artifacts/hype_ema_tb_v35_tp475_sl6_diagnostic_2026-07-15_equity.csv)
