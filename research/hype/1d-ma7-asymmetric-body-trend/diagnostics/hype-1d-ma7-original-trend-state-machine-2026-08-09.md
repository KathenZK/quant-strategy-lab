# HYPE 1D MA7 原始趋势状态机诊断

> 日期：2026-08-09。结论：`explore / not promoted / not live-ready`；不登记 V5，不修改 V1–V4。全部收益均为 researcher-exposed development evidence，不是 clean OOS。

## 1. 这轮把原始想法推进到了哪里

用户确认的原始想法现已落成无歧义、可执行的收盘到次开盘状态机，见[冻结合同](../specs/hype-1d-ma7-original-trend-state-machine-contract-2026-08-09.md)：

1. flat 时，前一完整日严格在 MA7 反侧、当日 fresh cross 到目标侧，次日 open 直接入场；入场日不要求 slope；
2. 持仓后 fresh cross 只先 armed；外穿 `0.75×ATR7` 且目标方向 slope 通过才反手；
3. 尚在容错带内但原方向 slope 消失时先平仓，armed 跨 flat 保留；重新穿回原侧才取消；
4. 空头连续 3 个完整日 `RSI6<30` 且信号收盘仍有浮盈，次 open 只止盈转 flat；
5. fresh down-cross 前连续 3 日 `RSI6>70` 且当日 short slope `<0`，允许 long 次 open 提前反手 short；
6. 主规则不继承 V4 的 trailing、hard stop、max hold 或 cooldown；`1.5×entry ATR7` emergency stop 单独作为 E 保护臂。

现有 V1–V4 的身份、逐笔路径和历史结论未改。本分支是对“原始 MA7 趋势跟随思想”的独立机制审计，不是 V4 调参。

## 2. 数据、执行与可复现性

- Binance USD-M `HYPEUSDT` perpetual；`10,390` 根连续 `1h`，`2025-05-30 10:00` 至 `2026-08-06 07:00 UTC`；SHA256 `e3598920ec9b4f6b9ddc5a7b186bf5153bd8d4ece35de1a3bbb188cd7de893ce`。
- funding `2,597` 条，截止 `2026-08-06 08:00 UTC`；SHA256 `78b529b9d9433801c31aeb830be04d3686bc63da7b4b55926cb28b1254a685a6`。
- 聚合 `432` 个完整 UTC 日，信号日 `2025-05-31` 至 `2026-08-05`；`2026-08-06 00:00 UTC` 只作 terminal open。
- 手续费 `0.001/fill`，基准不利滑点 `4 bps/fill`，压力 `8 bps/fill`；funding 按真实事件小时 open 结算。
- 全部收盘信号最早下一 session open 成交；翻仓计两次 fill；成交间数量固定。
- 合同、状态机、研究器 SHA256 分别为 `821019e3…d4cb6`、`4e2bcfda…f403`、`961c9acd…a126087`；23 项因果/账本测试通过。

机器主证据见[summary.json](../artifacts/hype_1d_ma7_original_trend_2026-08-09_summary.json)，完整路径见[交互式 HTML](../artifacts/hype_1d_ma7_original_trend_trade_path_2026-08-09.html)。

## 3. A–D 主结果

| Arm | 全期净收益 | MDD | PF | 交易 | Long PnL | Short PnL | Short 平均回吐 | 裁决 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `A_CORE` | `-33.52%` | `-57.28%` | `0.883` | 50 | `-0.1437` | `-0.1915` | `12.48%` | 核心机制失败 |
| `B_SHORT_RSI_EXIT` | `-8.54%` | `-50.27%` | `1.069` | 56 | `-0.1922` | `+0.1068` | `10.05%` | 有机制改善，但不通过接受门槛 |
| `C_OVERBOUGHT_REVERSAL` | `-33.52%` | `-57.28%` | `0.883` | 50 | `-0.1437` | `-0.1915` | `12.48%` | 与 A 逐笔完全相同，模块 dormant |
| `D_BOTH_RSI` | `-8.54%` | `-50.27%` | `1.069` | 56 | `-0.1922` | `+0.1068` | `10.05%` | 与 B 逐笔完全相同，无组合增量 |

同期同成本/funding 的 `1x` buy-and-hold 为 `+59.75%`。四个实验臂全部没有绝对收益或超额收益资格。

### 3.1 RSI6 空头止盈确实修复了什么

B 相对 A：

- 全期净收益提高 `24.98pp`，MDD 改善 `7.01pp`；
- 7 次 `short_rsi_take_profit` 把 short 腿从 `-0.1915` 改为 `+0.1068`；
- short 平均 profit giveback 从 `12.48%` 降到 `10.05%`；
- 12 个 90 日 rolling 中 6 个改善、3 个相同、3 个恶化，B 有 6 个正窗口，A 只有 4 个。

但这不是可保留模块：B 在 `8 bps/fill` 下仍为 `-12.54%`，全期本身为负，MC3 亏损概率 `56.40%`，5% ending-equity 仅 `0.321`，5% drawdown 分位约 `-74.67%`。额外延迟一天虽然为 `+6.48%`，但这种“延迟反而救活”的路径敏感本身也降低执行稳定性。

### 3.2 overbought 提前反空为什么没有融合效果

全期共有 49 次 raw fresh down-cross；连续 3 日 `RSI6>70` 后再 fresh down-cross 只有 1 次，而且该日 short slope 不为负，因此 C 没有一次 `overbought_fresh_down` 成交。A/C 的 path、trade、action 逐行相同；B/D 也逐行相同。

这不是“阈值 70 已被证明无效”，而是当前 HYPE 432 日历史对这个联合事件几乎没有样本。阈值 65/75 的预登记邻域也没有改变 D 的路径，不能据此选择新阈值。

## 4. 稳健性与风险

### 4.1 执行压力

| Arm | `8 bps` | 额外延迟 1 日 | 结论 |
| --- | ---: | ---: | --- |
| A / C | `-36.15%` | `-2.25%` | 两项均未持续为正 |
| B / D | `-12.54%` | `+6.48%` | 成本压力失败，延迟高度改写路径 |

### 4.2 Rolling、CPCV 与 MC3

- A：12 个 rolling 中 4 正；CPCV 15 组中 7 正，中位 `-8.61%`、最差 `-30.00%`；MC3 亏损概率 `75.41%`。
- B：12 个 rolling 中 6 正；CPCV 15 组中 8 正，中位 `+5.40%`、最差 `-28.49%`；MC3 亏损概率 `56.40%`。
- CPCV 每组至少 5 笔，形式上不是 insufficient evidence；但正负接近掷硬币，且尾部很差，不能构成 promotion evidence。

### 4.3 24 相位

phase `08:00 UTC` 因最后完整信号日缺 terminal open，固定回退到前一个完整可执行窗口；24 个相位均已产出。A/C 仅 3/24 正，中位 `-39.42%`；B/D 仅 7/24 正，中位约 `-14%`。相位不是单独否决门，但这里与主失败方向一致。

### 4.4 E emergency stop

`1.5×entry ATR7` 对称固定止损没有降低尾部，反而破坏趋势路径：

| Parent | E 净收益 | E MDD | Stop 次数 | 相对 parent |
| --- | ---: | ---: | ---: | --- |
| A / C | `-64.10%` | `-74.91%` | 9 | 明显恶化 |
| B / D | `-27.52%` | `-60.50%` | 8 | 明显恶化 |

因此 E 不并入核心，也不能作为 live-risk 修补。

## 5. 真正暴露出的核心问题

最重要的发现不是 RSI 参数，而是“严格日线 slope 必须一直同号”造成频繁退出与重入：

- 完全取消 slope exit，但保留外带反手 slope：`+8.79%`、28 笔、MDD `-55.12%`；
- 连外带反手 slope 也取消：`+18.47%`、28 笔、MDD `-55.12%`；
- 主 A 为 `-33.52%`、50 笔，累计成本 `0.1132` 初始权益；
- 但 `CORE_NO_SLOPE` 的 short 腿仍为 `-0.3433`，且这些是已揭示 OAT，不是可直接替换的候选。

所以当前研究问题已从“RSI6 应该取几天、多少阈值”推进为：

> fresh cross 有一定事件意义，但用 MA7 的单日严格斜率符号管理持仓过于抖动；空头又需要独立的利润锁定机制。下一步应研究 slope 的状态持续性/滞后定义与 long/short 非对称退出，而不是继续扫 RSI 阈值。

## 6. 裁决与遗留事项

### 当前裁决

- 不登记 V5：A 失败；B 有可解释增量但绝对、成本和 MC 门槛失败；C dormant；D 无新增贡献；E 恶化。
- 不 promotion、不写 runner spec、不进入 dry-run/live。
- V1–V4 继续保持原登记状态，本轮不能替换 V4。

### 尚需解决

1. **Slope 机制重构**：隔离比较单日符号、连续 K 日、斜率迟滞或只用于反手、不用于平仓；必须另开冻结合同，不能把 `CORE_NO_SLOPE` 赢家回填。
2. **RSI6 空头止盈外部验证**：当前只有 7 次实际止盈，需 clean prospective 或预先冻结的跨资产/更长历史验证；8 bps 仍亏说明成本余量不足。
3. **Overbought 反空样本不足**：当前只有 1 个 raw 联合事件且 slope 未通过；需要扩展样本域后先做事件频率/条件漏斗，不应先调 65/70/75。
4. **尾部风险未解决**：B 的 MDD 仍 `-50.27%`，固定 `1.5 ATR` stop 更差；需要独立的风险机制研究，而非把 stop 静默并入 alpha。
5. **Clean prospective 未开始**：若继续，按[前瞻观察协议](../specs/hype-1d-ma7-original-trend-prospective-observation-protocol-2026-08-09.md)从冻结后平仓起跑，A–D 并行 shadow，至少 `90d` 且每臂 `5` 笔平仓；观察期间不得选阈值。
6. **执行交接证据为空**：没有 quant-runner parity、restart recovery、线上开平仓对账或 live reconciliation；历史回测无权替代这些门禁。

## 7. 证据索引

- [A–D 指标](../artifacts/hype_1d_ma7_original_trend_2026-08-09_metrics.csv) · [执行压力](../artifacts/hype_1d_ma7_original_trend_2026-08-09_stress.csv) · [E 保护](../artifacts/hype_1d_ma7_original_trend_2026-08-09_protection.csv)
- [90 日 rolling](../artifacts/hype_1d_ma7_original_trend_2026-08-09_rolling_90d.csv) · [CPCV](../artifacts/hype_1d_ma7_original_trend_2026-08-09_cpcv.csv) · [MC3](../artifacts/hype_1d_ma7_original_trend_2026-08-09_mc3.csv)
- [核心消融](../artifacts/hype_1d_ma7_original_trend_2026-08-09_core_sensitivity.csv) · [RSI 邻域](../artifacts/hype_1d_ma7_original_trend_2026-08-09_rsi_sensitivity.csv) · [24 相位](../artifacts/hype_1d_ma7_original_trend_2026-08-09_phase24.csv)
- [近期切片](../artifacts/hype_1d_ma7_original_trend_2026-08-09_recent.csv) · [逐笔交易](../artifacts/hype_1d_ma7_original_trend_2026-08-09_trades.csv) · [完整路径](../artifacts/hype_1d_ma7_original_trend_2026-08-09_path.csv) · [动作账本](../artifacts/hype_1d_ma7_original_trend_2026-08-09_actions.csv)
- [交互式完整交易路径](../artifacts/hype_1d_ma7_original_trend_trade_path_2026-08-09.html)
