# SOL-1H-Adaptive-Regime 主账

## 家族身份

- Full family name：`SOL-1H-Adaptive-Regime`
- Short id：`SOL-1H-AR`
- Market：Binance USD-M Futures `SOLUSDT` perpetual
- Timeframe：`1h`
- Version lineage：独立家族；不得引用 BTC/HYPE 的裸版本号或继承其版本身份

## 当前状态

`SOL-1H-Adaptive-Regime-V2 registered observation / NO-GO / not promoted / not live-ready`。

V1 是 2026-07-03 百万组广搜后按 prefit 规则冻结并揭盲 locked OOS 的诊断基线。V2 是 2026-07-07 高胜率硬目标搜索中的最佳冻结观察值，机制为 `donchian_break + vwap_revert` ensemble。V2 full 区间达到 `2.07x` 年化、`-17.41%` 回撤、`93.91%` 胜率，但没有达到年化 `>=10x`，最近三个月 reused holdout 为 `0.70x` 年化、`66.67%` 胜率，因此仍不是 candidate、paper-live、dry-run、handoff 或 live 版本。

当前没有 SOL production runner、交易所订单/仓位对账、重启恢复、missing-bar fail-closed、kill switch、tick/step rounding 回测与真实 stop-market 滑点证据。

## 硬门槛

- 年化权益倍率 `>=10.0x`，等价于年化收益 `>=900%`。
- 胜率 `>=50%`。
- 最大回撤严格小于 `20%`。
- 最近三个月 locked OOS 必须按预冻结规则一次性评估。
- 进入任何 promotion 状态前必须通过 live-executable 审计，并具备可复现的生产状态机证据。

## 版本表

| Version | Status | Frozen mechanism | Evidence | Metrics | Decision |
| --- | --- | --- | --- | --- | --- |
| `SOL-1H-Adaptive-Regime-V1` | `registered baseline / NO-GO / not promoted / not live-ready` | `donchian_break + bb_revert` ensemble；`ENS__SOL_1H_AR_R594184__SOL_1H_AR_R736318`；闭合 `1h` 信号、下一根 open 成交、Binance fee `0.001`/fill、slippage `4 bps`/fill、真实 funding | `diagnostics/sol-1h-adaptive-regime-search-2026-07-03.md`；`ablations/sol-1h-ar-v1-full-parameter-ablation-2026-07-03.md`；`notes/sol-1h-ar-v1-clean-interface-2026-07-03.md`；`notes/sol-1h-ar-v1-clean-parameter-tune-2026-07-03.md`；`scripts/sol_1h_ar_v1.py`；`artifacts/sol_1h_adaptive_regime_search_2026-07-03.json` | full annual `2.18x`、return `330.75%`、DD `-18.86%`、win `76.60%`、trades `94`；locked OOS annual `0.71x`、return `-8.09%`、DD `-16.19%`、win `50.00%`、trades `8` | locked OOS 未通过 `10x / 50% / <20% DD` 硬门槛；禁止 candidate、paper-live、dry-run、handoff 或 live |
| `SOL-1H-Adaptive-Regime-V2` | `registered observation / NO-GO / not promoted / not live-ready` | `donchian_break + vwap_revert` ensemble；`ENS__SOL_1H_AR_HW_R132002__SOL_1H_AR_HW_R243705`；高胜率硬目标搜索最佳冻结观察值；闭合 `1h` 信号、下一根 open 成交、Binance fee `0.001`/fill、slippage `4 bps`/fill、真实 funding | `diagnostics/sol-1h-ar-high-win-target-search-2026-07-07.md`；`specs/sol-1h-ar-v2-parameter-spec-2026-07-07.md`；`scripts/research_sol_1h_ar_high_win_target_search.py`；`artifacts/sol_1h_ar_high_win_search_2026-07-07.json` | full annual `2.07x`、return `290.00%`、DD `-17.41%`、win `93.91%`、trades `115`；last `1y` annual `1.60x`、win `92.31%`；reused holdout annual `0.70x`、return `-8.53%`、DD `-15.69%`、win `66.67%`、trades `6` | 未达到 `10x / 80% / <20% DD` 硬目标，且最近三个月为已揭盲 reused holdout；禁止 candidate、paper-live、dry-run、handoff 或 live |

`V1` 后续 full ablation、clean interface、clean tune 只用于诊断删参与参数面观察；clean tune 不登记为 `V1.1`。V2 来自独立的高胜率硬目标搜索，不继承 clean tune 的版本身份。V2 登记只固定最佳观察值与参数规格，不改变 `NO-GO` 结论。

## 证据索引

- 数据抓取与质量检查：`scripts/fetch_sol_binance_1h.py`
- 多指标宽搜索：`scripts/research_sol_1h_adaptive_regime_search.py`
- V1 广搜诊断结论：`diagnostics/sol-1h-adaptive-regime-search-2026-07-03.md`
- 冻结边界与实盘可执行审计：`scripts/audit_sol_1h_adaptive_regime_boundary.py`
- V1 冻结 wrapper：`scripts/sol_1h_ar_v1.py`
- V1 全参数消融：`scripts/research_sol_1h_ar_v1_full_ablation.py`
- V1 全参数消融报告：`ablations/sol-1h-ar-v1-full-parameter-ablation-2026-07-03.md`
- V1 clean interface：`scripts/sol_1h_ar_v1_clean.py`
- V1 clean interface 报告：`notes/sol-1h-ar-v1-clean-interface-2026-07-03.md`
- V1 clean tune：`scripts/research_sol_1h_ar_v1_clean_tune.py`
- V1 clean tune 报告：`notes/sol-1h-ar-v1-clean-parameter-tune-2026-07-03.md`
- V2 高胜率硬目标搜索：`scripts/research_sol_1h_ar_high_win_target_search.py`
- V2 高胜率硬目标搜索报告：`diagnostics/sol-1h-ar-high-win-target-search-2026-07-07.md`
- V2 参数规格：`specs/sol-1h-ar-v2-parameter-spec-2026-07-07.md`
- 数据与搜索产物：`artifacts/`
