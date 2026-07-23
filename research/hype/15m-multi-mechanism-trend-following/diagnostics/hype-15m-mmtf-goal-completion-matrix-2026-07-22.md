# HYPE-15M-MMTF 目标验收矩阵 — 2026-07-22

| 目标项 | 权威证据 | 结论 |
| --- | --- | --- |
| 独立家族与路由 | family README、core ledger、两级 research index | PASS |
| 数据刷新、raw/normalized、funding、closed bar | [数据冻结](hype-15m-mmtf-data-freeze-2026-07-22.md) | PASS，0 blocker |
| 最近三个月锁定且搜索阶段未访问 | freeze manifest、V1/tune/robustness JSON | PASS |
| 48k 多机制原始搜索与多目标前沿 | [V1 广搜](hype-15m-mmtf-v1-broad-search-2026-07-22.md) | PASS，target pass 0 |
| V1 登记 | core ledger、V1 spec | PASS，registered |
| 全接线消融与 dormant 删除 | [V1 消融](../ablations/hype-15m-mmtf-v1-full-ablation-2026-07-22.md) | PASS |
| V2 clean-equivalent | exact trade signature | PASS |
| 仅调优有效表面 | 60k clean tune + 240 rolling audit | PASS，target pass 0 |
| V3 冻结后一次性揭示 | reveal guard + config/code hashes | PASS，不得重跑/回调 |
| full annual factor >=20x | final audit | FAIL：`1.822x` |
| full WR >=80% | final audit | PASS：`89.26%` |
| full MDD <20% | final audit | FAIL：`21.88%` |
| locked OOS 三项硬门槛 | final audit | FAIL：`0.526x / 76.19% / 21.88%` |
| 4/8bps、K+2、funding stress | robustness/reveal JSON | FAIL：8bps 与 delay 均破门槛 |
| 1m phase `{0,5,10}` | robustness JSON | FAIL：两个 shifted phase 均亏损 |
| MC/参数邻域/极端窗口 | robustness JSON | PARTIAL：邻域有形状通过项，但 MC 尾部不足 |
| 1x/2x/3x | reveal JSON | FAIL：无一达到 annual；3x MDD 超限 |
| 拒单/断流/重启/kill switch | final audit | NOT PROVEN：无 runner，不得 promotion |
| 最终状态 | core ledger + final audit | V1-V3 registered；HARD-GATE-FAILED / not promoted / not live-ready |

本矩阵满足任务完成路径 B：主要机制和参数空间已合理覆盖，最近三个月只揭示一次，最接近前沿、差距、失败原因和下一机制建议均已提交；没有放宽门槛或隐藏负面切片。

