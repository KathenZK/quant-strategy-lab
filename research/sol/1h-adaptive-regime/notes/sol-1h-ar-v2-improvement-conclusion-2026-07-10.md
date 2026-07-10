# SOL-1H-Adaptive-Regime-V2 改进结论 - 2026-07-10

## 结论

V2 的主要问题不是某一个参数偏差，而是组合层面的负偏收益结构与 VWAP short regime 失效：

1. `donchian_break` 是相对稳定的 core leg；
2. `vwap_revert` short 在 prefit 有增益，但最近三个月转为主要亏损来源；
3. V2 用大量小 TP 换取高胜率，少数大 stop 吞噬收益，导致胜率 `93.91%` 但 full annual 只有 `2.07x`；
4. 简单 entry veto、分段止盈、failure exit、腿级 cooldown 都没有在 prefit-only 选择下修复 reused holdout；
5. `arm → confirm → expire` 状态机在 prefit-only 选择下让 reused holdout 从负转正，是最值得冻结等待 fresh forward 的结构；
6. 状态机观察仍只有 `3` 笔 reused-holdout 交易，且该窗口已揭盲，因此不登记新版本、不 promotion。

下一步不应继续围绕 V2 做 TP/SL 或过滤器小调。建议把家族改造成：

- `Donchian core`：保留趋势突破腿，作为后续 fresh-forward 的核心观察对象；
- `VWAP satellite`：停止无条件并入；采用“偏离事件 arm → 等待快速趋势重新确认 → 有限窗口入场”的状态机；
- 当前最优观察为 `3` bars confirm window、`roc6 + MACD` 同向确认；
- 只有该状态机在新增 fresh forward 上继续提供独立增益时，才讨论登记新版本。

## V2 收益结构

V2 正式 full 区间：

- annual `2.0662x`，DD `-17.41%`，win `93.91%`，trades `115`；
- 平均盈利 `+1.75%`，平均亏损 `-6.89%`，payoff `0.253`；
- 最大单笔亏损 `-14.36%`；
- stop exits `5` 笔，合计权益收益约 `-43.87%`；
- 小 TP 维持高胜率，但单次 stop 约等于 `4` 次平均盈利。

这意味着继续追求更高胜率没有解决价值。改进目标应从“胜率”切换到：

- 限制单笔尾部亏损；
- 提高平均盈利/平均亏损比；
- 让 trend leg 吃到更长的正向尾部；
- 在 mean-reversion regime 失效时不入场，而不是事后靠 cooldown 补救。

## 双腿贡献

### Donchian core

收益结构重做后的 Donchian 单腿：

- 参数观察：`TP=1 ATR`、`SL=4 ATR`、`max_hold=72`、`3x fixed leverage`；
- prefit annual `2.1626x`，DD `-17.41%`，win `97.92%`，trades `48`；
- full annual `2.0023x`，DD `-17.41%`，win `98.00%`，trades `50`；
- reused holdout annual `1.2111x`，return `+4.89%`，DD `-2.43%`，win `100%`，但只有 `2` 笔。

Donchian 腿的缺点是频率低，不能单独支持 `10x` 年化目标；优点是最近三个月没有出现机制反转。它适合作为 core，但目前样本数仍不足以 promotion。

### VWAP satellite

收益结构重做后的 VWAP 单腿：

- 参数观察：`TP=1.5 ATR`、`SL=2 ATR`、`max_hold=18`、`1.5x fixed leverage`；
- prefit annual `1.7299x`，DD `-14.29%`，win `79.31%`，trades `58`；
- full annual `1.5110x`，DD `-14.29%`，win `75.81%`，trades `62`；
- reused holdout annual `0.6249x`，return `-11.05%`，DD `-14.01%`，win `25.00%`，trades `4`。

最近三个月的 ensemble 亏损全部由 VWAP short 贡献。两笔关键 stop 在信号时同时出现：

- `roc6 > 0`；
- `MACD 8/21/5 histogram > 0`；
- `PDI > MDI`；
- 但慢速 `h12_spread` 仍保持 bearish。

这表明现有 VWAP 条件识别的是“慢周期仍为空头”，却没有识别“快速反弹已经开始”。问题是多周期 regime 切换滞后，不是简单的 stop 偏宽。

## 机制实验

### 1. 收益结构重做

实验范围：

- Donchian：fixed/trailing、方向、TP、SL、hold、leverage；
- VWAP：fixed/trailing、方向、TP、SL、hold、leverage、快速方向 gate；
- 选择只使用 train/validation/prefit，reused holdout 在冻结后审计。

prefit-only 选中：

- Donchian：`TP=1`、`SL=4`、`hold=72`、`3x`；
- VWAP：`TP=1.5`、`SL=2`、`hold=18`、`1.5x`；
- 不使用额外 entry gate。

结果：

- prefit annual 从 `2.4392x` 提升到 `3.7789x`；
- full annual 从 `2.0662x` 提升到 `3.0520x`；
- full payoff 从 `0.253` 提升到 `0.616`；
- reused holdout DD 从 `-15.69%` 压到 `-10.04%`；
- 但 reused holdout 仍为 return `-6.71%`、annual `0.7568x`。

结论：收益结构重做有效，但不能修复 VWAP regime 失效。该观察不登记版本。

### 2. 快速 entry veto

测试了 `roc6`、`roc12`、MACD state、DI state、`h4` state 及组合 gate。

- prefit-only 前 100 个组合全部为 `gate=none`；
- 快速 gate 可以解释并删除最近两笔 VWAP stop，但会损伤此前 train/validation 的有效交易；
- 因此不能依据 reused holdout 倒选 gate。

结论：单 K 布尔 veto 过于粗糙。需要事件状态机，而不是再加一个当根过滤器。

### 3. 分段止盈与 failure exit

测试：

- 第一目标部分止盈；
- 剩余仓位延伸目标；
- 第一目标后保本 stop 次 K 生效；
- 快速动量失效后次根 open 退出；
- 同 K 止损/止盈冲突按 stop-first；
- 每个 tranche 单独计 fee、slippage 和 funding。

prefit-only 选中观察：

- prefit annual `3.1860x`；
- full annual `2.6188x`；
- full 最大单笔亏损降至 `-9.17%`；
- reused holdout annual `0.7284x`、return `-7.59%`。

结论：分段止盈降低尾部亏损，但整体弱于简单收益结构重做；failure exit 没有进入最优结构。暂不采用。

### 4. 腿级 governor

测试 VWAP 在 stop 或任意亏损后暂停 `24/72/168/336/720` bars，Donchian core 不受影响。

- prefit-only 最优仍为 `cooldown=0`；
- 所有 governor 结构都没有替代无 cooldown 的收益结构重做观察。

结论：事后暂停只能处理亏损聚集，不能修复入场 regime 定义。

### 5. VWAP Arm-Confirm-Expire 状态机

状态机定义：

- arm：V2 原始 VWAP 偏离回穿事件满足慢周期、body、volatility、funding 等过滤；
- confirm：arm 后至少等待一根完整 K，在 `3/6/12` bars 窗口内等待快速方向确认；
- expire：窗口内无确认则事件失效，不交易；
- entry：confirm K 闭合后，下一根 open 市价入场。

prefit-only 选中观察：

- Donchian core：`TP=1 ATR`、`SL=4 ATR`、`hold=72`、`3x`；
- VWAP satellite：`3` bars confirm window；
- confirm：short 要求 `roc6 <= 0` 且 MACD `8/21/5` histogram <= 0；
- VWAP exit：`TP=1.5 ATR`、`SL=1.5 ATR`、`hold=12`、`1x`；
- VWAP arm events `94`，confirmed `58`。

结果：

- prefit annual `2.3129x`、DD `-19.05%`、win `79.57%`、trades `93`；
- full annual `2.0977x`、DD `-19.05%`、win `79.17%`、trades `96`；
- reused holdout annual `1.1089x`、return `+2.61%`、DD `-4.55%`、win `66.67%`、trades `3`；
- last `1y` annual `1.7439x`、DD `-17.89%`、win `79.07%`、trades `43`。

诊断含义：

- 状态机牺牲了收益结构重做观察的 full annual（`3.05x → 2.10x`），但把 reused holdout 从 `-6.71%` 改为 `+2.61%`；
- 它避免了 6 月 26/29 的无确认 VWAP short，只保留 6 月 9 的一次受控亏损；
- 这是唯一同时由 prefit-only 排序选中、且 reused holdout 转正的机制改造；
- 但 reused holdout 只有 `3` 笔，不能视为稳健性证明。

结论：冻结为 `V2-SM-OBS` 研究观察，不登记 V3；等待 fresh forward。

## 推荐的新状态机

VWAP satellite 的下一阶段应沿用已经验证过的三阶段状态机，而不是回到偏离回穿即入场：

### A. Arm

- 只记录 VWAP deviation 超阈值事件；
- 不立即下单；
- 保存方向、触发价格、ATR、慢周期 regime 和触发时间。

### B. Confirm

在有限窗口内等待快速趋势重新与交易方向一致。当前 prefit-only 最优是 `3` 根 `1h` K：

- short：`roc6 <= 0` 且 MACD histogram <= 0；
- long：`roc6 >= 0` 且 MACD histogram >= 0；
- 可比较 DI confirmation，但不与 reused holdout 倒选；
- confirm 必须在闭合 K 上完成，下一根 open 入场。

若窗口内没有 confirm，事件过期，不交易。

### C. Manage

- 初始 protection stop 必须立即有效；
- 不继续使用 `0.75/3 ATR` 极端负盈亏比；
- 第一轮建议固定比较：
  - `TP/SL = 1/1.5`；
  - `TP/SL = 1.5/2`；
  - `0.75 ATR` 部分止盈 + `1.5/2 ATR` runner；
- 保本 stop 只能从下一根 K 生效；
- VWAP satellite 总风险应低于 Donchian core，不因高胜率提高杠杆。

## 建议的研究顺序

1. 冻结 V2，不再修改其身份。
2. 将收益结构重做观察保留为 `V2-MR-OBS`，不登记新版本。
3. 将 `3-bar roc6+MACD confirm` 状态机观察冻结为 `V2-SM-OBS`，不再依据 reused holdout 调参。
4. Donchian core 与 VWAP satellite 分别做新增 forward 的单腿指标、方向、月度和尾部审计。
5. 当前数据的最近三个月已重复使用，下一次判断必须等待新增 fresh forward trades。
6. 在 fresh forward 通过前，不登记 V3，不进入 dry-run/live。

## 证据

- V2 搜索：`diagnostics/sol-1h-ar-high-win-target-search-2026-07-07.md`
- 收益结构改造：`diagnostics/sol-1h-ar-v2-mechanism-redesign-2026-07-10.md`
- 分段止盈与失效退出：`diagnostics/sol-1h-ar-v2-staged-exit-2026-07-10.md`
- 腿级 governor：`diagnostics/sol-1h-ar-v2-leg-governor-2026-07-10.md`
- VWAP 状态机：`diagnostics/sol-1h-ar-v2-vwap-state-machine-2026-07-10.md`
- 收益结构脚本：`scripts/research_sol_1h_ar_v2_mechanism_redesign.py`
- 分段退出脚本：`scripts/research_sol_1h_ar_v2_staged_exit.py`
- governor 脚本：`scripts/research_sol_1h_ar_v2_leg_governor.py`
- 状态机脚本：`scripts/research_sol_1h_ar_v2_vwap_state_machine.py`

