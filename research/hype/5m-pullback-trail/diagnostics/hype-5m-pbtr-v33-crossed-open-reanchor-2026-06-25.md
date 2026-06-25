# HYPE-5M-PBTR-V3.3 crossed-open 重锚回测 2026-06-25

Family id：`HYPE-5M-PBTR`

本报告测试一个条件修复：V3.3 解锁时先按原 live-realistic 口径计算 `active_stop`；若发现该 stop 已被当前 K 开盘价穿越，不立刻市价平仓，而是用当前 K 开盘价重新锚定一个可挂 stop，再继续运行 trailing。

测试两种重锚距离：

- `open_stop_0p5atr`：`new_stop = unlock_open ± 0.5 ATR`，等同用 V3.3 `stop_atr` 距离重算。
- `open_stop_0p75atr`：`new_stop = unlock_open ± 0.75 ATR`，等同用 V3.3 `trail_atr` 距离重算。

## 结果对比

| 口径 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 | 解锁重锚比例 | stop-market | gap 市价 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `原始旧回测` | `8027` | `1331271064.12x` | `55.66%` | `4.15` | `3.31` | `-8.69%` | `0.00%` | `0.00%` | `0.00%` |
| `严格 live-realistic` | `8024` | `0.00x` | `38.43%` | `0.58` | `0.94` | `-100.00%` | `0.00%` | `22.74%` | `1.91%` |
| `crossed open / 0.5 ATR` | `7588` | `0.00x` | `39.34%` | `0.59` | `0.91` | `-100.00%` | `75.14%` | `59.07%` | `40.93%` |
| `crossed open / 0.75 ATR` | `7556` | `0.00x` | `39.21%` | `0.59` | `0.91` | `-100.00%` | `75.25%` | `46.88%` | `53.12%` |

## crossed_open_0p75atr 时间切片

| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `recent_1w` | `133` | `-27.85%` | `0.00x` | `34.59%` | `0.98` | `0.52` | `-32.29%` |
| `recent_1m` | `580` | `-62.33%` | `0.00x` | `40.69%` | `0.99` | `0.68` | `-64.05%` |
| `recent_3m` | `1753` | `-93.88%` | `0.00x` | `38.22%` | `0.99` | `0.61` | `-93.91%` |
| `recent_6m` | `3494` | `-99.65%` | `0.00x` | `38.72%` | `1.00` | `0.63` | `-99.65%` |
| `full` | `7556` | `-100.00%` | `0.00x` | `39.21%` | `0.91` | `0.59` | `-100.00%` |

## 结论

条件重锚可以避免解锁即市价平仓，但没有恢复 V3.3 旧回测优势。较宽的 `0.75 ATR` 重锚口径全样本 PF 为 `0.59`，仍低于 `1`，最大回撤 `-100.00%`。

这说明问题不是单纯“旧 stop 穿越后用 open 重新算一根 stop”就能解决；V3.3 的原始优势仍主要来自旧口径按已穿越 stop level 成交，重锚后状态机变成可执行版本，收益结构随之坍缩。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_crossed_open_reanchor.py`
- JSON：`artifacts/hype_5m_pbtr_v33_crossed_open_reanchor.json`
- 汇总 CSV：`artifacts/hype_5m_pbtr_v33_crossed_open_reanchor_summary.csv`
- 交易诊断 CSV：`artifacts/hype_5m_pbtr_v33_crossed_open_reanchor_trade_diagnostics.csv`
