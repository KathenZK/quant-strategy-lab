# HYPE-D15-HTO-V1 全参数与组件消融

- 生成时间：`2026-07-29T03:12:35.229539+00:00`
- 数据：只使用 locked OOS 之前的 frozen prefit；本报告未读取 OOS 绩效。
- 成本：每次成交手续费 `0.001`，不利滑点 `4 bps/fill`，计实际资金费。
- 时序：前一完整 UTC 日状态、`15m` 闭合信号、下一根开盘成交、stop-first。

## V1 基线

`annual_factor=1.4878x`，`return=43.75%`，`win_rate=62.07%`，`MDD=18.85%`，`trades=58`。

## 结论

逐槽位替换共 `34` 项，组件关闭共 `10` 项。成交路径完全不变的 dormant 槽位为：`daily_atr_window, daily_supertrend_mult, daily_vote_min, rsi_window, rsi_trigger, rsi_reclaim, pullback_atr, expansion_min, max_hold_bars`。

组件移除结果：

| 组件 | 年化倍数 | 收益 | 胜率 | MDD | 交易数 | 路径相同 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `daily_ema` | 1.000x | 0.00% | 0.00% | -0.00% | 0 | 否 |
| `daily_momentum` | 1.000x | 0.00% | 0.00% | -0.00% | 0 | 否 |
| `daily_dmi` | 1.000x | 0.00% | 0.00% | -0.00% | 0 | 否 |
| `daily_breakout` | 1.000x | 0.00% | 0.00% | -0.00% | 0 | 否 |
| `daily_supertrend` | 1.488x | 43.75% | 62.07% | 18.85% | 58 | 是 |
| `daily_adx_filter` | 1.488x | 43.75% | 62.07% | 18.85% | 58 | 是 |
| `primary_entry` | 1.000x | 0.00% | 0.00% | -0.00% | 0 | 否 |
| `micro_trend` | 1.413x | 37.17% | 62.50% | 24.54% | 72 | 否 |
| `micro_adx_filter` | 1.066x | 6.06% | 59.02% | 33.33% | 61 | 否 |
| `rvol_filter` | 1.039x | 3.58% | 56.45% | 26.52% | 62 | 否 |

V1 的 prefit 年化倍数未达到 `10x`，因此消融只用于识别有效机制与精简参数面，
不构成 promotion 证据。只有 path-equal/dormant 槽位可从 V2 接口删除；
对收益有负贡献但改变成交路径的组件不能仅凭单次消融静默删除，需在 clean 面重新搜索。

## 证据

- [逐项 CSV](../artifacts/hype_d15_hto_v1_ablation_2026-07-29.csv)
- [机器摘要 JSON](../artifacts/hype_d15_hto_v1_ablation_2026-07-29.json)
- [V1 冻结配置](../artifacts/hype_d15_hto_v1_search_2026-07-29.json)
