# HYPE-5M-Event-Quality-Scoring Core Ledger

家族名称：`HYPE-5M-Event-Quality-Scoring`

历史别名：`HYPE-5M-EQS`

本台账记录 Binance HYPEUSDT 永续 `5m` 事件质量打分研究的主线版本、候选状态、关键证据和后续审计边界。裸版本号不具有策略身份；必须使用完整名称，例如 `HYPE-5M-Event-Quality-Scoring-Seeded-V0`。

## 当前状态

- 当前 baseline：`HYPE-5M-Event-Quality-Scoring-Seeded-V0`，实现口径为 `current_70_20_10__q80`。
- 固定 seed-universe 旧 lead：`HYPE-5M-Event-Quality-Scoring-Seeded-V1`，实现口径为 `no_wick_no_breakout__cfg_side_88_12__q80`。
- 当前角色：V1 已在 strict seed-generation audit 中失败；仅保留为固定 seed-universe diagnostic，不再是 audit lead。
- 最大已知风险：固定 seed configs 来自 `HYPE-5M-Micro-Scalp` 历史 relaxed-search 产物，strict audit 显示存在显著 config-universe / seed-selection bias。
- 下一步主线：若继续本家族，应先做严格滚动 seed 的 V2 搜索；在出现严格 OOS 正结果前，不做 paper/live-dry-run 对账或部署推进。

## 版本台账

| Version | Status | Core idea | Evidence | Decision |
| --- | --- | --- | --- | --- |
| `HYPE-5M-Event-Quality-Scoring-Generic-V0` | no-go | 多源规则生成事件，再用低依赖 walk-forward ranker 分层 | `diagnostics/hype-5m-event-quality-v0-2026-06-27.md` | `252,277` 个事件但 `0` 个 paper-gate pass，不提升 |
| `HYPE-5M-Event-Quality-Scoring-Seeded-V0` | base / fixed-seed diagnostic | 使用 `HYPE-5M-Micro-Scalp` relaxed seeds，按 `0.70 cfg_mean + 0.20 style_mean + 0.10 side_mean` 打分，`q80` 交易 | `diagnostics/hype-5m-seeded-event-quality-v0-2026-06-27.md`，`diagnostics/hype-5m-seeded-event-quality-v0-ablation-2026-06-27.md` | 作为 Base 证据保留；不能作为 paper/live 候选 |
| `HYPE-5M-Event-Quality-Scoring-Seeded-V0.1-Style-Prune` | fixed-seed diagnostic | 在 Seeded V0 上精简事件源，优先移除弱贡献或高回撤 source | `diagnostics/hype-5m-seeded-event-quality-v01-style-prune-2026-06-27.md`，`diagnostics/hype-5m-seeded-event-quality-v01-full-ablation-2026-06-27.md` | `no_wick_no_breakout__cfg_side_88_12__q80` 为固定 seed-universe 全参数首位；只能作为后续严格 V2 搜索参考 |
| `HYPE-5M-Event-Quality-Scoring-Seeded-V1` | fixed-seed diagnostic / anti-leakage failed | 将 V0.1 全参数首位正式登记为 V1：`no_wick_no_breakout__cfg_side_88_12__q80` | `diagnostics/hype-5m-seeded-v1-live-feasibility-2026-06-27.md`，`diagnostics/hype-5m-seeded-v1-strict-seed-audit-2026-06-27.md` | strict seed-generation audit 失败；不再作为 audit lead，仅作为 selection-bias 证据保留 |

## Base: Seeded V0

Seeded V0 的标准口径：

- Seed source：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_relaxed_rounds_summary_2026-06-26.csv`
- Seed selection：仅用 `train_2025_05_30_to_2026_03_01` 指标选前 `100` 个 seed configs。
- Entry：闭合 K 信号，下一根 open 入场。
- Exit：固定 TP/SL，stop-first，open 穿越按 open 成交，超时按下一根 open。
- Cost：沿用 Binance 观测成本，entry slippage `10.73 bps`，fee `4.1466 bps/fill`，exit slippage `-2.64 bps`。
- Score：`0.70 * cfg_mean + 0.20 * style_mean + 0.10 * side_mean`。
- Baseline：`current_70_20_10__q80`。

固定 seed universe 过去一年分段回放：

- trades：`633`
- total return：`61.81%`
- PF：`1.128`
- average trade：`9.30 bps`
- max drawdown：`-26.94%`
- recent 3m return：`13.63%`
- negative active months：`6/13`

## 已知消融发现

打分公式 × 分位数门槛消融显示：

- 稳定性门槛排序首位仍是 `current_70_20_10__q80`。
- 全年收益最高为 `cfg_only__q60`（`179.93%`），但 recent-3m `-6.39%`，maxDD `-30.50%`，不作为替代基准。
- 收益很大程度来自 `cfg_name` 历史均值，`style` 和 `side` 更像辅助项。

按当前 Base 的 style 拆分，弱点集中在：

- `wick_reject`：交易最多但全年为负，是第一优先级精简对象。
- `micro_breakout`：样本很少，对整体贡献不足，适合先移除或降权。
- `trend_rsi_snapback`：在 Base 中为正，但在更严格门槛下不稳定，适合进入可选保留组。

## V0.1 Style-Prune

V0.1 固定 Seeded V0 的 score 公式 `0.70 cfg_mean + 0.20 style_mean + 0.10 side_mean`，只改变允许交易的事件源组合，并在每个测试月之前用该组合自己的训练事件重新计算分位数门槛。

当前精简首选：

- candidate：`no_wick_no_breakout__current_70_20_10__q80`
- allowed styles：`bb_revert`、`macd_flip`、`trend_rsi_snapback`、`vwap_revert`
- removed styles：`wick_reject`、`micro_breakout`
- trades：`545`
- total return：`238.78%`
- PF：`1.383`
- average trade：`24.05 bps`
- max drawdown：`-16.75%`
- recent 3m return：`25.33%`
- negative active months：`2/13`

全参数消融后，当前排序首位：

- candidate：`no_wick_no_breakout__cfg_side_88_12__q80`
- score：`0.875 cfg_mean + 0.125 side_mean`，移除 `style_mean`
- allowed styles：`bb_revert`、`macd_flip`、`trend_rsi_snapback`、`vwap_revert`
- trades：`549`
- total return：`287.61%`
- PF：`1.425`
- average trade：`26.33 bps`
- max drawdown：`-16.30%`
- recent 3m return：`24.59%`
- negative active months：`1/13`

全参数消融没有推翻精简方向：`no_wick_no_breakout` 在所有事件源集合中仍排名第一，`q80` 仍是最佳门槛。变化主要在 score 权重上：`cfg_side_88_12` 和 `cfg_only` 略强于原 `70/20/10`，说明 `style_mean` 在精简后不再贡献明显增益。

低回撤备选：

- candidate：`bb_vwap_only__current_70_20_10__q85`
- allowed styles：`bb_revert`、`vwap_revert`
- trades：`347`
- total return：`194.31%`
- PF：`1.489`
- average trade：`33.06 bps`
- max drawdown：`-10.79%`
- recent 3m return：`34.77%`
- negative active months：`1/13`

V0.1 的改善方向很明确：移除 `wick_reject` 和 `micro_breakout` 后，收益、PF、单笔均值、回撤和亏损月份均优于 Base。下一步不应直接推广到 live，而应围绕 V0.1 做 cost stress、seed audit 和 drawdown-control ablation。

## Seeded V1

V1 是 V0.1 全参数消融首位的正式命名版本：

- version：`HYPE-5M-Event-Quality-Scoring-Seeded-V1`
- candidate：`no_wick_no_breakout__cfg_side_88_12__q80`
- score：`0.875 cfg_mean + 0.125 side_mean`
- allowed styles：`bb_revert`、`macd_flip`、`trend_rsi_snapback`、`vwap_revert`
- removed styles：`wick_reject`、`micro_breakout`
- quantile：`q80`
- trades：`549`
- total return：`287.61%`
- PF：`1.425`
- average trade：`26.33 bps`
- max drawdown：`-16.30%`
- recent 90d return：`24.59%`
- recent 30d return：`46.29%`
- negative active months：`1/13`

Live feasibility audit conclusion:

- V1 曾可作为固定 seed-universe 的 research lead，但不能直接实盘，也不应直接 paper-live。
- 主要 blocker：seed-selection 前视、paper-runner 缺失、真实 entry fill 与 bracket 保护窗口未对账、stop-market/slippage 实测不足、restart recovery 和 kill switch 未实现。
- 成本压力：额外 roundtrip 成本 `10 bps` 后仍有 `124.08%` 收益和 `1.247` PF；`20 bps` 后收益降到 `29.47%`、PF `1.090`、DD `-29.74%`；`30 bps` 后变为负收益。

Strict seed-generation audit conclusion:

- script：`scripts/research_hype_5m_seeded_v1_strict_seed_audit.py`
- report：`diagnostics/hype-5m-seeded-v1-strict-seed-audit-2026-06-27.md`
- strict config universe：复用 relaxed-rounds 的固定随机生成器，但禁用 `seed_configs_from_previous()` 和历史 summary seeds；每轮 `2000` 个，共 `6000` 个无数据配置。
- rolling seed selection：每个测试月只用该月之前的数据筛 seed，再生成该月事件并应用 V1 的 `cfg_side_88_12 + q80`。
- OOS window：`2025-08-01` 到 `2026-06-26 04:20 UTC`，因数据从 `2025-05-30` 开始，先保留 `60` 天训练期。
- result：`493` 笔，`-61.16%` 收益，PF `0.843`，单笔 `-16.58 bps`，最大回撤 `-65.94%`。
- decision：strict audit 不支持 V1；固定 seed-universe V1 的 `287.61%` 收益大概率包含显著 config-universe selection bias。

## Live-Executable 边界

任何版本提升到 paper-live/live 之前，必须完成：

- seed-generation anti-leakage 审计必须先通过；V1 当前审计已失败。
- 成本压力测试与滑点放大。
- 逐笔路径复核，包括 stop-first、gap stop、timeout open。
- 订单维护审计：bracket 下单、撤单、重启恢复、缺失数据处理。
- paper/live-dry-run 对账。

在这些完成前，本家族所有收益数字都只能视为 research diagnostic。
