# Artifacts — Binance-1D-Generic-MA7-Trend

本目录保存冻结 universe snapshot、数据质量审计、单币/组合/扰动 CSV、机器 JSON、图表与可交互交易路径。所有结果都属于 current-top30 retrospective diagnostic，不是 clean prospective OOS。

- `*_market_cap_snapshot.json`：CoinGecko 原始快照、筛选判断与响应 hash。
- `*_universe.csv` / `*_data_quality.csv`：30 个独立暴露、Binance 交集和逐币序列 hash。
- `*_per_asset_metrics.csv` / `*_long_short.csv`：gross/net/stress 与方向分解。
- `*_period_slices.csv` / `*_universe_period_summary.csv`：逐币及组合年、季度、recent slices。
- `*_portfolio_daily.csv` / `*_portfolio_loao.csv`：equal-risk 组合与 leave-one-asset-out。
- `*_perturbations.csv`：冻结 OAT ±20% 稳定性检查；不可选优。
- `*_summary.json`：机器可读总账；`.sha256` 为完整性 sidecar。
- `*_interactive_trade_paths.html`：22 币横截面 Sharpe 分布与逐币完整交易路径。
