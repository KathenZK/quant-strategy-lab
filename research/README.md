# Research

`research/` 是本仓库的主要知识入口。它不只放 Markdown，也管理当前研究需要保留的一次性脚本和小型产物。

## 入口

- `hype/README.md`：HYPE 策略家族档案与阅读上下文。
- `btc/README.md`：Bitcoin 单资产策略家族入口。
- `binance/README.md`：Binance 跨资产研究入口。
- `mu/README.md`：`MU-HYPE-Transfer`（历史别名：`MU-HYPE-XFER`）迁移研究入口。

已经不作为 active research 入口的历史策略研究位于 `../archive/research/`，其中旧 HYPE cross-asset transfer 材料位于 `../archive/research/hype-transfer/`。

## 策略家族索引

本仓库使用明确的 strategy-family name，避免不同研究线复用 `V13`、`V21`、`V35` 等版本号造成串线。新研究优先使用展开后的完整名称，短 id 只作为历史别名。

阅读任何 HYPE 策略文档前，先读本文件和 `hype/README.md`。

| Full family name | Historical alias | Directory | Meaning | Current role |
| --- | --- | --- | --- | --- |
| `HYPE-Candle-Count-Reversal` | `HYPE-CC` | `hype/15m-candle-count-reversal/` | 10-of-8 candle color reversal with ATR risk controls and early exits | Archived/canonical research specs |
| `HYPE-EMA-Crossover` | `HYPE-EMA-X` | `hype/15m-ema-crossover/` | EMA golden/death cross family, evolved through V14-era regime, volume, oscillator, late-entry, and state-machine variants | Core historical research line |
| `HYPE-1M-EMA-Crossover` | `HYPE-1M-EMA-X` | `hype/1m-ema-crossover/` | Binance HYPEUSDT `1m` EMA golden/death cross research with live-executable next-bar entries and fixed/trailing exits | Diagnostic / paper-live candidate only |
| `HYPE-1M-MA-Pullback-Scalp` | - | `hype/1m-ma-pullback-scalp/` | Binance HYPEUSDT `1m` two-MA pullback/end-of-correction scalp with HH/HL or LL/LH structure and fixed brackets | No-go after first executable search |
| `HYPE-EMA-Trend-Breakout` | `HYPE-EMA-TB` | `hype/15m-ema-trend-breakout/` | Later 15m EMA96/384 trend breakout / chase-long-chase-short family with ADX, volume, 1h confirmation, and cross-exchange execution variants | Archived/canonical research specs |
| `HYPE-1H-Adaptive-Regime` | `HYPE-1H-AR` | `hype/1h-adaptive-regime/` | Binance HYPEUSDT `1h` DI trend + stochastic reversal adaptive ensemble with broad indicator/parameter search | V1 frozen boundary; V2 clean-equivalent baseline; both NO-GO |
| `HYPE-15M-Multi-Indicator-Intraday` | `HYPE-15M-MII` | `hype/15m-multi-indicator-intraday/` | Binance HYPEUSDT `15m` broad RSI/MACD/EMA/ADX/ATR/structure intraday search with live-realistic next-bar execution | V1 diagnostic baseline / not live-ready |
| `HYPE-15M-Riptide` | - | `hype/15m-riptide/` | Binance HYPEUSDT `15m` EMA20/60 trend-background RSI pullback with 1h RV regime gate and ATR bracket exits | Diagnostic / reproduction-pending |
| `HYPE-15M-Pullback-Trail` | - | `hype/15m-pullback-trail/` | Binance HYPEUSDT `15m` pullback event source research; V3.3 delayed trailing migration plus executable fixed bracket / emergency stop / timeout search | V3.3 migration no-go; bracket paper-audit candidate only |
| `HYPE-5M-Pullback-Trail` | `HYPE-5M-PBTR` | `hype/5m-pullback-trail/` | Binance HYPE `5m` pullback/resume entries with ATR trailing-stop exits | Active research candidate |
| `HYPE-5M-MA-Pullback-Scalp` | - | `hype/5m-ma-pullback-scalp/` | Binance HYPEUSDT `5m` two-MA pullback/end-of-correction scalp with HH/HL or LL/LH structure and fixed brackets | Paper-audit candidates only |
| `HYPE-5M-Micro-Scalp` | `HYPE-5M-MS` | `hype/5m-micro-scalp/` | Binance HYPEUSDT `5m` high-frequency micro-profit scalp search with immediate executable TP/SL brackets | Exploratory; relaxed-search paper-audit candidates only |
| `HYPE-5M-Event-Quality-Scoring` | `HYPE-5M-EQS` | `hype/5m-event-quality-scoring/` | Binance HYPEUSDT `5m` event-quality scoring over candidate events and seeded micro-scalp signals | Fixed seed-universe diagnostics only; V1 failed strict seed audit |

## 核心台账入口

- `HYPE-EMA-Crossover`（`HYPE-EMA-X`）: `hype/15m-ema-crossover/hype-ema-x-core-ledger.md`
  - `HYPE-EMA-Crossover-V15`（alias `HYPE-EMA-X-V15`）: high-win-rate / low-drawdown promoted research candidate.
  - `HYPE-EMA-Crossover-V16`（alias `HYPE-EMA-X-V16`）: high-return promoted research candidate.
  - `HYPE-EMA-Crossover-V17`（alias `HYPE-EMA-X-V17`）: V15/V16 hybrid promoted research candidate, balancing V16-like return with V15 drawdown.
  - `HYPE-EMA-Crossover-V17.1`（alias `HYPE-EMA-X-V17.1`）: V17 sizing-enhanced promoted research candidate, using `hq_scale=1.1`.
- `HYPE-1M-EMA-Crossover`（`HYPE-1M-EMA-X`）: `hype/1m-ema-crossover/README.md`
  - `HYPE-1M-EMA-Crossover-TRAIL-144-1597`: first diagnostic / paper-live candidate; not live-approved.
- `HYPE-1M-MA-Pullback-Scalp`: `hype/1m-ma-pullback-scalp/README.md`
  - First executable search: `hype/1m-ma-pullback-scalp/diagnostics/hype-1m-ma-pullback-scalp-search-2026-06-26.md`.
  - Current status: no paper-live or live candidate; no profitable config at `>=60` trades under the tested executable/cost model.
- `HYPE-EMA-Trend-Breakout`（`HYPE-EMA-TB`）: `hype/15m-ema-trend-breakout/hype-ema-tb-core-ledger.md`
- `HYPE-1H-Adaptive-Regime`（`HYPE-1H-AR`）: `hype/1h-adaptive-regime/hype-1h-ar-core-ledger.md`
  - `HYPE-1H-Adaptive-Regime-V1`: frozen `DI-cross + Stoch-reversal` diagnostic baseline; `NO-GO / not live-ready`.
  - `HYPE-1H-Adaptive-Regime-V2`: clean-equivalent baseline after full-field ablation; behavior equals V1; `NO-GO / not live-ready`.
- `HYPE-15M-Multi-Indicator-Intraday`（`HYPE-15M-MII`）: `hype/15m-multi-indicator-intraday/hype-15m-mii-core-ledger.md`
  - Independent Binance HYPEUSDT `15m` broad multi-indicator intraday research line.
  - It is not a version of `HYPE-EMA-Crossover`, `HYPE-EMA-Trend-Breakout`, or `HYPE-Candle-Count-Reversal`.
  - `HYPE-15M-Multi-Indicator-Intraday-V1` 基线规格：`hype/15m-multi-indicator-intraday/canonical-specs/hype-15m-mii-v1-baseline-spec.md`；状态为 diagnostic only，不可实盘。
  - `HYPE-15M-MII-V1.1` 固定 TP/SL 干净观察基线：`clean_rsi7_40_60_atrmin75_rvol1_h10_rsi14b0_tp120_sl360_hold16_x2`；分窗口回测见 `hype/15m-multi-indicator-intraday/research-notes/hype-15m-mii-v1-1-window-backtest-2026-06-30.md`，交易路径图见 `hype/15m-multi-indicator-intraday/research-notes/hype-15m-mii-v1-1-trade-paths-2026-06-30.md`，trailing 动态止盈测试见 `hype/15m-multi-indicator-intraday/research-notes/hype-15m-mii-v1-1-dynamic-take-profit-2026-06-30.md`。`HYPE-15M-MII-V1.2` 为 ATR96 动态止盈止损观察版，同事/AI 复现规格见 `hype/15m-multi-indicator-intraday/live-specs/hype-15m-mii-v1-2-reproduction-spec-not-live-ready-2026-06-30.md`，ATR bracket 报告见 `hype/15m-multi-indicator-intraday/research-notes/hype-15m-mii-v1-2-atr-bracket-exit-2026-06-30.md`，窗口/滚动/随机切片复核见 `hype/15m-multi-indicator-intraday/research-notes/hype-15m-mii-v1-2-window-slice-backtest-2026-06-30.md`；状态为 diagnostic observation only，不可实盘。
  - V1 全参数消融：`hype/15m-multi-indicator-intraday/ablations/hype-15m-mii-v1-full-parameter-ablation-2026-06-29.md`；`0/62` 通过完整 gate。
  - V1 实盘可行性审计：`hype/15m-multi-indicator-intraday/live-specs/hype-15m-mii-v1-live-feasibility-2026-06-29.md`；结论 `NO-GO`。
  - V1 干净参数演化：`hype/15m-multi-indicator-intraday/research-notes/hype-15m-mii-clean-parameter-evolution-2026-06-29.md`；K+1 领先诊断版为 `323.57%` 年化、`-18.67%` 回撤、`78.99%` 胜率，但不是 promotion。
  - K+2 延迟联合筛选：`hype/15m-multi-indicator-intraday/research-notes/hype-15m-mii-delay-aware-selection-2026-06-29.md`；联合通过 `0/201`。
  - 放宽回撤高收益选择：`hype/15m-multi-indicator-intraday/research-notes/hype-15m-mii-relaxed-dd-high-return-selection-2026-06-30.md`；样本内有 aggressive diagnostic 版本，但 K+2 稳健性不足。
  - 快速验证频率综合排名：`hype/15m-multi-indicator-intraday/research-notes/hype-15m-mii-fast-validation-frequency-ranking-2026-06-30.md`；严格 `1-3` 笔/天版本收益或近期稳定性偏弱。
  - 均衡策略杠杆压力测试：`hype/15m-multi-indicator-intraday/research-notes/hype-15m-mii-balanced-leverage-stress-2026-06-30.md`；`2x` 是均衡观察版本，`3x` 只作为 aggressive diagnostic。
  - Full ablation and time-slice diagnostic: `hype/15m-multi-indicator-intraday/ablations/hype-15m-mii-full-ablation-2026-06-26.md`.
  - Surface-improvement combo optimization: `hype/15m-multi-indicator-intraday/ablations/hype-15m-mii-surface-combo-optimization-2026-06-26.md`.
- `HYPE-15M-Pullback-Trail`: `hype/15m-pullback-trail/README.md`
  - V3.3 migration diagnostic: `hype/15m-pullback-trail/diagnostics/hype-15m-pullback-trail-v3-3-migration-2026-06-30.md`.
  - Bracket executable search: `hype/15m-pullback-trail/diagnostics/hype-15m-pullback-trail-bracket-search-2026-06-30.md`.
  - Current status: V3.3 direct 15m migration remains no-go; bracket search has one paper-audit candidate, not live-ready.
- `HYPE-15M-Riptide`: `hype/15m-riptide/README.md`
  - `HYPE-15M-Riptide-V13` cache replay audit: `hype/15m-riptide/diagnostics/hype-15m-riptide-v13-cache-audit-2026-06-30.md`.
  - Current status: diagnostic / reproduction-pending; fixed `cut_hi=104.7` replay did not fully match the external spec acceptance numbers, so no sim-paper/live promotion.
- `HYPE-5M-Pullback-Trail`（`HYPE-5M-PBTR`）: `hype/5m-pullback-trail/hype-5m-pullback-trail-core-ledger.md`
  - Independent Binance HYPE `5m` pullback + ATR trailing-stop research line.
  - Its local `V1/V2` numbers are not the legacy 15m `HYPE-EMA-Trend-Breakout` V1/V2/V35 sequence.
  - V2 implementation handoff spec: `hype/5m-pullback-trail/live-specs/hype-5m-pullback-trail-v2-live-spec.md`.
  - V6 paper candidate and full ablation: `hype/5m-pullback-trail/ablations/hype-5m-pbtr-v6-full-parameter-ablation-2026-06-25.md`.
- `HYPE-5M-MA-Pullback-Scalp`: `hype/5m-ma-pullback-scalp/README.md`
  - First executable search: `hype/5m-ma-pullback-scalp/diagnostics/hype-5m-ma-pullback-scalp-search-2026-06-26.md`.
  - Neighborhood robustness: `hype/5m-ma-pullback-scalp/diagnostics/hype-5m-ma-pullback-scalp-robustness-2026-06-26.md`.
  - Current status: paper-audit candidates only; no live-ready strategy.
- `HYPE-5M-Micro-Scalp`（`HYPE-5M-MS`）: `hype/5m-micro-scalp/README.md`
  - Independent Binance HYPEUSDT `5m` high-frequency micro-profit scalp research line.
  - First executable broad search: `hype/5m-micro-scalp/diagnostics/hype-5m-micro-scalp-search-2026-06-26.md`.
  - Relaxed constraint search: `hype/5m-micro-scalp/diagnostics/hype-5m-micro-scalp-relaxed-rounds-2026-06-26.md`.
  - Candidate robustness check: `hype/5m-micro-scalp/diagnostics/hype-5m-micro-scalp-candidate-robustness-2026-06-26.md`.
  - `HYPE-5M-Micro-Scalp-V1` baseline spec: `hype/5m-micro-scalp/canonical-specs/hype-5m-micro-scalp-v1-baseline-spec.md`.
  - V1 full parameter ablation: `hype/5m-micro-scalp/ablations/hype-5m-micro-scalp-v1-full-parameter-ablation-2026-06-29.md`.
  - V1 simplified combo search: `hype/5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-simplified-combo-search-2026-06-30.md`.
  - V1 simplified candidate robustness: `hype/5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-simplified-candidate-robustness-2026-06-30.md`; preferred paper-audit observation `V1S_rand_016782__N00596` was recorded as `HYPE-5M-Micro-Scalp-V1.1`, not live-ready.
  - `HYPE-5M-Micro-Scalp-V1.1` baseline spec: `hype/5m-micro-scalp/canonical-specs/hype-5m-micro-scalp-v1-1-baseline-spec.md`.
  - V1.1 full parameter ablation: `hype/5m-micro-scalp/ablations/hype-5m-micro-scalp-v1-1-full-parameter-ablation-2026-06-30.md`.
  - V1.1 micro-tune: `hype/5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-1-micro-tune-2026-06-30.md`; preferred row `V1.1_tune_grid_004895` was later recorded as V1.2.
  - `HYPE-5M-Micro-Scalp-V1.2` baseline spec: `hype/5m-micro-scalp/canonical-specs/hype-5m-micro-scalp-v1-2-baseline-spec.md`；默认 `1x`，paper-audit observation / not live-ready。
  - V1.2 registration and leverage retest: `hype/5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-2-registration-and-leverage-retest-2026-07-01.md`; fee `0.001`/fill、slippage `4 bps`/fill，`2x/3x` 仅为压力测试。
  - Current status: original `3-5` trades/day strict shape remains no-go; relaxed low-frequency VWAP/BB mean-reversion candidates may advance to paper audit only.
- `HYPE-5M-Event-Quality-Scoring`（`HYPE-5M-EQS`）: `hype/5m-event-quality-scoring/README.md`
  - Core ledger: `hype/5m-event-quality-scoring/hype-5m-event-quality-scoring-core-ledger.md`.
  - Generic event-quality V0: `hype/5m-event-quality-scoring/diagnostics/hype-5m-event-quality-v0-2026-06-27.md`.
  - Seeded V0: `hype/5m-event-quality-scoring/diagnostics/hype-5m-seeded-event-quality-v0-2026-06-27.md`.
  - Seeded V0.1 style-prune: `hype/5m-event-quality-scoring/diagnostics/hype-5m-seeded-event-quality-v01-style-prune-2026-06-27.md`.
  - Seeded V0.1 full ablation: `hype/5m-event-quality-scoring/diagnostics/hype-5m-seeded-event-quality-v01-full-ablation-2026-06-27.md`.
  - Seeded V1 live-feasibility audit: `hype/5m-event-quality-scoring/diagnostics/hype-5m-seeded-v1-live-feasibility-2026-06-27.md`.
  - Seeded V1 strict seed audit: `hype/5m-event-quality-scoring/diagnostics/hype-5m-seeded-v1-strict-seed-audit-2026-06-27.md`.
  - Current status: V1 failed strict anti-leakage seed generation; this family has no paper-live/live-ready candidate.
- `HYPE-Candle-Count-Reversal`（`HYPE-CC`）: `hype/15m-candle-count-reversal/hype-cc-15m-milestone-comparison.md`
- Repo rule mirrors:
  - `hype/15m-ema-crossover/research-notes/hype-ema-x-v15-v16-promoted-strategy-specs.md`
  - `hype/15m-ema-crossover/ablations/hype-ema-x-v17-hybrid-ablation.md`
  - `hype/15m-ema-crossover/canonical-specs/hype-ema-x-v18-baseline-spec.md`

## 跨资产与迁移研究

跨资产研究不是 HYPE 策略家族，除非文档明确把它提升为某个 HYPE family variant。

- `Binance-1D-Turtle-Breakout`: `binance/1d-turtle-breakout/README.md`，覆盖 Binance USD-M Futures `BTCUSDT`、`ETHUSDT`、`HYPEUSDT` 日线 20/10 turtle breakout 诊断。
- `Binance-15M-Multi-Indicator-Intraday-Transfer`: `binance/15m-multi-indicator-intraday/README.md`，基于 `HYPE-15M-MII-V1.1` 机制对 BTC/ETH `15m` 做受约束参数迁移诊断；BTC 有低收益 K+1/K+2 同正版本，ETH 未通过 K+2。
- `MU-HYPE-Transfer`（`MU-HYPE-XFER`）: `mu/README.md` and `mu/mu-hype-xfer-session-aware-ledger.md`
- Old HYPE cross-asset transfer checks: archived under `../archive/research/hype-transfer/`.

## Bitcoin 单资产研究

- `BTC-1H-Adaptive-Regime`（`BTC-1H-AR`）：`btc/1h-adaptive-regime/README.md`。Binance USD-M Futures `BTCUSDT` perpetual `1h` 两年多指标广搜；`BTC-1H-Adaptive-Regime-V1` 已登记为 diagnostic baseline，结论仍为 `NO-GO / not live-ready`。

## 核心研究方向

当前核心研究方向是：

1. `HYPE-Candle-Count-Reversal`（`HYPE-CC`）：HYPE candle-count technical reversal.
2. `HYPE-EMA-Crossover`（`HYPE-EMA-X`）：HYPE EMA golden/death cross family, iterated through V14-era research.
3. `HYPE-1M-EMA-Crossover`（`HYPE-1M-EMA-X`）：HYPE Binance `1m` EMA cross paper-live research.
4. `HYPE-1M-MA-Pullback-Scalp`：HYPE Binance `1m` two-MA pullback scalp no-go research.
5. `HYPE-EMA-Trend-Breakout`（`HYPE-EMA-TB`）：HYPE EMA trend breakout / chase-long-chase-short family.
6. `HYPE-1H-Adaptive-Regime`（`HYPE-1H-AR`）：Binance HYPEUSDT `1h` adaptive regime broad-search no-go research.
7. `HYPE-15M-Multi-Indicator-Intraday`（`HYPE-15M-MII`）：Binance HYPEUSDT `15m` broad multi-indicator intraday search.
8. `HYPE-15M-Riptide`：HYPE Binance `15m` EMA trend-background RSI pullback with RV regime and ATR bracket exits.
9. `HYPE-15M-Pullback-Trail`：HYPE Binance `15m` pullback event source research; V3.3 delayed trailing migration no-go, bracket search is paper-audit only.
10. `HYPE-5M-Pullback-Trail`（`HYPE-5M-PBTR`）：HYPE Binance `5m` pullback + ATR trailing-stop family.
11. `HYPE-5M-MA-Pullback-Scalp`：HYPE Binance `5m` two-MA pullback scalp paper-audit family.
12. `HYPE-5M-Micro-Scalp`（`HYPE-5M-MS`）：Binance HYPEUSDT `5m` high-frequency micro-profit scalp family.
13. `HYPE-5M-Event-Quality-Scoring`（`HYPE-5M-EQS`）：HYPE Binance `5m` event-quality scoring and seeded candidate ranking.
14. `MU-HYPE-Transfer`（`MU-HYPE-XFER`）：MU transfer research from HYPE trend kernels.

## 历史或浅层研究

这些方向曾经探索过，但不应作为当前核心研究线：

- `crowding_reversal`: archived under `../archive/research/legacy-strategies/`.
- early platform examples such as spot CTA, CTA grid, generic MA crossover, momentum rotation, Donchian variants.

## 命名规则

- Never cite a bare `V35` without a family name.
- Prefer full names like `HYPE-Candle-Count-Reversal-V35`, `HYPE-EMA-Crossover-V14`, and `HYPE-EMA-Trend-Breakout-V35`.
- If a document path contains `15m-candle-count-reversal`, use `HYPE-Candle-Count-Reversal` and optionally note alias `HYPE-CC`.
- If a document path contains `15m-ema-crossover`, use `HYPE-EMA-Crossover` and optionally note alias `HYPE-EMA-X`.
- If a document path contains `1m-ema-crossover`, use `HYPE-1M-EMA-Crossover` and optionally note alias `HYPE-1M-EMA-X`.
- If a document path contains `1m-ma-pullback-scalp`, use `HYPE-1M-MA-Pullback-Scalp`.
- If a document path contains `15m-ema-trend-breakout`, use `HYPE-EMA-Trend-Breakout` and optionally note alias `HYPE-EMA-TB`.
- If a document path contains `15m-multi-indicator-intraday`, use `HYPE-15M-Multi-Indicator-Intraday` and optionally note alias `HYPE-15M-MII`.
- If a document path contains `15m-riptide`, use `HYPE-15M-Riptide`.
- If a document path contains `15m-pullback-trail`, use `HYPE-15M-Pullback-Trail`.
- If a document path contains `5m-pullback-trail`, use `HYPE-5M-Pullback-Trail` and optionally note alias `HYPE-5M-PBTR`.
- If a document path contains `5m-ma-pullback-scalp`, use `HYPE-5M-MA-Pullback-Scalp`.
- If a document path contains `5m-micro-scalp`, use `HYPE-5M-Micro-Scalp` and optionally note alias `HYPE-5M-MS`.
- If a document path contains `5m-event-quality-scoring`, use `HYPE-5M-Event-Quality-Scoring` and optionally note alias `HYPE-5M-EQS`.
- If a document lives under `archive/`, treat it as historical evidence, not the current entrypoint.

## 研究目录约定

新的策略研究默认由对应资产下的时间片策略目录自管理；非资产专属研究可放在独立 topic 目录：

- 启动前先查本文件和对应资产目录的 `README.md`，确认是否已有相同 family。
- 新时间片或新策略机制必须新建独立目录，格式为 `research/<asset>/<timeframe>-<strategy-family-slug>/`。
- 示例：`research/hype/1m-ema-crossover/`、`research/hype/15m-ema-crossover/`、`research/hype/5m-pullback-trail/`。
- 不要因为指标相似就把新时间片研究塞进旧 family；`1m` EMA crossover 与 `15m` EMA crossover 必须分开。
- `README.md`、主账和 `decision-log.md`：长期入口和决策记录。
- `diagnostics/`、`ablations/`、`live-specs/`、`research-notes/`：按研究性质分类的 Markdown。
- `scripts/`：只服务当前研究的一次性复现、搜索、审计、报告生成脚本。
- `artifacts/`：需要随报告保留的 JSON、CSV、HTML、交易路径图等产物。

`src/strategy_lab/` 只放可复用的数据基础设施、质量检查、特征构建或窄口径研究数据集导出工具。不要把某个策略家族专用的一次性脚本提升到 `src/`。

## 报告存储规则

研究报告、策略主账、实验结论和持久 decision record 必须以 Markdown 保存在 `research/` 内。

所有新增或更新的长期研究文档默认使用中文，除非用户明确要求其他语言。这个规则包括 `decision-log.md`、README、策略主账、diagnostics、ablations、live specs、research notes、实验结论和交接文档；策略名、版本号、参数、路径、指标名和状态术语可以保留英文原文。

Cursor Canvas 和 Cursor 私有项目目录不是 canonical storage。Canvas 只能在用户明确要求时作为临时可视化界面；任何可持久化结论都必须同步写回对应 Markdown。

顶层 `reports/` 已退役，不再作为临时缓存、旧脚本兼容目录或 durable evidence 入口；需要保留的产物必须进入对应 `artifacts/` 或明确归档路径。
