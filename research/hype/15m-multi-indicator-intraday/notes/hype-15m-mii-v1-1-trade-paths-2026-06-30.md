# HYPE-15M-MII V1.1 交易路径图 2026-06-30

Family：`HYPE-15M-Multi-Indicator-Intraday`（alias：`HYPE-15M-MII`）

`HYPE-15M-MII-V1.1` 是 `V1base` 的干净参数登记版；本图用于逐笔检查价格路径、RSI(7) 触发位置和 MACD(12,26,9) 方向过滤是否符合预期。

## 汇总

| 交易数 | 年化 | 总收益 | 最大回撤 | 胜率 | PF | 平均单笔 | 最差单笔 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `187` | `272.30%` | `309.54%` | `-21.12%` | `80.75%` | `2.158` | `0.786%` | `-7.760%` |

## HTML 图

- HTML：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_v1_1_trade_paths_2026-06-30.html`
- 内容：每笔交易的局部 15m K 线、入场/出场连线、RSI(7) 与 40/60 阈值、MACD(12,26,9) 线/signal/histogram。

## 状态

本图只用于 `V1.1` diagnostic inspection，不改变 `NO-GO` 状态。

## 产物

- 脚本：`research/hype/15m-multi-indicator-intraday/scripts/research_hype_15m_mii_v1_1_trade_path_chart.py`
- trades CSV：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_v1_1_trades_2026-06-30.csv`
- JSON：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_v1_1_trade_paths_2026-06-30.json`
