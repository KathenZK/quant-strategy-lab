# HYPE-1D-Multi-Horizon-EMA-Forecast Core Ledger

## Family Identity

- Full family name：`HYPE-1D-Multi-Horizon-EMA-Forecast`
- Alias：`HYPE-1D-MHEF`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`HYPEUSDT` perpetual，UTC `1d`
- Mechanism：四组经典 EWMAC forecast 加权融合，forecast 强度控制最大 `1x` 连续方向仓位。
- Boundary：固定 EWMAC scalar 的日线适配，不继承 `15m` / `1h` 家族的滚动校准和版本身份。

## Current State

- Current version(s)：无；当前为未编号 baseline observation。
- Current status：`explore / not promoted / not live-ready`
- Runner / dry-run / live：无。
- Live-readiness blockers：EMA256 warmup 后仅有 153 根有效日 K，无法覆盖多个市场 regime；尚无 OOS、跨资产或统计显著性证据。
- Next decision gate：等待更长 HYPE 日线历史，或先完成同口径跨资产检验；当前正收益只保留为短样本观察。

## Version Rules

- `V1`：仅在用户要求登记，且补充更长历史或跨资产证据后创建。
- `Vx.y`：信号不变，仅做可逐路径对账的小幅执行修正。
- Observation：未编号试验保持 `explore`。
- New version trigger：EMA 集合/权重、EWMAC scalar、volatility estimator、调仓规则或风险上限发生身份级变化。

## Version Table

当前无 registered version。未编号基线使用 `0.10` 调仓缓冲时净收益 `+11.17%`、最大回撤 `-15.25%`、Sharpe `1.03`；同期 1x 永续买入持有 `+129.69%`。完整结果见 [2026-07-14 基线回测](notes/hype-1d-mhef-classic-ewmac-backtest-2026-07-14.md)。

## Shared Assumptions

- Data：由已通过质量门的标准 Binance `HYPEUSDT` perpetual `1h` 数据聚合完整 UTC 日 K。
- Cost：每单位换手手续费 `0.001` + adverse slippage `0.0004`。
- Execution timing：日 K 收盘计算，下一日 open 调仓。
- Position sizing：标准 EWMAC forecast 除以 `20` 映射到 `[-1x,1x]`；精确调仓与 `0.10` 缓冲并列观察。
- Funding：使用 Binance 历史 funding，按上一持仓在调仓前结算。

## Evidence Map

- Report：[hype-1d-mhef-classic-ewmac-backtest-2026-07-14.md](notes/hype-1d-mhef-classic-ewmac-backtest-2026-07-14.md)
- Script：[research_hype_1d_multi_horizon_ema_forecast.py](scripts/research_hype_1d_multi_horizon_ema_forecast.py)
- Artifacts：[artifacts/README.md](artifacts/README.md)
- Shared execution kernel：[multi-horizon-ema-forecast v1](../../_shared-kernels/multi-horizon-ema-forecast/README.md)
