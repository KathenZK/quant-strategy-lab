# Binance-15M-Asset-Specific-Six-Strategy-Selector

- Full family name：`Binance-15M-Asset-Specific-Six-Strategy-Selector`
- Short id：`BIN-15M-AS6S`
- Market：Binance USD-M Futures perpetual
- Symbols：`BTCUSDT / ETHUSDT / SOLUSDT / BNBUSDT / TRXUSDT / HYPEUSDT`
- Timeframe：资产专属 `15m / 1h` 混合信号，所有高周期状态只使用闭合 K

## 家族边界

先为每个币独立选择适合的趋势状态机、突破延续或短周期反转机制，再把通过单币门禁的不同机制放入六币全局单仓账户。HYPE 三条历史家族与 `BIN-1H-AR-MAE` 只提供机制和账户结构先验，本家族不继承其版本、参数或结论。

## 当前状态

`Binance-15M-Asset-Specific-Six-Strategy-Selector-V1`：`registered / not promoted / not live-ready`。V1 固定为九腿、全局单仓、不抢占路线；强突破抢占只保留为对照 observation。后续 15 腿资产优先研究已推进到未登记的 V5 joint-state observation；V3/V4 的状态语义缺陷均保留为审计证据，不构成 promotion。`2026-04-14` 至 `2026-07-14` 只作 reused-holdout 淘汰诊断，`2026-07-14` 至 `2026-10-14` 才是最终未来 OOS。

## 入口

- 主账：[binance-15m-as6s-core-ledger.md](binance-15m-as6s-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 数据同步：[scripts/sync_and_audit_binance_six_asset_15m_data.py](scripts/sync_and_audit_binance_six_asset_15m_data.py)
- 当前诊断：[diagnostics/binance-as6s-current-three-month-diagnostic-2026-07-14.md](diagnostics/binance-as6s-current-three-month-diagnostic-2026-07-14.md)
- 组合优先 V2 候选观察：[diagnostics/binance-as6s-portfolio-first-v2-observation-2026-07-14.md](diagnostics/binance-as6s-portfolio-first-v2-observation-2026-07-14.md)
- 单币优先 V3 候选观察：[diagnostics/binance-as6s-asset-first-v3-diagnostic-2026-07-14.md](diagnostics/binance-as6s-asset-first-v3-diagnostic-2026-07-14.md)
- V5 联合状态观察：[diagnostics/binance-as6s-v5-joint-state-observation-2026-07-14.md](diagnostics/binance-as6s-v5-joint-state-observation-2026-07-14.md)
- V1 近期切片：[diagnostics/binance-as6s-v1-recent-slices-2026-07-14.md](diagnostics/binance-as6s-v1-recent-slices-2026-07-14.md)
- 未来 OOS 冻结：[specs/binance-as6s-future-oos-freeze-2026-07-14.md](specs/binance-as6s-future-oos-freeze-2026-07-14.md)
- V3 observation 未来 OOS 冻结：[specs/binance-as6s-v3-future-oos-freeze-2026-07-14.md](specs/binance-as6s-v3-future-oos-freeze-2026-07-14.md)
