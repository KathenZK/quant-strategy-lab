# HYPE-1D-MA7-ABT-V7 问题与优化方向综合诊断

## 结论

把前面提出的 V7 问题和优化方向落地回测后，结论是：**当前没有一个优化方向足以替代 V7 或登记 V8**。

- Delayed impulse confirmation 能识别 `2026-04-07` 这类迟到趋势，但最佳候选只把收益从 `+711.04%` 提到 `+718.20%`，真实 `1h` MDD 从 `-18.40%` 恶化到 `-20.98%`，裁决 `FAIL / higher-return-higher-risk`。
- 空头 max_hold 延长没有吃到更多有效趋势，反而把 `2026-07-12` 空头从 `+21.15%` 降到 `+19.06%`，全窗降至 `+697.06%`，裁决 `FAIL`。
- 禁用 PEHC entry 全窗降至 `+512.12%/-21.57%`，说明 PEHC 总体净贡献为正，但仍有局部噪声。
- 空头 slope exit 放松已单独测试：收益降至 `+432.55%~+574.59%`，路径被更早的 `2025-10-15` 空头破坏，裁决 `FAIL / path-disruption`。

因此当前判断维持：V7 仍是 `registered / not promoted / not live-ready`。问题确实存在，但简单补票、延长持仓、放松退出或禁用 PEHC 都不能形成更优版本。

## A. Delayed Impulse Confirmation

固定网格：reverse-K + RSI extreme tag 后，在 `1-4d` 内要求同向实体 impulse；共144个候选。

| Candidate | 全窗收益 | 真实1h MDD | 交易数 | tag/confirm | 裁决 |
| --- | ---: | ---: | ---: | ---: | --- |
| `CTRL_EXACT_V7` | `+711.04%` | `-18.40%` | 20 | 0/0 | `CONTROL` |
| `DI_both_P200p45_B2p50_R0p55_G0p50_L1p00` | `+718.20%` | `-20.98%` | 22 | 14/1 | `FAIL / higher-return-higher-risk` |
| 同参数族其他顶部候选 | `+718.20%` | `-20.98%` | 22 | 6-14/1 | `FAIL / higher-return-higher-risk` |

顶部候选只确认一次：

- `2026-04-04` 打 tag；
- `2026-04-07` 出现 impulse confirm；
- `2026-04-08` 开多，`2026-04-20` protective stop 出，单笔 `+5.51%`；
- 随后同日带出一笔 `2026-04-20 → 2026-04-27` 空单，`-4.38%`。

它没有确认 `2025-08-07` 或 `2026-02-06/09/10`。这证明 delayed impulse 特征确实能解释 `2026-04`，但不是通用补漏器。

## B. Short Max-Hold Trend Extension

测试到达空头 `max_hold=20` 时，若 `close < MA7` 且 MA7 仍下降，则延长5/10日，可选要求至少低于 MA7 `0.25ATR`。

| Variant | 全窗收益 | 真实1h MDD | 交易数 | `2026-07-12` 空单 | 裁决 |
| --- | ---: | ---: | ---: | --- | --- |
| `CTRL_EXACT_V7` | `+711.04%` | `-18.40%` | 20 | `2026-07-12 → 2026-08-01`，`+21.15%` | `CONTROL` |
| `SHORT_MAXHOLD_EXTEND_5` | `+697.06%` | `-18.40%` | 20 | `2026-07-12 → 2026-08-04`，`+19.06%` | `FAIL` |
| `SHORT_MAXHOLD_EXTEND_10` | `+697.06%` | `-18.40%` | 20 | 同上 | `FAIL` |
| `SHORT_MAXHOLD_EXTEND_5_D0P25` | `+697.06%` | `-18.40%` | 20 | 同上 | `FAIL` |
| `SHORT_MAXHOLD_EXTEND_10_D0P25` | `+697.06%` | `-18.40%` | 20 | 同上 | `FAIL` |

`2026-07-12` 原本在 `2026-08-01` 已接近较优退出；延长到 `2026-08-04` 反而遇到反弹，少赚约 `2.09pp`。所以“7月趋势没吃完整”的直觉不成立，至少在这个 frozen 口径下不是优化空间。

## C. PEHC Entry Contribution

| Variant | 全窗收益 | 真实1h MDD | 交易数 | 裁决 |
| --- | ---: | ---: | ---: | --- |
| `CTRL_EXACT_V7` | `+711.04%` | `-18.40%` | 20 | `CONTROL` |
| `PEHC_ENTRY_DISABLED` | `+512.12%` | `-21.57%` | 18 | `FAIL / path-disruption` |

禁用 PEHC entry 后收益下降 `198.92pp`，MDD 恶化 `3.17pp`。这说明 PEHC 的总体贡献为正，不能因为 `2026-03-23` 这类短促失败就直接移除。

更合理的后续方向不是“禁用 PEHC”，而是局部过滤特定 handoff：例如利润退出后，如果反手方向的 MA7 斜率刚好走平、价格没有形成同向实体推进，才降低或跳过 handoff。

## D. Short Slope Exit

独立诊断已测试：

- `slope_exit_lookback=2/3`；
- `MA7上拐 + close > MA7`；
- `MA7上拐 + close > MA7 + 0.25/0.50/0.75ATR`。

全部失败。最好的 `SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA` 只有 `+574.59%/-18.40%`；`0.75ATR` 版本降到 `+432.55%/-19.98%`。

失败原因不是单笔 `2025-11-03` 没修好，而是更早的 `2025-10-15` 空头被拖到 `2025-10-24` 亏损退出，错过原始路径的 `2025-10-24 → 2025-11-01` 多头，随后 `2025-11-03` 空头也不再以同样路径出现。

## 策略判断

1. **V7 的强项是真的**：PEHC、OAPP、short cooldown 和原始空头退出组合在全路径上有协同；简单移除或慢化通常破坏路径。
2. **V7 的弱点也是真的**：它不是完整趋势识别器，对迟到趋势没有稳定补票能力。
3. **当前可优化空间很窄**：单独改 entry、max_hold、PEHC、slope exit 都没有产生双优版本。
4. **下一步不应继续大网格乱扫**：更合理的是把 V7 保持不变，同时把 delayed impulse 或 PEHC 局部过滤作为 clean prospective observer，等未来样本验证。

## 证据

- [综合诊断合同](../specs/hype-1d-ma7-abt-v7-issue-optimization-omnibus-contract-2026-08-11.md)
- [Delayed impulse 机器证据](../artifacts/hype_1d_ma7_abt_v7_delayed_impulse_confirmation_2026-08-11.json)
- [Delayed impulse SHA256](../artifacts/hype_1d_ma7_abt_v7_delayed_impulse_confirmation_2026-08-11.json.sha256)
- [State control 机器证据](../artifacts/hype_1d_ma7_abt_v7_state_control_variants_2026-08-11.json)
- [State control SHA256](../artifacts/hype_1d_ma7_abt_v7_state_control_variants_2026-08-11.json.sha256)
- [Short slope exit 诊断](hype-1d-ma7-abt-v7-short-slope-exit-variants-2026-08-11.md)
- [Delayed impulse 脚本](../scripts/audit_hype_1d_ma7_abt_v7_delayed_impulse_confirmation.py)
- [State control 脚本](../scripts/audit_hype_1d_ma7_abt_v7_state_control_variants.py)
