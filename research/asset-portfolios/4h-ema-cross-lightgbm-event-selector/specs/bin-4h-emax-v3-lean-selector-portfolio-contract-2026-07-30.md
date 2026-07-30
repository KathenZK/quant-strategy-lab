# BIN-4H-EMAX V3 精简选择器组合级立项契约（2026-07-30）

状态：契约冻结于运行前。本契约把 [local+trend 精简选择器](bin-4h-emax-local-trend-selector-contract-2026-07-29.md)（事件级门 B 已通过，top decile 净 +0.367 ATR、4/4 年为正）推进到组合级判定：在真实资金约束下，打分过滤能否把 P2 对照组暴露出的回撤红线问题压回可接受范围。

## 1. 立项对象与版本命名

- 候选版本：`Binance-4H-EMA-Cross-LightGBM-Event-Selector V3`（V3 = local+trend 精简特征双边选择器；V1 = 裸信号基线概念、V2 = 市场状态打分层，两者均未登记）。
- 家族此前状态为 `archived`；本立项基于 2026-07-29 产生的新证据（事件级门 B 首次通过）重开研究线，重开与判决均记入 [decision-log.md](../decision-log.md)。
- 判决规则（预注册）：主变体 S2 通过全部 kill gate → 登记 `V3`（`registered / not promoted / not live-ready`）并新建家族主账；任一 gate 失败 → 不登记版本，家族状态写 `explore / not promoted / not live-ready` 并落档死因。

## 2. 冻结输入（不重新训练、不加特征、不调参）

- 事件表：`artifacts/events_dev_4h.parquet`（majors 修复后版本），`in_trading_pool == True`，双边（金叉多 + 死叉空）。
- 分数：`artifacts/local_trend_selector/oof_scores_local_trend.parquet` 的 `score_local_trend`，按 `(sym_key, entry_ts, side)` 合并。OOF 协议为逐年 expanding window（purge 17 天、聚簇加权），每个 2022–2025 事件的分数都来自只见过既往年份的模型，与实盘"用截至上年的模型打分"时序一致。
- 回测窗口：`entry_ts ∈ [2022-01-01, dev 末端]`（2020–2021 无 OOF 分数，仅作训练年）；`2026-01`–`2026-06` 对本家族是污染 holdout，不进入本回测。
- Bracket：`b4_2`（TP 4 ATR / SL 2 ATR / 96 根超时）；成本已含在 `b4_2_net_frac` 内（fee 0.001 + slip 4 bps 每边 + as-of funding）。

## 3. 变体（预注册，禁止事后新增阈值）

| 变体 | 规则 | 角色 |
| --- | --- | --- |
| B0 | 窗口内全部池内双边事件，不过滤 | 对照组 |
| S1 | `score_local_trend > 0` | 稳健性参考（绝对阈值） |
| S2（主变体） | `score` > 过去 365 天（不含同刻）已评分事件分数的 90 分位；trailing 样本 < 200 时不交易 | 对应事件级 top-decile 证据的因果化规则 |

S2 阈值只使用历史分数，实盘可复现（对每个池内交叉打分并保留分数历史即可）。

## 4. 组合约束（逐字沿用 [P2 组合契约](bin-4h-emax-portfolio-contract-2026-07-24.md)）

初始资金 100,000；单笔风险 0.5%（名义 = equity×0.005/(2×atr_frac)，上限 10% equity）；最多 20 个并发持仓；总名义 ≤ 2× equity；同币互斥（不分方向）；PnL 在退出时实现、资金在退出 K 线结束（exit_ts+4h）释放。

## 5. Kill gates（预注册，对主变体 S2 判定）

- G1 回撤红线：max drawdown ≥ 40% → kill（沿用家族 P2 红线）。
- G2 年度稳健：2022–2025 中 ≥3 年组合年收益 > 0，且（总 PnL 为正时）无单年 PnL 占比 > 60%。
- G3 绝对收益：窗口总收益 > 0。
- G4 打分层增值：S2 的 max drawdown 严格小于 B0，且 S2 的 总收益/|maxDD| 严格大于 B0（打分层必须在组合级证明自己，否则裸信号即可）。

审计义务（不作为选择依据）：月度收益、最差 5 个月、多空分解、并发与 skip 统计、最近 `1d/7d/1m/3m/6m/1y` 分片（锚定数据末端）。

## 6. 边界

- 本契约不训练新模型、不改特征、不做阈值搜索；S1 结果无论好坏不改变 S2 判决。
- 生产模型（全 dev 数据训练）、2026H1 holdout 揭盲与 runner 交接属于后续独立契约，须在 V3 登记之后另行冻结。
