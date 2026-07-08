# HYPE-5M-Micro-Scalp-V1 精简候选局部稳健性 2026-06-30

Family id：`HYPE-5M-Micro-Scalp`

本报告围绕精简组合搜索的前排候选做局部邻域测试，目的是确认改善不是单点参数尖峰。它仍是 audit observation，不是 promotion。

## 输入

- 来源组合报告：`research/hype/5m-micro-scalp/notes/hype-5m-micro-scalp-v1-simplified-combo-search-2026-06-30.md`。
- 来源 summary：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_simplified_combo_summary_2026-06-30.csv`。
- seed candidates：`V1S_core_032883, V1S_core_023723, V1S_core_023702, V1S_core_034033, V1S_rand_016782`。
- 每个候选 random local configs：`2500`。

## 数据与执行口径

- 数据：`2025-05-30 10:30:00+00:00` 到 `2026-06-30 06:15:00+00:00`，`113998` 根 Binance HYPEUSDT perpetual `5m` K。
- 缺口 `0`，OHLC/VWAP/volume 硬违规：`{'high_lt_max_open_close': 0, 'low_gt_min_open_close': 0, 'nonpositive_ohlc': 0, 'negative_volume': 0, 'negative_quote_volume': 0, 'vwap_outside_hilo_nonzero_vol': 0}`。
- 执行：闭合 K 信号、下一根 open 入场、入场即 TP/SL bracket、同 K stop-first、timeout 下一根 open。
- 成本：fee `4.1466 bps/fill`，entry slippage `10.73 bps`，exit slippage `-2.64 bps`。

## 稳健性摘要

| seed | configs | strict improve | strict rate | audit-like | audit-like rate | median ann | p25 ann | median PF | median DD | p10 DD | best ann | best DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1S_core_023702` | `2682` | `77` | `2.9%` | `242` | `9.0%` | `1.14x` | `1.03x` | `1.365` | `-12.41%` | `-25.82%` | `2.18x` | `-12.03%` |
| `V1S_core_023723` | `2675` | `128` | `4.8%` | `238` | `8.9%` | `1.13x` | `1.04x` | `1.363` | `-10.93%` | `-23.72%` | `1.32x` | `-4.14%` |
| `V1S_core_034033` | `2671` | `34` | `1.3%` | `232` | `8.7%` | `1.15x` | `1.05x` | `1.507` | `-10.38%` | `-21.59%` | `1.56x` | `-5.97%` |
| `V1S_core_032883` | `2674` | `81` | `3.0%` | `204` | `7.6%` | `1.15x` | `1.05x` | `1.475` | `-10.46%` | `-21.36%` | `1.42x` | `-4.15%` |
| `V1S_rand_016782` | `2687` | `44` | `1.6%` | `185` | `6.9%` | `1.19x` | `1.07x` | `1.465` | `-11.72%` | `-21.72%` | `1.61x` | `-5.35%` |

## Top Audit-Like Neighbors

| name | seed | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 | strict | audit-like |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `V1S_rand_016782__N02381` | `V1S_rand_016782` | `0.38` | `152` | `1.61x` | `3.892` | `93.42%` | `34.26 bps` | `-5.35%` | `3.432` | `inf` | `6.61%` | `False` | `True` |
| `V1S_core_034033__N01788` | `V1S_core_034033` | `0.30` | `120` | `1.46x` | `4.047` | `92.50%` | `34.37 bps` | `-4.62%` | `4.935` | `inf` | `5.05%` | `False` | `True` |
| `V1S_rand_016782__N00596` | `V1S_rand_016782` | `0.46` | `182` | `2.13x` | `2.660` | `87.91%` | `45.88 bps` | `-8.06%` | `2.441` | `5.739` | `11.86%` | `True` | `True` |
| `V1S_rand_016782__N00646` | `V1S_rand_016782` | `0.50` | `199` | `1.80x` | `2.479` | `89.45%` | `32.68 bps` | `-7.67%` | `5.530` | `8.362` | `9.74%` | `True` | `True` |
| `V1S_core_032883__N00217` | `V1S_core_032883` | `0.32` | `128` | `1.59x` | `3.388` | `92.19%` | `39.87 bps` | `-5.14%` | `21.962` | `inf` | `7.68%` | `False` | `True` |
| `V1S_core_023702__N02585` | `V1S_core_023702` | `0.36` | `142` | `1.67x` | `3.166` | `93.66%` | `39.63 bps` | `-7.85%` | `inf` | `inf` | `11.74%` | `False` | `True` |
| `V1S_rand_016782__N00284` | `V1S_rand_016782` | `0.38` | `152` | `2.12x` | `3.339` | `92.11%` | `54.42 bps` | `-9.97%` | `2.518` | `2.790` | `6.93%` | `False` | `True` |
| `V1S_core_023702__N02659` | `V1S_core_023702` | `0.32` | `127` | `1.83x` | `2.480` | `85.04%` | `52.47 bps` | `-7.83%` | `41.683` | `4.490` | `11.26%` | `True` | `True` |
| `V1S_core_034033__N00051` | `V1S_core_034033` | `0.42` | `167` | `1.61x` | `3.126` | `92.81%` | `31.15 bps` | `-5.74%` | `3.679` | `inf` | `6.09%` | `False` | `True` |
| `V1S_core_034033__N02030` | `V1S_core_034033` | `0.30` | `120` | `1.44x` | `3.526` | `93.33%` | `33.00 bps` | `-5.33%` | `4.914` | `inf` | `5.05%` | `False` | `True` |
| `V1S_rand_016782__N00685` | `V1S_rand_016782` | `0.33` | `129` | `1.73x` | `2.687` | `89.15%` | `46.85 bps` | `-8.43%` | `3.414` | `inf` | `7.85%` | `False` | `True` |
| `V1S_rand_016782__N00321` | `V1S_rand_016782` | `0.44` | `176` | `1.87x` | `2.191` | `86.93%` | `39.63 bps` | `-7.97%` | `2.819` | `7.224` | `11.57%` | `True` | `True` |
| `V1S_rand_016782__N00123` | `V1S_rand_016782` | `0.37` | `145` | `1.83x` | `2.827` | `86.90%` | `45.73 bps` | `-7.17%` | `2.106` | `7.841` | `9.30%` | `True` | `True` |
| `V1S_core_032883__N00524` | `V1S_core_032883` | `0.41` | `164` | `1.61x` | `2.475` | `87.80%` | `32.04 bps` | `-6.59%` | `4.402` | `inf` | `9.02%` | `True` | `True` |
| `V1S_core_023702__N00042` | `V1S_core_023702` | `0.34` | `136` | `1.60x` | `3.038` | `91.91%` | `38.13 bps` | `-6.78%` | `24.705` | `inf` | `9.69%` | `False` | `True` |

## Top Strict Improve Neighbors

| name | seed | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 | strict | audit-like |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `V1S_rand_016782__N00596` | `V1S_rand_016782` | `0.46` | `182` | `2.13x` | `2.660` | `87.91%` | `45.88 bps` | `-8.06%` | `2.441` | `5.739` | `11.86%` | `True` | `True` |
| `V1S_rand_016782__N00646` | `V1S_rand_016782` | `0.50` | `199` | `1.80x` | `2.479` | `89.45%` | `32.68 bps` | `-7.67%` | `5.530` | `8.362` | `9.74%` | `True` | `True` |
| `V1S_core_023702__N02659` | `V1S_core_023702` | `0.32` | `127` | `1.83x` | `2.480` | `85.04%` | `52.47 bps` | `-7.83%` | `41.683` | `4.490` | `11.26%` | `True` | `True` |
| `V1S_rand_016782__N00321` | `V1S_rand_016782` | `0.44` | `176` | `1.87x` | `2.191` | `86.93%` | `39.63 bps` | `-7.97%` | `2.819` | `7.224` | `11.57%` | `True` | `True` |
| `V1S_rand_016782__N00123` | `V1S_rand_016782` | `0.37` | `145` | `1.83x` | `2.827` | `86.90%` | `45.73 bps` | `-7.17%` | `2.106` | `7.841` | `9.30%` | `True` | `True` |
| `V1S_core_032883__N00524` | `V1S_core_032883` | `0.41` | `164` | `1.61x` | `2.475` | `87.80%` | `32.04 bps` | `-6.59%` | `4.402` | `inf` | `9.02%` | `True` | `True` |
| `V1S_rand_016782__N00122` | `V1S_rand_016782` | `0.36` | `144` | `1.81x` | `2.803` | `86.81%` | `45.46 bps` | `-7.17%` | `2.106` | `7.841` | `9.30%` | `True` | `True` |
| `V1S_rand_016782__N00118` | `V1S_rand_016782` | `0.36` | `144` | `1.81x` | `2.803` | `86.81%` | `45.46 bps` | `-7.17%` | `2.106` | `7.841` | `9.30%` | `True` | `True` |
| `V1S_rand_016782__N00037` | `V1S_rand_016782` | `0.36` | `144` | `1.81x` | `2.803` | `86.81%` | `45.46 bps` | `-7.17%` | `2.106` | `7.841` | `9.30%` | `True` | `True` |
| `V1S_core_032883__N00202` | `V1S_core_032883` | `0.38` | `150` | `1.58x` | `2.546` | `90.00%` | `33.57 bps` | `-6.52%` | `4.451` | `inf` | `7.68%` | `True` | `True` |
| `V1S_core_032883__N00204` | `V1S_core_032883` | `0.38` | `150` | `1.58x` | `2.546` | `90.00%` | `33.57 bps` | `-6.52%` | `4.451` | `inf` | `7.68%` | `True` | `True` |
| `V1S_core_032883__N00032` | `V1S_core_032883` | `0.38` | `149` | `1.57x` | `2.527` | `89.93%` | `33.38 bps` | `-6.52%` | `4.292` | `inf` | `7.68%` | `True` | `True` |
| `V1S_core_032883__N00031` | `V1S_core_032883` | `0.38` | `149` | `1.57x` | `2.527` | `89.93%` | `33.38 bps` | `-6.52%` | `4.292` | `inf` | `7.68%` | `True` | `True` |
| `V1S_core_032883__N00000` | `V1S_core_032883` | `0.38` | `149` | `1.57x` | `2.527` | `89.93%` | `33.38 bps` | `-6.52%` | `4.292` | `inf` | `7.68%` | `True` | `True` |
| `V1S_core_032883__N00009` | `V1S_core_032883` | `0.38` | `149` | `1.57x` | `2.527` | `89.93%` | `33.38 bps` | `-6.52%` | `4.292` | `inf` | `7.68%` | `True` | `True` |

## 主观察结论

- 推荐下一步优先审计 `V1S_rand_016782__N00596`（seed `V1S_rand_016782`）：ann `2.13x`，PF `2.660`，win `87.91%`，maxDD `-8.06%`，recent30 `11.86%`，负收益月份 `2`。该行后续已记录为 `HYPE-5M-Micro-Scalp-V1.1`，但仍不是 live-ready。

## 推荐行参数

| field | value |
| --- | --- |
| `side_mode` | `both` |
| `ema_fast` | `21` |
| `ema_slow` | `192` |
| `ema_htf` | `384` |
| `vwap_dev_bps` | `65.0` |
| `min_adx` | `10.0` |
| `max_chop` | `62.0` |
| `min_rvol` | `1.0` |
| `min_atr_pct_bps` | `35.0` |
| `max_atr_pct_bps` | `350.0` |
| `max_dist_ema_bps` | `130.0` |
| `close_pos` | `0.76` |
| `require_htf` | `True` |
| `require_macd_turn` | `True` |
| `require_body_dir` | `True` |
| `tp_bps` | `90.0` |
| `sl_bps` | `500.0` |
| `max_hold_bars` | `96` |
| `cooldown_bars` | `48` |

固定机制与 dormant 字段：`entry_style=vwap_revert`，`require_trend=true`；RSI/Bollinger/Donchian/wick/pullback/breakout/momentum-pause 参数不参与当前信号。
- 该推荐不是 live-ready：还需要逐笔路径图、同 K TP/SL 与 gap ordering 审计、参数邻域二次收缩、walk-forward 固化、订单维护与 restart-state 审计。

## 产物

- 脚本：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_simplified_candidate_robustness.py`
- Summary CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_simplified_candidate_robustness_summary_2026-06-30.csv`
- By-seed CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_simplified_candidate_robustness_by_seed_2026-06-30.csv`
- Monthly CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_simplified_candidate_robustness_monthly_2026-06-30.csv`
- Preferred trades CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_simplified_candidate_robustness_preferred_trades_2026-06-30.csv`
- JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_simplified_candidate_robustness_2026-06-30.json`
