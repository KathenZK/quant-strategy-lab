# HYPE-EMA-TB-V35.2 冻结参数说明

日期：2026-07-20  
状态：`registered / not promoted / not live-ready`  
角色：V35.1 的空头高 MFE 分批止盈观察版

本文档登记 `HYPE-EMA-Trend-Breakout-V35.2`。V35.2 保持 V35.1 的入场、sizing、TP5/SL7、指标退出与 cooldown0，只在空单盘中达到 `4.4 × entry ATR672` 时执行一次 reduce-only，平掉初始 allocation 的 `75%`，剩余 `25%` 继续原状态机。

## 版本身份

```text
V35.1 = V35
      - short h1 EMA confirmation

V35.2 = V35.1
      + short partial trigger 4.4ATR
      + short partial fraction 75%
      + remaining fraction 25% keeps TP5/SL7
```

V35.2 不包含 V41 的 cooldown1，不提高空头风险预算，不采用 V39.3 的 `TP4.8/SL6.75`，也不包含 V37/V39.1 卫星或 V38 profit floor。

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

execution:
  signal_bar: K0 close
  entry_bar: K2 open
  entry_atr_source: completed K1 ATR672
  same_bar_reentry: false
  cooldown_bars: 0
  partial_order: reduce_only
  partial_fill_releases_strategy_position: false
```

TP、SL 与空头分批价均按 entry price 和入场时冻结的 K1 `ATR672` 固定计算；多单不分批。空单分批后最终 TP 的毛收益距离为 `0.75 × 4.4 + 0.25 × 5 = 4.55ATR`；分批后最终 SL 为 `0.75 × 4.4 + 0.25 × (-7) = +1.55ATR`。未达到 `4.4ATR` 的空单仍承担完整 `SL7`。

## 执行排序

1. 每根 K 先检查原始硬止损；
2. 未触发止损时，检查空头 `4.4ATR` 分批价；
3. 同一根 K 同时达到分批价与 TP5 时，先按 `4.4ATR` 平 75%，再按 TP5 平剩余 25%；
4. 分批不算策略平仓，不增加交易笔数、不释放单持仓占用、不允许重入；
5. 只有剩余仓位最终退出后，才允许下一根 K 按仍成立的延迟信号重新入场。

分批按固定 reduce-only limit 价格建模；有利跳空越过分批价时仍按固定目标价成交，不计价格改善。指标退出在收盘确认，下一根 open 成交。

## 冻结回测

| 窗口 | 收益 | MaxDD | 平仓数 |
| --- | ---: | ---: | ---: |
| `1d` | `0.00%` | `0.00%` | 0 |
| `7d` | `+11.02%` | `-11.10%` | 4 |
| `1m` | `+22.06%` | `-14.60%` | 7 |
| `3m` | `+165.43%` | `-21.90%` | 35 |
| `6m` | `+2168.81%` | `-21.90%` | 69 |
| `1y` | `+8750.77%` | `-22.04%` | 105 |
| `full` | `+9409.39%` | `-23.46%` | 112 |

Full Sharpe `4.81`，胜率 `79.46%`（`89/112`），多单 85 笔、空单 27 笔；退出标签为 TP 85、SL 16、indicator exit 11。共发生 23 次空头分批，最终 21 笔 TP、2 笔 SL。

同窗口 V35.1 为 `+8047.47% / -27.26% / Sharpe 4.55 / 112 笔 / 胜率 77.68%`。V35.2 最终权益为 V35.1 的 `116.72%`；入场、最终退出时间、方向与退出标签不变。

## 登记结论与门禁

- 主状态：`registered`；用户指定登记为 `HYPE-EMA-TB-V35.2`，不表示 promotion。
- `not promoted / not live-ready`：本规则来自既有阈值/比例扫描，当前只有 23 次分批触发。
- 峰值敏感性：已知关键交易的 MFE 仅约 `4.467ATR`，距触发线约 `0.067ATR`；`4.5ATR` 会漏掉该事件。
- 尚缺冻结后的独立时间前推 OOS、walk-forward/CPCV、Monte Carlo、成本/部分成交压力、真实 reduce-only 订单、保护单缩量、重启恢复及 live-executable 审计。
- quant-runner 的 `hype_ema_tb` 当前只实现 V35.1 状态机；V35.2 的分批状态、订单与持久化尚未实现，不创建 live spec、不修改 manifest、配置或生产服务。

## 证据

- [V35.2 诊断报告](../diagnostics/hype-ema-tb-v35-1-short-partial-4-4atr-2026-07-20.md)
- [复现脚本](../scripts/research_hype_ema_tb_v35_1_short_partial_4_4.py)
- [汇总 JSON](../artifacts/hype_ema_tb_v35_1_short_partial_4_4_2026-07-20.json)
- [逐笔交易](../artifacts/hype_ema_tb_v35_1_short_partial_4_4_2026-07-20_trades.csv)
- [权益曲线](../artifacts/hype_ema_tb_v35_1_short_partial_4_4_2026-07-20_equity.csv)
- [父版本 V35.1](hype-trend-strategy-v35-1-spec.md)
