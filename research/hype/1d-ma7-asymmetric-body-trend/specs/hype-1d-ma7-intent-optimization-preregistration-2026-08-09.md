# HYPE 1D MA7 原始意图优化预注册合同

> 冻结日期：2026-08-09。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 1. 身份、目标与禁止事项

本合同建立一条新的诊断机制，用来回答以下问题：固定 `SMA7` 的新鲜穿越、有限 armed 等待、ATR 归一化斜率持有、双侧 ATR 容错和 RSI6 空头止盈能否组成一套因果、可执行且相对登记 V4 有增量的日线趋势状态机。

本合同：

- 不是 `HYPE-1D-MA7-Asymmetric-Body-Trend-V5`；
- 不是对登记 V4 的静默调参，V4 参数、身份、逐笔路径和历史结论均不得改写；
- 不授权登记、promotion、live spec、runner、dry-run 或 live；
- 不允许把 `V` 或 `H` 揭盲后的结果用于扩展网格、改变公式、改变优先级、增加过滤或救回失败候选；
- 不写入任何候选历史结果。所有候选结果只能在合同冻结后生成并进入独立 diagnostics / ablations / artifacts。

Exact V4 仅作为基准，必须用它自己的冻结状态机、执行路径和成本模型在相同窗口重新运行；不得把新机制的状态转换套给 V4，也不得用全期摘要代替分段重算。

## 2. 数据快照与共同口径

### 2.1 冻结样本

- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 基础数据：accepted、closed-only 的真实 `1h` K 线聚合完整 UTC 日 K；funding 使用真实事件时间和 rate。
- 冻结日线样本数：`432`，索引为 `[0, 432)`。
- 日线首日：`2025-05-31 UTC`；索引 `432` 对应 terminal open `2026-08-06 00:00 UTC`。
- 运行前必须记录 raw / normalized 数据文件、研究脚本和 exact V4 实现的路径、SHA-256、最后闭合时间、缺口、重复、关键空值及 OHLC 校验。任一 blocker 出现即停止研究，不得带病搜索。

### 2.2 指标

- `SMA7[t] = mean(close[t-6:t])`，包含日 `t` 已闭合的 close。
- `TR[t] = max(high[t]-low[t], abs(high[t]-close[t-1]), abs(low[t]-close[t-1]))`。
- `ATR7[t] = mean(TR[t-6:t])`，为七日简单移动平均。
- `RSI6` 使用 Wilder / TradingView 口径：up/down change 分别以 `alpha=1/6` 的 Wilder RMA 平滑，首个值以六期简单平均初始化；边界值处理和缺失值处理必须在实现测试中固定。
- 所有日线信号只读取截至日 `t` 收盘已经闭合的数据，最早于 `t+1` open 成交。

### 2.3 仓位、成本与方向

- 单仓、非加仓；每次入场按成交后权益建立约 `1x` 目标，持仓期间数量固定。
- 手续费 `0.001/fill`；基准不利滑点 `4 bps/fill`；压力不利滑点 `8 bps/fill`。
- funding 只在真实持仓区间结算。
- 原子反手是平旧仓和开新仓两次独立 fill，分别计手续费、滑点和 turnover。
- `side=+1` 表示 long，`side=-1` 表示 short。
- 双重支配门使用统一的 `gate MDD`，不得直接比较两套冻结回测器原生但不同粒度的 MDD：exact V4 的冻结口径是在每个完整 UTC 日内按 `favorable extreme -> adverse extreme -> close` 更新 peak/drawdown；候选须由独立 ledger replayer 按完全相同的整日极值顺序重算 `v4_compatible_daily_extreme_mdd_pct`。候选原生逐小时 MDD 只作为额外风险审计，不能用于排名或过门。
- 候选 gate-MDD replayer 必须用同一逐笔 action、两次 fill 反手、费用、funding 和 terminal flatten 重放，并与原回测的 terminal equity、turnover、cost、funding 逐项对上；任一不一致、R0 出现非日开 action 或原生 `bankrupt=true` 均 fail closed。

## 3. 固定切分与揭盲边界

所有索引均以本合同的 `432` 根冻结日线为准。日期右端写作 terminal open；实际可交易日索引采用左闭右开区间。

| 角色 | Raw / eval 索引 | 可交易起点 | Terminal open | 用途 |
| --- | --- | --- | --- | --- |
| `D` development | `[0,259)` | `2025-05-31` | `2026-02-14` | 结构消融、全部搜索、排序 |
| `V raw` | `[259,346)` | `2026-02-14` | `2026-05-12` | 只提供 purge 与 validation 边界 |
| `V eval` | `[269,346)` | `2026-02-24` | `2026-05-12` | 一次性 validation 揭盲 |
| `H raw` | `[346,432)` | `2026-05-12` | `2026-08-06` | 只提供 purge 与最终边界 |
| `H eval` | `[356,432)` | `2026-05-22` | `2026-08-06` | 一次性 locked retrospective OOS 揭盲 |

`[259,269)` 与 `[346,356)` 是固定 `10d` purge：不得计入参数拟合、排名或区间绩效。运行 `V/H` 时可以因果读取 purge 内已经闭合的 K 线作为指标 warm-up，但必须从 eval 起点 flat-start，不能把早先仓位、armed、RSI 连续计数、slope-loss 连续计数或未完成订单带入 eval。

为统一两套冻结回测器的 flat-start 首开语义：新候选从 eval 索引 `s` 的 close 首次形成决策，最早在 `s+1` open 入场；exact V4 对所有 `s>0` 的分段比较也禁止消费 `s-1` 的信号，适配器内部从 engine index `s+1` 启动，使其首个 `decision_index=s`、同样最早在 `s+1` open 入场。报告必须同时记录 requested economic start `s` 与 V4 engine start `s+1`。`s=0` 的 D/full 窗口保持 exact V4 原始 start `0`；这个首日 flat 适配只统一分段机会集，不改写 V4 登记身份或全窗锚点。

### 3.1 D 内部 walk-forward

三个 OOS 均 flat-start，互不重叠：

| Fold | Train | Gap | OOS |
| --- | --- | --- | --- |
| `F1` | `[0,120)` | `[120,130)` | `[130,173)` |
| `F2` | `[0,163)` | `[163,173)` | `[173,216)` |
| `F3` | `[0,206)` | `[206,216)` | `[216,259)` |

- Gap 不得参与该折参数选择或绩效；OOS 起点可读取 gap 内闭合 bars 计算因果指标，但状态必须 flat / unarmed / counters reset。
- `D-WFO aggregate` 按 `F1 -> F2 -> F3` 顺序复合三个 flat-start OOS 的净收益；aggregate MDD 固定为三折各自统一 `gate MDD` 中最差的一折。由于每折都重置为 flat / equity=1，不把互不连续的三段权益伪装成一条可投资路径；exact V4 使用其同定义冻结 MDD，候选使用第 2.3 节的兼容重放值。
- 所有结构选择、参数选择和排名只允许读取 `D full`、三折 D-WFO 及 D 上的成本/执行审计。

### 3.2 揭盲纪律

1. D 阶段结束后必须冻结唯一一个 champion 的完整配置、实现哈希和逐笔自检，再揭盲 `V eval`。
2. `V` 只运行 champion 与 exact V4 一次。`FAIL` 或 `INSUFFICIENT` 均结束本轮并记为 `NO-GO`；不得返回 D 选择第二名。
3. 只有 V 通过才可揭盲 `H eval`；H 同样只运行冻结 champion 与 exact V4 一次。
4. H 只能称为 `locked retrospective OOS`。由于该家族价格历史及 V4 结果已经被研究者查看，H 不是 clean / prospective OOS。
5. H 失败或样本不足后不得修改参数、结构、数据切点或裁决门。任何 materially new repair 必须另立合同，并使用新的未来 prospective 边界。

## 4. 新机制状态机

### 4.1 Fresh cross

搜索参数 `N_cross=N` 对多空共享：

- fresh long cross：`close[t] > SMA7[t]`，且对全部 `k=1..N`，`close[t-k] <= SMA7[t-k]`；
- fresh short cross：`close[t] < SMA7[t]`，且对全部 `k=1..N`，`close[t-k] >= SMA7[t-k]`。

等于 MA7 归入 crossing 之前的一侧；signal day 必须严格站到目标侧。持续处于某侧不是新信号，禁止 persistent-regime 入场或反手。

### 4.2 Slope

对目标方向 `side`、lookback `L` 和阈值 `theta`：

`slope_atr[t,side] = side * (SMA7[t] - SMA7[t-L]) / (L * ATR7[t])`

当且仅当 `slope_atr[t,side] > theta` 时方向 slope 通过；`theta=0` 仍是严格同向而不是允许零斜率。`ATR7<=0`、指标非有限或 lookback 不足均为不通过，不得下单。

### 4.3 Flat entry 与 armed

1. flat 且当日出现 fresh cross：若目标方向资格同日通过，则在次日 open 入场；Stage A-C 的方向资格就是 slope，Stage D 的 short 资格按第 4.7 节允许 slope 或冻结的 overbought memory 二选一。fresh 日不增加 `0.75×ATR7` anti-chase 上限。
2. fresh 日目标方向资格未通过时建立 armed；`A=0` 表示不等待，`A=1/2` 表示 fresh 日之后最多再检查 `1/2` 个完整日。
3. armed 等待日 `u` 只有同时满足下列条件才可在 `u+1` open 入场：
   - 收盘仍严格位于目标侧；
   - `0 < side*(close[u]-SMA7[u]) <= 0.75*ATR7[u]`；
   - 目标方向资格通过；除 Stage D 已在 fresh short cross 日冻结为通过的 overbought memory 外，资格即为当日 slope 通过。
4. 价格返回 MA7 或反侧、出现相反 fresh cross、armed 到期、建立任何仓位、指标无效或数据中断时立即取消 armed。
5. 同一天出现无法唯一裁决的双向 armed 或数据异常时 fail closed，不得以排序优先级猜测方向。

### 4.4 持仓、反向 armed 与 ATR 容错

1. 持仓中出现相反方向 fresh cross 时，先建立相反方向 armed；该 armed 使用同一个 `A` 有效期。
2. 在 fresh 日或 armed 有效日，只有同时满足以下条件，才在次日 open 原子反手：
   - 收盘仍严格位于目标方向的 MA7 一侧；
   - 已越过当前 Stage B 的 adverse band `H`：long→short 要求 `close < SMA7-H*ATR7`，short→long 要求 `close > SMA7+H*ATR7`；
   - 相反方向资格通过；Stage A-C 要求 slope，Stage D 的 short 方向允许使用 fresh cross 日冻结的 overbought memory 替代 slope。
3. 反向 armed 在价格回到原持仓侧、到期、指标无效、仓位先被其他退出关闭或数据中断时取消。
4. adverse band 被越过但相反方向资格尚未通过时，不允许凭 persistent regime 反手；Stage A-C 的方向资格是 slope，Stage D 的 short 方向资格可以由 fresh-cross 日冻结的 overbought memory 替代 slope。当前仓位只能继续等待优先级更高的已冻结退出，或在 slope-loss 条件完成后平到 flat。
5. 原子反手绕过 flat-entry 流程；新方向不得继承旧方向的 armed 或连续计数。

### 4.5 Slope-loss flat exit

- 持仓方向的 `slope_atr[t,current_side] <= theta` 记作一个 slope-loss 日；重新严格通过即把连续计数清零。
- 连续 `C` 个完整日 slope-loss 时，在下一日 open 仅平仓到 flat。
- slope-loss 本身不得创建目标方向、不得复用已经过期的 raw cross，也不得在平仓后按持续 MA7 regime 反手。
- 因 slope-loss 退出后清空全部 armed 与 RSI 连续计数，后续必须等待新的 fresh cross。

### 4.6 RSI6 short take-profit

- 只在 short 实际建仓后开始计数；入场前、long 期间和 flat 期间的 RSI 不得带入。
- 日 `t` 的 `RSI6[t] < T` 记一日，`RSI6[t] >= T` 或指标无效即清零；必须严格连续 `M` 个完整持仓日。
- `profit_guard=true` 固定不搜索：仅当以日 `t` close 标记，并按保守 roundtrip 成本 `2*(0.001+0.0004)=0.0028` 覆盖已付入场成本与预计下一次退出成本后，short 仍为正净浮盈，才生成 take-profit 信号；已经实际结算的 funding 另记账，但不拿未来 funding 改写信号。
- 信号在 `t+1` open 只平 short 到 flat；真实跳空可能令最终成交不再盈利，仍须如实成交，不得使用未来 open 反向改写信号。
- RSI take-profit 后清空 armed 与全部连续计数，等待新的 fresh cross。

### 4.7 RSI6 overbought-memory short 模块

Stage D 只增加一个独立 short 资格通道：

- 阈值固定为 `70`；`M_ob` 个 signal day 之前的完整日必须全部满足 `RSI6 > 70`；
- 只有 fresh short cross 才能消费该记忆；持续处于 MA7 下方不能消费；
- short 的方向资格变为 `fresh short cross AND (short slope pass OR overbought memory pass)`；overbought memory 是 slope 的独立替代资格，不能要求二者同时通过；
- flat 时，fresh short cross 与 overbought memory 同日通过即可在次日 open 做空；持有 long 时仍须越过 Stage B adverse band 才能原子反手，但该次反手的 short 方向资格可以由 overbought memory 单独满足；
- fresh short cross 建立 armed 时，是否通过 overbought memory 在事件日一次性冻结到该 arm；arm 有效期内不得用后来新出现或消失的 RSI 路径追溯改写资格；
- 模块不改变 long entry，不改变 RSI short take-profit，不创建 persistent short regime。

### 4.8 日开盘执行优先级

同一个完整日产生多个次开动作时，只允许以下顺序：

1. 合格相反 fresh/armed + adverse band + 方向资格：原子反手；
2. short RSI6 take-profit：平到 flat；
3. 连续 `C` 日 slope-loss：平到 flat；
4. 原先已经 flat 时的 fresh/armed entry。

高优先级动作执行后，低优先级动作全部取消。一次日线决策最多产生一次方向迁移；不得同 open 先 RSI 平空、再把旧 long armed 用于反多。

## 5. 结构消融与搜索顺序

### 5.1 结构 OAT

在打开数值搜索前，先用 anchor `N=1, A=1, L=1, theta=0, H=0.75, C=1, T=30, M=3, M_ob=3` 在 D-only 做结构 OAT：

- full intent anchor；
- 去掉 fresh-cross、改为 persistent regime，仅作 negative control，不具 champion 资格；
- `A=0`，去掉 armed 等待；
- 去掉 entry slope gate；
- 去掉 slope-loss exit；
- 去掉 adverse band gate；
- 去掉 RSI short take-profit；
- 去掉 overbought-memory 通道；
- 禁止原子反手，合格相反信号也只平到 flat。

每个 OAT 必须输出 activation count、成交数和逐笔路径差异。完全 path-equal 的模块必须先用合成边界测试排查接线；不能把历史 dormant slot 当成已证明有效。若合成测试或 OAT 执行报错，数值搜索 fail closed；若合成测试已证明接线而 anchor 的 D 历史仍 path-equal，则明确记为 `historically_dormant`，但仍须完成预注册的 174 个 stage trials，因为 Stage C/D 的其他离散值可能激活该模块。结构 OAT 只使用 D，不得读取 V/H。Stage D 结束、champion 选出前，须按 champion 完整配置再运行一次同样的有效模块 OAT。这里的“行为贡献”只指 champion 实际启用的模块在 D 上确有激活且关闭后路径发生变化，不要求单模块 PnL 为正；若 champion 中本应 active 的核心模块仍 dormant 或未接线，则本轮直接 `NO-GO`，不得临时删除模块、生成新候选或揭盲 V。若关闭模块的 D 绩效反而更好，只作消融归因，不能事后替换 champion。

### 5.2 Stage A：fresh / armed / slope，固定 108 组

多空共享参数，不开放两侧独立值：

- `N_cross in {1,2,3}`；
- `A in {0,1,2}`；
- `L in {1,2,3}`；
- `theta in {0,0.01,0.02,0.04}`。

笛卡尔积固定为 `3*3*3*4 = 108`。本阶段 `H=0.75, C=1`，RSI short take-profit 与 overbought-memory 均关闭；`T=30, M=3` 只作为未激活占位，不得追加点位。按第 6.3 节的中间阶段顺序保留前 `5` 名进入 Stage B。

### 5.3 Stage B：band / slope-loss，固定 30 组

对 Stage A 的 D 排名前 `5` 名分别测试：

- `H in {0.50,0.75,1.00}`；
- `C in {1,2}`。

总计 `5*3*2 = 30`，RSI short take-profit 与 overbought-memory 仍关闭。按第 6.3 节的中间阶段顺序保留前 `3` 名进入 Stage C；三名 Stage B parent 继续作为最终无 RSI 控制，不因进入下一阶段而失去最终资格。

### 5.4 Stage C：RSI6 short take-profit，固定 27 组

对 Stage B 的 D 排名前 `3` 名分别测试：

- `T in {25,30,35}`；
- `M in {2,3,4}`；
- `profit_guard=true` 固定；
- RSI 连续计数仅从 short 实际成交后开始。

总计 `3*3*3 = 27`，本阶段明确开启 RSI short take-profit，overbought-memory 仍关闭。不得加入 `60/65/70`、改变 RSI length、切换 SMA/EMA 或搜索 profit guard。按第 6.3 节的中间阶段顺序保留前 `3` 名进入 Stage D；三名 Stage C parent 与三名 Stage B 无 RSI 控制都继续保留最终资格。

### 5.5 Stage D：overbought-memory short，固定 9 组

对 Stage C 的 D 排名前 `3` 名分别测试：

- `RSI6 threshold=70` 固定；
- `M_ob in {2,3,4}`，要求 signal day 之前连续满足。

总计 `3*3 = 9`，本阶段开启 overbought-memory。Stage D 完成后，把 9 个 Stage D 配置、3 个 Stage C parent 与 3 个 Stage B 无 RSI 控制合并为 final pool；重复配置按 config hash 去重，不新增回测。只有 final pool 的第一名同时通过第 6.2 节 D 硬门时才冻结唯一 champion；不存在供 V 失败后替补的第二 champion。

### 5.6 Trial 完整性

- 必须在首次运行前生成 deterministic trial manifest，包含结构 OAT、Stage A-D 的完整配置 id、父配置和预期数量。
- manifest 写入前必须由编排器在当前 Python 环境重新运行冻结的 intent engine、candidate harness contract、state trace、fair-MDD / risk audit、evidence attribution、V4 adapter、HTML renderer 与 orchestrator 目标测试；只有全部通过且 exact pass count、全部测试文件 SHA 和被测实现 SHA 均写入 manifest 后，才允许读取候选绩效。
- 所有运行结果，包括异常、零交易、失败和 path-equal，均写入 trials artifact；不得只保留赢家。
- 本合同数值搜索主体固定为 `108+30+27+9=174` 个 stage-scoped trial rows，结构 OAT 和 exact V4 控制另列；Stage B 中 `H=0.75,C=1` 会与 5 个 Stage A parent 参数等价，因此唯一参数 hash 最多为 `169`。等价 trial 必须保留各自 stage id，但可以复用同一冻结缓存结果；不得把 `174` 宣称为 174 个独立参数，也不得根据中间结果增加网格。

## 6. D 排名与 V4 双重支配硬门

### 6.1 双重支配定义

本节及第 6.2--6.5 节中的 `MDD` 均专指第 2.3 节冻结的统一 `gate MDD`。候选原生 1h MDD 与 exact V4 原生报告值仍须并列保留，但不得替代 gate MDD、混入排序或制造计量口径优势。

同一窗口、同一成本下，候选必须同时满足：

- `net_return_candidate > net_return_exact_V4`；
- `MDD_candidate > MDD_exact_V4`，即候选 MDD 更接近零；
- 且至少一项达到实质改善：`return delta >= 5.0 percentage points` 或 `MDD delta >= 2.0 percentage points`。

严格比较使用未四舍五入机器值；展示值不得用于边界裁决。

### 6.2 D 资格

候选必须在以下两项分别满足双重支配，才具 D 排名资格：

1. `D full [0,259)`；
2. `D-WFO aggregate`。

`8 bps` 压力下候选不得相对 exact V4 同时收益更低且 MDD 更差；压力结果只作否决，不用于挑选压力最优参数。

### 6.3 D 中间推进与唯一排序

Stage A/B/C/D 必须完成预注册的全部 108/30/27/9 组，即使中间核心尚未双重支配 V4 也不能提前停止，否则后置的 band、RSI 或 overbought 模块永远没有被检验。D 硬门只能在 Stage D 全部完成、final pool 形成后执行。中间推进对全部数据有效且非异常的配置按以下 lexicographic 顺序排序，不构造可调权重分数：

1. 在 `D full` 与 `D-WFO aggregate` 两个比较域中满足第 6.1 节双重支配的域数更多；
2. `D-WFO aggregate` 相对 exact V4 的 net-return delta 更高；
3. 三个 WFO 折中最差的候选相对 V4 net-return delta 更高；
4. `D-WFO aggregate` 的 MDD delta 更高；
5. `D full` 的 net-return delta 更高；
6. active parameter 数更少；
7. turnover 更低；
8. 若仍完全相同，按预注册 config id 字典序更小者优先。

Stage A/B/C 的 top `5/3/3` 按此顺序产生。Stage D 完成后的 final pool 也按同一顺序产生唯一第一名，但只有该第一名另外完整通过第 6.2 节 D 资格门才可冻结为 champion；若第一名不通过，不得跳到后名次或揭盲 V。

### 6.4 V 与 H 硬门

- `V eval` 和 `H eval` 均必须分别满足第 6.1 节双重支配。
- 候选在每个 eval 窗口至少 `3` 笔平仓；少于 3 笔直接记 `INSUFFICIENT`，不得当作通过。
- 每个 eval 的 `8 bps` 压力下不得相对 exact V4 双劣。
- V 的 `FAIL/INSUFFICIENT` 均为本轮 `NO-GO`，不揭 H；H 的 `FAIL/INSUFFICIENT` 同样为 `NO-GO`，不得救参。

### 6.5 最终 full-window 硬门

通过 H 后，冻结 champion 在相同 `[0,432)` 窗口还必须满足：

- 成本后净收益严格高于 `+398.840674%`；
- MDD 严格优于 `-26.813854%`；
- `8 bps` 下相对 exact V4 不得双劣。

这两个数值是预注册的 exact V4 full-window 门槛，不是新候选结果。若 exact V4 复算无法逐位重现其冻结锚点，应停止并先解决 comparator drift，不得修改门槛适配漂移实现。

## 7. Champion 冻结后的固定风险覆盖

风险覆盖不参与 Stage A-D 排名，不能救回 D/V/H 或 final-full 失败。只有 champion 的参数、代码和 V/H 裁决均冻结后才运行：

- `R0_NONE`：无额外 intraday hard stop，保持本合同日线状态机；
- `R1_SYMMETRIC_HARD_1P5`：long/short 入场即以 signal day 已知 `ATR7` 设置对称静态 `1.5×ATR7` hard stop。

R1 规则：

- long stop=`entry_price-1.5*ATR7`；short stop=`entry_price+1.5*ATR7`；持仓中不移动、不 trailing；
- 使用组成日 K 的真实 `1h` 路径；小时 open 已越过 stop 时按该 open 成交，小时内首次触发按冻结 stop-market 模型成交并计成本；
- stop 只平仓到 flat，绝不反手；触发后不读取同小时未知后续路径，并清空 armed 与连续计数；
- 小时 open 已越过 stop 时，必须先按该 open 平仓，再裁决该时点 exposure / funding；只有非 gap 的小时内 stop 才可先结算小时 open 时点已经发生的 funding。若冻结 harness 的原始记录与此边界不一致，独立 risk audit 必须显式纠正或标成 blocker，不能静默沿用；
- 不打开 ATR 倍数、trailing、cooldown、max-hold 或方向独立参数网格。

R0/R1 必须报告逐笔差异、最大不利路径、跳空、同小时路径处理和是否发生裸仓/破产，但风险覆盖结果不改变已完成的参数选择历史。

## 8. 执行自检与必须输出

在任何绩效读取前必须通过确定性行为测试：

- fresh cross 的 `N=1/2/3` 边界与 equality；
- armed 的 `A=0/1/2` 最后有效日、anti-chase、取消和到期；
- slope `L/theta` 公式及非有限输入；
- 持仓反向 fresh cross、adverse band、slope 与原子反手；
- slope-loss 连续计数和 reset；
- RSI 仅在 short 后计数、strict threshold、profit guard 和 gap-open 实际亏损可能；
- 同日四级优先级；
- 两次 fill 的反手成本、funding 边界和 terminal flatten；
- V/H flat-start 不继承任何状态；
- exact V4 锚点复算。
- 候选与 V4 的 gate-MDD 共同口径、candidate 原生 1h-MDD 差异、terminal ledger parity 与 `bankrupt` fail-closed；
- entry / exit / atomic reversal / terminal open 的 funding 边界，RSI 信号后的真实 gap-open 成交，以及 R1 gap-stop 与 intrahour-stop 的 funding / exposure 顺序；

报告与 artifacts 至少包括：

- deterministic manifest 与完整 trials；
- structure OAT、D full、逐折 WFO、aggregate、V、H、final full、4/8 bps；
- 最近 `1d/7d/1m/3m/6m/1y` 切片，明确只作审计、不作选择；
- trade count、long/short 贡献、MDD、净收益、成本、funding、turnover、暴露率、activation counts；
- 零交易与 `INSUFFICIENT` 窗口；
- champion 对 exact V4 的逐笔新增、删除、提前、延后、armed、RSI TP、slope-loss 与反手差异；
- R0/R1 风险覆盖及逐笔 diff、stop level、gap flag、触发小时 OHLC、同小时路径处理、funding-at-stop、最大不利路径、terminal flat / bankrupt / naked-position audit；
- 一份完整交易路径 HTML：K 线、SMA7、ATR band、slope、RSI6、armed/counters、仓位、权益，以及每笔 entry 与对应 exit 连线。

额外延迟、日界相位和 rolling 结果可在 champion 冻结后作为置信度检查；不得用于改参。相位表现本身不是 promotion 硬门，但若暴露 lookahead、错误聚合或 runner 不可复现，则按对应执行 blocker 处理。

## 9. 低样本限制、裁决与未来 prospective

- 432 日及低交易数不足以证明稳定 alpha；收益、PF、Sharpe 或单笔大赢家均不得替代独立样本。
- D/V/H 都来自研究者已经看过的市场历史；本合同的锁定只能阻止本轮算法继续追逐结果，不能把旧历史变成 clean OOS。
- 参数网格存在多重比较风险；必须保存全部 trials，并在最终报告披露尝试总数和选择链。
- V4 双重支配是本轮预注册硬门；即使某候选只改善收益或只改善回撤，也只能作为 diagnostic evidence，不能成为 champion。
- 任一数据、状态、成交或 comparator 自检失败均为 `BLOCKED`；不得在错误实现上继续优化。候选任一用于 D/V/H/final gate 的场景若原生回测出现 `bankrupt=true`，无论随后价格是否令账面权益恢复，都必须按无效场景 fail closed，不能进入排名或晋级。
- 没有候选通过 D、V、H 或 final-full 任一硬门时，结论为 `NO-GO`，策略状态保持不变。

即使所有 retrospective 门通过，状态仍保持 `explore / diagnostic-only / not promoted / not live-ready`。必须从合同与 champion 均冻结后的首根新闭合 UTC 日线起建立独立 prospective 台账，至少同时满足：

- `>=120` 个日历日；
- `>=6` 笔独立平仓交易；
- 至少 `1` 笔 long 和 `1` 笔 short；
- 数据、指标、armed、RSI、费用、funding 和逐笔执行与冻结研究实现一致。

prospective 不足只能记 `INSUFFICIENT`；失败不得追溯调参。完成 prospective 也不自动登记版本或 promotion，仍须另行完成 CPCV/OOS、Monte Carlo、执行压力、风险保护、runner parity 和线上逐笔对账门禁。只有用户之后明确要求登记，且主账、decision log 与所需证据同步更新时，才讨论新版本身份。
