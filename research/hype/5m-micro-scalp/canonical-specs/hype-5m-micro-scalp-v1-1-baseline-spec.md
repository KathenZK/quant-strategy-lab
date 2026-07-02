# HYPE-5M-Micro-Scalp-V1.1 基线规格

Family id：`HYPE-5M-Micro-Scalp`

版本：`HYPE-5M-Micro-Scalp-V1.1`

源候选：`V1S_rand_016782__N00596`

状态：`paper-audit observation / not live-ready`

## 一句话定义

`HYPE-5M-Micro-Scalp-V1.1` 是 Binance HYPEUSDT perpetual `5m` 上的低频 VWAP 偏离均值回归版本。它继承 V1 的 `vwap_revert + require_trend=true` 核心，但将趋势尺度放慢到 EMA `21/192/384`，打开 HTF 与 MACD turn 过滤，并使用更宽的 `90/500 bps` TP/SL bracket。

## 数据、执行与成本口径

- 数据：Binance HYPEUSDT perpetual `5m` normalized OHLCV。
- 当前验证范围：`2025-05-30 10:30:00+00:00` 到 `2026-06-30 06:15:00+00:00`，`113998` 根 K。
- 数据质量：`0` missing bars；raw/normalized `open/high/low/close/volume/quote_volume/trade_count/vwap/is_closed` 逐字段一致。
- 信号：只使用已收盘 K。
- 入场：信号 K 后下一根 open 入场。
- 退出：入场后立即设置固定 TP/SL bracket。
- 同 K 同时触及 TP 与 SL：按 stop-first 保守成交。
- stop/target 被下一根 open 穿越：按 open 市价成交。
- timeout：超过最长持仓后按下一根 open 退出。
- 成本：fee `4.1466 bps/fill`，entry slippage `10.73 bps`，exit slippage `-2.64 bps`。

## 当前回测摘要

- trades：`182`；trades/day：`0.46`。
- annualized：`2.13x`；PF：`2.660`；win：`87.91%`。
- avg trade：`45.88 bps`；maxDD：`-8.06%`。
- VAL PF：`2.441`；FWD PF：`5.739`；recent30：`11.86%`。
- 负收益月份：`2`。

## V1.1 参数总表

| 参数 | V1.1 值 | 当前是否生效 | 说明 |
| --- | ---: | --- | --- |
| `side_mode` | `both` | 是 | 多空双向。 |
| `entry_style` | `vwap_revert` | 是 | VWAP 偏离均值回归入场。 |
| `ema_fast` | `21` | 是 | 快 EMA，用于趋势方向与距离过滤。 |
| `ema_slow` | `192` | 是 | 慢 EMA，多头要求 EMA21 > EMA192，空头要求 EMA21 < EMA192。 |
| `ema_htf` | `384` | 是 | `require_htf=true` 时要求价格相对 EMA384 同方向。 |
| `donchian` | `96` | 否 | 当前 `vwap_revert` 不使用。 |
| `rsi_window` | `7` | 否 | 当前 `vwap_revert` 不使用。 |
| `rsi_low` | `40.0` | 否 | 当前 `vwap_revert` 不使用。 |
| `rsi_high` | `76.0` | 否 | 当前 `vwap_revert` 不使用。 |
| `bb_z` | `1.75` | 否 | 当前 `vwap_revert` 不使用。 |
| `vwap_dev_bps` | `65.0` | 是 | VWAP 偏离触发阈值。 |
| `pullback_bps` | `100.0` | 否 | 当前 `vwap_revert` 不使用。 |
| `breakout_bps` | `10.0` | 否 | 当前 `vwap_revert` 不使用。 |
| `min_dir_roc_bps` | `70.0` | 否 | 当前 `vwap_revert` 不使用。 |
| `max_counter_roc_bps` | `260.0` | 否 | 当前 `vwap_revert` 不使用。 |
| `min_adx` | `10.0` | 是 | ADX14 下限。 |
| `max_chop` | `62.0` | 是 | Chop14 上限。 |
| `min_rvol` | `1.0` | 是 | 相对成交量下限。 |
| `min_atr_pct_bps` | `35.0` | 是 | ATR14 百分比下限。 |
| `max_atr_pct_bps` | `350.0` | 是 | ATR14 百分比上限。 |
| `max_dist_ema_bps` | `130.0` | 是 | 收盘价距离 EMA21 的最大偏离。 |
| `wick_atr` | `1.4` | 否 | 当前 `vwap_revert` 不使用。 |
| `close_pos` | `0.76` | 是 | 多头要求收盘靠近 K 线上部，空头要求靠近下部。 |
| `require_trend` | `true` | 是 | 多空必须顺 EMA21/EMA192 趋势方向。 |
| `require_htf` | `true` | 是 | 要求价格相对 EMA384 同方向。 |
| `require_macd_turn` | `true` | 是 | 要求 MACD histogram 同向或转向。 |
| `require_body_dir` | `true` | 是 | 多头阳线、空头阴线。 |
| `tp_bps` | `90.0` | 是 | 固定止盈距离。 |
| `sl_bps` | `500.0` | 是 | 固定止损距离。 |
| `max_hold_bars` | `96` | 是 | 最长持仓 `96` 根 `5m` K。 |
| `cooldown_bars` | `48` | 是 | 平仓后冷却 `48` 根 `5m` K。 |

## 信号逻辑

- 多头方向：`side_mode != short`，`EMA21 > EMA192`，`close > EMA384`，并满足通用过滤。
- 空头方向：`side_mode != long`，`EMA21 < EMA192`，`close < EMA384`，并满足通用过滤。
- 多头入场：`vwap96_dev_bps <= -65` 或 `day_vwap_dev_bps <= -65`，且 `close_pos >= 0.76`。
- 空头入场：`vwap96_dev_bps >= 65` 或 `day_vwap_dev_bps >= 65`，且 `close_pos <= 0.24`。
- 通用过滤：`ADX14 >= 10`、`chop14 <= 62`、`rvol96 >= 1.0`、`35 <= atr_pct_bps <= 350`、`abs(close / EMA21 - 1) * 10000 <= 130`。
- `require_macd_turn=true`：多头要求 `macd_hist_delta > 0` 或 `macd_hist > 0`；空头相反。
- `require_body_dir=true`：多头要求 `close > open`，空头要求 `close < open`。
- 连续相同方向信号只保留第一根，避免密集重复信号。

## 全参数消融发现

V1.1 全参数 one-at-a-time 消融共 `103` 组。完全无影响参数组为：

- `bb_z`
- `breakout_bps`
- `min_dir_roc_bps`
- `max_counter_roc_bps`
- `pullback_bps`
- `rsi_high`
- `rsi_low`
- `donchian`
- `rsi_window`
- `wick_atr`

这些字段不是“参数值刚好不敏感”，而是在当前 `entry_style=vwap_revert` 下不参与信号。后续调参应集中在 EMA slow/HTF、VWAP 偏离、ADX/chop/rvol/ATR、EMA 距离、close position、HTF/MACD/body、TP/SL、hold/cooldown。

## 微调后的观察行

V1.1 全参数消融后的组合微调搜索评估 `44001` 组配置，找到 `2` 个 strict-improve rows。当前优先后续观察行是 `V1.1_tune_grid_004895`：

- trades：`178`；trades/day：`0.45`。
- annualized：`2.27x`；PF：`2.419`；win：`84.83%`。
- avg trade：`51.12 bps`；maxDD：`-7.75%`。
- VAL PF：`6.348`；FWD PF：`12.838`；recent30：`12.55%`。
- 参数差异：`ema_htf=192`、`min_adx=0`、`max_chop=70`、`min_rvol=0.75`、`max_atr_pct_bps=9999`、`tp_bps=110`、`sl_bps=400`。

该微调行在 2026-07-01 按用户要求正式登记为 `HYPE-5M-Micro-Scalp-V1.2`。版本登记不改变 promotion 边界；V1.2 仍是 paper-audit observation，不是 live-ready。

## 推进边界

`HYPE-5M-Micro-Scalp-V1.1` 不能直接实盘：

- 尚未完成逐笔路径图审计，尤其是同 K TP/SL、gap target/stop 与 timeout 的实际可维护性。
- 尚未完成 bracket order maintenance、restart recovery、状态机复现和 paper/live-dry-run reconciliation。
- 频率仍只有约 `0.46` 笔/天，不是原始 `3-5` 笔/天 micro-scalp 目标。
- VAL/FWD 曾参与前序搜索和稳健性筛选，不能当作完全独立 OOS。

## 关联报告与产物

- V1 simplified combo：`research/hype/5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-simplified-combo-search-2026-06-30.md`
- V1 simplified candidate robustness：`research/hype/5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-simplified-candidate-robustness-2026-06-30.md`
- V1.1 full ablation：`research/hype/5m-micro-scalp/ablations/hype-5m-micro-scalp-v1-1-full-parameter-ablation-2026-06-30.md`
- V1.1 micro tune：`research/hype/5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-1-micro-tune-2026-06-30.md`
- V1.2 baseline spec：`research/hype/5m-micro-scalp/canonical-specs/hype-5m-micro-scalp-v1-2-baseline-spec.md`
- Repro script：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_1_ablation_and_tuning.py`
