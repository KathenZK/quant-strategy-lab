# SOL-1H-Adaptive-Regime-V2 参数规格 - 2026-07-07

## 版本身份

- Version：`SOL-1H-Adaptive-Regime-V2`
- Status：`registered observation / NO-GO / not promoted / not live-ready`
- Market：Binance USD-M Futures `SOLUSDT` perpetual
- Timeframe：`1h`
- Mechanism：`donchian_break + vwap_revert` 双腿 ensemble
- Source observation：`ENS__SOL_1H_AR_HW_R132002__SOL_1H_AR_HW_R243705`
- Evidence：`diagnostics/sol-1h-ar-high-win-target-search-2026-07-07.md`

## 结论

V2 记录的是 2026-07-07 高胜率硬目标搜索中的最佳冻结观察值，不是 promotion。它在 full 区间达到高胜率和低回撤，但没有达到年化 `>=10x`，且最近三个月 reused holdout 明显走弱。

- full：annual `2.07x`，return `290.00%`，DD `-17.41%`，win `93.91%`，trades `115`，PF `3.907`。
- last `1y`：annual `1.60x`，return `60.19%`，DD `-17.41%`，win `92.31%`，trades `52`，PF `2.561`。
- reused holdout / last `3m`：annual `0.70x`，return `-8.53%`，DD `-15.69%`，win `66.67%`，trades `6`，PF `0.398`。
- hard target：`False`；`10x / 80% / <20% DD` 没有命中。

## 数据、成本与执行口径

- 数据：冻结两年研究帧，`2024-07-03T05:00:00+00:00` 至 `2026-07-03T04:00:00+00:00`，`17520` 根闭合 `1h` K。
- 选择窗口：train `2024-08-17T05:00:00+00:00` 至 `2025-09-07T07:24:00+00:00`；validation `2025-09-07T07:24:00+00:00` 至 `2026-04-03T05:00:00+00:00`。
- 最近三个月：`2026-04-03T05:00:00+00:00` 至 `2026-07-03T05:00:00+00:00`，已在 V1 揭盲，本轮作为 reused holdout，只用于审计。
- 费用：`0.001` fee/fill。
- 滑点：`4 bps` adverse slippage/fill。
- Funding：逐笔计入真实 Binance funding history。
- 执行：闭合 `1h` K 产生信号，下一根 open 市价成交；单仓不加仓；入场后保护 bracket 即生效；同 K 双触发 stop-first；open 穿越 stop 按 open 成交；trailing 只在完整 K 闭合后更新并从下一根 K 生效。

## Ensemble 规则

- Leg 优先级使用搜索时的 prefit score。
- 多腿交易合并时按 entry index 排序，若持仓区间重叠则只保留优先级更高的一笔；`blocked_until = exit_i`。
- V2 配置名：`SOL_1H_AR_HW_R132002 + SOL_1H_AR_HW_R243705`。

## Leg 1：Donchian Break

- `name` = `SOL_1H_AR_HW_R132002`
- `style` = `donchian_break`
- `side_mode` = `both`
- `ema_fast` = `144`
- `ema_slow` = `233`
- `ema_htf` = `377`
- `indicator_window` = `24`
- `threshold_low` = `25.0`
- `threshold_high` = `75.0`
- `band_k` = `1.5`
- `pullback_atr` = `0.25`
- `roc_window` = `24`
- `roc_threshold_bps` = `50.0`
- `macd_fast` = `34`
- `macd_slow` = `89`
- `macd_signal` = `13`
- `min_adx` = `36.0`
- `max_adx` = `100.0`
- `min_rvol` = `1.0`
- `min_atr_bps` = `100.0`
- `max_atr_bps` = `10000.0`
- `min_dir_roc_bps` = `100.0`
- `max_dist_ema_bps` = `750.0`
- `htf_mode` = `none`
- `require_macd_turn` = `true`
- `require_body_dir` = `false`
- `max_aligned_funding_bps` = `2.0`
- `exit_kind` = `fixed`
- `tp_atr` = `0.75`
- `sl_atr` = `4.0`
- `trail_activation_atr` = `0.75`
- `trail_atr` = `0.5`
- `max_hold_bars` = `120`
- `cooldown_bars` = `0`
- `entry_delay_bars` = `1`
- `sizing_kind` = `fixed`
- `fixed_leverage` = `3.0`
- `risk_fraction` = `0.01`
- `max_leverage` = `2.5`

## Leg 2：VWAP Revert

- `name` = `SOL_1H_AR_HW_R243705`
- `style` = `vwap_revert`
- `side_mode` = `short`
- `ema_fast` = `34`
- `ema_slow` = `55`
- `ema_htf` = `89`
- `indicator_window` = `48`
- `threshold_low` = `30.0`
- `threshold_high` = `70.0`
- `band_k` = `1.25`
- `pullback_atr` = `0.25`
- `roc_window` = `72`
- `roc_threshold_bps` = `50.0`
- `macd_fast` = `8`
- `macd_slow` = `21`
- `macd_signal` = `5`
- `min_adx` = `0.0`
- `max_adx` = `100.0`
- `min_rvol` = `0.0`
- `min_atr_bps` = `125.0`
- `max_atr_bps` = `10000.0`
- `min_dir_roc_bps` = `-10000.0`
- `max_dist_ema_bps` = `1000.0`
- `htf_mode` = `h12`
- `require_macd_turn` = `false`
- `require_body_dir` = `true`
- `max_aligned_funding_bps` = `1.0`
- `exit_kind` = `fixed`
- `tp_atr` = `0.75`
- `sl_atr` = `3.0`
- `trail_activation_atr` = `1.0`
- `trail_atr` = `1.25`
- `max_hold_bars` = `18`
- `cooldown_bars` = `3`
- `entry_delay_bars` = `1`
- `sizing_kind` = `fixed`
- `fixed_leverage` = `1.5`
- `risk_fraction` = `0.01`
- `max_leverage` = `1.5`

## 分片审计

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.66x` | `181.26%` | `-17.41%` | `95.65%` | `69` | `7.384` |
| `validation` | `2.08x` | `51.59%` | `-17.29%` | `95.00%` | `40` | `3.426` |
| `reused_holdout` | `0.70x` | `-8.53%` | `-15.69%` | `66.67%` | `6` | `0.398` |
| `full` | `2.07x` | `290.00%` | `-17.41%` | `93.91%` | `115` | `3.907` |
| `last_1d` | `1.00x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `last_7d` | `0.00x` | `-12.46%` | `-15.69%` | `33.33%` | `3` | `0.080` |
| `last_1m` | `0.34x` | `-8.53%` | `-15.69%` | `66.67%` | `6` | `0.398` |
| `last_3m` | `0.70x` | `-8.53%` | `-15.69%` | `66.67%` | `6` | `0.398` |
| `last_6m` | `1.03x` | `1.72%` | `-17.29%` | `86.96%` | `23` | `1.128` |
| `last_1y` | `1.60x` | `60.19%` | `-17.41%` | `92.31%` | `52` | `2.561` |

## Promotion 边界

- V2 不满足硬目标 `10x / 80% / <20% DD`，尤其 reused holdout 年化为 `0.70x` 且胜率降至 `66.67%`。
- 最近三个月不是新鲜 OOS；它已在 V1 登记时揭盲，因此不能作为 promotion 选择依据。
- 当前没有 SOL production runner、订单/仓位对账、重启恢复、missing-bar fail-closed、kill switch、tick/step rounding 回测与真实 stop-market 滑点证据。
- 禁止将 V2 标记为 candidate、paper-live、dry-run、handoff 或 live。

## 机器证据

- `artifacts/sol_1h_ar_high_win_search_2026-07-07.json`
- `artifacts/sol_1h_ar_high_win_prefit_2026-07-07.csv`
- `artifacts/sol_1h_ar_high_win_ranking_2026-07-07.csv`
- `artifacts/sol_1h_ar_high_win_slices_2026-07-07.csv`
- `artifacts/sol_1h_ar_high_win_top_trades_2026-07-07.csv`
- `scripts/research_sol_1h_ar_high_win_target_search.py`

