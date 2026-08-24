# Binance 1D MA7 P2-E Ordered 1H MDD 修复合同

## 1. 修复原因

P2-E 搜索 engine 的订单、stop 和 funding 使用真实 `1h` 路径，但 `max_drawdown_pct` 在无 stop 日使用日 high/low，并统一按“先 favorable、后 adverse”更新 peak 与 trough。该值是保守的日内顺序上界，不是按可观测 `1h` 时间顺序计算的 MDD。

在 P2-E 前列 pairs 中，多组 ETH 参数的 MDD 精确为 `-32.381106%`，均由 `2020-03-12` profitable short 当天的日 low 先抬高 peak、再用同日 high 计算回撤导致。由于 direct `1h` 已冻结且无 blocker，本轮必须先修复评估口径，再裁决 `MDD<=20%`。

## 2. 不变项

- 不改变任何 signal、参数、交易、fill、stop、cost、funding、terminal equity 或 trade sequence；
- 不重新生成参数，不改变 seed，不新增 pair；
- 只使用 P2-E development 的固定 `60 long × 60 short = 3,600` pairs；
- researcher-exposed audit 与 prospective 继续封存。

## 3. Ordered 1H MDD 定义

对每笔已成交交易按冻结 direct `1h` 顺序重放账户权益：

1. entry 前权益从 engine 逐笔 `net_pnl/net_return` 锚定，并复核相邻交易连续性；
2. entry 后仓位按 exact target-quantity 方程重建，计 entry cost；
3. 每小时按 UTC `open -> favorable extreme -> adverse extreme -> close` 更新；该小时内部仍采用最保守顺序，因此不是乐观插值；
4. long favorable/adverse 为 high/low，short 为 low/high；
5. 实际 funding event 在事件 timestamp 前计入，使用冻结 `mark_price` 与 `funding_rate`；
6. protective-stop 的 exit hour 把 adverse 价格截断于实际 stop fill；非 stop 的 daily-open exit 不消费 exit hour；
7. 每笔 exit 后用 engine 报告的成本后权益锚定，复核 replay 与 engine 的 terminal equity；
8. 全账户 ordered peak-to-trough 的最小值为 `ordered_1h_mdd_pct`。

同时保留原 engine `conservative_daily_extrema_mdd_pct`，两者都披露；后者作为压力上界，不再代替真实顺序 MDD 硬门。

## 4. 固定审计范围

- 重放全部 `3,600` P2-E pairs 在 BTC、ETH 的 combined development 路径；
- 报告 ordered MDD、原 MDD、终值、交易数、MDD timestamp/side/trade；
- 用 ordered MDD 重新统计：
  - 两资产均 `ordered MDD>=-20%` 的 dd-safe pairs；
  - 两资产均 `equity>=20x` 且 ordered MDD safe 的 hard-target pairs。

## 5. 后续裁决

- 若 hard-target pairs 为 `0`，P2-E 仍失败；不得打开 audit；
- 若存在 hard-target pair，按原 P2-E Stage 4 的 stress/delay/calendar/rolling 门选择唯一 development candidate；
- ordered 修复只纠正 MDD，不允许按修复结果扩展参数池或更换 seed；
- 若许多 pairs 只因原保守 MDD被错误淘汰，但 `20x` 仍无命中，后续 materially new mechanism 可沿 ordered MDD 统一实现，不能回头把 P2-E 次优参数登记为 V2。

