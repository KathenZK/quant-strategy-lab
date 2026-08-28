# NDX100-1D-MA7-RC-P0 冻结研究合同

冻结时间：2026-08-24 UTC  
Study ID：`NDX100-1D-MA7-RC-P0`  
配置真源：[`../configs/ndx100-1d-ma7-regime-continuation-p0.json`](../configs/ndx100-1d-ma7-regime-continuation-p0.json)

## 1. 研究问题与裁决边界

唯一问题是：historical Nasdaq-100 中，MA7 收盘跨越后的 1–40 个交易日方向收益，是否随 Slope / ER / RV regime 呈稳定、平滑、可解释的分离，并与 Binance USDT-M 日 K 研究方向一致。

这不是盈利策略搜索，不做止盈止损、仓位、成本后权益曲线或 promotion。观察到正 expectancy 也只允许形成 `explore / diagnostic-only / not promoted / not live-ready` 结论。

## 2. 数据与 point-in-time universe

- 区间：`2010-01-01` 至冻结时最新完整 XNAS session `2026-08-21`；实际首交易日为 `2010-01-04`。
- 交易日：`exchange-calendars` 的 XNAS regular sessions。
- Universe：每个 session 当日的 historical Nasdaq-100 securities；不得使用 2026 成分向过去回填。
- 成分事件：完整索引使用 revision-pinned historical component table，并保留每行引用与 `primary_official / secondary_cited / uncited_secondary_index` 层级；公司行动由 Nasdaq、NasdaqTrader、SEC 或发行人原始公告修正。
- 价格：只接受 Massive（原 Polygon）adjusted daily aggregates；原始 task cache 不直接成为 trusted data lake。
- 标识：每个 membership interval 的首尾日期查询 ticker details；按 composite/share-class FIGI 检查 rename 与 same-symbol generation；ticker-events entitlement 失败即阻塞结果。
- 收益口径：split-adjusted price return，不含 dividend 与 delisting return。该限制必须随任何结果披露。
- 缺失：feature 或 forward window 内缺一交易日即从该窗口排除；禁止补零。

## 3. 事件与 forward returns

- 主事件 `MA7`：
  - long：`Close[t-1] <= SMA7[t-1]` 且 `Close[t] > SMA7[t]`；
  - short：`Close[t-1] >= SMA7[t-1]` 且 `Close[t] < SMA7[t]`。
- 事件价：`Close[t]`；无止盈止损。
- Horizons：`1/3/5/10/20/40` 个同一 entity 连续 XNAS sessions。
- Long raw：`Close[t+h] / Close[t] - 1`；short raw：`1 - Close[t+h] / Close[t]`。
- ATR return：`direction * (Close[t+h] - Close[t]) / ATR14[t]`。
- MA5/MA10 只复用 MA7 已冻结的 regime edges 做邻域 robustness。

## 4. Regime 与分桶

MA7 不进入 regime。第一版只有：

1. `Normalized Slope = (SMA30[t] - SMA30[t-1]) / ATR14[t]`；
2. `ER20 = abs(Close[t]-Close[t-20]) / sum(abs(diff(Close)), 20 sessions)`；
3. `RV20 = std(log return, ddof=1, 20 sessions) * sqrt(252)`，再取该 security 最近 252 个 RV20 观察中当前值的 percentile。

Slope/ER edges 由全部 eligible point-in-time member sessions pooled quintiles 冻结，不读取事件结果；RV percentile 使用固定 `[0,.2,.4,.6,.8,1]`。禁止阈值搜索。

## 5. 统计与 robustness

- long/short 分开；raw/ATR return 分开。
- 输出三个单变量 quintiles 与 `5×5×5=125` 三变量组合。
- 每格输出样本、证券数、事件日数、均值、中位数、胜率、security/date 双向聚类 SE/t-stat/95% CI/p-value。
- 三变量在每个 `direction × horizon × return_metric` 内做 Benjamini-Hochberg FDR；可靠格要求 `n>=100`、`securities>=10`、`dates>=30`。
- Robustness：calendar year、QQQ bull/bear/transition、当日 trailing-dollar-volume Top20/other、当前成分任期 `<252/>=252` sessions、MA5/7/10、2020 前后组合 surface rank correlation。
- Gap：记录 `(Open[t]-Close[t-1])/Close[t-1]`；主结果不筛选。完成主结果后，固定比较 `abs(gap)<1%/2%/3%`，只作诊断。

## 6. Cross-market 输出

读取 Binance 家族既有单变量和三变量 CSV，按冻结 key 合并为 long format，并生成包含 `crypto_long / crypto_short / nasdaq100_long / nasdaq100_short` 指标列的 wide table。任何一侧缺失时只写 blocker JSON，不写占位统计值。

同时输出 common-event-date-window 诊断：用 Binance 冻结 event artifact 的首末事件日截取股票事件，双方都复用各自已经冻结的 regime bins，不根据交集期重估 edges。native full-history 与共同窗口必须分开，避免把 2010 起股票历史与 2020 起 crypto 历史伪装成同一时间样本。

## 7. 接受条件

只有下列条件全通过才允许生成股票统计结果：credential/entitlement、interval ticker details、FIGI/ticker-events lineage、OHLCV/XNAS session、重复键、连续 forward window。任何 blocker 都 fail closed，并保留可恢复命令。
