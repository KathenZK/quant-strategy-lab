# HYPE-1D-MA7-MLT P2 Episode Policy Learning 教学诊断

## 结论

P2 在“策略行为”上明显比 P1 更接近目标，但在“机器学习泛化”上失败。

- 行为进步：模型不再要求价格穿越与 MA7 斜率同日同步，成功在 `2026-07-08` raw short cross 后于 `2026-07-09` 做空，至 `2026-07-14` 净赚 `+5.93%`；并实际完成一次 `LONG -> SHORT` 直接反手。
- 趋势持有：最后一笔 long 持有满 30 日，净赚 `+10.89%`，盈利路径捕获率 `71.73%`，说明新的 survival 目标至少能产生长持仓行为。
- 统计失败：episode 入场模型 expanding group OOF AUC `0.403`，趋势存活模型 OOF AUC `0.467`，均低于随机排序。
- 策略对照失败：P2 full policy 为 `+9.41%/-24.09%`，虽高于 P1 的 `+6.82%/-1.44%`，但远低于无机器学习的 `RAW_CROSS_H7 +34.57%/-26.86%`，回撤也显著恶化。

冻结合同的机械标签为 `EDUCATIONAL_IMPROVEMENT`；研究解释必须写成 **`BEHAVIOR_IMPROVED_BUT_MODEL_GENERALIZATION_FAILED`**。P2 只证明修改候选空间、标签和动作空间可以让模型做出更接近意图的动作，不能证明这些动作来自可泛化规律。

## P2 相对 P1 改了什么

冻结合同见 [P2 教学合同](../specs/hype-1d-ma7-mlt-p2-episode-policy-learning-contract-2026-08-27.md)。

| 层级 | P1 | P2 |
| --- | --- | --- |
| 候选 | strict cross 且方向斜率已超过 `0.02 ATR` | 所有 raw cross；随后最多 7 日 episode |
| 斜率 | 入模前硬门槛 | 作为连续特征交给模型 |
| 入场样本 | 29 个完整事件 | 79 个完整 episode、300 个候选状态 |
| 退出目标 | 未来 5 日局部增量价值 | 未来 14 日是否仍有至少 1 ATR 延续空间 |
| 动作 | 继续 / 退出 | `LONG / FLAT / SHORT`，允许同开盘反手 |
| 最大持有 | 21 日 | 30 日 |

P2 仍使用低容量正则化逻辑回归，但 entry/survival 各固定 16 个特征。全部未来价格只进入标签，输入只使用决策日及此前状态；同一 episode 在 OOF 中按 group 整体切分。

## 数据和样本

- 模型训练：前 365 个完整 UTC 日；后 81 日为已被 P0/P1 揭示的教学回放。
- raw-cross episode：全窗 103 个；训练完整 episode 79 个、候选状态 300 行；验证段 episode 19 个、候选状态 77 行。
- validation replay：19 个 episode、77 个候选状态。
- survival 训练状态 8,753 行，但它们只来自 79 个 raw-cross episode；有效独立样本仍接近 79，不是 8,753。
- 单边 fee `0.10%` + slippage `0.04%`，另计 funding；日收盘决策、下一 UTC open 成交，`1x` 单仓。

## 前 365 日训练期表现补充

这里同时报告两种口径，避免把训练集内回放误写成泛化能力：

1. `resubstitution`：用前 365 日完整训练出的最终模型，再回放同一 365 日。模型在回放早期实际上见过后来的训练标签，因此这一口径含训练期内部时序泄露，只用于观察拟合上限，不参与选择。
2. `expanding group OOF`：每个测试 episode 只能由时间上更早的 episode 训练；这是本轮训练期内更可信的未知样本指标。

最终模型在训练样本内的 entry/survival AUC 为 `0.608/0.617`，但 expanding group OOF 降至 `0.403/0.467`，构成明显的泛化落差。

| 365 日 resubstitution 回放 | 净收益 | 最大回撤 | PF | 胜率 | 交易 | 反手 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P2 full policy | **-19.27%** | -50.57% | 0.891 | 52.17% | 23 | 3 |
| P2 no reversal | -28.83% | -50.97% | 0.703 | 52.17% | 23 | 0 |
| Raw cross + fixed 7d | -15.39% | -55.83% | 1.062 | 51.35% | 37 | 0 |
| P1 ML + dynamic exit | -11.51% | -35.03% | 0.958 | 58.33% | 12 | 0 |

因此，P2 不是“训练期赚、验证期失效”；它在训练样本上的分类拟合略高于随机，但转换为包含成本和动态持仓的策略后，训练期账户本身仍为负。验证期 `+9.41%` 不能反过来证明模型有效。

## 模型是否真的学得更准

### Episode 入场模型

| 指标 | 结果 |
| --- | ---: |
| 训练 episode / 状态行 | 79 / 300 |
| expanding group OOF episode / 行 | 47 / 178 |
| OOF 正类率 | 29.78% |
| OOF AUC | **0.403** |
| OOF Brier | 0.284 |
| OOF 0.5 accuracy | 35.39% |

入场概率在训练期后段没有正确排序趋势成败。扩大 episode 使模型拥有更多可选时机，但高度相关的 episode-day 行并没有自动变成更多独立信息。

### 趋势存活模型

| 指标 | 结果 |
| --- | ---: |
| 训练状态行 | 8,753 |
| expanding group OOF episode / 行 | 47 / 5,093 |
| OOF 正类率 | 45.71% |
| OOF AUC | **0.467** |
| OOF Brier | 0.277 |
| OOF 0.5 accuracy | 47.28% |

大量持仓日状态看起来像大样本，但同一趋势内的相邻日高度相似。按 episode 分组后，模型仍未表现出跨时间泛化。P2 的长拿行为来自我们更改了标签与最大持有期，不等于模型准确识别了趋势寿命。

## 教学回放结果

| 策略 | 净收益 | 最大回撤 | PF | 胜率 | 交易 | 反手 | 暴露日 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| P2 full policy | **+9.41%** | -24.09% | 1.757 | 57.14% | 7 | 1 | 43 |
| P2 no reversal | +7.71% | -25.28% | 1.599 | 42.86% | 7 | 0 | 42 |
| Raw cross + fixed 7d | **+34.57%** | -26.86% | 2.493 | 77.78% | 9 | 0 | 63 |
| P1 ML + dynamic exit | +6.82% | **-1.44%** | 无亏损笔 | 100.00% | 3 | 0 | 4 |
| exact V7.1 描述性参考 | +28.19% | -8.52% | 无亏损笔 | 100.00% | 3 | - | - |

P2 full 比 no-reversal 多 `1.70pp` 收益，说明这一次直接反手在账户路径上有小幅贡献；但 raw-cross 固定 7 日显著胜过两个 ML 策略，说明本轮最有效的改变是“把 raw cross 纳入候选”，不是模型打分。

## 用户截图附近的行为变化

P1 的 `E0397` 在 7 月 3 日入场、7 月 5 日退出，净赚 `+4.05%`，但 7 月 8 日 short cross 因 MA7 斜率仍为正而被硬门槛删除。

P2 的对应路径为：

1. `X091` long episode：7 月 2 日 raw long cross 后，模型前两天概率不足 `0.55`，到 7 月 4 日才达到 `0.551`，7 月 5 日开多；7 月 8 日退出，净亏 `-1.32%`。P2 为了等待 episode 成熟，反而破坏了 P1 原本漂亮的 long 入场。
2. `X092` short episode：7 月 8 日价格跌破 MA7，尽管方向对齐斜率为 `-0.175`（即 MA7 本身仍向上），入场概率仍为 `0.587`；7 月 9 日开空，持有到 7 月 14 日，净赚 `+5.93%`，盈利路径捕获率 `81.50%`。这正是 P1 动作空间无法实现的交易。
3. `X093 -> X094`：7 月 16 日先开 long，下一日 short episode 概率 `0.576`，比 long survival `0.463` 高 `0.113`，触发零延迟直接反手。但 long 腿先亏 `-9.46%`，随后 short 只赚 `+0.55%`。模型学会了“怎么反手”，没有学会“什么时候不该先做多”。

这组路径非常清楚地说明：扩大动作空间可以让想要的动作出现，但错误动作也会同时增加。

## 长拿趋势是否改善

P2 full 的 7 笔交易平均：

- 盈利交易 MFE 捕获率 `58.25%`；
- 退出后未来 14 日平均仍有 `0.892 ATR` 的同方向 MFE；
- 最新 `X095` long 持有满 30 日，净赚 `+10.89%`、MFE `3.00 ATR`、捕获率 `71.73%`。

与 P1 的 1–2 日退出相比，P2 确实产生了更连续的持仓。但账户 MDD 从 `-1.44%` 扩大到 `-24.09%`，说明“长拿”与“准确识别趋势存活”仍不是同义词。

## 这轮真正学到了什么

1. **特征不是模型能力的全部边界。** P1 不会 7 月 8 日做空，首先因为 hard gate 根本没给 short 动作；P2 放开候选后立刻能做。
2. **标签决定模型性格。** 把 5 日局部价值改成 14 日趋势存活，并把最长持有改成 30 日，模型自然更愿意长拿。
3. **动作空间决定能否反手。** 只有显式加入 `LONG/FLAT/SHORT` 目标仓位，模型才可能直接翻仓。
4. **行为更像目标，不代表预测更准。** 两个 OOF AUC 都低于 `0.5`，这是本轮最重要的反证。
5. **不断加同源特征会迅速过拟合。** 79 个 episode 不足以支撑对 16+16 特征反复试验；8,753 个相关状态行不能冒充独立样本。

## 裁决与下一步边界

- 机械标签：`EDUCATIONAL_IMPROVEMENT`。
- 研究结论：`BEHAVIOR_IMPROVED_BUT_MODEL_GENERALIZATION_FAILED`。
- 状态：`post-reveal educational replay / diagnostic-only / not promoted / not live-ready`。
- P2 参数和结果保持原样，不根据回放再调整。
- 若继续 P3，最有教学价值的方向不是再堆指标，而是做特征块消融：仅 cross geometry、再加 slope dynamics、再加 path memory、再加 volatility/volume；全部只在训练期 group-OOF 上比较，先看哪个特征块让 AUC 真正超过 `0.5`，再看账户路径。

## 复现与机器证据

```bash
.venv/bin/python research/hype/1d-ma7-machine-learning-trend/scripts/run_hype_1d_ma7_mlt_p2_episode_policy.py
.venv/bin/python -m pytest -q tests/test_hype_1d_ma7_mlt_p2_episode_policy.py tests/test_hype_1d_ma7_mlt_p1_cross_event.py
```

- [机器摘要](../artifacts/hype_1d_ma7_mlt_p2_episode_policy_2026-08-27_summary.json)
- [Episode 候选与概率](../artifacts/hype_1d_ma7_mlt_p2_episode_policy_2026-08-27_episode_candidates.csv)
- [Survival 训练状态](../artifacts/hype_1d_ma7_mlt_p2_episode_policy_2026-08-27_survival_training_rows.csv)
- [验证逐笔](../artifacts/hype_1d_ma7_mlt_p2_episode_policy_2026-08-27_validation_trades.csv)
- [验证每日路径](../artifacts/hype_1d_ma7_mlt_p2_episode_policy_2026-08-27_validation_path.csv)
- [逐次模型决策](../artifacts/hype_1d_ma7_mlt_p2_episode_policy_2026-08-27_validation_decisions.csv)
- [模型清单、系数与 group OOF](../artifacts/hype_1d_ma7_mlt_p2_episode_policy_2026-08-27_model_manifest.json)
