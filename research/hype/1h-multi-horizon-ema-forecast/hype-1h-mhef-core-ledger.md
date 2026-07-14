# HYPE-1H-Multi-Horizon-EMA-Forecast Core Ledger

## Family Identity

- Full family name：`HYPE-1H-Multi-Horizon-EMA-Forecast`
- Alias：`HYPE-1H-MHEF`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`HYPEUSDT` perpetual，`1h`
- Mechanism：四组 EMA 波动率归一化 forecast 加权融合，forecast 强度直接控制最大 `1x` 连续方向仓位。
- Boundary：与 `HYPE-1H-AR` 和所有 `15m` EMA 家族分离，不继承其版本或状态机。

## Current State

- Current version(s)：无；当前仅有未编号 baseline observation。
- Current status：`explore / not promoted / not live-ready`
- Runner / dry-run / live：无。
- Live-readiness blockers：全区间毛收益和净收益均未转正；回撤较高；未审计最小订单、数量步长、拒单、重启恢复与保护性风控。
- Next decision gate：只有新机制先在未加杠杆毛收益口径转正，才值得讨论版本登记。

## Version Rules

- `V1`：仅在用户要求登记，并冻结 forecast、执行、成本和证据后创建。
- `Vx.y`：信号不变，仅做可逐路径对账的小幅执行或参数修正。
- Observation：未编号试验保持 `explore`，不暗示可交易。
- New version trigger：EMA 集合/权重、forecast 校准、调仓规则或风险上限发生身份级变化。

## Version Table

当前无 registered version。基线结果见 [2026-07-14 回测](notes/hype-1h-mhef-baseline-backtest-2026-07-14.md)。

## Shared Assumptions

- Data：标准数据湖 Binance `HYPEUSDT` perpetual 闭合 `1h` K 线；raw/normalized 必须逐字段一致。
- Cost：每单位换手手续费 `0.001` + adverse slippage `0.0004`。
- Execution timing：K 线收盘计算，下一根 open 调仓。
- Position sizing：forecast 映射到 `[-1x,1x]`；同时观察精确调仓和 `0.10` 缓冲。
- Funding：使用 Binance 历史 funding，按上一持仓在调仓前结算。

## Evidence Map

- Report：[hype-1h-mhef-baseline-backtest-2026-07-14.md](notes/hype-1h-mhef-baseline-backtest-2026-07-14.md)
- Script：[research_hype_1h_multi_horizon_ema_forecast.py](scripts/research_hype_1h_multi_horizon_ema_forecast.py)
- Artifacts：[artifacts/README.md](artifacts/README.md)
- Shared kernel：[multi-horizon-ema-forecast](../../_shared-kernels/multi-horizon-ema-forecast/README.md)
