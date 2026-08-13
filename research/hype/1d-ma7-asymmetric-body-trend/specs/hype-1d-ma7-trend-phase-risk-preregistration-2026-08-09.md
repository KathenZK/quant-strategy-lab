# HYPE 1D MA7 趋势阶段识别与风险效率预注册合同

> 冻结日期：2026-08-09。状态：`explore / not promoted / not live-ready`。研究代号：`TPR`（Trend Phase & Risk）。本合同不修改已登记 V4，不登记 V5，不继承失败分支的版本身份。

## 1. 研究目标

以 exact `HYPE-1D-MA7-Asymmetric-Body-Trend-V4` 的 `1x` 实现为唯一 control，寻找一个低复杂度状态机，使其：

1. 更可靠地判断趋势开始，而不是在持续 regime 中反复追单；
2. 趋势有效时继续持有，趋势结束或利润明显回吐前退出；
3. 在同窗、同成本、同 funding、同执行账本下，成本后收益严格高于 exact V4，真实 `1h` 顺序 MDD 严格更小；
4. `1x` 候选独立通过后，才研究目标杠杆不高于 `3x` 的固定与动态入场杠杆，输出收益—回撤 Pareto 前沿。

杠杆不能参与 `1x` 候选选择，也不能救援失败的 `1x` 信号。

## 2. 已知证据与明确排除

### 2.1 保留

- exact V4 的 natural reclaim、MA7 slope、entry buffer、`0.75ATR` 持仓迟滞、long trailing、short hard/trailing stop、forced reversal MA-only确认、max hold、cooldown、成本和 funding 全部保留。
- `short RSI6<25` 连续2个实际持仓日且 signal close 的 gross short profit 严格覆盖 `0.28%` 往返 fee+slippage 后，下一 UTC open 平空。该 T 规则固定，不再搜索 RSI 阈值或连续日。
- Fresh reclaim 继续作为趋势事件的新鲜度来源；不改成 persistent regime。

### 2.2 排除

- 不使用上一轮失败的单日 slope-loss、held adverse-band直接反手、overbought memory、无限 pending。
- 不搜索 P 的等待日、anti-chase 上限或 handoff；P 在 WFO F1 双劣。
- 不搜索 F 的 forced slope 阈值；二元拒绝会删除高盈利 forced short。
- 不搜索 MA 长度、ATR 长度、RSI 长度、V4 原始 slope/exit/cooldown/保护参数。
- 不用降低仓位掩盖失败信号；风险缩放只在 `1x` Validation PASS 后启动。

## 3. 数据、时序与成本

- Binance USD-M `HYPEUSDT` perpetual。
- 432 根完整 UTC `1d`，底层 10,390 根闭合 `1h` 与 2,597 条 funding，terminal open 为 `2026-08-06 00:00 UTC`。
- 日线信号只读已闭合日 `t`，最早 `t+1` open 成交；intraday stop、forced reversal、funding 按真实 `1h`/event timestamp。
- fee `0.001/fill`；base slippage `4 bps/fill`；stress `8 bps/fill`。
- 原子反手按平旧、开新两个 fill 计费；数量在两次成交间分别更新。
- 任何 equity `<=0` 立即冻结为零并 fail closed。

## 4. 双 MDD 合同

### 4.1 主指标：`chronological_1h_mdd`

使用冻结交易 ledger 逐笔重放：

- 先结算成交成本；
- 按真实 timestamp 合并每根 `1h` open（连续市场中也是上一小时 close 的可复现 mark）、funding event 和实际 exit fill；
- funding 在其 event timestamp 结算；
- 每个 mark 只使用该时点已知价格和当时固定数量；
- 原子反手必须按 close-old cost、open-new cost 的顺序重放；
- MDD 从按时间排序的标记权益峰值计算。

该指标不使用同一日未知的 high/low 先后关系，是主晋级风险指标。

### 4.2 压力指标：`daily_extreme_mdd`

保留 exact V4 的 `favorable extreme -> adverse extreme -> close` 日极值 MDD。它用于最坏顺序压力，不作为“真实发生过的日内路径”叙事。候选在该指标上不得与收益同时弱于 V4；杠杆层另有绝对风险上限。

### 4.3 重放一致性

逐笔重放必须与原 backtest 的 terminal equity、cost、funding、turnover、trade count 在冻结容差内一致；否则所有绩效作废。另输出 hourly-open mark path 与 worst drawdown timestamp/trade attribution。

## 5. 固定 D/V/H 边界

| 角色 | Eval | 说明 |
| --- | --- | --- |
| D-full | `[0,259)` | researcher-exposed 结构研究 |
| WFO F1 | `[130,173)` | flat-start，engine 从131启动 |
| WFO F2 | `[173,216)` | flat-start，engine 从174启动 |
| WFO F3 | `[216,259)` | flat-start，engine 从217启动 |
| V | `[269,346)` | one-shot validation；`[259,269)` purge |
| H | `[356,432)` | one-shot retrospective holdout；`[346,356)` purge |

V/H 尚未运行过任何 TPR 候选。候选只在 D 选择；D失败不读取 V，V失败不读取 H。

## 6. 趋势开始模块 Q：方向效率

Q 只过滤 exact V4 natural `close_entry_signal`，不创造新 entry、不延迟追单、不改变 forced reversal。

对 side `s∈{+1,-1}`、lookback固定为7日：

`signed_ER7 = s × (close_t-close_{t-7}) / Σ_{i=t-6..t}|close_i-close_{i-1}|`

- 分母非正或任一输入非有限则 fail closed；
- exact V4 entry signal 先通过，随后要求 `signed_ER7 > q`；
- 固定 `q ∈ {0.20, 0.30, 0.40}`；另有 Q disabled；
- equality 不通过；无 pending、无 later regime entry。

Q 的含义是：fresh reclaim 发生时，最近7日净方向移动必须占实际路径长度的足够比例，避免震荡穿越被误判为趋势开始。

## 7. 趋势结束模块 E：盈利 long 的 slope decay

E 只新增 long 日线退出，不改变 intraday protective stop，也不作用于 short。

- long实际 fill 后 streak=0；
- 每个完整持仓日计算 `slope_atr=(MA7_t-MA7_{t-1})/ATR7_t`；
- 当 `slope_atr <= 0` 时 streak+1，否则清零；非有限清零；
- 固定确认日 `e ∈ {2,3}`；另有 E disabled；
- streak达到 e 且 signal close 相对实际 long entry 的 gross profit严格大于`0.28%`时，生成 `long_slope_decay_exit`；
- 次日 UTC open 平 long 到 flat，继承 V4 long cooldown；
- E 在日开与 V4 native daily exit 同价，E 优先用于原因归因；已经发生的 intraday protective stop自然优先。

E 只保护已经盈利的 long，不把普通短期浮亏变成额外止损，也不使用日内未来数据。

## 8. 固定 short 结束模块 T

- Wilder RSI6；实际 short fill 后开始 streak；`RSI6<25` 连续2日；equality重置。
- signal close gross short profit严格大于`0.0028`；下一 UTC open平仓；继承short 5日cooldown。
- T 优先于 V4 native daily short exit；不 handoff。
- 所有 ranked candidate 固定 T enabled；exact V4 control不启用T。
- champion 后执行 T disabled OAT，但 disabled 版本不参与替补或排名。

## 9. `1x` 候选网格

共13个 ranked/evidence arm：

- `C000_EXACT_V4`：exact V4 control；Q/E/T均关闭。
- 12个候选：Q阈值 `{disabled,0.20,0.30,0.40}` × E确认 `{disabled,2,3}`，全部 T enabled，目标仓位固定 `1x`。

候选 ID 按 `Q{OFF|20|30|40}_E{OFF|2|3}_T25X2` 固定。不得增加阈值、删除失败行或先看绩效再改优先级。

### 9.1 事件研究

在读取候选排名前保留所有 exact V4 natural entry 事件的 `signed_ER7`、side、entry/exit、未来3/5/10/20日MFE/MAE与最终交易结果；保留所有 long held-day 的 slope streak、MFE、giveback及 E hypothetical exit。事件研究只解释因果，不产生网格外参数。

## 10. `1x` Development 硬门

候选在 D-full 和 D-WFO aggregate 两个域都必须：

- net return严格高于 exact V4；
- `chronological_1h_mdd`严格更接近零；
- 每域至少一项 material：return delta `>=5pp` 或 chronological MDD delta `>=2pp`。

额外门：

- `8bps` D-full/WFO 不得收益与 chronological MDD同时更差；
- 每折不得双劣；
- D-full至少8笔、至少3笔short、至少3笔long；WFO合计至少3笔且每折至少1笔；
- `daily_extreme_mdd`与收益不得同时更差；
- 非破产、账本重放一致、无负持仓时长；
- Q/E/T enabled模块必须在D真实激活且关闭后去标签经济路径改变。

通过者排序：最差fold return delta、WFO return delta、WFO chronological MDD delta、D return delta、D chronological MDD delta、较少启用模块、ID。

无通过者则 `development hard-gate FAIL`，停止，不揭V、不研究杠杆。

## 11. Validation

唯一 D champion 在 V 与 exact V4 各运行一次，使用相同双重支配、materiality、至少3笔、非破产、ledger parity门。V失败或不足立即停止，不研究杠杆、不揭H。

## 12. 杠杆研究（仅 V PASS 后）

### 12.1 固定杠杆

目标 entry leverage：`1.25, 1.50, 2.00, 2.50, 3.00x`。信号、退出、cooldown和保护完全不变；数量固定至退出/反手。

### 12.2 动态入场杠杆

只在 entry 使用 signal day 已知的 `ATR7`、entry price和固定有效 stop distance `1.5×ATR7`：

`L_raw = risk_budget / (1.5×ATR7/entry_price)`

`L = clip(L_raw, 0.50, 3.00)`

固定 risk budget：`10%, 15%, 20%`。另有一个预注册质量调节版本：

`L = clip(L_R15 × clip(0.75 + signed_ER7, 0.75, 1.50), 0.50, 3.00)`。

forced reversal 沿用当时最近完整日的 signed ER；非有限时质量乘数为0.75。杠杆只在入场确定，不日内加仓或再平衡。

### 12.3 选择与风险

- leverage grid 在冻结 1x champion 通过 V 后，使用 D 与 V 两个已揭示域选择；H仍封存。
- 所有方案运行 base/8bps/funding-off、chronological/daily-extreme MDD、实际最大intraday leverage与破产审计。
- 任何 base/stress破产、非有限、terminal equity<=0 或目标 entry leverage>3 的方案淘汰。
- primary leverage candidate：D与V均相对1x champion收益更高，chronological MDD绝对值不超过35%，按最差域return、复合return、较低MDD、较低最大实际杠杆排序。
- aggressive audit candidate：同规则但MDD上限50%；只作风险前沿，不称可承受或live-ready。
- 若无方案满足35%，明确报告无 primary leverage candidate；不得放宽到50%救援。

## 13. Holdout 与最终前沿

只有1x V PASS才一次性运行H：exact V4、1x champion和全部预注册 leverage arm均运行一次，不根据H调参。1x champion继续使用V门；杠杆候选必须满足其冻结35%/50%风险层级、非破产和账本门。

最终按MDD上限 `20/25/30/35/40/50%` 分别报告H及全窗可获得的最高净收益、方案、目标/实际最大杠杆；没有满足者写 `NONE`。同时输出固定与动态杠杆 Pareto 前沿，不把50% MDD称为低风险。

## 14. 测试与产物

Manifest前必须通过：

- exact V4 anchor与all-off parity；
- signed ER equality/nonfinite/direction；
- E actual-fill/streak/equality/profit guard/priority/reset；
- T既有边界；
- 1h ledger replay terminal equity/cost/funding/atomic reversal/stop/gap parity；
- 13臂枚举、WFO flat-start、排序、D/V/H锁；
- fixed/dynamic leverage公式、3x cap、破产与Pareto；
- 完整path/trade HTML一致性。

Artifact前缀：`hype_1d_ma7_trend_phase_risk_2026-08-09`。JSON/HTML独占写入并带SHA256 sidecar。成功仍只为`explore / not promoted / not live-ready`。
