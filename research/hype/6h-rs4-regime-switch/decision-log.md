# HYPE-6H-RS4-Regime-Switch Decision Log

## 2026-06-26：启动同事 RS4 策略独立复现

- 输入材料：`/Users/ZK/Downloads/RS4-EXPLAINED-RS4策略详细图解.html`。
- 研究归属：新建 `HYPE-6H-RS4-Regime-Switch`，不并入既有 `15m`、`5m` 或 `1m` family。
- 初始状态：diagnostic only / not promoted。
- 原因：策略说明声称的核心证据包含 Bybit 2024-12 全史和 16 个 melt-leg 变体选择，但本仓库当前可直接复现的是 Binance HYPEUSDT perpetual `5m` normalized 数据湖聚合 `6h`。
- 硬性要求：任何收益结论都必须伴随数据质量、next-open 执行、成本、资金费和关键消融；若无法复核 raw-normalized equality 或 Bybit 全史，不能提升为 paper/live candidate。
