# HYPE-1D-MA7-ABT-V6 固定 3x 杠杆诊断

## 结论

固定 `3x` 在已暴露 432 日主相位把 exact V6 的成本后收益从 `+617.11%`
放大到 `+14,164.73%`，但真实顺序 `1h` MDD 从 `-18.39%` 扩大到
`-45.35%`。24 个日界相位中只有 19 个盈利，最差相位收益 `-59.97%`、
MDD `-94.19%`，最大 marked leverage 达 `7.65x`。

裁决为 `HIGH_TAIL_RISK / diagnostic-only / not promoted / not live-ready`。
V6 继续固定 `1x / shadow-only`；本结果不解锁杠杆、不改变前瞻 observer，
也不登记 V7。

## 冻结口径

- 市场：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`；保护与风险顺序使用真实 `1h`。
- 数据：`2025-05-31` 至 `2026-08-05 UTC`，432 个完整日；10,390 根连续 closed `1h`，
  2,597 个真实 funding 事件，质量 blocker 为 0。
- 成本：手续费 `0.001/fill`、不利滑点 `4 bps/fill`，压力为 `8 bps/fill`。
- 杠杆：每次自然、forced reversal 或 PEHC handoff 实际入场按成本后权益目标 `3x`；
  数量固定到退出，不逐日再平衡，因此持仓中 marked leverage 可漂过 `3x`。
- V6 的 19 笔交易、入退场时点、退出原因与 6 次 handoff opportunity / 5 次接受均与
  `1x` 逐笔相同；只有数量、成本、funding 与权益路径改变。

## 主结果

| 指标 | Exact V6 1x | Fixed 3x |
| --- | ---: | ---: |
| 成本后收益 | `+617.11%` | `+14,164.73%` |
| 折算年化 | `+428.31%` | `+6,509.27%` |
| 真实顺序 1h MDD | `-18.39%` | `-45.35%` |
| 日内极值 MDD | `-20.27%` | `-47.16%` |
| Sharpe | `3.207` | `3.393` |
| Profit Factor | `12.878` | `15.785` |
| 胜率 | `84.21%` | `84.21%` |
| 交易数（long / short） | `19 (10 / 9)` | `19 (10 / 9)` |
| 最大 intraday leverage | `1.11x` | `4.11x` |
| 最大 marked leverage | `1.20x` | `4.45x` |
| 成本 / 初始权益 | `15.04%` | `351.96%` |
| funding / 初始权益 | `-0.55%` | `-45.85%` |

funding 为负表示按账本符号净收取，但它不是主收益来源：funding-off 仍为
`+14,488.04% / -44.85%`。`8 bps` 压力为 `+13,591.22% / -45.35%`。

## 稳健性与近期切片

- 额外一日 signal lag：`+532.64% / -70.50%`，20 笔；收益相对主路径几乎被抹去，
  且回撤明显扩大。
- 8 个 54 日 cold-flat block：`8/8` 盈利、0 个归零，独立复利 `+20,114.19%`，
  最差块 MDD `-45.35%`。
- 13 个 90 日、步长 30 日窗口：`13/13` 盈利、0 个归零，最差 MDD `-45.35%`；
  重叠窗口的复利不作经济解释。
- 24 个日界相位：`19/24` 盈利，中位收益 `+105.05%`，最差收益 `-59.97%`，
  最差 MDD `-94.19%`，最大 marked leverage `7.65x`。

| 最近切片 | 3x 收益 | 1h MDD | 平仓 |
| --- | ---: | ---: | ---: |
| `1d` | `0.00%` | `0.00%` | 0 |
| `7d` | `0.00%` | `0.00%` | 0 |
| `1m` | `+18.42%` | `-21.52%` | 1 |
| `3m` | `+298.00%` | `-34.14%` | 4 |
| `6m` | `+543.56%` | `-42.00%` | 6 |
| `1y` | `+4,435.02%` | `-45.35%` | 15 |

近期切片只作审计，没有用于选择 V6 或杠杆。

## 风险解释

主相位在小时 open、funding 与引擎日内极值检查中没有权益归零；按 marked equity /
notional 做 `0.5%/1%/2.5%/5%` maintenance 敏感性也没有触发。但这不是 Binance
真实强平模拟：没有分层 maintenance tier、强平手续费与完整 intrahour liquidation
路径。主相位 MDD 只通过 `50%` 预算，未通过 `20%–40%` 预算；相位最差 MDD
已接近归零，因此不能把“主相位未强平”解释成可上线。

此外，`+14,164.73%` 是对已多轮研究过的 432 日历史做固定风险放大后的复利结果，
不是新 alpha，也不是 clean OOS。收益数字高度依赖 V6 已知赢家顺序；额外一日延迟和
日界相位已经显示尾部风险远高于主相位点估计。

## 治理记录

V6 规格与 PEHC 原预注册合同原本锁定“`1x` clean prospective PASS 前不运行杠杆”。
用户于 2026-08-10 明确要求查看当前 V6 的 `3x` 表现，因此本轮作为一次明确偏差的
researcher-exposed diagnostic observation 执行。偏差不修改原门禁：V6 仍须先完成
至少 90 日 clean prospective，且本次结果不得用于解锁或选择杠杆。

## 证据

- [首次运行前冻结合同](../specs/hype-1d-ma7-abt-v6-3x-leverage-contract-2026-08-10.md)
- [完整机器证据](../artifacts/hype_1d_ma7_abt_v6_3x_leverage_2026-08-10.json)
- [固定 3x 与 exact V6 1x 完整交易路径](../artifacts/hype_1d_ma7_abt_v6_3x_leverage_trade_path_2026-08-10.html)
- [交易路径审计 manifest](../artifacts/hype_1d_ma7_abt_v6_3x_leverage_trade_path_2026-08-10_manifest.json)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v6_3x_leverage.py)
- [HTML 生成器](../scripts/render_hype_1d_ma7_abt_v6_3x_leverage.py)
