# HYPE-1H-Bollinger-Keltner-Squeeze-Breakout 基础策略诊断（2026-07-23）

## 结论

`1h` 基础规则未通过本轮最低可行性门槛，门槛为
`4/8`。主口径净收益
`-51.71%`，MaxDD
`-68.32%`，闭合交易
`165` 笔，胜率
`31.52%`，profit factor
`0.814`。失败检查：
`full_return_positive, max_drawdown_not_worse_than_35pct, development_positive, validation_positive`。

本报告是冻结基础机制的探索性诊断，不是参数搜索，不登记版本，也不支持
promotion。当前状态保持 `explore / not promoted / not live-ready`。

## 冻结规则

- Bollinger：收盘 `SMA20 ± 2 × population std20`。
- Keltner：同一 `SMA20 ± 1.5 × mean true range20`。
- squeeze：布林上轨低于 Keltner 上轨且布林下轨高于 Keltner 下轨，连续至少
  `3` 根。
- release/breakout：布林离开 Keltner 且宽度扩张；释放当根及随后 `2` 根内，
  收盘突破 squeeze episode 的 high/low 才产生对应多/空信号。
- K0 闭合确认，主口径 K1 open 入场；固定 `1x`、单持仓、不加仓。
- 紧急止损：`3 × signal ATR20`，从入场 15m 子柱起生效，gap 按更差 open。
- 正常退出：多头收盘跌破 SMA20、空头收盘升破 SMA20，下一目标周期 open；
  最长 `40` 根目标周期，冷却 `1` 根。
- 成本：每 fill 手续费 `0.001` + adverse slippage `4 bps`，实际 Binance
  funding 按 15m 执行网格计入。

所有参数在运行前冻结；K2、零成本和事件 horizon 只作诊断，不用于选择或调参。

## 数据与质量

- 市场：Binance USD-M Futures `HYPEUSDT` perpetual。
- 原始执行网格：闭合 `15m`，`2025-05-30T10:30:00+00:00` 至 `2026-07-23T05:45:00+00:00`，
  `40206` 根；缺口 `0`、raw/normalized
  mismatch `0`、blocker
  `0`。
- 本周期：`2025-05-30T11:00:00+00:00` 至 `2026-07-23T05:00:00+00:00`，
  `10051` 根完整 `1h` K 线；
  丢弃不完整首尾桶 `1`，聚合 blocker
  `0`。
- 高周期信号由完整 UTC 桶构建；实际止损、mark-to-market 与 funding 仍在真实
  15m 子柱执行，未用高周期 OHLC 猜测止损顺序。

## 主口径结果

| Run | Return | Annual factor | MaxDD | Sharpe | Trades | Win rate | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| K1 net | -51.71% | 0.530x | -68.32% | -0.98 | 165 | 31.52% | 0.814 |
| K2 entry delay | -51.10% | 0.535x | -66.94% | -1.01 | 165 | 32.12% | 0.815 |
| K1 zero fee/slippage | -23.55% | 0.791x | -58.16% | -0.20 | 165 | 36.97% | 0.974 |
| Buy & hold 1x net | +83.74% | - | - | - | 1 | - | - |

策略相对 buy-and-hold 的 full excess return 为
`-135.44` 个百分点。这只是方向 beta
对照，不替代结构化 OOS。

## 连续时间拆分

| Split | Start | End | Return | MaxDD | Trades |
| --- | --- | --- | ---: | ---: | ---: |
| development | 2025-05-31T07:00:00+00:00 | 2025-12-26T06:15:00+00:00 | -58.33% | -59.73% | 81 |
| validation | 2025-12-26T06:30:00+00:00 | 2026-04-09T18:00:00+00:00 | -1.79% | -34.12% | 43 |
| test | 2026-04-09T18:15:00+00:00 | 2026-07-23T05:45:00+00:00 | +18.01% | -24.38% | 41 |

## 最近切片

切片锚定本周期最后一个完整 bar 的执行终点，只用于审计。

| Window | Return | MaxDD | Closed trades |
| --- | ---: | ---: | ---: |
| 1d | -0.59% | -3.53% | 1 |
| 7d | +1.27% | -3.53% | 3 |
| 1m | +2.91% | -8.77% | 9 |
| 3m | +20.55% | -24.38% | 34 |
| 6m | +41.00% | -34.12% | 72 |
| 1y | -44.97% | -62.81% | 148 |

## 信号事件研究

固定在信号后下一周期 open 入场，并在第 `h` 根后 open 退出；net 已扣双边
手续费与滑点，不含 funding。bootstrap 为 2,000 次信号抽样均值的
`5% / 95%` 分位。

| Horizon bars | Events | Gross mean | Net mean | Net median | Net win rate | Bootstrap mean p05/p95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 169 | +0.03% | -0.25% | -0.27% | 38.5% | -0.37% / -0.12% |
| 2 | 169 | -0.02% | -0.30% | -0.27% | 39.6% | -0.48% / -0.12% |
| 4 | 169 | -0.01% | -0.29% | -0.44% | 42.0% | -0.54% / -0.03% |
| 8 | 169 | -0.15% | -0.43% | -0.20% | 45.6% | -0.81% / -0.03% |
| 16 | 169 | -0.06% | -0.34% | +0.06% | 50.3% | -0.90% / +0.20% |

## 有效性判定

- 最低可行性门槛：full return `> 0`、MaxDD 不差于 `-35%`、至少 `30`
  笔闭合交易、development/validation/test、最近 `3m/6m` 均为正。
- 门槛结果：`4/8`，总体
  `FAIL`。
- 这不是 promotion review：未做消融、CPCV、Monte Carlo、真实 1m 相位扫描、
  拒单/断流/重启/kill-switch 或 runner parity，因此无论收益如何都保持
  `explore / not promoted / not live-ready`。

## 证据

- [汇总 JSON](../artifacts/hype-1h-bksb-baseline-2026-07-23-summary.json)
- [逐笔交易](../artifacts/hype-1h-bksb-baseline-2026-07-23-trades.csv)
- [权益曲线](../artifacts/hype-1h-bksb-baseline-2026-07-23-equity.csv)
- [事件路径](../artifacts/hype-1h-bksb-baseline-2026-07-23-event-study.csv)
- [消费方脚本](../scripts/run_baseline.py)
