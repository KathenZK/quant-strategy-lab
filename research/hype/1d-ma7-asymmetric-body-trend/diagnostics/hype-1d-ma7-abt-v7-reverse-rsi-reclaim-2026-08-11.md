# HYPE-1D-MA7-ABT-V7 Reverse-K RSI Reclaim 诊断

## 结论

用户提出的“突破 MA7 当天，如果前10天一半/60%以上是反向K，且过去10天 RSI6 出现过 `30/70` 极值，则允许开单”已经回测。该规则确实能命中 `2025-08-07`、`2026-02-06`、`2026-04-04` 这些 raw cross 起点，但全窗结果仍为 **`FAIL / diagnostic-only / not promoted / not live-ready`**。

54个候选没有一个全窗双优。最高收益候选是 short-only 满仓版本，只有 `+351.06%/-23.72%`，远低于 V7 的 `+711.04%/-18.40%`。

## 冻结口径

- Control：`CTRL_EXACT_V7`。
- 机制：V7 原生 entry 优先；只有原生 V7 不识别时，raw MA7 cross 当天才检查反向K占比与 RSI6 极值。
- 网格：`side_scope` 3档 × `reverse_ratio` 2档 × `max_distance_atr` 3档 × `target_leverage` 3档，共54个候选。
- 成本：手续费 `0.001/fill`、基础滑点 `4 bps/fill`、压力滑点 `8 bps/fill`，计真实 Binance funding；风险 replay 为真实 `1h` 顺序。

## Top 结果

| Candidate | 机制 | 全窗收益 | 真实1h MDD | 交易数 | 触发数 | 裁决 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `CTRL_EXACT_V7` | V7 control | `+711.04%` | `-18.40%` | 20 | 0 | `CONTROL` |
| `RK_short_only_R0p50_D1p00_L1p00` | short-only，50%，距离<=1ATR，满仓 | `+351.06%` | `-23.72%` | 23 | 11 | `FAIL` |
| `RK_short_only_R0p60_D1p00_L1p00` | short-only，60%，距离<=1ATR，满仓 | `+339.15%` | `-23.72%` | 22 | 10 | `FAIL` |
| `RK_short_only_R0p50_D1p50_L1p00` | short-only，50%，距离<=1.5ATR，满仓 | `+331.28%` | `-27.07%` | 24 | 12 | `FAIL` |
| `RK_short_only_R0p50_D1p00_L0p50` | short-only，50%，距离<=1ATR，0.5x | `+323.37%` | `-18.09%` | 23 | 11 | `FAIL` |

最高候选完整压力：`8 bps` 为 `+343.10%/-23.98%`，额外 `1d lag` 为 `+130.54%/-26.45%`，8个block中只有7个正收益。它不是候选，只是失败诊断。

## 目标行情

该规则确实捕捉到用户点名的 raw cross 起点：

- `2025-08-07` long：前10日反向K `7/10`，`min RSI6=15.87`，distance `0.79 ATR`。
- `2026-02-06` short：前10日反向K `5/10`，`max RSI6=86.31`，distance `0.06 ATR`。
- `2026-04-04` long：前10日反向K `8/10`，`min RSI6=25.42`，distance `0.01 ATR`。

但 both 方向版本会同时触发大量同型事件。比如 `RK_both_R0p50_D1p50_L0p25` 有21次触发，结果只有 `+68.68%/-33.81%`、31笔；说明这个条件不是“目标三段专用”，而是一个很宽的 exhaustion/reclaim 模式，会把许多低质量反弹/反转也带进来。

## 解释

这条规则比 stale reclaim 更接近用户想抓的三段行情，因为它在 raw cross 当天就判断“前面是否已经极端反向”。但它失败的原因也很清楚：`10日反向K占比 + RSI6 30/70` 在 HYPE 这段历史里太常见，不足以区分“趋势真正开始”与“极端后的普通反抽/假跌破”。

下一步如果还要继续攻这个方向，不能只加价格K线和 RSI 极值，至少要再引入一个质量维度，例如 breakout day 的真实实体/成交量、突破后首日 follow-through、或更高周期结构确认。否则它会继续补到痛点，也继续放噪声。

## 证据

- [冻结合同](../specs/hype-1d-ma7-abt-v7-reverse-rsi-reclaim-contract-2026-08-11.md)
- [完整机器证据](../artifacts/hype_1d_ma7_abt_v7_reverse_rsi_reclaim_2026-08-11.json)
- [机器证据 SHA256](../artifacts/hype_1d_ma7_abt_v7_reverse_rsi_reclaim_2026-08-11.json.sha256)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v7_reverse_rsi_reclaim.py)
