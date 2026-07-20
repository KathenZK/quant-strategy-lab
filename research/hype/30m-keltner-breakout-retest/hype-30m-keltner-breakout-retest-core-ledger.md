# HYPE-30M-Keltner-Breakout-Retest Core Ledger

## Family Identity

- Full family name：`HYPE-30M-Keltner-Breakout-Retest`
- Market / exchange / symbol / timeframe：Binance USDM 永续 `HYPEUSDT`；`30m` signal + `1h` trend regime。
- Mechanism：Keltner 突破先建立 setup，等待有限窗口内回踩突破轨且不破中轨，再以方向性 reclaim 收盘确认并 next-open 入场。
- Boundary：独立于 `HYPE-30M-Keltner-Trend-Breakout`；后者是直接突破入场，本家族是多 bar 状态机。

## Current State

- Current version：无 registered 版本。
- Status：`explore / not promoted / not live-ready`。
- Runner / dry-run / live：无。
- Next decision gate：当前 upper-retest→reclaim 假设已失败并停止；若继续研究，必须先提出不同且预先冻结的 Keltner 趋势假设，不能扩大同一网格。

## Version Rules

- 只有冻结完整 setup/retest/reclaim/exit 参数且有可复现证据时才登记 `V1`。
- setup 期限、回踩定义、reclaim 定义、方向、退出或仓位语义变化均触发新版本。
- 搜索候选与诊断行不构成 registered 版本。

## Version Table

| Version / Observation | Status | Role | Evidence | Decision |
| --- | --- | --- | --- | --- |
| Initial search | `explore / not promoted / not live-ready` | 864 组 Keltner breakout→retest→reclaim 搜索；0 组达到高胜率目标 | [diagnostics/hype-30m-keltner-breakout-retest-initial-search-2026-07-17.md](diagnostics/hype-30m-keltner-breakout-retest-initial-search-2026-07-17.md) | 最接近行胜率 `60.53%`；不登记 V1，停止该假设 |

## Shared Assumptions

- 数据：Binance futures `1m` closed bars 聚合完整 `30m` / `1h`。
- 成本：手续费 `0.001/fill` + 不利滑点 `0.0004/fill` + Binance 历史 funding。
- 执行：信号收盘确认，下一根 `30m` open 入场；同 bar bracket 冲突时 SL 优先。

## Evidence Map

- Diagnostics：[diagnostics/hype-30m-keltner-breakout-retest-initial-search-2026-07-17.md](diagnostics/hype-30m-keltner-breakout-retest-initial-search-2026-07-17.md)
- Live specs：无。
- Runner tracking：无。
