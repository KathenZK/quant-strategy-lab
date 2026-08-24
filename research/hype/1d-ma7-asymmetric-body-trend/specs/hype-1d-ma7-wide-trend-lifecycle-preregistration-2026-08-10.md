# HYPE 1D MA7 广域趋势生命周期研究预注册合同

> 冻结日期：2026-08-10。研究代号：`WTL`（Wide Trend Lifecycle）。状态：`explore / not promoted / not live-ready`。本合同不修改已登记的 exact V4，不登记 V5，不向 runner 交接。

## 1. 目标与前次失败复盘

唯一 `1x` control 是已登记 `HYPE-1D-MA7-Asymmetric-Body-Trend-V4` 的 exact 实现。目标是在同数据、同成本、同 funding、同执行账本和同风险计量器下，找到一个能更准确识别趋势开始、持续与结束的低复杂度状态机，并在唯一未揭示区间同时实现：

- 成本后收益严格高于 exact V4；
- 真实 chronological `1h` MDD 严格小于 exact V4；
- 至少一项达到 materiality：收益差 `>=5pp` 或 MDD 改善 `>=2pp`。

上一轮 TPR 的 `RSI6<25 × 2d` 只在 Development 的4段明显下跌中触发，改善集中在一个 WFO fold；Validation 中0次触发、逐笔与 V4相同。`signed_ER7` hard reject会删除高价值 fresh reclaim，连续2/3日非正 slope 的 long exit又在真实路径中完全休眠。WTL 因而不再围绕单一已选参数救援，而是把上一轮 D 与 Validation 全部降级为 researcher-exposed Development，广泛搜索实际能触及 long/short 常见盈利路径的 MFE/giveback保护，同时重新审计低复杂度入场质量与 short RSI。

## 2. 数据边界与唯一最终检验

- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 数据：432根完整 UTC 日 K；底层 closed `1h` 与 funding沿用已审计数据湖，任何新增缺口、重复、关键空值、OHLC或raw/normalized blocker均 fail closed。
- Exposed Development：`D=[0,259)` 与上一轮已揭示 `V=[269,346)`；`[259,269)` purge不用于绩效。
- Exposed rolling folds：`[130,173)`、`[173,216)`、`[216,259)`、`[270,295)`、`[295,320)`、`[320,346)`；非零左界均只作指标/关系预热，策略从左界下一日 open开始 flat-start。
- Final Holdout：`H=[356,432)`；`[346,356)` purge。任何 WTL 候选、短名单、消融、杠杆选择在冻结前不得读取 H 绩效、交易或路径。
- exact V4 的历史全窗结果已知，不把它冒充 prospective；本合同只保证 WTL 候选的 H 是单次未揭示裁决。

H 是一次性 final，不再设置可反复救援的 Validation。H FAIL 后不得在本合同下改参数或选择替补。

## 3. 固定执行与风险口径

- 日线只读闭合日 `t`，日线信号最早 `t+1` open成交；intraday protective stop、forced reversal和funding严格按真实 `1h`/event timestamp。
- fee `0.001/fill`；base slippage `4bps/fill`；stress `8bps/fill`；原子反手按平旧、开新两个fill收费。
- 主风险：冻结 ledger按真实timestamp重放的 `chronological_1h_mdd`；必须与回测terminal equity、cost、funding、turnover和trade count一致。
- 压力风险：exact V4 compatible `daily_extreme_mdd`；同日只作为保守极值压力，不伪称真实high/low顺序。
- 任何时点equity `<=0`立即冻结为0并 fail closed；不得在后续价格恢复后“复活”。
- `1x` 信号先独立选择；杠杆不能参与信号排名，也不能救援失败的 `1x`。

## 4. exact V4 保留项与新增模块优先级

WTL 保留 exact V4 的 SMA7/ATR7、natural reclaim、slope、entry buffer、`0.75ATR`持仓迟滞、intraday trailing/protective stop、forced reversal MA-only确认、max hold、cooldown、成本与 funding。新增模块不得创造 persistent-regime入场，也不得过滤 forced reversal。

每个日开先处理上一完整日已确定的 WTL exit；同价原因优先级固定为：

1. `short_rsi_take_profit`；
2. 对应方向的 `mfe_atr_trail_exit` 或 `mfe_fraction_trail_exit`；
3. exact V4 native daily exit。

已经在更早真实 `1h` 时间发生的 exact V4 protective stop自然优先。新增日线退出沿用该侧 exact V4 cooldown，不反手、不pending。

## 5. Stage A：555个单模块广搜

另保留 `C000_EXACT_V4` control；下列555个 arm 均只启用一个模块，在 D 与已暴露 V 运行 base `4bps`。所有组合、异常与休眠行都必须写入冻结 artifact，不得只保存赢家。

### 5.1 趋势开始：195个自然入场过滤

过滤只作用于 exact V4 已成立的 natural close entry，所有 equality均不通过，非有限值fail closed，无延迟入场。

- `signed_ER`：lookback `{3,5,7,10,14}` × threshold `{-0.25,-0.10,0,0.10,0.20,0.30,0.40}` × scope `{both,long,short}`，共105。
- `max_chase_atr`：要求 `side×(close-MA7)/ATR7 < cap`；cap `{0.25,0.50,0.75,1.00,1.50,2.00,3.00}` × scope3，共21。
- `entry_slope_atr`：要求 `side×(MA7_t-MA7_{t-1})/ATR7_t > threshold`；threshold `{0,0.01,0.02,0.04,0.06,0.08,0.10}` × scope3，共21。
- `directional_persistence`：最近lookback个日收益中与side同向的比例严格大于threshold；lookback `{3,5,7,10}` × threshold `{0.50,0.60,0.70,0.80}` × scope3，共48。

### 5.2 多头趋势结束：168个 MFE/giveback保护

只使用实际entry后、截至signal close已知的最高close；`peak_excursion_atr = (peak_close-entry_price)/ATR7_t`。必须 `peak_excursion_atr >= activation` 且signal close仍有严格大于`0.28%`的gross profit。

- ATR trail：activation `{0.5,1,1.5,2,3,4}` × giveback ATR `{0.25,0.50,0.75,1,1.25,1.50,2,2.50}` × confirm `{1,2}`，共96；触发为 `(peak_close-close)/ATR7_t >= giveback`。
- Fraction trail：相同6个activation × giveback fraction `{0.15,0.25,0.35,0.50,0.65,0.80}` × confirm `{1,2}`，共72；触发为 `(peak_close-close)/(peak_close-entry_price) >= fraction`。

确认日只统计连续满足日，equality满足 `>=`；未激活、非有限或profit guard失败均重置为0。

### 5.3 空头趋势结束：168个 MFE/giveback保护

与多头完全对称，使用截至signal close已知的最低close；`peak_excursion_atr=(entry_price-trough_close)/ATR7_t`。ATR/fraction/activation/confirm网格与多头相同，共168。

### 5.4 Short RSI6：24个止盈

Wilder RSI周期固定6；threshold `{15,20,25,30,35,40}` × 连续实际持仓日 `{1,2,3,4}`，共24。要求 `RSI6<threshold`，equality重置；signal close gross short profit严格覆盖`0.28%`后次日open平空。

## 6. 分层选择与组合搜索

### 6.1 Stage A shortlist

每个家族最多保留8个 single-module arm。资格：无错误/破产、在D或V真实激活且经济路径改变、D和V均不相对V4同时收益更低且MDD更差。排序依次为：双重支配域数量、较高的最差域return delta、较高的最差域MDD delta、D×V复合权益、较少参数自由度、arm ID。

### 6.2 Stage B稳健性

四个家族的shortlist运行D/V base与8bps、6个exposed flat-start rolling fold。每家族最多保留4个：先按无破产/账本一致、更多非双劣fold、更高rolling复合return delta、更高rolling worst MDD delta、较高最差D/V return delta、较高最差D/V MDD delta、ID排序。所有结果仍须保留，不能只保存进入组合的参数。

### 6.3 Stage C组合

对每个家族的 `{OFF + 最多4个Stage B survivor}` 做全笛卡尔积，去除all-off，最多 `5^4-1=624` 个组合。先在D/V base运行全部组合；按下列数值门选出最多64个进入8bps、funding-off和6-fold复核：

- D与V均严格提高收益且严格改善chronological MDD；
- D与V各至少一项material：return delta `>=5pp` 或MDD改善 `>=2pp`；
- D与V经济路径都必须不同于V4；
- D至少8笔、long/short各至少3笔；V候选与V4各至少3笔；
- 至少一个新增exit在V真实激活，避免再次冻结一个在验证路径中休眠的规则。

进入64强后还必须满足：D/V 8bps不双劣；funding-off非破产；6-fold复合收益和worst chronological MDD均严格优于对应V4且至少一项material；任何fold不得双劣；至少4/6 folds各有一笔候选与control交易。

排序：最差D/V return delta、最差D/V MDD delta、rolling return delta、rolling MDD delta、启用模块更少、交易更少、arm ID。

## 7. 多轮消融与唯一 `1x` champion

对数值门通过的前20个组合执行并完整保留：

1. `leave-one-out`：逐个关闭每个enabled模块；
2. `keep-one-only`：只保留每个enabled模块；
3. `adjacent-neighbor`：每个数值参数沿本合同有序网格向上/向下一个档位，其他不变；
4. `all-off parity`：必须逐笔等于 exact V4。

最终 champion 必须：

- 每个enabled模块在D+V至少真实激活一次且其leave-one-out改变经济路径；
- 每个enabled模块关闭后，不得在D与V两个域同时实现收益更高且MDD更小；否则该模块为负贡献并剔除，该原组合失去资格；
- 新增exit合计至少2次真实触发，且至少1次位于V；
- 至少有一个相邻参数邻居通过Stage C严格D/V双重支配，避免孤点峰值；
- all-off exact parity、base/8bps/funding-off solvency和账本门全部PASS。

仅冻结排序第一名为唯一 `1x` champion；其余不能在H失败后替补。

## 8. 杠杆预冻结（仅有 `1x` champion 后）

在D+V上运行并在揭H前冻结全部9个arm；信号、退出、cooldown不变，entry后数量固定至退出/原子反手：

- fixed target leverage：`1.25,1.50,2.00,2.50,3.00x`；
- ATR risk budget：`10%,15%,20%`，`L=clip(risk_budget/(1.5×ATR7/entry_price),0.5,3.0)`；
- quality-adjusted ATR R15：再乘 `clip(0.75+signed_ER7,0.75,1.50)`，非有限按0.75。

base/8bps/funding-off任何破产、非有限或entry target `>3x`均淘汰。D与V都必须比 `1x` champion收益更高；primary risk cap为chronological MDD `<=35%`，aggressive audit cap为`<=50%`。风险缩放不改变 `1x` champion身份。

## 9. 一次性 H 与最终裁决

冻结 implementation hashes、唯一 `1x` champion和全部9个leverage arm后，H一次性运行 exact V4、champion `1x`和9个杠杆臂。不得按H结果改参数、重新排序或选择Stage C第二名。

`1x` 目标成功必须：收益严格更高、chronological MDD严格更小、materiality满足、candidate/control各至少3笔、经济路径改变、非破产和账本一致。否则状态为 `H hard-gate FAIL`，不登记V5。

无论H成败，都只对预先冻结的杠杆臂报告事实；按MDD cap `20/25/30/35/40/50%`列出H和全窗最高净收益、目标/实际最大杠杆、破产与8bps结果。超过35%的方案不得称为可承受或低风险；超过50%只作失败审计。

## 10. 测试、证据与锁

Manifest前必须通过：

- exact V4 anchor、all-off path/trade/ledger parity；
- 195/168/168/24枚举计数、所有严格/equality/nonfinite/scope边界；
- MFE peak只读取截至signal close数据、entry/reset/confirm/profit guard/priority；
- Wilder RSI6 known vector与持仓日计数；
- 真实1h replay、atomic reversal、funding boundary、gap stop、bankruptcy；
- flat-start、D/V/H访问锁、Stage A/B/C排序、64/20 shortlist、多轮OAT；
- fixed/dynamic leverage、3x cap、Pareto与MDD caps；
- 完整逐笔交易路径HTML一致性。

Artifact前缀固定为 `hype_1d_ma7_wide_trend_lifecycle_2026-08-10`。Manifest记录数据SHA、合同与所有实现/测试SHA、完整参数清单及H未访问声明。JSON/HTML采用独占写入并带SHA256 sidecar；任一stage源码漂移、异常或已有下游artifact均fail closed。

