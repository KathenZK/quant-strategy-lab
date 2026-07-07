# Research

`research/` 是本仓库的主要知识入口。它不只放 Markdown，也管理当前研究需要保留的一次性脚本和小型产物。

本文件是**路由表**：只维护家族身份、一句话机制、当前状态标签和主账链接。版本级指标、证据清单和参数细节的唯一事实源是各家族 core ledger；不要把它们复述回本文件。

## 阅读顺序

1. 本文件：确定 family 与目录。
2. 对应资产 `README.md`（如 `hype/README.md`、`btc/README.md`）。
3. 目标家族 `README.md` → core ledger / 主账 → `decision-log.md`。
4. 按需打开 canonical specs、diagnostics、ablations、live specs、artifacts。

状态词定义见 `strategy-status-glossary.md`（唯一状态机来源）。工作约束见 `../AGENTS.md` 与 `../.cursor/rules/`。

## 命名规则

- 不要用裸版本号（`V13`、`V35`……）判断策略身份；版本号只在具体家族内有意义。
- 引用时使用完整 family name（如 `HYPE-EMA-Trend-Breakout-V35`），短 id 只作为历史别名。
- 目录名到 family name 的映射是确定性的：`research/<asset>/<timeframe>-<strategy-family-slug>/` 对应 `<ASSET>-<TIMEFRAME>-<Strategy-Family-Name>`；各家族 README 首行声明完整名称与别名，以家族 README 为准。
- `archive/` 下的文档一律视为历史证据，不是当前入口。

## HYPE 策略家族

详细路由与防串线警告见 `hype/README.md`。

| Full family name | Alias | Directory | 机制 | 状态 |
| --- | --- | --- | --- | --- |
| `HYPE-Candle-Count-Reversal` | `HYPE-CC` | `hype/15m-candle-count-reversal/` | 10-of-8 K 线颜色反转 + ATR 风控 | archived/canonical specs |
| `HYPE-EMA-Crossover` | `HYPE-EMA-X` | `hype/15m-ema-crossover/` | EMA 金叉/死叉家族（V14 时代演化） | promoted research candidates（V15-V18），未 live |
| `HYPE-EMA-Trend-Breakout` | `HYPE-EMA-TB` | `hype/15m-ema-trend-breakout/` | EMA96/384 趋势突破 / 追多追空 | archived/canonical specs；V35 在 runner 侧有历史实现 |
| `HYPE-1M-EMA-Crossover` | `HYPE-1M-EMA-X` | `hype/1m-ema-crossover/` | `1m` EMA 金叉/死叉，可执行时序 | diagnostic / dry-run candidate only |
| `HYPE-1M-MA-Pullback-Scalp` | - | `hype/1m-ma-pullback-scalp/` | `1m` 双 MA 回踩 scalp | NO-GO |
| `HYPE-1H-Adaptive-Regime` | `HYPE-1H-AR` | `hype/1h-adaptive-regime/` | `1h` DI 趋势 + 随机指标反转自适应 ensemble | V1-V4 registered / NO-GO |
| `HYPE-15M-Multi-Indicator-Intraday` | `HYPE-15M-MII` | `hype/15m-multi-indicator-intraday/` | `15m` 多指标日内广搜 | V1.3 runner implementation target / not live-ready |
| `HYPE-15M-Riptide` | - | `hype/15m-riptide/` | `15m` EMA 趋势背景 RSI 回踩 + RV regime | diagnostic / reproduction-pending |
| `HYPE-15M-Pullback-Trail` | - | `hype/15m-pullback-trail/` | `15m` 回踩事件源 + bracket 搜索 | V3.3 迁移 NO-GO；bracket paper-audit only |
| `HYPE-5M-Pullback-Trail` | `HYPE-5M-PBTR` | `hype/5m-pullback-trail/` | `5m` 回踩/恢复入场 + ATR trailing stop | active research candidate；V6.2.1 在 runner dry-run |
| `HYPE-5M-MA-Pullback-Scalp` | - | `hype/5m-ma-pullback-scalp/` | `5m` 双 MA 回踩 scalp | paper-audit candidates only |
| `HYPE-5M-Micro-Scalp` | `HYPE-5M-MS` | `hype/5m-micro-scalp/` | `5m` 高频小利 scalp 搜索 | V1-V1.3 registered paper-audit observations / not live-ready |
| `HYPE-5M-Event-Quality-Scoring` | `HYPE-5M-EQS` | `hype/5m-event-quality-scoring/` | `5m` 事件质量打分 | V1 failed strict seed audit / no candidate |
| `HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble` | `HYPE-15M-TB-MII-ENS` | `hype/15m-trend-breakout-multi-indicator-ensemble/` | `EMA-TB-V35` + `MII-V1.3` 组合研究 | first combination diagnostic / NO-GO |
| `HYPE-6H-RS4-Regime-Switch` | - | `hype/6h-rs4-regime-switch/` | `6h` regime-switch 趋势（压缩动量腿 + 扩张突破腿）复现 | V1 diagnostic only / not promoted |
| （诊断主题）HYPE cross-strategy account | - | `hype/cross-strategy-account/` | 多策略共享子账户 / 全局单仓组合诊断 | diagnostic topic；不提升任何子策略状态 |

## 单资产研究（非 HYPE）

| Family | Alias | Directory | 状态 |
| --- | --- | --- | --- |
| `BTC-1H-Adaptive-Regime` | `BTC-1H-AR` | `btc/1h-adaptive-regime/` | V1-V4 registered；V4 为 V3 最小等价干净版；forward-test required / not live-ready |
| `ETH-1H-Adaptive-Regime` | `ETH-1H-AR` | `eth/1h-adaptive-regime/` | V1-V3 registered / NO-GO |
| `SOL-1H-Adaptive-Regime` | `SOL-1H-AR` | `sol/1h-adaptive-regime/` | V1-V2 registered / NO-GO |
| `TRX-1H-Adaptive-Regime` | `TRX-1H-AR` | `trx/1h-adaptive-regime/` | V1-V3 registered / NO-GO |
| `BNB-1H-Adaptive-Regime` | `BNB-1H-AR` | `bnb/1h-adaptive-regime/` | V1-V3 registered / NO-GO |
| `BNB-15M-Adaptive-Regime` | `BNB-15M-AR` | `bnb/15m-adaptive-regime/` | active diagnostic research / not promoted |

各资产入口：`btc/README.md`、`eth/README.md`、`sol/README.md`、`trx/README.md`、`bnb/README.md`。

## 组合与跨资产研究

入口：`asset-portfolios/README.md`。跨资产研究不是 HYPE 策略家族，除非文档明确把它提升为某个 HYPE family variant。

| Family / Topic | Directory | 状态 |
| --- | --- | --- |
| `Binance-1D-Turtle-Breakout` | `asset-portfolios/1d-turtle-breakout/` | diagnostic |
| `Binance-15M-Multi-Indicator-Intraday-Transfer` | `asset-portfolios/15m-multi-indicator-intraday/` | 迁移诊断；整体不提升 |
| `Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble`（`BIN-1H-AR-MAE`） | `asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/` | V1 registered diagnostic / NO-GO |
| `MU-HYPE-Transfer`（`MU-HYPE-XFER`） | `mu/`（扁平结构，grandfathered） | core transfer research line |

旧 HYPE cross-asset transfer 材料位于 `../archive/research/hype-transfer/`。

## 共享研究内核

跨资产复用的研究引擎存放在 `_shared-kernels/`，按冻结版本目录管理（见 `_shared-kernels/README.md`）。当前内核：`1h-adaptive-regime-search/`（六个资产的 `1h` adaptive-regime 系列脚本共享引擎）。

## 目录与存储约定

细则以 `../.cursor/rules/research-report-storage.mdc` 为准，要点：

- 新时间片或新机制必须新建 `research/<asset>/<timeframe>-<strategy-family-slug>/`，不得因指标相似塞进旧 family。
- 家族目录内：`README.md` + core ledger + `decision-log.md` 为长期入口；`diagnostics/`、`ablations/`、`canonical-specs/`、`live-specs/`、`research-notes/` 按性质分类；`scripts/` 放一次性研究脚本；`artifacts/` 放需保留的产物；进入 dry-run 后增加 `forward-tracking/`。
- 新建家族必须同步登记进对应资产 README 和本文件的路由表（索引更新义务）。
- 长期研究文档默认中文；顶层 `reports/` 已退役；Canvas 不是 canonical storage。

## 历史或浅层研究

`crowding_reversal` 及早期平台示例（spot CTA、CTA grid、通用 MA crossover、momentum rotation、Donchian 变体）归档于 `../archive/research/`，不作为当前核心研究线。
