# SOL-1H-Adaptive-Regime 主账

## 家族身份

- Full family name：`SOL-1H-Adaptive-Regime`
- Short id：`SOL-1H-AR`
- Market：Binance USD-M Futures `SOLUSDT` perpetual
- Timeframe：`1h`
- Version lineage：独立家族；不得引用 BTC/HYPE 的裸版本号或继承其版本身份

## 当前状态

`SOL-1H-Adaptive-Regime-V1 registered diagnostic baseline / NO-GO / not promoted / not live-ready`。

V1 是 2026-07-03 百万组广搜后按 prefit 规则冻结并揭盲 locked OOS 的诊断基线，不是 candidate、paper-live、dry-run、handoff 或 live 版本。最近三个月 locked OOS 未通过收益硬门槛，且当前没有 SOL production runner、交易所订单/仓位对账、重启恢复、missing-bar fail-closed、kill switch、tick/step rounding 回测与真实 stop-market 滑点证据。

## 硬门槛

- 年化权益倍率 `>=10.0x`，等价于年化收益 `>=900%`。
- 胜率 `>=50%`。
- 最大回撤严格小于 `20%`。
- 最近三个月 locked OOS 必须按预冻结规则一次性评估。
- 进入任何 promotion 状态前必须通过 live-executable 审计，并具备可复现的生产状态机证据。

## 版本表

| Version | Status | Frozen mechanism | Evidence | Metrics | Decision |
| --- | --- | --- | --- | --- | --- |
| `SOL-1H-Adaptive-Regime-V1` | `registered diagnostic baseline / NO-GO / not promoted / not live-ready` | `donchian_break + bb_revert` ensemble；`ENS__SOL_1H_AR_R594184__SOL_1H_AR_R736318`；闭合 `1h` 信号、下一根 open 成交、Binance fee `0.001`/fill、slippage `4 bps`/fill、真实 funding | `diagnostics/sol-1h-adaptive-regime-search-2026-07-03.md`；`ablations/sol-1h-ar-v1-full-parameter-ablation-2026-07-03.md`；`research-notes/sol-1h-ar-v1-clean-interface-2026-07-03.md`；`research-notes/sol-1h-ar-v1-clean-parameter-tune-2026-07-03.md`；`scripts/sol_1h_ar_v1.py`；`artifacts/sol_1h_adaptive_regime_search_2026-07-03.json` | full annual `2.18x`、return `330.75%`、DD `-18.86%`、win `76.60%`、trades `94`；locked OOS annual `0.71x`、return `-8.09%`、DD `-16.19%`、win `50.00%`、trades `8` | locked OOS 未通过 `10x / 50% / <20% DD` 硬门槛；禁止 candidate、paper-live、dry-run、handoff 或 live |

`V1` 后续 full ablation、clean interface、clean tune 只用于诊断删参与参数面观察；除非另有新增 forward evidence 和完整 live-executable 审计，不得把 clean tune observation 自动登记为 `V1.1/V2`。本轮 clean tune 的 prefit annual 提升到 `5.7104x`，但 reused holdout annual `0.1607x`、DD `-42.87%`，current full DD 也为 `-42.87%`，进一步确认不能 promotion。

## 证据索引

- 数据抓取与质量检查：`scripts/fetch_sol_binance_1h.py`
- 多指标宽搜索：`scripts/research_sol_1h_adaptive_regime_search.py`
- V1 广搜诊断结论：`diagnostics/sol-1h-adaptive-regime-search-2026-07-03.md`
- 冻结边界与实盘可执行审计：`scripts/audit_sol_1h_adaptive_regime_boundary.py`
- V1 冻结 wrapper：`scripts/sol_1h_ar_v1.py`
- V1 全参数消融：`scripts/research_sol_1h_ar_v1_full_ablation.py`
- V1 全参数消融报告：`ablations/sol-1h-ar-v1-full-parameter-ablation-2026-07-03.md`
- V1 clean interface：`scripts/sol_1h_ar_v1_clean.py`
- V1 clean interface 报告：`research-notes/sol-1h-ar-v1-clean-interface-2026-07-03.md`
- V1 clean tune：`scripts/research_sol_1h_ar_v1_clean_tune.py`
- V1 clean tune 报告：`research-notes/sol-1h-ar-v1-clean-parameter-tune-2026-07-03.md`
- 数据与搜索产物：`artifacts/`
