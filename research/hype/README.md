# HYPE Research Index

HYPE has multiple unrelated strategy families that reuse version numbers. Do not read by bare version number: choose the family first, and always prefer the complete family name with historical aliases only as secondary labels.

## Required Reading Order

1. `../README.md`
2. This file
3. The target family `README.md`
4. That family's `decision-log.md`
5. Only then open canonical specs, diagnostics, reports indexes, or retained artifacts.

For the newer Binance HYPE `5m` pullback + ATR trailing-stop research line, use:

1. `5m-pullback-trail/README.md`
2. `5m-pullback-trail/hype-5m-pullback-trail-core-ledger.md`
3. `5m-pullback-trail/ablations/hype-5m-pbtr-v6-full-parameter-ablation-2026-06-25.md`
4. `5m-pullback-trail/live-specs/hype-5m-pullback-trail-v2-live-spec.md`
5. `5m-pullback-trail/research-notes/hype-5m-pullback-trail-v2-combo-test-2026-06-23.md`

For the Binance HYPEUSDT `15m` pullback event-source research line, use:

1. `15m-pullback-trail/README.md`
2. `15m-pullback-trail/decision-log.md`
3. `15m-pullback-trail/diagnostics/hype-15m-pullback-trail-bracket-search-2026-06-30.md`
4. `15m-pullback-trail/diagnostics/hype-15m-pullback-trail-v3-3-migration-2026-06-30.md`

For the Binance HYPEUSDT `15m` Riptide trend-background RSI pullback research line, use:

1. `15m-riptide/README.md`
2. `15m-riptide/decision-log.md`
3. `15m-riptide/diagnostics/hype-15m-riptide-v13-cache-audit-2026-06-30.md`

For the Binance HYPEUSDT `5m` micro-scalp research line, use:

1. `5m-micro-scalp/README.md`
2. `5m-micro-scalp/decision-log.md`
3. `5m-micro-scalp/diagnostics/hype-5m-micro-scalp-search-2026-06-26.md`
4. `5m-micro-scalp/diagnostics/hype-5m-micro-scalp-relaxed-rounds-2026-06-26.md`
5. `5m-micro-scalp/diagnostics/hype-5m-micro-scalp-candidate-robustness-2026-06-26.md`
6. `5m-micro-scalp/canonical-specs/hype-5m-micro-scalp-v1-baseline-spec.md`
7. `5m-micro-scalp/ablations/hype-5m-micro-scalp-v1-full-parameter-ablation-2026-06-29.md`
8. `5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-simplified-combo-search-2026-06-30.md`
9. `5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-simplified-candidate-robustness-2026-06-30.md`
10. `5m-micro-scalp/canonical-specs/hype-5m-micro-scalp-v1-1-baseline-spec.md`
11. `5m-micro-scalp/ablations/hype-5m-micro-scalp-v1-1-full-parameter-ablation-2026-06-30.md`
12. `5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-1-micro-tune-2026-06-30.md`
13. `5m-micro-scalp/canonical-specs/hype-5m-micro-scalp-v1-2-baseline-spec.md`
14. `5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-2-registration-and-leverage-retest-2026-07-01.md`

For the Binance HYPEUSDT `5m` event-quality scoring research line, use:

1. `5m-event-quality-scoring/README.md`
2. `5m-event-quality-scoring/hype-5m-event-quality-scoring-core-ledger.md`
3. `5m-event-quality-scoring/decision-log.md`
4. `5m-event-quality-scoring/diagnostics/hype-5m-event-quality-v0-2026-06-27.md`
5. `5m-event-quality-scoring/diagnostics/hype-5m-seeded-event-quality-v0-2026-06-27.md`
6. `5m-event-quality-scoring/diagnostics/hype-5m-seeded-event-quality-v01-style-prune-2026-06-27.md`
7. `5m-event-quality-scoring/diagnostics/hype-5m-seeded-event-quality-v01-full-ablation-2026-06-27.md`
8. `5m-event-quality-scoring/diagnostics/hype-5m-seeded-v1-live-feasibility-2026-06-27.md`
9. `5m-event-quality-scoring/diagnostics/hype-5m-seeded-v1-strict-seed-audit-2026-06-27.md`

For the Binance HYPEUSDT `5m` two-MA pullback scalp research line, use:

1. `5m-ma-pullback-scalp/README.md`
2. `5m-ma-pullback-scalp/decision-log.md`
3. `5m-ma-pullback-scalp/diagnostics/hype-5m-ma-pullback-scalp-search-2026-06-26.md`
4. `5m-ma-pullback-scalp/diagnostics/hype-5m-ma-pullback-scalp-robustness-2026-06-26.md`

For `HYPE-EMA-Crossover` promoted versions, start from `15m-ema-crossover/hype-ema-x-core-ledger.md`, then:

1. `15m-ema-crossover/canonical-specs/hype-ema-x-v18-baseline-spec.md`（干净参数）
2. `15m-ema-crossover/research-notes/hype-ema-x-v15-v16-promoted-strategy-specs.md`
3. `15m-ema-crossover/ablations/hype-ema-x-v17-hybrid-ablation.md`

For the Binance HYPEUSDT `1m` EMA cross research line, use:

1. `1m-ema-crossover/README.md`
2. `1m-ema-crossover/decision-log.md`
3. `1m-ema-crossover/diagnostics/hype-1m-ema-crossover-live-search-2026-06-25.md`

For the Binance HYPEUSDT `1m` two-MA pullback scalp research line, use:

1. `1m-ma-pullback-scalp/README.md`
2. `1m-ma-pullback-scalp/decision-log.md`
3. `1m-ma-pullback-scalp/diagnostics/hype-1m-ma-pullback-scalp-search-2026-06-26.md`

## Strategy Families

| Full family name | Historical alias | Directory | Core idea | Collision warning |
| --- | --- | --- | --- | --- |
| `HYPE-Candle-Count-Reversal` | `HYPE-CC` | `15m-candle-count-reversal/` | 10-of-8 candle color reversal with ATR risk controls and early-exit variants | `V35` here is not trend breakout `V35` |
| `HYPE-EMA-Crossover` | `HYPE-EMA-X` | `15m-ema-crossover/` | EMA golden/death cross lineage, evolved through V14-era filters, exits, state machine, late re-entry, and effective-cross scoring | Do not merge this with later `HYPE-EMA-Trend-Breakout` just because both use EMA96/384 |
| `HYPE-1H-Adaptive-Regime` | `HYPE-1H-AR` | `1h-adaptive-regime/` | Binance HYPEUSDT `1h` broad indicator search ending in a DI-cross + stochastic-reversal boundary ensemble | V1 frozen boundary; V2 clean-equivalent baseline; tune rejected; NO-GO |
| `HYPE-15M-Multi-Indicator-Intraday` | `HYPE-15M-MII` | `15m-multi-indicator-intraday/` | Binance HYPEUSDT `15m` broad RSI/MACD/EMA/ADX/ATR/volume/structure intraday search | Do not relabel broad indicator-search results as existing EMA-X, EMA-TB, or candle-count versions |
| `HYPE-15M-Riptide` | - | `15m-riptide/` | Binance HYPEUSDT `15m` EMA20/60 trend-background RSI pullback with 1h RV regime gate and ATR bracket exits | Do not merge with `HYPE-15M-MII` or `HYPE-15M-Pullback-Trail`; V13 is local to Riptide |
| `HYPE-1M-EMA-Crossover` | `HYPE-1M-EMA-X` | `1m-ema-crossover/` | Binance HYPEUSDT `1m` EMA cross lineage with live-executable next-bar entries, fixed TP, and trailing TP | Do not merge this with `15m-ema-crossover` just because both are EMA cross research |
| `HYPE-1M-MA-Pullback-Scalp` | - | `1m-ma-pullback-scalp/` | Binance HYPEUSDT `1m` slow/fast MA trend-pullback scalp with HH/HL or LL/LH structure and fixed brackets | Do not merge this with `HYPE-1M-EMA-Crossover`; first executable search is no-go |
| `HYPE-EMA-Trend-Breakout` | `HYPE-EMA-TB` | `15m-ema-trend-breakout/` | Later EMA trend breakout / chase-long-chase-short lineage with ADX, volume, 1h confirmation, and cross-exchange execution variants | `V35` here is not candle-count `V35` or EMA-cross `V14` |
| `HYPE-5M-Pullback-Trail` | `HYPE-5M-PBTR` | `5m-pullback-trail/` | Binance HYPE `5m` pullback/resume entries with ATR trailing-stop exits | Local `V1/V2` here are not legacy 15m `HYPE-EMA-Trend-Breakout` V1/V2 |
| `HYPE-15M-Pullback-Trail` | - | `15m-pullback-trail/` | Binance HYPEUSDT `15m` pullback event-source research; includes V3.3 delayed trailing migration and executable bracket search | V3.3 migration is no-go; bracket candidate is paper-audit only, not a 5m PBTR promoted version |
| `HYPE-5M-MA-Pullback-Scalp` | - | `5m-ma-pullback-scalp/` | Binance HYPEUSDT `5m` slow/fast MA trend-pullback scalp with HH/HL or LL/LH structure and fixed brackets | Do not merge this with `HYPE-5M-Micro-Scalp`; current candidates are paper-audit only |
| `HYPE-5M-Micro-Scalp` | `HYPE-5M-MS` | `5m-micro-scalp/` | Binance HYPEUSDT `5m` high-frequency micro-profit scalp search with immediate executable TP/SL brackets | Do not treat high win-rate no-go rows as pullback-trail or live candidates |
| `HYPE-5M-Event-Quality-Scoring` | `HYPE-5M-EQS` | `5m-event-quality-scoring/` | Binance HYPEUSDT `5m` event-quality scoring over candidate events and seeded micro-scalp signals | Do not treat seeded paper-audit rows as generic micro-scalp or live-ready candidates |

## Core Markdown Ledgers

- `cross-strategy-account/README.md`：HYPE 多策略共享子账户和全局单仓组合诊断入口；当前包含 `HYPE-5M-PBTR-V6.2.1` + `HYPE-15M-MII-V1.3` 共享 HYPEUSDT 子账户回放，结论为收益叠加但组合已平仓 DD 扩到 `-30.28%`，逐 K close MTM DD 为 `-32.34%`，最不利 high/low 标记浮亏约 `-55%`，不提升任一子策略状态。
- `1h-adaptive-regime/hype-1h-ar-core-ledger.md`：`HYPE-1H-Adaptive-Regime` 主账；V1 为冻结边界，V2 为全字段消融后的干净等价版，均不可实盘。后续登记 `Vx` 必须更新此主账。
- `1h-adaptive-regime/README.md`：`HYPE-1H-Adaptive-Regime` 入口。
- `1h-adaptive-regime/diagnostics/hype-binance-1h-data-quality-2026-07-02.md`：Binance HYPEUSDT 永续 `9,545` 根全量闭合 `1h` K 数据质量报告。
- `1h-adaptive-regime/canonical-specs/hype-1h-ar-v1-baseline-spec.md`：V1 正式版本与 current-full 冻结结果。
- `1h-adaptive-regime/canonical-specs/hype-1h-ar-v2-clean-baseline-spec.md`：V2 干净参数、逐笔等价证据及微调否决结论。
- `1h-adaptive-regime/ablations/hype-1h-ar-v1-full-parameter-ablation-2026-07-02.md`：两条腿 `76/76` 字段槽全量消融。
- `1h-adaptive-regime/diagnostics/hype-1h-adaptive-regime-boundary-audit-2026-07-01.md`：K+2、成本、`164` 行 active-field 消融和 live-executable 严格审计；结论 `NO-GO`。
- `15m-ema-crossover/hype-ema-x-core-ledger.md`: `HYPE-EMA-Crossover` promoted-candidate and version-evolution ledger.
- `15m-multi-indicator-intraday/hype-15m-mii-core-ledger.md`: `HYPE-15M-Multi-Indicator-Intraday` core ledger；当前 `HYPE-15M-MII-V1.2` 为 ATR 动态止盈止损 diagnostic observation only，不是 live-ready；同事/AI 复现规格见 `15m-multi-indicator-intraday/live-specs/hype-15m-mii-v1-2-reproduction-spec-not-live-ready-2026-06-30.md`；`V1.1` HTML 交易路径图在 `15m-multi-indicator-intraday/artifacts/hype_15m_mii_v1_1_trade_paths_2026-06-30.html`；trailing 动态止盈测试见 `15m-multi-indicator-intraday/research-notes/hype-15m-mii-v1-1-dynamic-take-profit-2026-06-30.md`，ATR bracket V1.2 报告见 `15m-multi-indicator-intraday/research-notes/hype-15m-mii-v1-2-atr-bracket-exit-2026-06-30.md`，V1.2 时间片复核见 `15m-multi-indicator-intraday/research-notes/hype-15m-mii-v1-2-window-slice-backtest-2026-06-30.md`。
- `15m-multi-indicator-intraday/README.md`: `HYPE-15M-Multi-Indicator-Intraday` exploratory broad-indicator `15m` intraday search entry.
- `15m-multi-indicator-intraday/canonical-specs/hype-15m-mii-v1-baseline-spec.md`：`HYPE-15M-Multi-Indicator-Intraday-V1` 固定基线；仅 diagnostic，不是实盘候选。
- `15m-multi-indicator-intraday/ablations/hype-15m-mii-v1-full-parameter-ablation-2026-06-29.md`：V1 标准数据湖可执行时序与全参数消融，完整 gate `0/62`。
- `15m-multi-indicator-intraday/live-specs/hype-15m-mii-v1-live-feasibility-2026-06-29.md`：V1 实盘可行性审计，结论 `NO-GO`。
- `15m-multi-indicator-intraday/research-notes/hype-15m-mii-clean-parameter-evolution-2026-06-29.md`：V1 干净参数演化；K+1 领先诊断版 `323.57%` 年化、`-18.67%` 回撤、`78.99%` 胜率。
- `15m-multi-indicator-intraday/research-notes/hype-15m-mii-delay-aware-selection-2026-06-29.md`：K+2 延迟联合筛选，联合通过 `0/201`。
- `15m-multi-indicator-intraday/research-notes/hype-15m-mii-relaxed-dd-high-return-selection-2026-06-30.md`：放宽回撤高收益选择；样本内 aggressive diagnostic，不是 promotion。
- `15m-multi-indicator-intraday/research-notes/hype-15m-mii-fast-validation-frequency-ranking-2026-06-30.md`：快速验证频率综合排名；严格 `1-3` 笔/天版本收益或近期稳定性偏弱。
- `15m-multi-indicator-intraday/research-notes/hype-15m-mii-balanced-leverage-stress-2026-06-30.md`：放弃频率后的均衡观察版本 `1.75x/2x/3x` 暴露阶梯；`2x` 均衡，`3x` 仅 aggressive diagnostic。
- `15m-multi-indicator-intraday/research-notes/hype-15m-mii-v1-1-dynamic-take-profit-2026-06-30.md`：`HYPE-15M-MII-V1.1` 动态止盈测试；单纯 trailing 未改善固定 TP baseline。
- `15m-multi-indicator-intraday/live-specs/hype-15m-mii-v1-2-reproduction-spec-not-live-ready-2026-06-30.md`：`HYPE-15M-MII-V1.2` 完整复现规格；给同事/AI 复刻策略使用，不是 live-ready 交接。
- `15m-multi-indicator-intraday/research-notes/hype-15m-mii-v1-2-atr-bracket-exit-2026-06-30.md`：`HYPE-15M-MII-V1.2` ATR 动态止盈止损测试；`atr96_tp1p25x_sl5x_hold24` 是唯一 K+1/K+2 联合改善配置，仍为 diagnostic。
- `15m-multi-indicator-intraday/research-notes/hype-15m-mii-v1-2-window-slice-backtest-2026-06-30.md`：`HYPE-15M-MII-V1.2` 最近窗口、滚动窗口和随机切片复核；全样本 Sharpe 高，但 30d 切片仍有负收益窗口。
- `15m-multi-indicator-intraday/ablations/hype-15m-mii-full-ablation-2026-06-26.md`: `HYPE-15M-Multi-Indicator-Intraday` best-search-candidate time-slice and full ablation diagnostic; still no-go.
- `15m-multi-indicator-intraday/ablations/hype-15m-mii-surface-combo-optimization-2026-06-26.md`: `HYPE-15M-Multi-Indicator-Intraday` surface-improvement combination optimization diagnostic; still no-go.
- `15m-riptide/README.md`: `HYPE-15M-Riptide` 研究入口；当前 `HYPE-15M-Riptide-V13` 为 diagnostic / reproduction-pending，不是 sim-paper/live-ready。
- `15m-riptide/diagnostics/hype-15m-riptide-v13-cache-audit-2026-06-30.md`: `HYPE-15M-Riptide-V13` 缓存口径复现审计；WF 形状接近外部规格，但固定切点第一验收未完全逐笔/汇总对齐。
- `1m-ema-crossover/diagnostics/hype-1m-ema-crossover-live-search-2026-06-25.md`: `HYPE-1M-EMA-Crossover` first diagnostic / paper-live search report.
- `1m-ma-pullback-scalp/diagnostics/hype-1m-ma-pullback-scalp-search-2026-06-26.md`: `HYPE-1M-MA-Pullback-Scalp` first executable two-MA pullback scalp search; no-go for paper-live/live.
- `15m-ema-trend-breakout/hype-ema-tb-core-ledger.md`: `HYPE-EMA-Trend-Breakout` trend strategy research ledger.
- `15m-candle-count-reversal/hype-cc-15m-milestone-comparison.md`: `HYPE-Candle-Count-Reversal` 15m milestone comparison ledger.
- `5m-pullback-trail/hype-5m-pullback-trail-core-ledger.md`: `HYPE-5M-Pullback-Trail` active `5m` pullback-trail ledger.
- `15m-pullback-trail/diagnostics/hype-15m-pullback-trail-bracket-search-2026-06-30.md`: `HYPE-15M-Pullback-Trail` 15m 回踩事件源 + 入场即 bracket / emergency stop / timeout 搜索；找到 paper-audit candidate，但不是 live-ready。
- `15m-pullback-trail/diagnostics/hype-15m-pullback-trail-v3-3-migration-2026-06-30.md`: `HYPE-15M-Pullback-Trail` V3.3 migration diagnostic; no-go under live-realistic trailing.
- `5m-ma-pullback-scalp/diagnostics/hype-5m-ma-pullback-scalp-search-2026-06-26.md`: `HYPE-5M-MA-Pullback-Scalp` first executable two-MA pullback scalp search.
- `5m-ma-pullback-scalp/diagnostics/hype-5m-ma-pullback-scalp-robustness-2026-06-26.md`: `HYPE-5M-MA-Pullback-Scalp` neighborhood robustness; current candidates are paper-audit only.
- `5m-micro-scalp/diagnostics/hype-5m-micro-scalp-search-2026-06-26.md`: `HYPE-5M-Micro-Scalp` first executable broad search; no-go for the original `3-5` trades/day strict shape.
- `5m-micro-scalp/diagnostics/hype-5m-micro-scalp-relaxed-rounds-2026-06-26.md`: relaxed-constraint search that found low-frequency profitable candidates.
- `5m-micro-scalp/diagnostics/hype-5m-micro-scalp-candidate-robustness-2026-06-26.md`: parameter-neighborhood robustness check; current relaxed candidates are paper-audit only, not live-ready.
- `5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-simplified-combo-search-2026-06-30.md`: V1 effective-parameter simplification and combo search; strict-improve rows exist on current data, but not live-ready.
- `5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-simplified-candidate-robustness-2026-06-30.md`: local robustness sweep for simplified combo leads; preferred paper-audit observation `V1S_rand_016782__N00596` was recorded as `HYPE-5M-Micro-Scalp-V1.1`.
- `5m-micro-scalp/canonical-specs/hype-5m-micro-scalp-v1-1-baseline-spec.md`: `HYPE-5M-Micro-Scalp-V1.1` baseline spec; paper-audit observation only, not live-ready.
- `5m-micro-scalp/ablations/hype-5m-micro-scalp-v1-1-full-parameter-ablation-2026-06-30.md`: V1.1 full one-at-a-time parameter ablation; identifies dormant fields under `vwap_revert`.
- `5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-1-micro-tune-2026-06-30.md`: V1.1 effective-parameter micro-tune；优先观察行 `V1.1_tune_grid_004895` 后续登记为 V1.2。
- `5m-micro-scalp/canonical-specs/hype-5m-micro-scalp-v1-2-baseline-spec.md`：`HYPE-5M-Micro-Scalp-V1.2` canonical 规格；默认 `1x`，仍不是 live-ready。
- `5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-2-registration-and-leverage-retest-2026-07-01.md`：V1.2 登记与指定成本杠杆复测；`2x/3x` 仅作压力测试。
- `5m-event-quality-scoring/diagnostics/hype-5m-event-quality-v0-2026-06-27.md`: generic event-quality scoring diagnostic; no paper-audit candidate.
- `5m-event-quality-scoring/diagnostics/hype-5m-seeded-event-quality-v0-2026-06-27.md`: seeded source-mean event ranker; `seeded_source_mean_q80` is paper-audit only, not live-ready.
- `5m-event-quality-scoring/hype-5m-event-quality-scoring-core-ledger.md`: `HYPE-5M-Event-Quality-Scoring` core ledger; Base is Seeded V0, fixed seed-universe V1 failed strict seed audit.
- `5m-event-quality-scoring/diagnostics/hype-5m-seeded-event-quality-v01-full-ablation-2026-06-27.md`: Seeded V0.1 full parameter ablation; fixed seed-universe lead was `no_wick_no_breakout__cfg_side_88_12__q80`.
- `5m-event-quality-scoring/diagnostics/hype-5m-seeded-v1-live-feasibility-2026-06-27.md`: `HYPE-5M-Event-Quality-Scoring-Seeded-V1` live-feasibility audit; superseded by strict seed audit failure, not live-ready.
- `5m-event-quality-scoring/diagnostics/hype-5m-seeded-v1-strict-seed-audit-2026-06-27.md`: strict rolling seed-generation audit; V1 failed anti-leakage validation and is downgraded to fixed seed-universe diagnostic only.

## Hard Rules

- Never answer from `Vxx` alone.
- Always name the full family name, for example `HYPE-Candle-Count-Reversal-V21` or `HYPE-EMA-Trend-Breakout-V36`.
- Treat `HYPE-EMA-Crossover` and `HYPE-EMA-Trend-Breakout` as separate core directions, not one EMA bucket.
- Treat `HYPE-15M-Multi-Indicator-Intraday` as a broad indicator-search family, not a version of `HYPE-EMA-Crossover`, `HYPE-EMA-Trend-Breakout`, or `HYPE-Candle-Count-Reversal`.
- Treat `HYPE-15M-Riptide` as a separate `15m` trend-background RSI pullback family, not a version of `HYPE-15M-MII`, `HYPE-15M-Pullback-Trail`, or any bare `V13`.
- Treat `HYPE-1M-EMA-Crossover` as a separate `1m` family, not as a subdocument or version of `HYPE-EMA-Crossover`.
- Treat `HYPE-1M-MA-Pullback-Scalp` as a separate `1m` family, not as a version of `HYPE-1M-EMA-Crossover`.
- Treat `HYPE-5M-Pullback-Trail` as a separate `5m` family, not as a subdocument of `HYPE-EMA-Trend-Breakout`.
- Treat `HYPE-15M-Pullback-Trail` as a separate `15m` migration diagnostic family, not as a version of `HYPE-5M-Pullback-Trail` or `HYPE-15M-Multi-Indicator-Intraday`.
- Treat `HYPE-5M-MA-Pullback-Scalp` as a separate `5m` family, not as a version of `HYPE-5M-Micro-Scalp` or `HYPE-5M-Pullback-Trail`.
- Treat `HYPE-5M-Micro-Scalp` as a separate `5m` family, not as a version of `HYPE-5M-Pullback-Trail` or `HYPE-15M-Multi-Indicator-Intraday`.
- Treat `HYPE-5M-Event-Quality-Scoring` as a separate `5m` family, not as a version of `HYPE-5M-Micro-Scalp` or `HYPE-5M-Pullback-Trail`.
- Durable HYPE research reports and ledgers must be repository-tracked Markdown under `research/`.
- Cursor Canvas files are legacy/private research assets, not canonical storage for new reports. If Canvas is used for temporary visualization, mirror the durable conclusion into the relevant Markdown file before finishing.
- Archived code under `archive/code/platform/` is limited to historical strategy source snapshots cited by research docs; it is not strategy truth or runnable platform code.
- Active code under `src/strategy_lab/` is data/research infrastructure, not strategy truth.

## Transfer Notes

- Legacy cross-asset checks that applied HYPE kernels to BTC, XMR, XAU, TradFi perpetuals, or broad CMC universes have been archived under `../../archive/research/hype-transfer/`.
- New promoted transfer research should get an explicit direction or asset family, as `MU-HYPE-Transfer` does under `../mu/`（historical alias: `MU-HYPE-XFER`）.

## Archived Cursor Assets

Legacy Cursor Canvas files are stored outside the repository in Cursor-managed project-private storage. The former repo-managed Canvas and agent artifact indexes have been archived under `../../archive/docs/hype-cursor-artifacts/`. Treat them as migration evidence, not active research entrypoints.
