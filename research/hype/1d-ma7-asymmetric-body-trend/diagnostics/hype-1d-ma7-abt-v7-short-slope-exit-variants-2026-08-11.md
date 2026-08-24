# HYPE-1D-MA7-ABT-V7 Short Slope Exit Variants 诊断

## 结论

按用户要求测试三类空头 `ma7_slope_exit` 放松规则：`2/3日斜率不利才退`、`MA7上拐 + close > MA7`、`MA7上拐 + close > MA7 + ATR buffer`。全部 **FAIL / diagnostic-only**。

这些变体没有把 `2025-11-03` 空头拿得更完整；相反，它们先改变了 `2025-10-15` 空头的退出，让该空头拖到 `2025-10-24` 亏损退出，错过原始 V7 的 `2025-10-24 → 2025-11-01` 多头，随后原本的 `2025-11-03` 空头也不再以同样路径出现。`2026-07-12` 空头基本不受影响，仍持有到 `max_hold=20`。

## 固定口径

- Control：`CTRL_EXACT_V7`。
- 只修改空头 `ma7_slope_exit` 触发口径；不修改入场、V7 short cooldown、OAPP、PEHC、多头退出、保护止损、trailing、max hold、手续费、滑点或 funding。
- 成本：手续费 `0.001/fill`、基础滑点 `4 bps/fill`、压力滑点 `8 bps/fill`，计真实 Binance funding；风险 replay 为真实 `1h` 顺序。
- 本轮不登记 V8，不生成 HTML，不创建 live spec，不推进 runner。

## 全窗结果

| Variant | 全窗收益 | 真实1h MDD | 交易数 | `ma7_slope_exit` | `max_hold` | 裁决 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `CTRL_EXACT_V7` | `+711.04%` | `-18.40%` | 20 | 6 | 1 | `CONTROL` |
| `SHORT_SLOPE_LOOKBACK_2` | `+511.02%` | `-17.77%` | 18 | 3 | 1 | `FAIL / path-disruption` |
| `SHORT_SLOPE_LOOKBACK_3` | `+478.66%` | `-17.77%` | 19 | 4 | 1 | `FAIL / path-disruption` |
| `SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA` | `+574.59%` | `-18.40%` | 18 | 4 | 1 | `FAIL / path-disruption` |
| `SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA_0P25ATR` | `+569.83%` | `-17.77%` | 18 | 3 | 1 | `FAIL / path-disruption` |
| `SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA_0P50ATR` | `+486.20%` | `-18.77%` | 18 | 2 | 1 | `FAIL` |
| `SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA_0P75ATR` | `+432.55%` | `-19.98%` | 18 | 0 | 1 | `FAIL` |

## 重点交易对比

原始 V7：

- `2025-11-03` short：`2025-11-03 → 2025-11-11`，`ma7_slope_exit`，`+2.31%`。
- `2026-07-12` short：`2026-07-12 → 2026-08-01`，`max_hold`，`+21.15%`。

放松斜率退出后的主要路径变化：

- `SHORT_SLOPE_LOOKBACK_2`、`SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA`、`0.75ATR` 等代表性变体中，`2025-10-15` short 从原始 V7 的 `2025-10-19 ma7_slope_exit +6.12%` 变为 `2025-10-24 ma7_hysteresis_exit -2.22%`。
- 因为 `2025-10-24` 仍在这笔 short 里，原始 V7 的 `2025-10-24 → 2025-11-01` long 不再出现。
- 路径被改写后，`2025-11-03` short 也不再作为同一笔 trade 出现；因此这些规则并没有修复 `2025-11-03` 的 premature exit，而是提前破坏了上一段路径。
- `2026-07-12` short 在各变体中仍然 `2026-07-12 → 2026-08-01 max_hold`，单笔收益率仍约 `+21.15%`；说明这类规则并不是为了改善 7月完整趋势，7月原本就不是斜率退出瓶颈。

## 压力摘要

收益或MDD有任一改善的变体已跑压力包：

- `SHORT_SLOPE_LOOKBACK_2`：`8 bps +502.64%/-17.83%`，`lag +157.81%/-26.45%`，8个block仅7个正收益。
- `SHORT_SLOPE_LOOKBACK_3`：`8 bps +470.25%/-17.83%`，`lag +117.06%/-30.47%`，8个block仅7个正收益。
- `SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA`：`8 bps +565.37%/-18.53%`，`lag +186.47%/-26.45%`，8个block全正，但全窗收益比 V7 少 `136.45pp`。
- `SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA_0P25ATR`：`8 bps +560.68%/-17.83%`，`lag +153.94%/-30.47%`，8个block全正，但全窗收益比 V7 少 `141.20pp`。

## 裁决

本轮三类放松规则均不应进入 V7。它们证明了 `2025-11-03` 的问题不是可以通过“单纯放慢所有空头斜率退出”解决；因为同一改动会先影响更早的空头，改变后续长短切换路径。

若继续研究，应改为局部识别“单日MA7上拐但价格仍在下行结构中”的 whipsaw 过滤，而不是全局放松空头斜率退出。

## 证据

- [冻结合同](../specs/hype-1d-ma7-abt-v7-short-slope-exit-variants-contract-2026-08-11.md)
- [机器证据](../artifacts/hype_1d_ma7_abt_v7_short_slope_exit_variants_2026-08-11.json)
- [机器证据 SHA256](../artifacts/hype_1d_ma7_abt_v7_short_slope_exit_variants_2026-08-11.json.sha256)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v7_short_slope_exit_variants.py)
