# HYPE 1D MA7持续趋势生命周期状态机预注册合同

> 冻结时间：2026-08-10。分支代号：`CTLS`（Continuous Trend Lifecycle State）。本合同签署时不运行CTLS历史候选；现有432日对V4/V5/V6均已暴露，只能用于诊断开发和拒绝候选，不能宣称clean OOS。

## 1. 研究问题与身份边界

目标是在`HYPE-1D-MA7-Asymmetric-Body-Trend`家族内另立尚未登记的CTLS分支，把趋势方向状态与真实仓位拆开，持续识别：

- 慢涨、慢跌；
- 已建立上升/下降趋势；
- 上升/下降加速；
- 上升/下降减速；
- 方向反转；
- 震荡与无方向状态。

CTLS不是V6静默改参，也不继承V6版本号。冻结`HYPE-1D-MA7-ABT-V4/V5/V6`为三个独立对照；只有本合同全部1x门禁和后续clean prospective通过，用户才可另行决定是否登记新版本。登记、promotion、live spec、runner和杠杆均不由本合同自动授权。

## 2. 数据、成本与可见性

- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 源：仓库标准化连续`1h` OHLCV与event-time funding；聚合完整UTC日。
- 冻结输入截止：hourly `2026-08-06T07:00:00Z`，funding `2026-08-06T08:00:00Z`。
- 已暴露完整日：`432`，索引`[0,432)`；terminal open只用于成交，不伪造未来OHLC。
- 成本：手续费`0.001/fill`，base不利滑点`4 bps/fill`，stress `8 bps/fill`，计实际funding；funding-off只作压力审计。
- 仓位：单账户、单方向、非加仓、目标`1x`；成交后数量固定至退出或反手。
- 信号：只读取已闭合UTC日和已经发生的`1h`；日线决策最早下一UTC日open成交。保护止损使用真实`1h`顺序、跳空按首个可执行open处理。
- 回撤主口径：真实`1h`时间顺序权益MDD；日极值MDD只作兼容审计。

任何缺口、重复、非有限OHLC、funding边界错误、账本不守恒、破产后恢复或源码pin漂移均fail closed。

## 3. 冻结窗口与访问顺序

现有历史全部标为`researcher-exposed`，但仍按下列顺序减少新一轮路径追逐：

1. Development：`D=[0,324)`，由6个连续、cold-flat、各54日block组成；只在D搜索和排名。
2. Locked Exposed Stress：`LES=[324,432)`；候选、配置SHA、实现SHA、OAT与D证据冻结后只运行一次。LES只能拒绝，不能称validation/OOS。
3. Exposed full：`[0,432)`；LES之后只用于最终诊断、逐笔图与对照归因，不参与替补。
4. Clean prospective：从`2026-08-11T00:00:00Z`后第一个新增完整UTC日起；沿用outcome-locked最早样本合格terminal，不允许选择运行日。

LES失败后不读取其他CTLS配置的LES，不降低门槛、不替补。后继机制必须写新合同并使用更晚的prospective起点。

## 4. 因果特征

在完整日`t`收盘后计算，所有分母使用当日已知`ATR7_t`：

```text
z_t   = (close_t - SMA7_t) / ATR7_t
s1_t  = (SMA7_t - SMA7_{t-1}) / ATR7_t
s3_t  = (SMA7_t - SMA7_{t-3}) / (3 * ATR7_t)
d3_t  = (close_t - close_{t-3}) / (3 * ATR7_t)
er7_t = (close_t - close_{t-7}) / sum(abs(close_i-close_{i-1}), i=t-6..t)
a_t   = s1_t - s3_t
```

`er7`在分母为0时固定为0。特征不读取`t+1`；未来路径只允许出现在离线评估标签中，绝不进入策略X或状态转换。

## 5. 方向证据与持续状态

对`side∈{+1,-1}`，四项证据为：

```text
side*z_t  > distance_min
side*s3_t > slow_slope_min
side*d3_t > drift_min
side*er7_t > er_min
```

通过项数为`score(side,t)`。方向状态独立于真实仓位，每个完整日都更新：

- flat方向连续`enter_confirm_days`满足`score>=direction_score_min`后进入该方向；
- 已有方向在`score<hold_score_min`连续`exit_confirm_days`后转neutral；
- 相反方向连续`reverse_confirm_days`满足入场分数后直接翻转方向状态；
- 同日两侧打平时保持原方向；原方向为flat则neutral；
- 非连续日期、非有限输入或ATR非正立即清空未完成确认并fail closed，不携带旧证据穿越数据中断。

这使cross与slope不必同日成立，也使账户持仓/cooldown期间仍能观察趋势，而不会把旧cross无限armed。

## 6. 冻结趋势阶段

方向为flat时：

- 最近5日MA7侧别翻转至少3次且`abs(er7)<0.15`：`CHOP`；
- 其余：`NEUTRAL`。

方向为`side`时，按优先级唯一归类：

1. `side*a_t > 0.03`且`side*s1_t > 0.03`：`ACCELERATING`；
2. `side*a_t < -0.03`或`score(side,t)<direction_score_min`：`DECELERATING`；
3. `side*s3_t < 0.08`：`SLOW`；
4. 其余：`ESTABLISHED`。

输出为`UP/DOWN × {SLOW,ESTABLISHED,ACCELERATING,DECELERATING}`加`CHOP/NEUTRAL`共10类。阶段只由因果状态决定；交易动作不得反向修改阶段历史。

## 7. 交易层

- flat且方向为long/short、阶段不是`DECELERATING`时可在下一UTC日open入场；成交前重新检查实际flat、pending时效和价格有限。
- 入场须满足`abs(z_t)<=chase_cap_atr`；`INF`表示关闭anti-chase。
- 方向状态确认反转时，下一open原子平仓并反手，计两个fill。
- 方向转neutral时，下一open退出到flat。
- deceleration退出按搜索配置决定；只允许`OFF/1d/2d`连续确认，不能单日盘中偷看。
- same-side reentry按`OFF/CONTINUATION/PULLBACK_RESUME`：后两者仅在真实退出后、方向状态仍保持、冷却结束且不追价时允许；`PULLBACK_RESUME`还要求上一日阶段为decelerating或价格回到`abs(z)<=0.5`后重新进入非decelerating阶段。
- 冷却时序在首次绩效读取前固定：保护止损、减速退出或盈利保护退出后，必须完整等待一个UTC日收盘，最早在再下一日open同向再入；方向丢失退出必须等方向状态重新确认，不得依赖旧方向再入；确认反转采用原子反手，不进入冷却。冷却天数不进入Stage B/C搜索。
- 保护止损、MFE与RSI模块由Stage C冻结组合决定；任何盈利退出都不得删除方向状态，但是否允许same-side reentry严格由上述配置控制。
- terminal有pending时只抑制，不使用未来数据强制创建新仓；真实遗留仓按统一terminal flatten审计，不把该成交用于新信号样本。

## 8. 离线趋势阶段标签与准确性

标签只评估、不参与交易。对有`t-3..t+3`完整数据的日期：

- 用7点中心线性回归斜率`beta7/ATR7`和`R²`定方向；`abs(beta)<0.08`或`R²<0.35`时，中心7日相对SMA7侧别翻转至少3次标为`CHOP`，否则标为`NEUTRAL`；
- 方向成立后，以过去3日斜率和未来3日斜率之差判阶段：方向化差值`>0.10`为accelerating，`<-0.10`为decelerating；否则`abs(beta)<0.20`为slow，其余established；
- 标签窗口越过评估段终点的日期从该段准确性统计剔除。

冻结指标：10类macro-F1、方向balanced accuracy、slow-up recall、slow-down recall、accelerating/decelerating macro-F1、每日状态flip率。交易收益与标签准确率分别报告，不能用其中一个代替另一个。

## 9. 搜索空间与顺序

### Stage A：纯状态识别，324项

```text
distance_min       ∈ {0, 0.10, 0.25}
slow_slope_min     ∈ {0, 0.01, 0.02}
drift_min          ∈ {0, 0.05, 0.10}
er_min             ∈ {0.10, 0.20, 0.30}
direction_score_min∈ {2, 3}
enter_confirm_days ∈ {1, 2}
```

固定`hold_score_min=1`、`exit_confirm_days=2`、`reverse_confirm_days=2`。Stage A不运行PnL，按6个D block的最差方向准确率、macro-F1、slow双向召回、flip率及复杂度确定最多24条独立状态路径；path-equal只保留最低复杂度。

### Stage B：生命周期交易，最多3,888项

对最多24个Stage A父项搜索：

```text
exit_confirm_days   ∈ {1,2,3}
reverse_confirm_days∈ {1,2}
chase_cap_atr       ∈ {0.75,1.5,INF}
same_side_reentry   ∈ {OFF,CONTINUATION,PULLBACK_RESUME}
decel_exit_days     ∈ {OFF,1,2}
```

Stage B使用固定`2.5ATR`双侧hard stop、保护后只转flat、不加MFE/RSI。按D收益/MDD、6-block稳定性、成本、交易样本和状态准确性筛到最多16条独立经济路径。

### Stage C：风险与退出，最多864项

对最多16个Stage B父项搜索：

```text
hard_stop_atr ∈ {1.5,2.5,OFF}
trail_atr     ∈ {1.5,2.5,4.0}
long_oapp     ∈ {OFF,V5_FIXED}
short_rsi     ∈ {OFF,20x2,25x2}
```

trail以入场后已实现最高/最低真实`1h`价格更新，跳空优先；`V5_FIXED`严格使用`0.5ATR/10%/2d/0.28% guard`。Stage C不得新增entry特征或改变标签。

随后对最终池做：逐模块OAT、相邻参数、8bps、funding-off、额外12h执行延迟、6个cold-flat block、最大赢家leave-one-out、phase-hour诊断和路径/账本一致性。任一启用模块必须在D有真实激活且关闭后路径变化。

## 10. 排名与1x硬门

### Stage A准确性门

- D aggregate方向balanced accuracy `>=0.55`；
- 10类macro-F1 `>=0.35`；
- slow-up与slow-down recall各`>=0.35`；
- accelerating/decelerating macro-F1 `>=0.25`；
- 每日方向flip率`<=0.15`；
- 6个block中至少4个方向balanced accuracy `>=0.50`。

### D交易门

候选必须相对同窗V4、V5、V6三个冻结控制中的最强者同时满足：

- base净收益至少高`5pp`；
- 真实`1h` MDD至少改善`2pp`；
- 8bps下仍同时收益更高、MDD更小；
- 6个54日block至少4个收益更高，收益差中位数`>0`，最差block MDD不差于最强控制；
- 至少12笔闭合交易，long/short各至少4笔；由`SLOW`阶段发起的long/short各至少2笔；
- 非破产、PF有限、账本守恒、成本/funding与fill数一致。

通过D门后按“最差block收益差、D收益差、MDD改善、macro-F1、复杂度、config hash”确定唯一候选并冻结，不允许人工选第二名。

### LES一次性门

LES候选必须相对三个控制中的最强者：净收益严格更高、真实`1h` MDD严格更小，且收益差`>=3pp`或MDD改善`>=1pp`；至少2笔闭合交易、状态路径非空、8bps不双劣、无破产。失败即停止，不替补、不研究杠杆。

## 11. Clean prospective与杠杆

即使D和LES通过，CTLS也只能冻结为shadow candidate。clean prospective最早裁决须同时满足：

- 至少90个新增完整UTC日；
- 候选与每个控制各至少5笔闭合交易，候选long/short各至少2笔；
- slow-up/slow-down状态各至少10个有效标签日，加速/减速各至少5日；
- base下相对最强控制收益严格更高、真实`1h` MDD严格更小，收益差`>=5pp`或MDD改善`>=2pp`；
- 8bps、账本、状态准确性和路径门全部通过。

只有clean prospective的1x门`PASS`后，才可冻结`<=3x`杠杆审计合同。届时最多比较固定`1.25/1.5/2/3x`与预注册波动率目标动态杠杆；必须建模maintenance margin、liquidation fee、资金费、目标漂移和延迟压力。杠杆不能改变1x候选身份或救援1x失败。

## 12. 失败后的唯一允许路径

- Stage A失败：先归因是标签不可分、慢趋势召回不足还是状态churn；另立新特征合同，不读LES。
- D交易门失败：保存全部trial和模块归因；不得用收益反向改标签阈值。
- LES失败：一次性锁死；后继须materially new且使用更晚prospective起点。
- Prospective失败：保留V4/V5/V6注册身份，CTLS不登记、不promotion；不能在同一未来窗调参重测。

## 13. 必备交付

- 预注册manifest、源码/数据SHA与自检证据；
- Stage A/B/C全trial与错误/跳过行；
- 唯一候选或明确NO-CANDIDATE裁决；
- 状态混淆矩阵、分阶段召回、逐模块OAT、逐笔与路径归因；
- 候选/V4/V5/V6完整自包含可缩放HTML，显示10类状态、交易连线、权益和事件；
- 中文诊断、消融、core ledger与decision log更新；
- 明确`registered`、`not promoted`或等待prospective结论，不使用含糊“优化成功”。
