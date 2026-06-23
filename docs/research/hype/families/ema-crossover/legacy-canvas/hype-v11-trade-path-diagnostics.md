# HYPE V11 Trade Path Diagnostics

> 迁移说明：本文由 legacy Cursor Canvas `hype-v11-trade-path-diagnostics.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-EMA-X legacy Canvas。

对 V6、V8、V8 clean、V10 逐笔交易做路径归因，判断当前瓶颈是入场、退出还是再入场。

Source: Binance HYPEUSDT perp 15m data lake · 2025-05-30 10:30 UTC → 2026-06-01 03:00 UTC · reports/hype_trade_path_diagnostics_v11.json.

> **核心结论**
> 当前最大问题不是缺少 RSI/KDJ/MACD，而是退出和再入场结构：V8/V8 clean 有 56.7% 交易属于早退后继续同向运行，V10 虽然更干净但仍有 54.9% 早退。下一步应该做 warning/confirm 双阶段退出和结构化再入场。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| V8 clean 早退率 | 56.70% |
| V8 clean 坏入场率 | 27.84% |
| V8 clean 好捕获率 | 10.31% |
| V10 交易数 | 51 |

## 策略路径汇总

| 策略 | 交易数 | 胜率 | 平均原始收益 | 平均 MFE | 中位捕获率 | 早退率 | 坏入场率 | 好捕获率 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V6 dynamic 3x | 49 | 69.39% | +2.01% | +5.40% | 25.79% | 59.18% | 30.61% | 4.08% |
| V8 baseline | 97 | 71.13% | +1.08% | +3.03% | 57.18% | 56.70% | 27.84% | 10.31% |
| V8 clean wick055 | 97 | 71.13% | +1.10% | +3.04% | 57.18% | 56.70% | 27.84% | 10.31% |
| V10 osc combo | 51 | 70.59% | +2.07% | +5.12% | 29.56% | 54.90% | 29.41% | 9.80% |

### 问题分类数量

X 轴：策略；Y 轴：交易数。分类来自 MFE、捕获率、退出后 96 根 K 的同向延续。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | early_exit | bad_entry | good_capture |
| --- | --- | --- | --- |
| V6 | 29 | 15 | 2 |
| V8 | 55 | 27 | 10 |
| V8 clean | 55 | 27 | 10 |
| V10 | 28 | 15 | 5 |

### 诊断结构

| 策略 | 早退 | 坏入场 | 好捕获 | 拿过头 | 混合 | 解读 |
| --- | --- | --- | --- | --- | --- | --- |
| V6 dynamic 3x | 29 | 15 | 2 | 1 | 2 | V6 交易少，但仍有大量退出后继续同向趋势，说明 ADX trend_break 太早终止了一些趋势段 |
| V8 baseline | 55 | 27 | 10 | 0 | 5 | V8 的量能衰竭把趋势切成更多段，早退出数量最多，但靠再入场提高了收益 |
| V8 clean wick055 | 55 | 27 | 10 | 0 | 5 | wick_min 改善的是少数退出质量，整体结构问题仍是频繁早退和再入场 |
| V10 osc combo | 28 | 15 | 5 | 1 | 2 | V10 最接近趋势持有：交易数接近 V6，收益更高，但仍有 28 笔早退 |

## 典型早退样本

早退定义：盈利退出后，后续 96 根 15m K 内继续同向运行超过 2ATR。

| 策略 | 交易 | 退出原因 | 实际收益 | MFE | 退出后延续 | 延续 ATR | 问题 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V8 clean | 2026-01-26 long | volume_exhaustion | +2.99% | +3.48% | +29.45% | 43.8 ATR | 典型问题：量能衰竭太早把大趋势第一段卖掉 |
| V8 clean | 2026-01-27 long | volume_exhaustion | +1.33% | +3.27% | +27.45% | 42.3 ATR | 同一趋势内反复短线退出，后续仍大幅延续 |
| V6 | 2025-09-08 long | trend_break | +2.19% | +4.51% | +8.93% | 18.7 ATR | ADX trend_break 在趋势整理中提前退出 |
| V10 | 2025-09-21 short | trend_break | +8.43% | +13.66% | +9.94% | 17.3 ATR | 趋势仍在，但趋势坏掉定义先触发 |

## 典型坏入场样本

坏入场定义：亏损交易且 MAE 超过 2ATR，说明不是出场慢，而是进场后没有有效跟随。

| 策略 | 交易 | 退出原因 | 实际收益 | MFE | MAE ATR | 问题 |
| --- | --- | --- | --- | --- | --- | --- |
| V8 clean | 2026-05-15 long | trend_break | -2.99% | +1.39% | 16.9 ATR | 入场后很快大幅不利，说明 regime 内再入场吸入了晚期趋势 |
| V8 clean | 2026-05-21 long | stop_loss | -6.48% | +0.29% | 10.9 ATR | 几乎没有 MFE，属于纯坏入场 |
| V10 | 2026-04-08 long | stop_loss | -4.01% | +0.29% | 10.1 ATR | 指标退出帮不上忙，问题在入场质量 |
| V6 | 2025-09-09 long | stop_loss | -4.21% | +1.20% | 9.1 ATR | 需要对刚经历高潮后的同向再入场做限制 |

### V12 应该怎么改

| 模块 | 诊断 | 改法 |
| --- | --- | --- |
| 退出结构 | 不要把 volume_exhaustion 直接当最终卖点 | 先进入 warning，再等价格结构跌破/升破确认 |
| 再入场 | V8 的收益来自多次再入场，但也制造了大量早退和坏入场 | 同一趋势内再次入场必须要求新结构突破，而不是过滤器仍满足就进 |
| 趋势阶段 | 增加阶段状态机：启动、加速、高潮、衰竭确认 | 只有高潮阶段才监听顶部/底部指标，启动阶段避免过早卖 |
| 下一版方向 | V12 不应继续堆指标 | 应重写为 V6/V10 入场 + warning/confirm 双阶段退出 + 结构化再入场 |

## 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/research_hype_trade_path_diagnostics_v11.py | V11 交易路径诊断脚本 |
| reports/hype_trade_path_diagnostics_v11.json | 结构化诊断报告 |
| reports/hype_trade_path_diagnostics_v11_detail.csv | 逐笔 MFE / MAE / 捕获率明细 |
| reports/hype_trade_path_diagnostics_v11_summary.csv | 策略级汇总 |
| reports/hype_trade_path_diagnostics_v11_categories.csv | 问题分类汇总 |
