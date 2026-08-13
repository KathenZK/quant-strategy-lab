# HYPE 1D MA7 PEHC 前瞻观察器 V1 冻结补充协议

> 冻结日期：2026-08-10。适用对象仅为已冻结 shadow candidate `PEHC_294` 与唯一 control exact V4 `1x`。本补充协议只补齐前瞻执行与一次性裁决口径，不修改 PEHC 状态机、参数、原预注册合同或历史结论。

## 1. 身份与不可变输入

- 上游预注册合同、PEHC manifest、shadow candidate、prospective protocol 及其 SHA256 sidecar 必须全部存在且通过校验。
- shadow candidate 必须仍为 `PEHC_294`，config SHA256 必须与冻结 artifact 一致；所有上游 implementation pins 必须与当前磁盘逐项一致。
- observer 自身协议、脚本和测试另建 manifest 并冻结 SHA256。observer 不写回或替换任何上游 artifact。
- 数据是唯一允许增长的输入；代码、参数、阈值、样本门与比较门不得随新增结果变化。

## 2. 数据与冷启动口径

- 前瞻起点固定为 `2026-08-11T00:00:00Z`。
- 每次观察先通过标准数据湖 trusted loader 校验 HYPEUSDT perpetual `1h` OHLCV 与 funding；只使用最后一个可证明前一 UTC 日已经完整闭合的 `00:00 UTC` open 作为 terminal。
- 全部早于前瞻起点的数据只用于 SMA7、ATR7、RSI6、V4 特征和冻结 anchor 的 warm-up；不得携带 actual position、shadow、pending、cooldown、PnL 或资金状态进入前瞻窗。
- requested window 从 `2026-08-11` 开始；为保持已冻结 nonzero flat-start 公平口径，首个可执行 open 为 requested start 后一日 open，候选与 exact V4 使用完全相同窗口。
- terminal 的研究性强制平仓只用于统一 mark-to-market；`terminal_flatten` 不计入“闭合交易数”或多空样本门。

## 3. 观察与最早裁决终点

- 新增完整 UTC 日不足 `90` 时，observer 只输出数据范围、天数、数据哈希、pin 状态和 `INSUFFICIENT_FUTURE_DATA`；不得计算或披露候选/对照收益与回撤。
- 达到 `90` 日后，允许只为样本充足性重放冻结候选与 exact V4；若交易或 handoff 样本不足，只持久化自然闭合交易计数与 handoff 计数，不持久化绩效。
- 裁决终点不是人工选择的运行日。observer 必须在当前可用数据中寻找第一个同时满足原协议全部样本门的 terminal，并锁定该最早 terminal；之后新增数据不得延长或替换该裁决窗。
- 自然闭合交易和 handoff event 的时间必须严格早于 terminal；发生在 terminal open 的事件不属于该前缀窗口。

## 4. 一次性锁与恢复

- 样本门第一次满足后，先独占写入 access lock，记录最早 terminal、使用的数据前缀哈希、样本计数、observer pins 与上游 artifact chain，且不记录绩效。
- access lock 存在后只能对完全相同的数据前缀恢复裁决；数据湖后续追加不改变已锁窗口。前缀数据发生修订或哈希漂移时 fail closed。
- final artifact 与完整逐笔 HTML 均为独占写入。final 一旦存在，只允许校验并返回既有裁决，禁止第二次揭示或覆盖。

## 5. 一倍最终门

样本门沿用原协议：候选与 exact V4 各至少 5 笔自然闭合交易；二者 long、short 各至少 2 笔；候选至少 2 个 handoff opportunity、1 次 handoff accept。

样本通过后一次性运行并同时要求：

1. base 成本后候选收益严格高于 exact V4；
2. 候选真实 chronological `1h` MDD 严格小于 exact V4；
3. 收益差至少 `5pp` 或 MDD 改善至少 `2pp`；
4. `8bps/fill` 不发生收益与 MDD 双劣；
5. funding-off 不破产；
6. candidate、exact V4、handoff-off 的逐笔账本 replay parity 全通过；
7. handoff opportunity/accept 实际激活，且 candidate 相对 handoff-off 的经济交易路径发生变化。

任一硬门失败即 `FAIL`，不得用同一前瞻窗改参数救援。只有 `PASS` 才解除 `<=3x` 杠杆研究锁；在此之前 observer 不运行、不输出、不选择任何杠杆结果。

## 6. 状态与后续

- `INSUFFICIENT_FUTURE_DATA`：继续积累，不判成败。
- `PASS`：只表示 PEHC `1x` 获得进入预注册杠杆研究的资格；promotion/live-ready 仍需独立门禁。
- `FAIL`：PEHC 冻结分支终止；先做失败归因，再从严格晚于已锁 terminal 的新起点预注册 materially new 机制，旧窗口不得复用为 OOS。

