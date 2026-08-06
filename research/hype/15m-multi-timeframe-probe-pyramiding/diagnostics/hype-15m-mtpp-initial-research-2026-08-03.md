# HYPE-15M-MTPP 交易员式试单—确认—滚仓初始研究（2026-08-03）

## 结论

这次不是又把趋势预测模型换成一组指标。研究逻辑已按用户描述改成：**日周只提出可能方向，低周期只找位置，小仓试错，只有真实浮盈和新回踩恢复共同出现才加仓，普通指标变弱不退出。**

结果分成两层：

1. **完整冻结方案 `trader_full` 失败，Long/Short 和 `1%/3%/10%` 风险全部净亏，零成本也全部亏。** 当前 `1R` 后的六根 `4h` 结构 stop 与 `2R` 后半 MFE 保护把持仓重新压到约 `27–31h`，并产生反复试单。
2. **“试仓 + 真实盈利确认 + 回踩恢复加仓”本身出现 Short 局部正线索。** 删除动态 stop、只保留原始结构 stop 的 `timed_pyramid`，Short 在 `1%/3%` 风险下为 `+5.37%/+13.87%`，平均持有 `101.9h`；但只有 `23` 个 campaign、五段中 `3/5` 为正，配对事件增量的 95% 区间仍跨零，不能登记或 promotion。

因此本轮不是“交易员思路被否定”，而是更具体地定位到：**入场假设 Long 无 edge；Short 的盈利确认滚仓值得新样本验证；当前频繁上移 stop 明确有害；把账户风险提到 10% 不会减少 stop 次数，只会放大亏损与回撤。**

## 数据、时序与证据身份

- Binance USD-M `HYPEUSDT` perpetual：`41,108` 根闭合 `15m`，`2025-05-30 10:30` 至 `2026-08-01 15:15 UTC`。
- 缺失 `15m`、重复、关键空值、无效 OHLCV 均为 `0`；raw/normalized 八字段完全一致；funding `2,568` 行且无空值。
- 聚合得到完整 `1h 10,276`、`4h 2,568`、`1d 427`、Monday-UTC `1w 60` 根；不完整首尾 bin 排除。
- 所有高周期特征在完整 bar 结束后才可见，动作最早在下一根 `15m open`；stop gap 按更差 open。
- 周期锚点在首轮执行中发现 `7D origin` 未生效后，改成语义等价且明确生效的 `168h + Monday UTC origin`，未改变任何交易阈值；本报告只使用修正后重跑。
- HYPE 历史已被相邻研究看过，全部结果只称 historical causal diagnostic。`[2026-08-02,2026-11-02 UTC)` prospective OOS 未读取。

## 冻结政策

共同入场是完整日/周同向、`4h RSI14` 同向、`1h RSI/KDJ` 处在中间回踩区、`15m KDJ` 恢复交叉；原始 stop 位于最近六根完整 `4h` 结构低/高点外 `0.25%`，最小价格距离 `1.5%`、最大 `15%`。

| policy | 仓位与保护 |
| --- | --- |
| `static_seed` | 全程固定计划 quantity 的 `25%`，原始 stop |
| `static_full` | 入场即 `100%`，原始 stop |
| `profit_step` | MFE 达 `0.5/1/2R` 后逐级 `25/50/75/100%`，原始 stop |
| `timed_pyramid` | 同样的 MFE 门槛，但必须等待新低周期回踩恢复才加，原始 stop |
| `trader_full` | `timed_pyramid` 加 `1R` 后六根 `4h` 结构收紧和 `2R` 后半 MFE 保护 |

每个风险预算只改变计划 quantity，不改变入场、价格 stop 或 MFE 门槛；`3x` 始终是上限而不是目标。

## 1% 风险下的模块对照

| 方向 | policy | net | Sharpe | MDD | campaigns | win | avg hold | adds |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Long | static seed | `-4.48%` | `-1.35` | `-5.96%` | 29 | `10.3%` | `90.2h` | 0 |
| Long | static full | `-16.88%` | `-1.34` | `-21.76%` | 29 | `10.3%` | `90.2h` | 0 |
| Long | profit step | `-16.77%` | `-1.50` | `-20.00%` | 29 | `10.3%` | `90.2h` | 41 |
| Long | timed pyramid | `-17.24%` | `-1.75` | `-19.37%` | 29 | `6.9%` | `90.2h` | 35 |
| Long | trader full | `-4.08%` | `-0.99` | `-7.36%` | 66 | `28.8%` | `27.0h` | 32 |
| Short | static seed | `+0.32%` | `+0.10` | `-4.62%` | 23 | `17.4%` | `101.9h` | 0 |
| Short | static full | `+0.71%` | `+0.11` | `-16.87%` | 23 | `17.4%` | `101.9h` | 0 |
| Short | profit step | `+3.44%` | `+0.30` | `-11.97%` | 23 | `17.4%` | `101.9h` | 30 |
| Short | timed pyramid | `+5.37%` | `+0.46` | `-10.89%` | 23 | `17.4%` | `101.9h` | 23 |
| Short | trader full | `-5.61%` | `-1.82` | `-6.93%` | 51 | `17.6%` | `30.6h` | 27 |

Long 从固定种子仓开始就为负，因此滚仓只能放大错误方向假设。Short 则呈现 seed → profit step → timed pyramid 的历史递增，但完整动态 stop 把它反转成亏损。

## 为什么动态 stop 破坏持有

- 不移动 stop 时，Long/Short 分别只有 `29/23` 个 campaign，平均持有 `90.2/101.9h`，已经进入用户想要的数日尺度。
- `trader_full` 变成 `66/51` 个 campaign，平均持有仅 `27.0/30.6h`；Long `66/66`、Short `50/51` 由 intrabar stop 退出。
- 达到 `2R` 的 `trader_full` Long/Short 分别有 `16/7` 个，说明并非完全没有趋势；但 `1R` 后立即切换到最近六根 `4h` 结构 stop，使大量尚未成熟的行情提前结束，随后新触发又重新试单。
- 这与前一轮概率退出的失败形式相同：退出控制再次把数日 campaign 压成约一天，只是这次触发源从概率翻动变成过紧的结构 stop。

## 1% / 3% / 10% 风险验证

### 完整 `trader_full`

| 方向 | risk | gross | base | 8bps stress | MDD | campaigns / avg hold | max effective leverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Long | 1% | `-2.03%` | `-4.08%` | `-4.48%` | `-7.36%` | `66 / 27.0h` | `0.30x` |
| Long | 3% | `-6.30%` | `-12.03%` | `-13.10%` | `-20.53%` | `66 / 27.0h` | `0.86x` |
| Long | 10% | `-16.74%` | `-30.81%` | `-33.65%` | `-49.48%` | `66 / 27.0h` | `2.31x` |
| Short | 1% | `-4.62%` | `-5.61%` | `-6.48%` | `-6.93%` | `51 / 30.6h` | `0.26x` |
| Short | 3% | `-13.47%` | `-16.09%` | `-18.34%` | `-19.52%` | `51 / 30.6h` | `0.79x` |
| Short | 10% | `-38.15%` | `-42.61%` | `-45.96%` | `-46.91%` | `51 / 30.6h` | `1.90x` |

同一政策在三档风险下的 campaign 数、stop 时刻和持有时间相同；这直接验证了 **1% 不会更容易被打 stop**。风险提高只增大 quantity。完整政策零成本仍负，因此不是 fee/slippage 制造失败。

`10%` 还暴露出更严重的控制问题：`static_full` Long/Short 的持仓途中有效杠杆达到 `3.19x/3.26x`；Short `timed_pyramid` 达 `3.05x`。即使 fill target 不超过 `3x`，权益和价格移动也会造成 effective leverage 漂移。`10%` 不可采用。

### Short 局部线索的风险梯度

| risk | timed pyramid net | Sharpe | MDD | effective leverage |
| ---: | ---: | ---: | ---: | ---: |
| 1% | `+5.37%` | `+0.46` | `-10.89%` | `0.55x` |
| 3% | `+13.87%` | `+0.51` | `-27.52%` | `1.69x` |
| 10% | `-0.87%` | `+0.33` | `-56.44%` | `3.05x`（breach） |

`3%` 虽然收益放大，但 `27.5%` MDD 已明显超过风险收益可接受线；`10%` 因复利路径、成本与 leverage cap 不再线性，收益转负且风险失控。

## 稳定性与同入口归因

- 五个连续时间块中，Long `trader_full` 只有 `1/5` 为正；Short `0/5` 为正。完整方案无时间稳定性。
- Short `timed_pyramid` 在 `1%/3%` 下均为 `3/5` 正，但收益集中：`1%` 五段约为 `-2.21%、+3.24%、+6.58%、-1.59%、+0.47%`；尚不是均匀 edge。
- 对相隔至少 `24h` 的相同入口做配对事件研究：Long `72` 个事件/`18` 个独立 14 日块，Short `65/21`。
- Short `timed_pyramid-profit_step` 平均增量 `+0.140pp/event`，14 日 block-bootstrap 95% CI `[-0.138,+0.433]pp`；区间跨零。
- Short `trader_full-timed_pyramid` 平均 `-0.166pp/event`，CI `[-1.408,+0.816]pp`；方向偏负但仍被少数右尾事件影响。
- Long 所有配对模块增量区间也跨零；中位增量均为 `0`，因为不少 campaign 未达到加仓或动态保护门槛。

最近 `1d/7d/1m/3m/6m/1y` 已按数据末端审计但不用于选择。近期个别 Short 盈利窗口不能推翻全历史、分块与配对门禁。

## 门禁判定

| gate | Long | Short |
| --- | --- | --- |
| `trader_full` base/stress 正收益 | FAIL | FAIL |
| 平均持有至少 24h | PASS（27.0h） | PASS（30.6h） |
| 相对 seed 与 timed policy 有稳定净增量 | FAIL | FAIL |
| 五块不过度依赖单一阶段 | FAIL（1/5） | FAIL（0/5） |
| 3x fill/effective leverage clean | PASS | PASS（完整政策；10% 对照其他 arm 有 breach） |
| historical mechanism support | **FALSE** | **FALSE** |

## 决策与下一步

1. `HYPE-15M-MTPP` 保持 `explore / diagnostic-only / not promoted / not live-ready`，不创建 `V1`。
2. 当前 `1R` 后六根 `4h` 动态结构 stop 明确淘汰；不能再把“不断调整止损”机械翻译成高频收紧。真正需要的是**少调整、只保护不可接受回吐**。
3. 账户风险不提高到 `10%`。本轮证据支持先把风险约束在 `1%`；`3%` 仅可作为研究压力档，不是可交易建议。
4. Short `timed_pyramid` 只保留为 successor 假设：小仓试错、浮盈确认、回踩恢复加仓、原始宽 stop、不做 `1R` 结构追踪；它没有通过事件 CI 和阶段稳定性，不能从已揭示 HYPE 历史继续调参救活。
5. 下一次可信验证应把相同冻结控制器独立放到更长历史的 BTC/ETH/SOL，Long/Short 分开，或等待 HYPE prospective OOS；不得在本历史上继续改变 RSI/KDJ、MFE 门槛或 stop 频率后选择最好结果。

## 证据

- [冻结合同](../specs/hype-15m-mtpp-initial-research-contract-2026-08-03.md)
- [机器主结果](../artifacts/hype_15m_mtpp_research_2026-08-03.json)
- [政策指标](../artifacts/hype_15m_mtpp_policy_metrics_2026-08-03.csv)
- [五段稳定性](../artifacts/hype_15m_mtpp_contiguous_blocks_2026-08-03.csv)
- Long / Short [配对事件](../artifacts/hype_15m_mtpp_long_paired_events_2026-08-03.csv) · [Short 配对事件](../artifacts/hype_15m_mtpp_short_paired_events_2026-08-03.csv)
- [复现脚本](../scripts/research_hype_15m_mtpp.py)
