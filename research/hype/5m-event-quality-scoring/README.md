# HYPE-5M-Event-Quality-Scoring

家族名称：`HYPE-5M-Event-Quality-Scoring`

历史别名：`HYPE-5M-EQS`

本家族覆盖 Binance HYPEUSDT 永续 `5m` 事件质量打分研究。
它不是纯粹的指标规则策略家族。规则用于生成候选事件；研究问题在于入场前上下文能否对这些事件进行有效排序，从而在扣除 live-executable 成本后只交易其中较好的子集。

它与以下家族相互独立：

- `HYPE-5M-Micro-Scalp`：固定规则的高频微利剥头皮搜索。
- `HYPE-5M-Pullback-Trail`：回踩/恢复入场 + ATR trailing-stop 出场。
- `HYPE-1M-EMA-Crossover`：Binance HYPEUSDT `1m` EMA 金叉/死叉研究。
- `HYPE-EMA-Crossover` 与 `HYPE-EMA-Trend-Breakout`：历史 `15m` EMA 家族。

## 当前范围

- 数据：仓库数据湖中 Binance HYPEUSDT 永续 `5m` 的 normalized 与 raw OHLCV。
- 事件来源：EMA 收复、VWAP 回归、Bollinger 回归、长影线拒绝、微型突破、MACD 翻转、动量停顿。
- 标注：收盘 K 线信号、下一根 K 线开盘入场、即时固定 TP/SL 框架，当单根 K 线可能同时触及目标与止损时采用保守的 stop-first 排序。
- 排序：仅使用历史事件的 walk-forward 事件质量排序，每个测试月之前设置 purge 窗口。
- 当前状态：seeded V0 paper-audit 候选；尚未达到 live-ready。

## 证据面

- `scripts/research_hype_5m_event_quality_v0.py`：自包含的 V0 事件生成、标注、walk-forward 排序、回放与报告输出脚本。
- `diagnostics/hype-5m-event-quality-v0-2026-06-27.md`：通用多源事件质量诊断。未找到 paper-audit 候选。
- `scripts/research_hype_5m_seeded_event_quality_v0.py`：seeded 诊断脚本，使用仅按 2026-03 之前训练指标筛选出的 `HYPE-5M-Micro-Scalp` relaxed-search 配置，再在 OOS 月份对其事件排序。
- `diagnostics/hype-5m-seeded-event-quality-v0-2026-06-27.md`：seeded source-mean ranker 报告。找到 `3` 行 paper-audit 记录；当前最优为 `seeded_source_mean_q80`。
- `artifacts/hype_5m_seeded_event_quality_v0_summary_2026-06-27.csv`：seeded V0 排序汇总。

## 当前结论

通用 V0 事件池从 EMA 收复、VWAP 回归、Bollinger 回归、长影线拒绝、微型突破、MACD 翻转、动量停顿中共生成 `252,277` 个事件。在观测到的 Binance 成本与 walk-forward 排序下，`0` 个配置通过 paper gate；最优行仍为负。

seeded V0 诊断仅使用 `train_2025_05_30_to_2026_03_01` 指标从 `HYPE-5M-Micro-Scalp` relaxed-rounds 中选出 `100` 个种子配置，随后从 `2026-03-01` 起向前评估。它找到 `3` 行 paper-audit 记录。当前最优为：

- `seeded_source_mean_q80`：`184` 笔 OOS 交易，`1.57` 笔/天，`28.89%` 1x 收益，`1.222` PF，`52.72%` 胜率，`15.47 bps` 单笔均值，`-15.38%` 最大回撤，`27.18%` 近 30 天收益。

这尚未达到 live-ready。它仍继承此前 `HYPE-5M-Micro-Scalp` 搜索的 config-universe 风险，仍需种子选择审计、成本压力测试、逐笔路径复核、订单维护审计，以及 paper/live-dry-run 对账。

## 目录规则

- `scripts/`：本家族的一次性可复现脚本。
- `artifacts/`：被 Markdown 报告引用的保留 JSON/CSV 证据。
- `diagnostics/`：搜索报告、模型诊断、no-go 记录与候选审计。
- `research-notes/`：非候选规格的探索性笔记。
- `live-specs/`：仅当候选已具备 paper-audit 证据后才可使用。

本家族不要使用裸版本号引用。请使用如 `HYPE-5M-Event-Quality-Scoring-V0` 这样的完整名称。
