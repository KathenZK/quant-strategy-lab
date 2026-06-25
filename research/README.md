# Research

`research/` 是本仓库的主要知识入口。它不只放 Markdown，也管理当前研究需要保留的一次性脚本和小型产物。

## 入口

- `hype/AI_CONTEXT.md`：阅读 HYPE 材料前必须先看的上下文。
- `hype/`：HYPE 策略家族档案。
- `mu/README.md`：`MU-HYPE-XFER` 迁移研究入口。

已经不作为 active research 入口的历史策略研究位于 `../archive/research/`，其中旧 HYPE cross-asset transfer 材料位于 `../archive/research/hype-transfer/`。

## 策略家族索引

本仓库使用明确的 strategy-family id，避免不同研究线复用 `V13`、`V21`、`V35` 等版本号造成串线。

阅读任何 HYPE 策略文档前，先读本文件和 `hype/AI_CONTEXT.md`。

| Family id | Directory | Meaning | Current role |
| --- | --- | --- | --- |
| `HYPE-CC` | `hype/candle-count-reversal/` | 10-of-8 candle color reversal with ATR risk controls and early exits | Archived/canonical research specs |
| `HYPE-EMA-X` | `hype/ema-crossover/` | EMA golden/death cross family, evolved through V14-era regime, volume, oscillator, late-entry, and state-machine variants | Core historical research line |
| `HYPE-EMA-TB` | `hype/ema-trend-breakout/` | Later 15m EMA96/384 trend breakout / chase-long-chase-short family with ADX, volume, 1h confirmation, and cross-exchange execution variants | Archived/canonical research specs |
| `HYPE-5M-PBTR` | `hype/5m-pullback-trail/` | Binance HYPE `5m` pullback/resume entries with ATR trailing-stop exits | Active research candidate |

## 核心台账入口

- `HYPE-EMA-X`: `hype/ema-crossover/hype-ema-x-core-ledger.md`
  - `HYPE-EMA-X-V15`: high-win-rate / low-drawdown promoted research candidate.
  - `HYPE-EMA-X-V16`: high-return promoted research candidate.
  - `HYPE-EMA-X-V17`: V15/V16 hybrid promoted research candidate, balancing V16-like return with V15 drawdown.
  - `HYPE-EMA-X-V17.1`: V17 sizing-enhanced promoted research candidate, using `hq_scale=1.1`.
- `HYPE-EMA-TB`: `hype/ema-trend-breakout/hype-ema-tb-core-ledger.md`
- `HYPE-5M-PBTR`: `hype/5m-pullback-trail/hype-5m-pullback-trail-core-ledger.md`
  - Independent Binance HYPE `5m` pullback + ATR trailing-stop research line.
  - Its local `V1/V2` numbers are not the legacy 15m `HYPE-EMA-TB` V1/V2/V35 sequence.
  - V2 implementation handoff spec: `hype/5m-pullback-trail/live-specs/hype-5m-pullback-trail-v2-live-spec.md`.
  - V6 paper candidate and full ablation: `hype/5m-pullback-trail/ablations/hype-5m-pbtr-v6-full-parameter-ablation-2026-06-25.md`.
- `HYPE-CC`: `hype/candle-count-reversal/hype-cc-15m-milestone-comparison.md`
- Repo rule mirrors:
  - `hype/ema-crossover/v15-v16-promoted-strategy-specs.md`
  - `hype/ema-crossover/v17-hybrid-ablation.md`

## 跨资产与迁移研究

跨资产研究不是 HYPE 策略家族，除非文档明确把它提升为某个 HYPE family variant。

- `MU-HYPE-XFER`: `mu/README.md` and `mu/mu-hype-xfer-session-aware-ledger.md`
- Old HYPE cross-asset transfer checks: archived under `../archive/research/hype-transfer/`.

## 核心研究方向

当前核心研究方向是：

1. `HYPE-CC`: HYPE candle-count technical reversal.
2. `HYPE-EMA-X`: HYPE EMA golden/death cross family, iterated through V14-era research.
3. `HYPE-EMA-TB`: HYPE EMA trend breakout / chase-long-chase-short family.
4. `HYPE-5M-PBTR`: HYPE Binance `5m` pullback + ATR trailing-stop family.
5. `MU-HYPE-XFER`: MU transfer research from HYPE trend kernels.

## 历史或浅层研究

这些方向曾经探索过，但不应作为当前核心研究线：

- `crowding_reversal`: archived under `../archive/research/legacy-strategies/`.
- early platform examples such as spot CTA, CTA grid, generic MA crossover, momentum rotation, Donchian variants.

## 命名规则

- Never cite a bare `V35` without a family id.
- Prefer ids like `HYPE-CC-V35`, `HYPE-EMA-X-V14`, and `HYPE-EMA-TB-V35`.
- If a document path contains `candle-count-reversal`, use `HYPE-CC`.
- If a document path contains `ema-crossover`, use `HYPE-EMA-X`.
- If a document path contains `ema-trend-breakout`, use `HYPE-EMA-TB`.
- If a document path contains `5m-pullback-trail`, use `HYPE-5M-PBTR`.
- If a document lives under `archive/`, treat it as historical evidence, not the current entrypoint.

## 研究目录约定

新的策略研究默认由对应 topic 或 family 自管理：

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
