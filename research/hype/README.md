# HYPE Research Index

HYPE 有多个互不相关但复用版本号的策略家族。不要按裸版本号阅读：先选家族，永远优先完整 family name，短 id 只作为历史别名。

本文件是**路由表**：每个家族只维护身份、机制、防串线警告、状态和主账链接。版本细节、证据清单和阅读顺序的唯一事实源是各家族 core ledger 与 `decision-log.md`。

## 阅读顺序（通用）

1. `../README.md`
2. 本文件
3. 目标家族 `README.md`
4. 该家族 core ledger / 主账
5. 该家族 `decision-log.md`
6. 按需打开 canonical specs、diagnostics、ablations、live specs、artifacts。

状态词定义见 `../strategy-status-glossary.md`。

## Strategy Families

| Full family name | Alias | Directory | 主账 / 入口 | 机制 | 防串线警告 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| `HYPE-Candle-Count-Reversal` | `HYPE-CC` | `15m-candle-count-reversal/` | `15m-candle-count-reversal/hype-cc-15m-milestone-comparison.md` | 10-of-8 K 线颜色反转 + ATR 风控与 early-exit 变体 | 这里的 `V35` 不是 trend breakout 的 `V35` | archived/canonical specs |
| `HYPE-EMA-Crossover` | `HYPE-EMA-X` | `15m-ema-crossover/` | `15m-ema-crossover/hype-ema-x-core-ledger.md` | EMA 金叉/死叉家族（V14 时代过滤、出场、状态机、late re-entry 演化） | 不要与 `HYPE-EMA-Trend-Breakout` 合并，即使都用 EMA96/384 | promoted research candidates（V15-V18），未 live |
| `HYPE-EMA-Trend-Breakout` | `HYPE-EMA-TB` | `15m-ema-trend-breakout/` | `15m-ema-trend-breakout/hype-ema-tb-core-ledger.md` | EMA 趋势突破 / 追多追空家族（ADX、volume、1h confirm、跨所执行变体） | 这里的 `V35` 不是 candle-count `V35` 或 EMA-cross `V14` | archived/canonical specs |
| `HYPE-1H-Adaptive-Regime` | `HYPE-1H-AR` | `1h-adaptive-regime/` | `1h-adaptive-regime/hype-1h-ar-core-ledger.md` | `1h` DI-cross + stochastic-reversal 自适应 ensemble 广搜 | 版本号 local 于本家族 | V1-V4 registered / not promoted / not live-ready |
| `HYPE-15M-Multi-Indicator-Intraday` | `HYPE-15M-MII` | `15m-multi-indicator-intraday/` | `15m-multi-indicator-intraday/hype-15m-mii-core-ledger.md` | `15m` RSI/MACD/EMA/ADX/ATR/volume/structure 广搜 | 不是 EMA-X、EMA-TB 或 candle-count 的版本 | V1.3 live spec / not live-ready |
| `HYPE-15M-Riptide` | - | `15m-riptide/` | `15m-riptide/README.md` | `15m` EMA20/60 趋势背景 RSI 回踩 + 1h RV regime + ATR bracket | `V13` local 于 Riptide | diagnostic / reproduction-pending |
| `HYPE-1M-EMA-Crossover` | `HYPE-1M-EMA-X` | `1m-ema-crossover/` | `1m-ema-crossover/README.md` | `1m` EMA cross，next-bar 入场、固定/trailing TP | 不是 `15m-ema-crossover` 的子文档 | diagnostic / dry-run candidate only |
| `HYPE-1M-MA-Pullback-Scalp` | - | `1m-ma-pullback-scalp/` | `1m-ma-pullback-scalp/README.md` | `1m` 双 MA 回踩 + HH/HL 结构 + 固定 bracket | 不是 `HYPE-1M-EMA-Crossover` 的版本 | not promoted / not live-ready |
| `HYPE-5M-Pullback-Trail` | `HYPE-5M-PBTR` | `5m-pullback-trail/` | `5m-pullback-trail/hype-5m-pullback-trail-core-ledger.md` | `5m` 回踩/恢复入场 + ATR trailing stop | 本地 `V1/V2` 不是 15m `EMA-TB` 的 V1/V2 | active research candidate；V6.2.1 在 runner dry-run |
| `HYPE-15M-Pullback-Trail` | - | `15m-pullback-trail/` | `15m-pullback-trail/README.md` | `15m` 回踩事件源 + V3.3 迁移 + bracket 搜索 | 不是 `HYPE-5M-Pullback-Trail` 的 promoted 版本 | V3.3 迁移 not promoted；bracket audit only |
| `HYPE-5M-MA-Pullback-Scalp` | - | `5m-ma-pullback-scalp/` | `5m-ma-pullback-scalp/README.md` | `5m` 双 MA 回踩 scalp + 固定 bracket | 不是 `HYPE-5M-Micro-Scalp` 的版本 | audit candidates only |
| `HYPE-5M-Micro-Scalp` | `HYPE-5M-MS` | `5m-micro-scalp/` | `5m-micro-scalp/hype-5m-micro-scalp-core-ledger.md` | `5m` 高频小利 scalp 搜索 + 立即 TP/SL bracket | 高胜率 no-go 行不得当作 pullback-trail 或 live 候选 | V1-V1.3 registered audit observations / not live-ready |
| `HYPE-5M-Event-Quality-Scoring` | `HYPE-5M-EQS` | `5m-event-quality-scoring/` | `5m-event-quality-scoring/hype-5m-event-quality-scoring-core-ledger.md` | `5m` 事件质量打分（候选事件 + seeded 信号） | seeded audit 行不是 micro-scalp 或 live 候选 | V1 failed strict seed audit / no candidate |
| `HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble` | `HYPE-15M-TB-MII-ENS` | `15m-trend-breakout-multi-indicator-ensemble/` | `15m-trend-breakout-multi-indicator-ensemble/hype-15m-tb-mii-ens-core-ledger.md` | `EMA-TB-V35` + `MII-V1.3` 组合（双子账户 / 单账户仲裁） | 不重定义任一 parent 版本 | first combination diagnostic / not promoted |
| `HYPE-6H-RS4-Regime-Switch` | - | `6h-rs4-regime-switch/` | `6h-rs4-regime-switch/hype-6h-rs4-regime-switch-core-ledger.md` | `6h` regime-switch：v10 压缩动量腿 + melt 扩张突破腿 | 同事外部规格复现线，与其他 HYPE 家族无版本关系 | V1 diagnostic only / not promoted |

## 诊断主题（非策略家族）

- `cross-strategy-account/README.md`：HYPE 多策略共享子账户 / 全局单仓组合诊断入口。当前含 `HYPE-5M-PBTR-V6.2.1` + `HYPE-15M-MII-V1.3` 共享子账户回放；结论与风险数字见该目录文档，不提升任何子策略状态。

## Hard Rules

- 永远不要只凭 `Vxx` 回答；引用时带完整 family name。
- 每个家族是独立研究线；指标相似不构成合并理由（详见上表防串线列）。
- 持久 HYPE 研究报告与主账必须是 `research/` 下的 repo-tracked Markdown；Canvas 与 `legacy-canvas/` 只是历史/临时表面（细则见 `../../.cursor/rules/research-report-storage.mdc`）。
- `archive/code/platform/` 只是被研究文档引用的历史源码快照；`src/strategy_lab/` 是数据基础设施，都不是策略事实来源。

## Transfer Notes

- 旧的 HYPE kernel 跨资产检查（BTC、XMR、XAU、TradFi perp、CMC universe）归档于 `../../archive/research/hype-transfer/`。
- 新的 promoted transfer 研究应获得明确方向或资产家族，如 `../mu/` 下的 `MU-HYPE-Transfer`（别名 `MU-HYPE-XFER`）。

## Archived Cursor Assets

旧 Cursor Canvas 文件存放在仓库外的 Cursor 私有存储；原 repo 管理的 Canvas / agent artifact 索引归档于 `../../archive/docs/hype-cursor-artifacts/`。它们是迁移证据，不是 active 入口。
