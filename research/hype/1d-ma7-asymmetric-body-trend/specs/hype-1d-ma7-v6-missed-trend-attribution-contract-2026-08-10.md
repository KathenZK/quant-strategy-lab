# HYPE-1D-MA7-ABT V6 漏趋势归因与隔离 Probe 合同（2026-08-10）

## 1. 研究问题与边界

本轮只回答两个问题：

1. `HYPE-1D-MA7-Asymmetric-Body-Trend-V6` 在已揭示的 432 个完整 UTC 日中，哪些事后稳定趋势段被实际覆盖，哪些未覆盖，未覆盖由同日 slope/buffer、freshness、全局 cooldown、单仓占用还是缺少因果 seed 导致；
2. 不修改 V6 状态、cooldown、OAPP、PEHC 或原交易时序时，一个固定 `0.25x`、可被 V6 无条件抢占的隔离 probe 是否存在值得前瞻验证的增量。

本轮是 `post-reveal diagnostic-only`。它不修改 V6，不登记 V7，不构成 OOS、promotion、runner handoff、杠杆解锁或实盘建议。事后趋势标签只用于归因，绝不进入 probe 信号。

## 2. 数据、成本与执行

- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 输入：冻结数据湖中的 `10,390` 根可信 `1h` K 线与 `2,597` 条 funding；聚合为 `[0,432)` 共 432 个完整 UTC 日。
- 数据加载：只允许使用 pinned `hype_1d_ma7_v4_fair_adapter.load_context()`；其市场身份、schema、连续性、闭合状态、raw/normalized 来源与 SHA 任一漂移即 fail closed。
- V6 control：固定 OAPP + `PEHC_294`，`1x`、单仓、非加仓；全窗锚点必须逐位复现 `+617.1070876096234%`、19 笔及 `PEHC_294` 配置 SHA。
- 决策：只读取已闭合 UTC 日线；所有新增 probe 最早在下一 UTC 日 open 成交。
- 成本：每 fill 手续费 `0.001`、基础不利滑点 `4 bps`、实际 funding；压力只把滑点提高到 `8 bps`。
- 风险：主口径使用真实 `1h` 时间顺序 marked-equity MDD。
- 近期切片：按数据尾端锚定 `1d/7d/1m/3m/6m/1y`，只作审计。

## 3. 事后参考趋势段

参考段完整复用 CTLS-R4 标签，不新增阈值：

1. 中心 7 日 close 回归，`abs(beta7/ATR7) >= 0.08`且`R² >= 0.35`时标为方向，否则为 `FLAT/CHOP`；
2. 三状态 Viterbi 的状态切换成本固定 `2.0`；
3. 少于 3 个完整日的方向 run：左右相同则合并，否则改为 flat；
4. 最终连续 `UP` 或 `DOWN` run 为一个 `reference_episode`，区间为 `[start 00:00, end+1d 00:00)`；
5. 全部显式标记 `hindsight_audit_only=true`。

参考段用于回答“图上有多少稳定趋势段”和“V6 覆盖了多少”，不得筛选 probe、参数或交易方向。

## 4. 因果 root opportunity

### 4.1 Raw cross

- long：`close[t-1] <= SMA7[t-1]` 且 `close[t] > SMA7[t]`；
- short：`close[t-1] >= SMA7[t-1]` 且 `close[t] < SMA7[t]`。

每个 raw cross 形成一个独立 root，最多观察 5 日。出现反向穿回、反向 cross、非有限数据或到期即结束，不跨段合并。

### 4.2 V6 原阈值与 later maturity

只复用 V6 原阈值：

- long：`distance=(close-SMA7)/ATR7 > 0`，`1d SMA7 slope/ATR7 >= 0.02`；
- short：`distance=(SMA7-close)/ATR7 > 0.10`，`2d down-slope/ATR7 >= 0.02`。

记录 cross 日的 buffer/slope 状态，并在同一 root 的 5 日有效期内寻找两项首次同时通过的日期。首次通过晚于 cross 日记为 `LATER_MATURITY / FRESHNESS_EXPIRED`。anti-chase 只报告 `0.75/1.0/1.5/INF ATR`分箱，不参与选择。

### 4.3 固定 5 日经济标签

对每个可评估 root，继续复用 DTEC 标签：

- 从确认日 close 到第 5 日 close 的方向收益严格大于 `0.0028`；
- 后续 5 个 close 至少 3 个仍在 SMA7 同侧；
- 两者同时成立才记 `trend_hit=true`；
- 尾部不足 5 日记 `UNEVALUABLE`，不得当作失败或通过。

另以确认后下一 UTC open 入场、5 个自然日后 open 退出，计算 `1x` 成本/funding 后 standalone 收益及真实小时 MAE/MFE。该固定退出只作统一经济标签，不是候选策略退出。

## 5. 逐段捕获与漏识别归因

每个参考段同时保留捕获轴、因果轴和经济轴：

1. V6 同方向实际持仓与参考段有正小时重叠：`CAPTURED`，来源细分为 `CARRY/NATIVE/FORCED_REVERSAL/PEHC_HANDOFF`；
2. 无同向暴露且没有同方向 root：`MISSED_HINDSIGHT_ONLY`；
3. root cross 日只失败 slope：`SLOPE_SAME_DAY_FAIL`；
4. 只失败 buffer：`BUFFER_SAME_DAY_FAIL`；
5. 两者都失败：`BOTH_SAME_DAY_FAIL`；
6. 5 日内两项后来成熟：附加 `LATER_MATURITY/FRESHNESS_EXPIRED`；
7. 可执行 open 已有 V6 仓位：`POSITION_OCCUPIED`；
8. V6 同 open 原生/forced/PEHC 交易优先：`CORE_PRECEDENCE`；
9. exact V6 全局 cooldown 尚未释放：`COOLDOWN_BLOCKED`；
10. 无上述阻断、同日原生条件通过却未成交：`ENGINE_INVARIANT_FAIL`，整次审计失败；
11. standalone 成本后不盈利：附加 `NON_ECONOMIC`，不得称为漏掉 alpha。

一个 raw-cross root 只归属与其有效窗重叠天数最多的同方向参考段；平局取最早参考段。每个参考段只把最早 root 作为主 root，其余保留为 secondary，不重复计数。

## 6. 隔离、可抢占 `0.25x` Probe

probe 是与 V6 状态完全隔离的 shadow satellite，规则预先固定：

1. 所有 raw-cross root 一视同仁，不读取参考段、`trend_hit`或未来收益；
2. root 在 5 日内首次满足 V6 原 buffer+slope 后，于下一 UTC open 尝试 `0.25x`；
3. 若该 open V6 已持仓、V6 同 open 将入场或另一 probe 尚未结束，则拒绝，不等待第二次机会；
4. probe 不读取、不修改 V6 cooldown、OAPP、shadow、PEHC、pending 或资金状态；
5. probe 退出取最早者：
   - closed bar 穿回 SMA7 后的下一 UTC open；
   - 入场满 5 个自然日的 UTC open；
   - V6 下一笔 core trade 的 entry timestamp，同价先平 probe、再让 V6 原交易无条件接管；
   - terminal open；
6. probe 不设置额外 hard/trailing stop；因此只能是短持有 shadow 诊断，必须报告真实 `1h` MAE/MDD，不能直接交接实盘；
7. 同一时刻先退出旧 probe，再执行 V6 core entry；全路径不得出现重叠仓位。

组合回放保持 V6 的原交易时点、价格、方向和退出不变，只让 core 每次按当时组合权益重新目标 `1x`；probe 按 `0.25x`。这衡量“隔离且可抢占”的经济增量，不声称已重放一个新的 V6 状态机。

## 7. 冻结审计矩阵

只运行：

- exact V6 control；
- exact V6 + base probe；
- exact V6 + probe，`8 bps`；
- exact V6 + probe，funding off；
- exact V6 + probe 额外延迟 1 日；
- base probe 删除最大正贡献 probe 的 leave-one-out。

禁止搜索 probe leverage、episode age、buffer、slope、退出天数、方向开关、RSI 或 anti-chase 阈值。

## 8. 输出与裁决

机器 JSON 至少包含：

- 数据质量与实现 SHA；
- V6 anchor、交易 SHA 和 replay parity；
- reference episodes、raw-cross roots、主/次 root 映射；
- 每段捕获来源、暴露小时、首次捕获延迟与主/次漏识别原因；
- cross 日门槛、later maturity、执行阻断、5 日标签、standalone 成本/MFE/MAE；
- probe 接受/拒绝、退出原因、逐笔结果；
- control/probe 的全窗、压力、funding-off、lag、leave-one-out与近期切片；
- 数据、账本、重叠、因果和 terminal invariants。

结论代码按以下顺序：

1. 任一 invariant 失败：`AUDIT_INVALID`；
2. 无未捕获且有因果 root 的参考段：`HINDSIGHT_ONLY_MISSES`；
3. probe 少于 4 个独立成交、分布少于 4 个 `54d` block：`INSUFFICIENT_INDEPENDENT_EPISODES`；
4. base probe 收益增量不为正：`NON_ECONOMIC_MISSES`；
5. 收益增加但真实 `1h` MDD 未改善：`NO_DUAL_IMPROVEMENT`；
6. base 双改善但任一 `8bps/funding-off/lag` 双劣，或删除最大赢家后增量不为正：`FRAGILE_EXPOSED_INCREMENT`；
7. 其余才可记 `EXPOSED_CAUSAL_LEAK_SUPPORTED`。

无论结果代码为何，本轮最高只允许形成下一份 clean prospective probe 合同；不得直接写回 V6 或登记 V7。
