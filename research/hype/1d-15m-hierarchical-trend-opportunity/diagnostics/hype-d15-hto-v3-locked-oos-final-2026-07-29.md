# HYPE-D15-HTO-V3 最近三个月 locked OOS 一次性揭示

- OOS：`[2026-04-29T03:00:00+00:00, 2026-07-29T03:00:00+00:00)`。
- 规则：冻结后首次且唯一一次读取；OOS 从空仓、权益 1.0 开始，不用于任何后续调参。
- 成本：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、实际资金费。

## OOS 结果

净收益 `-29.76%`，年化倍数 `0.242x`，胜率 `29.41%`，MDD `36.75%`，`17` 笔。
同期 1x 买入持有净收益 `35.69%`，策略超额 `-65.45%`。

## 全冻结样本连续回放

净收益 `22.50%`，年化倍数 `1.191x`，胜率 `52.24%`，MDD `36.75%`，`67` 笔。

## 决策

`HYPE-D15-HTO-V3` 未通过 OOS 三项硬门槛。
prefit 已在年化、回撤、参数邻域和相位上失败，因此无论 OOS 单段表现如何，
本家族均保持 `registered / not promoted / not live-ready`；不得依据已揭示 OOS 救参数。

## 证据

- [机器摘要](../artifacts/hype_d15_hto_v3_locked_oos_reveal_2026-07-29.json)
- [OOS 逐笔成交](../artifacts/hype_d15_hto_v3_locked_oos_trades_2026-07-29.csv)
- [OOS 权益路径](../artifacts/hype_d15_hto_v3_locked_oos_equity_2026-07-29.csv)
- [最近切片](../artifacts/hype_d15_hto_v3_final_slices_2026-07-29.csv)
