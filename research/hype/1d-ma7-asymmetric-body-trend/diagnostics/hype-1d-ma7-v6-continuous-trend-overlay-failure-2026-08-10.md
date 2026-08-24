# HYPE-1D-MA7-ABT-V6 连续趋势 Overlay 失败复盘

## 裁决

本轮裁决为 **`HARD-GATE-FAILED / diagnostic-only / not promoted / not live-ready`**。

四个冻结 overlay 候选均未通过。方向识别本身不是完全失败：`CTO_L189` 的唯一 long
确认命中，`CTO_L189_S005` 的 13 个可评估确认中 10 个命中。但把这些确认接入
exact V6 后，完整经济路径没有同时提高收益并降低真实 `1h` MDD。

因此不修改 V6，不登记 V7，不研究杠杆，不生成交易路径 HTML。

## 冻结口径

- Control：exact V6 `PEHC_294`，固定 `1x`、单仓、非加仓。
- 市场：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`；保护和回撤审计使用真实 `1h`。
- 数据窗：`2025-05-31` 至 `2026-08-05 UTC`，432 个完整日。
- 成本：手续费 `0.001/fill`、基础不利滑点 `4 bps/fill`、压力 `8 bps/fill`，计真实 funding。
- 候选：DTEC long-only `CTO_L189`、DTEC short-only `CTO_S005`、二者组合
  `CTO_L189_S005`、转换链代表候选 `CTO_C001`。

## 主结果

| 口径 | 收益 | 真实 `1h` MDD | 平仓 | 方向确认 | 裁决 |
| --- | ---: | ---: | ---: | ---: | --- |
| exact V6 | `+617.11%` | `-18.39%` | 19 | - | control |
| `CTO_L189` | `+623.48%` | `-20.97%` | 21 | `1/1` | FAIL |
| `CTO_S005` | `+242.07%` | `-26.40%` | 23 | `8/12` | FAIL |
| `CTO_L189_S005` | `+308.28%` | `-26.40%` | 25 | `10/13` | FAIL |
| `CTO_C001` | `+449.40%` | `-24.13%` | 26 | `1/1` | FAIL |

`CTO_L189` 是唯一全窗收益高于 V6 的候选，但只多 `+6.37pp`，同时 MDD 恶化
`2.58pp`，并且只有 1 个趋势确认样本；不满足“至少两个确认”和“回撤更小”两条门。

`CTO_S005` 与 `CTO_L189_S005` 的方向命中率看似可用，但组合层失败更严重：
short-only 增加 14 笔、删除/替换 10 笔 V6 交易，使 `handoff_accept` 少 2 次、
`long_trail_exit` 少 4 次、`shadow_start` 少 4 次。也就是说，它们不是给 V6 增加
独立收益腿，而是在单仓约束下破坏了原本更高价值的 long / OAPP / PEHC 链条。

`CTO_C001` 补到 transition 目标段，但收益少 `167.70pp`、MDD 多 `5.74pp`；
`shadow_start` 相对 V6 少 8 次，说明 cooldown / transition 放宽仍会显著改变 V6
的核心状态链。

## 压力与分块

- `8 bps` 压力下，四个候选全部未通过；`CTO_L189`仍小幅增收但 MDD 继续恶化，
  其余三个收益和 MDD 均双劣。
- funding-off 下，`CTO_L189`收益增量降至 `+4.95pp` 且 MDD 更差；其余三个仍双劣。
- 额外一日 signal lag 下，exact V6 为 `+135.64% / -31.06%`；四个候选均未显示
  可采纳优势。
- `8 × 54d` cold-flat block 中，没有候选满足全部不双劣门。`CTO_L189`独立复合
  `+489.04%`，低于 V6 的 `+689.87%`；`CTO_C001`复合 `+618.47%`，但最差块 MDD
  `-23.07%`，显著差于 V6 的 `-16.42%`。

最近切片未用于选择，只作审计：最近 `1d/7d` 均无交易；`1m`、`3m`、`6m` 的差异
没有改变全窗失败裁决。

## 机制评价

连续趋势 overlay 的关键失败点不是“趋势方向完全不可识别”，而是 **方向命中无法覆盖
机会成本**。V6 的收益来自稀疏高质量路径和复利基数；新增仓位即使短期方向正确，也会
占用单仓、改变 cooldown、减少 shadow 或 handoff，从而压低后续更大的 V6 交易链。

这次结果支持三个判断：

1. `long` 延迟趋势补入目前只有单样本证据，不能作为新机制；
2. `short` 连续趋势识别有一定方向信息，但在单仓组合里会牺牲 V6 的高价值 long /
   PEHC 机会；
3. 继续在同一 432 日上调 DTEC、cooldown、episode 或 anti-chase 阈值，容易把“局部
   视觉趋势补到了”误写成“策略变好了”。

## 决定

- 不修改 `HYPE-1D-MA7-Asymmetric-Body-Trend-V6`；
- 不登记 V7；
- 不研究固定或动态杠杆；
- 不生成交互式交易路径 HTML；
- 同一 432 日停止继续救援这些 overlay 阈值。

后续若继续做连续趋势，只能等待从 `2026-08-11` 起的 clean prospective，或另立跨资产 /
更长历史合同，并把“候选方向收益”与“单仓机会成本”同时作为冻结标签。

## 证据

- [连续趋势 overlay 合同](../specs/hype-1d-ma7-v6-continuous-trend-overlay-contract-2026-08-10.md)
- [完整机器证据](../artifacts/hype_1d_ma7_v6_continuous_trend_overlay_2026-08-10.json)
- [审计脚本](../scripts/research_hype_1d_ma7_v6_continuous_trend_overlay.py)
- [DTEC 引擎](../scripts/hype_1d_ma7_v6_delayed_episode_engine.py)
- [转换链引擎](../scripts/hype_1d_ma7_v6_transition_repair_engine.py)
