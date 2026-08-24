# V6 延迟趋势 episode 确认研究：Development hard-gate 失败

## 裁决

- 唯一 control 是已登记的 `HYPE-1D-MA7-Asymmetric-Body-Trend-V6`，即固定 OAPP `0.5ATR / 10% / 2d + RSI6 20×2` 之上的 `PEHC_294`。本轮没有回到 V4，也没有改写 V6。
- 本轮只研究一个简单问题：严格 raw MA7 cross 已发生、但 V6 当日没有自然入场或 PEHC handoff 时，若价格继续位于 MA7 同侧，是否可用连续同侧天数、累计 MA7 slope、距 MA7 的 anti-chase 上限和 episode 有效期补入慢涨/阴跌。
- 已完成 `576` 个 long-only、`576` 个 short-only 和 `16` 个多空组合，共 `1,168` 个冻结配置；全部无运行错误。Development 多空组合 `0/16` 通过，`champion=null`。
- 最终状态为 `HARD-GATE-FAILED / explore / not promoted / not live-ready`。评估区 `[324,432)` 保持未访问；没有 V7、没有杠杆研究、没有交易路径 HTML、没有 runner 交接。

## 冻结方法

- 预注册在读取任何 DTEC 绩效前改为 exact V6 唯一 control，并固定 D=`[0,324)`、六个 `54d` cold-flat blocks、评估=`[324,432)`。
- 每一侧网格为：`persistence={2,3,4,5}`、`slope_lookback={2,3,5}`、`slope_min_atr={0,0.01,0.02,0.04}`、`max_distance_atr={0.75,1.0,1.5}`、`max_age_days={5,10,20,until_recross}`，合计 `576` 项。
- V6 原生入场和 PEHC handoff 优先；DTEC 只接管二者均未成交的 raw-cross episode。触及/穿回 MA7、相反 cross、非有限数据、原生信号抢占或过期均取消 episode；确认后下一 UTC 日开盘成交。
- 成本、funding、真实 `1h` 时间顺序 MDD、flat-start WFO、`8bps` 压力和 V6 模块接线检查均沿用冻结执行链。manifest 前置 `41 passed`，DTEC 关闭时与 exact V6 的逐笔/path 完全一致。

## Development 结果

### Control

exact V6 在 D-full 的结果为：净收益 `+316.582473%`、真实 `1h` MDD `-17.769023%`、15 笔（8 long / 7 short）。六折 WFO 汇总为 `+349.791606% / -16.420754%`。

### Long-only 最优经济路径

`DTEC_L189`（其 `5/10/20/until_recross` 四个有效期变体历史路径等价）：

- 参数：连续 `3d` 位于 MA7 上方，`2d` MA7 slope/ATR `>0.04`，距 MA7 不超过 `1.5ATR`。
- D-full：`+339.536461% / -17.769023%`，16 笔；收益比 V6 高 `22.953988pp`，MDD完全不变。
- WFO：`+359.538245% / -16.420754%`；收益高 `9.746639pp`，最差 MDD仍完全不变。
- `8bps`：收益仍高 `22.344035pp`，MDD仍无改善。
- 13 次可评估 raw-cross episode 中只确认 1 次；该次 5 日方向/持续标签命中。它说明一个延迟多头历史上有正贡献，但 `n=1` 不能证明可重复的趋势识别能力，也没有触碰 V6 的主要回撤段。

### Short-only 最优筛选路径

`DTEC_S005`（四个有效期变体同样历史等价）：

- 参数：连续 `2d` 位于 MA7 下方，`2d` MA7 slope/ATR `>0`，距 MA7 不超过 `1.0ATR`。
- 局部标签看似有效：9 个可评估确认中 7 个命中，5 日 precision `77.78%`。
- 但 D-full 仅 `+130.104618% / -26.403778%`，相对 V6 少 `186.477854pp` 收益、MDD恶化 `8.634755pp`。
- WFO 为 `+270.816857% / -17.171598%`，收益少 `78.974749pp`、MDD恶化 `0.750844pp`；`8bps` 也同时更差。
- 它把 short 交易从 7 笔增至 14 笔，却把 long 从 8 笔压至 4 笔；V6 的 `long_trail_exit` 从 6 次降至 3 次、`shadow_start` 从 6 次降至 3 次、`handoff_accept` 从 3 次降至 2 次。由此可见，局部 5 日方向命中不等于组合层增益：新增 short 占用了单仓，使后续高价值 long/OAPP/PEHC 状态链无法发生。

### 多空组合

Stage B 的 16 个组合只有一条经济路径，差异仅来自历史未咬合的 `max_age_days`：

- D-full：`+177.573054% / -26.403778%`，20 笔（6 long / 14 short）；相对 V6 收益少 `139.009419pp`、MDD恶化 `8.634755pp`。
- WFO：`+276.758367% / -18.391413%`；相对 V6收益少 `73.033238pp`、MDD恶化 `1.970659pp`。
- `8bps` 压力相对 V6收益少 `138.514964pp`、MDD恶化 `8.754303pp`。
- 趋势标签为 11 次确认中 9 次命中（long `2/2`、short `7/9`），但 6 个 block 中有 2 个收益和 MDD同时更差。全部组合都触发 `d_full_dual_improvement=false`、`d_wfo_dual_improvement=false`、`blocks_not_double_worse=false` 和 `stress_not_double_worse=false`。

## 为什么简单规则没把 V6 变好

1. **识别正确不等于交易正确。** 5 日标签只判断确认后的一小段是否继续同向，不衡量这笔仓位会不会阻断稍后更大的 V6 long、OAPP 退出或 PEHC handoff。short 的 `77.78%` precision 仍对应显著更低的组合收益。
2. **单仓机会冲突是主因。** DTEC short 不是给 V6 增加一个独立收益腿，而是替换 V6 原本将要发生的状态链。它增加了低幅阴跌覆盖，同时删除了更稀缺、更高价值的多头 campaign。
3. **long 增量太稀疏。** 最优 long 只有 1 个确认样本，虽然盈利，但没有覆盖 V6 的最差回撤时间，所以只能提高收益，不能降低 MDD。
4. **有效期不是关键参数。** `5/10/20/until_recross` 在入选区域全部同路径，继续围绕 expiry 调参不会修复组合冲突。
5. **目标要求同时提高收益并降低回撤。** 事后把门改成“只提高收益”会让 long-only 看似成功，但那不是用户要求，也会把一个单样本结果误报成新版本。

## 后继边界

- 不在同一已暴露 D 上继续缩窄阈值并宣称验证，也不把 long-only 单事件写入 V6 或登记 V7。
- 如果继续这条机制，首先应冻结“机会预算/冲突仲裁”而非再搜 cross 参数：DTEC 只能在不会占用已知 V6 高价值 long/PEHC episode 的条件下试仓，且准确率标签需要同时计入机会成本与完整 campaign PnL。
- 更可靠的资格仍需来自 `2026-08-11` 起的 clean prospective，或跨资产/更长历史上的预注册重复；在 `1x` 同时提高收益、降低 MDD之前，杠杆继续锁定。

## 证据

- [预注册合同](../specs/hype-1d-ma7-delayed-trend-episode-confirmation-preregistration-2026-08-10.md)
- [Manifest](../artifacts/hype_1d_ma7_v6_delayed_episode_2026-08-10_manifest.json)
- [Stage A：1,152个单边配置](../artifacts/hype_1d_ma7_v6_delayed_episode_2026-08-10_stage_a.json)
- [Stage B：16个多空组合](../artifacts/hype_1d_ma7_v6_delayed_episode_2026-08-10_stage_b.json)
- [Evaluation未访问证明](../artifacts/hype_1d_ma7_v6_delayed_episode_2026-08-10_evaluation.json)
- [最终机器裁决](../artifacts/hype_1d_ma7_v6_delayed_episode_2026-08-10_final.json)

