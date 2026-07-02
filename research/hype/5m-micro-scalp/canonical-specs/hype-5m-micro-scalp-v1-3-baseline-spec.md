# HYPE-5M-Micro-Scalp-V1.3 基线规格

Family id：`HYPE-5M-Micro-Scalp`

版本：`HYPE-5M-Micro-Scalp-V1.3`

父版本：`HYPE-5M-Micro-Scalp-V1.2`

状态：`paper-audit observation / not live-ready`

## 一句话定义

V1.3 是 V1.2 的精简登记版：保留 `vwap_revert` 下全部有效参数，剔除 V1.2 中 dormant 字段与等效关闭的 `min_adx` / `max_atr_pct_bps`。交易逻辑与 V1.2 一致，仅配置 schema 更干净。

## 相对 V1.2 剔除的字段

- dormant（`vwap_revert` 不使用）：`donchian, rsi_window, rsi_low, rsi_high, bb_z, pullback_bps, breakout_bps, min_dir_roc_bps, max_counter_roc_bps, wick_atr`。
- 等效关闭：`min_adx`、`max_atr_pct_bps`（引擎内部固定为不过滤）。

## 数据、执行与成本口径

- 市场：Binance HYPEUSDT perpetual `5m`。
- 数据范围：UTC `2025-05-30 10:30:00+00:00` 至 `2026-06-30 06:15:00+00:00`，共 `113998` 根 K。
- 数据质量：raw/normalized 各 `397` 个分区；missing、duplicate、关键空值、OHLC/VWAP/volume 违规均为 `0`；关键字段逐行一致。
- 信号：只使用已经收盘的 K 线。
- 入场：信号 K 后下一根 open，按方向加入 `4 bps` 不利滑点。
- 退出：入场后立即设置固定 TP/SL bracket；退出成交加入 `4 bps` 不利滑点。
- 同 K 同时触及 TP/SL：保守按 stop-first。
- gap 穿越 stop/target：按该 K open 市价成交。
- timeout：最长持仓结束后按下一根 open 退出。
- 手续费：`0.001` / fill；默认仓位 `1x`。

## V1.3 默认 1x 回测摘要

- trades：`180`；trades/day：`0.45`。
- annualized equity multiple：`1.76x`；全区间收益：`84.28%`。
- win：`85.00%`；PF：`1.934`；平均单笔：`34.96 bps`。
- maxDD：`-9.96%`；最差单笔：`-4.25%`。
- VAL PF：`5.081`；FWD PF：`10.245`。

## V1.3 参数总表（仅有效字段）

| 参数 | V1.3 值 | 说明 |
| --- | ---: | --- |
| `side_mode` | `both` | 多空双向。 |
| `ema_fast` | `21` | 快 EMA；趋势方向与距 EMA 过滤。 |
| `ema_slow` | `192` | 慢 EMA；`require_trend=true` 时决定多空允许方向。 |
| `ema_htf` | `192` | 高阶 EMA；`require_htf=true` 时要求价格同侧。 |
| `vwap_dev_bps` | `65.0` | 相对 vwap96 或 day_vwap 的偏离触发阈值（bps）。 |
| `max_chop` | `70.0` | Chop14 上限。 |
| `min_rvol` | `0.75` | RVOL96 下限。 |
| `min_atr_pct_bps` | `35.0` | ATR14 百分比下限。 |
| `max_dist_ema_bps` | `130.0` | 收盘价距 EMA21 最大偏离（bps）。 |
| `close_pos` | `0.76` | K 线收盘位置过滤；多头要求靠近上部，空头靠近下部。 |
| `require_trend` | `True` | 必须顺 EMA fast/slow 趋势。 |
| `require_htf` | `True` | 价格须在 HTF EMA 同方向一侧。 |
| `require_macd_turn` | `True` | MACD histogram 同向或转向。 |
| `require_body_dir` | `True` | 多头阳线、空头阴线。 |
| `tp_bps` | `110.0` | 固定止盈距离。 |
| `sl_bps` | `400.0` | 固定止损距离。 |
| `max_hold_bars` | `96` | 最长持仓 K 数。 |
| `cooldown_bars` | `48` | 平仓后冷却 K 数。 |

## 固定内核（不在 V1.3 配置表暴露）

- `entry_style=vwap_revert`
- `min_adx=0`、`max_atr_pct_bps=9999`（不过滤）
- dormant 引擎占位：`donchian/rsi/bb/pullback/breakout/roc/wick` 固定常量，不参与信号。

## 推进边界

V1.3 不改变 V1.2 的 live-executable 审计缺口；版本精简不等于 promotion。

## 关联产物

- 脚本：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_3_simplified_ablation.py`
- Config JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_3_baseline_config_2026-07-01.json`
- 消融：`research/hype/5m-micro-scalp/ablations/hype-5m-micro-scalp-v1-3-full-parameter-ablation-2026-07-01.md`
