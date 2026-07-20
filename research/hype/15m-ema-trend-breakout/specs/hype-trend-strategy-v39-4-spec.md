# HYPE-EMA-TB-V39.4 冻结参数说明

日期：2026-07-17  
状态：`registered / not promoted / not live-ready`

本文档登记 `HYPE-EMA-Trend-Breakout-V39.4`。V39.4 是 V39.2 的空头分批止盈变体：入场、仓位、TP5/SL7、指标退出与 cooldown1 全部不变；空单盘中达到 `4.4 × entry ATR672` 时，一次性 reduce-only 平掉初始仓位的 `75%`，剩余 `25%` 继续原状态机。

## 版本身份

```text
V39.2 = V39
      + long_vol_min 0.35 -> 0.25
      + cooldown_bars 0 -> 1

V39.4 = V39.2
      + short partial trigger 4.4ATR
      + short partial fraction 75%
      + remaining fraction 25% keeps TP5/SL7
```

V39.4 不是 V39.3 的后继 bracket：它保留 V39.2 的 `TP5/SL7`，不采用 V39.3 的 `TP4.8/SL6.75`。它不包含 V37/V39.1 early-long 卫星或 V38 profit floor。

## 数据与成本

| 项目 | 冻结值 |
| --- | --- |
| 市场 | Binance USD-M perpetual |
| 标的 | `HYPE/USDT:USDT` |
| 周期 | `15m` |
| 回测数据窗口 | `2025-05-30 10:30 UTC` 至 `2026-07-17 08:45 UTC` |
| 数据质量 | `39,642` 根已闭合 K；缺口、重复、关键空值、OHLC 违规、raw/normalized 差异均为 0 |
| Funding | Binance funding，对齐实际剩余持仓 |
| 成本 | 每次 fill `0.00085`；入场、分批、最终退出分别按实际 allocation 计入 |

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

short_partial_take_profit:
  enabled: true
  trigger_atr: 4.4
  fraction_of_initial_allocation: 0.75
  max_fills_per_position: 1
  remaining_fraction: 0.25
  remaining_take_profit_atr: 5.0
  remaining_hard_stop_atr: 7.0
```

TP、SL 与分批价均使用入场时冻结的 K1 `ATR672`，从 entry price 固定计算。多单不分批。

空单若分批后最终 TP，忽略成本与 funding 的毛收益距离为：

```text
0.75 × 4.4ATR + 0.25 × 5ATR = 4.55ATR
```

空单若分批后最终 SL：

```text
0.75 × 4.4ATR + 0.25 × (-7ATR) = +1.55ATR
```

未达到 `4.4ATR` 的空单仍承担完整 `SL7`。

## 执行与冷却状态机

```yaml
execution:
  signal_bar: K0 close
  entry_bar: K2 open
  entry_atr_source: completed K1 ATR672
  same_bar_reentry: false
  cooldown_bars: 1
  partial_order: reduce_only
  partial_fill_releases_strategy_position: false
```

盘中排序：

1. 先检查原始硬止损；
2. 未触发止损时，检查空头 `4.4ATR` 分批价；
3. 同 bar 同时达到分批价与 TP5，先按 `4.4ATR` 平 75%，再按 TP5 平剩余 25%；
4. 分批不算一次策略平仓，不增加交易笔数、不释放单持仓占用、不触发 cooldown；
5. 只有剩余仓位最终退出后，才将该 bar 记为 `E`；禁止 `E+1` 开仓，最早 `E+2 open` 重新入场。

分批按固定 reduce-only limit 价格建模；有利跳空越过分批价时仍按固定目标价成交，不计价格改善。指标退出在收盘确认，下一根 open 成交。

## 冻结回测

| 窗口 | 收益 | MaxDD | 平仓数 |
| --- | ---: | ---: | ---: |
| `1d` | `+12.23%` | `-3.52%` | `1` |
| `7d` | `+9.65%` | `-11.10%` | `3` |
| `1m` | `+21.45%` | `-14.60%` | `6` |
| `3m` | `+150.56%` | `-20.99%` | `31` |
| `6m` | `+1888.16%` | `-20.99%` | `66` |
| `1y` | `+11072.80%` | `-20.99%` | `102` |
| `full` | `+11682.28%` | `-23.46%` | `109` |

Full Sharpe `4.97`，胜率 `81.65%`（`89/109`），多单 `84` 笔、空单 `25` 笔；退出标签为 TP `83`、SL `14`、indicator exit `12`。共发生 `23` 次空头分批：`22` 笔已结束，其中最终 TP `20`、最终 SL `2`；数据终点另有 `1` 笔已分批未结束。

同窗口 V39.2 为 `+9729.16% / -24.61% / Sharpe 4.72 / 109 笔 / 胜率 79.82%`。V39.4 最终资金为 V39.2 的 `119.87%`。

回测终点仍有一笔空单：`2026-07-17 02:00 UTC` 入场，`07:30 UTC` 在 `4.4ATR` 分批，终点剩余 allocation `0.75x`；该笔仅按 mark-to-market 进入权益，不计入 `109` 笔平仓数。

## 登记理由与门禁

- 主状态：`registered`。
- 角色：V39.2 的样本内高收益空头回吐保险变体。
- 登记依据：用户指定将 `V39.2 + short 4.4ATR reduce 75%` 登记为 V39.4；当前 full 收益、MaxDD、Sharpe 与胜率均优于 V39.2。
- `not promoted / not live-ready`：空单仅 `25` 笔，收益改善主要来自两笔高 MFE 后最终 SL 的事件。
- 关键敏感性：其中一笔被救回交易的最大 MFE 仅 `4.467464ATR`，距离 `4.4ATR` 触发线只有 `0.067464ATR`；把阈值提高到 `4.5ATR` 会漏掉该事件。
- 多重试验风险：本结论来自同一 full 样本上的 `4.0/4.2/4.4ATR × 50%/66.7%/75%` 扫描，`4.4/75%` 是样本内最优点。
- 尚缺：冻结后的独立时间前推 OOS、walk-forward/CPCV、Monte Carlo、成本与部分成交压力、entry phase/bar-alignment、跨所迁移及 live-executable reduce-only 审计。
- 不创建 V39.4 live spec，不修改任何 runner、active manifest 或生产配置。

## 证据

- 分批诊断：[hype-ema-tb-v39-2-short-partial-take-profit-2026-07-17.md](../diagnostics/hype-ema-tb-v39-2-short-partial-take-profit-2026-07-17.md)
- 复现脚本：[research_hype_ema_tb_v39_2_short_partial_take_profit.py](../scripts/research_hype_ema_tb_v39_2_short_partial_take_profit.py)
- 汇总 JSON：[hype_ema_tb_v39_2_short_partial_take_profit_2026-07-17.json](../artifacts/hype_ema_tb_v39_2_short_partial_take_profit_2026-07-17.json)
- 逐笔交易：[hype_ema_tb_v39_2_short_partial_take_profit_2026-07-17_trades.csv](../artifacts/hype_ema_tb_v39_2_short_partial_take_profit_2026-07-17_trades.csv)
- 权益曲线：[hype_ema_tb_v39_2_short_partial_take_profit_2026-07-17_equity.csv](../artifacts/hype_ema_tb_v39_2_short_partial_take_profit_2026-07-17_equity.csv)
