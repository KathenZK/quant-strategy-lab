# HYPE 5m executable broad search 2026-06-25

Family id：`HYPE-5M-PBTR`

目标：按实盘可执行口径重新搜索 Binance HYPE `5m` 策略，硬条件为年化 `>=20x`、胜率 `>=50%`、最大回撤优于 `-20%`。

执行口径：

- 所有信号只使用已收盘 K 线信息，下一根 K 的 open 入场。
- 入场即有固定 TP/SL bracket；保护止损从入场第一根 K 起生效。
- 可选 trailing stop 只在每根 K 结束后用已知 high/low/ATR 更新到下一根。
- 同一根 K 同时触及 TP/SL 时按保守口径优先止损。
- stop 被 open 跳空穿越时按 open 市价退出，不按旧 stop 价成交。
- 成本使用实盘统计：手续费 `4.1466 bps/fill`、开仓滑点 `10.73 bps`、平仓滑点 `2.64 bps`。

搜索规模：curated + random，共 `13134` 个配置。

## 硬条件结果

没有找到全样本同时满足年化、胜率、回撤三项硬条件的配置。

## 审计条件结果

没有配置通过附加审计条件：近期窗口不亏、VAL/FWD PF 均不低于 `1`、且有最低交易数。

## 年化分布审计

| 最低交易数 | 配置数 | 最高年化 | 是否存在年化>=20x |
| ---: | ---: | ---: | --- |
| `1` | `10474` | `1.18x` | 否 |
| `5` | `9119` | `1.18x` | 否 |
| `10` | `8415` | `1.18x` | 否 |
| `20` | `7554` | `1.18x` | 否 |
| `50` | `6247` | `1.10x` | 否 |
| `100` | `5127` | `1.05x` | 否 |

## 交易数>=100 的最接近配置

| name | style | side | trades | ann | win | PF | payoff | maxDD | VAL PF | FWD PF | recent1m ann |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE_5M_EXEC_R06509` | `momentum` | `long` | `194` | `1.05x` | `53.09%` | `1.057` | `0.934` | `-20.21%` | `1.379` | `1.958` | `1.99x` |
| `HYPE_5M_EXEC_R11382` | `momentum` | `both` | `110` | `1.04x` | `74.55%` | `1.112` | `0.380` | `-10.02%` | `0.602` | `1.909` | `0.81x` |
| `HYPE_5M_EXEC_R11449` | `trend_rsi_rebound` | `both` | `225` | `1.02x` | `76.44%` | `1.043` | `0.321` | `-11.20%` | `0.548` | `3.128` | `0.95x` |
| `HYPE_5M_EXEC_R08415` | `bb_reversion` | `both` | `129` | `0.98x` | `62.79%` | `0.961` | `0.569` | `-6.82%` | `0.858` | `1.291` | `0.84x` |
| `HYPE_5M_EXEC_R10646` | `breakout` | `short` | `101` | `0.97x` | `70.30%` | `0.852` | `0.360` | `-6.63%` | `0.617` | `0.632` | `0.82x` |

## 结论

本轮没有找到符合用户四项要求的可实盘候选。更重要的是，搜索结果不是“差一点到 20x”：在所有 `13134` 个可执行配置中，即使允许低到 `1` 笔交易，最高年化也只有 `1.18x`；在 `>=100` 笔交易的较可审计样本里，最高年化只有 `1.05x`。

## 产物

- 脚本：`research/hype/families/5m-pullback-trail/scripts/research_hype_5m_executable_broad_search.py`
- JSON：`artifacts/hype_5m_executable_broad_search.json`
- 汇总 CSV：`artifacts/hype_5m_executable_broad_search_summary.csv`
- 切片 CSV：`artifacts/hype_5m_executable_broad_search_slices.csv`
- 月度 CSV：`artifacts/hype_5m_executable_broad_search_monthly.csv`
