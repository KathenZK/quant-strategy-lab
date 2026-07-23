# HYPE-1H-MMTF V1 全组件消融 — 2026-07-22

## 结论

本轮在 locked OOS 之外覆盖 V1 的主入场、过滤、方向、退出、风控、风险预算与可能 dormant 槽，共 `18` 行。V1 中有 5 个直接 probe 与 baseline 逐笔完全等价，加上固定的机制/方向/trend-exit 状态，共删除 8 个槽并形成 V2 clean-equivalent。

## 逐笔等价删除项

- `adx_min=10`：移除 ADX filter 后逐笔等价，说明 V1 信号处 ADX 全部自然高于阈值。
- `breakeven_trigger_atr=1.5`：移除后逐笔等价；现有 trailing 已先行决定 stop。
- `max_hold_bars=168`：移除 timeout 后逐笔等价；全部仓位先由 stop/TP 退出。
- `breakout_atr`：time-series momentum 机制不读取该字段。
- `exit_window`：`trend_exit=false` 时不读取该字段。
- 机制固定为 time-series momentum、方向固定 both、trend-exit 固定关闭，不保留为 clean tune 旋钮。

V1 与 V2 逐笔 signature 均为 `f70a8ea2f64dfa9dd919383a761f1f6367f8fa5d0ce156d6eb95d8aef7a5224b`。

## 有效组件

- 移除主入场：`0` 笔，证明主信号接线有效。
- 移除 EMA regime：prefit 降至 `2.8425x / 31.46% MDD / 74.07% / 81`。
- 移除 RVOL：降至 `1.9065x / 29.50% / 72.00% / 75`。
- 移除 TP：降至 `1.4802x / 33.07% / 41.07% / 56`。
- 移除 hard stop：MDD 升至 `45.13%`，且不满足可执行保护合同。
- 移除 trailing：降至 `2.4828x / 35.16% / 84.48% / 58`。
- 移除 cooldown：降至 `1.1113x / 42.42% / 69.66% / 89`。
- 多头/空头拆分均有正贡献；风险预算改变收益与回撤，不是无效参数。

机器证据：[CSV](../artifacts/hype_1h_mmtf_v1_ablation_2026-07-22.csv) · [JSON](../artifacts/hype_1h_mmtf_v1_ablation_2026-07-22.json)
