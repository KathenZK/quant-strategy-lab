# HYPE 1D MA7 原始意图优化：Development 诊断（2026-08-09）

## 结论

本轮预注册搜索的 protocol decision 为 **development hard-gate `FAIL`**。`174/174` 个数值 trial 全部完成且无 `ERROR / SKIPPED`，但没有任何配置在同窗、同成本、共同最大回撤计量器下同时取得：

1. 高于 exact V4 的成本后收益；
2. 小于 exact V4 的最大回撤；
3. 在三折 WFO 上仍满足同样的双重支配与实质改善；
4. 在 `8 bps/fill` 压力下不发生收益和回撤同时更差。

因此没有 champion，不运行也不揭示 validation `V=[269,346)` 或 holdout `H=[356,432)`，不登记 V5，不修改 V1–V4，不进入 runner。本轮裁决为 `development hard-gate FAIL / 本轮不晋级`；研究分支继续标记为 `explore / not promoted / not live-ready`，结果仅作诊断证据。

## 研究问题与冻结边界

本轮研究的是用户原始 MA7 趋势想法，而不是在 V4 上做局部补丁：

- 前 `N` 日收盘位于 MA7 同一侧，出现 fresh raw MA7 cross；
- directional MA7 slope 通过后，在下一 UTC 日开盘成交；
- cross 可 armed 等待有限日数，持仓反向越过 `H×ATR7` 容错带才允许反手；
- 持仓期间 slope 连续失效 `C` 日则退出；
- short 盈利时，`RSI6<T` 连续 `M` 日于下一开盘止盈；
- fresh short 可由此前连续 `RSI6>70` 的 overbought memory 独立放行；
- 反手是同一开盘两次 fill，费用、滑点与 funding 均按真实持仓路径计入。

[预注册合同](../specs/hype-1d-ma7-intent-optimization-preregistration-2026-08-09.md)在任何绩效读取前冻结了数据、执行、参数空间、排序、D 门槛和 V/H one-shot 规则。搜索只使用 researcher-exposed development 数据；V/H 始终保持封存。

## 数据、实现与公平性自检

| 项目 | 冻结结果 |
| --- | --- |
| UTC 日线 | `432` 根，索引 `[0,432)` |
| 1h 数据 | `10,390` 行 |
| funding | `2,597` 条 |
| 数据质量 | 缺口、重复、关键空值、非法 OHLC、未闭合 bar、raw-normalized 不匹配均为 `0` |
| Development | `D=[0,259)`；WFO=`[130,173) / [173,216) / [216,259)` |
| 锁定区 | purge `[259,269)`、V `[269,346)`、purge `[346,356)`、H `[356,432)` |
| 基础执行成本 | fee `10 bps/fill` + slippage `4 bps/fill` + 实际 funding |
| 压力成本 | fee `10 bps/fill` + slippage `8 bps/fill` + 实际 funding |
| 测试门 | `83` 项 deterministic tests 全部通过 |
| 结构接线 | structure OAT `PASS`；trace parity 全部 `PASS` |
| 破产与回撤 | 破产 fail-closed；候选和 V4 均使用 V4-compatible daily-extreme gate MDD |

[冻结 manifest](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_manifest.json)的 SHA256 为 `2b1fb36a97c3c2066953a3799e267832f643ffc092365edece5895aef28acb79`；代码、合同、数据和测试 pin 在 Development 前后均保持一致。

## 搜索完整性

| Stage | 作用 | Trial 数 | 结果 |
| --- | --- | ---: | --- |
| A | `N × A × L × theta`：fresh、armed、slope | 108 | 108 `OK` |
| B | `H × C`：ATR 容错与 slope-loss 确认 | 30 | 30 `OK` |
| C | `T × M`：short RSI6 盈利止盈 | 27 | 27 `OK` |
| D | overbought memory days `{2,3,4}` | 9 | 9 `OK`，全部 path-equal |
| 合计 | 169 个唯一配置 | 174 | 0 error，0 skipped |

最终池按冻结排序得到 15 行：

`C001, C010, D001, D002, D003, D004, D005, D006, C019, D007, D008, D009, B001, B003, B007`

排名第一的 `C001` 只是第一个接受硬门检验的配置，不是 champion。`C001 / C010 / D001–D006` 的绩效完全相同；D 行只多了没有激活的 overbought 参数，排序因此优先保留更简单的 C control。协议禁止第一名失败后换用后排配置救援。

## 第一名 C001

### 配置

| 参数 | C001 |
| --- | ---: |
| 前置 MA7 侧别日数 `N` | `1` |
| armed expiry `A` | `0` 日 |
| slope lookback `L` | `1` 日 |
| normalized slope `theta` | `0.04×ATR7` |
| adverse band `H` | `0.50×ATR7` |
| slope-loss confirm `C` | `1` 日 |
| short RSI6 TP | `RSI6<25` 连续 `2` 日且 short 已盈利 |
| overbought memory | 关闭 |
| direct reversal | 开启 |

配置哈希为 `08694418c2a8e723dab4862a3f6445544a9c0556988aa15f44bec957472106eb`。

### 与 exact V4 的 D 门比较

下表 MDD 均为共同的 V4-compatible daily-extreme 口径；收益均已扣除手续费、滑点和 funding。

| 域 | C001 | exact V4 | 差值（C001 − V4） | 门槛结果 |
| --- | ---: | ---: | ---: | --- |
| D-full `4 bps` 收益 | `+62.122192%` | `+160.020323%` | `-97.898131pp` | FAIL |
| D-full `4 bps` MDD | `-29.245335%` | `-22.335816%` | `-6.909518pp` | FAIL |
| WFO `4 bps` 收益 | `+63.152465%` | `+62.342625%` | `+0.809840pp` | 未达 `+5pp` materiality |
| WFO `4 bps` worst-fold MDD | `-23.973966%` | `-19.674159%` | `-4.299807pp` | FAIL |
| D-full `8 bps` 收益 | `+59.561695%` | `+158.047156%` | `-98.485461pp` | double-worse |
| D-full `8 bps` MDD | `-29.477120%` | `-22.394135%` | `-7.082985pp` | double-worse |
| WFO `8 bps` 收益 | `+61.727792%` | `+61.860986%` | `-0.133194pp` | double-worse |
| WFO `8 bps` worst-fold MDD | `-24.101521%` | `-19.674159%` | `-4.427362pp` | double-worse |

C001 的 WFO 汇总收益只比 V4 多 `0.81pp`，而且并不跨折稳定：

| WFO fold | C001 收益 | V4 收益 | 差值 |
| --- | ---: | ---: | ---: |
| F1 | `-6.429347%` | `+6.123534%` | `-12.552881pp` |
| F2 | `+42.419553%` | `+26.979184%` | `+15.440369pp` |
| F3 | `+22.429017%` | `+20.472612%` | `+1.956405pp` |

因此它既不是“收益更高、回撤更小”，也不能用 WFO 汇总的轻微收益优势解释为接近过门。

### 成本与交易密度

| D-full | C001 | exact V4 |
| --- | ---: | ---: |
| 平仓交易 | `20` | `10` |
| turnover | `43.873998` | `28.229347` |
| `4 bps` 成本/初始权益 | `6.142360%` | `3.952109%` |
| funding/初始权益 | `1.503733%` | `0.874764%` |
| `4→8 bps` 收益损失 | `2.560496pp` | `1.973167pp` |

候选把交易数翻倍，却没有获得相应的趋势捕获；成本压力因此比 V4 更敏感。

## 全部 174 个配置的 Pareto 结果

- 超过 V4 D-full 收益：`0/174`。
- 改善 V4 D-full MDD：`13/174`。
- 超过 V4 WFO 收益：`8/174`，全部属于 C001 同路径簇。
- 改善 V4 WFO MDD：`60/174`，但收益显著更低或交易样本很少。
- 同时改善 WFO 收益和 MDD：`0/174`。
- `ranking.dominance_domains>0`：`0/174`。
- `8 bps` 至少一个 full/WFO double-worse：`161/174`。

单项极值同样不能晋级：

| 目标 | Trial | 结果 | 为什么无效 |
| --- | --- | --- | --- |
| 最高 D-full 收益 | `C019 / D007–D009` | `+63.654201%`，MDD `-29.245335%` | 收益仍落后 V4 `96.366122pp`，MDD也更差 |
| 并列最小有收益 D-full MDD中的较高收益行 | `A060`（与 `A048` 同 MDD） | `+21.278846%`，MDD `-19.945617%` | 回撤改善仅靠牺牲 `138.741477pp` 收益 |
| 并列最小非零交易 WFO MDD中的较好 D 路径 | `A048`（与 `A046/A047` 同 WFO MDD） | `+17.704499%`，MDD `-11.034101%`，2 笔 | 样本与收益均不足 |
| 风险较优的可读簇 | `A040 / B025 / B027 / B029` | D `+34.5891% / -20.8076%`；WFO `+34.2839% / -16.2299%` | 明显降低风险，但丢失约四分之三 V4 D 收益 |

`0%` WFO MDD 的配置均为零交易，不是有效风险改善。

## 逐笔因果归因

C001 的完整 D replay 与冻结的 trades/path/actions 哈希逐位一致，trace parity 和公平回撤账本均为 `PASS`。

### RSI6 止盈确有正贡献

从 `B001` 加入 `RSI6<25` 连续 2 日止盈成为 `C001`：

- D-full 收益由 `+30.187515%` 提高到 `+62.122192%`；
- D-full MDD由 `-34.107914%` 改善到 `-29.245335%`；
- WFO 收益由 `+43.097179%` 提高到 `+63.152465%`；
- short 净 PnL 由 `-0.053652` 转为 `+0.185354`；
- 3 笔 RSI TP 全部盈利，合计净 PnL `+0.619673`。

所以“空头不能等到重新穿越 MA7 才止盈”的判断得到支持；RSI TP 是本轮唯一清晰的晚阶段正向模块。但它只能修复部分 short 利润回吐，不能弥补入场和反手路径造成的损失。

### 真正的损失来自额外震荡交易

C001 有 20 笔，V4 有 10 笔。逐笔时序匹配后：

- V4 的 10 笔全部可以匹配到候选；候选另有 10 笔 unmatched trades；
- 10 笔额外交易为 `1` 胜 `9` 负，合计净 PnL `-0.506546`；
- 候选匹配到的 10 笔为 `7` 胜 `3` 负，合计净 PnL `+1.127768`；
- V4 对应 10 笔为 `8` 胜 `2` 负，合计净 PnL `+1.600203`；
- 候选相对匹配的 V4 交易有 6 笔提前退出、1 笔同日、3 笔延后退出；
- 7 次 short slope-loss 为 1 胜 6 负，合计 `-0.122666`；
- 2 次 short→long 原子反手所关闭的原 short 均亏，合计 `-0.311652`；随后建立的两笔 long 均盈利，说明净效果集中依赖后续大行情，而非反手本身稳定。

这说明失败不是“少抓到一次大趋势”，而是 fresh cross + 单日 slope-loss + 直接反手在震荡区生成了额外路径，并且较早退出了部分原本可继续持有的趋势。

[D-only 失败首位交易路径 HTML](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_failed_first_c001_development_trade_path.html)严格展示 `D=[0,259)`：提供 C001/V4 切换、MA7/ATR/RSI/state/equity、20/10 笔逐笔入出场连线和交易表。文件 SHA256 为 `0e53a79c2a86a12b43aa835ae933f49e0777369855058afb0dae7ed098569f17`；它是失败候选诊断，不是 champion 或 OOS 报告。

## 遗留问题

1. **slope-loss 过于抖动。** 单日失效会把正常趋势回踩当作终止；简单把确认从 1 日改成 2 日并未形成可支配平台，而 structure OAT 中完全关闭该退出反而大幅改善 anchor，说明问题更像退出状态定义错误，不是阈值略偏。
2. **direct reversal 放大错误事件。** fresh opposite cross 出现时立即两次 fill，不仅付出双边成本，还可能把一个错误退出直接变成反向错误仓位。C001 的两次 short→long 原子反手均亏损。
3. **ATR band 没有实现预期保护。** `H=0.5` 与 `0.75` 在许多入围父节点 path-equal，`H=1.0` 通常更差；关闭 band 的 OAT 反而优于 anchor。当前“先 fresh cross，再等 band”的状态语义并未提供稳定的趋势容错。
4. **freshness 仍会在震荡区重复产生低质量事件。** 候选相对 V4 多出 10 笔，9 笔亏损；提高 slope 到 `0.04×ATR7` 只能减少一部分，不能解决事件质量。
5. **RSI TP 有效但只是局部修复。** 其 3 笔全部获利，值得作为新机制假设保留；不能据此把 C001 登记或将 `25/2` 当作已验证生产参数。
6. **overbought memory 没有可识别样本。** Structure OAT 关闭它完全 path-equal，Stage D 的 `{2,3,4}` 全部与父 C 路径相同；当前历史不能判断怎样融合，不应继续微调天数。
7. **收益—回撤前沿不兼容。** `N=2` 等设置能显著降低回撤，却同时失去大部分 V4 收益；现有参数空间没有“同一机制下兼得”的证据。

## 裁决与下一研究边界

本轮在 Development 停止。不得：

- 用后排 final-pool 配置替补 C001；
- 在看到 D 结果后扩展阈值继续救援；
- 揭示 V/H、运行 final 或创建伪 champion；
- 将 C001、RSI `25/2` 或任何 D 极值登记为 V5。

若继续，必须另写 materially new mechanism 合同并重新锁定前瞻边界。最有信息量的方向不是继续调 `N/A/H/T/M`，而是分别验证：

- 将“趋势仍在”定义为独立的持仓状态或迟滞斜率，而非单日 slope-loss；
- opposite fresh event 先平仓，只有新的独立确认事件才反手；
- 把 extra-cross whipsaw 作为明确待过滤对象，但过滤器不得使用本轮已揭示 D 的逐笔标签选参；
- 把 RSI short TP 作为待前瞻复验的模块，而非已获 promotion 的结论。

## 证据索引

- [预注册合同](../specs/hype-1d-ma7-intent-optimization-preregistration-2026-08-09.md)
- [完整 174-row trials](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_development_trials.json)及其 [SHA256](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_development_trials.sha256)
- [Development 机器裁决](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_development.json)及其 [SHA256](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_development.sha256)
- [Manifest](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_manifest.json)及其 [SHA256](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_manifest.sha256)
- [冻结编排器](../scripts/research_hype_1d_ma7_intent_optimization.py) · [策略引擎](../scripts/hype_1d_ma7_intent_search_engine.py) · [公平 MDD](../scripts/hype_1d_ma7_intent_fair_metrics.py) · [状态 trace](../scripts/hype_1d_ma7_intent_state_trace.py) · [逐笔归因](../scripts/hype_1d_ma7_intent_evidence.py) · [exact V4 adapter](../scripts/hype_1d_ma7_v4_fair_adapter.py) · [HTML renderer](../scripts/render_hype_1d_ma7_intent_optimization_trade_path.py)
- [Development 消融报告](../ablations/hype-1d-ma7-intent-optimization-development-ablation-2026-08-09.md)
- [D-only 失败首位交易路径](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_failed_first_c001_development_trade_path.html)及其 [SHA256](../artifacts/hype_1d_ma7_intent_optimization_2026-08-09_failed_first_c001_development_trade_path.sha256)
