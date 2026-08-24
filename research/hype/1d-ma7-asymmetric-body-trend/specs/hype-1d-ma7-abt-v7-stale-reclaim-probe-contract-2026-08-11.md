# HYPE-1D-MA7-ABT-V7 Stale Reclaim Maturity Probe 诊断合同

> 冻结时间：2026-08-11（首次运行前）。状态：`post-reveal diagnostic-only / not promoted / not live-ready`。

## 研究问题

专门测试 V7 漏掉的三类行情：raw reclaim 当天因为 slope 或 buffer 不成熟而不入场，但随后 `1-4` 天趋势成熟。重点观察 `2025-08-07`、`2026-02-09/10`、`2026-04-07` 这类 stale reclaim 是否能用更窄规则补票，而不是像普通 pending reclaim 那样释放大量噪声。

本轮只生成诊断证据，不修改 V7，不登记新版本，不生成交易路径 HTML，不创建 live spec，不推进 runner。

## Control

- `CTRL_EXACT_V7`：V7 原始参数，short cooldown `3d`，OAPP/PEHC 不变。
- 数据、成本、funding、执行顺序和真实 `1h` 风险 replay 与 V7 一致。

## 固定机制

当 flat 且出现 raw reclaim / raw breakdown 时，如果原生 V7 entry 未触发，则建立一个 stale reclaim episode。episode 在后续若满足以下条件，则允许次日 open 入场：

1. 仍在同一侧 MA7，未 recross；
2. 年龄在 `[min_age_days, max_age_days]` 内；
3. 该侧 V7 的 `entry_buffer` 与 `slope_min_atr` 都已成熟；
4. 当前 MA7 距离不超过 `max_distance_atr`，避免追太远；
5. cooldown 仍按 V7 原始全局 cooldown 执行；
6. 原生 V7 entry 和 PEHC handoff 优先。

## 固定搜索网格

- `side_scope`：`both`、`long_only`、`short_only`。
- `min_age_days`：`1`、`2`。
- `max_age_days`：`3`、`4`。
- `max_distance_atr`：`1.00`、`1.25`、`1.50`、`INF`。
- `probe_leverage`：`1.00`、`0.50`、`0.25`。

总候选：`3 × 2 × 2 × 4 × 3 = 144`，外加 control。

## 必须输出

对 control 和全部候选输出全窗收益、真实 `1h` MDD、交易数、胜率、PF、成本、funding、最大 marked leverage、stale episode arm/confirm/expire/recross 计数、probe 目标杠杆计数。

对全窗双优候选与收益前20个非control 候选运行完整压力包：`8 bps`、funding-off、额外 `1d` signal lag、8个54日 cold-flat block、最近 `1d/7d/1m/3m/6m/1y`。

## 裁决纪律

- `POST_REVEAL_CANDIDATE_ONLY`：全窗收益高于 V7、真实 `1h` MDD 不差于 V7、`8 bps` 为正、`1d lag` 为正、8个block全正。
- 即使满足上述条件，也只作为未来 clean prospective 观察点，不直接改 V7。
- 若收益改善依赖大量新增交易、MDD扩大、block/lag失败或只补到噪声，裁决为 `FAIL / noise-releasing`。
