# HYPE 5m Micro-Scalp executable search 2026-06-26

Family id: `HYPE-5M-Micro-Scalp`

目标：在 Binance HYPEUSDT 永续 `5m` K 上搜索每天约 `3-5` 笔、回撤小、单笔微利、高胜率、累计年化尽量高的可实盘微利 scalp。

## 数据质量

- Normalized OHLCV: `393` 个日分区，`112822` 根 K。
- 时间范围：`2025-05-30 10:30:00+00:00` 到 `2026-06-26 04:15:00+00:00`。
- 连续性：expected `112822`，missing `0`，duplicate `0`。
- `is_closed`：`{'True': 112822}`。
- `source`：`{'binance_futures_kline_api': 101956, 'ccxt': 8423, 'binance_futures_api': 2443}`。
- OHLC/VWAP/volume 硬违规：`{'high_lt_max_open_close': 0, 'low_gt_min_open_close': 0, 'nonpositive_ohlc': 0, 'negative_volume': 0, 'negative_quote_volume': 0, 'vwap_outside_hilo_nonzero_vol': 0}`。
- Raw OHLCV evidence file count：`393`。

## 执行模型

- 信号只使用已收盘 K 线信息；下一根 K 的 open 入场。
- 入场后立刻有固定 TP/SL bracket；保护止损从第一根持仓 K 开始生效。
- 同一根 K 同时可能触及 TP/SL 时，保守按止损先成交。
- stop/target 被 open 穿越时按 open 市价成交，不按旧 stop/target 价成交。
- 超时退出使用下一根 open，不使用不可实盘保证的 bar close。
- 成本：fee `4.1466 bps/fill`，entry slippage `10.73 bps`，exit slippage `-2.64 bps`。

## 搜索规模

- curated + random configs: `12576`。
- random seed: `20260626`。
- 指标族：EMA、RSI、MACD、Bollinger z-score、rolling/day VWAP deviation、Donchian、ATR、ADX、Choppiness、relative volume、wick/close-position candle structure。

## 用户目标命中

- frequency pass (`3-5` trades/day): `1595`。
- hard pass (`3-5` trades/day, win >= `65%`, PF >= `1.05`, maxDD >= `-15%`, ann > 1x): `0`。
- audit pass (hard pass plus train/val/fwd/recent checks): `0`。

没有配置通过完整 audit gate。

## 最接近用户目标的配置

| name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE_5M_MS_R11999` | `wick_reject` | `short` | `4.05` | `1585` | `0.16x` | `83.72%` | `0.626` | `-12.17 bps` | `-86.53%` | `0.535` | `0.525` |
| `HYPE_5M_MS_R09398` | `macd_flip` | `long` | `3.92` | `1536` | `0.16x` | `55.34%` | `0.698` | `-12.59 bps` | `-86.77%` | `0.783` | `0.942` |
| `HYPE_5M_MS_R04327` | `macd_flip` | `both` | `3.85` | `1509` | `0.14x` | `65.47%` | `0.618` | `-13.59 bps` | `-87.76%` | `0.689` | `0.870` |
| `HYPE_5M_MS_R11725` | `vwap_revert` | `both` | `4.22` | `1655` | `0.11x` | `76.56%` | `0.654` | `-13.77 bps` | `-90.87%` | `0.613` | `0.647` |
| `HYPE_5M_MS_R02271` | `macd_flip` | `short` | `4.10` | `1607` | `0.18x` | `54.88%` | `0.718` | `-11.24 bps` | `-84.52%` | `0.664` | `0.690` |
| `HYPE_5M_MS_R10283` | `trend_rsi_snapback` | `both` | `4.10` | `1606` | `0.09x` | `82.88%` | `0.509` | `-15.45 bps` | `-92.34%` | `0.527` | `0.479` |
| `HYPE_5M_MS_R03666` | `momentum_pause` | `short` | `3.94` | `1543` | `0.09x` | `72.26%` | `0.664` | `-16.05 bps` | `-92.40%` | `0.548` | `0.708` |
| `HYPE_5M_MS_R10321` | `ema_reclaim` | `both` | `3.96` | `1552` | `0.11x` | `76.93%` | `0.552` | `-15.17 bps` | `-91.04%` | `0.535` | `0.435` |
| `HYPE_5M_MS_R03338` | `wick_reject` | `both` | `3.87` | `1515` | `0.11x` | `84.95%` | `0.410` | `-15.06 bps` | `-90.40%` | `0.544` | `0.345` |
| `HYPE_5M_MS_R05773` | `momentum_pause` | `long` | `4.11` | `1612` | `0.10x` | `82.44%` | `0.513` | `-15.11 bps` | `-91.92%` | `0.503` | `0.412` |
| `HYPE_5M_MS_R07556` | `bb_revert` | `both` | `3.79` | `1486` | `0.15x` | `56.46%` | `0.726` | `-13.05 bps` | `-87.74%` | `0.903` | `0.835` |
| `HYPE_5M_MS_R01043` | `momentum_pause` | `both` | `4.26` | `1670` | `0.11x` | `73.05%` | `0.705` | `-13.44 bps` | `-90.55%` | `0.783` | `0.489` |

## 频率达标内胜率最高的配置

| name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE_5M_MS_R03338` | `wick_reject` | `both` | `3.87` | `1515` | `0.11x` | `84.95%` | `0.410` | `-15.06 bps` | `-90.40%` | `0.544` | `0.345` |
| `HYPE_5M_MS_R08242` | `micro_breakout` | `long` | `4.29` | `1681` | `0.05x` | `84.77%` | `0.352` | `-19.22 bps` | `-96.34%` | `0.425` | `0.481` |
| `HYPE_5M_MS_R11999` | `wick_reject` | `short` | `4.05` | `1585` | `0.16x` | `83.72%` | `0.626` | `-12.17 bps` | `-86.53%` | `0.535` | `0.525` |
| `HYPE_5M_MS_R06180` | `ema_reclaim` | `both` | `4.81` | `1886` | `0.06x` | `82.93%` | `0.400` | `-15.34 bps` | `-94.87%` | `0.449` | `0.376` |
| `HYPE_5M_MS_R10283` | `trend_rsi_snapback` | `both` | `4.10` | `1606` | `0.09x` | `82.88%` | `0.509` | `-15.45 bps` | `-92.34%` | `0.527` | `0.479` |
| `HYPE_5M_MS_R06888` | `ema_reclaim` | `short` | `3.39` | `1329` | `0.16x` | `82.77%` | `0.522` | `-14.63 bps` | `-87.21%` | `0.443` | `0.392` |
| `HYPE_5M_MS_R11595` | `momentum_pause` | `both` | `3.26` | `1279` | `0.10x` | `82.56%` | `0.346` | `-19.26 bps` | `-91.98%` | `0.394` | `0.325` |
| `HYPE_5M_MS_R05773` | `momentum_pause` | `long` | `4.11` | `1612` | `0.10x` | `82.44%` | `0.513` | `-15.11 bps` | `-91.92%` | `0.503` | `0.412` |
| `HYPE_5M_MS_R06179` | `ema_reclaim` | `short` | `3.22` | `1262` | `0.10x` | `82.41%` | `0.417` | `-18.82 bps` | `-91.35%` | `0.462` | `0.338` |
| `HYPE_5M_MS_R08302` | `ema_reclaim` | `both` | `4.61` | `1807` | `0.08x` | `82.40%` | `0.482` | `-14.48 bps` | `-93.20%` | `0.413` | `0.622` |
| `HYPE_5M_MS_R07073` | `trend_rsi_snapback` | `both` | `4.43` | `1734` | `0.06x` | `82.06%` | `0.374` | `-16.95 bps` | `-95.23%` | `0.394` | `0.288` |
| `HYPE_5M_MS_R05695` | `momentum_pause` | `both` | `4.73` | `1852` | `0.06x` | `81.16%` | `0.493` | `-16.14 bps` | `-95.44%` | `0.551` | `0.593` |

## 年化上限审计

| 最低 trades/day | 配置数 | 最高全样本年化 |
| ---: | ---: | ---: |
| `1.0` | `6569` | `0.98x` |
| `2.0` | `4509` | `0.43x` |
| `3.0` | `3149` | `0.23x` |
| `4.0` | `2214` | `0.18x` |
| `5.0` | `1554` | `0.08x` |

## 月度风险提示

- top score `HYPE_5M_MS_R11999` 的负收益月份数：`12`。
- 最差月份 `2025_06`：return `-26.53%`，PF `0.488`，trades `138`。

## 结论

本轮不能提升 live/paper-live 候选。即使搜索空间专门偏向微利高胜率和每天 `3-5` 笔频率，最接近配置仍未同时通过频率、胜率、回撤、PF、VAL/FWD 和近期稳定性约束。

## 产物

- 脚本：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_search.py`
- JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_search_2026-06-26.json`
- 汇总 CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_search_summary_2026-06-26.csv`
- 切片 CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_search_slices_2026-06-26.csv`
- 月度 CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_search_monthly_2026-06-26.csv`
- Top trades CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_search_top_trades_2026-06-26.csv`
