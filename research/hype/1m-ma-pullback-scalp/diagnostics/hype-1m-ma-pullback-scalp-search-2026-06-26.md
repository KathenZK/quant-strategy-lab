# HYPE 1m MA Pullback Scalp executable search 2026-06-26

Family id: `HYPE-1M-MA-Pullback-Scalp`

目标：把“两条均线剥头皮”拆成可执行规则：慢 EMA 判断趋势，快 EMA 判断价格波浪/回调，HH/HL 或 LL/LH 判断结构，回调结束后下一根 open 入场，入场即挂固定 TP/SL，并在固定 K 数内超时退出。

## 数据质量

- Normalized OHLCV: `94` 个日分区，`134184` 根 K。
- Raw OHLCV: `94` 个日分区，`134184` 根 K。
- 时间范围：`2026-03-25 00:00:00+00:00` 到 `2026-06-26 04:23:00+00:00`。
- 连续性：expected `134184`，missing `0`，duplicate `0`。
- `is_closed`：`{'True': 134184}`。
- `source`：`{'binance_vision': 132480, 'binance_futures_api': 1177, 'fapi_rest': 527}`。
- OHLC/VWAP/volume hard violations：`{'high_lt_max_open_close': 0, 'low_gt_min_open_close': 0, 'nonpositive_ohlc': 0, 'negative_volume': 0, 'negative_quote_volume': 0, 'negative_trade_count': 0, 'vwap_outside_hilo_nonzero_vol': 0}`。
- Raw/normalized alignment：`{'rows': 134184, 'left_only': 0, 'right_only': 0, 'mismatch_counts': {'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0, 'quote_volume': 0, 'trade_count': 0, 'vwap': 0}, 'max_abs_diff': {'open': 0.0, 'high': 0.0, 'low': 0.0, 'close': 0.0, 'volume': 0.0, 'quote_volume': 0.0, 'trade_count': 0.0, 'vwap': 0.0}}`。

## 执行模型

- 信号只使用已收盘 `1m` K；下一根 K 的 open 入场。
- 入场后立即有固定 TP/SL bracket；保护止损从第一根持仓 K 开始有效。
- 同一根 K 同时可能触及 TP/SL 时，保守按止损先成交。
- stop/target 被 open 穿越时按 open 市价成交，不按旧 stop/target 价成交。
- 超时退出使用下一根 open，不使用不可保证的 bar close。
- 成本：fee `5.00 bps/fill`，entry slippage `10.73 bps`，exit slippage `5.00 bps`。

## 搜索规模

- curated + random configs: `6740`。
- random seed: `20260626`。
- 搜索维度：trigger style、fast/slow EMA、结构窗口、平台窗口、结构突破幅度、均线斜率、回调触碰/收回阈值、ATR/RVOL/ADX/离慢线距离过滤、TP/SL、max-hold、cooldown、long/short/both。

## 候选门槛

- paper candidate gate: trades >= `60`，full return > `0`，ann > `1x`，win >= `52%`，PF >= `1.15`，maxDD >= `-20%`，VAL/FWD PF >= `1`，VAL/FWD/recent returns 不得明显失血。
- 通过 paper candidate gate：`0`。

没有配置通过完整 paper candidate gate。

## 最接近目标的配置

| name | trigger | side | fast/slow | TP/SL/hold | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE_1M_MA_PBS_R03037` | `platform_break` | `long` | `13/89` | `260/130/30` | `0.77` | `72` | `0.73x` | `45.83%` | `0.769` | `-10.81 bps` | `-10.30%` | `0.720` | `1.141` | `-2.62%` |
| `HYPE_1M_MA_PBS_C01859` | `platform_break` | `long` | `34/233` | `300/180/30` | `1.46` | `136` | `0.48x` | `30.88%` | `0.606` | `-13.64 bps` | `-20.14%` | `1.970` | `0.805` | `-2.21%` |
| `HYPE_1M_MA_PBS_R02736` | `platform_break` | `long` | `5/34` | `60/100/30` | `1.34` | `125` | `0.51x` | `55.20%` | `0.642` | `-13.53 bps` | `-16.52%` | `1.109` | `0.540` | `-8.25%` |
| `HYPE_1M_MA_PBS_C01710` | `platform_break` | `long` | `34/233` | `300/180/30` | `0.68` | `63` | `0.54x` | `38.10%` | `0.480` | `-24.53 bps` | `-17.80%` | `0.509` | `1.915` | `-1.68%` |
| `HYPE_1M_MA_PBS_R01712` | `engulf_reclaim` | `both` | `55/377` | `50/130/30` | `1.14` | `106` | `0.54x` | `57.55%` | `0.568` | `-14.51 bps` | `-14.76%` | `0.621` | `0.706` | `-7.89%` |
| `HYPE_1M_MA_PBS_C01512` | `reclaim` | `long` | `34/233` | `300/180/30` | `0.80` | `75` | `0.66x` | `38.67%` | `0.711` | `-13.78 bps` | `-13.56%` | `0.511` | `1.169` | `-7.63%` |
| `HYPE_1M_MA_PBS_R02740` | `platform_break` | `long` | `55/377` | `140/100/15` | `0.82` | `76` | `0.66x` | `34.21%` | `0.495` | `-13.74 bps` | `-11.07%` | `1.560` | `0.473` | `0.86%` |
| `HYPE_1M_MA_PBS_C00648` | `platform_break` | `both` | `55/377` | `300/180/30` | `0.97` | `90` | `0.64x` | `36.67%` | `0.684` | `-12.48 bps` | `-15.53%` | `0.590` | `0.912` | `-7.38%` |
| `HYPE_1M_MA_PBS_C00432` | `reclaim` | `both` | `34/233` | `300/180/30` | `1.35` | `126` | `0.49x` | `38.10%` | `0.709` | `-13.93 bps` | `-20.63%` | `0.587` | `1.029` | `-12.93%` |
| `HYPE_1M_MA_PBS_R03281` | `reclaim` | `short` | `34/233` | `320/160/15` | `0.65` | `61` | `0.62x` | `44.26%` | `0.623` | `-19.14 bps` | `-13.95%` | `0.616` | `0.691` | `-9.85%` |
| `HYPE_1M_MA_PBS_R03336` | `platform_break` | `long` | `13/89` | `120/130/15` | `1.35` | `126` | `0.48x` | `36.51%` | `0.575` | `-14.81 bps` | `-17.79%` | `0.730` | `0.753` | `-6.26%` |
| `HYPE_1M_MA_PBS_R02693` | `reclaim` | `short` | `5/34` | `50/100/15` | `0.78` | `73` | `0.52x` | `56.16%` | `0.462` | `-22.55 bps` | `-17.34%` | `0.384` | `0.858` | `-10.51%` |
| `HYPE_1M_MA_PBS_R01053` | `reclaim` | `both` | `34/233` | `260/90/30` | `0.90` | `84` | `0.61x` | `38.10%` | `0.746` | `-14.55 bps` | `-20.70%` | `0.767` | `0.651` | `-15.77%` |
| `HYPE_1M_MA_PBS_R01928` | `reclaim` | `long` | `21/144` | `50/130/15` | `1.49` | `139` | `0.41x` | `53.24%` | `0.523` | `-15.94 bps` | `-20.85%` | `0.589` | `0.534` | `-11.97%` |
| `HYPE_1M_MA_PBS_C03240` | `engulf_reclaim` | `short` | `55/377` | `300/180/30` | `0.68` | `63` | `0.60x` | `39.68%` | `0.508` | `-20.27 bps` | `-14.09%` | `1.019` | `0.508` | `-4.65%` |

## 样本数足够时胜率最高的配置

| name | trigger | side | fast/slow | TP/SL/hold | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE_1M_MA_PBS_R01715` | `reclaim` | `both` | `21/144` | `50/130/45` | `3.38` | `315` | `0.05x` | `60.95%` | `0.475` | `-23.28 bps` | `-52.67%` | `0.464` | `0.475` | `-38.93%` |
| `HYPE_1M_MA_PBS_R01712` | `engulf_reclaim` | `both` | `55/377` | `50/130/30` | `1.14` | `106` | `0.54x` | `57.55%` | `0.568` | `-14.51 bps` | `-14.76%` | `0.621` | `0.706` | `-7.89%` |
| `HYPE_1M_MA_PBS_R03340` | `reclaim` | `both` | `21/144` | `60/160/45` | `3.39` | `316` | `0.04x` | `56.65%` | `0.486` | `-26.42 bps` | `-57.27%` | `0.503` | `0.412` | `-41.13%` |
| `HYPE_1M_MA_PBS_R02871` | `engulf_reclaim` | `long` | `13/89` | `50/100/45` | `4.81` | `448` | `0.02x` | `56.47%` | `0.483` | `-20.92 bps` | `-61.60%` | `0.413` | `0.464` | `-49.93%` |
| `HYPE_1M_MA_PBS_R03411` | `reclaim` | `both` | `34/233` | `50/220/45` | `1.55` | `144` | `0.17x` | `56.25%` | `0.378` | `-31.19 bps` | `-37.34%` | `0.367` | `0.405` | `-28.18%` |
| `HYPE_1M_MA_PBS_R02693` | `reclaim` | `short` | `5/34` | `50/100/15` | `0.78` | `73` | `0.52x` | `56.16%` | `0.462` | `-22.55 bps` | `-17.34%` | `0.384` | `0.858` | `-10.51%` |
| `HYPE_1M_MA_PBS_R02736` | `platform_break` | `long` | `5/34` | `60/100/30` | `1.34` | `125` | `0.51x` | `55.20%` | `0.642` | `-13.53 bps` | `-16.52%` | `1.109` | `0.540` | `-8.25%` |
| `HYPE_1M_MA_PBS_R00895` | `platform_break` | `short` | `13/89` | `60/160/45` | `0.79` | `74` | `0.48x` | `54.05%` | `0.493` | `-25.08 bps` | `-19.92%` | `0.700` | `0.406` | `-11.67%` |
| `HYPE_1M_MA_PBS_R03426` | `reclaim` | `both` | `55/377` | `60/160/45` | `2.19` | `204` | `0.12x` | `53.92%` | `0.481` | `-25.93 bps` | `-42.01%` | `0.497` | `0.423` | `-28.21%` |
| `HYPE_1M_MA_PBS_R01928` | `reclaim` | `long` | `21/144` | `50/130/15` | `1.49` | `139` | `0.41x` | `53.24%` | `0.523` | `-15.94 bps` | `-20.85%` | `0.589` | `0.534` | `-11.97%` |

## 频率压力测试

| 最低 trades/day | 配置数 | 最高全样本年化 | 最高 PF |
| ---: | ---: | ---: | ---: |
| `1.0` | `4143` | `0.57x` | `0.709` |
| `2.0` | `3556` | `0.22x` | `0.660` |
| `3.0` | `3163` | `0.10x` | `0.574` |
| `5.0` | `2370` | `0.02x` | `0.574` |
| `8.0` | `1574` | `0.00x` | `0.504` |

## 月度提示

- top score `HYPE_1M_MA_PBS_R03037` 的负收益月份数：`3`。
- 最差月份 `2026_05`：return `-3.96%`，PF `0.745`，trades `33`。

## 结论

本轮不能把这套 MA 回调剥头皮策略提升为 paper-live 或 live 候选；可以保留最佳配置继续做机制诊断，但不能宣称已盈利可实盘。

## 产物

- 脚本：`research/hype/1m-ma-pullback-scalp/scripts/research_hype_1m_ma_pullback_scalp.py`
- JSON：`research/hype/1m-ma-pullback-scalp/artifacts/hype_1m_ma_pullback_scalp_search_2026-06-26.json`
- Summary CSV：`research/hype/1m-ma-pullback-scalp/artifacts/hype_1m_ma_pullback_scalp_search_summary_2026-06-26.csv`
- Slices CSV：`research/hype/1m-ma-pullback-scalp/artifacts/hype_1m_ma_pullback_scalp_search_slices_2026-06-26.csv`
- Monthly CSV：`research/hype/1m-ma-pullback-scalp/artifacts/hype_1m_ma_pullback_scalp_search_monthly_2026-06-26.csv`
- Top trades CSV：`research/hype/1m-ma-pullback-scalp/artifacts/hype_1m_ma_pullback_scalp_search_top_trades_2026-06-26.csv`
