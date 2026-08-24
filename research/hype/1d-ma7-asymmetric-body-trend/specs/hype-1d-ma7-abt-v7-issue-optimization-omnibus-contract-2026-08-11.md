# HYPE-1D-MA7-ABT-V7 Issue Optimization Omnibus 诊断合同

> 冻结时间：2026-08-11（首次运行前）。状态：`post-reveal diagnostic-only / not promoted / not live-ready`。

## 研究问题

把当前对 V7 的策略分析判断落到可复现回测：

1. V7 是 fresh MA7 reclaim/反手事件捕捉器，不是完整趋势识别器：测试 delayed impulse confirmation 是否能补到迟到趋势。
2. V7 空头 max_hold 会截断仍在下行的趋势：测试空头 max_hold 趋势延长是否有效。
3. PEHC 能补反手但也会放噪声：测试禁用 PEHC entry 后的净贡献。
4. 空头 `ma7_slope_exit` 过敏问题已由独立诊断覆盖，本报告整合其证据，不重新扩大搜索。

## 固定诊断 A：Delayed Impulse Confirmation

只在 V7 原生 entry 不触发时启用 fallback：

- raw MA7 cross 当天满足前10日反向K占比 `>= 0.50` 且 RSI6 过去10日触及 long `<=30` / short `>=70`；
- tag 日趋势侧20日区间位置 `side_pos20 <= {0.45, 0.55}`；
- 后续 `1-4d` 内出现同向 impulse candle：
  - `body_vs_med20 >= {1.50, 2.00, 2.50}`；
  - `body_range >= {0.55, 0.65}`；
  - 相对 tag close 的同向推进 `>= {0.50, 0.80} ATR7(tag)`；
- `side_scope ∈ {both, long_only, short_only}`；
- fallback 目标杠杆 `{0.50, 1.00}`。

总候选：`3 × 2 × 3 × 2 × 2 × 2 = 144`。

## 固定诊断 B：Short Max-Hold Trend Extension

只修改空头 max_hold 出场：

- control：V7 原始 `max_hold_days=20`；
- `EXTEND_5` / `EXTEND_10`：到达 max_hold 时，若 `close < MA7` 且 MA7 仍下降，则最多延长5/10日；
- `EXTEND_5_D0P25` / `EXTEND_10_D0P25`：上述条件再要求 `(MA7-close)/ATR7 >= 0.25`。

其他出场优先级、OAPP、PEHC、保护止损、成本与 V7 不变。

## 固定诊断 C：PEHC Entry Contribution

- `PEHC_ENTRY_DISABLED`：保留 OAPP、原生 entry 和 exits，但禁用 PEHC entry；用于观察 PEHC 在 V7 全路径中的净贡献和风险。

## 输出与压力

所有候选输出全窗收益、真实 `1h` MDD、交易数、胜率、PF、成本、funding、最大 marked leverage、退出原因计数、fallback/PEHC 事件计数、重点交易变化。

对收益高于 V7 或 MDD 不差于 V7 的候选运行压力包：

- `8 bps` 滑点；
- funding-off；
- 额外 `1d` signal lag；
- 8个54日 cold-flat block；
- 最近 `1d/7d/1m/3m/6m/1y`。

## 裁决纪律

- `POST_REVEAL_CANDIDATE_ONLY`：全窗收益高于 V7、真实 `1h` MDD 不差于 V7、`8 bps` 为正、`1d lag` 为正、8个block全正。
- 若只修复单笔但整体收益/MDD/lag/block恶化，裁决 `FAIL`。
- 任何结果都不修改 V7、不登记 V8、不生成 HTML、不创建 live spec、不推进 runner。
