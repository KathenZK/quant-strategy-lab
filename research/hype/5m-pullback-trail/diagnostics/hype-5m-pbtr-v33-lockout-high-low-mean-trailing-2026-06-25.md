# HYPE-5M-PBTR-V3.3 过去9根 high/low 均价 trailing 回测 2026-06-25

Family id：`HYPE-5M-PBTR`

本报告测试锁仓期均价锚点：第 `10` 根 K 开始时，多头用过去 `9` 根 K 的 `high` 均价，空头用过去 `9` 根 K 的 `low` 均价作为 trailing reference。

定义：

- 多头：`reference = mean(lockout_high[9 bars])`，`stop = reference - 0.75 * ATR`。
- 空头：`reference = mean(lockout_low[9 bars])`，`stop = reference + 0.75 * ATR`。
- 如果该 stop 在 unlock open 已穿越，则按可执行口径市价退出。

## 结果对比

| 口径 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 | 解锁即市价 | stop-market | gap 市价 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `原始旧回测` | `8027` | `1331271064.12x` | `55.66%` | `4.15` | `3.31` | `-8.69%` | `0.00%` | `0.00%` | `0.00%` |
| `unlock open 重置` | `7191` | `0.00x` | `39.94%` | `0.61` | `0.91` | `-100.00%` | `0.00%` | `86.05%` | `13.95%` |
| `peak/open 均价` | `7865` | `0.00x` | `37.97%` | `0.59` | `0.97` | `-100.00%` | `49.27%` | `46.78%` | `3.95%` |
| `peak/trough/open 三均价` | `7411` | `0.00x` | `38.38%` | `0.60` | `0.96` | `-100.00%` | `16.35%` | `69.44%` | `14.21%` |
| `过去9根 high/low 均价` | `7698` | `0.00x` | `37.66%` | `0.60` | `0.99` | `-100.00%` | `42.19%` | `47.48%` | `10.33%` |

## high/low 均价时间切片

| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `recent_1w` | `139` | `-23.59%` | `0.00x` | `38.85%` | `0.93` | `0.59` | `-29.33%` |
| `recent_1m` | `598` | `-59.95%` | `0.00x` | `41.30%` | `1.01` | `0.71` | `-61.98%` |
| `recent_3m` | `1793` | `-93.65%` | `0.00x` | `37.31%` | `1.05` | `0.62` | `-93.67%` |
| `recent_6m` | `3567` | `-99.61%` | `0.00x` | `37.85%` | `1.06` | `0.65` | `-99.61%` |
| `full` | `7698` | `-100.00%` | `0.00x` | `37.66%` | `0.99` | `0.60` | `-100.00%` |

## 结论

过去 `9` 根 high/low 均价比单点 peak/trough 更平滑，但全样本 PF 只有 `0.60`，最大回撤 `-100.00%`。

该口径仍没有恢复长期正期望，不适合作为 V3.3 可交接修复。

## 产物

- 脚本：`research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_lockout_high_low_mean_trailing.py`
- JSON：`artifacts/hype_5m_pbtr_v33_lockout_high_low_mean_trailing.json`
- 汇总 CSV：`artifacts/hype_5m_pbtr_v33_lockout_high_low_mean_trailing_summary.csv`
- 交易诊断 CSV：`artifacts/hype_5m_pbtr_v33_lockout_high_low_mean_trailing_trade_diagnostics.csv`
