# Asset Portfolios Research Index

本目录存放组合策略、跨资产策略、迁移研究和多 sleeve 资金结构研究。当前材料主要基于 Binance USD-M Futures 市场数据；若某个研究线后续变成单一资产策略家族，应迁入对应资产目录并保留这里的交叉引用。

## 当前研究线

- `1d-turtle-breakout/`：Binance USD-M Futures `BTCUSDT`、`ETHUSDT`、`HYPEUSDT` 日线 20/10 turtle breakout 诊断。
- `15m-multi-indicator-intraday/`：基于 `HYPE-15M-MII-V1.1` 机制的 Binance USD-M `BTCUSDT`、`ETHUSDT` `15m` 受约束参数迁移诊断；BTC 有低收益 K+1/K+2 同正版本，ETH 只有 K+1-only 赚钱版本，整体不提升。
- `1h-adaptive-regime-multi-asset-ensemble/`：`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble`（`BIN-1H-AR-MAE`），六个 `1h` adaptive-regime 家族最新登记版本（TRX V3、SOL V2、HYPE V4、ETH V3、BTC V4、BNB V3）的跨资产组合；`V1` 已登记为全账户单仓、先到先得版本，full `287.01x / -21.43% DD / 90.30% win / 371 trades`，reused holdout `7.67x / -19.79% DD`；因 full 回撤穿破 `<20%` 且成分全 NO-GO，状态 `registered diagnostic / NO-GO / not promoted / not live-ready`。等权 `1/6` 首次组合回测保留为未编号 diagnostic observation。

## 单资产研究转介

- Bitcoin `1h` 独立策略家族位于 `../btc/1h-adaptive-regime/`：`BTC-1H-Adaptive-Regime`，2026-07-02 宽搜索与三个月 locked OOS 结论为 `NO-GO / not live-ready`。
