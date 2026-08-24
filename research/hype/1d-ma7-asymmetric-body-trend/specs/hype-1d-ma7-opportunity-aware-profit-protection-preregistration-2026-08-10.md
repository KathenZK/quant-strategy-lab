# HYPE 1D MA7 机会感知利润保护研究预注册合同

> 冻结日期：2026-08-10。研究代号：`OAPP`（Opportunity-Aware Profit Protection）。状态：`explore / not promoted / not live-ready`。本合同是 WTL hard-gate FAIL 后的独立研究，不修改 WTL、exact V4 或任何已锁产物。

## 1. 目标与证据角色

唯一 `1x` control 是登记的 exact `HYPE-1D-MA7-Asymmetric-Body-Trend-V4`。目标是在同一成交、成本、funding 与真实 `1h` chronological MDD 口径下，以最低新增复杂度改善 V4 的趋势结束：

- 多头在产生足够 MFE 后，按 close-based giveback 锁定利润；
- 盈利空头在 RSI6 连续低位后止盈；
- 不改变 V4 的趋势开始、natural reclaim、forced reversal、保护 stop、cooldown 或仓位状态机。

全部既有 D、V、TPR 与 WTL 结果均为 researcher-exposed Development。OAPP 不能把它们称作 OOS。

- `D=[0,259)`、`V=[269,346)`：exposed Development。
- Purge：`[259,269)` 与 `[346,356)`。
- Rolling folds：`[130,173)`、`[173,216)`、`[216,259)`、`[270,295)`、`[295,320)`、`[320,346)`；非零左界只预热指标，策略从左界下一日 open flat-start。
- `H=[356,432)`：唯一 one-shot final；冻结唯一 1x champion 与所有杠杆臂前，任何 OAPP 候选不得读取 H 指标、交易或路径。

## 2. 固定实现与成本

- exact V4 的 SMA7/ATR7、信号、natural entry、native exit、intraday stop、forced reversal、cooldown、max hold全部保留。
- 新增退出只使用截至日线 signal close 已知的数据，最早次日 open成交；退出后flat并沿用该侧V4 cooldown，不反手、不pending。
- 日开原因优先级：`short_rsi_take_profit` → `long_mfe_*_exit` → exact V4 native daily exit；更早发生的真实 `1h` stop自然优先。
- 手续费 `0.001/fill`；base slippage `4bps/fill`；stress `8bps/fill`；真实 funding timestamp/rate；原子反手两个fill。
- 主MDD是按真实timestamp回放的 chronological `1h` MDD；daily-extreme只作压力审计。
- 任一时点 equity `<=0` 立即归零并失败；账本 terminal equity、cost、funding、turnover、trade count必须一致。

## 3. Stage A：957个单模块宽搜

### 3.1 Long MFE/giveback：912个

使用 actual entry 后截至 signal close 的最高 close。要求：

- `peak_excursion_atr=(peak_close-entry_price)/ATR7_t >= activation`；
- signal close 仍有严格高于 `0.28%` 的 gross profit；
- giveback 条件连续满足 `confirm_days`；equality按触发，未激活/非有限/profit guard失败重置。

冻结网格：

- activation ATR：`{0.5,0.75,1,1.25,1.5,2,2.5,3,3.5,4,5,6}`；
- ATR giveback：`{0.15,0.25,0.35,0.5,0.75,1,1.25,1.5,2,2.5,3}`；
- fraction giveback：`{0.10,0.15,0.20,0.25,0.35,0.50,0.65,0.80}`；
- confirm days：`{1,2,3,4}`。

计数：`12×(11+8)×4=912`。

### 3.2 Short RSI6：45个

Wilder RSI周期固定6；threshold `{10,15,20,25,30,35,40,45,50}` × 实际持空连续日 `{1,2,3,4,5}`。要求 `RSI6<threshold`，equality重置，且 signal close 的gross short profit严格覆盖`0.28%`。

Stage A 每行在D、V运行，保留错误、休眠与重复经济路径。每族先按 D+V trades hash去重，再最多保留16个：无错误/破产、真实激活、至少一域路径变化、两个域均不双劣；排序为双重支配域数、最差域收益差、最差域MDD差、D×V复合权益、参数复杂度、ID。

## 4. Stage B：路径去重与稳健性

两族各最多16个运行D/V `8bps`和6个rolling folds；按完整D+V经济路径再次去重，每族最多保留8个。资格：

- base与8bps无错误/破产，D/V不双劣；
- rolling至少4/6个candidate/control pair都有已平交易，任何fold不得双劣；
- rolling复合收益与worst chronological MDD优先；
- 路径相同只保留复杂度更低、ID更小的一行。

## 5. Stage C：最多64个两模块组合

只组合 Stage B 的最多8个 long exit × 最多8个 short RSI；不加入entry filter或short MFE。每个组合必须同时启用两模块，all-off、long-only和RSI-only作为因果控制单独保留。

### 5.1 机会感知 prepass

候选必须：

- D和V收益严格高于exact V4、真实`1h` MDD严格更小；每域至少一项material：收益差`>=5pp`或MDD改善`>=2pp`；
- D/V经济路径均改变；D至少8笔且long/short各至少3笔；D+V合计至少12笔；V至少1笔而不是机械要求3笔；
- long MFE在D+V合计至少2次且V至少1次；RSI在D+V合计至少2次；
- exact V4 V的eligible closed episodes仍至少3个，并逐项记录候选保护退出、被抑制forced reversal与后续再入场，证明交易数下降来自可审计状态转移而不是漏单。

### 5.2 Deep gate

最多32个prepass通过者进入：D/V `8bps`、funding-off、6 folds、retained trades/path与独立episode审计。要求：

- 8bps每域不双劣，funding-off非破产；
- rolling复合收益严格更高、worst MDD严格更小且material；任何fold不双劣，至少4/6 active pair；
- D+V改变的独立entry episode至少3个、正增量episode至少3个；把最大正增量episode剔除后，剩余配对增量净PnL仍严格为正；
- 至少2个rolling fold发生候选路径变化，避免全靠单一时间块。

### 5.3 多轮消融与唯一 champion

对deep gate前16名完整执行：

1. `leave-one-out`：分别关闭long MFE、short RSI；
2. `keep-one-only`：分别只保留long MFE、short RSI；
3. `adjacent-neighbor`：activation、giveback、confirm、RSI threshold/days各上下相邻一档；
4. all-off逐笔/账本等于exact V4；
5. 配对episode与最大正增量剔除复核。

两个模块必须在D+V真实激活且leave-one-out改变路径；关闭任一模块不得在D、V两域都反向支配原候选；至少一个相邻参数组合通过prepass与deep gate。只冻结排序第一名，H失败后不得替补。

## 6. 杠杆预冻结

仅当唯一 1x champion 成立，才在D+V运行并在揭H前冻结：

- fixed：`1.25,1.50,2.00,2.50,3.00x`；
- ATR risk budget：`10%,15%,20%`，`L=clip(risk_budget/(1.5×ATR7/entry_price),0.5,3.0)`；
- quality-adjusted ATR R15：上述15%再乘`clip(0.75+signed_ER7,0.75,1.50)`。

base/8bps/funding-off必须非破产、target不超过3x。预冻结D/V的20/25/30/35/40/50% MDD预算Pareto；杠杆不参与1x champion选择。

## 7. H one-shot

冠军、实现hash、9个杠杆臂和H访问锁全部冻结后，同一次运行 exact V4、1x champion和9个杠杆臂。1x成功仍要求H收益严格更高、真实1h MDD严格更小、material、路径改变、机会审计一致、candidate至少1笔/control至少3笔、非破产与账本一致。

只有1x H PASS后，杠杆收益才可解释；按H与全窗的MDD上限`20/25/30/35/40/50%`报告最大收益。超过35%不得称低风险，超过50%只作失败审计。H后不调参、不替补、不扩网格；FAIL/INSUFFICIENT则等待新增前瞻数据。

## 8. 证据与状态

- Manifest前测试覆盖957枚举、严格边界、MFE/RSI、机会配对、最大赢家剔除、路径去重、rolling、8bps、账本、破产、杠杆3x上限和H锁。
- Artifact前缀固定为`hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10`；JSON/HTML独占写入并带SHA256 sidecar。
- 任一源码pin漂移、异常或下游产物提前存在均fail closed。
- 无论结果如何都不修改V4、不登记V5、不promotion、不推进runner。

