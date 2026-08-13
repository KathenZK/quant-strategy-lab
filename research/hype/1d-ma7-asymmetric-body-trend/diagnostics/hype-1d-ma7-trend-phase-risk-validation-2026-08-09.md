# HYPE 1D MA7 趋势阶段与风险效率研究裁决

> 研究代号：`TPR`。冻结日期：2026-08-09。完成日期：2026-08-10。最终状态：`Validation hard-gate FAIL / explore / not promoted / not live-ready`。本研究不修改 exact V4，不登记 V5，不推进 runner。

## 1. 结论

本轮没有找到可验证的“更高收益、更低回撤”版本。

Development 唯一通过者是 `QOFF_EOFF_T25X2`：完全保留 exact V4 的趋势开始、持有和多头退出，只增加固定的 short `RSI6<25` 连续2个实际持仓日、且浮盈严格覆盖 `0.28%` 往返成本后的次日开盘止盈。它在 D-full 和 WFO 上同时提高收益、降低真实 `1h` 顺序 MDD，但在一次性 Validation 中没有一次 T 触发，逐笔路径与 exact V4 完全相同，因此严格双重支配失败。

按[预注册合同](../specs/hype-1d-ma7-trend-phase-risk-preregistration-2026-08-09.md)，研究在 Validation 后停止：未运行固定或动态杠杆，未揭示 Holdout，未生成 leverage/holdout/final artifact。Development 的改善只保留为机制证据，不是可登记版本或 OOS 成功。

## 2. Control 与风险口径

- 唯一 control 是已登记 `HYPE-1D-MA7-Asymmetric-Body-Trend-V4` 的 exact `1x` 实现。
- 主风险指标是交易 ledger 按真实 timestamp 合并 `1h` open、funding event 和实际 fill 后重放得到的 `chronological_1h_mdd`。
- 次要压力指标继续保留 exact V4 的 `favorable extreme -> adverse extreme -> close` 日极值 MDD，命名为 `daily_extreme_mdd`。
- 主重放与原回测 terminal equity、cost、funding、turnover、trade count 五项全部一致；任何破产均 fail closed。
- Manifest 前通过56项测试；432根完整 UTC 日 K、10,390根闭合 `1h` 和2,597条 funding 均为0 blocker。

这解释了本轮与上一轮 V4-PFT 的门禁差异：上一轮把保守日极值 MDD作为主门，T 的 WFO MDD与 V4同为 `-19.6742%`；本轮预注册后使用真实顺序 `1h` MDD，T 的 WFO为 `-13.1424%`、V4为 `-14.2469%`。这不是改写上一轮结论，而是用不同且在绩效读取前冻结的风险定义重新回答问题。

## 3. Development 结果

### 3.1 唯一通过者

| 域 | exact V4 收益 | T 候选收益 | 收益差 | exact V4 1h MDD | T 候选 1h MDD | MDD改善 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| D-full | +160.0203% | +199.9330% | +39.9126pp | -21.6561% | -16.4208% | +5.2353pp |
| WFO aggregate | +62.3426% | +86.2882% | +23.9456pp | -14.2469% | -13.1424% | +1.1045pp |
| 8bps D-full | +158.0472% | +197.2181% | +39.1709pp | -21.7149% | -16.4208% | +5.2942pp |
| 8bps WFO | +61.8610% | +85.4626% | +23.6016pp | -14.2469% | -13.1772% | +1.0698pp |

候选 D-full 有12笔（long 5、short 7），exact V4有10笔；无破产，账本重放全一致。三个 WFO fold 中 F1、F3 与 V4 完全相同，全部改善只来自 F2；因此通过门禁，但跨折支持仍然很窄。

### 3.2 T 的因果贡献

T 在 D-full 实际退出4次，4笔均盈利：

| Short entry | T exit | 净收益率 | exact V4 原退出 |
| --- | --- | ---: | --- |
| 2025-07-24 | 2025-08-03 | +15.42% | 2025-08-08，+6.26% |
| 2025-09-20 18:00 | 2025-09-24 | +18.28% | 2025-10-01，+17.59% |
| 2025-11-21 | 2025-11-23 | +19.91% | 2025-11-29，+6.82% |
| 2025-12-06 | 2025-12-19 | +27.46% | 2025-12-25，+18.87% |

关闭 T 后，D 经济路径退回 exact V4；T 的 activation 与 OAT 均为 PASS。提前平空也释放了后续 natural reclaim，使候选新增了2025-12-25 long和2026-01-01 forced short，两笔合计为负，但仍未抵消四次提前止盈的收益贡献。

## 4. 趋势开始与结束模块归因

### 4.1 趋势开始 Q：失败

Q 使用7日方向效率 `signed_ER7` 对 exact V4 natural reclaim作二元过滤。结果显示阈值越高，越容易删掉少数决定收益的趋势事件：

| Q | D 收益 / 1h MDD | WFO 收益 / 1h MDD | D拒绝数 | 裁决 |
| --- | --- | --- | ---: | --- |
| disabled | +199.93% / -16.42% | +86.29% / -13.14% | 0 | 唯一通过 |
| 0.20 | +136.70% / -16.42% | +35.26% / -7.93% | 4 | 收益低于 V4；WFO仅2笔 |
| 0.30 | +98.63% / -16.74% | +9.35% / -15.46% | 6 | 收益与样本门失败 |
| 0.40 | +3.52% / -23.51% | -14.21% / -15.46% | 12 | 收益、回撤和样本均失败 |

结论：在该样本中，fresh MA7 reclaim本身已经很稀疏；再用短窗口路径效率作 hard reject，减少回撤的代价是删除高价值入场。Q不能替代 V4 的趋势开始规则。

### 4.2 多头趋势结束 E：休眠

`e=2/3` 的盈利 long、MA7 slope/ATR连续非正退出在所有12个候选中均为0次激活；D 的49个 long held-day 事件中，`e=2`与`e=3`的合格 hypothetical trigger也都为0。相同 Q 下，E2/E3 与 E disabled 的收益、交易和路径完全相同，模块接线门因此失败。

结论：V4 的 intraday protective stop、native daily exit和持仓轨迹会在“盈利且连续2/3日 slope非正”形成前结束仓位。继续搜索 E 阈值会是事后救援，本轮不做。

### 4.3 空头趋势结束 T：Development有效，Validation不可迁移

T 是本轮唯一产生真实正贡献的结束模块，但它只在 Development 的4段明显下跌中触发。它不是每个窗口都会出现的通用退出：Validation 唯一 short 由 long trailing stop强制反手产生，并在15小时后因 native MA7 slope退出，来不及形成2个 RSI持仓日。

## 5. 一次性 Validation

| 指标 | exact V4 | `QOFF_EOFF_T25X2` | 差值 |
| --- | ---: | ---: | ---: |
| 净收益 | +12.2129% | +12.2129% | 0.0000pp |
| chronological 1h MDD | -18.8155% | -18.8155% | 0.0000pp |
| daily extreme MDD | -20.4384% | -20.4384% | 0.0000pp |
| 交易数 | 3 | 3 | 0 |
| T exits | 0 | 0 | 0 |

三笔交易的时序与经济结果完全相同：21日 long盈利、同小时 forced short约15小时后小亏退出、随后2日 long亏损退出。候选没有变差，但“路径相同”不满足收益严格更高、chronological MDD严格更小及materiality，所以 Validation hard-gate为 `FAIL`。

## 6. 为什么没有杠杆结果

杠杆层在合同中是信号通过后的风险放大器，不允许救援失败的 `1x` 策略。由于 Validation FAIL：

- `1.25x–3x` 固定杠杆未运行；
- ATR risk-budget `10%/15%/20%` 和 ER调节动态杠杆未运行；
- 无收益—回撤 Pareto、无20/25/30/35/40/50% MDD cap结果；
- Holdout `[356,432)`保持未揭示。

因此不能诚实回答“最多能赚多少、需要承担多少回撤”。任何现在补跑的3x数字都会违反预注册，并把一个未验证的稀疏事件优势放大成更高风险。

## 7. 研究回答

1. **趋势开始**：本轮没有找到比 exact V4 fresh reclaim更好的低复杂度判定。`signed_ER7` hard filter明显损害收益和样本。
2. **趋势持续**：保留 V4 既有持有与保护路径仍是当前最有证据的选择。
3. **多头趋势结束**：连续2/3日非正 slope在真实路径中完全休眠，不是可用修复。
4. **空头趋势结束**：固定 RSI6 `25×2`盈利止盈在 D 有清晰正贡献，但 Validation 无触发，尚不能成为 V5。
5. **高收益低回撤版本**：没有通过 Validation；`QOFF_EOFF_T25X2`只能称 D-selected failed candidate。

若继续，当前 V 已揭示，不得在同一 V 上改 RSI、E或Q参数。下一条合规研究只能把 D+V作为已暴露诊断区，保持 H 封存，并预注册一个能实际触及常见 long protective path的全新机制，例如只使用当时已知 MFE/giveback与 ATR 的盈利保护；在新的单次 H 或新增前瞻数据上裁决。它仍需先通过 `1x`，才能研究杠杆。

## 8. 冻结证据

- [Manifest](../artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_manifest.json) · [SHA256](../artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_manifest.sha256)
- [13臂 Development trials与事件研究](../artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_development_trials.json) · [SHA256](../artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_development_trials.sha256)
- [Development机器裁决](../artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_development.json) · [D champion冻结](../artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_champion.json)
- [一次性Validation裁决](../artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_validation.json) · [SHA256](../artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_validation.sha256)
- [D完整逐笔交互HTML](../artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_development_QOFF_EOFF_T25X2_trade_path.html) · [SHA256](../artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_development_QOFF_EOFF_T25X2_trade_path.sha256)

所有持久化 JSON/HTML sidecar 均已重新校验通过。不存在 leverage、holdout 或 final artifact。
