# HYPE-EMA-TB-V39.2 冻结参数说明

日期：2026-07-17  
状态：`registered / not promoted / not live-ready`

本文档登记 `HYPE-EMA-Trend-Breakout-V39.2`。V39.2 是 V39 的再入场状态机变体：多头量能门槛回到 V35 的 `0.25`，并在每次平仓后冷却 1 根 `15m` K；V39 的空头仓位目标和空头确认精简保持不变。

## 版本身份

```text
V39 = V35
    + long_vol_min 0.25 -> 0.35
    + short_target_atr_pct 0.018 -> 0.022
    + 移除空头 1h EMA 确认

V39.2 = V39
      + long_vol_min 0.35 -> 0.25
      + cooldown_bars 0 -> 1
```

`HYPE-EMA-TB-V39.1` 已用于 V39 + V37 early-long 卫星组合；V39.2 不含卫星腿，两者不是递进覆盖关系。

## 数据与成本

| 项目 | 冻结值 |
| --- | --- |
| 市场 | Binance USD-M perpetual |
| 标的 | `HYPE/USDT:USDT` |
| 周期 | `15m` |
| 回测数据窗口 | `2025-05-30 10:30 UTC` 至 `2026-07-16 15:30 UTC` |
| 数据质量 | `39,573` 根已闭合 K；缺口、重复、关键空值、raw/normalized 差异均为 0 |
| Funding | Binance funding，对齐持仓区间 |
| 成本 | 每次 fill `0.00085`，开仓和平仓分别计入 |

## 指标与入场参数

```yaml
features:
  ema_fast: 96
  ema_slow: 384
  adx_window: 28
  volume_window: 192
  atr_window: 672
  h1_adx_window: 21
  h1_ema_fast: 24
  h1_ema_slow: 96
  h1_alignment: resample 15m to 1h, shift(1), forward-fill

entry:
  long:
    ema_spread_gt: 0.0
    adx_min: 28
    volume_surge_min: 0.25
    h1_adx_gt: 18
    h1_plus_di_gt_h1_minus_di: true
  short:
    ema_spread_lt: 0.0
    adx_min: 36
    volume_surge_min: 0.50
    h1_ema_confirm: removed
  conflict: skip when long and short are both true
```

`volume_surge = volume / rolling_mean(volume, 192) - 1`。1h 指标只使用已完成的上一根 1h K。

## 仓位与退出

```yaml
sizing:
  long_target_atr_pct: 0.020
  short_target_atr_pct: 0.022
  max_allocation: 3.0
  allocation: min(3.0, target_atr_pct / entry_atr_pct)

exits:
  take_profit_atr: 5.0
  hard_stop_atr: 7.0
  intrabar_conflict: stop_first
  adx_exit: 22
  delayed_bars: 3
  disable_indicator_exit_after_mfe_atr: 1.5
  max_hold_bars: 384
  trailing_stop: none
  profit_floor: none
```

TP/SL 使用入场时冻结的 K1 `ATR672`。指标退出在收盘确认，下一根 open 成交。

## 执行与冷却状态机

```yaml
execution:
  signal_bar: K0 close
  entry_bar: K2 open
  entry_atr_source: completed K1 ATR672
  same_bar_reentry: false
  cooldown_bars: 1
```

若在 bar `E` 平仓：

1. `E` 同 bar 不得重新开仓；
2. `E+1` 完整禁止开仓；
3. 最早允许在 `E+2 open` 按正常 K0/K1/K2 信号与过滤条件开仓。

冷却只限制新开仓，不改变持仓中的 TP、SL、funding、指标退出或 timeout。

## 冻结回测

| 窗口 | 收益 | MaxDD | 平仓数 |
| --- | ---: | ---: | ---: |
| `1d` | `+0.12%` | `-2.88%` | `1` |
| `7d` | `-15.28%` | `-22.94%` | `2` |
| `1m` | `-13.39%` | `-23.40%` | `6` |
| `3m` | `+96.81%` | `-24.61%` | `30` |
| `6m` | `+1249.11%` | `-24.61%` | `65` |
| `1y` | `+8455.56%` | `-24.61%` | `101` |
| `full` | `+8922.26%` | `-24.61%` | `108` |

Full Sharpe `4.66`，胜率 `79.63%`（`86/108`），多单 `84` 笔、空单 `24` 笔。相同延长窗口当前 V39 为 `+8430.39% / -27.26% / Sharpe 4.57 / 109 笔 / 胜率 77.98%`。

## 状态与门禁

- 主状态：`registered`。
- 角色：联合参数/状态机观察版本。
- `not promoted / not live-ready`：本轮是在同一 full 样本上选出的 cooldown 尖峰，最近 `3m/6m` 收益低于当前 V39。
- 尚缺：独立 OOS、walk-forward/CPCV、Monte Carlo、压力测试、entry phase/bar-alignment 敏感性、跨所迁移与 live-executable 审计。
- 不创建 V39.2 live spec，不修改任何 runner 或 active manifest。

## 证据

- 联合诊断：[hype-ema-tb-v39-long-vol025-cooldown1-2026-07-17.md](../diagnostics/hype-ema-tb-v39-long-vol025-cooldown1-2026-07-17.md)
- 复现脚本：[research_hype_ema_tb_v39_long_vol025_cooldown1.py](../scripts/research_hype_ema_tb_v39_long_vol025_cooldown1.py)
- 汇总 JSON：[hype_ema_tb_v39_long_vol025_cooldown1_2026-07-17.json](../artifacts/hype_ema_tb_v39_long_vol025_cooldown1_2026-07-17.json)
- 逐笔交易：[hype_ema_tb_v39_long_vol025_cooldown1_2026-07-17_trades.csv](../artifacts/hype_ema_tb_v39_long_vol025_cooldown1_2026-07-17_trades.csv)
- 权益曲线：[hype_ema_tb_v39_long_vol025_cooldown1_2026-07-17_equity.csv](../artifacts/hype_ema_tb_v39_long_vol025_cooldown1_2026-07-17_equity.csv)
