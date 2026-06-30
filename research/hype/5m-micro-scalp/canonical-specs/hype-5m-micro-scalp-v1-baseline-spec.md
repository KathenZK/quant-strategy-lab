# HYPE-5M-Micro-Scalp-V1 基线规格

Family id：`HYPE-5M-Micro-Scalp`

版本：`HYPE-5M-Micro-Scalp-V1`

源候选：`R1_relax_frequency_R01242__tp_sl_0011`

状态：`paper-audit candidate only / not live-ready`

## 一句话定义

`HYPE-5M-Micro-Scalp-V1` 是 Binance HYPEUSDT perpetual `5m` 上的低频 VWAP 偏离均值回归策略：当价格相对滚动 VWAP 或日内 VWAP 偏离达到阈值，并且趋势、波动、成交量与 K 线收盘位置过滤通过时，下一根 open 双向入场，立即挂固定 TP/SL bracket。

## 来源与历史指标

本 V1 基线来自 relaxed-frequency robustness sweep 的最佳平衡候选。完整参数来自历史提交 `c94dcac` 中已移除的 artifact 行：

- `research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_candidate_robustness_summary_2026-06-26.csv`
- 行名：`R1_relax_frequency_R01242__tp_sl_0011`

历史回测摘要：

- 交易数：`188`；频率：`0.48` 笔/天。
- 年化倍数：`1.32x`；总收益：`35.13%`。
- 胜率：`85.11%`；PF：`1.468`；平均单笔：`16.67 bps`。
- 最大回撤：`-8.16%`；负收益月份：`3/14`。
- VAL PF：`5.445`；FWD PF：`3.550`；recent 30d：`10.46%`。
- 多单 `95` 笔，空单 `93` 笔；平均持仓 `16.89` 根 `5m` K。

## 固定执行与成本口径

- 数据：Binance HYPEUSDT perpetual `5m` normalized OHLCV。
- 信号：只使用已收盘 K。
- 入场：信号 K 后下一根 open 入场。
- 退出：入场后立即设置固定 TP/SL bracket。
- 同 K 同时触及 TP 与 SL：按 stop-first 保守成交。
- stop/target 被下一根 open 穿越：按 open 市价成交。
- timeout：超过最长持仓后按下一根 open 退出。
- 成本：fee `4.1466 bps/fill`，entry slippage `10.73 bps`，exit slippage `-2.64 bps`。

## V1 参数总表

| 参数 | V1 值 | 是否在当前 `vwap_revert` 中生效 | 作用 |
| --- | ---: | --- | --- |
| `side_mode` | `both` | 是 | 允许多空双向信号；多空分别还要通过趋势/过滤条件。 |
| `entry_style` | `vwap_revert` | 是 | 入场风格：价格偏离 `vwap96` 或 `day_vwap` 后做均值回归。 |
| `ema_fast` | `21` | 是 | 快 EMA；用于趋势方向、距 EMA 过滤。 |
| `ema_slow` | `96` | 是 | 慢 EMA；当 `require_trend=true` 时决定多空允许方向。 |
| `ema_htf` | `384` | 部分 | 高阶 EMA；当前 `require_htf=false`，不限制方向，但仍作为可消融上下文参数保留。 |
| `donchian` | `96` | 否 | Donchian breakout 风格使用；当前 `vwap_revert` 不使用。 |
| `rsi_window` | `7` | 否 | RSI snapback 风格使用；当前 `vwap_revert` 不使用。 |
| `rsi_low` | `40.0` | 否 | 多头 RSI 超卖阈值；当前 `vwap_revert` 不使用。 |
| `rsi_high` | `76.0` | 否 | 空头 RSI 超买阈值；当前 `vwap_revert` 不使用。 |
| `bb_z` | `1.75` | 否 | Bollinger z-score 反转阈值；当前 `vwap_revert` 不使用。 |
| `vwap_dev_bps` | `75.0` | 是 | VWAP 偏离触发阈值；多头要求偏离小于等于 `-75 bps`，空头要求大于等于 `+75 bps`。 |
| `pullback_bps` | `100.0` | 否 | EMA reclaim/pullback 风格使用；当前 `vwap_revert` 不使用。 |
| `breakout_bps` | `10.0` | 否 | micro-breakout 风格使用；当前 `vwap_revert` 不使用。 |
| `min_dir_roc_bps` | `70.0` | 否 | momentum-pause 风格的顺势动量阈值；当前 `vwap_revert` 不使用。 |
| `max_counter_roc_bps` | `260.0` | 否 | wick-reject/momentum-pause 风格的反向动量限制；当前 `vwap_revert` 不使用。 |
| `min_adx` | `14.0` | 是 | 趋势强度下限；ADX14 低于该值不交易。 |
| `max_chop` | `48.0` | 是 | 震荡度上限；chop14 高于该值不交易。 |
| `min_rvol` | `0.75` | 是 | 相对成交量下限；`volume / rolling96(volume)` 太低不交易。 |
| `min_atr_pct_bps` | `35.0` | 是 | ATR14 百分比下限；波动太小不交易。 |
| `max_atr_pct_bps` | `9999.0` | 是 | ATR14 百分比上限；当前近似关闭高波动上限。 |
| `max_dist_ema_bps` | `260.0` | 是 | 收盘价距离 EMA21 的最大偏离；避免离快 EMA 太远后追入。 |
| `wick_atr` | `1.4` | 否 | wick-reject 风格使用；当前 `vwap_revert` 不使用。 |
| `close_pos` | `0.70` | 是 | K 线收盘位置过滤；多头需收在区间上部，空头需收在区间下部。 |
| `require_trend` | `true` | 是 | 多头只允许 EMA21 > EMA96，空头只允许 EMA21 < EMA96。 |
| `require_htf` | `false` | 是 | 是否要求价格站在 EMA384 同方向；当前关闭。 |
| `require_macd_turn` | `false` | 是 | 是否要求 MACD histogram 同向或转向；当前关闭。 |
| `require_body_dir` | `true` | 是 | 多头要求阳线收盘，空头要求阴线收盘。 |
| `tp_bps` | `67.5` | 是 | 固定止盈距离；约 `0.675%`。 |
| `sl_bps` | `275.0` | 是 | 固定止损距离；约 `2.75%`。 |
| `max_hold_bars` | `96` | 是 | 最长持仓 `96` 根 `5m` K，约 `8` 小时。 |
| `cooldown_bars` | `36` | 是 | 平仓后冷却 `36` 根 `5m` K，约 `3` 小时，避免连续进场。 |

## 信号逻辑

先计算多空允许方向：

- `side_mode=both` 允许多空。
- `require_trend=true` 后，多头要求 `EMA21 > EMA96`，空头要求 `EMA21 < EMA96`。
- `require_htf=false`，所以不要求价格相对 `EMA384` 同向。

然后计算 `vwap_revert` 入场：

- 多头：`vwap96_dev_bps <= -75` 或 `day_vwap_dev_bps <= -75`，且 `close_pos >= 0.70`。
- 空头：`vwap96_dev_bps >= 75` 或 `day_vwap_dev_bps >= 75`，且 `close_pos <= 0.30`。
- 再叠加 common filters：`ADX14 >= 14`、`chop14 <= 48`、`rvol96 >= 0.75`、`35 <= atr_pct_bps <= 9999`、`abs(close / EMA21 - 1) * 10000 <= 260`。
- 因 `require_body_dir=true`，多头要求 `close > open`，空头要求 `close < open`。
- 连续相同方向信号只保留第一根，避免密集重复信号。

## 风险与推进边界

V1 只能作为 paper-audit baseline，不能直接实盘：

- 尚未完成逐笔路径图审计，尤其需要检查 stop/target 同 K、gap stop 与 timeout 的实际可维护性。
- 尚未完成订单维护、重启恢复、状态机复现和 live dry-run reconciliation。
- 样本频率只有约 `0.48` 笔/天，FWD 样本仅 `19` 笔，统计显著性不足。
- 该策略盈利来自低频严格过滤和宽止损高胜率结构，不是原始 `3-5` 笔/天 micro-profit 目标。

## 关联报告

- Relaxed rounds：`research/hype/5m-micro-scalp/diagnostics/hype-5m-micro-scalp-relaxed-rounds-2026-06-26.md`
- Candidate robustness：`research/hype/5m-micro-scalp/diagnostics/hype-5m-micro-scalp-candidate-robustness-2026-06-26.md`
- Full parameter ablation：`research/hype/5m-micro-scalp/ablations/hype-5m-micro-scalp-v1-full-parameter-ablation-2026-06-29.md`
- Repro script：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_full_ablation.py`
