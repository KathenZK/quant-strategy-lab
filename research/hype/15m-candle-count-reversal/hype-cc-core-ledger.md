# HYPE-Candle-Count-Reversal Core Ledger

## Family Identity

- Full family name：`HYPE-Candle-Count-Reversal`
- Alias：`HYPE-CC`
- Market：Binance USD-M Futures `HYPEUSDT` perpetual
- Timeframe：`15m`
- Mechanism：最近 10 根闭合 K 中至少 8 根同色时做反向交易，配合 ATR672 动态仓位、固定 ATR bracket、连续止损风险倍率、冷却与 early-exit。
- Collision warning：`HYPE-CC-V35` 不是 `HYPE-EMA-TB-V35`；引用必须带完整 family name。

## Current State

- 当前版本：`HYPE-CC-V35`（runner strategy id：`HYPE-CANDLE-COUNT-V35`）。
- 状态：`dry-run / forward-test required / not live-ready`。
- Runner：quant-runner `kind = "hype_candle_count"`，manifest 实例 `hype-candle-count-v35-dry-run` 已启用。
- 历史 live underperformance 是 execution-risk 证据，不等于当前新终态；当前不得升级 live，也不得在 dry-run 观察前重新写 `NO-GO`。
- 当前 blocker：标准 parity、保护单与重启恢复、费用/滑点/funding 对账、历史 underperformance 复核、dated runner tracking 与 online open/close reconciliation。
- 下一决策门：积累 dry-run 订单与成交证据后，明确 keep / stop / adjust；当前 live disabled。

## Version Rules

- `Vx` 只在本家族内有效；信号计数、ATR 窗口、仓位、退出状态机、冷却或连续止损倍率改变均需登记新版本。
- 只改变报告、复现脚本、runner 观测或未采用的诊断参数，不产生新版本。
- V0-V34 是历史演化证据；当前身份只由版本表、V35 规格、handoff 与 manifest 决定。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| `HYPE-CC-V13` | historical research milestone | ATR288 双向动态仓位与 bracket，连续止损减半 | 1Y `+558.95% / -26.57% DD / 323 trades` | [里程碑台账](hype-cc-15m-milestone-comparison.md)；[V13 规格](specs/hype-v13-strategy-spec.md) | 保留为早期稳健性基线，不是当前 runner 版本 |
| `HYPE-CC-V18` | historical research milestone | ATR672 平滑仓位与 bracket | 1Y `+803.48% / -27.96% DD / 321 trades` | [里程碑台账](hype-cc-15m-milestone-comparison.md)；[V18 规格](specs/hype-v18-atr672-strategy-spec.md) | 证明 ATR 窗口迁移方向，已被后续版本 supersede |
| `HYPE-CC-V21` | historical research milestone | V18 + 多单三阴/空单三阳 early-exit | 1Y `+1291.67% / -26.54% DD / 330 trades` | [里程碑台账](hype-cc-15m-milestone-comparison.md)；[V21 规格](specs/hype-v21-reproducible-params.md) | early-exit 演化基线，已被后续版本 supersede |
| `HYPE-CANDLE-COUNT-V35`（`HYPE-CC-V35`） | dry-run / not live-ready | V34 双向 counter exit 从 `10/8` 改为 `12/9`；保留 3/3 early-exit、ATR672 风控、连续止损倍率与冷却 | 冻结历史 1Y `+8357.56% / -33.26% DD / 340 trades`；历史 live underperformance 需持续复核 | [V35 参数规格](specs/hype-v35-reproducible-params.md)；[handoff](live-specs/hype-cc-v35-handoff-not-live-ready.md)；[历史实盘复盘](diagnostics/hype-cc-v35-live-underperformance-review-2026-06-29.md)；[参数过拟合复诊](diagnostics/hype-cc-v35-parameter-overfit-rediagnosis-2026-06-29.md)；[runner tracking](runner-tracking/hype-cc-runner-2026-07-10.md) | manifest 已授权 dry-run；live disabled，等待 forward-test 与在线开平仓对账 |

## Shared Assumptions

- 数据：HYPE 永续 `15m` 闭合 K；当前 runner handoff 使用 Binance USD-M，历史里程碑包含早期 Hyperliquid 成本口径，跨 venue 数字不得无说明混用。
- 执行：闭合 K 产生信号，下一根 open 执行；mark high/low 触发保护；同 bar 冲突、gap-open、rounding 与 funding 以冻结规格和 runner SPEC 为准。
- Binance 研究默认成本：fee `0.001/fill`、adverse slippage `4 bps/fill`；历史里程碑的 Hyperliquid taker `0.045%`、slippage `4 bps` 与 funding 只作为原始证据。
- 仓位：单策略单仓；动态 allocation 与连续止损 risk multiplier 必须持久化，重启后不得静默重置。

## Evidence Map

- [家族路由](README.md)
- [决策记录](decision-log.md)
- [完整历史里程碑](hype-cc-15m-milestone-comparison.md)
- [V35 runner handoff](live-specs/hype-cc-v35-handoff-not-live-ready.md)
- [V35 runner tracking](runner-tracking/hype-cc-runner-2026-07-10.md)
- [V35 参数过拟合复诊](diagnostics/hype-cc-v35-parameter-overfit-rediagnosis-2026-06-29.md)
- [V35 历史实盘表现复盘](diagnostics/hype-cc-v35-live-underperformance-review-2026-06-29.md)
- [artifacts 索引](artifacts/README.md)
