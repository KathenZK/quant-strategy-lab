# BIN-MTF-PTC Data / Split Contract（2026-08-03）

## 1. 统一数据 cutoff

- Binance USD-M perpetual closed `15m` cutoff：`2026-08-03 11:45:00 UTC`。
- BTC：2019-09-08 17:45 UTC 起；ETH：2019-11-27 07:45 UTC 起；HYPE：2025-05-30 10:30 UTC 起。
- 三资产 missing/duplicate/critical-null/OHLCV/raw-normalized blocker 均为 0；contract status 均为 `TRADING`。
- Funding 分别覆盖到 `2026-08-03 08:00 UTC`（HYPE 还包含 12:00 settlement）。

## 2. 已揭示边界

三资产全历史价格以及多条旧策略结果均已在过去研究中观察。以下 `locked_historical_evaluation` 只约束本 Goal 不使用其结果救参，不宣称 fresh OOS。

## 3. 冻结切分

### BTC / ETH

- development：上市起至 `2023-12-31 23:59:59 UTC`；
- validation：`2024-01-01 00:00:00` 至 `2025-06-30 23:59:59 UTC`；
- locked historical evaluation：`2025-07-01 00:00:00` 至 cutoff。

### HYPE

- development：上市起至 `2025-10-31 23:59:59 UTC`；
- validation：`2025-11-01 00:00:00` 至 `2026-02-28 23:59:59 UTC`；
- locked historical evaluation：`2026-03-01 00:00:00` 至 cutoff。

## 4. Purge / warmup

- 任何以未来 14d path 构造的 label 在 split 边界前 purge 14d；
- ATR/RMS/回归等历史特征可从前一区间提供只读 warmup，但不能携带 label、拟合状态或未来标准化统计；
- validation/locked evaluation 的 scaler/model 只能由其开始前数据拟合；
- campaign 跨 boundary 时，选择一种规则后全实验固定：默认不允许新 campaign 在 purge 段入场，已有 campaign 按真实路径走完但不进入后一段新开仓统计。

## 5. 使用权限

- development：特征、标签、时间周期和参数搜索；
- validation：选择机制/参数、停止搜索；允许多次查看但所有实验必须登记；
- locked historical evaluation：最终冻结候选只揭示一次；失败后不得同候选救参；
- prospective：最终候选冻结后另写 start/hash，未成熟前 outcome-blind。

HYPE 样本显著较短；即使数值达标，也可能因 campaign 数不足判为 `insufficient evidence`。

