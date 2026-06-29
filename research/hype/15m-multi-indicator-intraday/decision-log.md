# HYPE-15M-MII 决策日志

这是 Binance HYPEUSDT `15m` multi-indicator intraday 研究的家族级阅读路径。

## 当前边界

- 这是一个新的探索性研究家族，不是已提升的 live strategy。
- 它之所以单独存在，是因为本次搜索允许广泛的指标组合，而不是纯 EMA crossover、trend-breakout 或 candle-count 规则。
- 任何 candidate 都必须在完成 live-realistic order timing、stop/target 可行性、费用、滑点、时间切片稳定性、以及重启/state-machine 可复现性检查后再判断。

## 决策

- `2026-06-25`：创建独立家族 `HYPE-15M-Multi-Indicator-Intraday`（`HYPE-15M-MII`），而不是挤入既有 `15m` EMA 或 candle-count 家族。
- `2026-06-25`：首次广泛的 Binance HYPEUSDT `15m` multi-indicator intraday 搜索结果为负。最佳组合 candidate 达到 `+141.92%` 年收益、`-18.88%` 最大回撤、`76.90%` 胜率和 `0.94` 笔/天，但未达到 `>= 2000%` 年收益目标，并且在最近 `90d` 退化为年化 `-5.26%`。不提升。
- `2026-06-26`：全参数消融和扩展时间切片回测确认了相同的负面边界。baseline 可以精确复现，但 `0/55` 个 baseline/variant 行满足完整 gate；唯一年化更高的行不是突破回撤，就是未通过近期稳定性，或降低了频率。对 `data/cache/hypeusdt_15m_fapi.csv` 的数据质量检查没有发现 gaps/duplicates/OHLC errors，但输入仍只是 cache-only，并缺少 `quote_volume/trade_count/vwap/source/is_closed`，因此不是可用于标准数据湖 promotion 的数据集。不提升。
- `2026-06-26`：组合 surface-improvement 消融参数没有得到优化策略。网格评估了 `594` 个非 baseline 组合；`0` 个组合同时实现更高年化收益、不更差最大回撤，并通过 trade-shape 与 recent-stability gate。最高收益组合把年化收益提高到 `+174.81%`，但最大回撤恶化到 `-23.24%`；最佳折中达到 `+153.01%`、最大回撤 `-19.94%`。不提升；不要把更高杠杆或扩大 TP 当作优化。

## 证据政策

- 优先使用本家族 README、持久 Markdown 报告和 artifacts，而不是 scratch outputs。
- 顶层 `reports/` 已退役，不是本家族的 durable evidence。
- 负面发现应写在这里或持久 diagnostic note 中，而不是被后续参数搜索掩盖。
