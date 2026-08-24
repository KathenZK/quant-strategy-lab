# BIN-1D-GMA7T-V0 Genericization Audit

## 结论

`HYPE-1D-MA7-ABT-V7.1` 包含一个可提出跨资产检验的 `SMA7 + reclaim + ATR-normalized slope + ATR hysteresis` 趋势核心，但 V7.1 不是现成通用参数：多空独立参数来自 HYPE 单资产各 `20,000` 组搜索，最终 `041` 又在最后 `90d` 揭示后筛选；OAPP 在 HYPE development/validation 形成、一次性 H 失败；PEHC 专门修复该 HYPE OAPP 截断 forced-short 的状态链，历史只有 6 次机会/5 次接受；V7 的 short cooldown=3 也是 432 日已揭示邻域赢家。

因此 audit 把“结构上可跨资产解释”与“参数值已证实通用”严格分开。A 只表示有通用机制解释，不表示沿用 HYPE 数值；B 表示 HYPE-specific 或 post-hoc specialization；C 表示风险/执行层。

## 逐项分类与 v0 裁决

| 模块 | 分类 | 仓库证据 | Generic v0 |
| --- | --- | --- | --- |
| `SMA7 / ATR7` | A + C | 原始搜索固定 SMA7，ATR7 用于可比斜率、迟滞与保护；均线长度没有在 `041` 搜索内事后挑选 | 保留 7/7；只在冻结后做 6/8 稳定性读数 |
| close reclaim | A | 搜索报告把 reclaim 解释为“从 MA7 附近重新回趋势方向”；V6 消融中删除 short/both reclaim 分别降到 `-16.85%/-9.32%` 且 MDD 约 `-68%` | 保留，long/short 严格镜像 |
| slope gate | A；HYPE 数值来源带 B 风险 | 移除全部 slope 为 `-30.96%/-67.33%`；`0.02 ATR` 比阈值降 0 更稳，但证据来自 HYPE 已揭示历史 | 保留唯一共同 `lookback=1 / threshold=0.02 ATR`；2 日 short lookback 不迁移 |
| long/short 独立参数 | B | 多空各搜索 `20,000` 组；最终 `041` 为 post-reveal；short 仅 6 笔，统计强度低 | 删除不对称，全部信号/退出/风控镜像 |
| short entry buffer `0.10 ATR` | B | HYPE 消融显示降 0 会伤害该资产路径，但没有跨资产结构理由；属于单资产选择性阈值 | v0 两侧均为 `0`，避免只给 short 加 post-hoc 门槛 |
| exit hysteresis `0.75 ATR` | A + C | 机制目标是避免首次穿越即 churn；V3 消融支持两侧迟滞有实际路径贡献 | 两侧保留 `0.75 ATR` |
| short slope exit | B | 只存在 short；lookback 变化显著改写少数 HYPE episode，未给出通用 long/short 市场结构依据 | 删除；两侧只用镜像 hysteresis + ATR stop |
| long trail `1.5` / short trail `4.0` | C，数值不对称为 B | ATR trailing 是通用风险层；`1.5/4.0` 来自 HYPE 分腿搜索，short trail 在早期 425 日甚至未触发 | 合并为两侧 `1.5 ATR`，选择已有较紧保护值，不新增优化值 |
| long 无 hard stop / short `1.5 ATR` | C，缺失 long 保护为执行 blocker | 早期报告明确“多头首个持仓日无 hard stop”为 live-readiness gap；short hard stop虽样本早期 dormant，V6 移除仍损失 `14.85pp` | 两侧均启用 entry-fixed `1.5 ATR` hard stop |
| max hold `90d / 20d` | C 外形、B 数值 | V3 消融中两侧 max hold 在 425 日逐笔零影响；天数来自单资产搜索且无通用不对称理由 | 删除。v0 由趋势破坏或 ATR 风险退出，不截断长趋势 |
| cooldown `2d / 3d` | C 外形、B 数值与选择 | long cooldown 主路径逐笔等价；short cooldown 对少数 HYPE episode敏感，3/8/10 日都在已揭示历史增收；V7 的 3 日来自邻域最高收益点 | v0 为 `0/0`；fresh reclaim 本身提供事件重置。扰动也不搜索 cooldown |
| OAPP long MFE fraction exit | B | 957 个单模块/组合搜索后形成；一次性 H 中虽改善 long，却截断随后 `+16.87%` forced short，候选低于 V4 | 删除 |
| short RSI6 `20×2` | B | 只针对 short；D 有贡献、V/H 0 触发，阈值 25 又成为 post-reveal 小幅赢家 | 删除 |
| PEHC shadow/handoff | B | PEHC 是对 OAPP 特定失效链的 materially new 修补；490 arms 收敛为 13 路径，只有 6 次机会/5 次接受且 1 次负贡献 | 删除；同时删除 forced reversal/shadow 状态 |
| fee/slippage/funding/next-open | C | 家族共享假设与仓库默认 Binance 成本；closed-bar/next-open、真实 1h stop replay 是可执行性要求 | 原样保留并同时给 gross/net/8bps |
| fixed `1x`/single position/no pyramiding | C | V7.1 冻结身份；2x/3x 历史诊断有明显尾部风险，不得用杠杆制造迁移 | 单币保留 `1x`；组合缩放单独报告 |

## 关键证据链

- [多空分离搜索](../../../hype/1d-ma7-asymmetric-body-trend/diagnostics/hype-1d-ma7-abt-separated-trend-search-2026-08-04.md)：明确 `20,000 + 20,000` 分腿搜索、最后 90 日 post-reveal 与仅 6 笔 short。
- [V3全参数消融](../../../hype/1d-ma7-asymmetric-body-trend/ablations/hype-1d-ma7-abt-v3-full-parameter-ablation-2026-08-07.md)：reclaim/slope/迟滞/long trail 的路径作用，以及 hard stop/max hold/long cooldown 的 dormant 风险合同身份。
- [V4 cooldown消融](../../../hype/1d-ma7-asymmetric-body-trend/ablations/hype-1d-ma7-abt-v4-cooldown-ablation-2026-08-07.md)：short cooldown 对 5 个已知 episode 高敏感，long cooldown主路径等价。
- [OAPP消融](../../../hype/1d-ma7-asymmetric-body-trend/ablations/hype-1d-ma7-opportunity-aware-profit-protection-ablation-2026-08-10.md)：OAPP/short RSI 的 HYPE development 与 H 失效链。
- [PEHC消融](../../../hype/1d-ma7-asymmetric-body-trend/ablations/hype-1d-ma7-profit-exit-handoff-continuity-ablation-2026-08-10.md)：专门状态修复、事件样本与已暴露边界。
- [V6全参数消融](../../../hype/1d-ma7-asymmetric-body-trend/ablations/hype-1d-ma7-abt-v6-full-parameter-ablation-2026-08-11.md)：V7 short cooldown 与 RSI 阈值都来自已揭示邻域；reclaim/slope 仍是主要选择性核心。
- [V7.1清理消融](../../../hype/1d-ma7-asymmetric-body-trend/ablations/hype-1d-ma7-abt-v7-full-parameter-cleanup-ablation-2026-08-11.md)：V7.1 只删 dormant/schema 字段，未 genericize 任何实际行为。
- [原 V7.1 Top30 成交额迁移失败](../../../hype/1d-ma7-asymmetric-body-trend/diagnostics/hype-1d-ma7-abt-v7-1-top30-binance-usdt-u-margin-transfer-2026-08-12.md)：固定 HYPE 完整参数在另一横截面中心为负，只作为对照，不参与 v0 参数选择。

## 冻结声明

本 audit 与 [v0规格](../specs/binance-1d-generic-ma7-trend-v0-spec.md)、[机器配置](../configs/binance-1d-generic-ma7-trend-v0.json) 在本任务 market-cap universe 回测生成前落盘。后续如果 v0 失败，结论是该冻结 generic core 未获支持；不得用单币赢家、扰动赢家、延长/缩短 hold/cooldown 或重新加入 OAPP/PEHC 救援同一已揭示结果。
