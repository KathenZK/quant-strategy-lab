# HYPE-1D-MA7-ABT-V7 固定 2x 杠杆诊断

## 结论

固定 `2x` 在已暴露432日主相位把 V7 的成本后收益从 `+711.05%` 放大到 `+4,550.71%`，真实顺序 `1h` MDD 从 `-18.39%` 扩大到 `-31.51%`。主相位小时 open / funding 顺序未出现权益归零，简化 maintenance-margin `0.5%/1%/2.5%/5%` 筛查也未触发。

裁决为 **`HISTORICAL_SCREEN_ONLY / diagnostic-only / not promoted / not live-ready`**。V7 默认仍是 `1x` 注册版本；本结果不解锁杠杆、不创建 live spec、不推进 runner，也不改变 clean prospective 要求。

## 冻结口径

- 市场：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`；保护与风险顺序使用真实 `1h`。
- 数据：`2025-05-31` 至 `2026-08-05 UTC`，432 个完整日；10,390 根连续 closed `1h`，2,597 个真实 funding 事件，质量 blocker 为0。
- 成本：手续费 `0.001/fill`、不利滑点 `4 bps/fill`，压力为 `8 bps/fill`。
- 杠杆：每次自然、forced reversal 或 PEHC handoff 真实入场按成本后权益目标 `2x`；数量固定到退出，不逐日再平衡，因此持仓中 marked leverage 可漂过 `2x`。
- V7 的20笔交易、入退场时点、退出原因与 handoff 事件均与 `1x` 逐笔相同；只有数量、成本、funding 与权益路径改变。

## 主结果

| 指标 | V7 1x | Fixed 2x |
| --- | ---: | ---: |
| 成本后收益 | `+711.05%` | `+4,550.71%` |
| 折算年化 | `+486.22%` | `+2,463.89%` |
| 真实顺序 1h MDD | `-18.39%` | `-31.51%` |
| 日内极值 MDD | `-20.27%` | `-34.43%` |
| Sharpe | `3.255` | `3.398` |
| Profit Factor | `17.509` | `19.425` |
| 胜率 | `85.00%` | `85.00%` |
| 交易数（long / short） | `20 (10 / 10)` | `20 (10 / 10)` |
| 最大 intraday leverage | `1.11x` | `2.34x` |
| 最大 marked leverage | `1.17x` | `2.56x` |
| 成本 / 初始权益 | `16.73%` | `106.93%` |
| funding / 初始权益 | `-1.35%` | `-14.62%` |

funding 为负表示按账本符号净收取，但它不是主收益来源：funding-off 为 `+4,597.27% / -31.59%`。`8 bps` 压力为 `+4,415.88% / -31.72%`。

## 稳健性与近期切片

- 额外一日 signal lag：`+927.44% / -47.30%`，22笔；收益仍为正，但回撤明显扩大。
- 8个54日 cold-flat block：`8/8`盈利、0个归零，独立复利 `+4,876.63%`，最差块 MDD `-31.48%`。
- 13个90日、步长30日窗口：`13/13`盈利、0个归零，最差 MDD `-31.51%`；重叠窗口的复利不作经济解释。
- 24个日界相位：`21/24`盈利，中位收益 `+89.51%`，最差收益 `-47.45%`，最差 MDD `-87.02%`，最大 marked leverage `3.11x`。

| 最近切片 | 2x 收益 | 1h MDD | 平仓 |
| --- | ---: | ---: | ---: |
| `1d` | `0.00%` | `0.00%` | 0 |
| `7d` | `0.00%` | `0.00%` | 0 |
| `1m` | `+12.30%` | `-16.05%` | 1 |
| `3m` | `+170.15%` | `-23.93%` | 4 |
| `6m` | `+285.79%` | `-31.51%` | 6 |
| `1y` | `+1,970.76%` | `-31.51%` | 16 |

近期切片只作审计，没有用于选择 V7 或杠杆。

## 风险解释

主相位 `2x` 未触发简化 liquidation/maintenance 筛查，minimum marked margin ratio 为 `0.3913`，并通过 `35%/40%/50%` MDD 预算，但未通过 `20%/25%/30%`预算。这仍不是 Binance 真实强平模拟：没有分层 maintenance tier、强平手续费与完整 intrahour liquidation path。

更关键的是相位尾部：同一 V7 规则在不同日界聚合下，固定 `2x` 最差 MDD 达 `-87.02%`。所以它只能说明“已暴露主相位历史上未爆、复利很强”，不能说明 `2x` 可上线、可默认使用或可替代 `1x` 注册身份。

## 治理记录

用户于 2026-08-11 明确要求查看 V7 的 `2x` 表现，因此本轮作为一次 researcher-exposed diagnostic observation 执行。偏差不修改原门禁：V7 仍须等待 clean prospective，且本次结果不得用于解锁或选择杠杆。

## 证据

- [首次运行前冻结合同](../specs/hype-1d-ma7-abt-v7-2x-leverage-contract-2026-08-11.md)
- [完整机器证据](../artifacts/hype_1d_ma7_abt_v7_2x_leverage_2026-08-11.json)
- [机器证据 SHA256](../artifacts/hype_1d_ma7_abt_v7_2x_leverage_2026-08-11.json.sha256)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v7_2x_leverage.py)
