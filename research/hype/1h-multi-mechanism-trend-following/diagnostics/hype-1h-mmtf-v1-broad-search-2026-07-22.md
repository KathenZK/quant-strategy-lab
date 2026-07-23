# HYPE-1H-MMTF V1 多机制广搜 — 2026-07-22

## 结论

本轮在 locked OOS 之外完成五类纯趋势机制广搜并冻结 V1。`48,000` 个候选中，prefit 硬门槛通过 `0`、内部 90 天 validation 代理通过 `2`、两者联合通过 `0`。因此没有达标策略；V1 是后续消融的 diagnostic baseline。

## 搜索协议

- Selection window：`[2025-05-30 10:00 UTC, 2026-04-22 10:00 UTC)`；locked OOS 未加载。
- 机制：Donchian breakout、Keltner breakout、EMA pullback continuation、time-series momentum、range-expansion breakout。
- 第一阶段 `30,000` 个确定性随机候选；第二阶段围绕多目标 frontier 的 `18,000` 个邻域候选。
- 同时保留 annual factor、win rate、MDD、trade count、validation 稳定性和机制多样性；frontier 保留 `2,909` 行。
- 执行：K+1 open、单净仓、stop-first、gap-open、fee `0.001/fill`、slippage `4 bps/fill`、真实 funding、leverage `<=3x`。

## V1 选择结果

V1 为双向 120h time-series momentum，使用 EMA96/120 regime、ATR48 bracket 和固定 `2x`。Prefit 为 `4.8034x / 20.04% MDD / 82.26% / 62 trades`；内部 validation 为 `10.3214x / 9.72% / 87.50% / 16 trades`。Prefit 年化与回撤均未过硬门槛。

机器证据：

- [搜索摘要与冻结配置](../artifacts/hype_1h_mmtf_v1_search_2026-07-22.json)
- [多目标 frontier](../artifacts/hype_1h_mmtf_v1_search_2026-07-22_frontier.csv)
- [V1 prefit 逐笔交易](../artifacts/hype_1h_mmtf_v1_search_2026-07-22_prefit_trades.csv)
- [V1 prefit 权益路径](../artifacts/hype_1h_mmtf_v1_search_2026-07-22_prefit_equity.csv)
- [冻结规格](../specs/hype-1h-mmtf-v1-original-baseline-spec.md)
