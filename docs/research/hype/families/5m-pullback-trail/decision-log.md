# HYPE-5M-PBTR 决策日志

Family id：`HYPE-5M-PBTR`

这是 Binance HYPE `5m` 回踩恢复入场与 ATR trailing-stop 研究的家族级阅读路径。

## 当前边界

- 这是一个独立的 HYPE 策略家族。
- 不要把新的 `HYPE-5M-PBTR` 研究存放到 `families/ema-trend-breakout/`。
- 不要从裸版本号 `V1`、`V2`、`V35` 或其他版本号推断策略身份。
- 活跃 package 代码仍只承载数据与研究基础设施；策略事实以本 Markdown 家族树和一次性研究脚本为准。

## 研究批次记录

- `research-notes/hype-5m-indicator-ensemble-search.md`：在 `2025-06-01` 到 `2026-06-01` 的 Binance HYPE 永续 `5m` 数据上进行指标组合搜索。单条原始或精炼策略均未达到 `20x 年化 / >=80% 胜率 / >-20% 回撤`；一个由高胜率 EMA/Bollinger 回归腿组成的单仓 ensemble 达到全样本目标。该批次只作为研究前身，存在明显过拟合风险，不是已提升的 live 版本。
- `live-specs/ensemble-specs/README.md`：记录最初 `7` 个 `target_pass=True` 的 HYPE Binance `5m` 单仓 ensemble 组合作为 live-code 交接规格。它们共享相同精炼腿，只是腿数和杠杆不同；当前仅保留为历史支撑材料，不是现行提升路线。
- `research-notes/hype-5m-ensemble-forward-oos-2026-06-23.md`：加入 `2026-06-01` 到 `2026-06-23 04:00 UTC` 的 Binance HYPE `5m` 数据后，早期 7 个 ensemble 配置无法保持 `>=80%` 胜率和 `<20%` 回撤。这否定了高胜率小利润路径作为 live-ready 方向。
- `research-notes/hype-5m-positive-payoff-search-2026-06-23.md`：要求 `payoff_ratio > 1`、每个切片胜率 `>=60%`、每个切片年化 `>=20x` 后，基础搜索没有命中。定向 refinement 虽产生数学命中，但回撤不可接受；结论是在讨论收益前必须加入生存约束。
- `research-notes/hype-5m-survival-frontier-2026-06-23.md`：生存前沿要求每个切片 `payoff_ratio > 1`、交易数、胜率底线 `55%/58%/60%`，以及回撤底线 `-20%/-25%/-30%`。最有用的中间候选是 `HYPE_PP_R05732__dir_htf_ge_0.688442`，全样本年化 `29.07x`，最差切片年化 `9.75x`，最差切片胜率 `58.29%`，payoff `2.19`。
- `ablations/hype-5m-r05732-strategy-ablation-2026-06-23.md`：将 R05732 提升为 `HYPE-5M-PBTR-V1` 候选。消融显示 `trail_atr=0.75` 和 `min_hold_bars=6` 是核心；删除最终 `dir_htf` 会显著提高频率和收益，但降低最差切片胜率；`pullback_buffer=0.01` 以及删除/提高固定止盈是最佳后续方向。
- `hype-5m-pullback-trail-core-ledger.md`：`HYPE-5M-PBTR-V1/V2` 主账。
- `research-notes/hype-5m-pullback-trail-v2-combo-test-2026-06-23.md`：围绕 V1 消融发现测试 `10240` 个同步组合，`1568` 个通过 V2 门槛。提升 `HYPE-5M-PBTR-V2`，参数为 `pullback_buffer=0.01`、`tp_atr=99`、`stop_atr=0.5`、`roc_window=96`、`min_efficiency=0`、`dir_htf>=0.5`。
- `live-specs/hype-5m-pullback-trail-v2-live-spec.md`：`HYPE-5M-PBTR-V2` 的详细复现规格，供实现 AI 使用，包含指标公式、信号构造、单仓执行、ATR trailing-stop 管理、重启恢复和验收指标。
- `ablations/hype-5m-pullback-trail-v2-ablation-slices-2026-06-23.md`：V2 全参数消融，包含 `56` 个周切片、滚动 1w/1m/3m/6m/full 统计，以及 V1/V2 横向对比。
- `ablations/hype-5m-pullback-trail-v2-live-cost-ablation-slices-2026-06-23.md`：用观测到的实盘执行成本重跑 V2 全参数消融和时间切片，成本为手续费 `4.1466 bps/turnover`、开仓滑点 `+10.73 bps`、平仓滑点 `-2.64 bps`、净滑点 `+4.0449 bps/total turnover`。
- `ablations/hype-5m-pullback-trail-v21-live-cost-variants-2026-06-23.md`：通过固定/删除 V2 中不活跃参数，提升简化表达 `HYPE-5M-PBTR-V2.1-clean`，随后在同一实盘成本模型下测试 V2.1A 收益分支、V2.1B clean-plus 分支和 V2.1C 稳定分支。
- `diagnostics/hype-5m-pbtr-v21a-remove-final-htf-live-cost-2026-06-24.md`：接受 `remove_final_filter_dir_htf` 作为来自 V2.1A 的独立高频候选，并使用观测实盘成本复核。
- `diagnostics/hype-5m-pbtr-v3-ablation-audit-2026-06-24.md`：正式将该高频候选记录为 `HYPE-5M-PBTR-V3`，包含全参数消融、周/月/滚动时间切片，以及对不真实年化的资深量化审计。V3 不是 V2.1A 的替代版本，需要小资金 dry-run 和执行压力测试。
- `diagnostics/hype-5m-pbtr-v31-min-hold-9-2026-06-24.md`：将 V3 消融中表现最强的 `min_hold_bars=9` 固化为 `HYPE-5M-PBTR-V3.1` 研究候选，并生成 HTML 交易路径图。V3.1 样本内显著提高胜率/PF，但最大回撤扩大，不能直接替代 V3。
- `diagnostics/hype-5m-pbtr-v32-clean-entry-filters-2026-06-24.md`：根据外部审计意见删除 V3.1 中剩余无贡献/负贡献入场过滤器，形成 `HYPE-5M-PBTR-V3.2`。V3.2 仅保留方向、pullback/resume、`min_hold_bars=9` 和 ATR trailing exit，样本内收益和回撤均优于 V3.1，是当前更简洁的 paper/dry-run 首选表达。

## 当前决策

- `HYPE-5M-PBTR-V1`：保留为更干净的胜率体验基线 dry-run 候选。
- `HYPE-5M-PBTR-V2`：当前主要收益 dry-run 候选，频率和 payoff 更高，但胜率略低。
- `HYPE-5M-PBTR-V2.1-clean`：在观测实盘成本分析下，作为 V2 的首选简化表达；表现与 V2 基本一致，同时移除了不活跃解释参数。
- `HYPE-5M-PBTR-V3`：来自 V2.1A、关闭 final HTF 的独立高频研究候选；与 `V3-lite = V2.1A + dir_htf >= 0` 并行测试，不作为生产直接替代版本。
- `HYPE-5M-PBTR-V3.1`：来自 V3，将 `min_hold_bars` 提高到 `9`；作为高收益研究候选单独 dry-run，重点观察真实回撤是否显著扩张。
- `HYPE-5M-PBTR-V3.2`：来自 V3.1，删除剩余入场过滤器；作为当前首选 clean 高频表达进入 paper/dry-run，重点验证新增交易子集和真实执行成本。
- V1/V2/V2.1/V3/V3.1/V3.2 候选在生产 sizing 前都必须先有 live dry-run 证据。
