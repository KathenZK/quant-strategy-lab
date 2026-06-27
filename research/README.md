# Research

`research/` 是本仓库的主要知识入口。它不只放 Markdown，也管理当前研究需要保留的一次性脚本和小型产物。

## 入口

- `hype/README.md`：HYPE 策略家族档案与阅读上下文。
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
| `HYPE-15M-Multi-Indicator-Intraday` | `HYPE-15M-MII` | `hype/15m-multi-indicator-intraday/` | Binance HYPEUSDT `15m` broad RSI/MACD/EMA/ADX/ATR/structure intraday search with live-realistic next-bar execution | Exploratory research |
| `HYPE-5M-Pullback-Trail` | `HYPE-5M-PBTR` | `hype/5m-pullback-trail/` | Binance HYPE `5m` pullback/resume entries with ATR trailing-stop exits | Active research candidate |
| `HYPE-5M-MA-Pullback-Scalp` | - | `hype/5m-ma-pullback-scalp/` | Binance HYPEUSDT `5m` two-MA pullback/end-of-correction scalp with HH/HL or LL/LH structure and fixed brackets | Paper-audit candidates only |
| `HYPE-5M-Micro-Scalp` | `HYPE-5M-MS` | `hype/5m-micro-scalp/` | Binance HYPEUSDT `5m` high-frequency micro-profit scalp search with immediate executable TP/SL brackets | Exploratory; relaxed-search paper-audit candidates only |
| `HYPE-5M-Event-Quality-Scoring` | `HYPE-5M-EQS` | `hype/5m-event-quality-scoring/` | Binance HYPEUSDT `5m` event-quality scoring over candidate events and seeded micro-scalp signals | Seeded V0 paper-audit candidate only |

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
- `HYPE-15M-Multi-Indicator-Intraday`（`HYPE-15M-MII`）: `hype/15m-multi-indicator-intraday/README.md`
  - Independent Binance HYPEUSDT `15m` broad multi-indicator intraday research line.
  - It is not a version of `HYPE-EMA-Crossover`, `HYPE-EMA-Trend-Breakout`, or `HYPE-Candle-Count-Reversal`.
  - Full ablation and time-slice diagnostic: `hype/15m-multi-indicator-intraday/ablations/hype-15m-mii-full-ablation-2026-06-26.md`.
  - Surface-improvement combo optimization: `hype/15m-multi-indicator-intraday/ablations/hype-15m-mii-surface-combo-optimization-2026-06-26.md`.
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
  - Current status: original `3-5` trades/day strict shape remains no-go; relaxed low-frequency VWAP/BB mean-reversion candidates may advance to paper audit only.
- `HYPE-5M-Event-Quality-Scoring`（`HYPE-5M-EQS`）: `hype/5m-event-quality-scoring/README.md`
  - Generic event-quality V0: `hype/5m-event-quality-scoring/diagnostics/hype-5m-event-quality-v0-2026-06-27.md`.
  - Seeded V0: `hype/5m-event-quality-scoring/diagnostics/hype-5m-seeded-event-quality-v0-2026-06-27.md`.
  - Current status: `seeded_source_mean_q80` is a paper-audit candidate only; not live-ready.
- `HYPE-Candle-Count-Reversal`（`HYPE-CC`）: `hype/15m-candle-count-reversal/hype-cc-15m-milestone-comparison.md`
- Repo rule mirrors:
  - `hype/15m-ema-crossover/v15-v16-promoted-strategy-specs.md`
  - `hype/15m-ema-crossover/v17-hybrid-ablation.md`

## 跨资产与迁移研究

跨资产研究不是 HYPE 策略家族，除非文档明确把它提升为某个 HYPE family variant。

- `MU-HYPE-Transfer`（`MU-HYPE-XFER`）: `mu/README.md` and `mu/mu-hype-xfer-session-aware-ledger.md`
- Old HYPE cross-asset transfer checks: archived under `../archive/research/hype-transfer/`.

## 核心研究方向

当前核心研究方向是：

1. `HYPE-Candle-Count-Reversal`（`HYPE-CC`）：HYPE candle-count technical reversal.
2. `HYPE-EMA-Crossover`（`HYPE-EMA-X`）：HYPE EMA golden/death cross family, iterated through V14-era research.
3. `HYPE-1M-EMA-Crossover`（`HYPE-1M-EMA-X`）：HYPE Binance `1m` EMA cross paper-live research.
4. `HYPE-1M-MA-Pullback-Scalp`：HYPE Binance `1m` two-MA pullback scalp no-go research.
5. `HYPE-EMA-Trend-Breakout`（`HYPE-EMA-TB`）：HYPE EMA trend breakout / chase-long-chase-short family.
6. `HYPE-15M-Multi-Indicator-Intraday`（`HYPE-15M-MII`）：Binance HYPEUSDT `15m` broad multi-indicator intraday search.
7. `HYPE-5M-Pullback-Trail`（`HYPE-5M-PBTR`）：HYPE Binance `5m` pullback + ATR trailing-stop family.
8. `HYPE-5M-MA-Pullback-Scalp`：HYPE Binance `5m` two-MA pullback scalp paper-audit family.
9. `HYPE-5M-Micro-Scalp`（`HYPE-5M-MS`）：Binance HYPEUSDT `5m` high-frequency micro-profit scalp family.
10. `HYPE-5M-Event-Quality-Scoring`（`HYPE-5M-EQS`）：HYPE Binance `5m` event-quality scoring and seeded candidate ranking.
11. `MU-HYPE-Transfer`（`MU-HYPE-XFER`）：MU transfer research from HYPE trend kernels.

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

新生成的研究报告默认使用中文，除非用户明确要求其他语言。

Cursor Canvas 和 Cursor 私有项目目录不是 canonical storage。Canvas 只能在用户明确要求时作为临时可视化界面；任何可持久化结论都必须同步写回对应 Markdown。

顶层 `reports/` 是 git 忽略的临时运行缓存或旧脚本兼容目录，不再作为 active research 的引用入口。
