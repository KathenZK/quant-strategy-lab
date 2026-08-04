# HYPE-15M-Multidimensional-Trend-Pyramiding Core Ledger

## Family Identity

- Full family：`HYPE-15M-Multidimensional-Trend-Pyramiding`
- Alias：`HYPE-15M-MDTP`
- 市场：Binance USD-M perpetual；主标的 `HYPE/USDT:USDT`
- 周期：`4h` regime、`1h` state、`15m` execution
- 机制：等权多维趋势分数、波动率目标、分阶段顺势加减仓、jump/延伸限制与右尾型慢速退出
- 边界：独立于 `HYPE-EMA-Trend-Breakout`、`HYPE-15M-MMTF`、`HYPE-15M-MHEF` 与其他 HYPE 家族

## Current State

- 当前版本：`HYPE-15M-MDTP-V1`
- 状态：`explore / not promoted / not live-ready`
- 主结论：初始标准成本净亏 `-64.39%`；`2026-08-02` 复审更新窗口后为 `-65.64%`，成本盈亏平衡仅 `1–2 bps/fill`，六币固定参数标准成本全部亏损。
- 主要失败来源：方向/强度分数跨六币均不单调，平均持仓约 `5.10h`、年化换手约 `788.12`；加仓不是唯一主因，禁止入场后增仓仍亏 `-52.21%`。
- live-executable blocker：当前模拟器不是显式 quantity/equity ledger，无法审计隐含再平衡、有效杠杆漂移、净盈利加仓与 open risk。
- successor 观察：未登记 campaign successor 已补显式 quantity/equity ledger；Long Validation `+1.96%` 但选中行 Train `-0.52%`，Short Validation `-3.87%`，两边均未通过研究可信度门槛。
- 下一门：不得重新使用已揭示 Validation；prospective OOS 已锁定为 `2026-08-02` 至 `2026-11-02 UTC`，本轮不揭示。

## Version Rules

- `Vx` 固定完整的方向分数、阶段仓位、执行与退出状态机。
- 等权成分、4h/1h/15m 分工、调仓节流、成本口径或退出族发生实质变化时才允许新版本。
- 参数稳定性、消融、跨币种迁移与成本压力只属 V1 证据，不自动形成新版本。

## Version Table

| Version | Status | Role / mechanism | Frozen result | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `HYPE-15M-MDTP-V1` | explore / not promoted / not live-ready | 4h 多维分数定方向，1h 阶段/恢复，15m next-open 波动率目标调仓；盈利后才加仓；jump/extension gate；ATR trail/Donchian/score decay | 初始 HYPE standard-cost `-64.39% / -65.14% DD / Sharpe -2.98`；复审更新窗口 `-65.64% / -66.23% DD / Sharpe -3.07`；六币净收益全负 | [规格](specs/hype-15m-mdtp-v1-spec.md) · [初始研究](diagnostics/hype-15m-mdtp-v1-initial-research-2026-07-31.md) · [失败复审](diagnostics/hype-15m-mdtp-v1-failure-audit-2026-08-02.md) | 不进入纸面交易；停止阈值优化 |

## Shared Assumptions

- 数据：Binance HYPEUSDT perpetual `15m` 已闭合 K 与实际 funding；主窗口 `2025-05-30 10:30 UTC` 至 `2026-07-30 10:00 UTC`。
- 主数据质量：`40895` 根，缺口/重复/关键 null/无效 OHLCV 均为 `0`，raw/normalized 对拍通过。
- 成本：标准比较为 fee `0.001` + adverse slippage `0.0004` 每次 fill，并计 funding；另保留 V35 canonical `0.00085` 合并成本复现行。
- 时序：1h/4h 由 15m 聚合并 shift 一根完整高周期 K；15m 收盘生成目标，下一根 open 执行；trailing close 后更新、下一根生效，gap 按更差 open。
- 仓位：只对浮盈 campaign 增仓；任何减仓与退出不受 extension/jump gate 阻挡。

## Evidence Map

- [decision-log.md](decision-log.md)
- [V1 规格](specs/hype-15m-mdtp-v1-spec.md)
- [初始研究报告](diagnostics/hype-15m-mdtp-v1-initial-research-2026-07-31.md)
- [失败复审](diagnostics/hype-15m-mdtp-v1-failure-audit-2026-08-02.md)
- [Campaign successor 冻结合同](specs/hype-15m-mdtp-campaign-successor-contract-2026-08-02.md)
- [Campaign successor 初始研究](diagnostics/hype-15m-mdtp-campaign-successor-initial-research-2026-08-02.md)
- [artifacts/README.md](artifacts/README.md)
- [scripts/README.md](scripts/README.md)
