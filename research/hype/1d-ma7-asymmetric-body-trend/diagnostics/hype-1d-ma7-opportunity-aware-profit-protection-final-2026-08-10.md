# HYPE 1D MA7 OAPP 最终裁决

- 日期：`2026-08-10`
- 分支：`Opportunity-Aware Profit Protection`（OAPP）
- 最终状态：`H hard-gate FAIL / not promoted / not live-ready`
- 唯一控制：登记的 exact V4，固定 `1x`
- 唯一 Development champion：`C_2AA556432E9E`
- H：`[356,432)` 已按锁一次性揭示；不得重跑、替补或调参

## 最终结论

OAPP 在 researcher-exposed D、V 和 rolling 上显著提高收益并降低真实 `1h` MDD，但在唯一未揭示 H 上没有战胜 exact V4，因此“更高收益、更低回撤”的目标没有完成。

| 窗口 | exact V4 收益 / MDD | OAPP 1x 收益 / MDD | 收益差 | MDD改善 | 裁决 |
| --- | ---: | ---: | ---: | ---: | --- |
| D `[0,259)` | `+160.02% / -21.66%` | `+263.04% / -16.42%` | `+103.02pp` | `+5.24pp` | PASS |
| V `[269,346)` | `+12.21% / -18.82%` | `+17.49% / -15.00%` | `+5.28pp` | `+3.82pp` | PASS |
| 6-fold rolling | `+88.80% / -14.25%` | `+134.42% / -13.14%` | `+45.62pp` | `+1.10pp` | PASS |
| H `[356,432)` | `+22.43% / -17.94%` | `+16.70% / -17.94%` | `-5.73pp` | `0.00pp` | **FAIL** |

全窗只是已揭示后的描述：OAPP `+509.26% / -21.56%`，exact V4 `+398.84% / -25.09%`。全窗数值更好不能覆盖 H FAIL，也不能登记 V5。

## 冻结策略

OAPP 保留 exact V4 的所有入场、native exit、intraday stop、forced reversal与cooldown，只增加：

1. long MFE fraction trail：最高close相对entry至少达到`0.5 ATR7`，从峰值回吐至少该笔MFE的`10%`并连续2日，且仍覆盖`0.28%`gross profit时，次日open平多；
2. short RSI：盈利空单连续2个实际持仓日`RSI6<20`，次日open平空。

Development 中 long trail触发D/V=`5/1`次，RSI触发=`3/0`次；两个模块OAT均改变路径，关闭任一模块都不能在D、V同时反向支配；相邻参数存在deep passer。

## 搜索与消融规模

| 阶段 | 规模 | 结果 |
| --- | ---: | --- |
| 冻结测试 | 68 | PASS |
| Stage A | `912` long MFE + `45` RSI=`957` | 0 error；去除213/4条重复经济路径 |
| Stage B | 16+16独立路径 | 8+8 survivors |
| Stage C | 64两模块组合 | 32 prepass、11 deep、11完整OAT |
| Champion消融 | leave-one、keep-one、全部相邻参数、6 folds、8bps、funding-off、独立episode、最大增量episode剔除 | PASS |
| 杠杆 | 5 fixed + 4 dynamic | H前全部冻结 |

完整因果表见[消融报告](../ablations/hype-1d-ma7-opportunity-aware-profit-protection-ablation-2026-08-10.md)。

## H 为什么失败

H中 RSI6 仍为0次触发；唯一新增事件是 long MFE exit：

- exact V4 的 `2026-07-03` long 持有到 `2026-07-11 06:00` protective stop，净 `-1.20%`；随后同open forced reversal short，持有到`2026-07-31`，净 `+16.87%`。
- OAPP 在 `2026-07-08` 提前锁利，long净 `+3.16%`；但提前退出后进入flat/cooldown，`2026-07-11` 不再处于原long stop状态，因此没有获得那笔高价值forced short。直到`2026-07-17`才自然开short，终端净`+6.77%`。

单看提前平多，OAPP相对V4改善约`+4.36`个初始权益点；考虑错过/延后short后，配对增量转为负。H总收益因此少`5.73pp`，而最差回撤发生在更早的`2026-06-04 17:00`，两者完全相同，long profit protection没有触及真正的H回撤源。

这揭示了比参数更重要的结构问题：**V4的long退出、forced reversal与后续short收益是一个不可分割的仓位交接链。提前止盈若只转flat，会同时切断未来的反手权利。** Development 中被切断的反手较差，H中被切断的反手很好，所以同一规则方向翻转。

## 杠杆结果

1x H已失败，按预注册合同，所有杠杆只作审计，不能用加杠杆掩盖信号失败。H事实前沿如下：

| H MDD上限 | 最高收益臂 | 收益 | MDD | 最大标记杠杆 | 解释资格 |
| ---: | --- | ---: | ---: | ---: | --- |
| 20% | ATRER-R15 | `+22.98%` | `-16.23%` | `2.06x` | 无；1x FAIL |
| 25% / 30% | ATR-R20 | `+31.09%` | `-23.49%` | `2.38x` | 无；1x FAIL |
| 35% | fixed 2.0x | `+35.19%` | `-30.84%` | `2.34x` | 无；1x FAIL |
| 40% | fixed 2.5x | `+45.14%` | `-36.06%` | `3.02x` | 超过实际3x且1x FAIL |
| 50% | fixed 3.0x | `+55.58%` | `-40.68%` | `3.73x` | 超过实际3x且1x FAIL |

ATRER-R15在这一段H恰好同时略高于V4收益并降低MDD，但这是动态交易加权而非1x信号验证，只有4笔交易，且合同明确要求1x先通过，故不构成成功。固定2.5/3.0x因数量固定，实际标记杠杆随权益变化超过3x，不属于用户要求的“不高于3倍”可承受方案。

全窗杠杆数字（例如fixed 2x `+2,642.47%/-37.00%`、fixed 3x `+9,805.16%/-49.20%`）全部来自已揭示历史且实际杠杆可能漂移，只能说明复利放大，不能说明更强alpha或live readiness。

## 报告恢复说明

冻结renderer最初因最后一笔在`2026-08-06 terminal open`成交、而完整日K只到`2026-08-05`而拒绝HTML。独立报告恢复器只追加一根OHLC全部等于terminal open `56.953`的display-only点；不读取该小时后续high/low/close，不改变策略指标、交易或路径。恢复脚本与SHA已写入最终JSON。

## 裁决与下一步

- OAPP：`H hard-gate FAIL`。
- exact V4：保持不变。
- OAPP champion：只保留为Development diagnostic，不登记V5。
- 杠杆：不采纳、不promotion。
- runner：不交接。
- H：已耗尽，后继不得把它再次当未揭示验证。

如果继续研究，只能把D+V+H全部标记为exposed，用“profit exit 后保留/恢复反手资格”的状态连续性作为新机制诊断，并把真正的最终判定留给新增HYPE前瞻数据或预注册的外部转移证据；不能继续在这432日内搜到一个赢家后声称完成目标。

## 证据

- [预注册合同](../specs/hype-1d-ma7-opportunity-aware-profit-protection-preregistration-2026-08-10.md)
- [Manifest](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_manifest.json)
- [Stage A](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_stage_a.json)
- [Stage B](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_stage_b.json)
- [Stage C与多轮消融](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_stage_c.json)
- [Champion](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_champion.json)
- [杠杆冻结](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_leverage_freeze.json)
- [H一次性裁决](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_holdout.json)
- [最终机器报告](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_final.json)
- [完整逐笔HTML](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_full_trade_path.html)

