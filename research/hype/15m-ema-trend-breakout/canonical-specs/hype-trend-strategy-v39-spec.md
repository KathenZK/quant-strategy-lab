# HYPE-EMA-TB-V39 可复现参数说明（观察候选）

日期：2026-07-08

本文档登记 `HYPE-EMA-Trend-Breakout-V39`。V39 来自 V35 全参数消融与最近 90 天微调中的候选 A（`v35_tuned_mild`），定位是 **V35 温和消融改进版**，不是 live-ready 版本。

## 版本身份

```text
V35 = V34 + max_hold_bars 192 -> 384，其余保持 live-realistic 口径。
V39 = V35 + long_vol_min 0.25 -> 0.35
          + short_target_atr_pct 0.018 -> 0.022
          + 移除冗余空头 1h EMA 确认
          + 保留 max_hold_bars=384 实盘 timeout 兜底
```

不要把本文档与 `HYPE-Candle-Count-Reversal` 的同名版本号混用。本文档只对应 Binance HYPEUSDT 永续 `15m` 的 `HYPE-EMA-TB` 趋势突破族。

## 数据与成本口径

| 项目 | 值 |
| --- | --- |
| 市场 | Binance USD-M 永续 |
| 标的 | `HYPE/USDT:USDT` |
| 周期 | `15m` |
| 数据窗口 | `2025-05-30 10:30 UTC` 至 `2026-07-08 05:30 UTC` |
| 数据质量 | 38765 根已闭合 K 线，缺口 0、重复 0、OHLCV 关键空值 0 |
| Funding | Binance funding，对齐持仓区间 |
| 成本 | `0.00085`/fill，表示手续费与 4 bps adverse slippage 合并口径，开平各一次 |

## 执行口径

```yaml
execution:
  signal_bar: K0 15m close
  entry_execution: K2 open
  entry_atr_source: K1 completed ATR672
  stop_take_execution: intrabar high/low, stop first
  indicator_timeout_exit: close confirmation, next bar open
  same_bar_reentry: false
  cooldown_bars: 0
```

## 指标参数

```yaml
features:
  ema_fast: 96
  ema_slow: 384
  adx_window: 28
  atr_window: 672
  volume_window: 192
  one_hour_adx_window: 21
  one_hour_ema_fast: 24
  one_hour_ema_slow: 96
  one_hour_alignment: 15m resample to 1h, shift(1), ffill
```

1h 指标必须只使用已完成的上一根 1h K，不允许使用当前未完成 1h bar。

## 入场规则

```yaml
entry:
  long:
    ema_spread_min: 0.0
    adx_min: 28
    volume_surge_min: 0.35
    one_hour_confirm:
      h1_adx21_gt: 18
      h1_plus_di_gt_h1_minus_di: true
  short:
    ema_spread_max: 0.0
    adx_min: 36
    volume_surge_min: 0.50
    one_hour_confirm: removed
  conflict: if long and short are both true, skip entry
  use_di_entry_filter: false
```

V39 删除的是空头 `h1_ema_spread < 0` 这一层 1h EMA 确认；15m 空头 `ema_spread < 0` 仍保留。消融显示两者单独移除均与 V35 逐字节一致，但两个同时移除会使 full 收益显著劣化，因此 V39 只删 1h 冗余确认。

## 仓位规则

```yaml
sizing:
  long_target_atr_pct: 0.020
  short_target_atr_pct: 0.022
  max_allocation: 3.0
  formula: allocation = min(max_allocation, target_atr_pct / entry_atr_pct)
  use_drawdown_scale: false
```

## 退出规则

```yaml
exits:
  take_profit_atr: 5.0
  hard_stop_atr: 7.0
  indicator_exit:
    type: adx_only
    adx_exit: 22
    delayed_bars: 3
    disable_after_mfe_atr: 1.5
  max_hold_bars: 384
  profit_floor: none
  trailing_stop: none
```

`max_hold_bars=384` 在当前样本中 0 触发，但实盘保留为异常兜底，不从 V39 规格中删除。

## 回测摘要

| 版本 | full收益 | full maxDD | Sharpe | 交易数 | full胜率 | 90d收益 | 90d maxDD | 90d胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V35 base | +8360.80% | -23.46% | 4.75 | 108 | 78.70% | +215.41% | -21.90% | 74.29% |
| V39 | +9969.45% | -23.46% | 4.81 | 107 | 79.44% | +217.53% | -21.90% | 77.14% |

标准分片验证：V39 在 `1d/7d/1m/3m/6m/1y/full` 所有窗口不劣于 V35；其中 1y 收益 `+11342.95%`，6m 收益 `+1802.57%`。

## 当前状态

- 状态：观察候选。
- 决策：按用户指定登记为 `HYPE-EMA-TB-V39`。
- live-readiness：未通过，不得标记为 live、paper-live、dry-run 或 handoff。
- 上线前 blocker：Hyperliquid/OKX 跨所同窗迁移检查、walk-forward 验证、订单时序审计、TP/SL reduce-only 挂单审计、重启恢复审计、缺失数据处理审计。

## 证据

- 研究报告：`../research-notes/hype-ema-tb-v35-full-ablation-recent-tune-2026-07-08.md`
- 空头放宽扫描：`../research-notes/hype-ema-tb-v35-short-relaxation-scan-2026-07-08.md`
- 复现脚本：`../scripts/research_hype_ema_tb_v35_full_ablation_recent_tune.py`
- 最终候选 JSON：`../artifacts/hype_ema_tb_v35_final_recent_tune_2026-07-08.json`
- 最终候选逐笔：`../artifacts/hype_ema_tb_v35_final_candidates_trades_2026-07-08.csv`
- 最终候选权益曲线：`../artifacts/hype_ema_tb_v35_final_candidates_equity_2026-07-08.csv`
