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
- 当前状态：seeded V0/V1 均只能作为 research diagnostic；尚未达到 live-ready。
- 固定 seed-universe 旧 lead：`HYPE-5M-Event-Quality-Scoring-Seeded-V1`，已在 strict seed-generation audit 中失败，不再作为 paper-audit lead。

## 证据面

- `hype-5m-event-quality-scoring-core-ledger.md`：本家族主台账，记录 Base、精简版和后续审计边界。
- `scripts/research_hype_5m_event_quality_v0.py`：自包含的 V0 事件生成、标注、walk-forward 排序、回放与报告输出脚本。
- `diagnostics/hype-5m-event-quality-v0-2026-06-27.md`：通用多源事件质量诊断。未找到 paper-audit 候选。
- `scripts/research_hype_5m_seeded_event_quality_v0.py`：seeded 诊断脚本，使用仅按 2026-03 之前训练指标筛选出的 `HYPE-5M-Micro-Scalp` relaxed-search 配置，再在 OOS 月份对其事件排序。
- `diagnostics/hype-5m-seeded-event-quality-v0-2026-06-27.md`：seeded source-mean ranker 报告。找到 `3` 行 paper-audit 记录；当前最优为 `seeded_source_mean_q80`。
- `artifacts/hype_5m_seeded_event_quality_v0_summary_2026-06-27.csv`：seeded V0 排序汇总。
- `diagnostics/hype-5m-seeded-event-quality-v0-ablation-2026-06-27.md`：seeded V0 打分公式 × 分位数门槛消融。显示较宽松的 `cfg_only__q60` 全年收益最高，但近期 3 个月为负且回撤越过稳定性门槛；当前 `current_70_20_10__q80` 仍是更均衡的 paper-audit 行。
- `diagnostics/hype-5m-seeded-event-quality-v01-style-prune-2026-06-27.md`：Seeded V0.1 style-prune 诊断。移除 `wick_reject` 和 `micro_breakout` 后，`no_wick_no_breakout__q80` 显著优于 Base。
- `diagnostics/hype-5m-seeded-event-quality-v01-full-ablation-2026-06-27.md`：Seeded V0.1 事件源集合 × 打分公式 × 分位门槛全参数消融。`no_wick_no_breakout__cfg_side_88_12__q80` 为当前排序首位。
- `diagnostics/hype-5m-seeded-v1-live-feasibility-2026-06-27.md`：Seeded V1 live feasibility 审计。将 `no_wick_no_breakout__cfg_side_88_12__q80` 登记为 V1，但明确不允许直接实盘或 paper-live。
- `diagnostics/hype-5m-seeded-v1-strict-seed-audit-2026-06-27.md`：Seeded V1 strict seed-generation audit。禁用历史 summary seeds，每月只用过去数据滚动筛 seed；结果为负，V1 固定 seed-universe 表现不被支持。

## 当前结论

通用 V0 事件池从 EMA 收复、VWAP 回归、Bollinger 回归、长影线拒绝、微型突破、MACD 翻转、动量停顿中共生成 `252,277` 个事件。在观测到的 Binance 成本与 walk-forward 排序下，`0` 个配置通过 paper gate；最优行仍为负。

seeded V0 诊断仅使用 `train_2025_05_30_to_2026_03_01` 指标从 `HYPE-5M-Micro-Scalp` relaxed-rounds 中选出 `100` 个种子配置，随后从 `2026-03-01` 起向前评估。它找到 `3` 行 paper-audit 记录。当前最优为：

- `seeded_source_mean_q80`：`184` 笔 OOS 交易，`1.57` 笔/天，`28.89%` 1x 收益，`1.222` PF，`52.72%` 胜率，`15.47 bps` 单笔均值，`-15.38%` 最大回撤，`27.18%` 近 30 天收益。

过去一年固定 seed universe 分段消融中，`current_70_20_10__q80` 回放 `633` 笔，全年收益 `61.81%`，PF `1.128`，单笔均值 `9.30 bps`，最大回撤 `-26.94%`。`cfg_only__q60` 全年收益更高（`179.93%`），但近 3 个月收益 `-6.39%` 且最大回撤 `-30.50%`，未通过稳定性门槛。

Seeded V0.1 style-prune 诊断显示，Base 中 `wick_reject` 和 `micro_breakout` 可以先移除。原精简首选 `no_wick_no_breakout__current_70_20_10__q80` 仅保留 `bb_revert`、`macd_flip`、`trend_rsi_snapback`、`vwap_revert`，过去一年固定 seed universe 回放 `545` 笔，收益 `238.78%`，PF `1.383`，单笔均值 `24.05 bps`，最大回撤 `-16.75%`，近 3 个月收益 `25.33%`。

V0.1 全参数消融进一步显示，当前排序首位为 `no_wick_no_breakout__cfg_side_88_12__q80`：`549` 笔，收益 `287.61%`，PF `1.425`，单笔均值 `26.33 bps`，最大回撤 `-16.30%`，近 3 个月收益 `24.59%`，负收益月份 `1/13`。低回撤备选 `bb_vwap_only__current_70_20_10__q85` 收益 `194.31%`，PF `1.489`，最大回撤 `-10.79%`。

`no_wick_no_breakout__cfg_side_88_12__q80` 已记录为 `HYPE-5M-Event-Quality-Scoring-Seeded-V1`。固定 seed-universe 下它曾有 `287.61%` 收益、PF `1.425`、最大回撤 `-16.30%`，但 strict seed-generation audit 禁用历史 summary seeds，并在每个测试月只使用过去数据滚动筛 seed；`6000` 个无数据配置的严格审计结果为 `493` 笔、`-61.16%` 收益、PF `0.843`、单笔 `-16.58 bps`、最大回撤 `-65.94%`。因此 V1 不再作为 paper-audit lead，只能保留为固定 seed-universe selection bias 诊断。

下一步如果继续本家族，应先做严格滚动 seed 的 V2 搜索；在出现严格 OOS 正结果前，不推进 paper-runner 对账、paper-live 或 live handoff。

## 目录规则

- `scripts/`：本家族的一次性可复现脚本。
- `artifacts/`：被 Markdown 报告引用的保留 JSON/CSV 证据。
- `diagnostics/`：搜索报告、模型诊断、no-go 记录与候选审计。
- `research-notes/`：非候选规格的探索性笔记。
- `live-specs/`：仅当候选已具备 paper-audit 证据后才可使用。

本家族不要使用裸版本号引用。请使用如 `HYPE-5M-Event-Quality-Scoring-V0` 这样的完整名称。
