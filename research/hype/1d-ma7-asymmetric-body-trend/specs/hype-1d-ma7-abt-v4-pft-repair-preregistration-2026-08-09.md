# HYPE 1D MA7 V4-PFT 修复预注册合同

> 冻结日期：2026-08-09。状态：`explore / not promoted / not live-ready`。本合同首次写入后，任何候选组合绩效读取前必须由 manifest 固定合同、实现、测试和数据 SHA256。

## 1. 研究身份与核心目标

本合同建立 `HYPE-1D-MA7-Asymmetric-Body-Trend` 家族内的一条独立 V4 修复研究分支，代号 `V4-PFT`。它不是 V4.1 或 V5，不改写已登记 V4 的参数、身份、历史逐笔路径或状态。

唯一核心目标是：在 exact V4 的同一市场、同一窗口、同一仓位、同一成本、同一 funding 和同一最大回撤计量器下，形成至多一个同时满足下列条件的研究候选：

1. 成本后净收益严格高于 exact V4；
2. 最大回撤严格小于 exact V4，即 MDD 更接近零；
3. D-full、三折 D-WFO 和 `8 bps/fill` 压力均通过冻结门；
4. 改善来自可审计的 P/F/T 交易路径，而不是不同回撤计量器、零交易、破产后恢复、遗漏费用或 V/H 事后选择。

即使候选最终通过，也只保持 `explore / not promoted / not live-ready`，不自动登记 V5、创建 live spec、推进 runner、dry-run 或 live。

## 2. 已知历史与本轮新增问题

### 2.1 exact V4

Exact V4 是登记的 `MA_ONLY` 实现：完整继承 V3 的自然 reclaim、slope、entry buffer、两侧迟滞、保护、cooldown、仓位和成本；long trailing stop 后只有拟反手真实 `1h open` 低于上一完整日 MA7 时才开 short。

本轮只允许通过冻结的 [exact V4 fair adapter](../scripts/hype_1d_ma7_v4_fair_adapter.py)调用它。adapter 的全窗锚点为 equity `4.988406741729143`、MDD `-26.813853621046835%`、17 笔；任何漂移均在候选读取前 fail closed。

### 2.2 P 的历史来源

旧的 post-reveal 局部诊断显示：short fresh reclaim 当日 slope 未确认时，等待 1 日、延迟确认距 MA7 不超过 `0.75×ATR7`，并只允许 delayed short 在原 V4 opposite reclaim 同 open handoff 到 long，可以补回一笔已知 short 并保留后续 long；但历史收益提高同时 MDD 扩大，不能直接替代 V4。

本轮把该完整结构作为一个冻结模块 P，不重新搜索 `wait/cap/handoff` 参数，也不把旧结果当作 V/H 证据。

### 2.3 F 的历史来源

V4 的 `MA_ONLY` 只检查拟成交 open 与上一完整日 MA7 的关系；获准的 5 笔 forced reversal 中仍有 3 笔只持有 1 日。旧的 `MA_AND_SLOPE` 对照能检查 last-complete-day downward slope，但未与 P 或 RSI6 组合验证。

本轮把 published `MA_AND_SLOPE` 语义作为冻结模块 F，不搜索新的 slope 参数。

### 2.4 T 的历史来源

上一轮 researcher-exposed Development 中，short `RSI6<25` 连续 2 个实际持仓日且已有正净浮盈的下一开盘止盈，在其父路径上明确减少 short giveback；但所属完整策略没有支配 V4。

本轮只移植 T 退出模块，不移植上一轮 fresh-cross/slope-loss/direct-reversal 状态机。`25×2` 是唯一具有候选资格的固定值；用户原始语义的 `30×3` 只作冠军结构 OAT，不得替补失败候选。

### 2.5 明确排除

- 不加入上一轮单日 slope-loss 状态机；V4 原退出保持不变。
- 不加入 held adverse-band 反手或 persistent MA7 regime。
- 不加入 `RSI6>70` overbought memory：当前历史路径 dormant，只有合成接线测试，不进入排名。
- 不搜索新的 MA、ATR、RSI length、阈值、连续日、pending 天数、anti-chase 上限、cooldown、保护或仓位。

## 3. 数据、指标和执行

### 3.1 冻结数据

- Binance USD-M `HYPEUSDT` perpetual；完整 UTC `1d` 信号，真实 `1h` 路径执行保护、反手和 funding。
- 沿用上一轮已冻结但 V/H 未揭示的 432 根 UTC 日线，索引 `[0,432)`；首日 `2025-05-31 UTC`，terminal open `2026-08-06 00:00 UTC`。
- manifest 前必须重新核对 raw/normalized 路径和 SHA、1h/funding 行数、最后闭合时间、缺口、重复、关键空值、OHLC、closed-only 与聚合 parity。
- manifest 前还必须断言上一轮及本轮 artifact 前缀下不存在 validation、holdout 或 final 文件；发现任何提前揭示即停止。

### 3.2 指标

- exact V4 的 `SMA7/ATR7` 和 long/short slope 公式、lookback、阈值全部原样继承。
- `RSI6` 使用 Wilder / TradingView 口径：首个值用 6 期 gain/loss 简单平均初始化，随后 `alpha=1/6` RMA；全涨为100、全跌为0、全平为50，非有限输入不产生信号。
- 所有日线信号只读取已经闭合的日 `t`，最早在 `t+1` open 成交；F 的 trailing 反手只读取触发时已知的最近完整日 MA7/slope 与真实下一根 `1h open`。

### 3.3 仓位、成本和资金费

- 单仓、非加仓、约 `1x` 目标；建仓后数量固定至退出。
- 手续费 `0.001/fill`；基准不利滑点 `4 bps/fill`；压力不利滑点 `8 bps/fill`；真实 event-time funding。
- 原子反手或 handoff 的平旧仓、开新仓是两个独立 fill，分别计成本与 turnover。
- 任何 intraday equity `<=0` 立即冻结为零、清仓并标记破产；破产 trial 不得排名或过门。
- 候选直接继承 exact V4 的 `favorable extreme -> adverse extreme -> close` 日内 MDD 计量顺序；另保留逐小时/逐事件风险审计。control 与 candidate 必须由同一冻结 compiled ledger 产生或经独立 replay 验证 terminal equity、turnover、cost、funding 一致。

## 4. 固定 D/V/H 边界

| 角色 | Raw / eval | 可交易起点 | Terminal open | 用途 |
| --- | --- | --- | --- | --- |
| D | `[0,259)` | 2025-05-31 | 2026-02-14 | 8 臂、OAT、排序、D硬门 |
| V raw | `[259,346)` | 2026-02-14 | 2026-05-12 | purge + validation 边界 |
| V eval | `[269,346)` | 2026-02-24 | 2026-05-12 | one-shot validation |
| H raw | `[346,432)` | 2026-05-12 | 2026-08-06 | purge + holdout 边界 |
| H eval | `[356,432)` | 2026-05-22 | 2026-08-06 | one-shot locked retrospective OOS |

`[259,269)`、`[346,356)` 是固定 10 日 purge。分段运行可读取 purge 内闭合 bar 计算指标，但必须从 eval 起点 flat、无 pending、无 delayed-entry 标记、RSI streak=0、无未完成订单。

为统一首个可成交机会，任意 `s>0` 分段的 control 和 candidate 都以 engine start `s+1` 启动，使首个 decision index 为 `s`、最早 `s+1` open 成交；D-full `s=0` 保持 exact V4 原始 start 0。

### 4.1 D-WFO

| Fold | Train | Gap | OOS |
| --- | --- | --- | --- |
| F1 | `[0,120)` | `[120,130)` | `[130,173)` |
| F2 | `[0,163)` | `[163,173)` | `[173,216)` |
| F3 | `[0,206)` | `[206,216)` | `[216,259)` |

三折 OOS 各自 flat-start / equity=1，收益按 F1→F2→F3 复合，aggregate MDD 取三折最差 MDD，不拼接成伪连续权益。

## 5. 模块 P：short pending quality + delayed handoff

P 只替换 V4 的自然 `close_entry_signal` short 路径；long wait 固定为 0，short wait 固定为 1。

1. fresh short reclaim 沿用 V4 原定义：当日 close 通过原 short entry buffer，前一日满足原 pullback touch；若同日原 short trend/slope 通过，仍按 exact V4 在次日 open 入场。
2. fresh reclaim 当日 trend/slope 未通过时，建立最多 1 个完整日的 short pending。
3. 延迟日只有同时满足以下条件才在下一 open 做空：
   - 原 V4 short entry buffer 通过；
   - 原 V4 short trend/slope 通过；
   - `0.25×ATR7 < (MA7-close) <= 0.75×ATR7`；下限来自 V4，`0.75` 是冻结 anti-chase 上限。
4. close 触碰或回到 MA7 上方、等待超过 1 日、指标无效、建立其他仓位或窗口终止时取消 pending；拒绝 overextended 后不继续等待。
5. 只有由 delayed pending 建立的 short，在随后因原 V4 `ma7_hysteresis_exit / ma7_slope_exit / max_hold` 于日开退出时，若同一 decision day 的原 V4 fresh long reclaim+slope+buffer 通过，才允许同 open 平 short 并开 long。
6. protective stop、T 的 RSI take-profit、普通 V4 short 和 F forced short 均禁止 handoff；handoff 后 long 完全回到 V4 状态机。

P 必须输出 arm、same-day/delayed confirm、MA7 invalidation、expiry、anti-chase rejection、delayed-entry 标记和 handoff 事件。

## 6. 模块 F：forced reversal 的 MA7+slope 确认

F 只改变 long trailing protective exit 后拟建立 forced short 的资格，不改变保护价、跳空 fill、触发小时或 V4 自然入场。

1. long trailing stop 仍先按 exact V4 的真实 1h 路径平仓；该保护事件创建一次性 forced-short intent。
2. 拟反手的真实下一根 `1h open` 必须严格低于最近完整日 MA7。
3. 最近完整日 downward slope 使用 V4 short 的冻结 lookback 和阈值；只有 `down_slope_atr >= short_config.slope_min_atr` 才通过。
4. MA7、ATR、slope lookback 非有限或不足均拒绝。
5. 若 stop 在 UTC 日最后一小时触发，则在下一日 open 用届时最近完整日数据检查。
6. 拒绝后保持 flat、执行 V4 long cooldown；forced intent 不进入 P，不保留 pending，也不按持续 regime 追单。
7. 通过后完全继承 V4 short 的迟滞、slope exit、hard/trailing stop、max hold、cooldown、funding 和成本。

F 必须分别记录 intraday/pending forced attempt、MA7 pass、slope pass、accepted、rejected 和一日内退出。

## 7. 模块 T：RSI6 short take-profit

1. 只在 short 实际 fill 后开始观察；flat/long/入场前 RSI 不得带入。
2. 每个完整持仓日 `RSI6<25` 时 streak+1；`RSI6>=25`、非有限、平仓或方向变化时清零。
3. 连续 2 日后，只有 signal close 相对实际 short entry price 的 gross short profit 严格大于 `0.0028`，才生成 `short_rsi_take_profit`。
4. `0.0028 = 2×(0.001+0.0004)` 是保守 roundtrip fee+slippage guard；已结算 funding 记账但不改变信号，未来 funding 不可使用。
5. 信号在下一 UTC open 只平 short 到 flat，并继承 V4 short 的 5 日 cooldown；实际 gap 可能令最终成交亏损，仍如实成交。
6. T 在日开决策中优先于原 V4 日线退出；若 T 触发，P handoff 被抑制。Intraday protective stop 已经发生时，自然先于尚未形成的下一日 T。
7. `RSI6<30` 连续3日使用相同 guard，只在 D champion 结构上作固定 OAT；它不能参加8臂排名或在25×2失败后替补。

T 必须记录 streak、threshold reset、profit-guard pass/block、实际退出、gap 后最终盈亏及与同日原 V4 exit 的重合。

## 8. 8 臂全因子与唯一候选

| ID | P | F | T | 角色 |
| --- | ---: | ---: | ---: | --- |
| `A000_V4` | 0 | 0 | 0 | exact V4 control，不具候选资格 |
| `A001_T` | 0 | 0 | 1 | RSI 单模块 |
| `A010_F` | 0 | 1 | 0 | forced-reversal repair 单模块 |
| `A011_FT` | 0 | 1 | 1 | F×T |
| `A100_P` | 1 | 0 | 0 | pending/handoff 单模块 |
| `A101_PT` | 1 | 0 | 1 | P×T |
| `A110_PF` | 1 | 1 | 0 | P×F |
| `A111_PFT` | 1 | 1 | 1 | 完整组合 |

8 臂全部必须运行并保留，不能只保存赢家。候选资格不要求三模块全开；研究目标是找到相对 V4 的最小有效修复，任何非 control arm 都可参加 D 硬门。

### 8.1 模块 OAT 与交互

- 8 臂本身给出 P/F/T 主效应和两两/三重交互，不允许把不同臂 PnL 简单相加。
- D champion 选出后，对其每个 enabled 模块执行关闭 OAT；必须在 D 有相关 activation 且关闭后去标签逐笔经济路径改变。
- 若 T enabled，再运行固定 `25×2 -> 30×3` 稳健性 OAT；只报告方向，不改变 champion。
- 若某 enabled 模块在 D dormant、未接线或关闭后 path-equal，候选 wiring gate 失败，不得临时删模块或换下一名。

## 9. Development 硬门与排序

### 9.1 同窗双重支配

在 D-full 和 D-WFO aggregate 两个域，候选都必须同时满足：

- `candidate net_return > exact V4 net_return`；
- `candidate MDD > exact V4 MDD`，即更接近零；
- 且每个域至少一项达到实质改善：return delta `>=5.0pp` 或 MDD delta `>=2.0pp`。

严格比较使用未四舍五入机器值。

### 9.2 额外硬门

- `8 bps/fill` 的 D-full 和 D-WFO 都不得同时出现收益低于 V4且 MDD差于V4。
- 每个 WFO fold 均不得相对 V4 同时收益更低、MDD更差。
- D-full 至少 8 笔、至少 3 笔 short；WFO aggregate 至少 3 笔且每折至少1笔。
- 候选和 V4 均不得破产、不得出现账本不一致、非有限 gate 指标或负持仓时长。
- 所有 enabled 模块通过第8.1节 wiring/activation gate。

### 9.3 多个通过臂的冻结排序

只在先独立通过全部 D 硬门的臂之间排序：

1. 三折中最差 return delta 较高；
2. WFO aggregate return delta 较高；
3. WFO MDD delta 较高；
4. D-full return delta 较高；
5. D-full MDD delta 较高；
6. enabled 模块更少；
7. arm ID 字典序。

若无臂通过，Development 结束并记录 `hard-gate FAIL / 本轮不晋级`。若有多个通过，只冻结排序第一名为唯一 champion；其他臂不能在 V 失败后替补。

## 10. V/H one-shot 门

### 10.1 Validation

- 只有 frozen D champion 可以与 exact V4 在 `V eval=[269,346)` 各运行一次。
- 使用与 D 相同的双重支配、`5pp/2pp` materiality、至少3笔、非破产和账本门。
- V `FAIL` 或样本不足均停止；不得重排、改参数、换臂、改变 RSI OAT 或读取 H。

### 10.2 Holdout

- 只有 V PASS 才能在 `H eval=[356,432)` one-shot 运行 frozen champion 与 exact V4。
- 使用相同双重支配、materiality、至少3笔、非破产和账本门。
- H 是 locked retrospective OOS，不称 clean/prospective OOS。
- H 失败或样本不足后不得改变本合同；下一机制必须另立合同并使用新的未来边界。

## 11. 成功后才运行的稳健性审计

只有 D/V/H 全部通过，才读取并报告：

- 全432日、最近 `1d/7d/1m/3m/6m/1y` 沿完整权益路径切片；
- 90日 rolling、固定 CPCV、MC3 trade-order、额外1日信号延迟；
- `8 bps`、funding on/off、R1 hard-stop/gap audit；
- long/short 分腿、forced reversal、pending delayed short、handoff、RSI TP 分组；
- 相对 V4 added/removed/matched trades、提前/延后退出、MFE/MAE/giveback、费用/funding/turnover；
- 完整 UTC 日K、MA7/ATR/RSI6、P/F/T state、权益与每笔入出场连线的自包含 HTML。

若 D 或 V 失败，可以生成明确标记的失败首位 D-only 或 V-only诊断路径，但不得生成 champion/final 叙事。

## 12. Manifest、测试与不可变产物

### 12.1 运行阶段

CLI 必须分为：

- `self-test`：纯计数/合同测试，不读取候选绩效；
- `manifest`：数据审计、exact V4 anchor、测试和源码 pin；
- `development`：8臂 D-only、唯一 champion 或硬门失败；
- `validation`：one-shot V；
- `holdout`：one-shot H；
- `finalize`：只消费已锁定组件，不重新选择。

### 12.2 测试前置

Manifest 前必须重新运行并记录 exact pass count 与测试 SHA：

- exact V4 all-off parity；
- P same-day/delayed/expiry/MA7 invalidation/anti-chase/handoff边界；
- F MA equality、slope equality、nonfinite、日末 pending和拒绝 cooldown；
- Wilder RSI6 known vector、阈值 equality、streak after actual fill、profit guard strict equality、gap open；
- T 与 native exit/handoff/protective stop 的优先级；
- 两次 fill、funding entry/exit/reversal边界、terminal flatten、破产 fail-closed；
- WFO flat-start、共同 MDD、8臂枚举、排序、D/V/H lock、artifact hash 和 HTML path/trade consistency。

### 12.3 锁与命名

Artifact 前缀固定为：

`hype_1d_ma7_v4_pft_repair_2026-08-09`

每个 JSON/HTML 均以独占创建方式写入并带 `.sha256` sidecar；已有目标、sidecar不匹配、实现 pin 漂移或 one-shot锁存在时 fail closed。Development 失败不得创建 validation、holdout、final；V失败不得创建 holdout/final。

## 13. 报告状态口径

- 家族主状态只使用词表允许的 `explore / not promoted / not live-ready`。
- 数值裁决写作 `development/validation/holdout hard-gate PASS|FAIL|INSUFFICIENT`。
- `registered`、V5、promotion、handoff、dry-run、live 只能由后续用户明确请求并满足独立门禁后处理。
- 任何结果都必须同时保留 exact V4 control、成本、funding、窗口、交易数、MDD口径、逐笔证据与锁定边界。
