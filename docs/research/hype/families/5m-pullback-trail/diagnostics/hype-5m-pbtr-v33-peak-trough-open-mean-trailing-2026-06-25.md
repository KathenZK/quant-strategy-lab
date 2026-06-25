# HYPE-5M-PBTR-V3.3 peak/trough/open 三均价 trailing 回测 2026-06-25

Family id：`HYPE-5M-PBTR`

本报告测试三价均值锚点：第 `10` 根 K 开始时，用锁仓期 `peak`、锁仓期 `trough`、`unlock_open` 的均值作为 trailing reference。

定义：

- `reference = (lockout_peak + lockout_trough + unlock_open) / 3`。
- 多头：`stop = reference - 0.75 * ATR`。
- 空头：`stop = reference + 0.75 * ATR`。
- 如果该 stop 在 unlock open 已穿越，则按可执行口径市价退出。

## 结果对比

| 口径 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 | 解锁即市价 | stop-market | gap 市价 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `原始旧回测` | `8027` | `1331271064.12x` | `55.66%` | `4.15` | `3.31` | `-8.69%` | `0.00%` | `0.00%` | `0.00%` |
| `unlock open 重置` | `7191` | `0.00x` | `39.94%` | `0.61` | `0.91` | `-100.00%` | `0.00%` | `86.05%` | `13.95%` |
| `peak/open 均价` | `7865` | `0.00x` | `37.97%` | `0.59` | `0.97` | `-100.00%` | `49.27%` | `46.78%` | `3.95%` |
| `peak/trough/open 三均价` | `7411` | `0.00x` | `38.38%` | `0.60` | `0.96` | `-100.00%` | `16.35%` | `69.44%` | `14.21%` |

## 三均价时间切片

| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `recent_1w` | `130` | `-25.82%` | `0.00x` | `36.15%` | `0.98` | `0.56` | `-31.61%` |
| `recent_1m` | `572` | `-60.01%` | `0.00x` | `41.78%` | `0.98` | `0.70` | `-62.59%` |
| `recent_3m` | `1717` | `-92.95%` | `0.00x` | `38.61%` | `1.00` | `0.63` | `-92.99%` |
| `recent_6m` | `3426` | `-99.64%` | `0.00x` | `38.15%` | `1.04` | `0.64` | `-99.64%` |
| `full` | `7411` | `-100.00%` | `0.00x` | `38.38%` | `0.96` | `0.60` | `-100.00%` |

## 结论

`peak/trough/open` 三均价把 reference 拉回锁仓区间中部，解锁穿越率相对 `peak/open` 均价下降，但全样本 PF 只有 `0.60`，最大回撤 `-100.00%`。

它解决了一部分穿越频率问题，但没有恢复长期正期望，不适合作为 V3.3 可交接修复。

## 产物

- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v33_peak_trough_open_mean_trailing.py`
- JSON：`reports/hype_5m_pbtr_v33_peak_trough_open_mean_trailing.json`
- 汇总 CSV：`reports/hype_5m_pbtr_v33_peak_trough_open_mean_trailing_summary.csv`
- 交易诊断 CSV：`reports/hype_5m_pbtr_v33_peak_trough_open_mean_trailing_trade_diagnostics.csv`
