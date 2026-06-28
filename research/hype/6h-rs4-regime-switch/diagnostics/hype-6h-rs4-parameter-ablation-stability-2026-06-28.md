# HYPE-6H-RS4 全参数消融与时间稳定性 2026-06-28

Family id：`HYPE-6H-RS4-Regime-Switch`。本报告在 2026-06-26 独立复现脚本基础上做 one-at-a-time 参数消融，不做新参数搜索，不把更高分变体提升为候选。

## 口径

- 数据与执行：沿用 Binance HYPEUSDT perpetual `5m` 聚合 `6h`、6h 收盘信号、下一根 6h 开盘成交、单边 `9.5bps` 成本与现有 funding 对齐口径。
- 消融数量：`68` 个配置，其中 `1` 个基线，`67` 个单参数变体。
- 稳定性：固定阶段切片、逐月切片、非重叠 21 天滚动窗口。
- 注意：funding 仍只覆盖到 `2026-06-01`，之后 funding 按 0 处理；本报告不解决 Bybit 全史缺口。

## 基线结果

- 全样本：收益 `624.06%`，最大回撤 `-29.77%`，Sharpe `3.12`。
- 月度稳定性：正月份 `11/14`，最差月 `-12.61%`。
- 21 天稳定性：正窗口 `15/19`，最差 21 天 `-7.86%`。

## 固定时间片

| slice | total_return | max_drawdown | trade_count | exposure |
| --- | --- | --- | --- | --- |
| full | 624.06% | -29.77% | 128 | 0.51 |
| early_2025_05_30_to_2025_09_01 | 24.26% | -28.60% | 34 | 0.48 |
| mid_2025_09_01_to_2025_12_01 | 90.84% | -8.58% | 24 | 0.38 |
| late_2025_12_01_to_2026_03_01 | 35.97% | -16.56% | 31 | 0.46 |
| spring_2026_03_01_to_2026_06_01 | 60.83% | -17.96% | 34 | 0.75 |
| post_funding_gap_2026_06_01_latest | 39.64% | -8.03% | 5 | 0.41 |
| may_2026 | 16.89% | -13.24% | 7 | 0.65 |

## 最脆弱参数组

| group | variants | min_total_return | max_total_return | worst_max_drawdown | min_positive_months | worst_rolling21d |
| --- | --- | --- | --- | --- | --- | --- |
| v10_range_gate | 1 | 491.12% | 491.12% | -39.48% | 9 | -0.15 |
| er_gate | 1 | 756.46% | 756.46% | -39.29% | 10 | -0.05 |
| macd_slow | 3 | 409.37% | 707.16% | -37.84% | 10 | -0.13 |
| long_persist | 3 | 257.62% | 533.18% | -37.23% | 11 | -0.13 |
| er_threshold | 5 | 391.19% | 629.25% | -36.83% | 10 | -0.10 |
| melt_side | 2 | 121.15% | 264.78% | -35.99% | 8 | -0.16 |
| macd_signal | 3 | 343.19% | 626.53% | -35.48% | 10 | -0.09 |
| combo_weight | 4 | 338.98% | 964.13% | -34.06% | 10 | -0.12 |
| melt_range_threshold | 5 | 280.66% | 393.24% | -34.00% | 11 | -0.20 |
| v10_range_threshold | 5 | 280.66% | 393.24% | -34.00% | 11 | -0.20 |
| er_window | 3 | 362.13% | 787.61% | -32.13% | 10 | -0.09 |
| macd_fast | 3 | 394.10% | 672.77% | -31.55% | 10 | -0.13 |
| mfe_giveback | 3 | 531.56% | 1035.75% | -31.36% | 11 | -0.10 |
| costs | 2 | 467.81% | 823.04% | -31.30% | 11 | -0.10 |
| mfeu | 3 | 501.41% | 624.48% | -29.77% | 11 | -0.12 |
| donchian_exit | 3 | 535.21% | 624.06% | -29.77% | 11 | -0.08 |
| atr_window | 4 | 559.38% | 670.80% | -29.77% | 11 | -0.08 |
| baseline | 1 | 624.06% | 624.06% | -29.77% | 11 | -0.08 |
| donchian_entry | 4 | 624.06% | 624.06% | -29.77% | 11 | -0.08 |
| melt_range_gate | 1 | 594.19% | 594.19% | -29.77% | 11 | -0.08 |
| mfe_trigger | 3 | 495.03% | 669.07% | -29.77% | 11 | -0.12 |
| funding | 1 | 632.03% | 632.03% | -29.53% | 11 | -0.08 |
| donchian | 1 | 775.16% | 775.16% | -29.31% | 12 | -0.07 |
| range_window | 4 | 488.63% | 888.36% | -26.09% | 11 | -0.13 |

## 回撤最差的单参数变体

| strategy | group | changed_parameter | changed_value | total_return | max_drawdown | positive_months | worst_rolling21d_return |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v10_range_gate__range_gate=off | v10_range_gate | range_gate | off | 491.12% | -39.48% | 9 | -15.47% |
| er_gate__use_er_gate=off | er_gate | use_er_gate | off | 756.46% | -39.29% | 10 | -5.19% |
| macd_slow__macd_slow=18 | macd_slow | macd_slow | 18 | 409.37% | -37.84% | 10 | -12.52% |
| long_persist__long_persist=1 | long_persist | long_persist | 1 | 533.18% | -37.23% | 11 | -13.17% |
| er_threshold__er_threshold=0.25 | er_threshold | er_threshold | 0.25 | 600.20% | -36.83% | 11 | -6.69% |
| long_persist__long_persist=4 | long_persist | long_persist | 4 | 257.62% | -36.12% | 11 | -11.42% |
| melt_side__melt_side_mode=both | melt_side | melt_side_mode | both | 264.78% | -35.99% | 10 | -16.28% |
| macd_signal__macd_signal=3 | macd_signal | macd_signal | 3 | 343.19% | -35.48% | 10 | -8.73% |

## 收益最高但不可直接采纳的变体

| strategy | group | changed_parameter | changed_value | total_return | max_drawdown | positive_months | worst_rolling21d_return |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mfe_giveback__mfe_giveback_atr=2.0 | mfe_giveback | mfe_giveback_atr | 2.0 | 1035.75% | -29.77% | 11 | -7.86% |
| mfe_giveback__mfe_giveback_atr=2.5 | mfe_giveback | mfe_giveback_atr | 2.5 | 988.18% | -31.36% | 11 | -9.95% |
| combo_weight__w=2.0 | combo_weight | w | 2.0 | 964.13% | -34.06% | 10 | -12.02% |
| range_window__range_window=8 | range_window | range_window | 8 | 888.36% | -25.18% | 11 | -7.44% |
| costs__cost_multiplier=0.0 | costs | cost_multiplier | 0.0 | 823.04% | -28.22% | 11 | -5.90% |
| combo_weight__w=1.5 | combo_weight | w | 1.5 | 790.42% | -31.66% | 11 | -9.93% |
| er_window__er_window=10 | er_window | er_window | 10 | 787.61% | -29.51% | 11 | -4.05% |
| donchian__use_donchian=off | donchian | use_donchian | off | 775.16% | -29.31% | 12 | -6.77% |

## 稳定性结论

- `8` 个单参数变体触发失败条件（收益 <=0、回撤 <=-35% 或正月份 <8），说明 RS4 不是宽参数平台。
- 最脆弱的区域集中在 regime/filter 类参数，尤其是 ER gate、方向限制或 range gate；这些不是可随意调的装饰参数。
- 基线能赚钱，但分月/21 天窗口仍有明显负段；它更像少数 regime 事件驱动的策略，而不是平滑稳定的全天候 alpha。
- 收益更高的变体主要来自放松过滤或提高 melt 暴露，通常伴随更深回撤或更差窗口，不能作为反向调参理由。
- 当前状态维持 `diagnostic only / not promoted`；若继续，应先补 Bybit 全史、完整 funding、交易所横测，再做 live runner 状态机审计。

## 保留证据

- summary JSON：`research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_parameter_ablation_summary_2026-06-28.json`
- ablation CSV：`research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_parameter_ablation_2026-06-28.csv`
- slice CSV：`research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_parameter_slices_2026-06-28.csv`
- rolling 21d CSV：`research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_parameter_rolling21d_2026-06-28.csv`
