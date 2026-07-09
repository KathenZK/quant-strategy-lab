# Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble

- Full family name：`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble`
- Short id：`BIN-1H-AR-MAE`
- Market：Binance USD-M Futures perpetual，六个 symbol：`TRXUSDT`、`SOLUSDT`、`HYPEUSDT`、`ETHUSDT`、`BTCUSDT`、`BNBUSDT`
- Timeframe：`1h`

## 家族定义

本家族研究把六个单资产 `1h` adaptive-regime 家族的最新登记版本组合成跨资产组合：

- `TRX-1H-Adaptive-Regime-V3`
- `SOL-1H-Adaptive-Regime-V2`
- `HYPE-1H-Adaptive-Regime-V4`
- `ETH-1H-Adaptive-Regime-V3`
- `BTC-1H-Adaptive-Regime-V4`
- `BNB-1H-Adaptive-Regime-V3`

每个 sleeve 保持其家族冻结交易路径（信号、执行契约、成本、funding 全部不变）；组合层只做账户级持仓/资金规则，不做信号融合。这是跨资产组合研究线，隶属 `research/asset-portfolios/`，不改变任何成分家族的版本身份。

## 当前状态

`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1 registered single-position version / not promoted / not live-ready`。

首次组合回测（2026-07-07）：全期小时再平衡年化 `4.07x`、最大回撤 `-4.43%`、胜率 `89.66%`；reused holdout（最近三个月，已揭盲）年化降至 `1.62x`。成分策略全部是 `not promoted / not live-ready` 版本，组合层未做压力与实盘可执行审计，禁止 promotion。详见主账与首次回测报告。

`V1`（2026-07-07 登记）：全账户同一时间只允许一笔持仓、先到先得、全额权益执行；全期年化 `287.01x` 但最大回撤 `-21.43%` 穿破 `<20%` 硬门槛，reused holdout `7.67x / -19.79% DD`；状态 `not promoted / not live-ready`。等权 `1/6` 结构保留为 V1 登记前 diagnostic observation，不是正式版本。

2026-07-09 V1 风险覆盖层诊断显示：全局 `3x` cap 只是在基准成本下贴线过关（最差 DD `-19.99%`），额外 `4 bps/fill` 滑点即失败；全局 `2.5x` cap 在基准成本与额外滑点下都守住 `<20%` DD，但仍未做逐 K 联合状态机重演，因此只是下一轮冻结候选方向，不是新登记版本。

## 入口

- 主账：`binance-1h-ar-mae-core-ledger.md`
- 决策记录：`decision-log.md`
- V1 完整复现规格（给同事/AI）：`specs/binance-1h-ar-mae-v1-full-reproduction-spec-2026-07-07.md`
- V1 简版规格：`specs/binance-1h-ar-mae-v1-single-position-spec-2026-07-07.md`
- 首次组合回测（等权 `1/6`）：`notes/binance-1h-ar-mae-first-combination-backtest-2026-07-07.md`
- V1 单仓先到先得回测：`notes/binance-1h-ar-mae-single-position-backtest-2026-07-07.md`
- V1 风险覆盖层诊断：`notes/binance-1h-ar-mae-v1-risk-overlay-diagnostics-2026-07-09.md`
- V1 每周交易统计：`notes/binance-1h-ar-mae-v1-weekly-stats-2026-07-09.md`
- 复现脚本：`scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py`、`scripts/research_binance_1h_ar_mae_single_position_backtest.py`
- 产物：`artifacts/`
