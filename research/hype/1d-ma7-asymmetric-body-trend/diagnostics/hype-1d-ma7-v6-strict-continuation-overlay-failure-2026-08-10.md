# HYPE-1D-MA7-ABT-V6 严格连续趋势 Overlay 失败复盘

## 裁决

本轮裁决为 **`HARD-GATE-FAILED / diagnostic-only / not promoted / not live-ready`**。

把“非 ML 三门放行器”落成一套严格规则后，结果明显劣于 exact V6：收益从
`+617.11%`降至`+255.26%`，真实 `1h` MDD 从`-18.39%`扩大至`-32.65%`，
交易数从19笔增至24笔。该规则不修改 V6，不登记 V7，不研究杠杆，不生成交易路径 HTML。

## 执行规则

本轮只允许 V6 原生入场未触发时的 raw MA7 cross 进入观察，随后必须同时满足：

1. 趋势延续门：至少3个完整日持续位于MA7同侧，`2d` MA7 slope / ATR `>=0.04`，
   距MA7在`[0.25,1.00]ATR`内，`ER5>=0.35`；
2. MAE门：从raw cross close到确认日close的最差反向变动不超过`0.75ATR`；
3. 机会成本门：不得削弱 V6 的 `long_mfe`、`short_rsi`、`shadow_start` 或
   `handoff_accept` 核心链条。

V6原生信号和PEHC永远优先；相反cross、穿回MA7、非有限数据或超过`5d`未确认即取消。

## 主结果

| 口径 | 收益 | 真实 `1h` MDD | 平仓 | 多/空 | PF | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| exact V6 | `+617.11%` | `-18.39%` | 19 | `10 / 9` | `12.878` | `84.21%` |
| 严格Overlay | `+255.26%` | `-32.65%` | 24 | `7 / 17` | `3.031` | `62.50%` |

候选侧共出现27次raw cross，确认10次，其中long 1次、short 9次；另有74次未通过严格门。
规则确实压掉了大量候选，但剩下的short仍然过多，且质量不足以支付单仓机会成本。

## 机会成本

严格Overlay新增12笔、删除/替换7笔V6交易。核心链条变化为：

- `handoff_accept`：`-2`
- `long_trail_exit`：`-3`
- `shadow_start`：`-3`
- `short_rsi_exit`：`0`

最关键的是，它删除了多笔V6高价值路径，包括2026-03-01至2026-03-21的long
`+26.16%`、2026-07-12至2026-08-01的PEHC short `+21.15%`，却新增了多笔亏损short：
2026-02-11 short `-10.59%`、2026-02-26 short `-10.54%`、2026-06-25 short `-4.89%`等。

这说明“确认后的连续趋势”仍然不是独立收益腿；它会改变 V6 的复利基数、cooldown 和
PEHC链条。

## 压力与分块

- `8 bps`压力仍双劣：相对V6收益少`358.14pp`，MDD多`14.30pp`。
- funding-off仍双劣：相对V6收益少`371.32pp`，MDD多`14.30pp`。
- 额外一日signal lag下，候选为`+92.87% / -32.24%`，弱于同口径V6。
- `8 × 54d` cold-flat复合从V6的`+689.87%`降至`+268.48%`，最差块MDD从
  `-16.42%`扩大至`-23.10%`。
- 最近`1d/7d`无交易；最近`1m`为`+17.20%/-8.33%`，但不改变全窗失败。

## 机制结论

这套严格规则不是因为“太宽”失败，而是因为它确认到的机会本身仍然与 V6 原路径冲突。
提高趋势确认门槛可以减少噪声，但不能自动解决单仓机会成本。尤其在本样本中，short
确认过多，会抢掉后续long、shadow和handoff。

因此当前结论更明确：在这432日上，继续靠MA7同侧持续、斜率、ER和距离阈值修补连续
趋势，会把局部视觉趋势补入转化为组合层劣化。后续不应在同一历史上继续调这些阈值；
若继续研究，只能换成新增前瞻或跨资产/更长历史，并先证明机会成本标签可迁移。

## 证据

- [严格Overlay合同](../specs/hype-1d-ma7-v6-strict-continuation-overlay-contract-2026-08-10.md)
- [完整机器证据](../artifacts/hype_1d_ma7_v6_strict_continuation_overlay_2026-08-10.json)
- [严格Overlay引擎](../scripts/hype_1d_ma7_v6_strict_continuation_overlay_engine.py)
- [审计脚本](../scripts/research_hype_1d_ma7_v6_strict_continuation_overlay.py)
