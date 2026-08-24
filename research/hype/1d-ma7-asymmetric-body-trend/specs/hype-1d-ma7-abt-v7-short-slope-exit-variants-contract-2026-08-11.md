# HYPE-1D-MA7-ABT-V7 Short Slope Exit Variants 诊断合同

> 冻结时间：2026-08-11（首次运行前）。状态：`post-reveal diagnostic-only / not promoted / not live-ready`。

## 研究问题

V7 空头使用 `slope_exit_lookback=1`，当 MA7 一日下降斜率消失时退出空头。`2025-11-03` 空单在 `2025-11-11` 因单日 MA7 上拐退出，之后价格继续下行，显示该退出可能过敏。本诊断只测试空头斜率退出的三类替代口径，观察是否能保留 `2025-11` 这类趋势，同时不放大其他区间风险。

## 固定变体

Control：

- `CTRL_EXACT_V7`：原始 V7，空头 `slope_exit_lookback=1`。

变体：

1. `SHORT_SLOPE_LOOKBACK_2`：空头斜率退出改为 `slope_exit_lookback=2`。
2. `SHORT_SLOPE_LOOKBACK_3`：空头斜率退出改为 `slope_exit_lookback=3`。
3. `SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA`：只有当 `MA7[t] > MA7[t-1]` 且 `close[t] > MA7[t]` 时退出空头。
4. `SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA_0P25ATR`：上述条件再要求 `close[t] - MA7[t] >= 0.25 * ATR7[t]`。
5. `SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA_0P50ATR`：上述条件再要求 `close[t] - MA7[t] >= 0.50 * ATR7[t]`。
6. `SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA_0P75ATR`：上述条件再要求 `close[t] - MA7[t] >= 0.75 * ATR7[t]`。

## 固定不变量

- 只修改空头 `ma7_slope_exit` 触发口径。
- 不修改入场、V7 short cooldown、OAPP、PEHC、多头退出、保护止损、trailing、max hold、手续费、滑点或 funding。
- 成交时间保持原引擎：日线条件在闭合日识别，下一可执行 open 出场；若原引擎支持小时保护止损，保留原行为。
- 不生成 HTML，不登记 V8，不创建 live spec，不推进 runner。

## 输出要求

每个变体输出全窗收益、真实 `1h` MDD、交易数、胜率、PF、成本、funding、最大 marked leverage、退出原因计数，以及 `2025-11-03` 与 `2026-07-12` 两笔空单的持有/退出变化。

对收益高于 V7 或 MDD 优于 V7 的候选运行压力包：

- `8 bps` 滑点；
- funding-off；
- 额外 `1d` signal lag；
- 8个54日 cold-flat block；
- 最近 `1d/7d/1m/3m/6m/1y` 分片。

## 裁决纪律

- `POST_REVEAL_CANDIDATE_ONLY`：全窗收益高于 V7、真实 `1h` MDD 不差于 V7、`8 bps` 为正、`1d lag` 为正、8个block全正。
- 若收益来自单笔已揭示修复但 MDD/lag/block明显恶化，裁决为 `FAIL / overfit-risk`。
- 任何通过都只作为 clean prospective 观察假设，不修改 V7。
