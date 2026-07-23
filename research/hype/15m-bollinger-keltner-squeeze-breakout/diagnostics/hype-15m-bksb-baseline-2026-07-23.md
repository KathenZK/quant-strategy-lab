# HYPE-15M-Bollinger-Keltner-Squeeze-Breakout 基础策略诊断（2026-07-23）

## 结论

`15m` 基础规则未通过本轮最低可行性门槛，门槛为
`1/8`。主口径净收益
`-93.16%`，MaxDD
`-94.31%`，闭合交易
`641` 笔，胜率
`28.08%`，profit factor
`0.570`。失败检查：
`full_return_positive, max_drawdown_not_worse_than_35pct, development_positive, validation_positive, test_positive, recent_3m_positive, recent_6m_positive`。

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
- 本周期：`2025-05-30T10:30:00+00:00` 至 `2026-07-23T05:45:00+00:00`，
  `40206` 根完整 `15m` K 线；
  丢弃不完整首尾桶 `0`，聚合 blocker
  `0`。
- 高周期信号由完整 UTC 桶构建；实际止损、mark-to-market 与 funding 仍在真实
  15m 子柱执行，未用高周期 OHLC 猜测止损顺序。

## 主口径结果

| Run | Return | Annual factor | MaxDD | Sharpe | Trades | Win rate | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| K1 net | -93.16% | 0.096x | -94.31% | -4.15 | 641 | 28.08% | 0.570 |
| K2 entry delay | -91.51% | 0.116x | -93.03% | -4.24 | 641 | 26.83% | 0.574 |
| K1 zero fee/slippage | -58.64% | 0.463x | -72.95% | -1.20 | 641 | 34.17% | 0.837 |
| Buy & hold 1x net | +79.32% | - | - | - | 1 | - | - |

策略相对 buy-and-hold 的 full excess return 为
`-172.48` 个百分点。这只是方向 beta
对照，不替代结构化 OOS。

## 连续时间拆分

| Split | Start | End | Return | MaxDD | Trades |
| --- | --- | --- | ---: | ---: | ---: |
| development | 2025-05-30T15:30:00+00:00 | 2025-12-25T22:30:00+00:00 | -81.93% | -84.06% | 326 |
| validation | 2025-12-25T22:45:00+00:00 | 2026-04-09T14:00:00+00:00 | -47.32% | -51.05% | 152 |
| test | 2026-04-09T14:15:00+00:00 | 2026-07-23T05:45:00+00:00 | -28.17% | -33.42% | 163 |

## 最近切片

切片锚定本周期最后一个完整 bar 的执行终点，只用于审计。

| Window | Return | MaxDD | Closed trades |
| --- | ---: | ---: | ---: |
| 1d | +0.03% | -2.01% | 2 |
| 7d | +5.51% | -4.78% | 12 |
| 1m | -12.16% | -17.63% | 49 |
| 3m | -18.21% | -33.42% | 136 |
| 6m | -57.51% | -63.57% | 271 |
| 1y | -90.56% | -91.50% | 562 |

## 信号事件研究

固定在信号后下一周期 open 入场，并在第 `h` 根后 open 退出；net 已扣双边
手续费与滑点，不含 funding。bootstrap 为 2,000 次信号抽样均值的
`5% / 95%` 分位。

| Horizon bars | Events | Gross mean | Net mean | Net median | Net win rate | Bootstrap mean p05/p95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 652 | -0.00% | -0.28% | -0.34% | 24.2% | -0.33% / -0.24% |
| 2 | 652 | -0.05% | -0.33% | -0.36% | 27.5% | -0.39% / -0.26% |
| 4 | 652 | -0.03% | -0.31% | -0.36% | 32.8% | -0.38% / -0.24% |
| 8 | 652 | -0.04% | -0.32% | -0.37% | 37.0% | -0.41% / -0.22% |
| 16 | 652 | -0.05% | -0.33% | -0.40% | 41.9% | -0.47% / -0.19% |

## 有效性判定

- 最低可行性门槛：full return `> 0`、MaxDD 不差于 `-35%`、至少 `30`
  笔闭合交易、development/validation/test、最近 `3m/6m` 均为正。
- 门槛结果：`1/8`，总体
  `FAIL`。
- 这不是 promotion review：未做消融、CPCV、Monte Carlo、真实 1m 相位扫描、
  拒单/断流/重启/kill-switch 或 runner parity，因此无论收益如何都保持
  `explore / not promoted / not live-ready`。

## 证据

- [汇总 JSON](../artifacts/hype-15m-bksb-baseline-2026-07-23-summary.json)
- [逐笔交易](../artifacts/hype-15m-bksb-baseline-2026-07-23-trades.csv)
- [权益曲线](../artifacts/hype-15m-bksb-baseline-2026-07-23-equity.csv)
- [事件路径](../artifacts/hype-15m-bksb-baseline-2026-07-23-event-study.csv)
- [消费方脚本](../scripts/run_baseline.py)
