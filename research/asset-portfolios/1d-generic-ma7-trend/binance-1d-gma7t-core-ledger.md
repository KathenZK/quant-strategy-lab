# Binance-1D-Generic-MA7-Trend Core Ledger

## Family Identity

- Full family name：`Binance-1D-Generic-MA7-Trend`
- Alias：`BIN-1D-GMA7T`
- Market / timeframe：Binance USD-M crypto perpetual，UTC `1d` + `1h` risk replay。
- Mechanism：对称 `SMA7/ATR7` reclaim、ATR-normalized slope、MA/ATR hysteresis 与 ATR hard/trailing protection。
- Boundary：跨资产统一参数；不继承 HYPE OAPP、RSI、PEHC、forced reversal、cooldown/max-hold 或多空不对称。

## Current State

- Current research contract：`Binance-1D-Generic-MA7-Trend-v0`。
- Status：`explore / frozen research contract / not promoted / not live-ready`。
- Freeze：2026-08-18，在本任务 market-cap universe 回测前冻结。
- 2026-08-18 audit：`22` 币、`876` trades、Sharpe>0 `12/22`、PF>1 `12/22`；equal-risk net `+22.84% / Sharpe 0.582 / MDD -25.11%`。
- Decision：存在弱 generic core，但 `2025`、最近一年、对称 short 与 protective-stop 邻域不稳；`NO-GO for promotion`。
- Next gate：若继续，必须新建前瞻分支并使用 point-in-time/dynamic universe 或新鲜 prospective window；不得回写 v0。

## Version Rules

- `v0` 是研究合同，不是 registered production version；参数不得依据本轮结果回写。
- 只有新数据/新 universe 合同才能提出后继；重新加入 HYPE modules 或单币参数属于 materially new branch。

## Version Table

| Version | Status | Role | Frozen evidence | Decision |
| --- | --- | --- | --- | --- |
| `BIN-1D-GMA7T-V0` | `explore / not promoted / not live-ready` | HYPE V7.1 的最小对称 generic-core 检验 | [规格](specs/binance-1d-generic-ma7-trend-v0-spec.md) · [audit](diagnostics/binance-1d-generic-ma7-trend-v0-genericization-audit-2026-08-18.md) · [报告](diagnostics/binance-1d-generic-ma7-trend-v0-top30-market-cap-backtest-2026-08-18.md) · [配置](configs/binance-1d-generic-ma7-trend-v0.json) | `NO-GO for promotion`；保留为新鲜前瞻研究候选 |

## Shared Assumptions

- Fee `0.001/fill`，slippage `4 bps/fill`，实际 funding；另给 gross 与 `8 bps`。
- Closed daily signal -> next UTC open；真实 `1h` 顺序 stop replay。
- Current market-cap snapshot，因此只能称 retrospective，不能称 point-in-time historical universe。

## Evidence Map

- [Genericization audit](diagnostics/binance-1d-generic-ma7-trend-v0-genericization-audit-2026-08-18.md)
- [v0规格](specs/binance-1d-generic-ma7-trend-v0-spec.md)
- [current market-cap Top30 迁移报告](diagnostics/binance-1d-generic-ma7-trend-v0-top30-market-cap-backtest-2026-08-18.md)
- [决策记录](decision-log.md)
- [产物索引](artifacts/README.md)
