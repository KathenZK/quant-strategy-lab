# HYPE-1D-MA7-ABT-V7 四机制逐项消融诊断合同

> 冻结时间：2026-08-11（首次运行前）。状态：`diagnostic-only / not promoted / not live-ready`。

## 研究问题

回答一个且仅一个问题：围绕用户指出的 V7 漏单、慢平仓和 exit 后不交接问题，固定四个机制，在已登记 V7 上逐项 ablation，判断这些机制是在补漏，还是在释放噪声。

本轮不搜索大网格，不根据结果修改 V7，不登记 V8，不生成交易路径 HTML，不创建 live spec，不推进 runner。

## Control

- `CTRL_EXACT_V7`：已登记 V7，short cooldown `3d`，其余 V6/OAPP/PEHC 全部不变。
- 数据、成本、funding、执行顺序、单仓、真实 `1h` 风险 replay 与 V7 一致。

## 固定候选机制

1. `M1_PENDING_RECLAIM_MATURITY`：raw MA7 cross / reclaim 出现但原生 V7 因 slope 或 buffer 未成熟而未开仓时，保留同侧 pending episode 最多 `3d`；期间若同侧仍未 recross、距离不超过 `1.5 ATR7`，且 V7 原侧 `slope` 与 `entry_buffer` 均成熟，则次日 open 入场。原生 V7 入场和 PEHC handoff 优先。
2. `M2_SHORT_RSI_RELAXED_TP`：只放宽空头 RSI 止盈为 `RSI6 < 25` 且连续 `1d`，仍要求空头毛利超过 `roundtrip_guard=0.28%`；不改变多头 OAPP、不改变入场。
3. `M3_OVERBOUGHT_EXHAUSTION_SHORT`：只新增 flat 状态下的超买衰竭空头入场。若最近 `5` 个已闭合日中至少 `3` 日 `RSI6 >= 70`，当日 close 跌到 `MA7 - 0.10 ATR7` 下方且低于前一日 close，则允许次日 open 开空；为观察该反转机会，long 退出后的 cooldown 改为方向性 cooldown（只限制同侧）。
4. `M4_POST_EXIT_COOLDOWN_OVERRIDE`：不新增信号，只把全局 cooldown 改为方向性 cooldown；退出 long 后只限制后续 long，退出 short 后只限制后续 short，允许相反方向原生 V7 信号入场。

## 组合观察

- `COMBO_ALL_FOUR`：同时启用 `M1`、`M2`、`M3` 和 `M4`，仅用于观察交互项；不得把组合结果当作搜索后的 champion。

## 必须输出

对 control、四个单项候选和组合候选，输出：

1. 全窗收益、真实顺序 `1h` MDD、日内极值 MDD、交易数、胜率、PF、long/short 交易数、成本、funding、最大 marked leverage；
2. `8 bps`、funding-off、额外 `1d` signal lag；
3. 8个54日 cold-flat block 与最近 `1d/7d/1m/3m/6m/1y`；
4. 每个机制的触发计数、被 cooldown 阻挡计数、PEHC handoff 计数、OAPP/RSI/protective/max-hold 出口计数；
5. 相对 V7 的收益差、MDD 差、交易数差和机制归因摘要。

## 裁决纪律

- 单项候选只有同时满足全窗收益更高、真实 `1h` MDD 不更差、`8 bps` 为正、额外 `1d` lag 为正、8个 block 均为正，才可标记为 `DIAGNOSTIC_CANDIDATE`。
- 若收益提高但 MDD 更差、lag/block 失败、交易数大幅增加或核心 V7/PEHC 链条被破坏，裁决为 `FAIL / noise-releasing` 或 `FAIL / chain-disruptive`。
- 即使某项通过，也只进入 clean prospective observer 假设，不直接修改 V7。
