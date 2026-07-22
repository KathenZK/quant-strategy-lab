# HYPE-EMA-TB-V41 冻结参数说明

日期：2026-07-20  
状态：`registered / not promoted / not live-ready`

V41 从 V40 出发，只把空头 ATR 风险预算从 `0.022` 回退到 V35 的 `0.018`。V40 的 cooldown1 和“移除空头 1h EMA 确认”保持不变；这不是 live 配置变更，也不授权修改现有 V35 runner。

## 版本身份

```text
V41 = V40
    + short_target_atr_pct 0.022 -> 0.018

等价展开：
V41 = V35
    + cooldown_bars 0 -> 1
    + remove short h1 EMA confirmation
```

`short_target_atr_pct` 是波动率目标风险预算，不是固定杠杆。V41 只是撤销 V40 对空头 sizing 的放大；多头风险、`3.0x` cap、`TP5/SL7` 和其它退出规则均不变。

## 数据与成本

| 项目 | 冻结值 |
| --- | --- |
| 市场 | Binance USD-M perpetual |
| 标的 | `HYPE/USDT:USDT` |
| 周期 | `15m` |
| 回测数据窗口 | `2025-05-30 10:30 UTC` 至 `2026-07-17 08:45 UTC` |
| 数据质量 | `39,642` 根已闭合 K；缺口、重复、关键空值、OHLC 违规均为 0 |
| Funding | Binance funding，对齐持仓区间 |
| 成本 | 每次 fill `0.00085`，开仓和平仓分别计入 |

## 冻结参数

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

sizing:
  long_target_atr_pct: 0.020
  short_target_atr_pct: 0.018
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
  partial_take_profit: none

execution:
  signal_bar: K0 close
  entry_bar: K2 open
  entry_atr_source: completed K1 ATR672
  same_bar_reentry: false
  cooldown_bars: 1
```

平仓发生在 bar `E` 时，`E` 与 `E+1` 均不得重新开仓，最早允许在 `E+2 open` 按正常信号开仓。TP/SL 使用入场时冻结的 K1 `ATR672`；指标退出在收盘确认，下一根 open 成交。

## 冻结回测

| 窗口 | 收益 | MaxDD | 平仓数 |
| --- | ---: | ---: | ---: |
| `1d` | `+8.94%` | `-4.64%` | `1` |
| `7d` | `-7.71%` | `-22.94%` | `3` |
| `1m` | `+2.22%` | `-23.40%` | `6` |
| `3m` | `+114.20%` | `-24.61%` | `31` |
| `6m` | `+1336.69%` | `-24.61%` | `66` |
| `1y` | `+7886.01%` | `-24.61%` | `102` |
| `full` | `+8321.65%` | `-24.61%` | `109` |

Full Sharpe `4.69`，胜率 `79.82%`（`87/109`）；多单 `84` 笔、空单 `25` 笔；退出为 TP `83`、SL `14`、indicator exit `12`。

## V40 对照与风险边界

- V40：`+9729.16% / -24.61% / Sharpe 4.72 / 109 笔 / 胜率 79.82%`。
- V41：`+8321.65% / -24.61% / Sharpe 4.69 / 109 笔 / 胜率 79.82%`。
- V40/V41 的 `entry_ts + exit_ts + direction + exit_reason` 逐笔签名完全一致；差异只来自空头 allocation。
- V41 中位/p90/最大理论单笔 SL 账户风险约 `12.77% / 14.00% / 14.00%`；V40 约为 `13.89% / 15.00% / 15.40%`。
- V41 撤销了 V40 的额外空头风险，但没有把全策略单笔风险降到 `7%～9%`，也没有解决 profit giveback、滑点或 runner 账本问题。

## 状态与门禁

- 主状态：`registered / not promoted / not live-ready`。
- V41 是风险回退观察版，不是 V35 live runner 的替换授权。
- cooldown1 仍是样本内孤立尖峰；V41 未完成冻结后 OOS、walk-forward/CPCV、Monte Carlo、压力测试、entry phase、跨所迁移与 live-executable 审计。
- 不创建 V41 live spec，不修改 runner、active manifest 或生产配置。

## 证据

- 回测脚本：[research_hype_ema_tb_v41.py](../scripts/research_hype_ema_tb_v41.py)
- 汇总产物：[hype_ema_tb_v41_2026-07-20.json](../artifacts/hype_ema_tb_v41_2026-07-20.json)
- 逐笔产物：[hype_ema_tb_v41_2026-07-20_trades.csv](../artifacts/hype_ema_tb_v41_2026-07-20_trades.csv)
- 权益产物：[hype_ema_tb_v41_2026-07-20_equity.csv](../artifacts/hype_ema_tb_v41_2026-07-20_equity.csv)
- 父版本：[hype-trend-strategy-v40-spec.md](hype-trend-strategy-v40-spec.md)
