# HYPE 1D MA7 广域趋势生命周期研究失败裁决

- 日期：`2026-08-10`
- 分支：`HYPE-1D-MA7-Wide-Trend-Lifecycle`（WTL）
- 状态：`Development hard-gate FAIL / no champion / H untouched / not promoted / not live-ready`
- 唯一控制：登记的 `HYPE-1D-MA7-Asymmetric-Body-Trend-V4` exact implementation，固定 `1x`
- 数据角色：`D=[0,259)` 与 `V=[269,346)` 均为 researcher-exposed Development；`H=[356,432)` 从未运行任何 WTL 候选，继续保留为唯一 one-shot 最终裁决窗

## 结论

本轮没有冻结 1x champion，也没有运行杠杆或 H。失败并非因为没有找到收益更高、回撤更小的数值路径，而是预注册的 `V candidate closed trades >= 3` 样本硬门与“盈利保护提前退出后主动避免坏反手”发生结构性冲突：`624` 个 Stage C 组合中有 `440` 个在 D、V 的收益与真实 `1h` chronological MDD 上都严格优于 exact V4，且满足 materiality、路径变化和 V 退出激活，但这些候选在 V 只留下 `1` 或 `2` 笔已平仓交易，因此全部按冻结合同失败。

该门槛不能在看到结果后放松。WTL 因而是一次方法学上诚实的 `FAIL`，不是可以事后宣称成功的候选发现。

## 冻结控制与切分

| 区域 | 索引 | 角色 | exact V4 收益 | exact V4 真实 1h MDD | exact V4 平仓数 |
| --- | ---: | --- | ---: | ---: | ---: |
| D | `[0,259)` | exposed Development | `+160.0203%` | `-21.6561%` | `10` |
| V | `[269,346)` | exposed Development | `+12.2129%` | `-18.8155%` | `3` |
| H | `[356,432)` | untouched one-shot final | 未运行 | 未运行 | 未运行 |

全窗 exact V4 锚点仅用于实现与账本校验：`+398.8407%`、真实 `1h` MDD `-25.0877%`、`17` 笔。它不是 WTL 的调参目标，也没有用于候选排序。

## 实际搜索规模

| 阶段 | 内容 | 完成量 | 错误 | 结果 |
| --- | --- | ---: | ---: | --- |
| Manifest | 数据、实现、57项测试、窗口与 exact V4 锚点冻结 | 1 | 0 | PASS |
| Stage A | entry `195` + long MFE exit `168` + short MFE exit `168` + short RSI `24` | `555/555` | 0 | 每族保留 8 个 |
| Stage B | 每族最多 8→4 的六折 flat-start rolling WFO | `32/32` | 0 | 每族保留 4 个 |
| Stage C | 低复杂度组合 | `624/624` | 0 | `0` 个 prepass passer |
| Post-fail | 经济路径聚类、全组合 leave-one-out 与代表性多次消融 | `162` 条独立 D+V 经济路径 | 0 | DIAGNOSTIC ONLY |

Stage C 的失败计数允许同一组合命中多个门：`V_candidate_floor=600`、`V_exit_activation=124`、`D_strict_dual=84`、`V_path_changed=24`、`V_strict_dual=24`、`D_path_changed=3`。其中 `440` 个组合只差 `V_candidate_floor`；`350` 个在 V 为 1 笔，`90` 个为 2 笔。

## 找到但不能冻结的路径

| 结构 | D 收益 / MDD | V 收益 / MDD | V平仓 | 为什么失败 |
| --- | ---: | ---: | ---: | --- |
| exact V4 | `+160.0203% / -21.6561%` | `+12.2129% / -18.8155%` | 3 | control |
| long MFE ATR `activation=2.0, giveback=0.5, confirm=1` | `+167.9492% / -21.6561%` | `+16.9116% / -15.4160%` | 2 | 只差 V 交易数硬门 |
| 上述 long MFE + RSI6 `25×2` | `+209.0789% / -16.4208%` | `+16.9116% / -15.4160%` | 2 | 只差 V 交易数硬门 |
| ER7 long `0.1` + long MFE + RSI6 `20×2` | `+200.1036% / -16.4208%` | `+25.5416% / -10.7429%` | 1 | 只差 V 交易数硬门，且 entry 使样本进一步收缩 |

这里的 V 交易数下降不是漏单或回测错误。long MFE 保护把一笔持续 `21` 日的盈利多单提前锁利，随后不再触发 exact V4 的亏损 forced short；部分 entry filter 又拒绝了后续亏损 long。候选因此用更少的交易产生更高收益与更小回撤，恰好与按“候选最终平仓数”设定的固定样本门相冲突。

## 因果复盘

1. **long MFE giveback 是唯一同时在 D 与 V 稳定为正的模块。** 它在 `496/496` 个可比上下文中都改变 D、V 路径，并在 D 的 `421/496`、V 的 `496/496` 个上下文同时改善收益与 MDD。
2. **short RSI 是 D 中稳定的增益项，但在 V 休眠。** 它在 D 的 `496/496` 个上下文改变路径并同时改善收益与 MDD；V 中 `0/496` 改变路径。它应作为与 long 保护正交的长期收益模块保留研究，但不能把 V 的零激活说成验证成功。
3. **entry filter 不应成为主搜索轴。** 它在 V 常能过滤坏路径，但在 D 仅 `20/496` 个上下文同时改善两指标，并会把 V 样本进一步压至 1 笔。它更像样本内时点选择器，而不是跨阶段稳定的趋势开始判定。
4. **short MFE 在 V 完全休眠。** D 中有贡献，但 V `0/496` 路径变化；继续围绕它扩参对当前验证问题没有信息增益。
5. **真正的问题是门禁设计，不是参数还不够多。** 对退出型策略，用“候选最后留下多少已平仓交易”衡量样本，会把成功避免的坏反手也当作样本损失。下一轮必须预先改为机会数、被保护趋势数、独立路径/折数与 leave-one-trade-out 稳健性；不能在 WTL 原合同内补救。

## 裁决

- WTL：`FAIL`。
- 1x champion：不存在。
- fixed/dynamic leverage：未运行；无资格解释。
- H：未访问，仍为 `[356,432)`。
- exact V4：不修改，仍是唯一登记 control。
- V5 / promotion / runner：均不发生。

后继研究必须作为全新、预注册的 Development 任务，以 long MFE/giveback 与 short RSI 为核心，放弃已证伪或休眠的 entry/short-MFE 主搜索；先在 D+V 上按机会感知门禁与多重稳健性冻结唯一 1x champion，再冻结全部 `<=3x` 杠杆臂，最后才允许 H 一次性裁决。

## 证据

- [预注册合同](../specs/hype-1d-ma7-wide-trend-lifecycle-preregistration-2026-08-10.md)
- [冻结 Manifest](../artifacts/hype_1d_ma7_wide_trend_lifecycle_2026-08-10_manifest.json)
- [Stage A 完整搜索](../artifacts/hype_1d_ma7_wide_trend_lifecycle_2026-08-10_stage_a.json)
- [Stage B rolling WFO](../artifacts/hype_1d_ma7_wide_trend_lifecycle_2026-08-10_stage_b.json)
- [Stage C 624组合与硬门](../artifacts/hype_1d_ma7_wide_trend_lifecycle_2026-08-10_stage_c.json)
- [Post-fail 多轮消融机器证据](../artifacts/hype_1d_ma7_wide_trend_lifecycle_2026-08-10_post_fail_ablation.json)
- [Post-fail 消融解读](../ablations/hype-1d-ma7-wide-trend-lifecycle-post-fail-ablation-2026-08-10.md)

