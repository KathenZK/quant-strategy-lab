# Binance 1D MA7 P2-G Entry-Information 归因合同

## 1. 研究问题

P2-F 显示 frontier 最大回撤通常发生在入场后前 `0.83–1.83d`，且事件前完整日线 close 的 MFE 中位数为 `0`；slow regime、vol-state 与 lifecycle 均未达到共享覆盖门。下一轮不再添加退出 overlay，而是检验 P0 已冻结且当时可观测的成交活跃度与 funding crowding，能否在 entry 前稳定区分早期方向错误。

本轮先做 label/feature attribution，不直接优化 PnL；只有特征通过预注册门，才另立有限 entry gate 合同。

## 2. 数据可用性

只使用 P0 已存在字段：

- daily/hourly `quote_volume`、`trade_count`；
- funding event 的 `funding_rate` 与 `mark_price`；
- MA7/ATR7 与 OHLC 仅用于 exact control、标准化及 outcome label。

BTC/ETH development 均有连续 `1h` klines；共同 funding 从 `2019-12-23 16:00 UTC` 起可用。P0 没有完整 OI、liquidation、order-book 或 taker-buy 历史，本轮禁止临时抓取、回填其它交易所或用当前快照伪造历史。

## 3. 冻结样本与标签

- exact sample：P2-F 的 `236` 个去重 frontier pairs；
- 每个 pair/asset 的每次实际 entry 构成一行；同一经济 entry 可因不同 pair 重复，但统计必须同时给出 pair-weighted 与 unique `(asset, side, entry_ts)` 两种口径；
- `EARLY_TAIL`：entry 后 `48h` 内、或更早实际 exit 前的真实 `1h` adverse excursion `<=-8%`；
- 次标签：`48h` return、最终净收益、是否为该账户 ordered MDD trade；
- 所有特征只截到 entry signal 所用的最后完整 UTC 日线及其之前已结算 funding event。

`8%` 只定义归因标签，不是 stop 或候选参数；不得根据结果改成其它阈值。

## 4. 固定特征

1. `QV20`：前一完整日 `quote_volume / trailing-20d median`；
2. `TC20`：前一完整日 `trade_count / trailing-20d median`；
3. `RVOL7`：过去 `7d` 日收益 realized volatility 相对 trailing `365d` percentile；
4. `FUND24`：entry 前已结算 `24h` funding sum；
5. `FUND7Z`：entry 前 `7d` funding sum 相对 trailing `180d` 的 z-score；
6. `CROWD7Z = side × FUND7Z`：正值代表持仓方向拥挤。

不加入 RSI、慢均线、未来 MFE、事件日未收盘量或 entry 后 funding。

计算细则在看结果前固定如下：

- `QV20/TC20` 的分子是 signal 可见的最后完整日，分母为截至该日、含该日的 trailing `20d` median；
- `RVOL7` 是截至最后完整日的 `7d` log-return 样本标准差，其 percentile 以截至该日、含当前值的 trailing `365d` 有效 RVOL7计算；
- funding 事件严格要求 `event_ts < entry_ts`；entry timestamp 同时刻或其后的事件不计；
- `FUND7Z` 当前值是 `[entry-7d, entry)` funding sum，基准为同一 UTC hour phase 下前 `180` 个逐日锚点的各自 trailing-7d sum，当前值不进入基准均值/标准差；
- pair-weighted `EARLY_TAIL` 只消费实际持仓至 `min(entry+48h, exit)` 的路径，并计实际 early exit fill；
- unique-entry 口径在每个 stratum 内按 `pair_rank` 最小者确定唯一代表，不按 outcome、exit 或特征择行；
- 主门使用 asset×stratum（合并 side）与 asset overall；asset×side×stratum只作结构诊断；
- AUC 门取 pair-weighted 与 unique-entry 两口径中离 `0.5` 更近者；effect 门也取两口径绝对值较小者，且两者必须同号。

## 5. 预注册归因门

每个特征分别计算 BTC/ETH、long/short、growth/risk/balanced 的：样本数、missing、EARLY_TAIL rate、rank-biserial effect、单变量 ROC-AUC、五分位 tail rate。特征进入下一轮必须：

1. BTC、ETH 的方向一致；
2. 每资产至少两个 strata 的 effect 绝对值 `>=0.15`；
3. pair-weighted 与 unique-entry 方向一致；
4. 每资产有效 unique entries `>=30`；
5. 最弱资产的单变量 `AUC>=0.58` 或 `<=0.42`；
6. calendar leave-one-year-out 至少 `70%` folds 方向一致。

若多个特征通过，优先保留缺失最少、最弱资产 AUC 最远离 `0.5` 的一个；`QV20` 与 `TC20` 若同时通过只保留较强者，避免共线堆叠。若无特征通过，关闭当前 P0 交易活跃度/funding 信息线，转向新的 price-path entry mechanism；不得组合多个 FAIL 特征。

## 6. 后续 PnL 边界

通过归因不等于候选。后续必须另立合同，使用预先固定的 expanding/rolling quantile gate，包含：

- exact P2-E control 与 OAT；
- BTC/ETH 共享规则、closed-bar/next-open、真实 ordered `1h` MDD；
- `1x`，禁止用风险缩放制造收益；
- development `>=20x` 且 `MDD<=20%` hard gate；
- stress、delay、calendar、rolling 通过后才允许一次性打开 researcher-exposed audit。

本轮状态固定为 `explore / not promoted / not live-ready`，不得登记 V2。
