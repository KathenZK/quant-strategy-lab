# HYPE-5M-Micro-Scalp-V1.3 基线回测 2026-07-01

Family id：`HYPE-5M-Micro-Scalp`

V1.3 自 V1.2 剔除 dormant 与等效关闭参数，仅保留 `18` 个有效字段；本报告验证两者在相同成本下是否逐笔一致。

## 数据与成本

- 数据：`2025-05-30 10:30:00+00:00` 到 `2026-06-30 06:15:00+00:00`，`113998` 根 K。
- raw/normalized：`{'raw_files': 397, 'normalized_rows': 113998, 'raw_rows': 113998, 'merged_rows': 113998, 'timestamp_mismatch': 0, 'field_mismatches': {'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0, 'quote_volume': 0, 'trade_count': 0, 'vwap': 0, 'is_closed': 0}, 'max_abs_diff': {'open': 0.0, 'high': 0.0, 'low': 0.0, 'close': 0.0, 'volume': 0.0, 'quote_volume': 0.0, 'trade_count': 0.0, 'vwap': 0.0, 'is_closed': 0.0}}`。
- fee `0.001`/fill，slippage `4.0 bps`/fill。

## V1.3 基线

- trades `180`，trades/day `0.45`。
- ann `1.76x`，PF `1.934`，win `85.00%`。
- avg `34.96 bps`，maxDD `-9.96%`。

## 与 V1.2 一致性

- V1.2 ann `1.76x`，PF `1.934`，trades `180`。
- 指标逐笔等价：`是`。

## 产物

- JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_3_baseline_backtest_2026-07-01.json`
- Trades CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_3_baseline_backtest_trades_2026-07-01.csv`
- Spec：`research/hype/5m-micro-scalp/canonical-specs/hype-5m-micro-scalp-v1-3-baseline-spec.md`
