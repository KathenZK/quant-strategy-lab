# HYPE-15M-Multi-Horizon-EMA-Forecast

- Alias：`HYPE-15M-MHEF`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，`15m`
- 机制：EMA `8/32`、`16/64`、`32/128`、`64/256` 分别形成波动率归一化 forecast，按 `0.2/0.3/0.3/0.2` 融合并映射为最大 `1x` 连续仓位。
- 当前状态：`explore / not promoted / not live-ready`

## 边界

本家族不是 `HYPE-EMA-Crossover`、`HYPE-EMA-Trend-Breakout` 或 `HYPE-15M-Multi-Indicator-Intraday` 的版本；它研究的是多参数风险分散和连续仓位，不复用这些家族的离散入场/退出状态机。

## 入口

- 主账：[hype-15m-mhef-core-ledger.md](hype-15m-mhef-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 基线回测：[hype-15m-mhef-baseline-backtest-2026-07-14.md](notes/hype-15m-mhef-baseline-backtest-2026-07-14.md)
- 脚本：[scripts/README.md](scripts/README.md)
- 产物：[artifacts/README.md](artifacts/README.md)
