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

## 2026-07-03：登记 ETH-1H-Adaptive-Regime-V1

- 首轮生成 `600,768` 组配置，可交易评估 `343,795` 组，prefit eligible `126,636` 组，prefit 硬门槛命中 `0`。
- prefit 冻结冠军为 `BB breakout long + RSI reversal both` ensemble；按用户要求登记为 `ETH-1H-Adaptive-Regime-V1`。
- V1 prefit `2.8109x / -16.29% / 71.57% / 102 trades`；locked OOS `0.5196x / -20.87% / 14.29% / 7 trades`；current full `2.2462x / -20.87% / 67.89% / 109 trades`。
- 独立复现入口 `scripts/eth_1h_ar_v1.py` 与首轮 summary 逐项一致。
- 状态为 `registered diagnostic baseline / NO-GO / not promoted / not live-ready`；不生成 live spec。
- 后续按用户要求对 V1 两腿全部字段槽做 one-at-a-time 全参数消融，删除不必要参数后再从 clean 参数面微调。

## 2026-07-03：V1 全参数消融与 clean-equivalent interface

- 两腿各 `39/39` 个 `StrategyConfig` 字段槽，共 `78/78`，coverage missing=`0`。
- 分类为 active tunable `33`、baseline-fixed remove `30`、neutral-fixed remove `3`、contract fixed `12`。
- 单字段同时满足 prefit 年化更高、回撤更小、胜率 `>=50%`、train/validation 同正且 validation DD<20% 的变体为 `15` 行。
- 删除或硬编码 `45` 个槽，建立 `33` 参数 clean interface；组件与 merged 交易签名和 V1 exact equal，指标完全一致。

## 2026-07-03：clean 参数微调仍为 NO-GO

- BB breakout / RSI 每腿各生成并评估 `150,001` 组，保留 `350 + 350`；组合评估 `122,500`，可评分 `75,020`。
- 相对 V1 prefit 收益更高、回撤更小、胜率在 `55%-85%`、train/validation 同正且 DD<20% 的组合观察为 `156`；其中通过 K+2 与 8 bps 全窗口 gate 为 `16`。
- 冻结 clean tuned observation：prefit `3.4333x / -15.02% / 73.33% / 105`，current full `2.6071x / -18.93% / 71.30% / 115`。
- 最近三个月 reused holdout 为 `0.4323x / -18.93% / 50.00% / 10`，总收益 `-18.86%`；收益失败。
- `66` 个 one-at-a-time / exposure 邻域中，`42` 个继续满足 prefit + K+2 改善，但 reused-holdout positive 为 `0`。月度 `23` 块中 `4` 块为负；10,000 次 bootstrap 的 5/50/95 年化为 `1.72x / 2.62x / 3.90x`，原始 `10x / >=50% / DD<20%` 形状命中率 `0%`。
- 不登记 V1.1/V2，不生成 live spec，状态保持 `NO-GO / not live-ready`。
