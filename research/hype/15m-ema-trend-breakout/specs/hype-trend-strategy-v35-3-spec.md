# HYPE-EMA-TB-V35.3 冻结参数说明

日期：2026-07-20  
状态：`registered / not promoted / not live-ready`  
角色：V35.2 的非对称硬止损观察版

## 版本身份

```text
V35.2 = V35.1
      + short MFE4.4ATR reduce 75%
      + remaining 25% keeps TP5/SL7

V35.3 = V35.2
      + long hard stop 7.0 -> 6.75ATR
      + short hard stop 7.0 -> 5.70ATR
```

V35.3 只冻结上述两个方向止损。它不包含 cooldown1、提高空头风险预算、profit floor、trailing stop 或 early-long 卫星。

## 数据与成本

| 项目 | 冻结值 |
| --- | --- |
| 市场 | Binance USD-M perpetual |
| 标的 | `HYPE/USDT:USDT` |
| 周期 | `15m` |
| 回测数据窗口 | `2025-05-30 10:30 UTC` 至 `2026-07-20 08:15 UTC` |
| 数据质量 | `39,928` 根已闭合 K；缺口、重复、关键空值、OHLC 违规、raw/normalized 差异均为 0 |
| Funding | Binance funding，对齐实际剩余 allocation |
| 成本 | 每次 fill `0.00085`；入场、分批、最终退出分别按实际 allocation 计入 |

## 冻结参数

```yaml
features:
  ema_fast: 96
  ema_slow: 384
  adx_window: 28
  volume_window: 192
  atr_window: 672
  h1_adx_window: 21
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
  take_profit_atr:
    long: 5.0
    short: 5.0
  hard_stop_atr:
    long: 6.75
    short: 5.70
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
  remaining_hard_stop_atr: 5.70

execution:
  signal_bar: K0 close
  entry_bar: K2 open
  entry_atr_source: completed K1 ATR672
  same_bar_reentry: false
  cooldown_bars: 0
  partial_order: reduce_only
  partial_fill_releases_strategy_position: false
```

## 执行排序

1. 信号在 K0 close 确认，跳过完整 K1，K2 open 入场；
2. TP、方向止损和空头分批价均按 entry price 与 K1 `ATR672` 固定计算；
3. 每根 K 先检查方向硬止损；
4. 空头未触发 SL5.7 时，再检查 `4.4ATR` 分批止盈；
5. 同 bar 同时达到空头分批价与 TP5，先平初始 allocation 的 75%，再按 TP5 平剩余 25%；
6. 分批不释放持仓槽位；只有最终退出才允许下一根 K 按仍成立的延迟信号重新入场。

空头在未分批前直接 SL5.7 的未封顶理论风险约为 `0.018 × 5.7 = 10.26%`；多头 SL6.75 约为 `0.020 × 6.75 = 13.50%`。实际结果还受 3.0x allocation cap、成本、funding 与成交滑点影响。

## 冻结回测

| 窗口 | 收益 | MaxDD | 平仓数 |
| --- | ---: | ---: | ---: |
| `1d` | `0.00%` | `0.00%` | 0 |
| `7d` | `+11.61%` | `-10.64%` | 4 |
| `1m` | `+22.70%` | `-14.60%` | 7 |
| `3m` | `+166.83%` | `-21.90%` | 35 |
| `6m` | `+2180.76%` | `-21.90%` | 69 |
| `1y` | `+9246.34%` | `-21.90%` | 106 |
| `full` | `+10017.59%` | `-22.88%` | 113 |

Full Sharpe `4.86`，胜率 `79.65%`（`90/113`），多单 86 笔、空单 27 笔；退出标签为 TP 86、SL 17、indicator exit 10。方向新止损共触发 5 笔，其中多头 2 笔、空头 3 笔。

同窗口 V35.2 为 `+9409.39% / -23.46% / Sharpe 4.81 / 112 笔 / 胜率 79.46%`；V35.3 最终权益为 V35.2 的 `106.40%`。

## 登记结论与门禁

- 主状态：`registered`；用户指定登记为 `HYPE-EMA-TB-V35.3`，不表示 promotion。
- 多头 SL6.75 来自同窗方向扫描，只触发 2 笔，并在 `6.70→6.75ATR` 出现路径断点和一条新增 TP。
- 空头 SL5.7 只触发 3 笔；`5.6ATR` 会额外击中一笔最终 TP。
- 两个参数均是同一 full 样本上的事后选择，标准分片不能替代冻结后 OOS。
- 尚缺 walk-forward/CPCV、Monte Carlo、stop-market 跳空/滑点压力、真实部分成交、重启恢复和 live-executable review。
- quant-runner 当前只实现 V35.1 状态机；V35.2/V35.3 均未实现，不创建 live spec、不修改 manifest、配置或线上 V35。

## 证据

- [组合回测报告](../diagnostics/hype-ema-tb-v35-3-asymmetric-stop-backtest-2026-07-20.md)
- [复现脚本](../scripts/research_hype_ema_tb_v35_3.py)
- [汇总 JSON](../artifacts/hype_ema_tb_v35_3_2026-07-20.json)
- [逐笔交易](../artifacts/hype_ema_tb_v35_3_2026-07-20_trades.csv)
- [权益曲线](../artifacts/hype_ema_tb_v35_3_2026-07-20_equity.csv)
- [父版本 V35.2](hype-trend-strategy-v35-2-spec.md)
