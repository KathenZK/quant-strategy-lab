# HYPE-5M-PBTR-V3.3 peak/open 均价 trailing 回测 2026-06-25

Family id：`HYPE-5M-PBTR`

本报告测试一个折中解锁锚点：第 `10` 根 K 开始时，不直接用锁仓期 peak/trough，也不完全用 unlock open，而是使用二者均价作为 trailing 锚点。

定义：

- 多头：`reference = (lockout_peak + unlock_open) / 2`，`stop = reference - 0.75 * ATR`。
- 空头：`reference = (lockout_trough + unlock_open) / 2`，`stop = reference + 0.75 * ATR`。
- 如果该 stop 在 unlock open 仍已穿越，则按可执行口径市价退出。

## 结果对比

| 口径 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 | 解锁即市价 | stop-market | gap 市价 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `原始旧回测` | `8027` | `1331271064.12x` | `55.66%` | `4.15` | `3.31` | `-8.69%` | `0.00%` | `0.00%` | `0.00%` |
| `unlock open 重置` | `7191` | `0.00x` | `39.94%` | `0.61` | `0.91` | `-100.00%` | `0.00%` | `86.05%` | `13.95%` |
| `peak/open 均价` | `7865` | `0.00x` | `37.97%` | `0.59` | `0.97` | `-100.00%` | `49.27%` | `46.78%` | `3.95%` |

## peak/open 均价时间切片

| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `recent_1w` | `139` | `-19.41%` | `0.00x` | `41.01%` | `0.96` | `0.67` | `-25.46%` |
| `recent_1m` | `607` | `-55.60%` | `0.00x` | `42.83%` | `0.99` | `0.74` | `-57.13%` |
| `recent_3m` | `1834` | `-93.07%` | `0.00x` | `37.90%` | `1.04` | `0.64` | `-93.10%` |
| `recent_6m` | `3651` | `-99.68%` | `0.00x` | `37.99%` | `1.04` | `0.64` | `-99.68%` |
| `full` | `7865` | `-100.00%` | `0.00x` | `37.97%` | `0.97` | `0.59` | `-100.00%` |

## 结论

`peak/open` 均价锚点比纯 `unlock_open` 更保留锁仓期浮盈信息，但仍没有恢复旧 V3.3 优势：全样本 PF `0.59`，最大回撤 `-100.00%`。

因此，均价锚点可以作为机制探索记录，但不是可交接的 V3.3 修复版本。

## 产物

- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v33_blend_peak_open_trailing.py`
- JSON：`reports/hype_5m_pbtr_v33_blend_peak_open_trailing.json`
- 汇总 CSV：`reports/hype_5m_pbtr_v33_blend_peak_open_trailing_summary.csv`
- 交易诊断 CSV：`reports/hype_5m_pbtr_v33_blend_peak_open_trailing_trade_diagnostics.csv`
