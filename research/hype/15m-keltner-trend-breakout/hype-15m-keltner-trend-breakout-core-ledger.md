# HYPE-15M-Keltner-Trend-Breakout Core Ledger

## Family Identity

- 完整名称：`HYPE-15M-Keltner-Trend-Breakout`
- 别名：`HYPE-15M-KTB`
- 市场：Binance USD-M Futures `HYPEUSDT` perpetual
- 周期：`15m`
- 机制：只使用 `EMA96 ± 2.4 × ATR144` Keltner 通道测试外轨突破、压缩扩张和中轨回踩，闭合 K 线确认后于后续 open 执行。
- 边界：不是 `HYPE-EMA-Trend-Breakout` V2P/V35，也不是 `HYPE-30M-Keltner-Trend-Breakout` 的版本。

## Current State

- 当前状态：`explore / not promoted / not live-ready`
- 已登记版本：无
- 当前观察：首轮固定 bracket 及三条新机制均失败；新机制中相对最好的压缩扩张 K1 仍为 full `-68.54% / -74.41% MaxDD`，零交易成本仍为 `-36.15%`。
- Live readiness：无候选、无 live spec、无 runner、无 dry-run。
- 下一决策门：停止纯 Keltner 扩搜；只有与当前家族不同、预先提出且可执行的新机制才能重开研究。

## Version Rules

- 只有冻结明确、可复现且至少通过基础收益/回撤与执行审计的机制才可登记 `V1`。
- 通道宽度、bracket 或时序的诊断变体不自动构成版本。
- 重新加入趋势、ADX/DI、成交量或高周期确认属于 materially new mechanism，必须明确身份边界，不能继承本轮状态。

## Version Table

| Observation / Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| 2026-07-20 纯通道首轮诊断 | explore / not promoted / not live-ready | `EMA96 ± 2.4 × ATR144` 纯突破，K1 open 主执行 | K1 ATR-risk `-86.46% / -89.60% / 343 trades`；固定 1x `-73.56% / -78.46%`；K2 `-8.55% / -72.43%` | [诊断报告](diagnostics/hype-15m-keltner-only-initial-backtest-2026-07-20.md) | 失败；不登记 V1，不继续同机制扩搜 |
| 2026-07-21 新机制假设诊断 | explore / not promoted / not live-ready | 外轨事件突破、压缩扩张突破、中轨趋势回踩；中轨退出 | 三条 K1 full `-97.55% / -68.54% / -77.18%`；MaxDD `-97.85% / -74.41% / -80.37%`；零交易成本仍全部亏损 | [诊断报告](diagnostics/hype-15m-keltner-mechanism-hypotheses-2026-07-21.md) | 全部失败；不登记 V1，停止纯 Keltner 扩搜 |

## Shared Assumptions

- 数据：Binance HYPEUSDT 永续闭合 `15m` K 线，当前范围 `2025-05-30 10:30` 至 `2026-07-21 08:00 UTC`，质量门禁 `0 blocker`。
- 成本：每 fill 手续费 `0.001`，adverse slippage `0.0004`，计入实际 funding。
- 执行：K0 收盘确认；主口径 K1 open，时序审计 K2 open；entry ATR 固定；stop gap 按更差 open；闭合后退出在下一根 open。
- 仓位：单持仓、无加仓；首轮以 ATR-risk 为主，新机制比较统一固定 `1x`。

## Evidence Map

- [首轮诊断](diagnostics/hype-15m-keltner-only-initial-backtest-2026-07-20.md)
- [新机制假设诊断](diagnostics/hype-15m-keltner-mechanism-hypotheses-2026-07-21.md)
- [决策日志](decision-log.md)
- [回测脚本](scripts/research_hype_15m_keltner_only.py)
- [新机制脚本](scripts/research_hype_15m_keltner_mechanisms.py)
- [汇总 JSON](artifacts/hype_15m_keltner_only_initial_2026-07-20.json)
- [新机制汇总 JSON](artifacts/hype_15m_keltner_mechanism_hypotheses_2026-07-21.json)
- [逐笔交易](artifacts/hype_15m_keltner_only_initial_2026-07-20_trades.csv)
- [权益曲线](artifacts/hype_15m_keltner_only_initial_2026-07-20_equity.csv)
