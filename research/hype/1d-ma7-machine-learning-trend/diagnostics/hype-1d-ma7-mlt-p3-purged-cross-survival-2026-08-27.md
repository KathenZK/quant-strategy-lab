# HYPE-1D-MA7-MLT P3 Purged Cross Survival 诊断

## 结论

P3 严格执行了“365日开发、81日只验证”的两阶段流程。训练期内部出现了比 P1/P2 更清晰的入场排序，但一次性验证失败：

- 冻结裁决：**`VALIDATION_FAILED`**。
- selected entry `GEOMETRY_4`：开发 OOF AUC `0.646`；13个标签完整的验证穿越 AUC 降为 `0.500`。
- selected survival `SURVIVAL_CORE_6`：开发 OOF AUC `0.527`；验证 cross 等权 AUC `0.578`，但固定动作映射未能控制尾部亏损。
- 开发集内部确认：`+7.47% / -12.96% MDD / PF 2.466 / 7 trades`。
- 81日验证：`-8.96% / -26.10% MDD / PF 0.825 / 7 trades`。
- raw-cross 固定7日验证：`+34.57% / -26.86% MDD / PF 2.493 / 9 trades`。

这说明“穿越形态在训练期出现一定排序能力”尚不能泛化为81日的穿越质量识别；动态存活模型虽有轻微验证排序能力，但学出的概率方向与固定 `0.50` 退出规则没有形成可靠尾部保护。

## 数据隔离审计

冻结合同见 [P3合同](../specs/hype-1d-ma7-mlt-p3-purged-cross-survival-contract-2026-08-27.md)。

- `develop` 特征管线在计算任何特征前截断到365日，末日为 `2026-05-30 00:00 UTC`。
- development manifest 明确记录 `validation_rows_read_by_feature_pipeline=0`。
- 前285日用于特征块 OOF 选择；其后开发时段只作内部确认，不参与选择。
- entry OOF fold 前按标签结束索引执行21日 purge；survival 标签也不得跨 fold 或训练边界。
- manifest 与合同均在验证前保存 SHA256；`validate` 先校验两者，才读取后81日。
- 81日已在 P0–P2 中揭示，故仍是 `reused holdout`，不能称为 clean OOS。

## Entry 特征块消融

选择阶段共63个标签完整的精确 raw-cross；每个穿越只有一行。OOF覆盖39个时间后置事件。

| 特征块 | 特征数 | OOF AUC | Brier | 常数Brier | Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| **GEOMETRY_4** | **4** | **0.646** | **0.234** | 0.238 | **64.10%** |
| GEOMETRY_SLOPE_8 | 8 | 0.606 | 0.237 | 0.238 | 58.97% |
| GEOMETRY_SLOPE_PATH_12 | 12 | 0.526 | 0.247 | 0.238 | 56.41% |
| ALL_16 | 16 | 0.523 | 0.252 | 0.238 | 53.85% |

`GEOMETRY_4` 的三个 fold AUC 为 `0.575 / 0.694 / 0.825`，均高于 `0.5`。固定选择规则因此选中最简单的四项：

1. 穿越前价格距 MA7；
2. 穿越后价格距 MA7；
3. 方向对齐的穿越 K 线实体；
4. 方向对齐的收盘位置。

关键教学结论是：加入 MA7 斜率后 AUC 反而下降约 `0.040`；继续加入路径、波动和成交量后接近随机。至少在这63个开发事件中，“穿得多深、K线实体和收盘位置”比斜率更有排序信息，堆因子明显恶化。

## Survival 特征块消融

每个 raw-cross 只构造一条 canonical campaign；选择阶段为63个 cross、1,836行。每个 cross 的全部状态权重之和为1。

| 特征块 | 特征数 | 等权 OOF AUC | Brier | 常数Brier | Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| **SURVIVAL_CORE_6** | **6** | **0.527** | 0.250 | **0.249** | 51.20% |
| SURVIVAL_PATH_11 | 11 | 0.526 | 0.251 | 0.249 | 51.55% |
| SURVIVAL_ALL_15 | 15 | 0.526 | 0.251 | 0.249 | 51.68% |

`SURVIVAL_CORE_6` fold AUC 为 `0.498 / 0.509 / 0.651`。按冻结门禁有2个 fold 高于 `0.5`，机械通过，但 Brier 还略差于常数预测，说明它只是很弱的边缘信号。

被选六项为：当前 MA7 距离、MA7 一日/三日斜率、持仓年龄、未实现收益、MFE giveback。

## 365日训练表现

最终模型使用前365日内标签完整的78个 raw-cross；survival 为78个 cross、2,297行。

| 模型 | 训练集内 AUC | 开发期 selected OOF AUC |
| --- | ---: | ---: |
| Entry GEOMETRY_4 | 0.669 | 0.646 |
| Survival CORE_6 | 0.607 | 0.527 |

365日最终模型 resubstitution 账户回放只作拟合上限：

| 策略 | 净收益 | 最大回撤 | PF | 胜率 | 交易 |
| --- | ---: | ---: | ---: | ---: | ---: |
| P3 full policy | +25.41% | -26.15% | 1.756 | 57.14% | 28 |
| P3 no reversal | +25.41% | -26.15% | 1.756 | 57.14% | 28 |
| Raw cross + fixed 7d | -15.81% | -55.83% | 1.055 | 50.00% | 36 |

更可信的内部确认段此前完全没有参与特征选择：

| 策略 | 净收益 | 最大回撤 | PF | 胜率 | 交易 | 暴露日 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P3 full policy | **+7.47%** | **-12.96%** | **2.466** | 57.14% | 7 | 20 |
| Raw cross + fixed 7d | -29.35% | -35.72% | 0.355 | 28.57% | 7 | 44 |

内部确认支持把冻结模型送入一次性81日验证，但7笔交易仍然非常少。

## 81日一次性验证

| 策略 | 净收益 | 最大回撤 | PF | 胜率 | 交易 | Long/Short | 反手 | 暴露日 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **P3 full policy** | **-8.96%** | -26.10% | 0.825 | 71.43% | 7 | 2/5 | 0 | 19 |
| P3 no reversal | -8.96% | -26.10% | 0.825 | 71.43% | 7 | 2/5 | 0 | 19 |
| Raw cross + fixed 7d | **+34.57%** | -26.86% | 2.493 | 77.78% | 9 | 6/3 | 0 | 63 |

P3 的验证入场分类审计：18个候选穿越中只有13个拥有完整21日未来路径；AUC `0.500`、Brier `0.271`、accuracy `38.46%`。因此训练期 entry 排序没有外推。

validation survival 有14个 cross、301行，cross 等权 AUC `0.578`；但这不代表固定阈值动作正确。

## 尾部失败：P3X101

前6笔 P3 交易为5赢1小亏，随后最后一笔 short 抹掉盈利：

- `2026-08-09` short raw-cross，entry probability `0.523`，`2026-08-10` 下一 open 入场。
- 持有10日，MFE仅 `0.057 ATR`，MAE达到 `7.354 ATR`。
- 每日 survival probability 从 `0.520`、`0.506` 一路升至 `0.659`，始终没有跌破 `0.50`。
- `2026-08-12` 出现反向 long cross，但 entry probability 只有 `0.496`，差一点未达到固定 `0.50`，因此既未退出也未反手。
- terminal mark 净亏 `-26.10%`。

最终 survival 模型中 `unrealized_atr` 系数为 `-0.176`：对 short 而言，亏损越大、未实现收益越负，线性项反而越提高 survival probability。这表明模型在训练期学到了一种“亏损后等待均值回归”的关系，与趋势死亡/止损目标相冲突。P3 没有盘中保护，因此该错误直接成为账户尾部。

## 裁决与下一步边界

- 训练门禁：机械通过，但 survival 证据很弱、样本很少。
- 验证门禁：失败；净收益、PF及 raw-cross 对照均不通过。
- 最终裁决：`VALIDATION_FAILED / diagnostic-only / not promoted / not live-ready`。
- P3 不再修改、不再对同一81日重跑选择。
- 若继续 P4，不能根据 `P3X101` 增加一个专门规则来修补；应回到365日，重新定义“趋势死亡”标签或把风险保护作为与 ML 分离的冻结安全层，并使用新的未来数据作真正验证。

## 证据

- [开发冻结清单](../artifacts/hype_1d_ma7_mlt_p3_purged_cross_survival_2026-08-27_development_manifest.json)
- [机器摘要](../artifacts/hype_1d_ma7_mlt_p3_purged_cross_survival_2026-08-27_summary.json)
- [验证后模型审计](../artifacts/hype_1d_ma7_mlt_p3_purged_cross_survival_2026-08-27_post_validation_model_audit.json)
- [验证逐笔](../artifacts/hype_1d_ma7_mlt_p3_purged_cross_survival_2026-08-27_validation_trades.csv)
- [验证每日决策](../artifacts/hype_1d_ma7_mlt_p3_purged_cross_survival_2026-08-27_validation_decisions.csv)
- [研究脚本](../scripts/run_hype_1d_ma7_mlt_p3_purged_cross_survival.py)

