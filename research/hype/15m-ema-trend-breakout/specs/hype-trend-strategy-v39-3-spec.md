# HYPE-EMA-TB-V39.3 冻结参数说明

日期：2026-07-17  
状态：`registered / not promoted / not live-ready`

本文档登记 `HYPE-EMA-Trend-Breakout-V39.3`。V39.3 是 V39.2 的防守型固定 bracket 变体：入场、仓位、cooldown1 与指标退出状态机全部不变，只把 entry-anchored 硬止损从 `7ATR` 收窄到 `6.75ATR`，并把固定止盈从 `5ATR` 收窄到 `4.8ATR`。

## 版本身份

```text
V39.2 = V39
      + long_vol_min 0.35 -> 0.25
      + cooldown_bars 0 -> 1

V39.3 = V39.2
      + hard_stop_atr 7.0 -> 6.75
      + take_profit_atr 5.0 -> 4.8
```

V39.3 不包含 V37/V39.1 early-long 卫星，不包含 V38 profit floor，也不采用 `MFE>=1.5ATR` 后再动态收紧至 `5ATR` 的已否决规则。

## 数据与成本

| 项目 | 冻结值 |
| --- | --- |
| 市场 | Binance USD-M perpetual |
| 标的 | `HYPE/USDT:USDT` |
| 周期 | `15m` |
| 回测数据窗口 | `2025-05-30 10:30 UTC` 至 `2026-07-17 08:45 UTC` |
| 数据质量 | `39,642` 根已闭合 K；缺口、重复、关键空值、OHLC 违规、raw/normalized 差异均为 0 |
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
  take_profit_atr: 4.8
  hard_stop_atr: 6.75
  intrabar_conflict: stop_first
  adx_exit: 22
  delayed_bars: 3
  disable_indicator_exit_after_mfe_atr: 1.5
  max_hold_bars: 384
  trailing_stop: none
  profit_floor: none
```

TP/SL 使用入场时冻结的 K1 `ATR672`，从开仓起固定，不随 MFE 动态移动。指标退出在收盘确认，下一根 open 成交。若 bar open 已越过硬止损，执行审计按更差的 open 成交；否则按 stop 价成交。样本内 gap-open 对照与原回测 equity 最大差异为 `0`。

忽略费用、funding 与 3x cap 时，完整止损/止盈距离比为 `6.75/4.8 = 1.40625`；V39.3 的目标是减少近 TP5 回吐，不是改善理论盈亏比。

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
| `1d` | `+8.85%` | `-4.87%` | `2` |
| `7d` | `+8.30%` | `-10.06%` | `5` |
| `1m` | `+12.69%` | `-18.59%` | `8` |
| `3m` | `+164.51%` | `-20.57%` | `35` |
| `6m` | `+1553.29%` | `-22.47%` | `70` |
| `1y` | `+6840.42%` | `-22.79%` | `106` |
| `full` | `+7680.24%` | `-22.88%` | `114` |

Full Sharpe `4.47`，胜率 `78.07%`（`89/114`），多单 `87` 笔、空单 `27` 笔；退出为 TP `87`、SL `16`、indicator exit `11`。同窗口 V39.2 为 `+9729.16% / -24.61% / Sharpe 4.72 / 109 笔 / 胜率 79.82%`。

回测终点仍有一笔 V39.3 空单：`2026-07-17 08:00 UTC` 入场，终点仅用于 mark-to-market，不计入上述 `114` 笔平仓数。

## 登记理由与门禁

- 主状态：`registered`。
- 角色：V39.2 的近止盈回吐防守版本，以长期收益让渡换取较低 full/近期回撤。
- 登记依据：两次近 TP5 回吐事件分别达到 `4.829929ATR` 和 `4.990884ATR`；`TP4.8` 均能在原规则回吐前退出。
- `not promoted / not live-ready`：参数由同一 full 样本及已知近期事件选择，第二个事件只是补齐数据窗口，不是严格时间前推 OOS。
- 已知敏感性：固定 `SL6.75` 时，`TP4.75/4.80/4.85` 的 full 路径差异显著；固定 TP 会改变 cooldown1 后的再入场链。
- 尚缺：独立 OOS、walk-forward/CPCV、Monte Carlo、压力测试、entry phase/bar-alignment 敏感性、跨所迁移与 live-executable 审计。
- 不创建 V39.3 live spec，不修改任何 runner、active manifest 或生产配置。

## 证据

- 组合诊断：[hype-ema-tb-v39-2-sl675-tp48-2026-07-17.md](../diagnostics/hype-ema-tb-v39-2-sl675-tp48-2026-07-17.md)
- 静态止损扫描：[hype-ema-tb-v39-2-static-stop-scan-2026-07-17.md](../diagnostics/hype-ema-tb-v39-2-static-stop-scan-2026-07-17.md)
- 复现脚本：[research_hype_ema_tb_v39_2_sl675_tp48.py](../scripts/research_hype_ema_tb_v39_2_sl675_tp48.py)
- 汇总 JSON：[hype_ema_tb_v39_2_sl675_tp48_2026-07-17.json](../artifacts/hype_ema_tb_v39_2_sl675_tp48_2026-07-17.json)
- 逐笔交易：[hype_ema_tb_v39_2_sl675_tp48_2026-07-17_trades.csv](../artifacts/hype_ema_tb_v39_2_sl675_tp48_2026-07-17_trades.csv)
- 权益曲线：[hype_ema_tb_v39_2_sl675_tp48_2026-07-17_equity.csv](../artifacts/hype_ema_tb_v39_2_sl675_tp48_2026-07-17_equity.csv)
