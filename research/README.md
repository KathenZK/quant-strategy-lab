# Research

`research/` 是本仓库的主要知识入口。它不只放 Markdown，也管理当前研究需要保留的一次性脚本和小型产物。

本文件是**路由表**：只维护家族身份、一句话机制、当前状态标签和主账链接。版本级指标、证据清单和参数细节的唯一事实源是各家族 core ledger；不要把它们复述回本文件。

## 阅读顺序

1. 本文件：确定 family 与目录。
2. 对应资产 README（如 [hype/README.md](hype/README.md)、[btc/README.md](btc/README.md)）。
3. 目标家族 `README.md` → core ledger / 主账 → `decision-log.md`。
4. 按需打开 `specs/`（研究侧版本规格）、diagnostics、ablations、`live-specs/`（runner 交接规格）、artifacts。

状态词定义见 [strategy-status-glossary.md](../docs/research-governance/strategy-status-glossary.md)（唯一状态机来源）；策略推进门禁见 [strategy-validation-gates.md](../docs/research-governance/strategy-validation-gates.md)。工作约束见 [../AGENTS.md](../AGENTS.md) 与 `../.cursor/rules/`。

## 命名规则

- 不要用裸版本号（`V13`、`V35`……）判断策略身份；版本号只在具体家族内有意义。
- 引用时使用完整 family name（如 `HYPE-EMA-Trend-Breakout-V35`），短 id 只作为历史别名。
- 目录名到 family name 的映射是确定性的：`research/<asset>/<timeframe>-<strategy-family-slug>/` 对应 `<ASSET>-<TIMEFRAME>-<Strategy-Family-Name>`；各家族 README 首行声明完整名称与别名，以家族 README 为准。
- `archive/` 下的文档一律视为历史证据，不是当前入口。

## HYPE 策略家族

详细路由与防串线警告见 [hype/README.md](hype/README.md)。

| Full family name | Alias | Directory | 机制 | 状态 |
| --- | --- | --- | --- | --- |
| `HYPE-Candle-Count-Reversal` | `HYPE-CC` | [hype/15m-candle-count-reversal/](hype/15m-candle-count-reversal/README.md) | 10-of-8 K 线颜色反转 + ATR 风控 | V35 dry-run / forward-test required |
| `HYPE-EMA-Crossover` | `HYPE-EMA-X` | [hype/15m-ema-crossover/](hype/15m-ema-crossover/README.md) | EMA 金叉/死叉家族（V14 时代演化） | V18 dry-run / forward-test required |
| `HYPE-EMA-Trend-Breakout` | `HYPE-EMA-TB` | [hype/15m-ema-trend-breakout/](hype/15m-ema-trend-breakout/README.md) | EMA96/384 趋势突破 / 追多追空 | V35 live（外部 hype-trend runner）；V36-V39.1 registered / not promoted |
| `HYPE-15M-Multi-Horizon-EMA-Forecast` | `HYPE-15M-MHEF` | [hype/15m-multi-horizon-ema-forecast/](hype/15m-multi-horizon-ema-forecast/README.md) | `15m` 四组 EMA 波动率归一化 forecast 加权连续仓位 | explore / not promoted / not live-ready |
| `HYPE-1M-EMA-Crossover` | `HYPE-1M-EMA-X` | [hype/1m-ema-crossover/](hype/1m-ema-crossover/README.md) | `1m` EMA 金叉/死叉，可执行时序 | explore / not promoted / not live-ready |
| `HYPE-1M-MA-Pullback-Scalp` | - | [hype/1m-ma-pullback-scalp/](hype/1m-ma-pullback-scalp/README.md) | `1m` 双 MA 回踩 scalp | explore / not promoted / not live-ready |
| `HYPE-1H-Adaptive-Regime` | `HYPE-1H-AR` | [hype/1h-adaptive-regime/](hype/1h-adaptive-regime/README.md) | `1h` DI 趋势 + 随机指标反转自适应 ensemble | V1-V4 registered / not promoted / not live-ready |
| `HYPE-1H-Multi-Horizon-EMA-Forecast` | `HYPE-1H-MHEF` | [hype/1h-multi-horizon-ema-forecast/](hype/1h-multi-horizon-ema-forecast/README.md) | `1h` 四组 EMA 波动率归一化 forecast 加权连续仓位 | explore / not promoted / not live-ready |
| `HYPE-1D-Multi-Horizon-EMA-Forecast` | `HYPE-1D-MHEF` | [hype/1d-multi-horizon-ema-forecast/](hype/1d-multi-horizon-ema-forecast/README.md) | `1d` 四组经典 EWMAC forecast 加权连续仓位 | explore / not promoted / not live-ready |
| `HYPE-15M-Multi-Indicator-Intraday` | `HYPE-15M-MII` | [hype/15m-multi-indicator-intraday/](hype/15m-multi-indicator-intraday/README.md) | `15m` 多指标日内广搜 | V1.3 dry-run / forward-test required |
| `HYPE-15M-Riptide` | - | [hype/15m-riptide/](hype/15m-riptide/README.md) | `15m` EMA 趋势背景 RSI 回踩 + RV regime | explore / not promoted（复现对账未完成） |
| `HYPE-30M-Keltner-Trend-Breakout` | `K2-FQ-V2-ATRVT-OFF` | [hype/30m-keltner-trend-breakout/](hype/30m-keltner-trend-breakout/README.md) | `30m` Keltner 突破 + `1h` EMA regime + ATRVT 动态杠杆 | V3 registered / not promoted / not live-ready |
| `HYPE-15M-Pullback-Trail` | - | [hype/15m-pullback-trail/](hype/15m-pullback-trail/README.md) | `15m` 回踩事件源 + bracket 搜索 | explore / not promoted / not live-ready |
| `HYPE-5M-Pullback-Trail` | `HYPE-5M-PBTR` | [hype/5m-pullback-trail/](hype/5m-pullback-trail/README.md) | `5m` 回踩/恢复入场 + ATR trailing stop | V6.2.1 dry-run / forward-test required |
| `HYPE-5M-MA-Pullback-Scalp` | - | [hype/5m-ma-pullback-scalp/](hype/5m-ma-pullback-scalp/README.md) | `5m` 双 MA 回踩 scalp | explore / not promoted / not live-ready |
| `HYPE-5M-Micro-Scalp` | `HYPE-5M-MS` | [hype/5m-micro-scalp/](hype/5m-micro-scalp/README.md) | `5m` 高频小利 scalp 搜索 | V1-V1.3 registered / not promoted / not live-ready |
| `HYPE-5M-Event-Quality-Scoring` | `HYPE-5M-EQS` | [hype/5m-event-quality-scoring/](hype/5m-event-quality-scoring/README.md) | `5m` 事件质量打分 | V1 registered / not promoted（strict seed audit 未通过） |
| `HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble` | `HYPE-15M-TB-MII-ENS` | [hype/15m-trend-breakout-multi-indicator-ensemble/](hype/15m-trend-breakout-multi-indicator-ensemble/README.md) | `EMA-TB-V39` + `MII-V1.4` 单账户组合（V39 优先 + 强平让位） | V2 dry-run active / replay parity PASS / live disabled / not live-ready |
| `HYPE-6H-RS4-Regime-Switch` | - | [hype/6h-rs4-regime-switch/](hype/6h-rs4-regime-switch/README.md) | `6h` regime-switch 趋势（压缩动量腿 + 扩张突破腿）复现 | V1 registered / not promoted / not live-ready |

## 单资产研究（非 HYPE）

| Family | Alias | Directory | 状态 |
| --- | --- | --- | --- |
| `BTC-1H-Adaptive-Regime` | `BTC-1H-AR` | [btc/1h-adaptive-regime/](btc/1h-adaptive-regime/README.md) | V1-V4 registered / not promoted / not live-ready（V4 为 V3 clean-equivalent） |
| `ETH-1H-Adaptive-Regime` | `ETH-1H-AR` | [eth/1h-adaptive-regime/](eth/1h-adaptive-regime/README.md) | V1-V4 registered / not promoted / not live-ready |
| `SOL-1H-Adaptive-Regime` | `SOL-1H-AR` | [sol/1h-adaptive-regime/](sol/1h-adaptive-regime/README.md) | V1-V3 registered；V3 Donchian core + VWAP arm-confirm satellite；not promoted / not live-ready |
| `SOL-1H-Volatility-Compression-Breakout` | `SOL-1H-VCB` | [sol/1h-volatility-compression-breakout/](sol/1h-volatility-compression-breakout/README.md) | 首轮扩展搜索 NO-GO / explore / not promoted / not live-ready |
| `SOL-4H-RS4-Regime-Switch` | `SOL-4H-RS4` | [sol/4h-rs4-regime-switch/](sol/4h-rs4-regime-switch/README.md) | 首轮 base-gate 0 / NO-GO / explore / not promoted / not live-ready |
| `SOL-1H-Pullback-Bracket` | `SOL-1H-PB` | [sol/1h-pullback-bracket/](sol/1h-pullback-bracket/README.md) | 首轮 hard-pass 0 / low-return NO-GO / explore / not promoted / not live-ready |
| `TRX-1H-Adaptive-Regime` | `TRX-1H-AR` | [trx/1h-adaptive-regime/](trx/1h-adaptive-regime/README.md) | V1-V3 registered / not promoted / not live-ready |
| `BNB-1H-Adaptive-Regime` | `BNB-1H-AR` | [bnb/1h-adaptive-regime/](bnb/1h-adaptive-regime/README.md) | V1-V3 registered / not promoted / not live-ready |
| `BNB-15M-Adaptive-Regime` | `BNB-15M-AR` | [bnb/15m-adaptive-regime/](bnb/15m-adaptive-regime/README.md) | explore / not promoted |

各资产入口：[btc/README.md](btc/README.md)、[eth/README.md](eth/README.md)、[sol/README.md](sol/README.md)、[trx/README.md](trx/README.md)、[bnb/README.md](bnb/README.md)。

## 组合与跨资产研究

入口：[asset-portfolios/README.md](asset-portfolios/README.md)。跨资产研究不是 HYPE 策略家族，除非文档明确把它提升为某个 HYPE family variant。

| Family / Topic | Directory | 状态 |
| --- | --- | --- |
| `Binance-1D-Turtle-Breakout` | [asset-portfolios/1d-turtle-breakout/](asset-portfolios/1d-turtle-breakout/README.md) | explore |
| `Binance-15M-Multi-Indicator-Intraday-Transfer` | [asset-portfolios/15m-multi-indicator-intraday/](asset-portfolios/15m-multi-indicator-intraday/README.md) | explore / not promoted |
| `Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble`（`BIN-1H-AR-MAE`） | [asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/](asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/README.md) | V1 registered / not promoted / not live-ready |
| `Binance-MK7-Multi-Strategy-Account`（外部别名 `mk7`） | [asset-portfolios/mk7-multi-strategy-account/](asset-portfolios/mk7-multi-strategy-account/README.md) | `mk7-v8` external observation / explore / not promoted / not live-ready |
| `HYPE-Cross-Strategy-Account` | [asset-portfolios/hype-cross-strategy-account/](asset-portfolios/hype-cross-strategy-account/README.md) | explore；HYPE 单资产多策略子账户诊断，不提升子策略状态 |
| `MU-HYPE-Transfer`（`MU-HYPE-XFER`） | [mu/](mu/README.md)（扁平结构，grandfathered） | explore |

旧 HYPE cross-asset transfer 材料位于 `../archive/research/hype-transfer/`。

## 共享研究内核

跨资产或跨家族复用的研究引擎存放在 `_shared-kernels/`，按冻结版本目录管理（见 [_shared-kernels/README.md](_shared-kernels/README.md)）。当前包括 [1h-adaptive-regime-search/](_shared-kernels/1h-adaptive-regime-search/README.md) 与 [multi-horizon-ema-forecast/](_shared-kernels/multi-horizon-ema-forecast/README.md)。

## 目录与存储约定

细则以 `../.cursor/rules/research-report-storage.mdc` 为准，要点：

- 新时间片或新机制必须新建 `research/<asset>/<timeframe>-<strategy-family-slug>/`，不得因指标相似塞进旧 family。
- 家族目录内：`README.md` + core ledger + `decision-log.md` 为长期入口；`specs/` 放研究侧版本规格，`live-specs/` 放 runner 交接规格；`diagnostics/`、`ablations/`、`notes/` 按性质分类；验证门禁报告按 [strategy-validation-gates.md](../docs/research-governance/strategy-validation-gates.md) 落入对应类型目录；`scripts/` 放一次性研究脚本；`artifacts/` 放需保留的产物；进入 dry-run 后增加 `runner-tracking/`。
- 新建或重构主账先使用 [core-ledger-template.md](../docs/research-governance/core-ledger-template.md)；主账只保存版本身份、当前状态、版本规则、版本表和证据链接，不承载完整实验报告或参数表。
- 新建家族必须同步登记进对应资产 README 和本文件的路由表（索引更新义务）。
- 长期研究文档默认中文；顶层 `reports/` 已退役；Canvas 不是长期事实源。

## 历史或浅层研究

`crowding_reversal` 及早期平台示例（spot CTA、CTA grid、通用 MA crossover、momentum rotation、Donchian 变体）归档于 `../archive/research/`，不作为当前核心研究线。
