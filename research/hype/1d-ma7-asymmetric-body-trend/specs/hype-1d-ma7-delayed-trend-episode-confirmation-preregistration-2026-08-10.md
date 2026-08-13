# HYPE-1D-MA7延迟趋势episode确认预注册合同

> 冻结日期：2026-08-10。研究代号：`DTEC`（Delayed Trend Episode Confirmation）。主状态：`explore / not promoted / not live-ready`。用户在首次运行DTEC绩效前明确主对照必须为V6，本合同据此修订并冻结；不修改V4、V5、V6或CTLS既有文件。

## 研究问题

本轮只回答一个交易问题：价格已经发生严格MA7 cross，但当日没有满足V6继承的V4自然入场；fresh事件随后过期，而价格继续在MA7同一侧慢涨或阴跌时，能否在exact V6上用一个有起点、有取消条件的episode补入场，同时提高收益并降低回撤。

这不是逐日十状态分类，不使用LightGBM，也不是任何时刻都可入场的persistent regime。

## 唯一对照与V6继承

- 对照为固定实现SHA、配置SHA与数据SHA的exact `HYPE-1D-MA7-Asymmetric-Body-Trend-V6 / PEHC_294`；
- exact V6完整包含V5固定OAPP：long `0.5ATR/10%/2d` MFE利润保护、short RSI6 `20×2`盈利止盈与`0.28%`guard；
- exact V6完整包含`PEHC_294`：8日shadow、MA-only、下一UTC日复核、无额外slope与anti-chase；配置SHA为`b155a35133224e77266ba0c22fb84ba1657ab89212a700e9f551b3fa3431af00`；
- V6继承的V4自然long/short入场、退出、保护、强制反手、cooldown、单仓、固定`1x`、funding与成本全部不变；
- DTEC信号只在账户flat、cooldown为0、没有PEHC handoff成交且V6当日没有自然入场时有机会生效；
- PEHC handoff与V6自然信号始终优先，DTEC不得覆盖、延后或替换它；DTEC实际开long时按V6原规则取消仍活跃的shadow，开short导致后续handoff因actual nonflat被拒绝时必须如实记录。

## Episode状态机

在完整UTC日`t`收盘后，用当日及更早数据决策，最早于`t+1`日open成交。

### 启动

- long raw cross：`close[t-1] <= SMA7[t-1]`且`close[t] > SMA7[t]`；
- short raw cross：`close[t-1] >= SMA7[t-1]`且`close[t] < SMA7[t]`；
- 若同日V6继承的自然信号已通过，直接按V6处理，不建立DTEC episode；
- 否则只为启用方向建立一个episode，记录`side/armed_index/age/same_side_run`。

### 持续与取消

- 只要`side × (close-SMA7) > 0`，episode继续，`same_side_run`逐日增加；
- 再次到达或穿回MA7，即`side × (close-SMA7) <= 0`，立即取消；
- 出现相反raw cross时，旧episode取消，并可为启用的相反方向建立新episode；
- `max_age_days>0`时，`age>max_age_days`取消；`max_age_days=0`表示只由再cross取消；
- 持仓和cooldown期间不建立、续期或跨越保存episode。

### 延迟确认

episode至少经过一个后续完整日，且同时满足：

1. `same_side_run >= persistence_days`；cross日计作第1日；
2. `side × (SMA7[t]-SMA7[t-L]) / ATR7[t] >= slope_min_atr`；
3. `0 < side × (close[t]-SMA7[t]) / ATR7[t] <= max_distance_atr`；
4. 当日没有V6继承的自然long或short信号，也没有PEHC handoff成交。

满足后只消费一次episode，下一UTC日open按V6同一侧配置建立仓位。此后所有OAPP、PEHC、退出、保护和cooldown完全沿用V6。

## 冻结参数面

Stage A按long-only与short-only独立搜索，每侧`576`项：

- `persistence_days ∈ {2,3,4,5}`；
- `slope_lookback ∈ {2,3,5}`；
- `slope_min_atr ∈ {0.00,0.01,0.02,0.04}`；
- `max_distance_atr ∈ {0.75,1.00,1.50}`；
- `max_age_days ∈ {5,10,20,0}`，其中0为直到再cross；
- 另一侧DTEC关闭，但该侧exact V6仍完整保留。

不搜索MA长度、退出、stop、trail、RSI、仓位、成本或杠杆。

## 数据、窗口与成本

- Binance USD-M `HYPEUSDT` perpetual；accepted `1h`聚合完整UTC日；冻结book为432日；
- Development：`D=[0,324)`；
- D内六个cold-flat block：`[0,54)`、`[54,108)`、`[108,162)`、`[162,216)`、`[216,270)`、`[270,324)`；非零起点的首个可执行open为`start+1`，与exact V4公平一致；
- 一次性exposed evaluation：`LES=[324,432)`；只有唯一D champion冻结后才运行；
- 现有432日全部已被研究者查看，D/LES均只能提供researcher-exposed诊断，不是clean OOS；
- 手续费`0.001/fill`、基准不利滑点`4 bps/fill`、压力`8 bps/fill`、真实event-time funding；
- 用逐笔账本在真实`1h` open与funding事件上重放chronological MDD；daily-extreme MDD只作并列审计；
- exact V6全432日冻结锚点为净收益`+617.11%`、chronological MDD `-18.39%`、19笔；manifest必须逐位复现后才能读取DTEC绩效。

## Stage A：单侧搜索

### A1全D

每侧576项均运行D-full。保留至少触发一次可评估delayed confirmation的路径；按以下固定顺序各取24项进入A2：

1. D-full收益与chronological MDD是否同时优于V6；
2. 5日趋势识别precision；
3. 收益增量；
4. MDD改善；
5. 参数复杂度与配置id。

### A2分段与成本

48项运行六个cold-flat block与8bps D-full。每侧按以下顺序固定4项：

1. D-full及六折合成相对V6不双劣；
2. 有效5日趋势识别precision；
3. 最差block收益增量；
4. 六折合成收益增量、MDD改善；
5. 复杂度与配置id。

Stage A只是父配置筛选，不产生champion。

## Stage B：双侧组合

4个long父项×4个short父项=`16`项，分别运行D-full、六个cold-flat block与8bps D-full。不得从A1/A2落选项替补。

### 趋势识别准确率

对每个DTEC确认日`t`，若`t+5`仍在窗口内：

- `direction_hit`：`side × (close[t+5]/close[t]-1) > 0.0028`；
- `persistence_hit`：未来5个收盘中至少3个仍严格位于MA7同方向；
- `trend_hit = direction_hit AND persistence_hit`；
- precision为`trend_hit / 可评估确认数`，按long、short和combined分别报告；
- capture rate为`可评估确认数 / 可评估raw-cross episode数`，只作覆盖审计，不设高覆盖奖励。

该未来5日标签只用于离线评估，绝不进入信号。

### D硬门

唯一champion必须同时满足：

1. D-full净收益严格高于V6，chronological MDD严格更小；
2. 六折复合净收益严格高于V6，六折worst MDD严格更小；
3. 物质性：收益至少提高`5pp`或MDD至少改善`2pp`；
4. 8bps D-full不得在收益与MDD上同时劣于V6；
5. D-full至少4个可评估DTEC确认，long/short各至少2个；
6. combined precision `>=0.55`，long与short precision各`>=0.50`；
7. 至少4/6个block中DTEC有实际激活，且任一block不得收益和MDD同时劣于V6；
8. 非破产、账本/成本/funding/逐笔重放一致，经济路径相对V6发生改变；
9. V6原OAPP与PEHC模块仍保持接线：全D存在相应机会时，关闭DTEC必须逐笔回到exact V6，DTEC不得静默关闭handoff或RSI/MFE退出。

多项通过时依次按最差block收益增量、六折MDD改善、D收益增量、combined precision、复杂度排序，只冻结第一名；其他项不能在LES失败后替补。

## LES与裁决

冻结唯一D champion后才允许一次运行LES：

- 候选与V6各至少2笔平仓；
- 候选净收益严格更高、chronological MDD严格更小；
- 8bps不双劣；
- 至少1个可评估DTEC确认且precision不低于`0.50`；
- 非破产、路径变化、账本一致。

LES任一门失败即`HARD-GATE-FAILED`。本轮不使用杠杆救援；即使D与LES都通过，因全部432日已暴露，也只冻结1x观察候选并要求新增clean prospective，不登记V7、不promotion。

## 输出

- 冻结manifest与实现/data SHA；
- A1/A2/B所有行、错误行与排序证据；
- 每个入选路径的episode arm/cancel/expire/confirm事件与5日标签；
- exact V6/候选逐笔差异、V6 shadow/handoff交互、真实成本、funding、chronological MDD和六折路径；
- 只有D champion存在时才生成完整可缩放D交易路径HTML；LES通过后才生成全窗观察HTML；
- 失败则输出因果复盘并同步README、core ledger与decision log。
