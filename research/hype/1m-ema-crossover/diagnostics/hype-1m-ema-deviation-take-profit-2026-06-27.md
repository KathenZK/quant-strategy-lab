# HYPE 1m EMA deviation take-profit diagnostic 2026-06-27

Family id: `HYPE-1M-EMA-Crossover`

Status: diagnostic only. This is a new exit-mechanics study for the `1m` EMA-cross family, not a live approval.

## 数据质量

- Normalized OHLCV: `94` 个日分区，`134184` 根 K。
- Raw OHLCV: `94` 个日分区，`134184` 根 K。
- 时间范围：`2026-03-25 00:00:00+00:00` 到 `2026-06-26 04:23:00+00:00`。
- 连续性：expected `134184`，missing `0`，duplicate `0`。
- `is_closed`：`{'True': 134184}`。
- `source`：`{'binance_vision': 132480, 'binance_futures_api': 1177, 'fapi_rest': 527}`。
- OHLC/VWAP/volume hard violations：`{'high_lt_max_open_close': 0, 'low_gt_min_open_close': 0, 'nonpositive_ohlc': 0, 'negative_volume': 0, 'negative_quote_volume': 0, 'negative_trade_count': 0, 'vwap_outside_hilo_nonzero_vol': 0}`。
- Raw/normalized alignment：`{'rows': 134184, 'left_only': 0, 'right_only': 0, 'mismatch_counts': {'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0, 'quote_volume': 0, 'trade_count': 0, 'vwap': 0}, 'max_abs_diff': {'open': 0.0, 'high': 0.0, 'low': 0.0, 'close': 0.0, 'volume': 0.0, 'quote_volume': 0.0, 'trade_count': 0.0, 'vwap': 0.0}}`。

## 策略定义

- 入场：快 EMA 上穿慢 EMA，下一根 `1m` open 做多；快 EMA 下穿慢 EMA，下一根 open 做空。
- EMA 组合：`8/21`、`13/48`、`21/55`、`21/72`、`21/96`、`30/120`。
- 核心偏离变量：多头 `dev = (close - fast_ema) / ATR14`，空头镜像为 `dev = (fast_ema - close) / ATR14`。
- 核心回撤变量：多头 `drawdown = (highest_since_entry - close) / ATR14`，空头镜像为 `drawdown = (close - lowest_since_entry) / ATR14`。
- B 版：`dev` 达到阈值后 arm；arm 后从持仓极值回撤达到阈值，下一根 open 全平。
- C 版：极端偏离先平 `50%`；剩余仓位继续用 arm 后高低点回撤止盈。
- D 版：B 版基础上加入连续两根收回快线另一侧、快线斜率与 EMA gap 同时转弱的衰竭确认。

## 执行模型

- 信号、arm、衰竭确认都只使用已收盘 K；对应动作在下一根 open 执行。
- ATR 硬止损按入场前已知的 `ATR14` 设置；open 穿越 stop 时按 open 市价成交，不按旧 stop 价美化。
- 同一根 K 内，硬止损优先于收盘后的偏离止盈信号。
- 成本：每次 fill fee `5.00 bps` + slippage `2.50 bps`；完整进出 round-trip `15.00 bps`。
- Exposures evaluated: `1,2,3`。

## 搜索规模

- EMA pairs: `8:21,13:48,21:55,21:72,21:96,30:120`。
- Config rows including filters and exposure: `2970`。
- Paper gate: trades >= `30`，PF >= `1.1`，win >= `48%`，maxDD >= `-20%`，validation/forward/recent slices 不得亏损。
- 通过 paper gate：`0`。

没有配置通过完整 paper gate；下面列出的是最接近的诊断配置，不能升级为 paper-live 或 live。

## Top rows

| name | exposure | full_trades | full_total_return | full_annualized_multiple | full_max_dd | full_win_rate | full_profit_factor | fwd_last_20pct_total_return | recent_30d_total_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `HYPE_1M_EMA_DEVIATION_TP_FAST8_SLOW21_D_exhaust_arm2p2_dd1p8_sl1p5_slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.30%` | `0.05x` | `-53.63%` | `18.04%` | `0.436` | `-10.70%` | `-20.49%` |
| `HYPE_1M_EMA_DEVIATION_TP_FAST8_SLOW21_D_exhaust_arm2_dd1p8_sl1p5_slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.45%` | `0.05x` | `-53.78%` | `17.85%` | `0.433` | `-11.21%` | `-20.45%` |
| `HYPE_1M_EMA_DEVIATION_TP_FAST8_SLOW21_B_devtrail_arm2_dd1p2_sl1p5_slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.57%` | `0.05x` | `-53.86%` | `18.23%` | `0.430` | `-11.40%` | `-21.17%` |
| `HYPE_1M_EMA_DEVIATION_TP_FAST8_SLOW21_D_exhaust_arm2_dd1p2_sl1p5_slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.57%` | `0.05x` | `-53.86%` | `18.23%` | `0.430` | `-11.40%` | `-21.17%` |
| `HYPE_1M_EMA_DEVIATION_TP_FAST8_SLOW21_D_exhaust_arm2_dd1p5_sl1p5_slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.61%` | `0.05x` | `-53.93%` | `18.62%` | `0.429` | `-11.72%` | `-20.91%` |
| `HYPE_1M_EMA_DEVIATION_TP_FAST8_SLOW21_B_devtrail_arm2p2_dd1p8_sl1p5_slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.75%` | `0.05x` | `-54.08%` | `18.04%` | `0.431` | `-11.08%` | `-21.03%` |
| `HYPE_1M_EMA_DEVIATION_TP_FAST8_SLOW21_D_exhaust_arm2p2_dd1p5_sl1p5_slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.74%` | `0.05x` | `-54.06%` | `18.43%` | `0.429` | `-11.40%` | `-21.11%` |
| `HYPE_1M_EMA_DEVIATION_TP_FAST8_SLOW21_B_devtrail_arm2_dd1p5_sl1p5_slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.87%` | `0.05x` | `-54.19%` | `18.62%` | `0.426` | `-11.77%` | `-21.01%` |
| `HYPE_1M_EMA_DEVIATION_TP_FAST8_SLOW21_C_staged_p2_dd1p2_sl1p5_slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.66%` | `0.05x` | `-54.12%` | `19.19%` | `0.423` | `-12.63%` | `-22.05%` |
| `HYPE_1M_EMA_DEVIATION_TP_FAST8_SLOW21_B_devtrail_arm2_dd1p8_sl1p5_slope_adx20_atr3p5_100` | `1.000` | `521` | `-54.05%` | `0.05x` | `-54.37%` | `17.85%` | `0.425` | `-11.59%` | `-20.85%` |
| `HYPE_1M_EMA_DEVIATION_TP_FAST8_SLOW21_B_devtrail_arm2p2_dd1p5_sl1p5_slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.94%` | `0.05x` | `-54.26%` | `18.43%` | `0.426` | `-11.45%` | `-21.36%` |
| `HYPE_1M_EMA_DEVIATION_TP_FAST8_SLOW21_C_staged_p2_dd1p5_sl1p5_slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.81%` | `0.05x` | `-54.26%` | `19.39%` | `0.420` | `-12.82%` | `-21.97%` |

## EMA pair surface

| fast_ema | slow_ema | exit_model | filter_name | exposure | full_trades | full_total_return | full_max_dd | full_profit_factor | fwd_last_20pct_total_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `8` | `21` | `D_exhaust_arm2p2_dd1p8_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.30%` | `-53.63%` | `0.436` | `-10.70%` |
| `30` | `120` | `D_exhaust_arm2p2_dd1p8_sl2` | `slope_adx20_atr3p5_100` | `1.000` | `837` | `-65.62%` | `-66.18%` | `0.459` | `-24.54%` |
| `13` | `48` | `D_exhaust_arm2p2_dd1p8_sl2` | `slope_adx20_atr3p5_100` | `1.000` | `906` | `-71.47%` | `-71.55%` | `0.522` | `-16.65%` |
| `21` | `96` | `C_staged_p2p2_dd1p8_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `945` | `-74.34%` | `-74.55%` | `0.318` | `-27.65%` |
| `21` | `72` | `B_devtrail_arm1p8_dd1p8_sl2` | `slope_adx20_atr3p5_100` | `1.000` | `1003` | `-75.99%` | `-76.24%` | `0.415` | `-26.18%` |
| `21` | `55` | `D_exhaust_arm1p8_dd1p8_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `1033` | `-79.10%` | `-79.31%` | `0.380` | `-28.59%` |

## EMA21/96 focus

| fast_ema | slow_ema | exit_model | filter_name | exposure | full_trades | full_total_return | full_max_dd | full_profit_factor | fwd_last_20pct_total_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `21` | `96` | `C_staged_p2_dd1p8_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `945` | `-74.28%` | `-74.48%` | `0.301` | `-28.45%` |
| `21` | `96` | `C_staged_p2p2_dd1p8_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `945` | `-74.34%` | `-74.55%` | `0.318` | `-27.65%` |
| `21` | `96` | `D_exhaust_arm2_dd1p8_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `945` | `-74.80%` | `-75.05%` | `0.398` | `-29.85%` |
| `21` | `96` | `C_staged_p2_dd1p2_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `945` | `-74.81%` | `-75.01%` | `0.267` | `-28.35%` |
| `21` | `96` | `B_devtrail_arm2_dd1p8_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `945` | `-74.83%` | `-75.07%` | `0.397` | `-29.85%` |
| `21` | `96` | `C_staged_p2_dd1p5_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `945` | `-74.83%` | `-75.03%` | `0.277` | `-28.19%` |
| `21` | `96` | `C_staged_p2p5_dd1p8_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `945` | `-74.91%` | `-75.09%` | `0.337` | `-28.77%` |
| `21` | `96` | `C_staged_p2p2_dd1p5_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `945` | `-75.06%` | `-75.27%` | `0.292` | `-27.27%` |
| `21` | `96` | `C_staged_p2p2_dd1p2_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `945` | `-75.13%` | `-75.33%` | `0.278` | `-27.79%` |
| `21` | `96` | `B_devtrail_arm1p8_dd1p2_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `945` | `-75.36%` | `-75.61%` | `0.315` | `-28.36%` |

## Exit family surface

| exit_family | fast_ema | slow_ema | exit_model | filter_name | exposure | full_trades | full_total_return | full_max_dd | full_profit_factor | fwd_last_20pct_total_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `D_exhaustion_confirm` | `8` | `21` | `D_exhaust_arm2p2_dd1p8_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.30%` | `-53.63%` | `0.436` | `-10.70%` |
| `B_deviation_trail` | `8` | `21` | `B_devtrail_arm2_dd1p2_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.57%` | `-53.86%` | `0.430` | `-11.40%` |
| `C_staged_partial` | `8` | `21` | `C_staged_p2_dd1p2_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.66%` | `-54.12%` | `0.423` | `-12.63%` |
| `A_cross_only` | `8` | `21` | `A_cross_only` | `slope_adx20_atr3p5_100` | `1.000` | `521` | `-57.43%` | `-58.64%` | `0.419` | `-8.74%` |

## Filter surface

| fast_ema | slow_ema | exit_model | filter_name | exposure | full_trades | full_total_return | full_max_dd | full_profit_factor | fwd_last_20pct_total_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `8` | `21` | `D_exhaust_arm2p2_dd1p8_sl1p5` | `slope_adx20_atr3p5_100` | `1.000` | `521` | `-53.30%` | `-53.63%` | `0.436` | `-10.70%` |
| `8` | `21` | `B_devtrail_arm2_dd1p8_sl1p5` | `slope_adx18` | `1.000` | `713` | `-61.89%` | `-62.65%` | `0.465` | `-7.36%` |
| `30` | `120` | `B_devtrail_arm1p8_dd1p8_sl1p5` | `none` | `1.000` | `1399` | `-83.36%` | `-83.67%` | `0.421` | `-35.40%` |

## 月度提示

- top score `HYPE_1M_EMA_DEVIATION_TP_FAST8_SLOW21_D_exhaust_arm2p2_dd1p8_sl1p5_slope_adx20_atr3p5_100` 的负收益月份数：`4`。
- 最差月份 `2026-04`：return `-24.87%`，PF `0.265`，trades `175`。

## 结论

本轮证明了“先 arm 偏离、再等回撤确认”的出场机制可以被写成 live-executable 状态机，但在当前数据片段中还没有满足稳健 paper gate 的配置。
重点观察：不要把 `dev >= X ATR` 当成最高点预测；它只应该启动保护状态，真正退出要靠高低点回撤、快线失守或趋势 gap 收窄确认。

## 产物

- 脚本：`research/hype/1m-ema-crossover/scripts/research_hype_1m_ema_deviation_take_profit.py`
- JSON：`research/hype/1m-ema-crossover/artifacts/hype_1m_ema_deviation_take_profit_2026-06-27.json`
- Summary CSV：`research/hype/1m-ema-crossover/artifacts/hype_1m_ema_deviation_take_profit_summary_2026-06-27.csv`
- Slices CSV：`research/hype/1m-ema-crossover/artifacts/hype_1m_ema_deviation_take_profit_slices_2026-06-27.csv`
- Monthly CSV：`research/hype/1m-ema-crossover/artifacts/hype_1m_ema_deviation_take_profit_monthly_2026-06-27.csv`
- Top trades CSV：`research/hype/1m-ema-crossover/artifacts/hype_1m_ema_deviation_take_profit_top_trades_2026-06-27.csv`
