# BIN-1H-MHCSML 目标完成度矩阵（2026-07-19）

## 结论

原目标共 10 项。当前第 `1–7` 项的研究与冻结工作已完成，第 `8` 项必须等待基础版本 prospective OOS 先通过，第 `9` 项必须等待未来三个月一次性揭盲，第 `10` 项除 prospective 逐腿/绩效/压力/验收报告外均已有交付物。因此整体目标仍为 `active`，策略状态保持 `registered / not promoted / not live-ready`。

本矩阵只核对交付证据和盲测运行状态，不读取 prospective OOS 的标签、收益、逐腿结果、IC 或绩效。

## 逐项对账

| # | 原始要求 | 权威证据 | 当前判定 | 完成前仍需满足 |
| ---: | --- | --- | --- | --- |
| 1 | 修复线性 USD-M 空头公式并作废旧结论 | [收益实现](../../../../src/strategy_lab/data/linear_contract_returns.py)、[公式测试](../../../../tests/test_linear_contract_returns.py)、[旧 V1 撤销规格](../../1h-cross-sectional-lightgbm-selector/specs/binance-1h-cslgbm-v1-reproduction-spec.md)、[旧 artifact 机器撤销清单](../../1h-cross-sectional-lightgbm-selector/artifacts/v1_oos_2026q2/REVOCATION.json)、旧家族纠错审计 | `COMPLETE` | 无；旧 `+221.84%` 等结论不得恢复或继承，原件只保留为事故证据 |
| 2 | 全市场 OHLCV/mark/funding/生命周期/PIT 数据审计与补齐 | [数据质量报告](binance-1h-mhcsml-data-quality-2026-07-18.md)、data quality manifest、nontradable interval 与 funding quarantine 证据 | `COMPLETE` | prospective 期间每轮仍须同步闭合数据并保持无 blocker |
| 3 | 因子数量按目标扩展，并做泄漏、覆盖、稳定、相关和消融 | [因子面板审计](binance-1h-mhcsml-factor-panel-2026-07-18.md)、[因子组消融](../ablations/binance-1h-mhcsml-factor-group-ablation-2026-07-19.md)、235/86 冻结 feature lists | `COMPLETE` | volatility-tail 正 IC drop 占 `87.62%` 的集中依赖风险必须保留披露 |
| 4 | 分离 long/short/tail 标签与模型，比较多类 LightGBM、线性和规则 | [历史 OOF 审计](binance-1h-mhcsml-oof-model-allocator-2026-07-18.md)、16 个冻结模型与受控基线 manifest | `COMPLETE` | 最终还需用同一 prospective OOS 证明 R4 超过 Ridge 与规则基线 |
| 5 | 搜索多期限/频率/方向/可变 N/阈值，允许空仓 | [开发矩阵审计](binance-1h-mhcsml-development-matrix-2026-07-18.md)、allocator 搜索结果、R1–R3 作废链、R4 锁 | `COMPLETE` | prospective 期间不得切换到历史上表现更好的其它网格行 |
| 6 | nested rolling WF、purge/embargo、OOF、多 seed；2026Q2 只作 reused holdout | [历史 OOF 审计](binance-1h-mhcsml-oof-model-allocator-2026-07-18.md)、7-fold 预测与 seed audit | `COMPLETE` | 最终报告必须继续把 2026Q2 标为 reused holdout，而非独立 OOS |
| 7 | 冻结全部规则与 SHA，执行 2026-07-19 至 2026-10-19 prospective OOS | [R4 master freeze](../artifacts/freeze/bin-1h-mhcsml-v1-freeze-r4.json)、[外部复现规格](../specs/binance-1h-mhcsml-v1-r4-external-reproduction-spec-2026-07-19.md)、盲链健康审计器 | `COMPLETE / OOS RUNNING` | 必须收齐 552 个 `FROZEN_ON_TIME` 或 `MISSED` 节点；`2026-10-20 21:05 UTC` 前不得揭盲 |
| 8 | 基础版本先通过，再评估 3 倍杠杆 | [3x 尾部风险规格](../specs/binance-1h-mhcsml-v1-r4-3x-tail-risk-audit-spec-2026-07-19.md)、[outcome-blind 风险合同](../artifacts/freeze/bin-1h-mhcsml-v1-three-x-risk-contract-r4.json) | `CONTRACT COMPLETE / EXECUTION PENDING` | 只有第 9 项基础 OOS 全部通过后，才执行已预先冻结的 6 场景逐时 mark、保证金和强平审计；不得用杠杆挽救失败基础版本 |
| 9 | 全部最终硬门槛 | master freeze 的 `final_hard_gates`、一次性 reveal guard 与 [最终裁决合同](../artifacts/freeze/bin-1h-mhcsml-v1-final-adjudication-contract-r4.json) | `PENDING FUTURE OOS` | 揭盲后由确定性裁决器逐项验证收益、年化、DD、胜率、Sharpe、PF、数量、月份、压力、集中度、历史稳定与基线胜负 |
| 10 | 数据、测试、因子、OOF、比较、逐笔、绩效、冻结、主账、一次性报告、外部复现规格 | [家族入口](../README.md)、[Core ledger](../binance-1h-mhcsml-core-ledger.md)、[Decision log](../decision-log.md)、[外部复现规格](../specs/binance-1h-mhcsml-v1-r4-external-reproduction-spec-2026-07-19.md) | `PARTIAL` | 尚缺 prospective revealed legs、decisions、最终绩效/压力和一次性 OOS 中文验收报告；这些在揭盲前不应存在 |

## 已冻结的不可变合同

- 版本：`BIN-1H-MHCSML-V1 freeze R4`
- 主 SHA256：`64ee12688980673aa2cd348a961553c89d246d1f338eba0192ddcbfdd095fe11`
- 信号窗：`2026-07-19 00:00 <= K0 ts < 2026-10-19 00:00 UTC`
- 最早揭盲：`2026-10-20 21:05 UTC`
- 决策/持有：`4h / 48h / short-only`
- 特征：return/MAE/squeeze 使用 stable-full `235`；确认模型使用 compact `86`
- seeds：`7/17/29/42`
- allocator：`utility_z>=1.75`、最多 `5` 腿、允许空仓
- exposure：gross cap `37.5%`；每批 sleeve `3.125%`；批内等权
- 成本：双边 `0.28%` 加实际 funding；压力成本 `1.5x`
- 最终裁决合同 SHA256：`a5bb2d45f4edd5289990315ee67a5953b16ead61436fc438dc4b4bb27407f433`；测试逐项覆盖 15 个 OOS 门槛的阈值边界和三段固定月份
- 条件式 3x 风险合同 SHA256：`0cc877cd934173af033e355462e627b6a64ddcfa0c1fedb0c9b408f145a0b4ce`；仅预先冻结审计方法，尚未获基础策略授权执行

## 最终一次性验收清单

揭盲任务只有在以下证据全部存在且一致时，才允许考虑结束目标：

1. 552 个链节点时间连续，全部状态仅为 `FROZEN_ON_TIME` 或 `MISSED`，链、快照和 master SHA 全部通过；
2. 最后一条合法 48h 腿已经成熟，普通 K 线和 funding 数据覆盖退出时点；
3. 一次性 reveal receipt 和报告只生成一次；
4. R4、Ridge、规则三者均按同一成本、持有期、仓位和信号窗报告；
5. 逐腿和决策文件 SHA 固化，收益公式仍为 `1-exit/entry-cost+funding`；
6. 所有硬门槛逐项给出布尔值，不允许只给综合分数；
7. 历史因子消融和 tail IC `PASS` 与 OOS 报告合并解释，但不事后新增门槛；
8. 若任一门槛失败，写 `HARD-GATE-FAILED / not promoted / not live-ready`；
9. 若基础版本全部通过，才执行已经 outcome-blind 冻结的 3x 保证金、逐时 mark-to-market、维持保证金与强平风险审计；
10. 完成 requirement-by-requirement 复核后，才可把长期目标标记为完成。

## 当前运行快照

截至 `2026-07-22 05:15 UTC`：应有节点 `20`，实际节点 `20`，其中 `FROZEN_ON_TIME=2`、`MISSED=18`、缺失 `0`；链尾 SHA256 为 `5deaa2d7a94c183761b949e0baaf507f356597a70185d7e79b57f4d3477efc18`。`17` 个新增 `MISSED` 来自目标 `usageLimited` 期间自动任务暂停，已按合同补记而未回填；恢复后的 `2026-07-22 04:00 UTC` 节点已在截止前冻结。最新整轮同步当前 `530/530` 个合约，OHLCV/mark 无 stale 或 missing symbol、重复键为 `0`；feature-only 面板含 `150` 个币、`1,200` 行、无 label 列、无冻结特征缺失，两个 manifest 均为 `PASS` 且未读取 outcome。该快照只证明治理链和数据输入恢复完整，不证明策略盈利。
