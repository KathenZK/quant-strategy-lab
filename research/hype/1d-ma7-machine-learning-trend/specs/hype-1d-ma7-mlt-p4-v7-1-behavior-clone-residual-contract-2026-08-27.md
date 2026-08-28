# HYPE-1D-MA7-MLT P4 V7.1 行为克隆与残差超越冻结合同

## 1. 身份、问题与边界

- Family：`HYPE-1D-MA7-Machine-Learning-Trend`（`HYPE-1D-MA7-MLT`）。
- 实验：`P4 V7.1 Behavior Clone + Residual Overlay`；不修改、重命名或晋升冻结的 `HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1`。
- 教师：必须直接调用 V7.1 冻结 engine/config，禁止用“类似 MA7”的简化规则代替。
- 问题分两级：先检验模型能否复刻 V7.1 的日线动作；再检验只用训练期标签学习的残差，能否在相同交易机会、时点、成本和 `1x` 下超过 V7.1。
- 小时级 protective stop / stop reversal / PEHC 安全状态继续由冻结教师引擎负责，不把事后小时路径作为日线模型特征，也不声称 P4 已成为独立可执行策略。
- 状态固定为 `explore / diagnostic-only / not promoted / not live-ready`。

## 2. 数据隔离

- 市场：Binance USD-M `HYPEUSDT` perpetual；可信连续 `1h` OHLCV 聚合完整 UTC `1d` K，真实 funding。
- 全窗 446 个完整日；前 365 日是唯一训练/开发期，后 81 日是已经被 P0-P3 揭示的 `reused holdout`。
- 所有特征、标签、模型、阈值、候选残差臂和选择规则在本合同中先冻结。开发程序仅允许教师引擎运行 `[0, 365)`；标签所需的未来数据不得越过第 365 日。
- 训练期教师交易按开仓顺序固定拆为：前 13 笔用于拟合残差，余下交易作一次训练期内部时间确认；该确认不得回流重选特征或阈值。
- `develop` 必须输出冻结 manifest 与 SHA256。`validate` 必须先校验 manifest，并严格按 manifest 在 365 日重训后，才允许读取后 81 日；验证结果揭示后不得静默再训练 P4。

## 3. 教师动作与行为克隆

### 3.1 教师动作

V7.1 每个日线收盘状态产生下一执行时点的动作标签：

`FLAT / HOLD_LONG / HOLD_SHORT / ENTER_LONG / ENTER_SHORT / EXIT_LONG / EXIT_SHORT / REVERSE_LONG_TO_SHORT`。

- 日线计划动作包括原生 long/short entry、OAPP long exit、MA7 slope exit、short RSI take-profit、max-hold 和 PEHC handoff。
- 小时级 protective 动作标为 `SAFETY_DELEGATE`，不作为模型可预测标签；terminal 也不参加拟合。
- 第 365 日之后的动作不得成为训练标签。

### 3.2 因果特征

只读取动作决策时已经存在的信息：

1. 市场结构：`close/MA7/ATR7` 距离、MA7 一日/二日/三日方向斜率、实体、收盘位置、range/ATR、1/3/7 日收益、ER7、RSI6、ATR/close、14 日穿越次数；
2. 教师状态：当前方向、持有天数、距上次平仓天数、未实现收益、MFE、MAE、giveback、V7.1 的 long/short/RSI 连续确认计数；
3. PEHC 状态：shadow 是否活动、shadow 年龄、origin side、handoff/recheck 状态。它们只能由截至当日已经发生的教师状态转移构造。

禁止输入未来收益、未来最高/最低价、当前交易最终盈亏、最终 exit reason 或验证期统计。

### 3.3 固定模型与复刻指标

- 模型：`SimpleImputer(median) + ExtraTreesClassifier(n_estimators=500, max_features=None, min_samples_leaf=1, class_weight=balanced, random_state=20260827)`；无特征块搜索、无阈值搜索。
- 同时报告：完整训练集 accuracy、transition recall、macro-F1、混淆矩阵；以及按时间 expanding OOF 的同组指标。
- `transition` 指非 `FLAT/HOLD_LONG/HOLD_SHORT` 动作。
- 复刻门禁：完整 365 日训练集 action accuracy `>= 0.99` 且 transition recall `= 1.00`。这只证明“能拟合教师轨迹”，不证明泛化。
- expanding OOF 只用于揭示时间泛化能力，不以训练集内高分掩盖；若 OOF transition recall `< 0.50`，必须明确标记 `CLONE_GENERALIZATION_WEAK`。

## 4. 残差超越模型

P4 不重新发明入场。每笔候选交易的开仓时间、方向及小时级安全动作均来自 V7.1 教师。固定训练两个低自由度二分类器：

### 4.1 Trade filter

- 样本：V7.1 每笔已平仓训练期交易。
- 标签：该笔教师交易在原始时点与相同成本/funding 下净收益是否为正。
- 入场前特征：方向对齐 MA7 距离、1/2/3 日斜率、实体、收盘位置、RSI6、ATR/close、ER7、14 日穿越次数、entry 是否 PEHC、此前最后一笔教师交易收益。
- 模型：`SimpleImputer(median) + StandardScaler + LogisticRegression(C=0.05, L2, class_weight=balanced, random_state=20260827)`；固定接受阈值 `0.50`。
- 若某个拟合窗口标签只有单一类别，模型退化为该窗口的固定类别概率；这属于预先声明的可识别性保护，不新增参数搜索。
- 被拒绝的教师交易保持空仓；教师仍在 shadow 中继续推进状态并提供下一笔独立机会。

### 4.2 三日 exit extension

- 仅对 V7.1 的日线计划退出（OAPP、MA7 slope、short RSI、max-hold）建样本；protective stop、reversal、terminal 永不延迟。
- 标签：从教师原计划退出价继续保持原方向，到第三个后续 UTC open 的方向收益是否为正；标签终点必须留在训练期。
- 特征：退出前方向对齐 MA7 距离、1/2/3 日斜率、1/3 日收益、实体、RSI6、ATR/close、未实现收益、MFE、giveback、持有天数，以及固定 exit-reason one-hot。
- 模型与阈值同 trade filter。概率 `>=0.50` 时延迟到第三个后续 UTC open；若更早遇到下一笔教师交易开仓，则先在该开仓时点退出，避免重叠；不改变入场。

### 4.3 固定候选与训练期选择

仅比较三个预先声明的臂：

1. `FILTER_ONLY`；
2. `EXTEND_ONLY`；
3. `FILTER_AND_EXTEND`。

- 前 13 笔教师交易拟合后，只在其后的训练期交易上做一次顺序确认。
- 候选选择规则：内部确认 terminal equity 最高；相差不超过 `0.5%` 时优先 `EXTEND_ONLY`，再 `FILTER_ONLY`，最后 `FILTER_AND_EXTEND`；仍同分时选 1h MDD 更浅者。
- 若所有候选都未超过同段 V7.1，P4 裁决 `RESIDUAL_TRAINING_FAILED`，不得打开 81 日验证来救结果。
- 若内部确认胜出，则按冻结候选用全部合格训练交易重训，并写入 manifest；训练期完整拟合收益和内部确认收益必须分别报告，禁止混为一谈。

## 5. 公平回放与最终裁决

- 所有臂固定 `1x`、单仓、不加仓；fee `0.10%/fill`、不利 slippage `0.04%/fill`，另计真实 funding。
- 回放使用 V7.1 同一 `1h` mark/funding 时间轴，报告收益、chronological 1h MDD、PF、胜率、交易数、long/short、暴露、换手、成本、funding、逐笔变化和最近 `1d/7d/1m/3m/6m/1y`。
- 只有行为克隆训练门禁和残差内部确认门禁同时通过，才执行一次 reused-holdout 对决。
- 验证胜过 V7.1 的条件：残差臂净收益严格更高、chronological 1h MDD 不更差超过 `2 pct`、且不是靠更高杠杆；否则 `V7_1_NOT_BEATEN`。
- 即使通过，也只记 `EDUCATIONAL_REUSED_HOLDOUT_WIN`；由于验证窗已反复揭示、教师状态仍是策略依赖，不得登记为可交易版本或 promotion。

## 6. 必须留存的证据

- 合同、教师 source/config hashes、训练期教师逐日状态与动作、clone 全样本与 OOF 预测、残差训练样本、内部确认逐笔对照、冻结 manifest、最终摘要、逐笔交易和所有产物 SHA256。
- 报告必须把“训练集记忆能力”“训练期时间泛化”“残差是否超越”“81日 reused-holdout”分成四栏，不得只汇报最后一栏。
