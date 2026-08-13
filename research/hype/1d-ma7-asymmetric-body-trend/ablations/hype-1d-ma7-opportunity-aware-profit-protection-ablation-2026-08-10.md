# HYPE 1D MA7 OAPP 多轮消融与失效归因

- 日期：`2026-08-10`
- 对象：唯一Development champion `C_2AA556432E9E`
- 角色：D/V/rolling为exposed Development归因；H为一次性final失败归因

## 1. 宽网格不是单点救援

- long MFE：912个参数，覆盖12档activation、19档ATR/fraction giveback、4档确认日。
- RSI6：45个参数，覆盖9档threshold、5档连续日。
- Stage A完成957/957、0 error；213个long参数与4个RSI参数经济路径重复，被去重后才排序。
- Stage B对32条独立路径做8bps和6-fold rolling，保留8×8；Stage C完整组合64条，32条过机会prepass、11条过deep，11条全部完成OAT与相邻参数。

## 2. Champion 模块消融

| 结构 | D 收益 / MDD | V 收益 / MDD | D触发 | V触发 | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| exact V4 | `+160.02% / -21.66%` | `+12.21% / -18.82%` | — | — | control |
| long MFE only | `+171.95% / -21.66%` | `+17.49% / -15.00%` | 4 | 1 | 跨D/V稳定改善，主要负责V路径 |
| RSI20×2 only | `+198.19% / -16.42%` | `+12.21% / -18.82%` | 3 | 0 | D强正贡献，V休眠 |
| long MFE + RSI20×2 | `+263.04% / -16.42%` | `+17.49% / -15.00%` | 5+3 | 1+0 | 两模块在D有正向路径交互 |

关闭long后，D从`+263.04%`降至`+198.19%`，V回到exact V4；关闭RSI后，D降至`+171.95%`且MDD回到`-21.66%`，V保持long改善。两个leave-one-out都改变经济路径，且没有任何模块在关闭后同时支配原候选。

## 3. Rolling与逐事件稳健性

- 6-fold aggregate：OAPP `+134.42%/-13.14%`，V4 `+88.80%/-14.25%`。
- 6折均非双劣；5折candidate/control都有已平交易；至少2折路径改变。
- D+V配对审计发现16个改变episode，13个正增量episode；总增量净PnL `+1.0830`，最大单episode `+0.2932`，剔除后仍`+0.7899`。
- base、8bps、funding-off均非破产且账本一致。

这些检查说明Development改善不是单笔最大赢家或单个参数孤点造成；它真正失败在未见阶段的状态链分布变化。

## 4. 相邻参数

Champion参数为fraction trail `activation=0.5 ATR / giveback=0.10 / confirm=2`与RSI `20×2`。上下相邻参数全部保留机器结果；至少一个邻居同时通过prepass与deep，满足非孤点门。较慢的RSI `20×3`失去D MDD改善，较快的`20×1`仍过prepass但deep失败，说明`×2`不是任意替换点。

## 5. H失效是状态交接，不是trail单笔本身

H的long exit局部上是正确的：将`2026-07-03`多单从V4的`-1.20%`变为`+3.16%`。但V4在`2026-07-11 06:00`的protective stop会原子反手short并赚`+16.87%`；OAPP已于三日前flat，失去这条forced-reversal状态链，只在`2026-07-17`自然开short并赚`+6.77%`。

因此：

- long局部改善：约`+4.36`初始权益点；
- lost/delayed short：损失更大；
- H总收益：OAPP比V4低`5.73pp`；
- H MDD：两者都为`-17.94%`，最差点早于该事件，保护未触及。

RSI在H 0次触发，不能承担补偿作用。这也解释了为什么Development里同一trail看似稳健：D/V被提前切断的后续short较差或亏损，而H被切断的是一笔大赢家。

## 6. 后继机制假设

后继若研究，核心不应继续微调`0.5/0.10/2`，而应显式建模“profit exit handoff continuity”：

1. long盈利退出后记录原long的V4 trailing/protective stop资格；
2. 在有限窗口内，若原long虚拟路径达到V4 forced-reversal条件，则允许按当时可知MA7确认开short；
3. 同时用anti-chase、过期和单次handoff防止persistent regime追单；
4. 对handoff关闭、仅long保护、仅RSI、完整组合做OAT；
5. D+V+H全部只能作已暴露诊断，最终资格必须来自新前瞻数据或冻结的外部资产/相位迁移。

这是一条materially new状态机制，不是OAPP的参数修补；不能回写OAPP或V4，也不能再次使用H选择阈值后称作验证。

## 证据

- [Stage C完整消融](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_stage_c.json)
- [Champion retained路径](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_champion.json)
- [H逐笔裁决](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_holdout.json)
- [完整交易路径HTML](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_full_trade_path.html)

