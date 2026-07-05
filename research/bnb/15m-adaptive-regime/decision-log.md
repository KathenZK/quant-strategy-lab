# BNB-15M-Adaptive-Regime Decision Log

## 2026-07-05：从 1h NO-GO 转向独立 15m 家族

- `BNB-1H-Adaptive-Regime` 完成约 `1,000,000` 随机配置与 `500,000` 邻域搜索，prefit hard-gate 命中为 `0`；冻结 primary 的 locked OOS 为负，明确 `NO-GO`。
- 不在失效的 1h family 内继续挤参数，另建 `BNB-15M-Adaptive-Regime`。
- 15m 研究保持原硬门槛和最近三个月 locked OOS，不把 OOS 用作第二轮调参集。
- 搜索优先覆盖 BNB 自身的波动压缩、成交量脉冲、结构修复与多周期状态，不机械复制其他币种的最终参数。
