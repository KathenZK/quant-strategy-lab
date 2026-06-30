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
- `2026-06-29`：将最佳综合策略冻结为 `HYPE-15M-Multi-Indicator-Intraday-V1` 研究基线。V1 不是 promotion；状态为 `diagnostic baseline only / not live-ready`。
- `2026-06-29`：在标准 Binance HYPEUSDT perpetual `15m` raw/normalized 数据湖上重跑 V1 全参数消融。数据共 `37,607` 根闭合 K，gap/duplicate/null/OHLCV 错误和 raw/normalized 不一致均为 `0`。
- `2026-06-29`：修复旧模拟器的两处不可执行时序：timeout K 不能先看 high/low 再按 open 退出；盘中退出后不能回到同一根 K 的 open 重新入场。并补充 `MACD` 与 `ATR` 指标周期消融，共 `62` 行，完整 gate `0/62`。
- `2026-06-29`：按 Binance 成本 `0.1000% fee/fill + 0.0400% slippage/fill` 重算后，V1 可执行口径为年化 `18.66%`、最大回撤 `-31.84%`、胜率 `75.28%`、`0.919` 笔/天、PF `1.106`、Last90 年化 `-41.44%`。实盘审计结论 `NO-GO`：没有 runner、真实 stop-market/滑点证据、资金费、重启恢复、对账、missing-bar fail-closed 与 kill switch；禁止提升为 candidate、paper-live、dry-run、handoff 或 live。
- `2026-06-30`：根据 V1 消融删除 dormant 参数，并在干净参数空间重新演化 `7,926` 个唯一配置。K+1 领先诊断版 `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp120_sl450_hold16_x2` 达到年化 `323.57%`、回撤 `-18.67%`、胜率 `78.99%`、PF `1.925`、Last90 年化 `245.66%`，但交易频率只有 `0.608` 笔/天，且仍是同一样本二次优化。
- `2026-06-30`：K+2 延迟联合筛选对 `201` 个 risk-feasible 配置全部失败，联合通过 `0/201`。K+1 领先诊断版在 K+2 下退化为年化 `42.00%`、回撤 `-38.68%`、胜率 `74.79%`，因此不能视为稳健策略。
- `2026-06-30`：接受更大回撤后，样本内存在高收益高胜率诊断版本：`DD<=25%` 首位年化 `337.95%`、回撤 `-23.18%`、胜率 `80.71%`；`DD<=30%` 首位年化 `356.74%`、回撤 `-26.94%`、胜率 `86.71%`，但 Last90 仅 `0.63%`。这些版本只允许作为 aggressive diagnostic，不得提升为 candidate、paper-live、dry-run、handoff 或 live。
- `2026-06-30`：为了快速验证，新增频率/收益/回撤/胜率/Last90/K+2 综合排名。严格 `1-3` 笔/天版本没有形成高收益低回撤组合；综合第一是接近 `1` 笔/天的 `clean_rsi7_40_55_atrmin75_rvol0p75_h10_rsi14b0_tp120_sl320_hold32_x1`，K+1 年化 `97.07%`、回撤 `-20.13%`、胜率 `81.45%`，K+2 年化 `32.03%`。只可用于小额观察优先级，不是 promotion。
- `2026-06-30`：若放弃频率，在收益、回撤、胜率上更均衡的观察版本为 `clean_rsi7_40_60_atrmin105_rvol0_h10_rsi14b0_tp120_sl450_hold32_x2`。K+1 年化 `216.81%`、总收益 `244.44%`、回撤 `-15.65%`、胜率 `91.60%`；K+2 年化 `101.73%`、回撤 `-27.39%`。`3x` K+1 年化 `443.62%`，但 K+2 回撤 `-39.22%`、最差单笔 `-14.34%`，因此只作为 aggressive diagnostic，不作为小额实盘起步版本。

## 证据政策

- 优先使用本家族 README、持久 Markdown 报告和 artifacts，而不是 scratch outputs。
- 顶层 `reports/` 已退役，不是本家族的 durable evidence。
- 负面发现应写在这里或持久 diagnostic note 中，而不是被后续参数搜索掩盖。
