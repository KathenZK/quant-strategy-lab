# HYPE-D15-HTO Decision Log

## 2026-07-29：建立独立家族并锁定最近三个月 OOS

建立 `HYPE-1D-15M-Hierarchical-Trend-Opportunity` 独立研究线；完整 UTC 日线仅确定允许方向，`15m` 负责入场与仓位退出。锁定 OOS 为 `[2026-04-29 03:00 UTC, 2026-07-29 03:00 UTC)`，在原始策略冻结、消融和调优完成前不得读取该区间绩效。

## 2026-07-29：冻结 V1、V2 clean-equivalent 与 prefit 调优 V3

50,000 组原始广搜冻结 V1；完成 34 个参数槽位和 10 个组件消融后，删除 path-equal/dormant 自由度并冻结逐笔等价 V2；再在 clean 面搜索 120,000 组并冻结 V3。V3 prefit 年化与回撤已失败，参数邻域和真实 1m 相位也未通过；证据见 [V1 消融](ablations/hype-d15-hto-v1-full-ablation-2026-07-29.md) 与 [V3 prefit 稳健性](diagnostics/hype-d15-hto-v3-prefit-robustness-2026-07-29.md)。

## 2026-07-29：一次性揭示 locked OOS，不晋升

在参数冻结且 prefit 审计完成后首次、一次性揭示最近三个月 OOS。V3 OOS 净亏损、胜率和回撤均未达到用户门槛，且零成本仍亏损；V1-V3 登记为研究版本，但保持 `registered / not promoted / not live-ready`，不创建 live spec、不交接 runner、不依据已揭示 OOS 救参数。证据见 [最终 OOS 报告](diagnostics/hype-d15-hto-v3-locked-oos-final-2026-07-29.md)。
