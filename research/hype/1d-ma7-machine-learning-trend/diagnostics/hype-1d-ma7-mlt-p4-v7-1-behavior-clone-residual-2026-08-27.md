# HYPE-1D-MA7-MLT P4：V7.1 行为克隆与残差超越

## 结论

P4 首次直接调用冻结的 `HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1` 作为教师，而不是继续学习一个简化的 MA7 穿越策略。模型已经能够拟合 V7.1 的日线教师轨迹，但训练期学到的三日退出延长没有在后 81 日超过 V7.1。

- 最终裁决：`V7_1_NOT_BEATEN / diagnostic-only / not promoted / not live-ready`。
- 训练集记忆能力：362 个可学习日线动作 accuracy `100%`，31 个 entry/exit transition recall `100%`。
- 训练期时间泛化：182 个 expanding OOF 动作 accuracy `95.60%`，11 个 transition recall `72.73%`。
- 训练期 V7.1：`+515.73% / -18.40% chronological 1h MDD / 17 trades / PF 12.97`。
- 训练期残差全量回放：`+544.33% / -17.77% / 17 trades / PF 15.17`。
- 后 81 日 V7.1：`+28.19% / -8.52% / 3 trades / 100% win`。
- 后 81 日 P4：`+25.06% / -10.20% / 3 trades / 100% win`，低于 V7.1 `3.13 pct`。

这回答了两个不同问题：模型确实可以把 V7.1 的训练轨迹拟合出来；但“拟合教师”不等于“知道什么时候应当违背教师”，本轮残差超越失败。

## 1. 本轮真正学习了什么

### 1.1 教师不是普通 MA7

教师逐日状态来自冻结 V7.1 engine/config，完整保留：

- 多空不对称 MA7 reclaim 与 slope；
- long OAPP MFE fraction trail；
- short RSI6 take-profit；
- long/short 不同 cooldown 与 max-hold；
- MA7 hysteresis/slope exit；
- 小时级 hard/trailing protective stop；
- PEHC shadow、延迟 recheck 与 short handoff。

P4 的日线模型不尝试事后预测小时级 protective stop；这类动作由原 V7.1 安全层继续负责，并从 clone 标签中标记为 `SAFETY_DELEGATE`。

### 1.2 行为克隆特征

模型共使用 27 个当时可见特征，分三组：

1. 市场结构：MA7 距离、1/2/3 日 MA7 斜率、实体、收盘位置、range/ATR、1/3/7 日收益、ER7、RSI6、ATR/close、14 日穿越次数；
2. 持仓状态：方向、持有天数、距上次退出天数、未实现收益、MFE、MAE、giveback、long/short/RSI 连续确认计数；
3. PEHC 状态：shadow 是否活动、shadow 年龄、handoff 是否 pending。

模型固定为 median imputer + 500 棵 Extra Trees。它预测下一执行时点的 `FLAT / HOLD_LONG / HOLD_SHORT / ENTER_LONG / ENTER_SHORT / EXIT_LONG / EXIT_SHORT`，没有做事后特征筛选。

### 1.3 残差模型

P4 预先冻结两个低容量逻辑回归：

- trade filter：判断一笔 V7.1 交易是否应接受；
- exit extension：判断 V7.1 的日线退出是否应延长到第三个后续 UTC open。

前三个固定候选为 `FILTER_ONLY / EXTEND_ONLY / FILTER_AND_EXTEND`。前 13 笔教师交易拟合，后 4 笔只作内部时间确认。内部确认选择 `EXTEND_ONLY`，随后才用 17 笔训练交易重训并冻结。

## 2. 365 日训练期成绩

### 2.1 V7.1 教师本身

| 指标 | V7.1 |
| --- | ---: |
| 净收益 | +515.73% |
| chronological 1h MDD | -18.40% |
| 交易数 | 17 |
| 胜率 | 82.35% |
| Profit Factor | 12.97 |
| long / short | 9 / 8 |

训练期定义为 `2025-05-31` 至 `2026-05-30` 的 365 个完整 UTC 日；训练标签最晚结束于 `2026-05-30`，没有使用 `2026-05-31` 之后的信息。

最终开发运行在数据加载层把 hourly/funding cutoff 物理固定为 `2026-05-31 00:00 UTC`，生成的 context 恰为 365 日、terminal 恰为该时点；不是先算 446 日特征再丢弃后段。严格截断重跑与原开发数值逐项差异为 0，随后重新冻结 manifest 才执行验证。

### 2.2 行为克隆：记忆与时间泛化分开报告

| 口径 | 行数 | Accuracy | Macro-F1 | Transition 数 | Transition recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| 完整训练集拟合 | 362 | 100.00% | 100.00% | 31 | 100.00% |
| Expanding OOF | 182 | 95.60% | 80.44% | 11 | 72.73% |

完整训练集的 100% 说明 Extra Trees 有足够容量表达 V7.1 的教师状态映射；OOF 的 72.73% 才更接近“遇到后来的状态还能不能做对关键动作”。因此本轮不把 100% 解释成策略已经泛化。

### 2.3 训练期内部残差确认

固定的最后四笔教师交易结果：

| 口径 | 净收益 | 1h MDD | 交易数 | 胜率 |
| --- | ---: | ---: | ---: | ---: |
| V7.1 | +92.44% | -18.40% | 4 | 75% |
| EXTEND_ONLY | +107.27% | -17.77% | 4 | 100% |

主要变化发生在 `2026-03-23` 的 short：V7.1 于 `2026-03-29` 因 MA7 slope exit 平仓并亏损；残差概率 `0.6479`，延长至 `2026-04-01` 后转为盈利。该结果使内部训练门禁通过。

用全部训练交易重训后的拟合回放为 `+544.33% / -17.77%`，高于 V7.1 的 `+515.73% / -18.40%`。这仍是训练期成绩，不能代替验证。

## 3. 后 81 日 reused holdout

后段是 `2026-05-31` 至 `2026-08-19`，terminal 为 `2026-08-20`。V7.1 与 P4 都从独立验证窗口的 flat state 开始；第一笔实际交易出现在 `2026-07-03`。该窗口已在 P0-P3 中揭示，只能称 reused holdout，不是 clean OOS。

### 3.1 对决

| 指标 | V7.1 | P4 EXTEND_ONLY | 差值（P4 - V7.1） |
| --- | ---: | ---: | ---: |
| 净收益 | +28.19% | +25.06% | -3.13 pct |
| chronological 1h MDD | -8.52% | -10.20% | -1.68 pct |
| 交易数 | 3 | 3 | 0 |
| 胜率 | 100% | 100% | 0 |
| 曝露天数 | 32 | 35 | +3 |

三笔交易的 entry、方向、价格和 `1x` leverage 完全相同。唯一变化是：

- `2026-07-03 long`：V7.1 在 `2026-07-08` 以 `69.187` 退出；模型延长概率仅 `0.5020`，刚越过冻结阈值，延长至 `2026-07-11` 的 `67.516`，单笔独立净收益由约 `+2.97%` 降到 `+0.45%`。
- `2026-07-12 short` 与 `2026-08-09 long`：模型未延长，保持 V7.1 原退出。

因此 P4 不是因为漏掉大趋势，而是对一笔本来正确的 OAPP 退出做了错误干预。

冻结逐笔回放的最近切片如下；`3m/6m/1y` 的起点早于验证策略第一笔交易，因此等于完整验证结果：

| 切片 | V7.1 收益 / MDD | P4 收益 / MDD |
| --- | ---: | ---: |
| 1d | 0.00% / 0.00% | 0.00% / 0.00% |
| 7d | +1.29% / -4.60% | +1.29% / -4.60% |
| 1m | +17.02% / -4.75% | +17.02% / -4.75% |
| 3m | +28.19% / -8.52% | +25.06% / -10.20% |
| 6m | +28.19% / -8.52% | +25.06% / -10.20% |
| 1y | +28.19% / -8.52% | +25.06% / -10.20% |

### 3.2 Clone 在验证期的真实短板

行为克隆验证共有 80 个动作：accuracy `96.25%`，但 6 个 transition 只正确 3 个，recall `50%`。

错误恰好都在关键动作：

- `2026-07-03 ENTER_LONG` 被预测为 `FLAT`；
- `2026-08-01 EXIT_SHORT (max_hold)` 被预测为 `HOLD_SHORT`；
- `2026-08-09 ENTER_LONG` 被预测为 `FLAT`。

其余 74 个大多是 HOLD/FLAT，所以总体 accuracy 看起来很高。P4 的残差回放仍依赖 V7.1 教师提供交易机会，不能把 `+25.06%` 说成行为克隆模型独立交易的收益。

## 4. 为什么训练内能赢，验证却输

1. exit extension 训练只有 14 个合格退出，其中正类 4 个；样本过少，概率不稳定。
2. 内部确认的成功例是亏损 short 的 slope exit，验证误判的是盈利 long 的 OAPP exit，机制不同但被同一个小模型合并学习。
3. 验证错误概率 `0.5020` 几乎贴着 `0.50` 阈值，说明不是强信号。阈值已经冻结，结果揭示后不能调成 `0.51` 来救 P4。
4. V7.1 本身在该 81 日的三笔交易全胜；想超过它，残差必须改善持有收益，而任何错误延长都会直接落后。

## 5. 教学结论与下一轮边界

这轮证明“不断构造状态特征可以精准拟合训练期 V7.1”是可行的，但要分清三个难度：

1. 记住 V7.1 历史动作：本轮已做到 100%；
2. 对后来出现的 V7.1 状态预测关键动作：目前 OOF `72.73%`、reused holdout `50%`，还不够；
3. 在不知道未来的情况下改得比 V7.1 更好：本轮失败。

下一轮不能根据本次验证把 threshold 改成 `0.51`。合规的 P5 应只用 365 日重新设计“关键转移动作优先”的学习问题，例如分别训练 long entry、short entry、long exit、short exit，按 transition class 做代价敏感验证，并把 exit reason 分模型；新的超越结论需要等待未见过的新未来数据。

## 6. 证据

- [冻结合同](../specs/hype-1d-ma7-mlt-p4-v7-1-behavior-clone-residual-contract-2026-08-27.md)
- [研究脚本](../scripts/run_hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual.py)
- [开发冻结清单](../artifacts/hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27_development_manifest.json)
- [365日开发摘要](../artifacts/hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27_development_summary.json)
- [81日验证摘要](../artifacts/hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27_validation_summary.json)
- [训练教师状态](../artifacts/hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27_teacher_daily_states.csv)
- [Clone OOF 预测](../artifacts/hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27_clone_oof_predictions.csv)
- [验证 Clone 预测](../artifacts/hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27_validation_clone_predictions.csv)
- [验证残差决策](../artifacts/hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27_validation_residual_decisions.csv)
- [V7.1 验证交易](../artifacts/hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27_validation_teacher_trades.csv)
- [P4 验证交易](../artifacts/hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27_validation_overlay_trades.csv)
- [冻结验证最近切片](../artifacts/hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27_recent_slices.json)
- [P4 与 exact V7.1 同图交易路径](../artifacts/hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27_v7_1_comparison_trade_paths.html)
