# Binance-15M-Asset-Specific-Six-Strategy-Selector

- Full family name：`Binance-15M-Asset-Specific-Six-Strategy-Selector`
- Short id：`BIN-15M-AS6S`
- Market：Binance USD-M Futures perpetual
- Symbols：`BTCUSDT / ETHUSDT / SOLUSDT / BNBUSDT / TRXUSDT / HYPEUSDT`
- Timeframe：资产专属 `15m / 1h` 混合信号，所有高周期状态只使用闭合 K

## 家族边界

先为每个币独立选择适合的趋势状态机、突破延续或短周期反转机制，再把通过单币门禁的不同机制放入六币全局单仓账户。HYPE 三条历史家族与 `BIN-1H-AR-MAE` 只提供机制和账户结构先验，本家族不继承其版本、参数或结论。

## 当前状态

`BIN-15M-AS6S-V1` 保持 `registered / not promoted / not live-ready`；`BIN-15M-AS6S-V6-NP` 与 `BIN-15M-AS6S-V6-SBP` 均为 `dry-run / not live-ready`。V1 是九腿 nonpreemptive 历史基线；V6 固定 15 条资产专属腿、真实 15m mark 保护退出和双路线。V6 两个实例独立记账并同时运行持续 dry-run；`[2026-07-14T09:00Z, 2026-10-14T09:00Z)` 仍为锁定未来 OOS，live disabled。

## 入口

- 主账：[binance-15m-as6s-core-ledger.md](binance-15m-as6s-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 数据同步：[scripts/sync_and_audit_binance_six_asset_15m_data.py](scripts/sync_and_audit_binance_six_asset_15m_data.py)
- 当前诊断：[diagnostics/binance-as6s-current-three-month-diagnostic-2026-07-14.md](diagnostics/binance-as6s-current-three-month-diagnostic-2026-07-14.md)
- 组合优先 V2 候选观察：[diagnostics/binance-as6s-portfolio-first-v2-observation-2026-07-14.md](diagnostics/binance-as6s-portfolio-first-v2-observation-2026-07-14.md)
- 单币优先 V3 候选观察：[diagnostics/binance-as6s-asset-first-v3-diagnostic-2026-07-14.md](diagnostics/binance-as6s-asset-first-v3-diagnostic-2026-07-14.md)
- V5 联合状态观察：[diagnostics/binance-as6s-v5-joint-state-observation-2026-07-14.md](diagnostics/binance-as6s-v5-joint-state-observation-2026-07-14.md)
- V6 mark联合状态冻结：[specs/binance-as6s-v6-mark-joint-future-oos-freeze-2026-07-15.md](specs/binance-as6s-v6-mark-joint-future-oos-freeze-2026-07-15.md)
- V6 最终账户审计：[diagnostics/binance-as6s-v6-mark-clean-rsi-joint-candidate-audit-2026-07-15.md](diagnostics/binance-as6s-v6-mark-clean-rsi-joint-candidate-audit-2026-07-15.md)
- V6 消融与微调完成审计：[diagnostics/binance-as6s-v6-ablation-microtune-completion-audit-2026-07-15.md](diagnostics/binance-as6s-v6-ablation-microtune-completion-audit-2026-07-15.md)
- V6 标准近期切片：[diagnostics/binance-as6s-v6-recent-slices-2026-07-15.md](diagnostics/binance-as6s-v6-recent-slices-2026-07-15.md)
- V6 最终 OOS 门禁合同审计：[diagnostics/binance-as6s-v6-final-oos-gate-contract-audit-2026-07-15.md](diagnostics/binance-as6s-v6-final-oos-gate-contract-audit-2026-07-15.md)
- V6 Runner 对拍：[runner-tracking/binance-as6s-v6-mark-joint-runner-2026-07-15.md](runner-tracking/binance-as6s-v6-mark-joint-runner-2026-07-15.md)
- V6 Runner handoff：[live-specs/binance-as6s-v6-mark-joint-runner-draft.md](live-specs/binance-as6s-v6-mark-joint-runner-draft.md)
- V1 近期切片：[diagnostics/binance-as6s-v1-recent-slices-2026-07-14.md](diagnostics/binance-as6s-v1-recent-slices-2026-07-14.md)
- 未来 OOS 冻结：[specs/binance-as6s-future-oos-freeze-2026-07-14.md](specs/binance-as6s-future-oos-freeze-2026-07-14.md)
- V3 observation 未来 OOS 冻结：[specs/binance-as6s-v3-future-oos-freeze-2026-07-14.md](specs/binance-as6s-v3-future-oos-freeze-2026-07-14.md)
