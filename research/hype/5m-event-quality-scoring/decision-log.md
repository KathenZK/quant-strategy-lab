# HYPE-5M-Event-Quality-Scoring 决策日志

## 2026-06-27 - 创建独立事件质量打分线

状态：`active diagnostic`

决策：

- 创建 `HYPE-5M-Event-Quality-Scoring` 作为新家族，而不是把工作放在 `HYPE-5M-Micro-Scalp` 或 `HYPE-5M-Pullback-Trail` 下。
- 将指标规则视为候选事件源，而不是最终策略。
- 在加入更重的机器学习依赖前，先从可解释的 walk-forward ranking model 开始。

原因：

- 既有 `1m` EMA-crossover 诊断显示，增加 exits 或迁移 strength filters 不能救回原始 cross-chasing。
- 既有 `5m` fixed-rule scalp 研究只有在放宽频率后才找到 audit candidates，因此下一个有用问题不是再找一个静态规则，而是能否选择事件质量。

V0 必需标准：

- 报告性能前，验证数据连续性、closed-bar 状态、OHLC 合法性，以及 raw vs normalized alignment。
- 只使用 closed-bar signals 和 next-open entries。
- 在训练标签和测试月份之间使用 purge window。
- 在本家族下保留 JSON/CSV artifacts 和 Markdown diagnostic。

## 2026-06-27 - Generic V0 no-go；seeded V0 audit candidate

状态：`audit candidate`

证据：

- Generic V0 report：
  `diagnostics/hype-5m-event-quality-v0-2026-06-27.md`
- Seeded V0 report：
  `diagnostics/hype-5m-seeded-event-quality-v0-2026-06-27.md`

决策：

- 不提升 generic multi-source event pool。它产生了 `252,277` 个 candidate events，但 paper-gate pass 为 `0`；排名最好的行在 OOS 仍为负。
- 仅将 `seeded_source_mean_q80` 保留为 audit candidate。

Seeded V0 摘要：

- Seed selection 使用 `HYPE-5M-Micro-Scalp` relaxed-rounds 配置，但仅按 `train_2025_05_30_to_2026_03_01` 指标筛选 seeds。
- OOS window 从 `2026-03-01 00:00:00+00:00` 开始。
- 最佳行 `seeded_source_mean_q80`：`184` 笔 OOS trades，`1.57` 笔/天，`28.89%` 1x return，`1.222` PF，`15.47 bps` average trade，`-15.38%` max drawdown，`27.18%` recent-30d return。

边界：

- 这不是 live-ready。config universe 继承自先前的 `HYPE-5M-Micro-Scalp` 研究，因此下一步必须是 anti-leakage seed-generation audit，加上 cost stress 和 paper-runner reconciliation。

## 2026-06-27 - Seeded V0 score/quantile ablation

状态：`audit candidate unchanged`

证据：

- Ablation report：
  `diagnostics/hype-5m-seeded-event-quality-v0-ablation-2026-06-27.md`
- Full-year segment diagnostic：
  `diagnostics/hype-5m-seeded-event-quality-v0-q80-full-year-segments-2026-06-27.md`

决策：

- 不要用全年收益最高的行替换 `current_70_20_10__q80`。
- 保留 `current_70_20_10__q80` 作为后续审计的均衡 audit 行，同时将高收益 `q50/q60` 行视为不稳定诊断。

发现：

- `current_70_20_10__q80`：`633` 笔 fixed-seed full-year replay trades，`61.81%` return，`1.128` PF，`9.30 bps` average trade，`-26.94%` max drawdown，`13.63%` recent-3m return，`6/13` 个 active months 为负。
- `cfg_only__q60`：全年收益最高，为 `179.93%`，PF `1.206`，average trade `14.32 bps`；但 recent-3m return 为 `-6.39%`，max drawdown 达到 `-30.50%`，因此未通过 stability gate。
- 消融显示，全年 edge 的大部分来自 `cfg_name` 历史均值；`style` 和 `side` 是次要项。这提高了任何 live 或 paper-live promotion 前进行 anti-leakage seed-generation audit 的必要性。

边界：

- 该消融是 fixed seed-universe retrospective diagnostic，不是 `2026-03-01` 前严格 anti-leakage OOS。seeds 仍然使用 `train_2025_05_30_to_2026_03_01` 指标筛选。

## 2026-06-27 - 创建主账并进行 Seeded V0.1 style-prune

状态：`audit candidate refined`

证据：

- Core ledger：
  `hype-5m-event-quality-scoring-core-ledger.md`
- Style-prune report：
  `diagnostics/hype-5m-seeded-event-quality-v01-style-prune-2026-06-27.md`

决策：

- 将 `HYPE-5M-Event-Quality-Scoring-Seeded-V0` / `current_70_20_10__q80` 视为 Base version。
- 将 `no_wick_no_breakout__q80` 提升为当前 refined diagnostic candidate，用于后续 audit。
- 保留 `bb_vwap_only__q85` 作为低回撤简化替代项。
- 不再继续把 `wick_reject` 和 `micro_breakout` 视为必需的 baseline event sources；除非后续 focused audit 证明受约束版本有用，否则它们应保持移除。

发现：

- Base `base_all__q80`：`633` 笔，`61.81%` full-year return，`1.128` PF，`9.30 bps` average trade，`-26.94%` max drawdown，`6/13` 个负收益月份。
- Refined `no_wick_no_breakout__q80`：`545` 笔，`238.78%` full-year return，`1.383` PF，`24.05 bps` average trade，`-16.75%` max drawdown，`25.33%` recent-3m return，`2/13` 个负收益月份。
- Lower-drawdown `bb_vwap_only__q85`：`347` 笔，`194.31%` full-year return，`1.489` PF，`33.06 bps` average trade，`-10.79%` max drawdown，`34.77%` recent-3m return，`1/13` 个负收益月份。

边界：

- 这些结果仍是 fixed seed-universe diagnostics，不是 `2026-03-01` 前严格 anti-leakage OOS。下一步必须是 seed audit、cost stress、drawdown-control ablation 和 paper-runner reconciliation。

## 2026-06-27 - Seeded V0.1 full parameter ablation

状态：`audit candidate refined`

证据：

- Full parameter ablation：
  `diagnostics/hype-5m-seeded-event-quality-v01-full-ablation-2026-06-27.md`

决策：

- 确认在更宽参数搜索下，`no_wick_no_breakout` 仍是最佳 event-source set。
- 保留 `no_wick_no_breakout__current_70_20_10__q80` 作为 Base-score V0.1 control。
- 将 `no_wick_no_breakout__cfg_side_88_12__q80` 提升为当前 V0.1 full-ablation lead，用于后续审计。
- 不要把 `style_only` 或 `side_only` 当作可用的简化模型；二者都未通过更严格的 stability gate。

发现：

- Full grid：`6` 个 style sets × `7` 个 score variants × `7` 个 quantile thresholds。
- Lead row `no_wick_no_breakout__cfg_side_88_12__q80`：`549` 笔，`287.61%` full-year return，`1.425` PF，`26.33 bps` average trade，`-16.30%` max drawdown，`24.59%` recent-3m return，`1/13` 个负收益月份。
- Base-score control `no_wick_no_breakout__current_70_20_10__q80`：`545` 笔，`238.78%` return，`1.383` PF，`24.05 bps` average trade，`-16.75%` max drawdown，`25.33%` recent-3m return，`2/13` 个负收益月份。
- Low-drawdown alternative `bb_vwap_only__current_70_20_10__q85`：`347` 笔，`194.31%` return，`1.489` PF，`33.06 bps` average trade，`-10.79%` max drawdown，`34.77%` recent-3m return。
- 最好的 score variants 是 `cfg_side_88_12` 和 `cfg_only`；style pruning 后移除 `style_mean` 会改善结果。这支持一个判断：策略仍主要由历史 config quality ranking 驱动，side 只是小的辅助项。

边界：

- 这仍是 fixed seed-universe diagnostic，不是 `2026-03-01` 前严格 anti-leakage OOS。在 seed audit、cost stress、drawdown-control ablation 和 paper-runner reconciliation 之前，不能提升。

## 2026-06-27 - 登记 Seeded V1 并阻止 live promotion

状态：`research lead / audit lead only`

证据：

- Live feasibility audit：
  `diagnostics/hype-5m-seeded-v1-live-feasibility-2026-06-27.md`

决策：

- 将 `no_wick_no_breakout__cfg_side_88_12__q80` 登记为 `HYPE-5M-Event-Quality-Scoring-Seeded-V1`。
- 不要将 V1 标记为 live-ready、paper-live-ready 或 dry-run handoff。
- 任何 live 或 paper-live promotion 之前，必须完成 seed-generation anti-leakage、paper-runner reconciliation、order-maintenance audit、cost/slippage stress、restart recovery 和 kill switch definition。

V1 摘要：

- Score：`0.875 * cfg_mean + 0.125 * side_mean`。
- Event styles：保留 `bb_revert`、`macd_flip`、`trend_rsi_snapback`、`vwap_revert`；移除 `wick_reject` 和 `micro_breakout`。
- Fixed seed-universe full-year replay：`549` 笔，`287.61%` return，`1.425` PF，`26.33 bps` average trade，`-16.30%` max drawdown。
- Recent 90d：`112` 笔，`24.59%` return，`1.303` PF，`-16.30%` max DD。
- Recent 30d：`51` 笔，`46.29%` return，`2.209` PF，`-5.24%` max DD。

实盘可行性阻塞项：

- Fixed seed universe 仍来自之前的 `HYPE-5M-Micro-Scalp` 搜索；严格 anti-leakage seed generation 尚未证明。
- Backtest entry 是 next-open 加观测滑点；K 线收盘后的 live latency 和真实 market-order fill 需要 paper-runner reconciliation。
- Backtest 假设入场后立即挂 TP/SL bracket；entry fill 和 bracket confirmation 之间的 live unprotected window 尚未审计。
- Stop-market behavior 在回测中是保守的，但真实 Binance trigger、slippage、reduce-only order handling、orphan-order cleanup 和 restart recovery 尚未审计。
- 额外 roundtrip cost stress：`10 bps` 仍有 `124.08%` return 和 `1.247` PF，但 `20 bps` 降至 `29.47%` return / `1.090` PF，`30 bps` 转负。Position-size slippage 未建模。

边界：

- V1 是强 research lead，不是可交易 deployment spec。

## 2026-06-27 - Seeded V1 strict seed-generation audit 失败

状态：`fixed-seed diagnostic / anti-leakage failed`

证据：

- Strict seed audit：
  `diagnostics/hype-5m-seeded-v1-strict-seed-audit-2026-06-27.md`
- Script：
  `scripts/research_hype_5m_seeded_v1_strict_seed_audit.py`

决策：

- 将 `HYPE-5M-Event-Quality-Scoring-Seeded-V1` 从 audit lead 下调为仅 fixed seed-universe diagnostic。
- 不要从 V1 继续推进 paper-runner reconciliation、paper-live、dry-run handoff 或 live deployment。
- 将此前 fixed seed-universe V1 结果视为很可能包含实质性 config-universe / seed-selection bias。

严格审计方法：

- 从 relaxed-rounds targeted random generator 生成固定 no-data config universe，但禁用 `seed_configs_from_previous()`，也不读取任何 historical summary seed list。
- 每个 relaxed round 使用 `2000` 个配置，共 `6000` 个配置，并限制在 V1 允许的 styles：`bb_revert`、`macd_flip`、`trend_rsi_snapback`、`vwap_revert`。
- 对每个测试月，只使用该月之前且扣除 `12h` purge window 的交易，选择最多 `100` 个 seed configs。
- 然后用选出的 seeds 生成该月事件，并以 V1 scorer `0.875 * cfg_mean + 0.125 * side_mean` 在 `q80` 交易。
- OOS 从 `2025-08-01` 开始，因为数据从 `2025-05-30` 开始，审计保留 `60` 天最低 seed-selection history。

发现：

- Strict audit result：`493` 笔，`-61.16%` return，`0.843` PF，`-16.58 bps` average trade，`-65.94%` max drawdown。
- 只有 `2025_08`、`2025_11` 和 `2026_03` 为正；大多数月份为负，包括 `2026_01` 的 `-32.35%`。
- 这与 fixed seed-universe V1 矛盾，后者为 `549` 笔、`287.61%` return、`1.425` PF、`-16.30%` max drawdown。

边界：

- 严格审计使用的是有界 `6000`-config universe，不是原始完整 `21000` relaxed-round 规模。扩展 strict universe 可以作为后续工作，但当前证据已经是 promotion blocker。
- 未来如果继续，应是新的 strict rolling-seed V2 search，而不是在 fixed-seed V1 上做参数调整。
