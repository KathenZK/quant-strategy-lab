# ETH-1H-Adaptive-Regime Decision Log

## 2026-07-03：初始化独立 ETH 1h 家族

- 用户要求抓取 Binance `ETHUSDT` 永续最近两年全部 `1h` K，并尝试寻找年化权益倍率 `>=10x`、胜率 `>=50%`、最大回撤 `<20%`、可实盘的全新策略。
- 最后三个月固定为 locked OOS；参数生成、筛选、排序和组合构建不得读取该区间。
- 新建独立家族 `ETH-1H-Adaptive-Regime`（`ETH-1H-AR`），不把 ETH 结果登记为 BTC/HYPE family 的迁移版本。
- 在数据质量、盲测和 live-executable 审计完成前，状态固定为 `research in progress / not promoted / not live-ready`。

## 2026-07-03：两年数据质量通过

- Binance server time cutoff 为 `2026-07-03T05:58:56.977Z`；精确闭合 K 时间窗为 `2024-07-03T05:00:00Z` 至 `2026-07-03T04:00:00Z`，共 `17,520` 根。
- missing、duplicate、critical null、OHLCV violation、raw/normalized mismatch 和未闭合 K 误收均为 `0`。
- 历史资金费共 `2,190` 条；合约快照状态为 `TRADING / PERPETUAL`。
- 最近三个月 locked OOS 固定为 `2026-04-03T05:00:00Z` 至 `2026-07-03T05:00:00Z`。
