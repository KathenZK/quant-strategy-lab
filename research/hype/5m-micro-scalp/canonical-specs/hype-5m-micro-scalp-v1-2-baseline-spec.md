# HYPE-5M-Micro-Scalp-V1.2 基线规格

Family id：`HYPE-5M-Micro-Scalp`

版本：`HYPE-5M-Micro-Scalp-V1.2`

源观察行：`V1.1_tune_grid_004895`

状态：`paper-audit observation / not live-ready`

## 一句话定义

`HYPE-5M-Micro-Scalp-V1.2` 是 V1.1 有效参数微调后的低频 VWAP 偏离均值回归版本。相对 V1.1，它将 HTF EMA 从 `384` 收紧到 `192`，放宽 ADX、Chop、RVOL 与 ATR 上限过滤，并把固定 TP/SL 从 `90/500 bps` 调整为 `110/400 bps`。

## 版本身份

- 2026-06-30 的 V1.1 微调搜索将本参数组记录为 `V1.1_tune_grid_004895`。
- 2026-07-01 用户明确要求将该观察行登记为 `HYPE-5M-Micro-Scalp-V1.2`。
- 版本登记只固定参数、成本和默认敞口口径，不表示 live、paper-live、dry-run、handoff 或实盘批准。
- 默认账户敞口为 `1x`；`2x/3x` 只保留为压力测试，不属于 V1.2 默认仓位。

## 数据、执行与成本口径

- 市场：Binance HYPEUSDT perpetual。
- 周期：`5m`。
- 数据范围：UTC `2025-05-30 10:30:00+00:00` 至 `2026-06-30 06:15:00+00:00`，共 `113998` 根 K。
- 数据质量：raw/normalized 各 `397` 个分区；missing、duplicate、关键空值、OHLC/VWAP/volume 违规均为 `0`；关键字段逐行一致。
- 信号：只使用已经收盘的 K 线。
- 入场：信号 K 后下一根 open，按方向加入 `4 bps` 不利滑点。
- 退出：入场后立即设置固定 TP/SL bracket；退出成交加入 `4 bps` 不利滑点。
- 同 K 同时触及 TP/SL：保守按 stop-first。
- gap 穿越 stop/target：按该 K open 市价成交，不使用旧 stop/target 价。
- timeout：最长持仓结束后按下一根 open 退出。
- 手续费：`0.001` / fill，即每次成交按名义价值计 `10 bps`，完整进出约 `20 bps`。
- 默认仓位：每笔名义价值等于当时账户权益，即 `1x` 敞口；一次只持有一个仓位并逐笔复利。
- 未计 funding；未模拟 Binance maintenance margin 与强平价格。

## V1.2 默认 1x 回测摘要

- trades：`180`；trades/day：`0.45`。
- annualized equity multiple：`1.76x`；全区间收益：`84.28%`。
- win：`85.00%`；PF：`1.934`；平均单笔账户收益：`34.96 bps`。
- maxDD：`-9.96%`；最差单笔账户收益：`-4.25%`。
- train：annualized `1.51x`，PF `1.532`，maxDD `-9.96%`。
- VAL：annualized `2.21x`，PF `5.081`，maxDD `-4.89%`。
- FWD：区间收益 `10.55%`，PF `10.245`，maxDD `-3.14%`，但只有 `14` 笔。
- 负收益月份：`1`；最差月：`-1.40%`。

## 杠杆压力测试

| 杠杆 | 年化资金倍数 | 全区间收益 | maxDD | 最差单笔账户收益 | 定位 |
| ---: | ---: | ---: | ---: | ---: | --- |
| `1x` | `1.76x` | `84.28%` | `-9.96%` | `-4.25%` | V1.2 默认 paper-audit 敞口 |
| `2x` | `2.98x` | `227.11%` | `-19.90%` | `-8.49%` | aggressive research stress |
| `3x` | `4.89x` | `458.10%` | `-29.67%` | `-12.74%` | aggressive research stress |

杠杆按 `account return = leverage * net_ret_1x` 计算，同时放大价格盈亏、手续费、滑点和持仓内 MAE。该表不是实盘仓位建议。

## V1.2 参数总表

| 参数 | V1.2 值 | 当前是否生效 | 说明 |
| --- | ---: | --- | --- |
| `side_mode` | `both` | 是 | 多空双向。 |
| `entry_style` | `vwap_revert` | 是 | VWAP 偏离均值回归入场。 |
| `ema_fast` | `21` | 是 | 快 EMA，用于趋势方向与距离过滤。 |
| `ema_slow` | `192` | 是 | 多头要求 EMA21 > EMA192，空头相反。 |
| `ema_htf` | `192` | 是 | `require_htf=true` 时要求价格相对 EMA192 同方向。 |
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
| `min_adx` | `0.0` | 是但等效关闭 | ADX14 下限为 0，不再形成实际过滤。 |
| `max_chop` | `70.0` | 是 | Chop14 上限。 |
| `min_rvol` | `0.75` | 是 | RVOL96 下限。 |
| `min_atr_pct_bps` | `35.0` | 是 | ATR14 百分比下限。 |
| `max_atr_pct_bps` | `9999.0` | 是但等效关闭 | ATR14 百分比上限，不形成实际过滤。 |
| `max_dist_ema_bps` | `130.0` | 是 | 收盘价距离 EMA21 的最大偏离。 |
| `wick_atr` | `1.4` | 否 | 当前 `vwap_revert` 不使用。 |
| `close_pos` | `0.76` | 是 | 多头要求收盘靠近 K 线上部，空头要求靠近下部。 |
| `require_trend` | `true` | 是 | 多空必须顺 EMA21/EMA192 趋势方向。 |
| `require_htf` | `true` | 是 | 价格必须位于 EMA192 的同方向一侧。 |
| `require_macd_turn` | `true` | 是 | MACD histogram 必须同向或转向。 |
| `require_body_dir` | `true` | 是 | 多头阳线、空头阴线。 |
| `tp_bps` | `110.0` | 是 | 固定止盈距离。 |
| `sl_bps` | `400.0` | 是 | 固定止损距离。 |
| `max_hold_bars` | `96` | 是 | 最长持仓 `96` 根 `5m` K。 |
| `cooldown_bars` | `48` | 是 | 平仓后冷却 `48` 根 `5m` K。 |

## 精确信号逻辑

- 多头方向：`EMA21 > EMA192`，`close > EMA192`，并满足通用过滤。
- 空头方向：`EMA21 < EMA192`，`close < EMA192`，并满足通用过滤。
- 多头入场：`vwap96_dev_bps <= -65` 或 `day_vwap_dev_bps <= -65`，且 `close_pos >= 0.76`。
- 空头入场：`vwap96_dev_bps >= 65` 或 `day_vwap_dev_bps >= 65`，且 `close_pos <= 0.24`。
- 通用过滤：`chop14 <= 70`、`rvol96 >= 0.75`、`atr_pct_bps >= 35`、`abs(close / EMA21 - 1) * 10000 <= 130`。
- `require_macd_turn=true`：多头要求 `macd_hist_delta > 0` 或 `macd_hist > 0`；空头要求相反条件。
- `require_body_dir=true`：多头要求 `close > open`；空头要求 `close < open`。
- 连续相同方向信号只保留第一根；持仓与冷却期间的新信号不执行。

## 相对 V1.1 的变化

| 参数 | V1.1 | V1.2 |
| --- | ---: | ---: |
| `ema_htf` | `384` | `192` |
| `min_adx` | `10.0` | `0.0` |
| `max_chop` | `62.0` | `70.0` |
| `min_rvol` | `1.0` | `0.75` |
| `max_atr_pct_bps` | `350.0` | `9999.0` |
| `tp_bps` | `90.0` | `110.0` |
| `sl_bps` | `500.0` | `400.0` |

在用户指定成本下，V1.2 的 `1x` 收益高于 V1.1，但 maxDD 为 `-9.96%`，略深于 V1.1 的 `-9.84%`，因此 V1.2 不是 V1.1 的全指标严格替代。

## 推进边界

`HYPE-5M-Micro-Scalp-V1.2` 不能直接实盘：

- 尚未完成逐笔路径图审计，尤其是同 K TP/SL、gap target/stop 与 timeout 的实际可维护性。
- 尚未完成 bracket order maintenance、restart recovery、状态机复现和 paper/live-dry-run reconciliation。
- 尚未纳入 funding、maintenance margin、强平价格和真实下单数量精度。
- FWD 仅 `14` 笔，且 VAL/FWD 已参与前序筛选，不能视为干净独立 OOS。
- 频率约 `0.45` 笔/天，仍不满足原始 `3-5` 笔/天目标。

## 关联报告与产物

- V1.1 micro tune：`research/hype/5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-1-micro-tune-2026-06-30.md`
- V1.2 registration and leverage retest：`research/hype/5m-micro-scalp/research-notes/hype-5m-micro-scalp-v1-2-registration-and-leverage-retest-2026-07-01.md`
- Repro script：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_2_registration_and_leverage_retest.py`
- Config JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_2_baseline_config_2026-07-01.json`
