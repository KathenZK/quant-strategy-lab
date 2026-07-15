# Binance-1H-Multi-Leg-Six-Asset-Selector

- Full family name：`Binance-1H-Multi-Leg-Six-Asset-Selector`
- Short id：`BIN-1H-ML6AS`
- Market：Binance USD-M Futures perpetual
- Symbols：`BTCUSDT / ETHUSDT / SOLUSDT / BNBUSDT / TRXUSDT / HYPEUSDT`
- Timeframe：`4h` regime + `1h` signal/execution

## 家族边界

六币分别研究趋势回调、突破延续、均值回归三类完整交易臂，并比较“独立交易臂统一仲裁”与“币内多腿评分融合”两条路线。账户层允许空仓，比较持仓不抢占与强信号抢占两种单仓状态机；多空双向，暴露上限 `3x`。

本家族不复用或改写 `Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble` 的版本身份，也不自动继承六个单资产 adaptive-regime 家族的参数、指标或结论。

## 当前状态

`explore / not promoted / not live-ready`。四条预拟合冻结路线在首次最近三个月锁定 OOS 揭示中全部失败，没有登记版本；已揭示 OOS 不再用于候选选择。

## 入口

- 主账：[binance-1h-ml6as-core-ledger.md](binance-1h-ml6as-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 数据脚本：[scripts/sync_and_audit_binance_six_asset_1h_data.py](scripts/sync_and_audit_binance_six_asset_1h_data.py)
- 锁定 OOS 结论：[diagnostics/binance-1h-ml6as-prefit-oos-failure-2026-07-14.md](diagnostics/binance-1h-ml6as-prefit-oos-failure-2026-07-14.md)
