# SOL-1H-Adaptive-Regime 主账

## 家族身份

- Full family name：`SOL-1H-Adaptive-Regime`
- Short id：`SOL-1H-AR`
- Market：Binance USD-M Futures `SOLUSDT` perpetual
- Timeframe：`1h`
- Version lineage：独立家族；不得引用 BTC/HYPE 的裸版本号或继承其版本身份

## 当前状态

`SOL-1H-Adaptive-Regime-V3 registered / not promoted / not live-ready`。

V1 是 2026-07-03 百万组广搜后按 prefit 规则冻结并揭盲 locked OOS 的诊断基线。V2 是 2026-07-07 高胜率硬目标搜索中的最佳冻结观察值。V3 是 V2 的机制重构：保留 Donchian core，将 VWAP 改为 `arm → confirm → expire` satellite。V3 full annual `2.10x`、DD `-19.05%`、win `79.17%`；reused holdout 只有 `3` 笔，因此不是 dry-run/live 版本。

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
| `SOL-1H-Adaptive-Regime-V1` | `historical pre-dry-run finding / not live-ready` | `donchian_break + bb_revert` ensemble；闭合 `1h` 信号、下一根 open 成交 | [搜索诊断](diagnostics/sol-1h-adaptive-regime-search-2026-07-03.md)；[V1 消融](ablations/sol-1h-ar-v1-full-parameter-ablation-2026-07-03.md) | full annual `2.18x`、DD `-18.86%`、win `76.60%`、trades `94`；locked OOS annual `0.71x` | locked OOS 未通过硬门槛；历史 finding，不是当前终态 |
| `SOL-1H-Adaptive-Regime-V2` | `historical pre-dry-run finding / not live-ready` | `donchian_break + vwap_revert` ensemble；高胜率搜索冻结观察值 | [高胜率搜索](diagnostics/sol-1h-ar-high-win-target-search-2026-07-07.md)；[V2 规格](specs/sol-1h-ar-v2-parameter-spec-2026-07-07.md) | full annual `2.07x`、DD `-17.41%`、win `93.91%`；reused holdout annual `0.70x` | 未达硬目标且 holdout 已揭盲；历史 finding，不是当前终态 |
| `SOL-1H-Adaptive-Regime-V3` | `registered / not promoted / not live-ready` | `Donchian core + VWAP arm-confirm-expire satellite`；此前 `V2-SM-OBS`；VWAP 偏离事件后等待最多 3 bars 的 `roc6 + MACD` 同向确认 | `specs/sol-1h-ar-v3-parameter-spec-2026-07-13.md`；`diagnostics/sol-1h-ar-v2-vwap-state-machine-2026-07-10.md`；`scripts/research_sol_1h_ar_v2_vwap_state_machine.py`；`artifacts/sol_1h_ar_v2_vwap_state_machine_2026-07-10.json` | prefit annual `2.3129x`、DD `-19.05%`、win `79.57%`、trades `93`；full annual `2.0977x`、DD `-19.05%`、win `79.17%`、trades `96`；reused holdout return `+2.61%`、DD `-4.55%`、trades `3` | 用户明确登记；reused holdout 已揭盲且仅 3 笔，禁止 dry-run/live，等待 fresh forward 与 live-executable audit |

`V1` 后续 full ablation、clean interface、clean tune 只用于诊断删参与参数面观察；clean tune 不登记为 `V1.1`。V2 来自独立的高胜率硬目标搜索，不继承 clean tune 的版本身份。V1/V2 的旧失败判断统一保留为 historical pre-dry-run findings；当前家族状态以上方 Current State 的 V3 `registered / not promoted / not live-ready` 为准。

2026-07-10 机制诊断确认 V2 的核心问题是负偏收益结构与 VWAP short regime 失效。`arm → confirm → expire` 状态机的 prefit-only 观察把 reused holdout 改为 return `+2.61%`、annual `1.1089x`、DD `-4.55%`，但只有 `3` 笔且窗口已揭盲。2026-07-13 用户明确将该观察登记为 V3；随后约 10 天 fresh forward 为 `0` 笔，不能验证或否定 V3。登记不改变其 not-promoted / not-live-ready 边界。

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
- V2 改进综合结论：`notes/sol-1h-ar-v2-improvement-conclusion-2026-07-10.md`
- V2 收益结构改造：`diagnostics/sol-1h-ar-v2-mechanism-redesign-2026-07-10.md`
- V2 分段止盈/失效退出：`diagnostics/sol-1h-ar-v2-staged-exit-2026-07-10.md`
- V2 腿级 governor：`diagnostics/sol-1h-ar-v2-leg-governor-2026-07-10.md`
- V2 VWAP 状态机：`diagnostics/sol-1h-ar-v2-vwap-state-machine-2026-07-10.md`
- V3 参数规格：`specs/sol-1h-ar-v3-parameter-spec-2026-07-13.md`
- V3 fresh forward：`diagnostics/sol-1h-ar-v3-fresh-forward-2026-07-13.md`
- 数据与搜索产物：`artifacts/`
