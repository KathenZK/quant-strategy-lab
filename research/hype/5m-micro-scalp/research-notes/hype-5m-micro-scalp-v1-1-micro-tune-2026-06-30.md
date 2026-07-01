# HYPE-5M-Micro-Scalp-V1.1 微调搜索 2026-06-30

Family id：`HYPE-5M-Micro-Scalp`

本报告基于 V1.1 全参数消融暴露出的有效字段做组合微调，目标是寻找更高收益、更低回撤、胜率不过度极端的后续观察版本。

## 搜索规模

- configs evaluated：`44001`。
- 微调只围绕有效参数：EMA、VWAP deviation、ADX/chop/rvol/ATR、EMA distance、close position、HTF/MACD/body、TP/SL、hold/cooldown。

## V1.1 基线

- trades `182`，trades/day `0.46`，ann `2.13x`。
- win `87.91%`，PF `2.660`，avg `45.88 bps`，maxDD `-8.06%`。
- VAL PF `2.441`，FWD PF `5.739`，recent30 `11.86%`。

## 微调结果

- strict improve gate：`2` / `44000`。
- balanced gate：`625` / `44000`。

### 严格优于 V1.1 的候选

| name | changed params | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1.1_tune_grid_004895` | `ema_htf=192; min_adx=0.0; max_chop=70.0; min_rvol=0.75; max_atr_pct_bps=9999.0; tp_bps=110.0; sl_bps=400.0` | `0.45` | `178` | `2.27x` | `2.419` | `84.83%` | `51.12 bps` | `-7.75%` | `6.348` | `12.838` | `12.55%` |
| `V1.1_tune_grid_017477` | `ema_htf=192; min_rvol=0.75; tp_bps=110.0; sl_bps=400.0; max_hold_bars=144` | `0.44` | `173` | `2.21x` | `2.327` | `85.55%` | `50.91 bps` | `-7.64%` | `4.917` | `11.768` | `12.16%` |

### 均衡候选

| name | changed params | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1.1_tune_rand_015295` | `ema_fast=12; vwap_dev_bps=75.0; max_chop=55.0; min_rvol=1.25; max_dist_ema_bps=260.0; close_pos=0.7; require_macd_turn=False; sl_bps=800.0; cooldown_bars=0` | `0.40` | `158` | `2.11x` | `3.285` | `89.24%` | `51.99 bps` | `-7.69%` | `5.624` | `2.928` | `8.30%` |
| `V1.1_tune_grid_021742` | `ema_slow=144; vwap_dev_bps=75.0; max_chop=55.0; min_rvol=0.75; max_atr_pct_bps=9999.0; tp_bps=110.0; sl_bps=400.0; max_hold_bars=144; cooldown_bars=24` | `0.41` | `162` | `2.30x` | `2.634` | `87.65%` | `56.74 bps` | `-9.28%` | `4.095` | `inf` | `14.45%` |
| `V1.1_tune_grid_021901` | `ema_slow=144; vwap_dev_bps=75.0; max_chop=55.0; min_rvol=0.75; max_atr_pct_bps=220.0; tp_bps=110.0; sl_bps=400.0; cooldown_bars=24` | `0.41` | `161` | `2.25x` | `2.685` | `85.71%` | `55.66 bps` | `-9.28%` | `4.107` | `inf` | `13.66%` |
| `V1.1_tune_grid_014910` | `ema_slow=144; vwap_dev_bps=75.0; min_adx=0.0; min_rvol=0.75; tp_bps=110.0; sl_bps=400.0; max_hold_bars=144` | `0.42` | `165` | `2.25x` | `2.542` | `86.06%` | `54.48 bps` | `-9.28%` | `4.095` | `19.540` | `14.84%` |
| `V1.1_tune_grid_004895` | `ema_htf=192; min_adx=0.0; max_chop=70.0; min_rvol=0.75; max_atr_pct_bps=9999.0; tp_bps=110.0; sl_bps=400.0` | `0.45` | `178` | `2.27x` | `2.419` | `84.83%` | `51.12 bps` | `-7.75%` | `6.348` | `12.838` | `12.55%` |
| `V1.1_tune_grid_005966` | `ema_htf=192; min_adx=0.0; min_rvol=0.75; close_pos=0.7; sl_bps=400.0` | `0.48` | `190` | `2.11x` | `2.447` | `87.89%` | `43.47 bps` | `-7.82%` | `5.796` | `13.837` | `14.22%` |
| `V1.1_tune_grid_017685` | `ema_slow=144; vwap_dev_bps=75.0; max_chop=55.0; min_rvol=0.75; max_atr_pct_bps=220.0; sl_bps=400.0; cooldown_bars=72` | `0.39` | `155` | `2.00x` | `2.899` | `89.03%` | `49.19 bps` | `-9.64%` | `3.275` | `inf` | `11.54%` |
| `V1.1_tune_grid_017477` | `ema_htf=192; min_rvol=0.75; tp_bps=110.0; sl_bps=400.0; max_hold_bars=144` | `0.44` | `173` | `2.21x` | `2.327` | `85.55%` | `50.91 bps` | `-7.64%` | `4.917` | `11.768` | `12.16%` |
| `V1.1_tune_grid_017204` | `ema_htf=192; vwap_dev_bps=75.0; min_adx=0.0; min_rvol=0.75; max_atr_pct_bps=9999.0; max_dist_ema_bps=180.0; close_pos=0.7; tp_bps=110.0; sl_bps=400.0` | `0.40` | `157` | `2.13x` | `2.586` | `84.71%` | `53.34 bps` | `-8.59%` | `5.227` | `15.031` | `10.55%` |
| `V1.1_tune_grid_010053` | `vwap_dev_bps=75.0; min_adx=0.0; max_atr_pct_bps=220.0; tp_bps=130.0; max_hold_bars=144` | `0.40` | `157` | `2.37x` | `2.466` | `82.80%` | `61.08 bps` | `-8.64%` | `1.937` | `inf` | `18.89%` |
| `V1.1_tune_grid_019422` | `ema_slow=144; min_rvol=0.75; max_atr_pct_bps=9999.0; max_dist_ema_bps=90.0; close_pos=0.7; tp_bps=75.0; sl_bps=400.0; max_hold_bars=144` | `0.51` | `202` | `1.99x` | `2.456` | `91.58%` | `37.65 bps` | `-8.02%` | `2.761` | `12.798` | `12.92%` |
| `V1.1_tune_grid_016440` | `ema_fast=34; vwap_dev_bps=75.0; min_adx=0.0; max_atr_pct_bps=9999.0; sl_bps=650.0; max_hold_bars=144; cooldown_bars=24` | `0.47` | `186` | `2.06x` | `2.349` | `88.71%` | `42.97 bps` | `-9.65%` | `3.209` | `inf` | `14.38%` |
| `V1.1_tune_grid_008269` | `ema_htf=192; min_adx=0.0; max_chop=70.0; min_rvol=0.75; max_atr_pct_bps=9999.0; max_dist_ema_bps=180.0; tp_bps=110.0; sl_bps=400.0; max_hold_bars=144` | `0.46` | `181` | `2.17x` | `2.158` | `85.08%` | `47.64 bps` | `-8.76%` | `5.092` | `12.838` | `13.33%` |
| `V1.1_tune_grid_003604` | `ema_slow=144; vwap_dev_bps=75.0; max_atr_pct_bps=9999.0; max_dist_ema_bps=180.0; tp_bps=110.0; sl_bps=400.0; max_hold_bars=144` | `0.31` | `121` | `1.95x` | `2.938` | `88.43%` | `60.86 bps` | `-8.26%` | `2.621` | `inf` | `10.94%` |
| `V1.1_tune_rand_010308` | `side_mode=short; ema_fast=34; vwap_dev_bps=85.0; min_adx=0.0; min_atr_pct_bps=18.0; max_dist_ema_bps=260.0; require_macd_turn=False; require_body_dir=False; max_hold_bars=48` | `0.32` | `128` | `1.71x` | `3.066` | `85.16%` | `46.17 bps` | `-5.59%` | `3.137` | `4.038` | `7.17%` |

### 高收益排序

| name | changed params | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1.1_tune_grid_003790` | `ema_slow=144; min_adx=0.0; max_chop=70.0; min_rvol=0.75; max_atr_pct_bps=220.0; close_pos=0.7; tp_bps=110.0; sl_bps=400.0` | `0.56` | `223` | `2.54x` | `2.158` | `83.86%` | `46.54 bps` | `-12.50%` | `5.457` | `23.537` | `24.86%` |
| `V1.1_tune_grid_010793` | `ema_slow=144; min_adx=0.0; min_rvol=0.75; max_atr_pct_bps=220.0; close_pos=0.7; tp_bps=110.0; max_hold_bars=144` | `0.55` | `216` | `2.52x` | `2.144` | `85.65%` | `47.68 bps` | `-13.05%` | `4.672` | `23.537` | `25.73%` |
| `V1.1_tune_grid_020977` | `ema_slow=144; min_adx=0.0; min_rvol=0.75; max_dist_ema_bps=180.0; close_pos=0.7; tp_bps=110.0; max_hold_bars=144` | `0.56` | `222` | `2.46x` | `2.047` | `85.14%` | `45.43 bps` | `-13.05%` | `4.672` | `23.537` | `25.73%` |
| `V1.1_tune_grid_011693` | `ema_slow=144; min_rvol=0.75; max_atr_pct_bps=9999.0; max_dist_ema_bps=90.0; close_pos=0.7; tp_bps=110.0` | `0.50` | `196` | `2.52x` | `2.409` | `86.22%` | `52.34 bps` | `-12.50%` | `2.671` | `19.258` | `19.78%` |
| `V1.1_tune_grid_005462` | `ema_slow=144; min_rvol=0.75; max_dist_ema_bps=90.0; close_pos=0.7; tp_bps=110.0; sl_bps=650.0; max_hold_bars=144` | `0.49` | `195` | `2.58x` | `2.450` | `88.21%` | `54.26 bps` | `-13.11%` | `2.165` | `19.258` | `20.62%` |
| `V1.1_tune_grid_021742` | `ema_slow=144; vwap_dev_bps=75.0; max_chop=55.0; min_rvol=0.75; max_atr_pct_bps=9999.0; tp_bps=110.0; sl_bps=400.0; max_hold_bars=144; cooldown_bars=24` | `0.41` | `162` | `2.30x` | `2.634` | `87.65%` | `56.74 bps` | `-9.28%` | `4.095` | `inf` | `14.45%` |
| `V1.1_tune_grid_004687` | `ema_slow=144; vwap_dev_bps=75.0; min_adx=0.0; max_chop=70.0; min_rvol=0.75; close_pos=0.7; tp_bps=110.0; sl_bps=400.0; max_hold_bars=144` | `0.48` | `190` | `2.41x` | `2.340` | `85.79%` | `51.27 bps` | `-13.80%` | `4.750` | `25.553` | `19.71%` |
| `V1.1_tune_grid_009044` | `ema_slow=144; min_adx=0.0; min_rvol=0.75; max_atr_pct_bps=9999.0; max_dist_ema_bps=90.0; close_pos=0.7` | `0.51` | `200` | `2.41x` | `2.776` | `90.00%` | `48.55 bps` | `-11.54%` | `2.274` | `15.567` | `16.16%` |
| `V1.1_tune_grid_021901` | `ema_slow=144; vwap_dev_bps=75.0; max_chop=55.0; min_rvol=0.75; max_atr_pct_bps=220.0; tp_bps=110.0; sl_bps=400.0; cooldown_bars=24` | `0.41` | `161` | `2.25x` | `2.685` | `85.71%` | `55.66 bps` | `-9.28%` | `4.107` | `inf` | `13.66%` |
| `V1.1_tune_grid_005106` | `ema_slow=144; vwap_dev_bps=75.0; min_adx=0.0; min_rvol=0.75; max_atr_pct_bps=220.0; close_pos=0.7; tp_bps=110.0; max_hold_bars=144` | `0.46` | `183` | `2.33x` | `2.354` | `85.79%` | `51.48 bps` | `-12.51%` | `4.105` | `25.553` | `19.71%` |
| `V1.1_tune_rand_015295` | `ema_fast=12; vwap_dev_bps=75.0; max_chop=55.0; min_rvol=1.25; max_dist_ema_bps=260.0; close_pos=0.7; require_macd_turn=False; sl_bps=800.0; cooldown_bars=0` | `0.40` | `158` | `2.11x` | `3.285` | `89.24%` | `51.99 bps` | `-7.69%` | `5.624` | `2.928` | `8.30%` |
| `V1.1_tune_rand_012697` | `ema_fast=34; min_adx=14.0; min_atr_pct_bps=25.0; max_atr_pct_bps=9999.0; max_dist_ema_bps=400.0; max_hold_bars=144` | `0.64` | `254` | `2.56x` | `2.223` | `88.98%` | `41.13 bps` | `-16.27%` | `2.997` | `5.325` | `16.29%` |
| `V1.1_tune_grid_014910` | `ema_slow=144; vwap_dev_bps=75.0; min_adx=0.0; min_rvol=0.75; tp_bps=110.0; sl_bps=400.0; max_hold_bars=144` | `0.42` | `165` | `2.25x` | `2.542` | `86.06%` | `54.48 bps` | `-9.28%` | `4.095` | `19.540` | `14.84%` |
| `V1.1_tune_rand_007932` | `ema_fast=34; ema_slow=288; vwap_dev_bps=75.0; min_adx=14.0; max_chop=70.0; min_rvol=1.5; max_dist_ema_bps=400.0; require_body_dir=False; tp_bps=150.0; sl_bps=650.0; max_hold_bars=144; cooldown_bars=96` | `0.34` | `133` | `2.42x` | `2.729` | `81.20%` | `73.51 bps` | `-15.43%` | `2.394` | `inf` | `18.77%` |
| `V1.1_tune_grid_016762` | `ema_slow=144; min_rvol=0.75; max_atr_pct_bps=220.0; max_dist_ema_bps=180.0; close_pos=0.7; tp_bps=110.0; max_hold_bars=144; cooldown_bars=72` | `0.54` | `212` | `2.37x` | `2.057` | `84.91%` | `45.53 bps` | `-14.84%` | `4.389` | `22.467` | `24.43%` |

### 低回撤排序

| name | changed params | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1.1_tune_rand_011703` | `ema_slow=144; vwap_dev_bps=75.0; min_adx=0.0; require_macd_turn=False; tp_bps=67.5; sl_bps=800.0; max_hold_bars=144; cooldown_bars=96` | `0.36` | `143` | `1.76x` | `3.941` | `93.71%` | `43.25 bps` | `-7.23%` | `31.774` | `inf` | `8.35%` |
| `V1.1_tune_rand_008764` | `ema_fast=34; vwap_dev_bps=75.0; min_adx=18.0; max_chop=70.0; min_rvol=1.25; max_atr_pct_bps=140.0; max_dist_ema_bps=400.0; close_pos=0.82; require_body_dir=False; tp_bps=75.0; max_hold_bars=192; cooldown_bars=24` | `0.30` | `120` | `1.68x` | `3.664` | `94.17%` | `47.48 bps` | `-6.99%` | `4.035` | `inf` | `6.42%` |
| `V1.1_tune_rand_015295` | `ema_fast=12; vwap_dev_bps=75.0; max_chop=55.0; min_rvol=1.25; max_dist_ema_bps=260.0; close_pos=0.7; require_macd_turn=False; sl_bps=800.0; cooldown_bars=0` | `0.40` | `158` | `2.11x` | `3.285` | `89.24%` | `51.99 bps` | `-7.69%` | `5.624` | `2.928` | `8.30%` |
| `V1.1_tune_rand_015955` | `ema_fast=34; ema_slow=288; vwap_dev_bps=75.0; min_adx=0.0; max_chop=48.0; min_rvol=1.25; min_atr_pct_bps=25.0; max_atr_pct_bps=9999.0; max_dist_ema_bps=180.0; require_macd_turn=False; tp_bps=67.5; sl_bps=400.0; max_hold_bars=144; cooldown_bars=72` | `0.44` | `174` | `1.87x` | `3.211` | `93.10%` | `39.44 bps` | `-6.80%` | `inf` | `inf` | `9.02%` |
| `V1.1_tune_rand_014810` | `ema_fast=34; ema_slow=288; vwap_dev_bps=100.0; min_adx=0.0; max_chop=70.0; min_rvol=1.5; min_atr_pct_bps=18.0; max_atr_pct_bps=9999.0; max_dist_ema_bps=260.0; require_macd_turn=False; tp_bps=67.5; sl_bps=650.0; cooldown_bars=72` | `0.31` | `124` | `1.62x` | `3.775` | `94.35%` | `42.90 bps` | `-8.92%` | `inf` | `inf` | `8.35%` |
| `V1.1_tune_rand_010308` | `side_mode=short; ema_fast=34; vwap_dev_bps=85.0; min_adx=0.0; min_atr_pct_bps=18.0; max_dist_ema_bps=260.0; require_macd_turn=False; require_body_dir=False; max_hold_bars=48` | `0.32` | `128` | `1.71x` | `3.066` | `85.16%` | `46.17 bps` | `-5.59%` | `3.137` | `4.038` | `7.17%` |
| `V1.1_tune_grid_000750` | `ema_slow=144; min_adx=18.0; max_atr_pct_bps=9999.0; max_dist_ema_bps=90.0; close_pos=0.7; max_hold_bars=144; cooldown_bars=24` | `0.31` | `122` | `1.83x` | `3.470` | `91.80%` | `54.51 bps` | `-6.17%` | `6.924` | `1.775` | `2.53%` |
| `V1.1_tune_rand_016446` | `ema_fast=12; vwap_dev_bps=75.0; min_adx=0.0; max_chop=100.0; min_rvol=1.25; min_atr_pct_bps=25.0; max_atr_pct_bps=9999.0; max_dist_ema_bps=260.0; close_pos=0.82; require_macd_turn=False; sl_bps=800.0; max_hold_bars=144` | `0.31` | `124` | `1.85x` | `3.600` | `90.32%` | `54.59 bps` | `-8.08%` | `1.680` | `inf` | `6.95%` |
| `V1.1_tune_grid_004895` | `ema_htf=192; min_adx=0.0; max_chop=70.0; min_rvol=0.75; max_atr_pct_bps=9999.0; tp_bps=110.0; sl_bps=400.0` | `0.45` | `178` | `2.27x` | `2.419` | `84.83%` | `51.12 bps` | `-7.75%` | `6.348` | `12.838` | `12.55%` |
| `V1.1_tune_grid_021901` | `ema_slow=144; vwap_dev_bps=75.0; max_chop=55.0; min_rvol=0.75; max_atr_pct_bps=220.0; tp_bps=110.0; sl_bps=400.0; cooldown_bars=24` | `0.41` | `161` | `2.25x` | `2.685` | `85.71%` | `55.66 bps` | `-9.28%` | `4.107` | `inf` | `13.66%` |
| `V1.1_tune_grid_021742` | `ema_slow=144; vwap_dev_bps=75.0; max_chop=55.0; min_rvol=0.75; max_atr_pct_bps=9999.0; tp_bps=110.0; sl_bps=400.0; max_hold_bars=144; cooldown_bars=24` | `0.41` | `162` | `2.30x` | `2.634` | `87.65%` | `56.74 bps` | `-9.28%` | `4.095` | `inf` | `14.45%` |
| `V1.1_tune_grid_013355` | `ema_htf=192; vwap_dev_bps=75.0; min_rvol=0.75; max_atr_pct_bps=9999.0; tp_bps=110.0; sl_bps=400.0` | `0.35` | `137` | `2.00x` | `2.810` | `84.67%` | `55.86 bps` | `-8.59%` | `4.331` | `10.522` | `7.16%` |
| `V1.1_tune_grid_017685` | `ema_slow=144; vwap_dev_bps=75.0; max_chop=55.0; min_rvol=0.75; max_atr_pct_bps=220.0; sl_bps=400.0; cooldown_bars=72` | `0.39` | `155` | `2.00x` | `2.899` | `89.03%` | `49.19 bps` | `-9.64%` | `3.275` | `inf` | `11.54%` |
| `V1.1_tune_grid_005966` | `ema_htf=192; min_adx=0.0; min_rvol=0.75; close_pos=0.7; sl_bps=400.0` | `0.48` | `190` | `2.11x` | `2.447` | `87.89%` | `43.47 bps` | `-7.82%` | `5.796` | `13.837` | `14.22%` |
| `V1.1_tune_grid_003604` | `ema_slow=144; vwap_dev_bps=75.0; max_atr_pct_bps=9999.0; max_dist_ema_bps=180.0; tp_bps=110.0; sl_bps=400.0; max_hold_bars=144` | `0.31` | `121` | `1.95x` | `2.938` | `88.43%` | `60.86 bps` | `-8.26%` | `2.621` | `inf` | `10.94%` |

## 推荐观察行

- `V1.1_tune_grid_004895`：ann `2.27x`，PF `2.419`，win `84.83%`，avg `51.12 bps`，maxDD `-7.75%`，VAL PF `6.348`，FWD PF `12.838`，recent30 `12.55%`，负收益月份 `0`。
- 最差月份 `2025_05`：return `0.00%`，PF `0.000`，trades `0`。

推荐行参数：

| field | value |
| --- | --- |
| `side_mode` | `both` |
| `ema_fast` | `21` |
| `ema_slow` | `192` |
| `ema_htf` | `192` |
| `vwap_dev_bps` | `65.0` |
| `min_adx` | `0.0` |
| `max_chop` | `70.0` |
| `min_rvol` | `0.75` |
| `min_atr_pct_bps` | `35.0` |
| `max_atr_pct_bps` | `9999.0` |
| `max_dist_ema_bps` | `130.0` |
| `close_pos` | `0.76` |
| `require_htf` | `True` |
| `require_macd_turn` | `True` |
| `require_body_dir` | `True` |
| `tp_bps` | `110.0` |
| `sl_bps` | `400.0` |
| `max_hold_bars` | `96` |
| `cooldown_bars` | `48` |

## 结论

- 微调阶段可以找到更激进的收益版本，但如果回撤、分段样本或胜率范围不过关，不应替代 V1.1。
- 推荐观察行仍然只是 paper-audit observation；进入 live/paper-live/handoff 前必须补逐笔路径、订单维护、重启恢复和 paper/live reconciliation。

## 产物

- Summary CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_1_micro_tune_summary_2026-06-30.csv`
- Monthly CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_1_micro_tune_monthly_2026-06-30.csv`
- Preferred trades CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_1_micro_tune_preferred_trades_2026-06-30.csv`
- JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_1_micro_tune_2026-06-30.json`
