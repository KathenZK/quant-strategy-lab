# HYPE 1D MA7 利润退出后反手机会连续性预注册合同

> 冻结日期：2026-08-10。研究代号：`PEHC`（Profit-Exit Handoff Continuity）。状态：`explore / shadow-only / not promoted / not live-ready`。本合同承接OAPP H FAIL，但不修改exact V4、WTL或OAPP。

## 1. 已知问题与研究边界

OAPP的long MFE退出在旧H中把一笔long从亏损改为盈利，却因actual position提前转flat而失去exact V4三日后由原long protective stop触发的盈利forced short。PEHC研究的是“退出后状态权利连续性”，不是继续微调止盈阈值。

现有432日、旧D/V/H、TPR/WTL/OAPP的全部指标与交易均已researcher-exposed：

- exposed历史：`[0,432)`；允许机制诊断、宽搜、rolling和shadow候选选择；
- 旧H `[356,432)`：只能作已知失败案例，不能再次称为Validation/H/OOS；
- clean prospective起点：`2026-08-11T00:00:00Z`；最低裁决窗为从该时刻起连续`>=90`个新增完整UTC日，且满足第8节事件门。冻结数据的terminal open仍为`2026-08-06T00:00:00Z`，`2026-08-06`以后至前瞻起点以前的数据只可补齐shadow warm-up，不得进入参数选择或前瞻绩效。

唯一control仍为登记的exact V4 `1x`。PEHC不能登记V5、promotion或交接runner。

## 2. 固定OAPP层

PEHC固定而不重搜OAPP Development champion的两个模块：

- long fraction trail：activation `0.5ATR7`、MFE giveback `10%`、连续2日、`0.28%`gross profit guard；
- profitable short RSI：Wilder RSI6 `<20`连续2个实际持仓日、`0.28%`gross profit guard。

exact V4其余入场、native exit、intraday stop、forced reversal、cooldown、max hold、成本与funding不变。固定层只是研究起点，不因历史全窗优于V4而获得任何验证资格。

## 3. Shadow original-long 状态

每次actual long因OAPP long MFE exit成交时，同时创建不持有资金、不产生PnL/funding/cost的`shadow_original_long`：

- shadow继承该actual long在退出前的entry、quantity-independent价格状态、peak、原V4 long stop/trailing状态与cooldown上下文；
- 此后只用真实closed `1h`/日线继续模拟“若该long没有OAPP退出，exact V4会怎样”；
- shadow不得影响actual equity、MDD、仓位或信号；所有读写必须单独记账；
- shadow在expiry、原V4非反手型native exit、actual新开long、数据中断或被消费时立即清除；
- 同时最多一个shadow，禁止叠加、刷新或重复消费。

只有shadow exact V4发生本来会尝试forced reversal的intraday protective/trailing stop事件，才生成一次`handoff_opportunity`。普通MA7/slope/native exit不伪造反手机会。

## 4. Handoff 入场

handoff opportunity发生时，actual必须flat。决策只读当时已知上一完整日MA7/ATR7/slope；候选必须满足：

1. 该`1h` open严格低于上一完整日MA7（exact V4 MA-only底线）；
2. 距MA7的short向追价距离`(MA7-open)/ATR7`严格小于frozen cap；
3. 若启用short slope门，`-(MA7_t-MA7_{t-lookback})/ATR7_t`严格大于threshold；
4. execution timing按arm为同一真实`1h` open，或只允许下一UTC日open；若延迟期间条件失效则取消，不追单；
5. 成交后shadow消费，actual short沿用exact V4 short exit/cooldown/funding/cost。

如果actual非flat、数据非有限、超期、条件不满足或同一机会已消费，则只记录拒绝原因，不创建pending重试。

## 5. 冻结490个handoff组合

- shadow expiry calendar days：`{1,2,3,5,8,13,21}`；
- short slope：`OFF`或lookback固定1日、threshold `{0,0.01,0.02,0.04}`，共5档；
- anti-chase cap ATR：`{0.25,0.50,0.75,1.00,1.50,2.00,INF}`；`INF`只保留MA-only底线；
- execution：`same_1h_open`、`next_utc_open`。

总计`7×5×7×2=490`。另冻结控制：exact V4、固定OAPP、long-only、RSI-only、shadow-without-entry、handoff-without-RSI。所有490行和控制的错误、休眠、机会/接受/拒绝/过期计数必须持久化。

## 6. Exposed历史搜索与多轮消融

### 6.1 分层搜索

1. Stage A：490臂在完整`[0,432)`与8个blocked flat-start窗`[0,54)`、`[54,108)`、`[108,162)`、`[162,216)`、`[216,270)`、`[270,324)`、`[324,378)`、`[378,432)`运行，按完整经济路径去重；非零左界只作指标预热、资金与策略状态从下一日open重新flat-start；H区不得单独进入排序键。
2. Stage B：最多32条独立路径运行`8bps`、funding-off、12h phase和逐事件状态审计。
3. Stage C：最多16条做leave-one-out、keep-one-only、每参数上下邻居、最大增量episode剔除、去旧H案例后的`[0,356)`复核与旧H单列归因。

### 6.2 Shadow候选资格

仅可冻结一个`shadow candidate`，不得称champion/validated。至少要求：

- all-off与exact V4、handoff-off与固定OAPP逐笔parity；
- 全历史与`[0,356)`中收益高于V4且真实1h MDD更小，至少一项material；
- 8bps非双劣、funding-off非破产；
- 至少3个独立handoff opportunity、2次接受，且接受事件跨至少2个blocked窗；
- 关闭handoff后路径改变；剔除最大正增量handoff后总增量仍为正；
- 至少一个相邻参数经济路径也满足上述主方向；
- 12h phase与冻结外部迁移只作反证：任一发生破产或机制性账本错误即淘汰，绩效不用于宣称OOS。

排序只用全历史与blocked aggregate的最差收益/MDD差、机会覆盖、较低复杂度和ID；旧H绩效不得单独加权。

## 7. 外部迁移

在可获得且数据质量通过时，冻结后对BTCUSDT、ETHUSDT同周期进行零调参机制迁移；若exact V4基础在该资产没有同类事件，则标记`NOT_APPLICABLE`，不得据此补样本。迁移只检验状态机与机会方向，不把其他资产收益冒充HYPE final。

## 8. Clean prospective 最终门

shadow参数、实现SHA、数据截止与观察协议冻结后，HYPE新增数据不得回填调参。最早裁决必须同时满足：

- `>=90`个新增完整UTC日；
- exact V4与PEHC各至少5笔闭合交易；
- long与short各至少2笔；
- 至少2个handoff opportunity且至少1次实际接受；不足则`INSUFFICIENT`并继续等待，不判PASS；
- base成本后收益严格高于exact V4、真实1h MDD严格更小，且收益差`>=5pp`或MDD改善`>=2pp`；
- 8bps不双劣、funding-off非破产、账本一致、handoff真实激活且路径改变。

FAIL后不得改参数继续使用同一前瞻窗；只能冻结materially new机制并从更晚起点重新积累。

## 9. 杠杆

前瞻1x PASS之前不运行、不选择、不解释杠杆。PASS后才预注册target和actual marked leverage都不超过3x的fixed/dynamic网格；固定数量导致marked leverage漂过3x的臂必须在入场时动态再平衡或直接淘汰。按20/25/30/35/40/50% MDD预算报告，但风险缩放不能救援1x失败。

## 10. 证据与测试

实现前测试至少覆盖：shadow与actual资金隔离、精确V4 counterfactual parity、expiry边界、同小时/次日时序、MA equality、slope equality/nonfinite、anti-chase strict cap、actual非flat拒绝、单次消费、数据中断清除、成本/funding、破产、blocked flat-start、490枚举、H区不单独排序与前瞻截止锁。

Artifact前缀固定为`hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10`；JSON/HTML独占写入并带SHA256 sidecar。完整逐笔HTML必须区分actual交易、shadow生命周期、handoff机会/拒绝/接受和exact V4控制。
