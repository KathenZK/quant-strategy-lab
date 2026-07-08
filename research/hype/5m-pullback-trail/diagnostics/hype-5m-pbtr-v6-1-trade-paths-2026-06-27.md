# HYPE-5M-PBTR-V6.1 交易路径图 2026-06-27

Family id：`HYPE-5M-PBTR`

`HYPE-5M-PBTR-V6.1` 定义为 V6 的 sizing/exit 变体：`tp_atr=2.5`，`sl_atr=7`，`time_exit_bars=36`，不使用 trailing，固定 `3x` 仓位。该版本仍是 audit candidate，不是生产 sizing 版本。

## 结果

| 交易数 | 总收益 | 胜率 | PF | payoff | 最大回撤 | 单笔最差 | 单笔最好 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `157` | `408.95%` | `63.69%` | `1.773` | `1.011` | `-25.63%` | `-14.81%` | `9.23%` |

## 交易路径图

- HTML：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_trade_paths_2026-06-27.html`
- HTML 内含每笔交易的局部 5m K 线、EMA21/EMA55、入场点、出场点和入场-出场连线。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_1_trade_paths.py`
- trades CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_trades_2026-06-27.csv`
- summary CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_summary_2026-06-27.csv`
- JSON：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_2026-06-27.json`
