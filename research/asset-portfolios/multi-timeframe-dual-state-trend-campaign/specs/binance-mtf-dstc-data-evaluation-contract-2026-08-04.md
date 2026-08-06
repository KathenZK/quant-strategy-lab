# BIN-MTF-DSTC 数据与评估合同

## 1. 数据冻结

- 市场：Binance USD-M perpetual；HYPEUSDT、BTCUSDT、ETHUSDT。
- BTC/ETH 搜索与 historical audit 的 closed `15m` cutoff：`2026-08-03 11:45:00 UTC`。
- HYPE 的 closed `15m` cutoff：`2026-08-01 15:15:00 UTC`；数据加载器必须在查询层截断，禁止把更晚行读入本 Goal 的内存、缓存或产物。
- 原始来源、normalized/raw parity、连续性、重复、关键空值、OHLCV、funding、contract status 必须重新审计；旧审计只作对照。
- `1h/4h/1d` 由连续完整 `15m` 聚合；任何源 K 数不足的高周期 bar 排除。
- `HYPE-15M-MTPP [2026-08-02, 2026-11-02)` prospective 不读取，不用于本 Goal 搜索、排名或回测；本家族不能以“独立家族”为由穿透这条更早存在的 outcome-blind 边界。

## 2. 证据身份

三资产价格和多条历史策略结果均已被研究者查看；本 Goal 的历史结果只能称 causal walk-forward / historical audit。

Fresh prospective 固定从 `2026-08-05 00:00:00 UTC` 起；在最终候选和代码 hash 冻结前到达的新数据保持未读取。Prospective 至少 180 天且 30 个 closed campaigns 才能提供 promotion 证据。

## 3. 搜索分区

### BTC / ETH

- development：上市起至 `2023-12-31 23:59:59 UTC`；
- mechanism validation：`2024-01-01` 至 `2025-06-30 23:59:59 UTC`；
- historical final audit：`2025-07-01` 至该资产 cutoff，只允许最终冻结候选运行一次。

### HYPE

- development：上市起至 `2025-10-31 23:59:59 UTC`；
- mechanism validation：`2025-11-01` 至 `2026-02-28 23:59:59 UTC`；
- researcher-exposed audit：`2026-03-01` 至 `2026-08-01 15:15:00 UTC`；不能作为 final locked OOS，也不能授权 promotion。

## 4. Walk-forward 与 purge

- development 内至少五个 expanding/rolling folds；HYPE 事件不足时如实标记，不复制重叠日锚充样本。
- 使用未来 30d path 的任何标签在边界前 purge 30d；仅历史特征可提供只读 warmup。
- 跨边界 Campaign 按真实路径走完，但不得计入后一区间的新开仓样本。
- validation 可用于阶段选择但所有 experiment 必须登记；historical final audit 一次揭示后禁止同机制救参。

## 5. 成本与成交

- fee：`0.001/fill`；base adverse slippage `4bps/fill`；stress `8bps/12bps`。
- actual funding；每层 entry/add/trim/exit/retry 分别计费。
- closed decision bar 后下一根 `15m open`；stop-market gap 使用更差 open。
- 同 bar high/low 顺序未知时采用保守顺序；禁止用 high 获得资格后再假设更早的 low 成交。
- tick/step/min-notional/precision 在 candidate 进入 final audit 前强制加入。

## 6. 账户与门禁

- 真实 quantity/lot/equity ledger；逐 15m liquidation equity 和 bar 内不利极值 MDD。
- 计划风险、实际 stop-out risk、fill leverage、effective leverage 分开记录。
- 初始总计划风险 1%；机制通过后才机械比较 1.5%/2%/3%。
- candidate 最低门禁：annual equity multiple `>=2x`、MDD `<=20%`、PF `>=1.3`、effective leverage `<=3x`、base/stress 稳定、无执行/数据 blocker。
- `5x` 为 Tier S、`20x` 为 Stretch；不能通过提高杠杆替代 alpha。
