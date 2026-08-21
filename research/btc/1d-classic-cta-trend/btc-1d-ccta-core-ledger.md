# BTC-1D-Classic-CTA-Trend Core Ledger

## Family Identity

- Full family name：`BTC-1D-Classic-CTA-Trend`
- Alias：`BTC-1D-CCTA`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`BTCUSDT` perpetual，UTC `1d`
- Mechanism：Carver EWMAC 四速等权 forecast，按 BTC 自身 σ 缩放到 20% 年化目标，次日开盘连续调仓。
- Boundary：文献参数零调参的 BTC 单资产诊断；不继承 HYPE-1D-MHEF 的 `±1x` 映射，也不继承已关闭的 XA-1D-EWMAC-UT 组合门禁。

## Current State

- Current version(s)：无；当前为未编号 literature baseline observation。
- Current status：`explore / not promoted / not live-ready`
- Runner / dry-run / live：无。
- Live-readiness blockers：相对同成本 1x 买入持有无超额；空头腿亏损；资金费为最大拖累；连续仓位未模拟最小名义/步长；无 OOS/CPCV、消融门禁包或 live-executable 审计。
- Next decision gate：不在同一历史上改速度对、scalar、波动目标或 buffer。若继续，只能换评估单元（例如多资产）或换执行面，并另立契约。

## Version Rules

- `V1`：仅在用户要求登记，且补充超额/稳健性证据后创建。
- `Vx.y`：信号不变，仅做可逐路径对账的执行修正。
- Observation：未编号试验保持 `explore`。
- New version trigger：EMA 集合、scalar、波动目标、仓位上限或调仓规则发生身份级变化。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| 2026-08-17 文献基线 | `explore / not promoted / not live-ready` | 统一 EWMAC + 20% vol target + `0.10` 波动率缓冲 | 净 `+71.45%` / Sharpe `0.530` / MDD `-37.04%`；1x 持有净 `+238.62%` / `-78.89%`；多头-only `+98.55%`，空头-only `-16.10%` | [诊断](diagnostics/btc-1d-ccta-classic-cta-backtest-2026-08-17.md) | 绝对收益成立但无超额；不登记、不晋升 |

## Shared Assumptions

- Data：标准湖 native UTC `1d` 闭合 K，raw/normalized 对齐；资金费用 `funding_rates` 8h 事件，回测窗口裁到可收费日。
- Cost：每单位换手手续费 `0.001` + adverse slippage `0.0004`。
- Execution timing：日 K 收盘计算，下一日 open 调仓。
- Position sizing：`w = (F/10) × (0.20/σ_ann)`，上限 `2x`；主口径 buffer `0.10 × (0.20/σ_ann)`。
- Funding：`(previous open, current open]` 的实际 funding 在调仓前按上一持仓结算。

## Evidence Map

- Spec：[btc-1d-ccta-literature-baseline-2026-08-17.md](specs/btc-1d-ccta-literature-baseline-2026-08-17.md)
- Diagnostic：[btc-1d-ccta-classic-cta-backtest-2026-08-17.md](diagnostics/btc-1d-ccta-classic-cta-backtest-2026-08-17.md)
- Script：[research_btc_1d_classic_cta.py](scripts/research_btc_1d_classic_cta.py)
- Artifacts：[artifacts/README.md](artifacts/README.md)
- Shared execution kernel：[multi-horizon-ema-forecast v1](../../_shared-kernels/multi-horizon-ema-forecast/README.md)
