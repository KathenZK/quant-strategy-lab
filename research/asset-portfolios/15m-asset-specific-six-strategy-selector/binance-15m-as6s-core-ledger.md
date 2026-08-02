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

- Status：`BIN-15M-AS6S-V6-NP` 与 `BIN-15M-AS6S-V6-SBP` 均为 `dry-run / not live-ready`；live disabled。
- Registered versions：`BIN-15M-AS6S-V1` 与 `BIN-15M-AS6S-V6`。
- Canonical routes：V1 是九腿 nonpreemptive 历史基线；V6 是当前 15 腿、真实 mark
  保护退出的双路线注册观察，nonpreemptive 为主观察、强突破抢占为对照。
- Runner：V6 两条路线均已实现，严格离线 parity、失败注入、配置与 CLI smoke
  通过；两个独立实例已获准持续 dry-run，live 仍未获授权。
- Current gate：等待 `2026-10-14T09:00Z` 后执行一次性未来最终 OOS；此前不得调参或 promotion。中期账本观察（audit-only，不作选择依据）：[2026-07-30 interim](runner-tracking/binance-as6s-v6-dry-run-interim-2026-07-30.md)。
- Final OOS：`[2026-07-14, 2026-10-14)` 的未来新增数据；冻结后不得调参。

## Version Rules

- `V1` 固定九条资产专属腿、账户缩放 `0.75`、nonpreemptive 单仓仲裁、成本、执行和冻结时点。
- `V6` 固定 15 条资产专属腿、真实 15m mark 保护语义、账户缩放 `0.75` 与两套
  路由；任何腿、参数、scale、路由或成交语义变化都必须新版本，且在最终 OOS
  揭示前禁止修改。
- 单币机制试验与 reused-holdout 淘汰均为 observation；V6 的
  strong-breakout-preemptive 是同一注册版本内的冻结对照路线，不单独获得版本号。
- 成分机制或全局账户状态机变化都需要新 observation；已登记后发生交易路径变化则需要新版本。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| `BIN-15M-AS6S-V1` | `registered / not promoted / not live-ready` | 九条资产专属 `15m/1h` 腿，全局单仓，持仓期间绝不抢占，账户缩放 `0.75` | full：`3.611x annual / +1012.61% / -12.37% DD / 90.55% / 307`；reused 3m：`+42.32% / -6.25% DD / 92.50% / 40` | [冻结规格](specs/binance-as6s-future-oos-freeze-2026-07-14.md)；[近期切片](diagnostics/binance-as6s-v1-recent-slices-2026-07-14.md) | 当前诊断通过；未来三个月最终 OOS 未完成，禁止 promotion |
| `BIN-15M-AS6S-V6-NP` / `BIN-15M-AS6S-V6-SBP` | `dry-run / not live-ready` | 15 条资产专属腿、真实 15m mark 保护退出、全局单仓双路线，scale `0.75` | NP full：`31.078x annual / -17.99% DD / 85.65% / 634`；SBP full：`30.817x / -17.04% DD / 85.21% / 568` | [冻结规格](specs/binance-as6s-v6-mark-joint-future-oos-freeze-2026-07-15.md)；[账户审计](diagnostics/binance-as6s-v6-mark-clean-rsi-joint-candidate-audit-2026-07-15.md)；[Runner 对拍](runner-tracking/binance-as6s-v6-mark-joint-runner-2026-07-15.md)；[handoff](live-specs/binance-as6s-v6-mark-joint-runner-draft.md) | 两条独立 dry-run 路线已获授权；45 信号、15 退出、`634/568` 全路由 PASS；未来 OOS 未完成，live 禁止 |
| `BIN-15M-AS6S-V5-JOINT-NP`（V5 joint-state observation） | `explore / not registered / not promoted / not live-ready` | 15 条资产专属腿、真实成交驱动 cooldown、nonpreemptive 联合单仓，账户缩放 `0.40` | full：`5.8156x annual / +3280.13% / -12.86% DD / 85.17% / 553` | [Runner 对拍](runner-tracking/binance-as6s-v5-joint-runner-2026-07-15.md)；[handoff](live-specs/binance-as6s-v5-joint-state-runner-draft.md) | Runner 已实现且配置 disabled；45 信号、15 退出、553 路由 PASS；不构成 V5 注册或 promotion |
| `portfolio-first-v2-observation` | `explore / not registered / not promoted / not live-ready` | 单腿不限胜率、账户胜率硬门槛；六腿、账户缩放 `0.50`；nonpreemptive 主候选与强突破抢占对照 | nonpreemptive full：`6.525x annual / +4154.96% / -8.93% DD / 89.07% / 247`；当前 3m：`+28.46% / -7.49% DD / 81.08% / 37` | [组合优先诊断](diagnostics/binance-as6s-portfolio-first-v2-observation-2026-07-14.md) | 当前诊断通过；最近 1m 为负且未来 OOS 未完成，不登记 V2 |

## Shared Assumptions

- BTC/ETH/SOL/BNB/TRX 单币研究尽量使用最近两年；HYPE 使用 Binance 上市以来全部历史。
- V1 选择只使用 `<2026-04-14` 数据；`[2026-04-14, 2026-07-14)` 对 V1 是 reused holdout，只能淘汰。组合优先 observation 按用户新口径把截至 `2026-07-14` 的数据用于研究选择，并把 `[2026-07-14, 2026-10-14)` 保留为自己的未来最终 OOS。
- Binance 成本：手续费 `0.001/fill`、基础滑点 `4 bps/fill`、真实历史 funding；另做 `8 bps/fill` 压力。
- 多空双向，允许空仓，账户最大暴露 `3x`。
- V1 账户缩放 `0.75`，冻结腿的最大有效暴露 `1.875x`；同一时刻最多一笔持仓。
- V6 两条路线账户缩放均为 `0.75`，最大有效暴露 `2.25x`；同一时刻最多一笔持仓。
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
- V6 冻结规格：[specs/binance-as6s-v6-mark-joint-future-oos-freeze-2026-07-15.md](specs/binance-as6s-v6-mark-joint-future-oos-freeze-2026-07-15.md)
- V6 机器冻结：[artifacts/binance_as6s_v6_mark_joint_future_oos_freeze_2026-07-15.json](artifacts/binance_as6s_v6_mark_joint_future_oos_freeze_2026-07-15.json)
- V6 全参数账户消融：[ablations/binance-as6s-v6-mark-account-ablation-2026-07-15.md](ablations/binance-as6s-v6-mark-account-ablation-2026-07-15.md)
- V6 参数 clean surface：[ablations/binance-as6s-v6-clean-surface-2026-07-15.md](ablations/binance-as6s-v6-clean-surface-2026-07-15.md)
- V6 消融与微调完成审计：[diagnostics/binance-as6s-v6-ablation-microtune-completion-audit-2026-07-15.md](diagnostics/binance-as6s-v6-ablation-microtune-completion-audit-2026-07-15.md)
- V6 标准近期切片：[diagnostics/binance-as6s-v6-recent-slices-2026-07-15.md](diagnostics/binance-as6s-v6-recent-slices-2026-07-15.md)
- V6 最终 OOS 门禁合同审计：[diagnostics/binance-as6s-v6-final-oos-gate-contract-audit-2026-07-15.md](diagnostics/binance-as6s-v6-final-oos-gate-contract-audit-2026-07-15.md)
- V6 最终账户审计：[diagnostics/binance-as6s-v6-mark-clean-rsi-joint-candidate-audit-2026-07-15.md](diagnostics/binance-as6s-v6-mark-clean-rsi-joint-candidate-audit-2026-07-15.md)
- V6 Runner 对拍：[runner-tracking/binance-as6s-v6-mark-joint-runner-2026-07-15.md](runner-tracking/binance-as6s-v6-mark-joint-runner-2026-07-15.md)
- V6 Runner 机器证据：[artifacts/binance_as6s_v6_mark_joint_runner_parity_2026-07-15.json](artifacts/binance_as6s_v6_mark_joint_runner_parity_2026-07-15.json)
- V6 Runner handoff：[live-specs/binance-as6s-v6-mark-joint-runner-draft.md](live-specs/binance-as6s-v6-mark-joint-runner-draft.md)
