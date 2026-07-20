# HYPE-EMA-TB-V35 MFE≥4ATR Trailing 跟踪保护回测

日期：2026-07-20

## 结论

在 `HYPE-EMA-TB-V35` 上测试「MFE 达到 `4ATR` 后启动 trailing 跟踪保护」：**不合入 V35，不登记新版本**。

全扫描档位相对 V35 base 都显著降低 full 收益；即便最松的 `trail_a40_d35`（MFE≥4 后按 3.5ATR 回撤跟踪）也只保留约 71% 的 full 收益，Sharpe 下降，且 maxDD 几乎不改善。更紧的回撤距离会进一步截断 `5ATR` TP 尾部，并抬高交易数与 trailing 退出次数。

这与 2026-07-09 的 [V39 trailing 诊断](hype-ema-tb-v39-trailing-stop-diagnostic-2026-07-09.md) 同向：该家族收益依赖打满 `5ATR` 的趋势单，通用 trailing 会系统性砍掉盈利尾部。

## 数据与执行口径

- 市场：Binance USD-M 永续，`HYPE/USDT:USDT`，`15m`
- 数据：本地数据湖 `2025-05-30 10:30 UTC` 至 `2026-07-17 08:45 UTC`，39642 根已闭合 K 线
- 数据质量：缺口 `0`、重复 `0`、关键 OHLCV/null `0`
- 成本：`0.00085`/fill（手续费 + 4bps 滑点合并口径），含 funding
- 执行：K0 close 信号、K2 open 入场、entry ATR 取 K1 已完成值
- Trailing 时序：MFE 与 trailing stop 只在 15m 收盘后更新，下一根起生效；open 已穿越则按 open，否则按 stop 价；同 bar stop/TP 冲突时 stop-first

## V35 基线（同窗）

| 指标 | 数值 |
| --- | ---: |
| full收益 | +7708.65% |
| full maxDD | -27.26% |
| Sharpe | 4.56 |
| 交易数 | 111 |
| 胜率 | 77.48% |
| 退出结构 | TP 84 / SL 16 / indicator 11 |
| 90d收益 | +138.64% |
| 90d maxDD | -27.26% |
| 90d胜率 | 68.57% |

## 主扫描：activation 固定 4ATR

`trail_a40_dY` = MFE≥`4ATR` 后，stop = 最高有利浮盈 − `Y ATR`。

| 变体 | full收益 | full maxDD | Sharpe | 胜率 | 交易数 | trailing退出 | 90d收益 | 90d maxDD | Δfull收益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V35 base | +7708.65% | -27.26% | 4.56 | 77.48% | 111 | 0 | +138.64% | -27.26% | — |
| `trail_a40_d05` | +1666.02% | -30.02% | 3.25 | 75.78% | 128 | 68 | +45.39% | -28.16% | -6042.63pp |
| `trail_a40_d10` | +1541.17% | -35.33% | 3.15 | 75.19% | 129 | 55 | +49.32% | -28.16% | -6167.48pp |
| `trail_a40_d15` | +1653.79% | -33.43% | 3.18 | 76.56% | 128 | 46 | +97.00% | -30.39% | -6054.86pp |
| `trail_a40_d20` | +3280.80% | -34.16% | 3.83 | 78.57% | 126 | 36 | +101.34% | -34.16% | -4427.85pp |
| `trail_a40_d25` | +4192.52% | -25.40% | 4.13 | 79.03% | 124 | 29 | +132.81% | -24.69% | -3516.13pp |
| `trail_a40_d30` | +4593.10% | -26.12% | 4.19 | 79.20% | 125 | 25 | +137.64% | -25.30% | -3115.55pp |
| `trail_a40_d35` | +5507.77% | -26.81% | 4.39 | 80.49% | 123 | 24 | +117.37% | -25.89% | -2200.88pp |
| `trail_a40_d40` | +4308.09% | -27.79% | 4.14 | 75.41% | 122 | 23 | +125.65% | -26.53% | -3400.56pp |

要点：

1. **最好档仍是 `trail_a40_d35`**，但 full 收益少 `2200.88pp`，Sharpe `4.56 -> 4.39`，maxDD 仅改善 `0.45pp`。
2. **`trail_a40_d25` 是唯一明显改善 full maxDD 的档**（`-27.26% -> -25.40%`），但收益少 `3516.13pp`，不可用。
3. 回撤距离越紧，trailing 退出越多、TP 越少；`d05` 把 84 次 TP 砍到 28 次，收益塌陷。

## 标准分片（base vs 最好 trailing）

| 窗口 | V35 base 收益 | V35 base maxDD | `a40_d35` 收益 | `a40_d35` maxDD |
| --- | ---: | ---: | ---: | ---: |
| 1d | +8.94% | -4.64% | +2.25% | -8.30% |
| 7d | -7.71% | -22.94% | -11.75% | -21.49% |
| 1m | -1.53% | -23.96% | -5.84% | -22.54% |
| 3m | +138.64% | -27.26% | +117.37% | -25.89% |
| 6m | +1575.77% | -27.26% | +1218.46% | -25.89% |
| 1y | +7167.82% | -27.26% | +4251.59% | -26.81% |
| full | +7708.65% | -27.26% | +5507.77% | -26.81% |

近期分片也没有被 trailing 救回来：7d/1m 仍为负，且比 base 更差或接近。

## 相邻启动线对照

| 变体 | full收益 | full maxDD | Sharpe | trailing退出 | 判断 |
| --- | ---: | ---: | ---: | ---: | --- |
| `trail_a35_d30` | +2544.20% | -35.35% | 3.70 | 39 | 更早启动更差 |
| `trail_a45_d35` | +5429.85% | -26.81% | 4.29 | 9 | 仍远低于 base |
| `trail_a45_d40` | +5455.56% | -27.49% | 4.28 | 8 | 仍远低于 base |

把启动线挪到 `4.5ATR` 也救不回收益，只是 trailing 触发更少；说明问题不是「4ATR 这个数字选错了」，而是 trailing 机制本身与 V35 的 `5ATR` 趋势 TP 冲突。

## 判断

1. **不合入 V35**：MFE≥4ATR trailing 不能同时改善收益与回撤。
2. **不登记新版本**：本轮是失败诊断，不是候选版本。
3. **与既有结论一致**：近 TP 保护若要继续研究，应走极窄 profit floor（如历史 V38）或事件驱动规则，而不是通用 trailing；即便如此，V38 先前扩展复测也已否决合入。
4. **live-readiness 不变**：V35 仍为 live 主 runner 版本；本诊断不修改 runner。

## 复现与证据

- 脚本：[`../scripts/research_hype_ema_tb_v35_mfe4_trailing.py`](../scripts/research_hype_ema_tb_v35_mfe4_trailing.py)
- 汇总 JSON：[`../artifacts/hype_ema_tb_v35_mfe4_trailing_2026-07-20.json`](../artifacts/hype_ema_tb_v35_mfe4_trailing_2026-07-20.json)
- 逐笔 CSV：[`../artifacts/hype_ema_tb_v35_mfe4_trailing_2026-07-20_trades.csv`](../artifacts/hype_ema_tb_v35_mfe4_trailing_2026-07-20_trades.csv)
- 权益 CSV：[`../artifacts/hype_ema_tb_v35_mfe4_trailing_2026-07-20_equity.csv`](../artifacts/hype_ema_tb_v35_mfe4_trailing_2026-07-20_equity.csv)
