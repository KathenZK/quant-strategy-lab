# HYPE-1D-MA7-ABT-V7 Reverse-K RSI Reclaim 诊断合同

> 冻结时间：2026-08-11（首次运行前）。状态：`post-reveal diagnostic-only / not promoted / not live-ready`。

## 研究问题

测试用户提出的规则：MA7 突破/跌破当天，如果前10天有一半或60%以上是反向K，并且过去10天 RSI6 出现过 `30/70` 极值，则即使 V7 的 slope/buffer 不成熟，也允许开单。

本轮只判断该规则是否能补到 `2025-08-07`、`2026-02-06/09`、`2026-04-04/07` 这类行情，并评估它是否释放噪声。结果不得直接修改 V7、登记新版本、生成 HTML、创建 live spec 或推进 runner。

## 固定规则

- V7 原生 entry 优先；只有 V7 原生 `close_entry_signal=false` 时才进入本规则。
- 触发日必须是 raw MA7 cross：
  - long：前一日 `close <= MA7`，当日 `close > MA7`；
  - short：前一日 `close >= MA7`，当日 `close < MA7`。
- 前10个已闭合日的反向K占比达到阈值：
  - long 的反向K：`close < open`；
  - short 的反向K：`close > open`。
- 前10个已闭合日 RSI6 出现过极值：
  - long：`min(RSI6) <= 30`；
  - short：`max(RSI6) >= 70`。
- 可选距离上限防追高/追空：`distance_atr <= max_distance_atr`。
- 入场为次日 open；OAPP、PEHC、cooldown、成本、funding 与 V7 保持一致。

## 固定搜索网格

- `side_scope`：`both`、`long_only`、`short_only`。
- `reverse_ratio`：`0.50`、`0.60`。
- `max_distance_atr`：`1.00`、`1.50`、`INF`。
- `target_leverage`：`1.00`、`0.50`、`0.25`。

总候选：`3 × 2 × 3 × 3 = 54`，外加 control。

## 必须输出

对 control 与全部候选输出全窗收益、真实 `1h` MDD、交易数、胜率、PF、成本、funding、最大 marked leverage、exhaustion reclaim 触发计数。

对全窗双优候选与收益前20个非control 候选运行完整压力包：`8 bps`、funding-off、额外 `1d` signal lag、8个54日 cold-flat block、最近 `1d/7d/1m/3m/6m/1y`。

## 裁决纪律

- `POST_REVEAL_CANDIDATE_ONLY`：全窗收益高于 V7、真实 `1h` MDD 不差于 V7、`8 bps` 为正、`1d lag` 为正、8个block全正。
- 即使通过，也只作为未来 clean prospective 观察假设，不修改 V7。
- 若交易数明显增加、MDD扩大、lag/block失败或收益改善只来自暴露期特例，裁决为 `FAIL / noise-releasing` 或 `FAIL / overfit-risk`。
