# HYPE-5M-PBTR-V3.3.1 rescue search 2026-06-27

Family id：`HYPE-5M-PBTR`

本报告尝试在 V3.3.1 上“救活”旧 pullback-trailing 线：固定 no-initial-stop trailing overlay，扫描负/小 `pullback_buffer`、多空方向、信号 K 可得过滤器、`stop_arm_deadline` 和 `max_hold`。

过滤器只使用信号 K 收盘前可得数据：`dir_ret192_bps`、EMA21/96 spread bps、方向性 adverse wick / ATR、方向性 close position。

Prescreen 配置数：`262`；进入四口径复核配置数：`60`。

## 5m conservative prescreen Top 20

| config | mode | trades | total | win | PF | payoff | max_dd |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `pbm0p0125__both__close0p75_wick0p25__deadline9__maxholdnone` | `5m_conservative` | `5` | `4.96%` | `80.00%` | `75.822` | `18.956` | `-1.75%` |
| `pbm0p0125__both__close0p75_wick0p25__deadline9__maxhold36` | `5m_conservative` | `5` | `4.96%` | `80.00%` | `75.822` | `18.956` | `-1.75%` |
| `pbm0p0125__both__adverse_wick_le_0p25__deadline9__maxholdnone` | `5m_conservative` | `6` | `3.70%` | `66.67%` | `3.922` | `1.961` | `-2.92%` |
| `pbm0p0125__both__adverse_wick_le_0p25__deadline9__maxhold36` | `5m_conservative` | `6` | `3.70%` | `66.67%` | `3.922` | `1.961` | `-2.92%` |
| `pbm0p0100__long__ret192_ge_250__deadline9__maxholdnone` | `5m_conservative` | `12` | `8.28%` | `66.67%` | `3.236` | `1.618` | `-4.58%` |
| `pbm0p0100__long__ret192_ge_250__deadline9__maxhold36` | `5m_conservative` | `12` | `8.28%` | `66.67%` | `3.236` | `1.618` | `-4.58%` |
| `pbm0p0100__long__ret250_spread200__deadline9__maxholdnone` | `5m_conservative` | `12` | `8.28%` | `66.67%` | `3.236` | `1.618` | `-4.58%` |
| `pbm0p0100__long__ret250_spread200__deadline9__maxhold36` | `5m_conservative` | `12` | `8.28%` | `66.67%` | `3.236` | `1.618` | `-4.58%` |
| `pbm0p0100__long__ret250_spread200_close0p6__deadline9__maxholdnone` | `5m_conservative` | `12` | `8.28%` | `66.67%` | `3.236` | `1.618` | `-4.58%` |
| `pbm0p0100__long__ret250_spread200_close0p6__deadline9__maxhold36` | `5m_conservative` | `12` | `8.28%` | `66.67%` | `3.236` | `1.618` | `-4.58%` |
| `pbm0p0100__long__close0p75_wick0p25__deadline9__maxholdnone` | `5m_conservative` | `10` | `7.47%` | `60.00%` | `2.716` | `1.811` | `-4.58%` |
| `pbm0p0100__long__close0p75_wick0p25__deadline9__maxhold36` | `5m_conservative` | `10` | `7.47%` | `60.00%` | `2.716` | `1.811` | `-4.58%` |
| `pbm0p0100__long__spread125_wick0p25__deadline9__maxholdnone` | `5m_conservative` | `9` | `7.39%` | `66.67%` | `2.671` | `1.335` | `-4.58%` |
| `pbm0p0100__long__spread125_wick0p25__deadline9__maxhold36` | `5m_conservative` | `9` | `7.39%` | `66.67%` | `2.671` | `1.335` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200__deadline9__maxholdnone` | `5m_conservative` | `34` | `18.07%` | `55.88%` | `2.360` | `1.863` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200__deadline9__maxhold36` | `5m_conservative` | `34` | `18.07%` | `55.88%` | `2.360` | `1.863` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200_close0p6__deadline9__maxholdnone` | `5m_conservative` | `34` | `18.07%` | `55.88%` | `2.360` | `1.863` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200_close0p6__deadline9__maxhold36` | `5m_conservative` | `34` | `18.07%` | `55.88%` | `2.360` | `1.863` | `-4.58%` |
| `pbm0p0100__long__adverse_wick_le_0p25__deadline9__maxholdnone` | `5m_conservative` | `11` | `6.18%` | `54.55%` | `2.135` | `1.779` | `-4.58%` |
| `pbm0p0100__long__adverse_wick_le_0p25__deadline9__maxhold36` | `5m_conservative` | `11` | `6.18%` | `54.55%` | `2.135` | `1.779` | `-4.58%` |

## 四口径复核 Top 30

| config | mode | trades | total | win | PF | payoff | max_dd |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `pbm0p0100__both__close0p75_wick0p25__deadline9__maxholdnone` | `5m_optimistic` | `20` | `12.26%` | `65.00%` | `2.435` | `1.311` | `-5.19%` |
| `pbm0p0100__both__close0p75_wick0p25__deadline9__maxhold36` | `5m_optimistic` | `20` | `12.26%` | `65.00%` | `2.435` | `1.311` | `-5.19%` |
| `pbm0p0075__long__ret250_spread200__deadline9__maxholdnone` | `5m_conservative` | `34` | `18.07%` | `55.88%` | `2.360` | `1.863` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200__deadline9__maxhold36` | `5m_conservative` | `34` | `18.07%` | `55.88%` | `2.360` | `1.863` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200_close0p6__deadline9__maxholdnone` | `5m_conservative` | `34` | `18.07%` | `55.88%` | `2.360` | `1.863` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200_close0p6__deadline9__maxhold36` | `5m_conservative` | `34` | `18.07%` | `55.88%` | `2.360` | `1.863` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200__deadline9__maxholdnone` | `1m_conservative` | `34` | `17.57%` | `55.88%` | `2.326` | `1.836` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200__deadline9__maxholdnone` | `1m_optimistic` | `34` | `17.57%` | `55.88%` | `2.326` | `1.836` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200__deadline9__maxhold36` | `1m_conservative` | `34` | `17.57%` | `55.88%` | `2.326` | `1.836` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200__deadline9__maxhold36` | `1m_optimistic` | `34` | `17.57%` | `55.88%` | `2.326` | `1.836` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200_close0p6__deadline9__maxholdnone` | `1m_conservative` | `34` | `17.57%` | `55.88%` | `2.326` | `1.836` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200_close0p6__deadline9__maxholdnone` | `1m_optimistic` | `34` | `17.57%` | `55.88%` | `2.326` | `1.836` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200_close0p6__deadline9__maxhold36` | `1m_conservative` | `34` | `17.57%` | `55.88%` | `2.326` | `1.836` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200_close0p6__deadline9__maxhold36` | `1m_optimistic` | `34` | `17.57%` | `55.88%` | `2.326` | `1.836` | `-4.58%` |
| `pbm0p0100__both__adverse_wick_le_0p25__deadline9__maxholdnone` | `5m_optimistic` | `21` | `11.59%` | `61.90%` | `2.272` | `1.398` | `-5.19%` |
| `pbm0p0100__both__adverse_wick_le_0p25__deadline9__maxhold36` | `5m_optimistic` | `21` | `11.59%` | `61.90%` | `2.272` | `1.398` | `-5.19%` |
| `pbm0p0075__long__ret250_spread200__deadline9__maxholdnone` | `5m_optimistic` | `34` | `16.65%` | `50.00%` | `2.190` | `2.190` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200__deadline9__maxhold36` | `5m_optimistic` | `34` | `16.65%` | `50.00%` | `2.190` | `2.190` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200_close0p6__deadline9__maxholdnone` | `5m_optimistic` | `34` | `16.65%` | `50.00%` | `2.190` | `2.190` | `-4.58%` |
| `pbm0p0075__long__ret250_spread200_close0p6__deadline9__maxhold36` | `5m_optimistic` | `34` | `16.65%` | `50.00%` | `2.190` | `2.190` | `-4.58%` |
| `pbm0p0100__both__close0p75_wick0p25__deadline9__maxholdnone` | `1m_optimistic` | `20` | `10.51%` | `65.00%` | `2.148` | `1.156` | `-5.19%` |
| `pbm0p0100__both__close0p75_wick0p25__deadline9__maxhold36` | `1m_optimistic` | `20` | `10.51%` | `65.00%` | `2.148` | `1.156` | `-5.19%` |
| `pbm0p0100__both__ret192_ge_250__deadline9__maxholdnone` | `5m_optimistic` | `25` | `11.98%` | `64.00%` | `2.077` | `1.168` | `-7.39%` |
| `pbm0p0100__both__ret192_ge_250__deadline9__maxhold36` | `5m_optimistic` | `25` | `11.98%` | `64.00%` | `2.077` | `1.168` | `-7.39%` |
| `pbm0p0075__long__ret192_ge_250__deadline9__maxholdnone` | `5m_conservative` | `39` | `16.02%` | `53.85%` | `2.047` | `1.754` | `-4.58%` |
| `pbm0p0075__long__ret192_ge_250__deadline9__maxhold36` | `5m_conservative` | `39` | `16.02%` | `53.85%` | `2.047` | `1.754` | `-4.58%` |
| `pbm0p0100__long__none__deadline9__maxholdnone` | `5m_optimistic` | `20` | `8.93%` | `55.00%` | `2.025` | `1.657` | `-5.53%` |
| `pbm0p0100__long__none__deadline9__maxhold36` | `5m_optimistic` | `20` | `8.93%` | `55.00%` | `2.025` | `1.657` | `-5.53%` |
| `pbm0p0100__long__spread_le_200__deadline9__maxholdnone` | `5m_optimistic` | `20` | `8.93%` | `55.00%` | `2.025` | `1.657` | `-5.53%` |
| `pbm0p0100__long__spread_le_200__deadline9__maxhold36` | `5m_optimistic` | `20` | `8.93%` | `55.00%` | `2.025` | `1.657` | `-5.53%` |

## Robust 聚合

| config | min_trades | min_pf | min_total | max_dd_worst | modes |
| --- | ---: | ---: | ---: | ---: | ---: |
| `pbm0p0075__long__ret250_spread200__deadline9__maxhold36` | `34` | `2.190` | `16.65%` | `-4.58%` | `4` |
| `pbm0p0075__long__ret250_spread200__deadline9__maxholdnone` | `34` | `2.190` | `16.65%` | `-4.58%` | `4` |
| `pbm0p0075__long__ret250_spread200_close0p6__deadline9__maxhold36` | `34` | `2.190` | `16.65%` | `-4.58%` | `4` |
| `pbm0p0075__long__ret250_spread200_close0p6__deadline9__maxholdnone` | `34` | `2.190` | `16.65%` | `-4.58%` | `4` |
| `pbm0p0075__long__ret192_ge_250__deadline9__maxhold36` | `39` | `1.911` | `14.51%` | `-4.58%` | `4` |
| `pbm0p0075__long__ret192_ge_250__deadline9__maxholdnone` | `39` | `1.911` | `14.51%` | `-4.58%` | `4` |
| `pbm0p0100__both__close0p75_wick0p25__deadline9__maxhold36` | `20` | `1.894` | `8.75%` | `-5.56%` | `4` |
| `pbm0p0100__both__close0p75_wick0p25__deadline9__maxholdnone` | `20` | `1.894` | `8.75%` | `-5.56%` | `4` |
| `pbm0p0100__both__ret192_ge_250__deadline9__maxhold36` | `25` | `1.759` | `9.05%` | `-7.39%` | `4` |
| `pbm0p0100__both__ret192_ge_250__deadline9__maxholdnone` | `25` | `1.759` | `9.05%` | `-7.39%` | `4` |
| `pbm0p0100__both__adverse_wick_le_0p25__deadline9__maxhold36` | `21` | `1.689` | `7.45%` | `-5.56%` | `4` |
| `pbm0p0100__both__adverse_wick_le_0p25__deadline9__maxholdnone` | `21` | `1.689` | `7.45%` | `-5.56%` | `4` |
| `pbm0p0100__long__close_pos_ge_0p6__deadline9__maxhold36` | `20` | `1.632` | `6.04%` | `-6.10%` | `4` |
| `pbm0p0100__long__close_pos_ge_0p6__deadline9__maxholdnone` | `20` | `1.632` | `6.04%` | `-6.10%` | `4` |
| `pbm0p0100__long__none__deadline9__maxhold36` | `20` | `1.632` | `6.04%` | `-6.10%` | `4` |
| `pbm0p0100__long__none__deadline9__maxholdnone` | `20` | `1.632` | `6.04%` | `-6.10%` | `4` |
| `pbm0p0100__long__spread_le_200__deadline9__maxhold36` | `20` | `1.632` | `6.04%` | `-6.10%` | `4` |
| `pbm0p0100__long__spread_le_200__deadline9__maxholdnone` | `20` | `1.632` | `6.04%` | `-6.10%` | `4` |
| `pbm0p0100__both__ret250_spread200__deadline9__maxhold36` | `22` | `1.466` | `5.29%` | `-7.39%` | `4` |
| `pbm0p0100__both__ret250_spread200__deadline9__maxholdnone` | `22` | `1.466` | `5.29%` | `-7.39%` | `4` |

## 结论

若 robust 表中没有 `min_trades >= 30` 且四口径 `min_pf > 1` 的配置，则本轮过滤/overlay 仍不能证明 V3.3.1 被救活。少量低样本正收益只能作为事件质量线索，不能直接进入 paper/live。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3-1_rescue_search.py`
- JSON：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_rescue_search_2026-06-27.json`
- prescreen CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_rescue_prescreen_2026-06-27.csv`
- full CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_rescue_full_2026-06-27.csv`
- robust CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_rescue_robust_2026-06-27.csv`
- top trades CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_rescue_top_trades_2026-06-27.csv`
