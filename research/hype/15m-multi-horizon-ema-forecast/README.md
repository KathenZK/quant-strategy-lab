# HYPE-15M-Multi-Horizon-EMA-Forecast

- Alias：`HYPE-15M-MHEF`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，`15m`
- 机制：多速度 EMA 波动率归一化 forecast 融合为连续目标仓位；V2 observation 另加入跨周期 coherence、dead zone、波动率目标、成本感知目标带、最小调仓量与单 K 仓位限速。
- 当前状态：`explore / NO-GO / not promoted / not live-ready`

## 边界

本家族不是 `HYPE-EMA-Crossover`、`HYPE-EMA-Trend-Breakout` 或 `HYPE-15M-Multi-Indicator-Intraday` 的版本；它研究的是多参数风险分散和连续仓位，不复用这些家族的离散入场/退出状态机。

## 入口

- 主账：[hype-15m-mhef-core-ledger.md](hype-15m-mhef-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 基线回测：[hype-15m-mhef-baseline-backtest-2026-07-14.md](notes/hype-15m-mhef-baseline-backtest-2026-07-14.md)
- V2 连续目标仓位全参数研究：[hype-15m-mhef-v2-continuous-target-research-2026-07-28.md](notes/hype-15m-mhef-v2-continuous-target-research-2026-07-28.md)
- V2 冻结候选中心消融：[hype-15m-mhef-v2-candidate-centered-ablation-2026-07-28.md](notes/hype-15m-mhef-v2-candidate-centered-ablation-2026-07-28.md)
- 脚本：[scripts/README.md](scripts/README.md)
- 产物：[artifacts/README.md](artifacts/README.md)
