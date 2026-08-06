# Artifacts

本目录保留 `HYPE-1D-MA7-Asymmetric-Body-Trend` 初始规则与多空分离搜索的机器证据。

## 多空分离搜索

- [机器摘要](hype_1d_ma7_separated_summary_2026-08-04.json)：搜索合同、候选、基准、压力、切片、相位、邻域、消融与 bootstrap。
- [完整交易路径交互图](hype_1d_ma7_separated_trade_path_2026-08-04.html)：日 K、MA7、逐笔入场/出场连线、权益曲线与交易表。
- [单边候选前沿](hype_1d_ma7_separated_frontier_2026-08-04.csv)与[组合候选前沿](hype_1d_ma7_separated_pairs_2026-08-04.csv)。
- [主候选交易](hype_1d_ma7_separated_primary_trades_2026-08-04.csv)与[完整权益路径](hype_1d_ma7_separated_primary_path_2026-08-04.csv)。
- [近期切片](hype_1d_ma7_separated_primary_recent_2026-08-04.csv)与[90 日滚动窗口](hype_1d_ma7_separated_primary_rolling_90d_2026-08-04.csv)。
- [多空消融](hype_1d_ma7_separated_primary_components_2026-08-04.csv)。
- [参数邻域](hype_1d_ma7_separated_primary_neighborhood_2026-08-04.csv)。
- [日界相位](hype_1d_ma7_separated_primary_phase_2026-08-04.csv)。

## V1 EMA7 替换

- [机器摘要](hype_1d_v1_ema7_substitution_summary_2026-08-05.json)与[指标表](hype_1d_v1_ema7_substitution_metrics_2026-08-05.csv)。
- [近期切片](hype_1d_v1_ema7_substitution_recent_2026-08-05.csv)、[日界相位](hype_1d_v1_ema7_substitution_phase_2026-08-05.csv)与[90 日滚动窗口](hype_1d_v1_ema7_substitution_rolling_90d_2026-08-05.csv)。
- [EMA7 交易](hype_1d_v1_ema7_substitution_trades_2026-08-05.csv)与[EMA7 组合路径](hype_1d_v1_ema7_substitution_path_2026-08-05.csv)。

## V1 3x 杠杆

- [机器摘要](hype_1d_v1_3x_leverage_summary_2026-08-05.json)与[指标表](hype_1d_v1_3x_leverage_metrics_2026-08-05.csv)。
- [近期切片](hype_1d_v1_3x_leverage_recent_2026-08-05.csv)、[日界相位](hype_1d_v1_3x_leverage_phase_2026-08-05.csv)与[90 日滚动窗口](hype_1d_v1_3x_leverage_rolling_90d_2026-08-05.csv)。
- [3x 交易](hype_1d_v1_3x_leverage_trades_2026-08-05.csv)与[3x 组合路径](hype_1d_v1_3x_leverage_path_2026-08-05.csv)。

## 初始规则

- [机器摘要](hype_1d_ma7_abt_summary_2026-08-04.json)：合同、数据质量、基准、全期指标与交易 bootstrap。
- [全期指标](hype_1d_ma7_abt_metrics_2026-08-04.csv)：三种空头退出解释及 long-only / short-only 消融。
- [近期切片](hype_1d_ma7_abt_recent_slices_2026-08-04.csv)：沿完整权益路径、锚定数据终点的 `1d/7d/1m/3m/6m/1y`，不重置仓位。
- [时间切分](hype_1d_ma7_abt_chronological_2026-08-04.csv)：flat-start prefit、researcher-exposed 最后 90 日与全期。
- [90 日滚动窗口](hype_1d_ma7_abt_rolling_90d_2026-08-04.csv)。
- [MA 邻域](hype_1d_ma7_abt_ma_neighborhood_2026-08-04.csv)：`SMA5–SMA10` 稳健性诊断。
- [执行压力](hype_1d_ma7_abt_execution_stress_2026-08-04.csv)：`8 bps`、额外延迟与零 funding 控制。
- [日界相位](hype_1d_ma7_abt_phase_audit_2026-08-04.csv)：UTC 与 `12:00 UTC` 日界。
- [字面版交易](hype_1d_ma7_abt_literal_trades_2026-08-04.csv)与[字面版权益路径](hype_1d_ma7_abt_literal_path_2026-08-04.csv)。

这些文件是已揭示历史上的 diagnostic evidence，不是 prospective OOS 或 promotion 许可。
