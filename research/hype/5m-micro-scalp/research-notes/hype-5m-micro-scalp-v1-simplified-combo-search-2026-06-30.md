# HYPE-5M-Micro-Scalp-V1 精简参数组合搜索 2026-06-30

Family id：`HYPE-5M-Micro-Scalp`

本轮目标是把 V1 中在 `vwap_revert` 下不生效的 dormant 参数固定，只围绕真实影响信号与退出的字段做组合搜索，寻找比 V1 更高收益、更低回撤、胜率适中的后续观察版本。

## 精简方式

- 固定入场机制：`entry_style=vwap_revert`，继续保留 `require_trend=true` 和 EMA 趋势门槛；不再搜索 RSI、Bollinger、Donchian、wick、pullback、breakout、momentum-pause 等对当前入场风格不生效的字段。
- 保留有效字段 `19` 个：`side_mode, ema_fast, ema_slow, ema_htf, vwap_dev_bps, min_adx, max_chop, min_rvol, min_atr_pct_bps, max_atr_pct_bps, max_dist_ema_bps, close_pos, require_htf, require_macd_turn, require_body_dir, tp_bps, sl_bps, max_hold_bars, cooldown_bars`。
- 允许少量 filter-disable 组合，例如 `cooldown_bars=0`、`max_chop=100`、`max_dist_ema_bps=9999`、`require_body_dir=false`，用于确认 V1 的过滤是否真的必要。

## 数据与执行口径

- 数据：Binance HYPEUSDT perpetual `5m`，`2025-05-30 10:30:00+00:00` 到 `2026-06-30 06:15:00+00:00`，`113998` 根 K。
- 连续性：expected `113998`，missing `0`，duplicate `0`。
- OHLC/VWAP/volume 硬违规：`{'high_lt_max_open_close': 0, 'low_gt_min_open_close': 0, 'nonpositive_ohlc': 0, 'negative_volume': 0, 'negative_quote_volume': 0, 'vwap_outside_hilo_nonzero_vol': 0}`。
- raw/normalized 对齐：`{'raw_files': 397, 'normalized_rows': 113998, 'raw_rows': 113998, 'merged_rows': 113998, 'timestamp_mismatch': 0, 'field_mismatches': {'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0, 'quote_volume': 0, 'trade_count': 0, 'vwap': 0, 'is_closed': 0}, 'max_abs_diff': {'open': 0.0, 'high': 0.0, 'low': 0.0, 'close': 0.0, 'volume': 0.0, 'quote_volume': 0.0, 'trade_count': 0.0, 'vwap': 0.0, 'is_closed': 0.0}}`。
- 信号：闭合 K；入场：下一根 open；退出：入场即固定 TP/SL bracket；同 K 同时触及按 stop-first；timeout 下一根 open。
- 成本：fee `4.1466 bps/fill`，entry slippage `10.73 bps`，exit slippage `-2.64 bps`。

## 搜索规模

- configs evaluated：`49016`。
- seed：`20260630`；core configs sampled：`24000`；random configs requested：`25000`。
- 结构：V1 baseline + 消融优选 seed + 固定 EMA21/96 的核心网格 + 有效字段 random combo。

## 当前数据上的 V1 精简基线

- trades `189`，trades/day `0.48`，ann `1.34x`。
- win `85.71%`，PF `1.490`，avg `17.32 bps`，maxDD `-8.16%`。
- VAL PF `5.445`，FWD PF `4.186`，recent30 `9.95%`。

## 组合结果

- balanced gate：`6548` / `49015`。
- strict improve gate（收益高于 V1 且回撤低于 V1）：`633` / `49015`。

### 严格改进候选

| name | changed effective params | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1S_core_032883` | `max_atr_pct_bps=220.0; max_dist_ema_bps=130.0; close_pos=0.76; sl_bps=400.0; max_hold_bars=72; cooldown_bars=0` | `0.38` | `149` | `1.57x` | `2.527` | `89.93%` | `33.38 bps` | `-6.52%` | `4.292` | `inf` | `7.68%` |
| `V1S_core_023723` | `min_adx=18.0; max_atr_pct_bps=220.0; max_dist_ema_bps=130.0; close_pos=0.64; sl_bps=500.0; max_hold_bars=36; cooldown_bars=24` | `0.42` | `167` | `1.57x` | `2.272` | `86.83%` | `29.69 bps` | `-6.90%` | `5.754` | `3.144` | `8.23%` |
| `V1S_core_032980` | `max_dist_ema_bps=130.0; close_pos=0.76; sl_bps=500.0; max_hold_bars=72; cooldown_bars=0` | `0.38` | `149` | `1.55x` | `2.409` | `89.93%` | `32.31 bps` | `-7.68%` | `4.292` | `inf` | `7.68%` |
| `V1S_core_034423` | `min_adx=0.0; max_atr_pct_bps=220.0; max_dist_ema_bps=180.0; close_pos=0.76; sl_bps=400.0; max_hold_bars=72; cooldown_bars=24` | `0.38` | `150` | `1.52x` | `2.277` | `89.33%` | `30.77 bps` | `-6.52%` | `3.974` | `inf` | `7.02%` |
| `V1S_core_023702` | `min_adx=0.0; max_dist_ema_bps=130.0; close_pos=0.64; sl_bps=400.0` | `0.48` | `191` | `1.59x` | `1.950` | `89.53%` | `26.98 bps` | `-7.56%` | `4.381` | `3.049` | `9.21%` |
| `V1S_core_032887` | `min_adx=0.0; max_atr_pct_bps=220.0; max_dist_ema_bps=130.0; close_pos=0.76; sl_bps=400.0; max_hold_bars=72; cooldown_bars=24` | `0.35` | `140` | `1.49x` | `2.356` | `89.29%` | `31.55 bps` | `-7.09%` | `3.974` | `inf` | `7.02%` |
| `V1S_core_023526` | `min_adx=18.0; max_dist_ema_bps=130.0; close_pos=0.64; sl_bps=300.0; max_hold_bars=36; cooldown_bars=0` | `0.45` | `178` | `1.54x` | `2.027` | `86.52%` | `26.80 bps` | `-6.65%` | `6.189` | `3.844` | `8.99%` |
| `V1S_core_034429` | `min_adx=0.0; max_atr_pct_bps=220.0; max_dist_ema_bps=180.0; close_pos=0.76; sl_bps=400.0; max_hold_bars=72` | `0.37` | `148` | `1.50x` | `2.243` | `89.19%` | `30.35 bps` | `-6.52%` | `3.974` | `inf` | `7.02%` |
| `V1S_core_028133` | `min_adx=18.0; max_atr_pct_bps=220.0; max_dist_ema_bps=130.0; sl_bps=300.0; max_hold_bars=36; cooldown_bars=0` | `0.39` | `156` | `1.51x` | `2.209` | `87.18%` | `29.12 bps` | `-6.23%` | `7.361` | `3.237` | `6.99%` |
| `V1S_core_034438` | `max_dist_ema_bps=180.0; close_pos=0.76; sl_bps=400.0; max_hold_bars=72; cooldown_bars=48` | `0.37` | `147` | `1.49x` | `2.226` | `89.12%` | `30.14 bps` | `-6.52%` | `3.815` | `inf` | `7.02%` |

### 均衡候选

| name | changed effective params | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1S_core_032883` | `max_atr_pct_bps=220.0; max_dist_ema_bps=130.0; close_pos=0.76; sl_bps=400.0; max_hold_bars=72; cooldown_bars=0` | `0.38` | `149` | `1.57x` | `2.527` | `89.93%` | `33.38 bps` | `-6.52%` | `4.292` | `inf` | `7.68%` |
| `V1S_core_023723` | `min_adx=18.0; max_atr_pct_bps=220.0; max_dist_ema_bps=130.0; close_pos=0.64; sl_bps=500.0; max_hold_bars=36; cooldown_bars=24` | `0.42` | `167` | `1.57x` | `2.272` | `86.83%` | `29.69 bps` | `-6.90%` | `5.754` | `3.144` | `8.23%` |
| `V1S_core_032980` | `max_dist_ema_bps=130.0; close_pos=0.76; sl_bps=500.0; max_hold_bars=72; cooldown_bars=0` | `0.38` | `149` | `1.55x` | `2.409` | `89.93%` | `32.31 bps` | `-7.68%` | `4.292` | `inf` | `7.68%` |
| `V1S_core_026870` | `min_adx=0.0; close_pos=0.64; sl_bps=500.0` | `0.53` | `211` | `1.65x` | `1.922` | `89.10%` | `26.43 bps` | `-9.36%` | `4.881` | `3.918` | `10.24%` |
| `V1S_rand_016782` | `ema_slow=144; vwap_dev_bps=65.0; min_adx=10.0; max_chop=62.0; min_rvol=1.0; max_atr_pct_bps=140.0; max_dist_ema_bps=9999.0; close_pos=0.76; require_htf=True; require_macd_turn=True; require_body_dir=False; tp_bps=90.0; sl_bps=500.0; max_hold_bars=72; cooldown_bars=48` | `0.38` | `151` | `1.77x` | `2.468` | `86.09%` | `41.75 bps` | `-8.34%` | `2.211` | `7.841` | `9.30%` |
| `V1S_core_034423` | `min_adx=0.0; max_atr_pct_bps=220.0; max_dist_ema_bps=180.0; close_pos=0.76; sl_bps=400.0; max_hold_bars=72; cooldown_bars=24` | `0.38` | `150` | `1.52x` | `2.277` | `89.33%` | `30.77 bps` | `-6.52%` | `3.974` | `inf` | `7.02%` |
| `V1S_core_023702` | `min_adx=0.0; max_dist_ema_bps=130.0; close_pos=0.64; sl_bps=400.0` | `0.48` | `191` | `1.59x` | `1.950` | `89.53%` | `26.98 bps` | `-7.56%` | `4.381` | `3.049` | `9.21%` |
| `V1S_core_032887` | `min_adx=0.0; max_atr_pct_bps=220.0; max_dist_ema_bps=130.0; close_pos=0.76; sl_bps=400.0; max_hold_bars=72; cooldown_bars=24` | `0.35` | `140` | `1.49x` | `2.356` | `89.29%` | `31.55 bps` | `-7.09%` | `3.974` | `inf` | `7.02%` |
| `V1S_core_023526` | `min_adx=18.0; max_dist_ema_bps=130.0; close_pos=0.64; sl_bps=300.0; max_hold_bars=36; cooldown_bars=0` | `0.45` | `178` | `1.54x` | `2.027` | `86.52%` | `26.80 bps` | `-6.65%` | `6.189` | `3.844` | `8.99%` |
| `V1S_core_034429` | `min_adx=0.0; max_atr_pct_bps=220.0; max_dist_ema_bps=180.0; close_pos=0.76; sl_bps=400.0; max_hold_bars=72` | `0.37` | `148` | `1.50x` | `2.243` | `89.19%` | `30.35 bps` | `-6.52%` | `3.974` | `inf` | `7.02%` |
| `V1S_core_028133` | `min_adx=18.0; max_atr_pct_bps=220.0; max_dist_ema_bps=130.0; sl_bps=300.0; max_hold_bars=36; cooldown_bars=0` | `0.39` | `156` | `1.51x` | `2.209` | `87.18%` | `29.12 bps` | `-6.23%` | `7.361` | `3.237` | `6.99%` |
| `V1S_core_026871` | `max_atr_pct_bps=220.0; close_pos=0.64; sl_bps=500.0` | `0.52` | `207` | `1.61x` | `1.881` | `88.89%` | `25.75 bps` | `-9.36%` | `4.742` | `3.918` | `10.24%` |

### 高收益排序

| name | changed effective params | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1S_core_003454` | `vwap_dev_bps=60.0; close_pos=0.58; tp_bps=55.0; sl_bps=500.0; cooldown_bars=48` | `0.71` | `283` | `1.83x` | `2.098` | `91.87%` | `23.72 bps` | `-8.59%` | `5.007` | `2.965` | `10.74%` |
| `V1S_core_003453` | `vwap_dev_bps=60.0; max_atr_pct_bps=220.0; close_pos=0.58; tp_bps=55.0; sl_bps=500.0; cooldown_bars=48` | `0.71` | `282` | `1.83x` | `2.090` | `91.84%` | `23.63 bps` | `-8.63%` | `5.007` | `2.965` | `10.74%` |
| `V1S_core_034033` | `min_adx=0.0; max_atr_pct_bps=220.0; max_dist_ema_bps=180.0; close_pos=0.76; tp_bps=55.0; sl_bps=400.0; max_hold_bars=72; cooldown_bars=0` | `0.42` | `167` | `1.58x` | `2.877` | `92.81%` | `29.88 bps` | `-6.68%` | `3.679` | `inf` | `6.09%` |
| `V1S_core_003446` | `vwap_dev_bps=60.0; min_adx=0.0; close_pos=0.58; tp_bps=55.0; sl_bps=500.0` | `0.74` | `292` | `1.93x` | `2.198` | `92.12%` | `24.78 bps` | `-8.88%` | `5.230` | `2.205` | `9.12%` |
| `V1S_core_003439` | `vwap_dev_bps=60.0; min_adx=0.0; max_atr_pct_bps=220.0; close_pos=0.58; tp_bps=55.0; sl_bps=500.0; cooldown_bars=24` | `0.77` | `305` | `1.94x` | `2.119` | `92.13%` | `24.01 bps` | `-9.32%` | `5.452` | `2.277` | `9.66%` |
| `V1S_rand_018690` | `ema_slow=144; vwap_dev_bps=65.0; min_adx=10.0; max_chop=100.0; max_atr_pct_bps=350.0; max_dist_ema_bps=130.0; close_pos=0.76; require_htf=True; require_macd_turn=True; require_body_dir=False; tp_bps=110.0; sl_bps=650.0; max_hold_bars=192; cooldown_bars=72` | `0.51` | `200` | `2.12x` | `1.869` | `87.50%` | `42.46 bps` | `-21.23%` | `2.645` | `19.257` | `20.61%` |
| `V1S_rand_016782` | `ema_slow=144; vwap_dev_bps=65.0; min_adx=10.0; max_chop=62.0; min_rvol=1.0; max_atr_pct_bps=140.0; max_dist_ema_bps=9999.0; close_pos=0.76; require_htf=True; require_macd_turn=True; require_body_dir=False; tp_bps=90.0; sl_bps=500.0; max_hold_bars=72; cooldown_bars=48` | `0.38` | `151` | `1.77x` | `2.468` | `86.09%` | `41.75 bps` | `-8.34%` | `2.211` | `7.841` | `9.30%` |
| `V1S_core_000380` | `vwap_dev_bps=60.0; min_adx=0.0; max_dist_ema_bps=130.0; close_pos=0.58; tp_bps=55.0; sl_bps=500.0; cooldown_bars=48` | `0.66` | `260` | `1.77x` | `2.148` | `91.92%` | `24.24 bps` | `-9.48%` | `4.896` | `2.866` | `10.20%` |
| `V1S_core_023412` | `min_adx=18.0; max_dist_ema_bps=130.0; close_pos=0.64; tp_bps=55.0; sl_bps=500.0; cooldown_bars=24` | `0.42` | `167` | `1.55x` | `2.662` | `93.41%` | `28.78 bps` | `-5.96%` | `3.227` | `3.362` | `6.74%` |
| `V1S_core_007669` | `vwap_dev_bps=60.0; min_adx=0.0; max_atr_pct_bps=220.0; max_dist_ema_bps=180.0; close_pos=0.64; tp_bps=90.0; sl_bps=500.0` | `0.64` | `254` | `2.14x` | `1.897` | `83.46%` | `33.28 bps` | `-11.04%` | `2.619` | `1.962` | `10.71%` |
| `V1S_core_007664` | `vwap_dev_bps=60.0; min_adx=0.0; max_dist_ema_bps=180.0; close_pos=0.64; tp_bps=90.0; sl_bps=500.0; cooldown_bars=24` | `0.68` | `271` | `2.24x` | `1.887` | `83.76%` | `33.21 bps` | `-11.04%` | `1.925` | `2.048` | `11.64%` |
| `V1S_core_032883` | `max_atr_pct_bps=220.0; max_dist_ema_bps=130.0; close_pos=0.76; sl_bps=400.0; max_hold_bars=72; cooldown_bars=0` | `0.38` | `149` | `1.57x` | `2.527` | `89.93%` | `33.38 bps` | `-6.52%` | `4.292` | `inf` | `7.68%` |

### 低回撤排序

| name | changed effective params | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1S_core_034033` | `min_adx=0.0; max_atr_pct_bps=220.0; max_dist_ema_bps=180.0; close_pos=0.76; tp_bps=55.0; sl_bps=400.0; max_hold_bars=72; cooldown_bars=0` | `0.42` | `167` | `1.58x` | `2.877` | `92.81%` | `29.88 bps` | `-6.68%` | `3.679` | `inf` | `6.09%` |
| `V1S_core_023412` | `min_adx=18.0; max_dist_ema_bps=130.0; close_pos=0.64; tp_bps=55.0; sl_bps=500.0; cooldown_bars=24` | `0.42` | `167` | `1.55x` | `2.662` | `93.41%` | `28.78 bps` | `-5.96%` | `3.227` | `3.362` | `6.74%` |
| `V1S_core_035670` | `min_adx=18.0; close_pos=0.76; tp_bps=55.0; sl_bps=500.0; max_hold_bars=72; cooldown_bars=0` | `0.37` | `146` | `1.49x` | `2.844` | `93.84%` | `30.02 bps` | `-7.22%` | `3.171` | `inf` | `5.56%` |
| `V1S_core_034131` | `max_atr_pct_bps=220.0; max_dist_ema_bps=180.0; close_pos=0.76; tp_bps=55.0; sl_bps=500.0; max_hold_bars=72; cooldown_bars=0` | `0.42` | `165` | `1.55x` | `2.778` | `92.73%` | `29.29 bps` | `-7.65%` | `3.552` | `inf` | `6.09%` |
| `V1S_core_034038` | `min_adx=18.0; max_dist_ema_bps=180.0; close_pos=0.76; tp_bps=55.0; sl_bps=400.0; max_hold_bars=72; cooldown_bars=0` | `0.35` | `139` | `1.45x` | `2.768` | `93.53%` | `29.48 bps` | `-6.24%` | `2.917` | `inf` | `5.05%` |
| `V1S_core_034040` | `min_adx=0.0; max_dist_ema_bps=180.0; close_pos=0.76; tp_bps=55.0; sl_bps=400.0; max_hold_bars=72; cooldown_bars=24` | `0.38` | `151` | `1.49x` | `2.710` | `92.72%` | `28.87 bps` | `-6.68%` | `3.171` | `inf` | `5.56%` |
| `V1S_core_023424` | `min_adx=18.0; max_dist_ema_bps=130.0; close_pos=0.64; tp_bps=55.0; sl_bps=500.0; cooldown_bars=48` | `0.41` | `161` | `1.51x` | `2.559` | `93.17%` | `28.01 bps` | `-6.00%` | `3.116` | `3.008` | `5.70%` |
| `V1S_core_023417` | `min_adx=18.0; max_atr_pct_bps=220.0; max_dist_ema_bps=130.0; close_pos=0.64; tp_bps=55.0; sl_bps=500.0` | `0.41` | `161` | `1.51x` | `2.559` | `93.17%` | `28.01 bps` | `-6.00%` | `3.116` | `3.185` | `6.22%` |
| `V1S_core_034037` | `min_adx=18.0; max_atr_pct_bps=220.0; max_dist_ema_bps=180.0; close_pos=0.76; tp_bps=55.0; sl_bps=400.0; max_hold_bars=72; cooldown_bars=0` | `0.35` | `138` | `1.45x` | `2.746` | `93.48%` | `29.33 bps` | `-6.24%` | `2.917` | `inf` | `5.05%` |
| `V1S_core_034046` | `min_adx=0.0; max_dist_ema_bps=180.0; close_pos=0.76; tp_bps=55.0; sl_bps=400.0; max_hold_bars=72` | `0.38` | `150` | `1.48x` | `2.691` | `92.67%` | `28.73 bps` | `-6.68%` | `3.171` | `inf` | `5.56%` |
| `V1S_core_034052` | `min_adx=0.0; max_dist_ema_bps=180.0; close_pos=0.76; tp_bps=55.0; sl_bps=400.0; max_hold_bars=72; cooldown_bars=48` | `0.38` | `150` | `1.48x` | `2.691` | `92.67%` | `28.73 bps` | `-6.68%` | `3.171` | `inf` | `5.56%` |
| `V1S_core_032499` | `max_atr_pct_bps=220.0; max_dist_ema_bps=130.0; close_pos=0.76; tp_bps=55.0; sl_bps=400.0; max_hold_bars=72; cooldown_bars=0` | `0.38` | `150` | `1.48x` | `2.691` | `92.67%` | `28.73 bps` | `-6.68%` | `3.552` | `inf` | `6.09%` |

## 月度提示

- 主观察行：`V1S_core_032883`；负收益月份 `0`。

## 结论

本轮找到严格优于当前数据 V1 的观察候选 `V1S_core_032883`，但它仍只是 `paper-audit observation`，不能替代 V1 或进入实盘。下一步必须做逐笔路径、参数邻域、walk-forward 和订单维护审计。

## 产物

- 脚本：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_simplified_combo_search.py`
- Summary CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_simplified_combo_summary_2026-06-30.csv`
- Monthly CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_simplified_combo_monthly_2026-06-30.csv`
- Top trades CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_simplified_combo_top_trades_2026-06-30.csv`
- JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_simplified_combo_2026-06-30.json`
