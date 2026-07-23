# HYPE-1H-MMTF 目标验收矩阵 — 2026-07-22

本矩阵逐项核对本轮目标。研究流程已完成，但策略绩效目标明确失败；完成状态的含义是已得到可审计的 NO-GO，而不是宣称找到达标策略。

| Requirement | Evidence | Result |
| --- | --- | --- |
| 全新独立 HYPEUSDT 1h 趋势家族 | [README](../README.md)、[主账](../hype-1h-mmtf-core-ledger.md)、顶层与 HYPE 路由 | 完成；未继承 1H-AR 身份/参数/结论 |
| 数据质量优先 | [数据冻结](hype-1h-mmtf-data-freeze-2026-07-22.md) | `10,032` 根；missing/duplicate/null/mismatch/unclosed 全为 `0` |
| 搜索前冻结最近三个月 OOS | [freeze JSON](../artifacts/hype_1h_mmtf_dataset_freeze_2026-07-22.json) | 完成；`[2026-04-22 10:00, 2026-07-22 10:00) UTC` |
| 闭合 K、K+1、成本、funding、stop-first、gap-open、单净仓、`<=3x` | [engine](../scripts/mmtf_engine.py)、[tests](../../../../tests/test_hype_1h_mmtf.py)、[prefit robustness](../artifacts/hype_1h_mmtf_v3_prefit_robustness_2026-07-22.json) | 回测合同完成；runner 运维证据缺失，故 not live-ready |
| 多机制广搜与多目标 frontier | [V1 广搜](hype-1h-mmtf-v1-broad-search-2026-07-22.md) | `48,000` 候选、5 机制、`2,909` frontier；联合通过 `0` |
| 冻结登记原始 V1 | [V1 spec](../specs/hype-1h-mmtf-v1-original-baseline-spec.md)、[主账](../hype-1h-mmtf-core-ledger.md) | 完成；registered diagnostic baseline / NO-GO |
| 有效组件与 dormant 参数消融 | [消融报告](../ablations/hype-1h-mmtf-v1-full-ablation-2026-07-22.md) | `18` 行；识别并删除 fixed/dormant/path-equal 槽 |
| clean-equivalent V2 | [V2 spec](../specs/hype-1h-mmtf-v2-clean-equivalent-spec.md) | 完成；V1/V2 逐笔 SHA256 exact equal，20 槽降至 12 参数 |
| 仅在 selection 数据调优 | [clean tune](hype-1h-mmtf-v2-clean-tune-2026-07-22.md) | `60,000` 候选 + `240` rolling audit；OOS 未参与 |
| 冻结 V3 | [V3 spec](../specs/hype-1h-mmtf-v3-tuned-spec.md) | 完成；配置与代码 SHA256 在 reveal 前冻结 |
| MC、邻域、K+2、8bps、极端窗口、相位 | [prefit robustness JSON](../artifacts/hype_1h_mmtf_v3_prefit_robustness_2026-07-22.json) | 全部执行；K+2、8bps、相位与 MC tail 失败 |
| 唯一一次 OOS 揭示 | [reveal JSON](../artifacts/hype_1h_mmtf_v3_locked_oos_reveal_2026-07-22.json) | 完成；脚本在 reveal 产物存在时拒绝重跑 |
| Prefit/OOS/full/recent slices/PF/成本报告 | [最终审计](hype-1h-mmtf-v3-final-audit-2026-07-22.md) | 完成；机器证据含逐笔交易与权益路径 |
| 完整样本 `>=20x / >=80% / <20% / >=60` | [最终审计](hype-1h-mmtf-v3-final-audit-2026-07-22.md) | 失败：`5.4102x / 87.67% / 33.07% / 73` |
| Locked OOS `>=20x / >=80% / <20% / >=15` | [最终审计](hype-1h-mmtf-v3-final-audit-2026-07-22.md) | 失败：`1.7887x / 84.62% / 33.07% / 13` |
| 不因失败改口径或追 OOS | [decision log](../decision-log.md) | 完成；最终结论固定为 NO-GO / not promoted / not live-ready |

最终判定：研究目标的规定流程和失败分支均已完成；没有候选满足硬门槛，不建议 promotion review。
