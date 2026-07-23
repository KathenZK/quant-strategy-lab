# HYPE-4H-Bollinger-Keltner-Squeeze-Breakout 基础策略诊断（2026-07-23）

## 结论

`4h` 基础规则未通过本轮最低可行性门槛，门槛为
`1/8`。主口径净收益
`-41.52%`，MaxDD
`-53.97%`，闭合交易
`45` 笔，胜率
`42.22%`，profit factor
`0.640`。失败检查：
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
- 本周期：`2025-05-30T12:00:00+00:00` 至 `2026-07-23T00:00:00+00:00`，
  `2512` 根完整 `4h` K 线；
  丢弃不完整首尾桶 `2`，聚合 blocker
  `0`。
- 高周期信号由完整 UTC 桶构建；实际止损、mark-to-market 与 funding 仍在真实
  15m 子柱执行，未用高周期 OHLC 猜测止损顺序。

## 主口径结果

| Run | Return | Annual factor | MaxDD | Sharpe | Trades | Win rate | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| K1 net | -41.52% | 0.624x | -53.97% | -0.50 | 45 | 42.22% | 0.640 |
| K2 entry delay | -46.90% | 0.573x | -55.58% | -0.68 | 45 | 42.22% | 0.540 |
| K1 zero fee/slippage | -33.71% | 0.697x | -50.36% | -0.31 | 45 | 44.44% | 0.721 |
| Buy & hold 1x net | +66.13% | - | - | - | 1 | - | - |

策略相对 buy-and-hold 的 full excess return 为
`-107.64` 个百分点。这只是方向 beta
对照，不替代结构化 OOS。

## 连续时间拆分

| Split | Start | End | Return | MaxDD | Trades |
| --- | --- | --- | ---: | ---: | ---: |
| development | 2025-06-02T20:00:00+00:00 | 2025-12-27T11:45:00+00:00 | -28.88% | -44.98% | 19 |
| validation | 2025-12-27T12:00:00+00:00 | 2026-04-10T07:45:00+00:00 | -11.03% | -34.35% | 12 |
| test | 2026-04-10T08:00:00+00:00 | 2026-07-23T03:45:00+00:00 | -7.58% | -17.69% | 14 |

## 最近切片

切片锚定本周期最后一个完整 bar 的执行终点，只用于审计。

| Window | Return | MaxDD | Closed trades |
| --- | ---: | ---: | ---: |
| 1d | +0.00% | 0.00% | 0 |
| 7d | -3.74% | -5.24% | 1 |
| 1m | -5.31% | -16.35% | 5 |
| 3m | -8.41% | -17.67% | 13 |
| 6m | -24.46% | -32.99% | 23 |
| 1y | -28.54% | -44.24% | 40 |

## 信号事件研究

固定在信号后下一周期 open 入场，并在第 `h` 根后 open 退出；net 已扣双边
手续费与滑点，不含 funding。bootstrap 为 2,000 次信号抽样均值的
`5% / 95%` 分位。

| Horizon bars | Events | Gross mean | Net mean | Net median | Net win rate | Bootstrap mean p05/p95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 46 | +0.26% | -0.02% | -0.18% | 50.0% | -0.46% / +0.45% |
| 2 | 46 | +0.04% | -0.24% | +0.19% | 52.2% | -0.87% / +0.38% |
| 4 | 46 | +0.19% | -0.09% | +0.38% | 58.7% | -1.16% / +1.00% |
| 8 | 46 | -0.09% | -0.37% | +0.16% | 50.0% | -1.90% / +1.07% |
| 16 | 45 | +0.88% | +0.60% | +0.79% | 60.0% | -1.51% / +2.59% |

## 有效性判定

- 最低可行性门槛：full return `> 0`、MaxDD 不差于 `-35%`、至少 `30`
  笔闭合交易、development/validation/test、最近 `3m/6m` 均为正。
- 门槛结果：`1/8`，总体
  `FAIL`。
- 这不是 promotion review：未做消融、CPCV、Monte Carlo、真实 1m 相位扫描、
  拒单/断流/重启/kill-switch 或 runner parity，因此无论收益如何都保持
  `explore / not promoted / not live-ready`。

## 证据

- [汇总 JSON](../artifacts/hype-4h-bksb-baseline-2026-07-23-summary.json)
- [逐笔交易](../artifacts/hype-4h-bksb-baseline-2026-07-23-trades.csv)
- [权益曲线](../artifacts/hype-4h-bksb-baseline-2026-07-23-equity.csv)
- [事件路径](../artifacts/hype-4h-bksb-baseline-2026-07-23-event-study.csv)
- [消费方脚本](../scripts/run_baseline.py)
