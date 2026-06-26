# HYPE 5m MA Pullback Scalp robustness 2026-06-26

Family id: `HYPE-5M-MA-Pullback-Scalp`

目标：围绕第一轮通过 paper candidate gate 的两条配置做本地参数邻域复核，判断它们是否只是单点过拟合。

## 固定口径

- 闭合 `5m` K 信号；下一根 open 入场。
- 入场即固定 TP/SL bracket；同 K 同时触及按止损先成交。
- stop/target open 穿越按 open 市价成交；timeout 下一根 open 退出。
- 成本沿用第一轮脚本里的 observed Binance live cost constants。

## 邻域结果

- base candidates: `['HYPE_5M_MA_PBS_R03072', 'HYPE_5M_MA_PBS_R00199']`。
- tested configs: `840`。
- robust pass: `14`。
- robust + monthly pass: `9`。

### HYPE_5M_MA_PBS_R03072

- configs `420`；robust pass `10`；monthly pass `7`。

| base | name | trigger | side | fast/slow | TP/SL/hold | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 | neg months |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__nb_0370` | `reclaim` | `both` | `13/89` | `260/160/45` | `0.19` | `76` | `1.12x` | `50.00%` | `1.233` | `17.81 bps` | `-13.59%` | `2.230` | `4.285` | `6.39%` | `4` |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__nb_0127` | `reclaim` | `both` | `34/233` | `100/240/50` | `0.18` | `70` | `1.08x` | `70.00%` | `1.238` | `12.20 bps` | `-7.91%` | `1.280` | `2.437` | `3.53%` | `5` |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__nb_0298` | `reclaim` | `both` | `34/233` | `160/200/25` | `0.18` | `70` | `1.03x` | `54.29%` | `1.091` | `5.74 bps` | `-9.19%` | `1.558` | `2.093` | `4.30%` | `6` |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__nb_0229` | `reclaim` | `both` | `21/144` | `100/240/40` | `0.15` | `60` | `1.10x` | `73.33%` | `1.346` | `17.41 bps` | `-9.35%` | `1.209` | `inf` | `1.90%` | `4` |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__base` | `reclaim` | `both` | `21/144` | `180/160/45` | `0.35` | `138` | `1.13x` | `52.90%` | `1.158` | `10.89 bps` | `-12.64%` | `1.134` | `1.768` | `0.90%` | `4` |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__nb_0220` | `reclaim` | `both` | `21/144` | `200/200/50` | `0.20` | `80` | `0.89x` | `43.75%` | `0.831` | `-14.80 bps` | `-26.84%` | `1.104` | `3.035` | `3.77%` | `8` |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__nb_0212` | `reclaim` | `both` | `21/144` | `200/160/50` | `0.28` | `109` | `0.98x` | `46.79%` | `0.998` | `-0.13 bps` | `-20.49%` | `1.355` | `2.174` | `-0.27%` | `6` |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__nb_0339` | `reclaim` | `both` | `13/89` | `160/180/35` | `0.53` | `208` | `0.98x` | `54.33%` | `1.003` | `0.19 bps` | `-24.75%` | `1.226` | `1.897` | `-2.06%` | `8` |

### HYPE_5M_MA_PBS_R00199

- configs `420`；robust pass `4`；monthly pass `2`。

| base | name | trigger | side | fast/slow | TP/SL/hold | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 | neg months |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE_5M_MA_PBS_R00199` | `HYPE_5M_MA_PBS_R00199__nb_0394` | `engulf_reclaim` | `both` | `34/233` | `140/180/50` | `0.21` | `81` | `1.07x` | `55.56%` | `1.181` | `9.74 bps` | `-9.87%` | `1.210` | `1.284` | `0.80%` | `5` |
| `HYPE_5M_MA_PBS_R00199` | `HYPE_5M_MA_PBS_R00199__nb_0181` | `engulf_reclaim` | `both` | `89/610` | `220/200/25` | `0.27` | `104` | `1.10x` | `56.73%` | `1.231` | `10.63 bps` | `-8.50%` | `1.218` | `1.024` | `-0.41%` | `6` |
| `HYPE_5M_MA_PBS_R00199` | `HYPE_5M_MA_PBS_R00199__nb_0245` | `engulf_reclaim` | `both` | `89/610` | `160/120/25` | `0.35` | `136` | `0.93x` | `47.06%` | `0.870` | `-5.50 bps` | `-17.58%` | `2.822` | `1.111` | `-0.59%` | `6` |
| `HYPE_5M_MA_PBS_R00199` | `HYPE_5M_MA_PBS_R00199__base` | `engulf_reclaim` | `both` | `89/610` | `180/160/30` | `0.15` | `60` | `1.07x` | `58.33%` | `1.290` | `12.04 bps` | `-6.36%` | `inf` | `1.091` | `2.68%` | `5` |
| `HYPE_5M_MA_PBS_R00199` | `HYPE_5M_MA_PBS_R00199__nb_0001` | `engulf_reclaim` | `both` | `34/233` | `100/80/35` | `0.15` | `59` | `1.00x` | `45.76%` | `1.003` | `0.10 bps` | `-6.39%` | `1.480` | `1.526` | `0.94%` | `5` |
| `HYPE_5M_MA_PBS_R00199` | `HYPE_5M_MA_PBS_R00199__nb_0270` | `engulf_reclaim` | `both` | `55/377` | `100/200/35` | `0.24` | `95` | `0.96x` | `55.79%` | `0.933` | `-3.57 bps` | `-15.84%` | `0.688` | `1.768` | `1.59%` | `7` |
| `HYPE_5M_MA_PBS_R00199` | `HYPE_5M_MA_PBS_R00199__nb_0081` | `engulf_reclaim` | `both` | `89/610` | `100/120/10` | `0.30` | `116` | `0.92x` | `43.10%` | `0.786` | `-7.26 bps` | `-12.91%` | `1.427` | `1.907` | `0.94%` | `7` |
| `HYPE_5M_MA_PBS_R00199` | `HYPE_5M_MA_PBS_R00199__nb_0165` | `engulf_reclaim` | `both` | `89/610` | `260/80/30` | `0.19` | `74` | `1.12x` | `43.24%` | `1.366` | `16.94 bps` | `-10.25%` | `0.787` | `0.923` | `2.38%` | `6` |

## Top Robust Rows

| base | name | trigger | side | fast/slow | TP/SL/hold | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 | neg months |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__nb_0370` | `reclaim` | `both` | `13/89` | `260/160/45` | `0.19` | `76` | `1.12x` | `50.00%` | `1.233` | `17.81 bps` | `-13.59%` | `2.230` | `4.285` | `6.39%` | `4` |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__nb_0127` | `reclaim` | `both` | `34/233` | `100/240/50` | `0.18` | `70` | `1.08x` | `70.00%` | `1.238` | `12.20 bps` | `-7.91%` | `1.280` | `2.437` | `3.53%` | `5` |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__nb_0229` | `reclaim` | `both` | `21/144` | `100/240/40` | `0.15` | `60` | `1.10x` | `73.33%` | `1.346` | `17.41 bps` | `-9.35%` | `1.209` | `inf` | `1.90%` | `4` |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__base` | `reclaim` | `both` | `21/144` | `180/160/45` | `0.35` | `138` | `1.13x` | `52.90%` | `1.158` | `10.89 bps` | `-12.64%` | `1.134` | `1.768` | `0.90%` | `4` |
| `HYPE_5M_MA_PBS_R00199` | `HYPE_5M_MA_PBS_R00199__nb_0394` | `engulf_reclaim` | `both` | `34/233` | `140/180/50` | `0.21` | `81` | `1.07x` | `55.56%` | `1.181` | `9.74 bps` | `-9.87%` | `1.210` | `1.284` | `0.80%` | `5` |
| `HYPE_5M_MA_PBS_R00199` | `HYPE_5M_MA_PBS_R00199__base` | `engulf_reclaim` | `both` | `89/610` | `180/160/30` | `0.15` | `60` | `1.07x` | `58.33%` | `1.290` | `12.04 bps` | `-6.36%` | `inf` | `1.091` | `2.68%` | `5` |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__nb_0190` | `reclaim` | `both` | `21/144` | `260/140/45` | `0.14` | `54` | `1.13x` | `53.70%` | `1.427` | `25.41 bps` | `-10.20%` | `2.063` | `6.016` | `5.15%` | `5` |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__nb_0287` | `reclaim` | `both` | `34/233` | `220/240/45` | `0.14` | `53` | `1.12x` | `50.94%` | `1.369` | `25.45 bps` | `-7.98%` | `1.600` | `2.994` | `1.77%` | `4` |
| `HYPE_5M_MA_PBS_R03072` | `HYPE_5M_MA_PBS_R03072__nb_0255` | `reclaim` | `both` | `13/89` | `200/240/35` | `0.13` | `52` | `1.21x` | `65.38%` | `1.568` | `41.01 bps` | `-7.94%` | `3.217` | `1.176` | `2.42%` | `5` |

## 结论

邻域复核保留了若干可推进配置；它们仍然只是 paper-audit 候选，下一步需要逐笔路径图、paper runner 和 live-runner 订单维护/重启审计。

## 产物

- JSON：`research/hype/5m-ma-pullback-scalp/artifacts/hype_5m_ma_pullback_scalp_robustness_2026-06-26.json`
- Summary CSV：`research/hype/5m-ma-pullback-scalp/artifacts/hype_5m_ma_pullback_scalp_robustness_summary_2026-06-26.csv`
- Monthly CSV：`research/hype/5m-ma-pullback-scalp/artifacts/hype_5m_ma_pullback_scalp_robustness_monthly_2026-06-26.csv`
- Candidate trades CSV：`research/hype/5m-ma-pullback-scalp/artifacts/hype_5m_ma_pullback_scalp_candidate_trades_2026-06-26.csv`
