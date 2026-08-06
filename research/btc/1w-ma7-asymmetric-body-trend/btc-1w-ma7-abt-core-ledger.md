# BTC-1W-MA7-Asymmetric-Body-Trend Core Ledger

## Family Identity

- Full family name：`BTC-1W-MA7-Asymmetric-Body-Trend`
- Alias：`BTC-1W-MA7-ABT`
- Market / symbol / timeframe：Binance USD-M `BTCUSDT` perpetual，anchored `1w`
- Mechanism：`HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 的固定 SMA7/ATR7、多空独立 reclaim、迟滞与 ATR 保护零调参周线迁移。
- Boundary：独立于 BTC 日线 transfer 与其他 BTC 趋势家族；周线观察不继承来源 V1 状态。

## Current State

- Current version：无；本家族未登记版本。
- Current status：`explore / not promoted / not live-ready`；direct transfer 已失败。
- Primary result：`2024-08-05` 至 `2026-07-27 UTC`，combined `-21.72%`、MDD `-29.61%`、3 笔且全亏；long-only `-30.82%`，short-only `-8.38%`。
- Time contracts：bar-transfer 与 clock-equivalent 结果完全相同，因为 max-hold / cooldown 没有成为逐笔约束。
- Stress / phase：`8 bps` 为 `-21.91%`，额外延迟一周为 `-5.46%`；`84h` 相位 combined `-13.48%`，两相位均亏。
- Stability：6 个滚动 `26w` combined 窗口仅 1 个为正，中位 `-5.07%`；最近 `1y` 为 `-18.10%`，最近 `6m` 无交易。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Blockers：combined 与多空单腿均亏损、无超额、只有 3 笔、近半年无信号；长仓首周无 hard stop；无 clean prospective OOS、CPCV、runner parity 或线上对账。
- Next gate：停止原参数周线迁移，不在已揭示 BTC 周线历史上调参；若研究新的 BTC 周线机制，应另立预先冻结的机制合同。

## Version Rules

- 当前只是来源 V1 的 timeframe-transfer observation，不产生 `BTC-...-V1`。
- SMA/ATR、周界线、max-hold/cooldown、方向、成本或保护变化均属于新观察合同，不回写本结果。
- “登记/冻结 Vx”只固定身份；本次用户没有提出登记或 promotion。

## Version Table

| Observation | Status | Role / Core Idea | Key Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| Weekly V1 direct transfer | `explore / not promoted / not live-ready` | 日线 V1 参数迁移至 `SMA7/ATR7` 周 K | `-21.72%`，MDD `-29.61%`，3 笔；`84h=-13.48%` | [周线诊断](diagnostics/btc-1w-ma7-v1-transfer-2026-08-05.md) | 绝对、超额、多空与稳定性失败，不登记 |

## Shared Assumptions

- Data：accepted Binance `BTCUSDT` perpetual `1h` raw/normalized，按锚点聚合正好 `168` 根 closed 小时 K。
- Cost：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、实际 event-time funding；压力滑点 `8 bps/fill`。
- Execution：周收盘信号次周 open；stop 用 `1h` 路径，gap 穿越按小时 open；约 `1x`、单仓、非加仓。
- Evidence role：BTC 历史已揭示，只是 timeframe-transfer diagnostic。

## Evidence Map

- [周线迁移合同](specs/btc-1w-ma7-v1-transfer-contract-2026-08-05.md)
- [周线回测诊断](diagnostics/btc-1w-ma7-v1-transfer-2026-08-05.md)
- [机器摘要](artifacts/btc_1w_ma7_v1_transfer_summary_2026-08-05.json)
- [复现脚本](scripts/research_btc_1w_ma7_v1_transfer.py)
- [决策记录](decision-log.md)
