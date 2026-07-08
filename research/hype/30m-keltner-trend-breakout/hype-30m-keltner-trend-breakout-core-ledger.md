# HYPE-30M-Keltner-Trend-Breakout Core Ledger

## Family Identity

- Full family name：`HYPE-30M-Keltner-Trend-Breakout`
- Alias：`K2-FQ-V2-ATRVT-OFF`
- Market / exchange / symbol / timeframe：Binance USDM 永续 `HYPEUSDT`；`1m` 闭合 K 线重采样为 `30m` 信号周期与 `1h` 趋势周期。
- Mechanism summary：`1h` EMA trend regime + `30m` Keltner 突破，下一根 `30m` open 入场，固定 TP/SL/time exit，ATRVT 动态杠杆。
- Boundary / collision warnings：同事外部 K2/Keltner 规格复现线，不是 `HYPE-EMA-Trend-Breakout`、`HYPE-EMA-Crossover` 或 `HYPE-15M-Multi-Indicator-Intraday` 的版本。

## Current State

- Current version(s)：`K2-FQ-V2-ATRVT-OFF` 外部规格复现观察。
- Current status：`explore / not promoted / not live-ready`（状态词见 [../../strategy-status-glossary.md](../../strategy-status-glossary.md)）。
- Runner / dry-run / live status：无 runner handoff、无 dry-run、无 live。
- Live-readiness blockers：funding 未计入；止损滑点、gap-open、stop-market 成交、逐笔外部脚本 diff、runner 状态机对账未完成；高杠杆路径风险显著。
- Next decision gate：完成 live-executable 成交审计与外部逐笔对账后，再决定是否冻结本仓库正式 `V1`。

## Version Rules

- `V1`：仅当本仓库完成逐笔对账、数据质量确认、funding/滑点压力和 live-executable 审计后，才可登记为本仓库正式版本。
- `Vx.y`：仅用于已登记版本的小幅参数或执行语义修订；任何 TP/SL/hold/ATRVT target/杠杆上限变化都需要新版本行。
- Observation / diagnostic rows：外部规格复现、样本截止对账、成本压力和执行审计可作为观察行记录，不代表 promotion。
- New version trigger：信号逻辑、相位组合、杠杆目标、成本/funding 口径或 runner 可执行合同发生变化。

## Version Table

| Version / Observation | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| `K2-FQ-V2-ATRVT-OFF` external observation | `explore / not promoted / not live-ready` | 外部 30m Keltner + 1h EMA regime + ATRVT 进攻档复现 | `2025-05-30 10:30` 至 `2026-07-06 23:59 UTC`；单相位 6 bps `+7516.88% / MDD -26.08% / 114 笔`；剔除最新一笔后对齐外部 `+7698.66% / 113 笔` | [research-notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md](research-notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md) | 复现可信，但不提升；需完成 funding、滑点和 live-executable 审计 |

## Shared Assumptions

- Data：Binance futures `1m` 闭合 K 线；重采样后只保留完整 `30m` / `1h` bar。
- Cost：主口径 `6 bps/side`；压力口径 `15 bps/side`。
- Execution timing：`30m` 收盘确认，下一根 `30m` open 入场；入场 bar 起检查固定 TP/SL，SL 优先；`hold=30` 在该 bar close 平仓。
- Position sizing：账户复利；每笔名义为入场时权益乘以 ATRVT 杠杆，杠杆冻结到平仓。
- Funding / carry：本次复现未计入 funding；promotion 前必须补齐。

## Evidence Map

- Canonical specs：外部文件 `/Users/ZK/Downloads/2-k2-fq-v2-atrvt-off-20260707.md`（仓库外来源，不作为 repo 内可复现依赖）。
- Diagnostics / ablations：[research-notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md](research-notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md)
- Live specs：无。
- Forward tracking：无。
- Scripts / artifacts：[scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py](scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py)，[artifacts/hype_30m_k2_fq_v2_atrvt_off_backtest_2026-07-08.json](artifacts/hype_30m_k2_fq_v2_atrvt_off_backtest_2026-07-08.json)，[artifacts/hype_30m_k2_fq_v2_atrvt_off_trades_2026-07-08.csv](artifacts/hype_30m_k2_fq_v2_atrvt_off_trades_2026-07-08.csv)
