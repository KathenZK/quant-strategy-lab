# HYPE-15M-SMA-XS 数据冻结（2026-07-28）

## 数据合同

| 项目 | 值 |
| --- | --- |
| 市场 | Binance USD-M Futures `HYPEUSDT` perpetual |
| 周期 | `15m` 闭合 K |
| 数据范围 | `2025-05-30 10:30 UTC` 至 `2026-07-28 07:45 UTC` |
| 全量行数 | 40,694 |
| prefit 行数 | 31,958 |
| reused locked OOS | `[2026-04-28 08:00, 2026-07-28 08:00 UTC)`，8,736 行 |
| prefit validation | `[2026-01-28 08:00, 2026-04-28 08:00 UTC)` |
| funding 事件 | 2,542 |

## 质量审计

缺口、重复时间戳、关键字段空值、未闭合 K、OHLC 关系异常、非正价格、负成交量和 raw/normalized 字段差异均为 0；`blocker_count=0`。完整哈希和逐字段计数见 [机器冻结清单](../artifacts/hype_15m_sma_xs_dataset_freeze.json)。

## 成本与执行

- 信号只读取第 `t` 根闭合 K，第 `t+1` 根 open 成交。
- 单净仓、1x；每次 fill fee `0.001`，adverse slippage `0.0004`，另计真实 Binance funding。
- slope exit 后不允许在同一均线 regime 内重入，直到出现新交叉。
- 本次是精确机制诊断，不含固定止损，不构成 live-ready 风控合同。

## OOS 说明

最后三个月在 37 个候选定义冻结后一次性揭示；由于其他 HYPE 家族已经研究过重叠日期，只能称 reused OOS，不能声称 pristine OOS。
