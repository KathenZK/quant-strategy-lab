# HYPE-D15-HTO-V3 prefit 稳健性审计

- 本报告只读取 locked OOS 之前的数据；未使用 OOS 排名或调参。
- 成本基线：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、实际资金费。

## 基线

年化倍数 `1.838x`，净收益 `74.40%`，胜率 `60.00%`，MDD `20.98%`，`50` 笔。年化与回撤均未通过用户硬门槛。

## 稳健性

非重叠 30 日窗口 `7` 组，正收益占比 `71.43%`，零交易窗口 `0`。
交易 bootstrap `10000` 次：亏损概率 `3.42%`，MDD 95 分位 `30.58%`。
真实 1m 重聚合相位：+5m 收益 6.31% / MDD 41.00%；+10m 收益 -8.81% / MDD 28.57%。

## 结论

`HYPE-D15-HTO-V3` 在揭示 OOS 前已经失败：没有达到 `10x` 年化，且 prefit MDD 超过 `20%`。
因此它只能作为 `registered / not promoted / not live-ready` 的冻结研究版本；
后续一次性 OOS 只用于完成用户指定验证，不得用于救参数。

## 证据

- [机器摘要](../artifacts/hype_d15_hto_v3_prefit_audit_2026-07-29.json)
- [场景 CSV](../artifacts/hype_d15_hto_v3_prefit_scenarios_2026-07-29.csv)
- [CPCV CSV](../artifacts/hype_d15_hto_v3_prefit_cpcv_2026-07-29.csv)
- [参数邻域 CSV](../artifacts/hype_d15_hto_v3_prefit_neighbors_2026-07-29.csv)
