# HYPE-15M-Multi-Horizon-EMA-Forecast Core Ledger

## Family Identity

- Full family name：`HYPE-15M-Multi-Horizon-EMA-Forecast`
- Alias：`HYPE-15M-MHEF`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`HYPEUSDT` perpetual，`15m`
- Mechanism：多速度 EMA 波动率归一化 forecast 加权融合，forecast 强度控制连续方向仓位；V2 observation 加入 coherence、dead zone、波动率目标与成本感知的分步仓位追踪。
- Boundary：与 `HYPE-EMA-X`、`HYPE-EMA-TB`、`HYPE-15M-MII` 分离，不继承其版本或状态机。

## Current State

- Current version(s)：无；当前仅有未编号 baseline observation。
- Current status：`explore / NO-GO / not promoted / not live-ready`
- Runner / dry-run / live：无。
- Live-readiness blockers：V1 基线全区间毛净收益为负；V2 冻结候选虽在 train/tune 为正，但未参与选择的三个月验证毛收益 `-9.20%`、净收益 `-11.47%`，零成本亦为负；尚无 fresh prospective OOS，且未审计最小订单、数量步长、拒单、重启恢复与保护性风控。
- Next decision gate：本单资产 `15m` 机制已判 NO-GO，不再使用已揭示验证调参。后继必须是 materially new mechanism 或多市场组合契约，并使用 `2026-07-28 08:00 UTC` 之后的 fresh outcome-blind prospective OOS。

## Version Rules

- `V1`：仅在用户要求登记，并冻结 forecast、执行、成本和证据后创建。
- `Vx.y`：信号不变，仅做可逐路径对账的小幅执行或参数修正。
- Observation：未编号试验保持 `explore`，不暗示可交易。
- New version trigger：EMA 集合/权重、forecast 校准、调仓规则或风险上限发生身份级变化。

## Version Table

当前无 registered version。证据包括 [2026-07-14 基线](notes/hype-15m-mhef-baseline-backtest-2026-07-14.md) 与 [2026-07-28 V2 连续仓位研究](notes/hype-15m-mhef-v2-continuous-target-research-2026-07-28.md)；二者均为未编号 observation。

## Shared Assumptions

- Data：标准数据湖 Binance `HYPEUSDT` perpetual 闭合 `15m` K 线；raw/normalized 必须逐字段一致。
- Cost：每单位换手手续费 `0.001` + adverse slippage `0.0004`。
- Execution timing：K 线收盘计算，下一根 open 调仓。
- Position sizing：forecast 映射到 `[-1x,1x]`；V2 使用波动率目标、目标仓位带、最小调仓量与单 K 仓位限速。
- Funding：使用 Binance 历史 funding，按上一持仓在调仓前结算。

## Evidence Map

- Report：[hype-15m-mhef-baseline-backtest-2026-07-14.md](notes/hype-15m-mhef-baseline-backtest-2026-07-14.md)
- V2 report：[hype-15m-mhef-v2-continuous-target-research-2026-07-28.md](notes/hype-15m-mhef-v2-continuous-target-research-2026-07-28.md)
- V2 candidate-centered ablation：[hype-15m-mhef-v2-candidate-centered-ablation-2026-07-28.md](notes/hype-15m-mhef-v2-candidate-centered-ablation-2026-07-28.md)
- Script：[research_hype_15m_multi_horizon_ema_forecast.py](scripts/research_hype_15m_multi_horizon_ema_forecast.py)
- Artifacts：[artifacts/README.md](artifacts/README.md)
- Shared kernel：[multi-horizon-ema-forecast](../../_shared-kernels/multi-horizon-ema-forecast/README.md)
