# HYPE-1D-MA7-ABT-V7 Reverse-K RSI Follow-Through 诊断合同

> 冻结时间：2026-08-11（首次运行前）。状态：`post-reveal diagnostic-only / not promoted / not live-ready`。

## 研究问题

测试“反向K+RSI极值”不直接入场，而是作为 raw MA7 cross 当天的背景标签；随后等待 `1-4` 天内出现同方向 follow-through，才允许开单。目标是减少上一轮 reverse-rsi reclaim 直接触发带来的噪声，同时观察是否仍能补到 `2025-08-07`、`2026-02-06/09/10`、`2026-04-04/07` 这类行情。

本轮只生成诊断证据，不修改 V7，不登记新版本，不生成 HTML，不创建 live spec，不推进 runner。

## 固定规则

- V7 原生 entry 优先；只有原生 V7 不识别时才建立或确认本标签。
- raw MA7 cross 当天若满足：
  - 前10个已闭合日反向K占比达到阈值；
  - long 的 `min(RSI6) <= 30`，short 的 `max(RSI6) >= 70`；
  - side_scope 允许该方向；
  则建立 reverse-rsi tag，但不入场。
- 后续若在 `[min_age_days, max_age_days]` 内满足：
  - 仍在 MA7 正确侧，未 recross；
  - 相对 tag 日 close 的同方向推进至少 `min_progress_atr`；
  - 当前 MA7 距离不超过 `max_distance_atr`；
  则次日 open 入场。
- OAPP、PEHC、cooldown、成本、funding 与 V7 保持一致。

## 固定搜索网格

- `side_scope`：`both`、`long_only`、`short_only`。
- `reverse_ratio`：`0.50`、`0.60`。
- `max_age_days`：`2`、`4`；`min_age_days` 固定为 `1`。
- `min_progress_atr`：`0.00`、`0.25`、`0.50`。
- `max_distance_atr`：`1.25`、`1.50`、`INF`。
- `target_leverage`：`1.00`、`0.50`、`0.25`。

总候选：`3 × 2 × 2 × 3 × 3 × 3 = 324`，外加 control。

## 必须输出

对 control 与全部候选输出全窗收益、真实 `1h` MDD、交易数、胜率、PF、成本、funding、最大 marked leverage、tag arm/confirm/expire/recross 计数。

对全窗双优候选与收益前20个非control 候选运行完整压力包：`8 bps`、funding-off、额外 `1d` signal lag、8个54日 cold-flat block、最近 `1d/7d/1m/3m/6m/1y`。

## 裁决纪律

- `POST_REVEAL_CANDIDATE_ONLY`：全窗收益高于 V7、真实 `1h` MDD 不差于 V7、`8 bps` 为正、`1d lag` 为正、8个block全正。
- 即使通过，也只作为未来 clean prospective 观察假设，不修改 V7。
- 若交易数明显增加、MDD扩大、lag/block失败或收益改善依赖暴露期特例，裁决为 `FAIL / noise-releasing` 或 `FAIL / overfit-risk`。
