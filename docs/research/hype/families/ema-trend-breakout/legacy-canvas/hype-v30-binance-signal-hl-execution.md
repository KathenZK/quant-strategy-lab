# HYPE V30 Binance Signal + HL Execution

> 迁移说明：本文由 legacy Cursor Canvas `hype-v30-binance-signal-hl-execution.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-TB legacy Canvas。

用 Binance 生成 V30 信号和 ATR 参数，在 Hyperliquid 上按 HL K 线执行入场、止盈、止损、timeout 与 funding。

Source: local Binance and Hyperliquid HYPE 15m data lake, aligned 2025-08-13 to 2026-06-01 UTC.

## 结论

| 项目 | 判断 | 证据 |
| --- | --- | --- |
| 核心结论 | Binance 信号 + HL 执行没有失效 | +1365.06% / -16.38%，略高于同区间 Binance native |
| 信号来源 | EMA/ADX/volume/1h确认/ATR 全部用 Binance | 执行价、止盈止损触发、funding 用 Hyperliquid |
| 交易路径 | 入场信号数量不变 | Cross 71 笔，Binance native 71 笔；多 / 空都是 52 / 19 |
| 主要风险 | 常态跨所价差很小，但极端日有异常 | p99 abs spread 0.1727%，最大 8.1866% 出现在 2025-10-10 21:15 UTC |

## 场景对比

| 场景 | 收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 多 / 空 | 止盈 / 指标 / 止损 / timeout |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Binance native | +1267.92% | -16.81% | 5.29 | 71 | 84.29% | 52 / 19 | 56 / 11 / 2 / 1 |
| HL native | +517.37% | -24.60% | 3.57 | 67 | 77.27% | 46 / 21 | 49 / 10 / 4 / 3 |
| Binance signal + HL execution | +1365.06% | -16.38% | 5.27 | 71 | 85.71% | 52 / 19 | 55 / 10 / 2 / 3 |

## 固定窗口

| 窗口 | Binance native 收益 | Cross 收益 | Binance native 回撤 | Cross 回撤 |
| --- | --- | --- | --- | --- |
| 7d | +0.09% | +0.03% | -2.66% | -2.74% |
| 30d | +47.42% | +47.35% | -15.07% | -15.41% |
| 90d | +168.67% | +169.45% | -15.07% | -15.41% |
| 180d | +585.35% | +572.19% | -16.81% | -16.38% |
| Full | +1267.92% | +1365.06% | -16.81% | -16.38% |

## 滚动窗口

| 场景 | 窗口 | 样本数 | 正收益数 | 最低收益 | 中位收益 | 平均收益 | 最差回撤 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Binance native | 30天 | 38 | 36 | -8.10% | +27.73% | +30.78% | -18.36% |
| Binance signal + HL execution | 30天 | 38 | 36 | -7.53% | +28.51% | +31.74% | -20.90% |
| Binance native | 90天 | 29 | 29 | +20.45% | +109.35% | +125.54% | -16.81% |
| Binance signal + HL execution | 90天 | 29 | 29 | +29.82% | +117.80% | +128.99% | -16.38% |

## 退出归因

| 场景 | 退出方式 | 次数 | 收益合计 | 单笔平均 | 胜率 | 平均持仓K | 平均MAE | 平均MFE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Binance native | Take profit | 56 | +333.68% | +5.96% | 100.00% | 35.96 | -1.30% | +3.36% |
| Binance native | Indicator | 11 | -34.05% | -3.10% | 27.27% | 27.64 | -3.31% | +0.98% |
| Binance native | Stop | 2 | -21.80% | -10.90% | 0.00% | 75.50 | -5.06% | +1.74% |
| Binance signal + HL execution | Take profit | 55 | +333.81% | +6.07% | 100.00% | 34.73 | -1.23% | +3.45% |
| Binance signal + HL execution | Indicator | 10 | -33.71% | -3.37% | 20.00% | 28.70 | -3.58% | +0.87% |
| Binance signal + HL execution | Stop | 2 | -22.76% | -11.38% | 0.00% | 75.50 | -4.97% | +1.80% |
| Binance signal + HL execution | Timeout | 3 | +3.61% | +1.20% | 100.00% | 192.00 | -4.33% | +2.49% |

## 跨所价差

| 指标 | 数值 | 说明 |
| --- | --- | --- |
| Close spread median | +0.0120% | HL close / Binance close - 1 |
| Close spread p95 abs | 0.1297% | 常态价差很小 |
| Close spread p99 abs | 0.1727% | 多数入场环境可接受 |
| Close spread p99.9 abs | 0.2421% | 尾部仍不大 |
| Close spread max abs | 8.1866% | 2025-10-10 21:15 UTC 极端异常 |

## 数据口径

| 项目 | 说明 |
| --- | --- |
| 统计窗口 | 2025-08-13 01:00 → 2026-06-01 03:00 UTC |
| 共同 15m bars | 29,641 |
| 信号源 | Binance HYPE/USDT 15m；V30 EMA/ADX/volume/1h confirm/ATR |
| 执行源 | Hyperliquid HYPE/USDC 15m close/high/low；本地 HL funding forward-fill |
| 策略口径 | 无 DI 入场、无 DD 降仓、ADX<22 连续 3 根退出、2ATR MFE 后关闭指标退出、固定 entry ATR 4.30 止盈 / 9ATR 止损 |
| 建议保护 | 实盘可加跨所价差保护，例如 abs(HL/Binance - 1) 超过 0.3%-0.5% 暂停新开仓 |
