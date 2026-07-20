# HYPE-EMA-TB-V40 冻结参数说明

日期：2026-07-17  
状态：`registered / not promoted / not live-ready`

本文档登记 `HYPE-EMA-Trend-Breakout-V40`。V40 从 V35 出发只保留三项结构变化：提高空头 ATR 风险预算、平仓后冷却一根 K、移除空头 1h EMA 确认。其参数与状态机和已登记的 V39.2 完全相同，因此 V40 是对 V39.2 的等价重编号，不产生新的交易路径或独立统计样本。

## 版本身份

```text
V40 = V35
    + short_target_atr_pct 0.018 -> 0.022
    + cooldown_bars 0 -> 1
    + remove short h1 EMA confirmation

V40 ≡ V39.2
```

V39.1 曾在研究过程中短暂使用过“V40”称呼，但已正式降级并冻结为 V39.1；该临时称呼不构成版本登记。自本文档起，`HYPE-EMA-TB-V40` 只指上述三项变化组合。

V40 不包含 V39 的多头量能 `0.35`，多头量能保持 V35 的 `0.25`；不包含 V39.3 的 `TP4.8/SL6.75`、V39.4 的空头分批止盈、V37 early-long 卫星或 V38 profit floor。

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
```

`short_target_atr_pct=0.022` 只改变空头 allocation，不改变信号。它是风险预算，不应被解释为新增 alpha 或已证明的最优常数。TP/SL 使用入场时冻结的 K1 `ATR672`；指标退出在收盘确认，下一根 open 成交。

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
| `1d` | `+8.94%` | `-4.64%` | `1` |
| `7d` | `-7.71%` | `-22.94%` | `3` |
| `1m` | `+2.22%` | `-23.40%` | `6` |
| `3m` | `+114.41%` | `-24.61%` | `31` |
| `6m` | `+1369.77%` | `-24.61%` | `66` |
| `1y` | `+9220.72%` | `-24.61%` | `102` |
| `full` | `+9729.16%` | `-24.61%` | `109` |

Full Sharpe `4.72`，胜率 `79.82%`（`87/109`），多单 `84` 笔、空单 `25` 笔；退出为 TP `83`、SL `14`、indicator exit `12`。

上述结果直接复用同窗口 V39.2 canonical baseline。V40 与 V39.2 配置完全相同，因此预期逐笔交易签名和逐根 equity 最大差异均为 `0`；这些数字不是第二组独立证据。

回测终点仍有一笔 `2026-07-17 02:00 UTC` 入场的空单，仅按 mark-to-market 进入权益，不计入 `109` 笔平仓数。

## 三项变化的证据边界

- 空头风险预算：从 `0.018` 提高到 `0.022` 是机械收益/风险放大；当前仅约 `25` 笔空单，不能证明 `0.022` 永久最优。
- cooldown1：当前比较中阻止 `38` 条立即重入并形成 `36` 条延迟路径，净变化为多 `1` 胜、少 `3` 负、少 `2` 次 SL；但收益主要由少数关键路径贡献，且一根冷却是局部参数尖峰。
- 移除空头 1h EMA 确认：定位为删除冗余条件和降低复杂度，不计为独立 alpha。

## 状态与门禁

- 主状态：`registered`。
- 角色：V35 三项结构精简版，同时是 V39.2 的等价身份。
- `not promoted / not live-ready`：没有新增 OOS；V40 与 V39.2 共享同一份样本和回测证据，不能把两个版本当成两次成功验证。
- 尚缺：冻结后的独立时间前推 OOS、walk-forward/CPCV、Monte Carlo、压力测试、entry phase/bar-alignment、跨所迁移及 live-executable 审计。
- 不创建 V40 live spec，不修改任何 runner、active manifest 或生产配置。

## 证据

- V39.2 冻结规格：[hype-trend-strategy-v39-2-spec.md](hype-trend-strategy-v39-2-spec.md)
- 联合参数诊断：[hype-ema-tb-v39-long-vol025-cooldown1-2026-07-17.md](../diagnostics/hype-ema-tb-v39-long-vol025-cooldown1-2026-07-17.md)
- 最新等价基线摘要：[hype_ema_tb_v39_2_short_partial_take_profit_2026-07-17.json](../artifacts/hype_ema_tb_v39_2_short_partial_take_profit_2026-07-17.json)
- 复现脚本：[research_hype_ema_tb_v39_2_short_partial_take_profit.py](../scripts/research_hype_ema_tb_v39_2_short_partial_take_profit.py)
