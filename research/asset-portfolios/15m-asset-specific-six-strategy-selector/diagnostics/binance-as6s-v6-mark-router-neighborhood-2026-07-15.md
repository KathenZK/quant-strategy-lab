# BIN-15M-AS6S V6 mark抢占路由邻域（2026-07-15）

对完整mark账户重放独立扰动scale、抢占阈值、强度差和最短持仓。

- scale硬门槛通过率：85.71%。
- scale含-18.5%缓冲通过率：57.14%。
- 路由参数硬门槛通过率：100.00%。
- 路由参数含缓冲通过率：100.00%。

| threshold | margin | min hold | hard pass | 缓冲通过 | 分数变化 |
|---:|---:|---:|---|---|---:|
| 0.70 | 0.05 | 1h | `True` | `True` | -0.580 |
| 0.80 | 0.05 | 1h | `True` | `True` | -1.289 |
| 0.75 | 0.00 | 1h | `True` | `True` | +0.365 |
| 0.75 | 0.10 | 1h | `True` | `True` | +0.000 |
| 0.75 | 0.05 | 0h | `True` | `True` | +0.011 |
| 0.75 | 0.05 | 2h | `True` | `True` | -0.154 |
| 0.75 | 0.05 | 4h | `True` | `True` | -0.246 |

结构化结果：[`binance_as6s_v6_mark_router_neighborhood_2026-07-15.json`](../artifacts/binance_as6s_v6_mark_router_neighborhood_2026-07-15.json)。
