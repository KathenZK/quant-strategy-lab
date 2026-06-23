# MUUSDT HYPE V35 Session-Aware 迁移

> 迁移说明：本文由 legacy Cursor Canvas `mu-v35-session-aware-transfer.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：MU-HYPE-XFER legacy Canvas。

本主账只保留迁移决策需要的版本：原版诊断、当前 Binance shadow、固定 3x 观察组、regular-only 对照、动态仓位候选，以及多空双向诊断。这里使用精简主账编号 V1-V5。

Binance source: MUUSDT 15m · 2026-04-07 13:30 UTC → 2026-06-17 05:45 UTC。Polygon source: MU 15m · 2025-06-17 → 2026-06-16。

> **当前结论**
> MU 迁移主账现在保留两条主线：Binance shadow 先用 V1 fixed 2x regular+overnight；下一轮候选记录为 V4 dynamic target 1.25% / max3。V4 已补跑 Binance regular+overnight：收益低于固定 V2，但回撤略低，适合作为动态仓位候选继续观察。

## 主线版本

| 版本 | 收益 | MDD | 交易 | 胜率 | 样本 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| B0 原版 HYPE V35 | +25.64% | -29.58% | 34 | 67.65% | Binance 约 2 个月 | HYPE 参数原样迁移；空头与快止盈都不适合 MU |
| B1 TP10/SL9 fixed 2x | +122.55% | -15.19% | 20 | 75.00% | Binance 约 2 个月 | 旧基线：参数层面有效，但仍允许非美盘追单 |
| V1 fixed 2x regular+overnight | +115.81% | -15.84% | 13 | 84.62% | Binance 约 2 个月 | 当前 Binance shadow 基线；只做多，盘前/盘后不放开 |
| V2 fixed 3x regular+overnight | +205.79% | -22.99% | 13 | 84.62% | Binance 约 2 个月 | 激进观察组；固定 3x 回撤压力高于 V1 |
| V3 fixed 2x regular-only | +57.06% | -10.60% | 9 | 77.78% | Binance 约 2 个月 | 保守对照；最干净，但错过 Binance 夜盘趋势 |
| V4 dynamic target 1.25% / max3 | +165.00% | -22.52% | 29 | 82.76% | Binance regular+overnight | 平均实际杠杆 2.76x；Polygon 一年 regular-only 为 +610.92% / -27.98% |
| V5 dynamic long-short target 1.25% / max3 | +462.11% | -31.91% | 31 | 77.42% | Polygon 一年真股 | 多空双向诊断；空头 2 笔、胜率 0%、合计 -22.63% |

## 关键分窗口

V1-V3 来自 Binance MUUSDT；V4 同时记录 Binance regular+overnight 补跑和 Polygon 一年 regular-only 验证；V5 来自 Polygon 多空诊断。Binance warmup 后样本不足 3 个月，因此 Binance 3M 与 ALL 相同。

| 版本 | 设置 | 1周收益 | 1周回撤 | 1月收益 | 1月回撤 | 3个月收益 | 3个月回撤 | 1年收益 | 1年回撤 | 1年平均止盈 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V1 | fixed 2x regular+overnight | +12.97% | -4.64% | +71.66% | -9.95% | +115.81% | -15.84% | +115.81% | -15.84% | - |
| V2 | fixed 3x regular+overnight | +19.79% | -6.91% | +120.91% | -14.69% | +205.79% | -22.99% | +205.79% | -22.99% | - |
| V3 | fixed 2x regular-only | +12.97% | -4.64% | +44.47% | -9.95% | +57.06% | -10.60% | +57.06% | -10.60% | - |
| V4 | dynamic target 1.25% / max3 | -3.54% | -12.45% | +6.81% | -23.35% | +65.44% | -23.35% | +165.00% | -22.52% | 2.76x |
| V5 | dynamic long-short target 1.25% / max3 | - | - | - | - | - | - | +462.11% | -31.91% | 2.29x |

### 迁移决策

| 状态 | 规则 | 理由 |
| --- | --- | --- |
| 当前 shadow | V1: long-only + TP10/SL9 + fixed 2x + regular+overnight entry gate | 基于 Binance MUUSDT 两个月样本；夜盘贡献趋势延续，盘前/盘后暂不放开。 |
| 下一候选 | V4: dynamic target 1.25% / max3 | Binance regular+overnight 补跑为 +165.00% / -22.52%，低于固定 V2 收益但回撤略降；Polygon 一年 regular-only 验证为 +610.92% / -27.98%。 |
| 激进观察 | V2: fixed 3x regular+overnight | 收益高，但固定 3x 回撤压力明显；动态 max3 优先级高于固定 3x。 |
| 暂不放开 | premarket 和 16:00-20:00 afterhours | Binance 与 Polygon 两边都显示盘前/盘后会增加止损、降低胜率或抬高回撤。 |
| 诊断保留 | V5: dynamic long-short target 1.25% / max3 | Polygon 一年真股测试为 +462.11% / -31.91%，低于 V4 long-only；空头 2 笔、胜率 0%、合计 -22.63%。 |
| 保留原则 | 非美盘已有仓位管理 | 不在非美盘开新仓，但已有仓位仍需要全时段 TP/SL，因为 Binance 盘后仍可能跳动。 |
| 下一步验证 | 在 Binance MUUSDT 上补跑动态 regular+overnight | V4 目前来自 Polygon regular-only 口径；要替代 V1，必须补齐 Binance overnight 回测。 |

> **主账口径**
> V1 是当前 Binance MUUSDT shadow 基线；V4 是动态杠杆候选。Binance regular+overnight 补跑后，V4 比 V2 回撤略低但收益也低，暂不替代 V1。

## 产物路径

| 文件 | 内容 |
| --- | --- |
| archive/scripts/research/research_mu_v35_session_aware.py | Binance MUUSDT session-aware 研究脚本 |
| archive/scripts/research/research_mu_polygon_hype_v35_transfer.py | Polygon 一年真股与动态杠杆验证脚本 |
| reports/mu_usdt_v35_session_aware_ledger.csv | V1-V14 Binance 时段版本台账 |
| reports/mu_polygon_hype_v35_dynamic_leverage_summary.json | V4 动态杠杆验证摘要 |
| reports/mu_polygon_hype_v35_dynamic_leverage_ledger.csv | 动态杠杆 1W/1M/3M/ALL 台账 |
| reports/mu_binance_dynamic_regular_overnight_summary.json | V4 Binance regular+overnight 动态补跑摘要 |
| reports/mu_binance_dynamic_regular_overnight_ledger.csv | V2 fixed vs V4 dynamic Binance 对照台账 |
| reports/mu_polygon_hype_v35_dynamic_long_short_summary.json | V4 加空头对照诊断 |
| docs/research/mu/mu-hype-xfer-session-aware-ledger.md | Markdown 主账 |
| reports/mu_usdt_v35_session_aware_trades.csv | Binance 候选交易明细 |
| reports/mu_polygon_hype_v35_dynamic_leverage_trades.csv | 动态杠杆交易明细 |
