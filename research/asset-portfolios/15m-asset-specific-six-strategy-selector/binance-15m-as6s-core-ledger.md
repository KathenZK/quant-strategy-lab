# Binance-15M-Asset-Specific-Six-Strategy-Selector Core Ledger

## Family Identity

- Full family name：`Binance-15M-Asset-Specific-Six-Strategy-Selector`
- Short id：`BIN-15M-AS6S`
- Market：Binance USD-M Futures perpetual
- Symbols：`BTCUSDT / ETHUSDT / SOLUSDT / BNBUSDT / TRXUSDT / HYPEUSDT`
- Timeframe：资产专属 `15m / 1h` 混合信号；高周期状态只使用闭合 K
- Mechanism：每币独立发现机制，再做六币全局单仓仲裁；比较不抢占与强信号抢占。
- Collision warning：不是 `BIN-1H-AR-MAE` 或 `BIN-1H-ML6AS` 的版本，不改变三条 HYPE 参考家族身份。

## Current State

- Status：`registered / not promoted / not live-ready`。
- Registered version：`Binance-15M-Asset-Specific-Six-Strategy-Selector-V1`（`BIN-15M-AS6S-V1`）。
- Canonical route：九腿、全局单仓、nonpreemptive；强突破抢占只保留为对照 observation，不属于 V1 交易路径。
- Current research observation：组合优先六腿候选已完成当前诊断，但未登记为 V2，不改变 V1 canonical route。
- Runner / dry-run / live：均未开始。
- Current gate：等待 `2026-10-14T09:00Z` 后执行一次性未来最终 OOS；此前不得调参或 promotion。
- Final OOS：`[2026-07-14, 2026-10-14)` 的未来新增数据；冻结后不得调参。

## Version Rules

- `V1` 固定九条资产专属腿、账户缩放 `0.75`、nonpreemptive 单仓仲裁、成本、执行和冻结时点。
- 单币机制试验、reused-holdout 淘汰和 strong-breakout-preemptive 对照路线均为 observation，不获得版本号。
- 成分机制或全局账户状态机变化都需要新 observation；已登记后发生交易路径变化则需要新版本。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| `BIN-15M-AS6S-V1` | `registered / not promoted / not live-ready` | 九条资产专属 `15m/1h` 腿，全局单仓，持仓期间绝不抢占，账户缩放 `0.75` | full：`3.611x annual / +1012.61% / -12.37% DD / 90.55% / 307`；reused 3m：`+42.32% / -6.25% DD / 92.50% / 40` | [冻结规格](specs/binance-as6s-future-oos-freeze-2026-07-14.md)；[近期切片](diagnostics/binance-as6s-v1-recent-slices-2026-07-14.md) | 当前诊断通过；未来三个月最终 OOS 未完成，禁止 promotion |
| `portfolio-first-v2-observation` | `explore / not registered / not promoted / not live-ready` | 单腿不限胜率、账户胜率硬门槛；六腿、账户缩放 `0.50`；nonpreemptive 主候选与强突破抢占对照 | nonpreemptive full：`6.525x annual / +4154.96% / -8.93% DD / 89.07% / 247`；当前 3m：`+28.46% / -7.49% DD / 81.08% / 37` | [组合优先诊断](diagnostics/binance-as6s-portfolio-first-v2-observation-2026-07-14.md) | 当前诊断通过；最近 1m 为负且未来 OOS 未完成，不登记 V2 |

## Shared Assumptions

- BTC/ETH/SOL/BNB/TRX 单币研究尽量使用最近两年；HYPE 使用 Binance 上市以来全部历史。
- V1 选择只使用 `<2026-04-14` 数据；`[2026-04-14, 2026-07-14)` 对 V1 是 reused holdout，只能淘汰。组合优先 observation 按用户新口径把截至 `2026-07-14` 的数据用于研究选择，并把 `[2026-07-14, 2026-10-14)` 保留为自己的未来最终 OOS。
- Binance 成本：手续费 `0.001/fill`、基础滑点 `4 bps/fill`、真实历史 funding；另做 `8 bps/fill` 压力。
- 多空双向，允许空仓，账户最大暴露 `3x`。
- V1 账户缩放 `0.75`，冻结腿的最大有效暴露 `1.875x`；同一时刻最多一笔持仓。
- 最终组合硬门槛：full 和未来 OOS 胜率均 `>=80%`，full trades `>=200`，未来 OOS trades `>=30`，full 和未来 OOS 最大回撤均严格 `<20%`，收益均为正。

## Evidence Map

- 数据同步与审计：[scripts/sync_and_audit_binance_six_asset_15m_data.py](scripts/sync_and_audit_binance_six_asset_15m_data.py)
- 数据质量审计：[diagnostics/binance-six-asset-15m-data-quality-2026-07-14.md](diagnostics/binance-six-asset-15m-data-quality-2026-07-14.md)
- 结构化数据质量报告：[artifacts/binance_six_asset_15m_data_quality_2026-07-14.json](artifacts/binance_six_asset_15m_data_quality_2026-07-14.json)
- 当前三个月与组合诊断：[diagnostics/binance-as6s-current-three-month-diagnostic-2026-07-14.md](diagnostics/binance-as6s-current-three-month-diagnostic-2026-07-14.md)
- V1 近期切片审计：[diagnostics/binance-as6s-v1-recent-slices-2026-07-14.md](diagnostics/binance-as6s-v1-recent-slices-2026-07-14.md)
- V1 近期切片结构化结果：[artifacts/binance_15m_as6s_v1_recent_slices_2026-07-14.json](artifacts/binance_15m_as6s_v1_recent_slices_2026-07-14.json)
- 未来 OOS 冻结规格：[specs/binance-as6s-future-oos-freeze-2026-07-14.md](specs/binance-as6s-future-oos-freeze-2026-07-14.md)
- 机器冻结清单：[artifacts/binance_as6s_future_oos_freeze_2026-07-14.json](artifacts/binance_as6s_future_oos_freeze_2026-07-14.json)
- 混合账户结果：[artifacts/binance_hybrid_asset_specific_account_2026-07-14.json](artifacts/binance_hybrid_asset_specific_account_2026-07-14.json)
- 组合优先 V2 candidate observation：[diagnostics/binance-as6s-portfolio-first-v2-observation-2026-07-14.md](diagnostics/binance-as6s-portfolio-first-v2-observation-2026-07-14.md)
- 组合优先结构化结果：[artifacts/binance_as6s_portfolio_first_v2_candidate_2026-07-14.json](artifacts/binance_as6s_portfolio_first_v2_candidate_2026-07-14.json)
- 组合优先研究脚本：[scripts/research_binance_as6s_portfolio_first_v2.py](scripts/research_binance_as6s_portfolio_first_v2.py)
