# HYPE 5m MA Pullback Scalp executable search 2026-06-26

Family id: `HYPE-5M-MA-Pullback-Scalp`

目标：把“两条均线剥头皮”拆成可执行规则：慢 EMA 判断趋势，快 EMA 判断价格波浪/回调，HH/HL 或 LL/LH 判断结构，回调结束后下一根 open 入场，入场即挂固定 TP/SL，并在固定 K 数内超时退出。

## 数据质量

- Normalized OHLCV: `393` 个日分区，`112822` 根 K。
- Raw OHLCV: `393` 个日分区，`112822` 根 K。
- 时间范围：`2025-05-30 10:30:00+00:00` 到 `2026-06-26 04:15:00+00:00`。
- 连续性：expected `112822`，missing `0`，duplicate `0`。
- `is_closed`：`{'True': 112822}`。
- `source`：`{'binance_futures_kline_api': 101956, 'ccxt': 8423, 'binance_futures_api': 2443}`。
- OHLC/VWAP/volume hard violations：`{'high_lt_max_open_close': 0, 'low_gt_min_open_close': 0, 'nonpositive_ohlc': 0, 'negative_volume': 0, 'negative_quote_volume': 0, 'negative_trade_count': 0, 'vwap_outside_hilo_nonzero_vol': 0}`。
- Raw/normalized alignment：`{'rows': 112822, 'left_only': 0, 'right_only': 0, 'mismatch_counts': {'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0, 'quote_volume': 0, 'trade_count': 0, 'vwap': 0}, 'max_abs_diff': {'open': 0.0, 'high': 0.0, 'low': 0.0, 'close': 0.0, 'volume': 0.0, 'quote_volume': 0.0, 'trade_count': 0.0, 'vwap': 0.0}}`。

## 执行模型

- 信号只使用已收盘 `5m` K；下一根 K 的 open 入场。
- 入场后立即有固定 TP/SL bracket；保护止损从第一根持仓 K 开始有效。
- 同一根 K 同时可能触及 TP/SL 时，保守按止损先成交。
- stop/target 被 open 穿越时按 open 市价成交，不按旧 stop/target 价成交。
- 超时退出使用下一根 open，不使用不可保证的 bar close。
- 成本：fee `4.15 bps/fill`，entry slippage `10.73 bps`，exit slippage `-2.64 bps`。

## 搜索规模

- curated + random configs: `6740`。
- random seed: `20260626`。
- 搜索维度：trigger style、fast/slow EMA、结构窗口、平台窗口、结构突破幅度、均线斜率、回调触碰/收回阈值、ATR/RVOL/ADX/离慢线距离过滤、TP/SL、max-hold、cooldown、long/short/both。

## 候选门槛

- paper candidate gate: trades >= `60`，full return > `0`，ann > `1x`，win >= `52%`，PF >= `1.15`，maxDD >= `-20%`，VAL/FWD PF >= `1`，VAL/FWD/recent returns 不得明显失血。
- 通过 paper candidate gate：`2`。

通过 paper candidate gate 的配置如下；它们仍然只能进入 paper audit，不能直接实盘。
| name | trigger | side | fast/slow | TP/SL/hold | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE_5M_MA_PBS_R03072` | `reclaim` | `both` | `21/144` | `180/160/45` | `0.35` | `138` | `1.13x` | `52.90%` | `1.158` | `10.89 bps` | `-12.64%` | `1.134` | `1.768` | `0.90%` |
| `HYPE_5M_MA_PBS_R00199` | `engulf_reclaim` | `both` | `89/610` | `180/160/30` | `0.15` | `60` | `1.07x` | `58.33%` | `1.290` | `12.04 bps` | `-6.36%` | `inf` | `1.091` | `2.68%` |

## 最接近目标的配置

| name | trigger | side | fast/slow | TP/SL/hold | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE_5M_MA_PBS_R03072` | `reclaim` | `both` | `21/144` | `180/160/45` | `0.35` | `138` | `1.13x` | `52.90%` | `1.158` | `10.89 bps` | `-12.64%` | `1.134` | `1.768` | `0.90%` |
| `HYPE_5M_MA_PBS_R00199` | `engulf_reclaim` | `both` | `89/610` | `180/160/30` | `0.15` | `60` | `1.07x` | `58.33%` | `1.290` | `12.04 bps` | `-6.36%` | `inf` | `1.091` | `2.68%` |

## 样本数足够时胜率最高的配置

| name | trigger | side | fast/slow | TP/SL/hold | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE_5M_MA_PBS_R00332` | `reclaim` | `short` | `21/144` | `60/220/45` | `0.19` | `76` | `0.90x` | `75.00%` | `0.750` | `-13.62 bps` | `-14.50%` | `0.530` | `0.872` | `0.86%` |
| `HYPE_5M_MA_PBS_R01221` | `reclaim` | `both` | `21/144` | `60/220/45` | `0.37` | `143` | `0.87x` | `74.83%` | `0.803` | `-9.99 bps` | `-20.24%` | `0.608` | `0.843` | `3.74%` |
| `HYPE_5M_MA_PBS_R02531` | `reclaim` | `both` | `34/233` | `50/220/15` | `0.32` | `127` | `0.86x` | `72.44%` | `0.721` | `-11.96 bps` | `-20.32%` | `0.571` | `1.426` | `4.12%` |
| `HYPE_5M_MA_PBS_R00645` | `platform_break` | `both` | `5/34` | `60/220/30` | `0.34` | `132` | `0.79x` | `71.97%` | `0.676` | `-18.58 bps` | `-25.63%` | `0.485` | `0.773` | `-4.63%` |
| `HYPE_5M_MA_PBS_R00675` | `engulf_reclaim` | `both` | `21/144` | `50/220/45` | `0.92` | `361` | `0.60x` | `71.19%` | `0.678` | `-14.63 bps` | `-42.11%` | `0.613` | `0.859` | `-3.69%` |
| `HYPE_5M_MA_PBS_R02303` | `engulf_reclaim` | `long` | `8/55` | `50/160/20` | `0.41` | `161` | `0.81x` | `70.19%` | `0.690` | `-13.71 bps` | `-24.55%` | `0.862` | `0.518` | `-10.33%` |
| `HYPE_5M_MA_PBS_R03411` | `reclaim` | `both` | `34/233` | `50/220/45` | `0.40` | `157` | `0.79x` | `69.43%` | `0.664` | `-15.41 bps` | `-23.77%` | `0.553` | `0.651` | `-1.18%` |
| `HYPE_5M_MA_PBS_R02431` | `reclaim` | `short` | `21/144` | `60/220/30` | `0.97` | `380` | `0.80x` | `68.42%` | `0.859` | `-5.98 bps` | `-31.57%` | `0.663` | `1.137` | `8.46%` |
| `HYPE_5M_MA_PBS_R00163` | `reclaim` | `long` | `13/89` | `50/220/5` | `0.25` | `98` | `1.00x` | `68.37%` | `1.003` | `0.09 bps` | `-6.48%` | `1.095` | `1.599` | `2.95%` |
| `HYPE_5M_MA_PBS_R03238` | `reclaim` | `short` | `13/89` | `60/220/30` | `0.88` | `345` | `0.60x` | `67.83%` | `0.705` | `-15.25 bps` | `-45.33%` | `0.572` | `1.231` | `1.97%` |

## 频率压力测试

| 最低 trades/day | 配置数 | 最高全样本年化 | 最高 PF |
| ---: | ---: | ---: | ---: |
| `1.0` | `3177` | `0.80x` | `0.960` |
| `2.0` | `1914` | `0.39x` | `0.851` |
| `3.0` | `1154` | `0.20x` | `0.805` |
| `5.0` | `449` | `0.06x` | `0.722` |
| `8.0` | `132` | `0.01x` | `0.710` |

## 月度提示

- top score `HYPE_5M_MA_PBS_R03072` 的负收益月份数：`4`。
- 最差月份 `2025_11`：return `-4.25%`，PF `0.686`，trades `14`。

## 结论

本轮找到可进入 paper audit 的盈利配置，但还不能真实资金上线；下一步必须做参数邻域、逐笔路径图、paper runner 和重启/订单维护审计。

## 产物

- 脚本：`research/hype/5m-ma-pullback-scalp/scripts/research_hype_5m_ma_pullback_scalp.py`
- JSON：`research/hype/5m-ma-pullback-scalp/artifacts/hype_5m_ma_pullback_scalp_search_2026-06-26.json`
- Summary CSV：`research/hype/5m-ma-pullback-scalp/artifacts/hype_5m_ma_pullback_scalp_search_summary_2026-06-26.csv`
- Slices CSV：`research/hype/5m-ma-pullback-scalp/artifacts/hype_5m_ma_pullback_scalp_search_slices_2026-06-26.csv`
- Monthly CSV：`research/hype/5m-ma-pullback-scalp/artifacts/hype_5m_ma_pullback_scalp_search_monthly_2026-06-26.csv`
- Top trades CSV：`research/hype/5m-ma-pullback-scalp/artifacts/hype_5m_ma_pullback_scalp_search_top_trades_2026-06-26.csv`
