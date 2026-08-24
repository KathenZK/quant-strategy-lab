# HYPE 1D MA7 V4-PFT 修复：Development 裁决与机制归因

> 日期：2026-08-09。状态：`explore / not promoted / not live-ready`。数值裁决：`development hard-gate FAIL`。没有 champion，Validation / Holdout 均未揭示。

## 1. 结论

本轮没有找到同时满足“相对 exact V4 收益更高、最大回撤更小”的可晋级结构。8 个冻结结构臂全部完成，0 个通过 Development 硬门；因此研究在 D 结束，不运行 RSI `30×3` 替补，不读取 V/H，不登记 V5，不修改 V4，也不推进 runner。

最重要的机制结论不是“RSI6 无效”，而是：

1. `T = short RSI6<25 连续2日且已有成本保护利润` 是明确正贡献。单独加入 T 的 `A001_T` 在 D-full 同时提高收益、降低 MDD，在 D-WFO 也明显提高收益。
2. D-WFO 的最差 MDD 来自 F3 唯一一笔 long，`-19.674159%`；F3 没有 short，也没有 P/F/T 的有效路径变化。因此这组只修 short pending、forced short 和 short take-profit 的模块，结构上无法把 WFO worst-fold MDD 推得比 V4 更小。
3. `P` 的两次 delayed short 一盈一亏；Development 全窗受益，但 WFO 只看到亏损的那次，F1 同时少 `0.743477pp` 收益并多 `1.238241pp` MDD。
4. `F` 过于粗：它确实拒绝了 V4 的 forced short，但同时删掉一笔重要盈利 short，D-full 收益比 V4 少 `36.679018pp`，MDD没有实质改善。

所以，本轮核心目标失败的直接原因是：新增模块主要修复空头利润回吐和空头入场质量，而冻结门要求最差折的组合回撤也改善；实际最差折风险由 long protective 路径决定，三个模块都碰不到它。

## 2. 冻结边界与前置完整性

- 数据：432 根完整 UTC 日线，底层 10,390 根 `1h`、2,597 条 funding；缺口、重复、关键空值、OHLC、closed-only、raw/normalized parity blocker 均为 0。
- 成本：`0.001/fill` fee + `4 bps/fill` 不利滑点；压力为 `8 bps/fill`；event-time funding。
- exact V4 全窗锚点：`+398.840674%`、MDD `-26.813854%`、17 笔，与冻结 adapter 一致。
- 测试：manifest 前 38 项通过；A000 在 D 的 metrics、trades 与去除 PFT 展示字段后的经济 path 均与 exact V4 完全相同。
- 边界：D `[0,259)`；WFO `[130,173)`、`[173,216)`、`[216,259)`；V `[269,346)`、H `[356,432)` 均保持封存。

## 3. 8 臂结果

| Arm | D-full return | D-full MDD | D-WFO return | D-WFO worst MDD | D 裁决 |
| --- | ---: | ---: | ---: | ---: | --- |
| `A000_V4` | `+160.020323%` | `-22.335816%` | `+62.342625%` | `-19.674159%` | control |
| `A001_T` | `+199.932966%` | `-19.674159%` | `+86.288196%` | `-19.674159%` | FAIL：WFO MDD相同 |
| `A010_F` | `+123.341304%` | `-22.335816%` | `+62.342625%` | `-19.674159%` | FAIL |
| `A011_FT` | `+178.240296%` | `-19.674159%` | `+86.197660%` | `-19.674159%` | FAIL：WFO MDD相同 |
| `A100_P` | `+176.872721%` | `-22.335816%` | `+61.205289%` | `-19.674159%` | FAIL：F1双劣 |
| `A101_PT` | `+219.372177%` | `-19.674159%` | `+84.983103%` | `-19.674159%` | FAIL：F1双劣、WFO MDD相同 |
| `A110_PF` | `+137.816468%` | `-22.335816%` | `+61.205289%` | `-19.674159%` | FAIL |
| `A111_PFT` | `+196.273564%` | `-19.674159%` | `+84.893202%` | `-19.674159%` | FAIL：F1双劣、WFO MDD相同 |

所有臂都非破产，交易数和账本检查通过；所有已启用模块在 D 都有真实 activation，关闭后经济路径均改变。失败不是 dormant、未接线、不同 MDD 计量器或样本为零造成的。

## 4. 模块 T：有价值，但不能独自解决组合最差回撤

### 4.1 量化贡献

`A001_T` 相对 V4：

- D-full：收益 `+39.912643pp`，MDD改善 `+2.661657pp`；双重支配通过。
- D-WFO：收益 `+23.945571pp`，MDD改善恰为 `0.000000pp`；因此严格双重支配失败。
- `8 bps` D-full：收益仍多 `39.170899pp`，MDD改善 `2.719976pp`。
- `8 bps` D-WFO：收益仍多 `23.601595pp`，MDD仍相同。

T 在 D-full 实际退出4次，四笔均为盈利退出：

| Short entry | V4 exit / return | T exit / return | 作用 |
| --- | --- | --- | --- |
| 2025-07-24 | 2025-08-08 / `+6.256%` | 2025-08-03 / `+15.416%` | 降低回吐 |
| 2025-09-20 | 2025-10-01 / `+17.591%` | 2025-09-24 / `+18.277%` | 略提前锁利 |
| 2025-11-21 | 2025-11-29 / `+6.822%` | 2025-11-23 / `+19.906%` | 显著降低回吐 |
| 2025-12-06 | 2025-12-25 / `+18.870%` | 2025-12-19 / `+27.459%` | 显著降低回吐 |

代价是提前离场后重新开放了后续入场：新增 2025-12-25 long `-4.706%` 和 2026-01-01 forced short `-7.947%`。即使包含这两笔，T 的净贡献仍为正。

### 4.2 为什么 WFO MDD 不动

- F1：T 0 次触发，路径与 V4 相同。
- F2：T 2 次触发，收益从 `+26.979184%` 提高到 `+45.708641%`，MDD从 `-16.229881%` 改善到 `-15.858770%`。
- F3：只有1笔 long、0笔 short、T 0次触发；收益与 V4 同为 `+20.472612%`，MDD同为 `-19.674159%`。

WFO aggregate 取三折最差 MDD，F3 恰是最差折。因此 T 即使在 F2 很有效，也不可能改变 aggregate MDD。

## 5. 模块 P：补到漏单，但跨窗稳定性不足

P 在 D-full 发生11次 arm、2次 delayed confirm、1次 handoff、3次 expiry、1次 anti-chase reject、1次被其他入场取消。

- 2025-06-19 delayed short 到 2025-06-28，净回报 `+7.232%`，随后 handoff 保留原 V4 long；这是历史已知的正样本。
- 2025-11-13 delayed short 次日退出，净回报 `-0.701%`。

D-full 因两者合计仍提高 `16.852398pp` 收益，但 MDD未改善。WFO F1只包含第二笔，因而收益少 `0.743477pp`、MDD差 `1.238241pp`，触发 fold double-worse。P 是有选择性的覆盖修复，却仍不足以证明跨时段稳定。

## 6. 模块 F：过滤方向正确，门槛过于粗

F 在 D-full 对 forced reversal 产生4次拒绝，经济路径确实改变，但：

- `A010_F` 收益只有 `+123.341304%`，比 V4 少 `36.679018pp`；
- MDD与 V4 在机器精度内相同；
- 三个 WFO fold 与 V4逐路径相同。

原因是“down slope不通过就拒绝”不仅删掉短命亏损反手，也删掉 2025-09-20 后的大额盈利 short。F 没有区分“暂未确认”和“方向错误”，直接 flat 会损失趋势延续收益。

## 7. 交互结论

- `P+T` 给出最高 D-full 收益 `+219.372177%`，说明两者并非互相抵消；但继承 P 的 F1双劣和 T 无法触及 F3 long MDD，仍失败。
- `F+T` 的 D-full 比 T 单独少 `21.692671pp`，说明 F 会侵蚀 T 保留下来的空头趋势收益。
- `P+F+T` 没有产生新的回撤修复机制：D-full优于 V4，但 WFO worst MDD仍完全相同，并继承 P 的 F1双劣。

不能把 P、F、T 的单臂收益简单相加；完整 2×2×2 路径已经显示交互主要发生在 cooldown、重新入场和 forced reversal 序列。

## 8. 实现审计备注

预注册文本把 P delayed confirmation 的下界写成 `0.25×ATR7`，并误称其来自 V4；exact V4 实际 short `entry_buffer_atr=0.10`。冻结实现继承的是 exact V4 的 `0.10` buffer，并另外限制上界 `0.75`。

这是 manifest 后发现的合同/实现潜在不一致。D 中两次实际 delayed confirmation 的距离为 `0.315917` 与 `0.491117×ATR7`，都高于 `0.25`，所以本次已实现 D 经济路径与合同要求相同，没有改变“0个臂通过”的裁决。但该源不能在不另立合同、重新锁 pin 的情况下推进 V/H；本轮本来已因 D FAIL 停止。

## 9. 下一研究问题

如果继续追求“在 V4 基础上同时提高收益、降低回撤”，下一合同不应继续搜索 RSI 阈值或 P/F 参数，而应拆成两个独立问题：

1. 保留本轮已证明有正贡献的 T 作为固定退出模块，不再用已揭示 D 搜索 `25/30/35` 或 `2/3/4日`。
2. 新增一个专门针对 long protective path 的风险模块，使其有能力影响 WFO F3 的 `-19.674159%` long drawdown；候选必须通过 long-only path activation、保护前后MFE/MAE、跳空、额外成本和不误杀趋势的审计。
3. P 若继续，只能作为单独的前瞻假设；当前两次 delayed 样本一盈一亏，不能据此调 anti-chase 或等待天数。
4. F 当前二元拒绝不再继续调 slope 阈值；若重做，应研究“拒绝后等待一次 fresh short confirmation”而不是直接永久 flat，但必须是 materially new 合同和新的未揭示边界。

## 10. 证据

- [预注册合同](../specs/hype-1d-ma7-abt-v4-pft-repair-preregistration-2026-08-09.md)
- [冻结 manifest](../artifacts/hype_1d_ma7_v4_pft_repair_2026-08-09_manifest.json)
- [8 臂完整 trials](../artifacts/hype_1d_ma7_v4_pft_repair_2026-08-09_development_trials.json)
- [Development 机器裁决](../artifacts/hype_1d_ma7_v4_pft_repair_2026-08-09_development.json)
- [A001_T D-only 完整交易路径](../artifacts/hype_1d_ma7_v4_pft_repair_2026-08-09_development_failed_A001_T_trade_path.html)

以上均为 researcher-exposed Development diagnostic evidence，不是 prospective/OOS 或 promotion 许可。
