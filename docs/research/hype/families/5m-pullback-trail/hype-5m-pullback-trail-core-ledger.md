# HYPE-5M-PBTR 5m Pullback-Trail Core Ledger

Ledger id：`HYPE-5M-PBTR`

Created：2026-06-23

## Boundary

`HYPE-5M-PBTR` 是一条新的 HYPE Binance 永续 `5m` 回踩-追踪止损研究线。

它和已有 `hype-ema-tb-core-ledger.md` 的 15m 趋势突破/跨所执行系列不是同一条主线。虽然两者都使用 EMA，但版本号不能混读：

- `HYPE-5M-PBTR-V1/V2`：本文中的 5m 回踩-追踪止损策略。
- `HYPE-EMA-TB-V35/V36/V37`：原 15m 趋势突破/跨所执行策略。
- `HYPE-EMA-X-V15/V16/V17`：另一个 EMA 金死叉/交叉质量策略族。

本文中的 V1/V2 只在 `HYPE-5M-PBTR` 主账内有效。

## Strategy Idea

一句话：在 HYPE 的 `5m` 局部趋势中，等待价格回踩或反抽 EMA21 后重新恢复趋势方向，下一根 K 开仓，然后至少持有 6 根 K，用 `0.75 ATR` 追踪止损锁住趋势恢复后的利润。

核心不是传统 EMA 交叉，也不是追 Donchian 突破，而是：

```text
趋势背景确认 -> 回踩/反抽 EMA21 -> 收盘重新站回趋势方向 -> 至少持有 6 根 K -> ATR trailing stop 退出
```

## Data And Cost

- Exchange：Binance。
- Symbol：HYPEUSDT USDT 永续。
- Timeframe：`5m`。
- 数据范围：本地数据湖全量，约 `2025-05-30 10:30 UTC` 到 `2026-06-23 04:20 UTC`。
- 成本口径：自 `2026-06-24` 起，主账新回测统一使用线上实盘统计成本。
- 手续费：`3.0578 / 7374.2110 = 4.1466 bps/成交额`，按每次成交额扣除。
- 开仓滑点：`+10.73 bps`。
- 平仓滑点：`-2.64 bps`。
- 净滑点：`+4.0449 bps/总成交额`。
- 杠杆：当前研究统一按 `1x`。
- 仓位：单策略单仓，不叠仓。
- 回撤口径：`HYPE-5M-PBTR` 主账使用真实开仓到实际平仓路径 MAE/MFE。

## Version Rules


| 层级  | 说明                                                   |
| --- | ---------------------------------------------------- |
| V1  | 第一版可实盘观察基线，来自 `HYPE_PP_R05732__dir_htf_ge_0.688442`。 |
| V2  | 基于 V1 全参数消融后的同步微调版本。                                 |
| V2.1 | 基于 V2 实盘成本消融后的参数简化和候选分支；不改变 `HYPE-5M-PBTR` 核心机制。       |
| V3 | 独立高频候选：来自 `V2.1A`，移除 final `dir_htf` 过滤；不直接替代 V2.1A。       |
| 后缀  | 若后续只是改变过滤强度或执行保护，可用 V3-lite/V3.1；若改变核心机制，再升 V4。           |


## Version Table


| 版本                | 核心变化                                                                                                | 状态                              | 全样本交易  | 年化        | 胜率       | payoff | 最大回撤     | 最差切片胜率   | 结论                                |
| ----------------- | --------------------------------------------------------------------------------------------------- | ------------------------------- | ------ | --------- | -------- | ------ | -------- | -------- | --------------------------------- |
| `HYPE-5M-PBTR-V1` | R05732 基线：`pullback_buffer=0.0025`，`tp_atr=1.875`，`stop_atr=0.75`，`dir_htf>=0.688442`               | live dry-run candidate          | `1341` | `14.97x`  | `54.29%` | `2.37` | `-7.77%` | `52.74%` | 实盘成本下收益仍为正，但胜率体验弱于旧默认成本口径。            |
| `HYPE-5M-PBTR-V2` | 同步微调：`pullback_buffer=0.01`，删除固定止盈，`stop_atr=0.5`，`roc_window=96`，`min_efficiency=0`，`dir_htf>=0.5` | research live-dry-run candidate | `2519` | `181.87x` | `52.44%` | `2.77` | `-7.01%` | `50.49%` | 实盘成本下仍明显优于 V1，频率和收益提高但胜率下降。 |
| `HYPE-5M-PBTR-V2.1-clean` | V2 实盘成本口径简化：固定/移除不生效参数，保留核心入场与 ATR trailing exit。                                      | preferred simplified V2 expression | `2521` | `181.96x` | `52.44%` | `2.77` | `-7.01%` | 见报告 | 与 V2 实盘成本表现几乎一致，适合作为新解释/实现基线。 |
| `HYPE-5M-PBTR-V2.1A` | 在 V2.1-clean 上放开 RSI 上下界。                                                                      | return candidate                | `3146` | `352.15x` | `51.40%` | `2.64` | `-6.62%` | 见报告 | 收益最高、回撤改善，但胜率下降；适合继续 dry-run 观察。 |
| `HYPE-5M-PBTR-V3` | 独立高频候选：在 V2.1A 上移除 final `dir_htf` 过滤。                                                        | high-frequency research candidate | `9108` | `1544745.29x` | `48.39%` | `2.75` | `-7.95%` | 见诊断 | 交易数约为 V2.1A 的 `2.9x`，收益极高但执行敏感性显著提高；只适合小资金 dry-run。 |
| `HYPE-5M-PBTR-V2.1B` | 在 V2.1-clean 上去掉 `min_dir_roc`。                                                                  | clean-plus candidate            | `2537` | `185.51x` | `52.38%` | `2.77` | `-7.01%` | 见报告 | 低风险进一步简化，收益略升，行为接近 V2.1-clean。 |
| `HYPE-5M-PBTR-V2.1C-HTF` | 在 V2.1-clean 上提高最终 `dir_htf` 阈值到 `0.688442`。                                                  | stable candidate                | `1823` | `71.37x`  | `53.70%` | `2.85` | `-7.27%` | 见报告 | 胜率和盈亏比提高，但交易数和收益显著下降，回撤略变差。 |
| `HYPE-5M-PBTR-V2.1C-ADX14` | 在 V2.1-clean 上加入 `min_adx=14`。                                                               | stable candidate                | `2351` | `153.61x` | `53.08%` | `2.79` | `-7.01%` | 见报告 | 更温和的稳定版，胜率提高且回撤不变，收益低于 clean。 |

注：上表从 `2026-06-24` 起采用线上实盘成本口径。早期 V1/V2 小节中的历史切片表来自旧默认成本报告，仅作为研究来源记录；当前候选横向比较以上表和实盘成本诊断为准。


## V1 Specification

Canonical name：`HYPE-5M-PBTR-V1`

Source candidate：`HYPE_PP_R05732__dir_htf_ge_0.688442`

参数：


| 参数                | 值                     |
| ----------------- | --------------------- |
| `side_mode`       | `both`                |
| `ema_fast`        | `21`                  |
| `ema_slow`        | `96`                  |
| `entry_style`     | `pullback_resume`     |
| `pullback_buffer` | `0.0025`              |
| `roc_window`      | `48`                  |
| `min_regime_age`  | `3`                   |
| `max_regime_age`  | `2000`                |
| `max_dist_ema`    | `0.06`                |
| `min_dir_roc`     | `-0.01`               |
| `min_dir_rsi`     | `55`                  |
| `max_dir_rsi`     | `72`                  |
| `max_chop`        | `62`                  |
| `min_efficiency`  | `0.025`               |
| `stop_atr`        | `0.75`                |
| `tp_atr`          | `1.875`               |
| `trail_atr`       | `0.75`                |
| `min_hold_bars`   | `6`                   |
| `max_hold_bars`   | `576`                 |
| `final_filter`    | `dir_htf >= 0.688442` |


表现：


| 切片                    | 交易数    | 年化        | 胜率       | payoff | 最大回撤     |
| --------------------- | ------ | --------- | -------- | ------ | -------- |
| full                  | `1340` | `29.07x`  | `59.18%` | `2.58` | `-7.70%` |
| 2025-05-30~2025-09-01 | `350`  | `22.98x`  | `59.43%` | `2.22` | `-4.10%` |
| 2025-09-01~2025-12-01 | `350`  | `113.91x` | `58.29%` | `3.17` | `-4.16%` |
| 2025-12-01~2026-03-01 | `173`  | `9.75x`   | `58.96%` | `2.74` | `-7.70%` |
| 2026-03-01~2026-06-01 | `328`  | `13.82x`  | `58.54%` | `2.37` | `-3.30%` |
| 2026-06-01~2026-06-23 | `139`  | `530.16x` | `62.59%` | `2.19` | `-4.34%` |


频率：

- 全样本约 `3.45` 笔/天，`24.13` 笔/周，`104.92` 笔/月。
- forward 约 `6.27` 笔/天。

## V2 Specification

Canonical name：`HYPE-5M-PBTR-V2`

Source combo label：

```text
ema21_96_pb0.01_tp99_sl0.5_chop62_eff0_rsi55_roc96_htf0.5
```

参数：


| 参数                | 值                 |
| ----------------- | ----------------- |
| `side_mode`       | `both`            |
| `ema_fast`        | `21`              |
| `ema_slow`        | `96`              |
| `entry_style`     | `pullback_resume` |
| `pullback_buffer` | `0.01`            |
| `roc_window`      | `96`              |
| `min_regime_age`  | `3`               |
| `max_regime_age`  | `2000`            |
| `max_dist_ema`    | `0.06`            |
| `min_dir_roc`     | `-0.01`           |
| `min_dir_rsi`     | `55`              |
| `max_dir_rsi`     | `72`              |
| `max_chop`        | `62`              |
| `min_efficiency`  | `0`               |
| `stop_atr`        | `0.5`             |
| `tp_atr`          | `99.0`            |
| `trail_atr`       | `0.75`            |
| `min_hold_bars`   | `6`               |
| `max_hold_bars`   | `576`             |
| `final_filter`    | `dir_htf >= 0.5`  |


表现：


| 切片                    | 交易数    | 年化           | 胜率       | payoff | 最大回撤     |
| --------------------- | ------ | ------------ | -------- | ------ | -------- |
| full                  | `2515` | `548.67x`    | `57.46%` | `2.79` | `-6.85%` |
| 2025-05-30~2025-09-01 | `622`  | `210.32x`    | `56.91%` | `2.43` | `-5.64%` |
| 2025-09-01~2025-12-01 | `658`  | `3290.48x`   | `56.23%` | `3.08` | `-5.14%` |
| 2025-12-01~2026-03-01 | `391`  | `237.61x`    | `60.87%` | `2.95` | `-6.85%` |
| 2026-03-01~2026-06-01 | `607`  | `137.91x`    | `57.00%` | `2.61` | `-5.42%` |
| 2026-06-01~2026-06-23 | `237`  | `184639.47x` | `57.81%` | `2.96` | `-4.39%` |


频率：

- 全样本约 `6.47` 笔/天，`45.29` 笔/周，`196.92` 笔/月。
- forward 约 `10.69` 笔/天。

交易结构：

- 多头：`1364` 笔，胜率 `56.96%`，payoff `2.69`，profit factor `3.57`。
- 空头：`1151` 笔，胜率 `58.04%`，payoff `2.90`，profit factor `4.01`。
- 退出：全部为 trailing stop，因为固定止盈被等效删除。
- 平均持仓：`7.22` 根 5m K，约 `36.1` 分钟。

## V2.1 Live-Cost Variant Ledger

来源报告：`ablations/hype-5m-pullback-trail-v21-live-cost-variants-2026-06-23.md`。

成本口径来自实盘统计，不同于旧研究默认成本：

```text
fee = 4.1466 bps / turnover
entry_slippage = +10.73 bps
exit_slippage = -2.64 bps
net_slippage = +4.0449 bps / total turnover
```

V2.1 系列的目的不是改变 `HYPE-5M-PBTR` 核心机制，而是在 V2 实盘成本消融后拆分两个动作：

1. 先得到可解释性更干净的 `HYPE-5M-PBTR-V2.1-clean`。
2. 再在 V2.1-clean 上测试收益增强、进一步简化、稳定性增强分支。

### V2.1-clean

Canonical name：`HYPE-5M-PBTR-V2.1-clean`

相对 V2：

| 参数 | V2.1-clean 处理 |
| --- | --- |
| `max_regime_age` | 固定/移除，设为 `100000`，不再作为真实约束 |
| `max_dist_ema` | 固定/移除，设为 `99.0`，不再作为真实约束 |
| `min_dir_cmf` | 固定/移除，设为 `-99.0`，不再作为真实约束 |
| `max_hold_bars` | 固定为 `96`；上一轮显示 `96/576/100000` 结果相同 |
| `exit_ema` | 保持 `0`，不引入 EMA 退出 |
| `require_htf` | 保持 `false`，只使用最终 `dir_htf >= threshold` |

仍保留：

```text
EMA21/EMA96
pullback_resume
pullback_buffer = 0.01
roc_window = 96
min_regime_age = 3
min_dir_roc = -0.01
max_chop = 62
min_efficiency = 0
stop_atr = 0.5
tp_atr = 99
trail_atr = 0.75
min_hold_bars = 6
final dir_htf >= 0.5
```

表现：

| 交易数 | 累计收益 | 年化 | 胜率 | payoff | profit factor | 最大回撤 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `2521` | `+25330.23%` | `181.96x` | `52.44%` | `2.77` | `3.06` | `-7.01%` |

结论：V2.1-clean 与 V2 实盘成本基线几乎完全一致，适合作为后续解释和实现基线。

### V2.1A: RSI 放开

Canonical name：`HYPE-5M-PBTR-V2.1A`

相对 V2.1-clean：

```text
min_dir_rsi = 0
max_dir_rsi = 100
```

表现：

| 交易数 | 累计收益 | 年化 | 胜率 | payoff | profit factor | 最大回撤 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `3146` | `+51249.39%` | `352.15x` | `51.40%` | `2.64` | `2.79` | `-6.62%` |

结论：当前实盘成本口径下收益最高且最大回撤改善，但胜率下降、周度盈利占比降到 `98.21%`。这是收益增强候选，不应直接视为生产批准。

### V3: V2.1A Remove Final HTF

Canonical name：`HYPE-5M-PBTR-V3`

来源报告：`diagnostics/hype-5m-pbtr-v21a-remove-final-htf-live-cost-2026-06-24.md`。

全参数消融与量化审计：`diagnostics/hype-5m-pbtr-v3-ablation-audit-2026-06-24.md`。

相对 V2.1A：

```text
final dir_htf filter = disabled
```

不改变：

```text
EMA21/EMA96
pullback_resume
pullback_buffer = 0.01
min_dir_rsi = 0
max_dir_rsi = 100
stop_atr = 0.5
tp_atr = 99
trail_atr = 0.75
min_hold_bars = 6
```

表现：

| 交易数 | 累计收益 | 年化 | 胜率 | payoff | profit factor | 最大回撤 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `9108` | `+386302054.17%` | `1544745.29x` | `48.39%` | `2.75` | `2.58` | `-7.95%` |

分桶：

| 桶 | 交易数 | 单桶权益倍数 | 胜率 | payoff | profit factor |
| --- | ---: | ---: | ---: | ---: | ---: |
| 原本通过 `dir_htf>=0.5` | `3089` | `510.01x` | `51.47%` | `2.67` | `2.83` |
| `0 < dir_htf < 0.5` | `3075` | `114.93x` | `47.77%` | `2.81` | `2.57` |
| `dir_htf <= 0` | `2944` | `65.90x` | `45.79%` | `2.75` | `2.32` |

结论：接受 `remove_final_filter_dir_htf` 作为 `HYPE-5M-PBTR-V3` 独立高频候选继续测。它不替代 V2.1A，因为胜率更低、交易频率约为 V2.1A 的 `2.9x`，执行滑点、订单失败和限价错过风险都会被放大。

并行观察的中间版：

```text
V3-lite = V2.1A + dir_htf >= 0
```

`V3-lite` 在实盘成本下为 `6254` 笔、年化 `36579.67x`、胜率 `49.70%`、payoff `2.75`、最大回撤 `-7.95%`。它保留“高周期至少同向”的解释性，适合作为 V3 的低风险对照。

V3 全参数消融审计补充：

- `min_hold_bars=6` 和 `trail_atr=0.75` 仍是核心。删除 `min_hold` 后策略直接失效；删除 trailing 后胜率仅约 `9.55%`。
- `min_hold_bars=9` 在样本内进一步抬升收益和胜率，但最大回撤扩大到约 `-10.03%`，应视为 V3.1 研究方向，而不是 V3 即时替换。
- 年化异常来自高频复利和右尾 payoff：全样本 `9108` 笔，约 `23.43` 笔/天；平均单笔 `+0.1691%`，中位单笔 `-0.0179%`，但平均盈利约为平均亏损的 `2.75x`。
- 执行敏感性极高：开仓滑点若升至当前假设 `2x`，权益倍数约降至 `4121x`；升至 `3x`，权益倍数约降至 `13x`；若再额外增加 `5 bps/成交`，策略会接近或直接失效。

### V2.1B: 去掉 ROC

Canonical name：`HYPE-5M-PBTR-V2.1B`

相对 V2.1-clean：

```text
min_dir_roc = -99
```

表现：

| 交易数 | 累计收益 | 年化 | 胜率 | payoff | profit factor | 最大回撤 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `2537` | `+25857.87%` | `185.51x` | `52.38%` | `2.77` | `3.05` | `-7.01%` |

结论：低风险进一步简化，收益略高于 V2.1-clean，胜率基本不变。可作为 clean-plus 候选。

### V2.1C: HTF 提高

Canonical name：`HYPE-5M-PBTR-V2.1C-HTF`

相对 V2.1-clean：

```text
final dir_htf >= 0.688442
```

表现：

| 交易数 | 累计收益 | 年化 | 胜率 | payoff | profit factor | 最大回撤 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `1823` | `+9291.22%` | `71.37x` | `53.70%` | `2.85` | `3.31` | `-7.27%` |

结论：胜率和盈亏比提高，但交易数与收益显著下降，最大回撤略变差。更适合作为胜率体验分支，而不是主收益分支。

### V2.1C: ADX14

Canonical name：`HYPE-5M-PBTR-V2.1C-ADX14`

相对 V2.1-clean：

```text
min_adx = 14
```

表现：

| 交易数 | 累计收益 | 年化 | 胜率 | payoff | profit factor | 最大回撤 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `2351` | `+21135.18%` | `153.61x` | `53.08%` | `2.79` | `3.16` | `-7.01%` |

结论：比 HTF 提高更温和，胜率和 profit factor 提高，最大回撤不变，但收益低于 V2.1-clean。若目标是实盘体验优化，优先级高于 `V2.1C-HTF`。

## Signal Logic

### Direction

```text
spread = EMA21 - EMA96
side = +1 if spread > 0
side = -1 if spread < 0
```

高周期方向：

```text
htf_spread = EMA96 - EMA384
dir_htf = side * htf_spread
```

方向化指标：

```text
dir_roc = side * ROC(roc_window)
dir_rsi = RSI14 for long, 100 - RSI14 for short
dir_cmf = side * CMF20
```

### Long Entry

当前 K 收盘时：

1. `EMA21 > EMA96`。
2. `regime_age >= 3` 且 `regime_age <= 2000`。
3. `abs(close / EMA21 - 1) <= 0.06`。
4. `dir_roc >= -0.01`。
5. `55 <= RSI14 <= 72`。
6. `CHOP14 <= 62`。
7. `CMF20 >= -0.30`。
8. `low <= EMA21 * (1 + pullback_buffer)`。
9. `close > EMA21`。
10. `close > open`。
11. `dir_htf >= threshold`。

下一根 5m K 开盘做多。

### Short Entry

当前 K 收盘时：

1. `EMA21 < EMA96`。
2. `regime_age >= 3` 且 `regime_age <= 2000`。
3. `abs(close / EMA21 - 1) <= 0.06`。
4. `-ROC(roc_window) >= -0.01`。
5. `55 <= 100 - RSI14 <= 72`。
6. `CHOP14 <= 62`。
7. `-CMF20 >= -0.30`。
8. `high >= EMA21 * (1 - pullback_buffer)`。
9. `close < EMA21`。
10. `close < open`。
11. `dir_htf >= threshold`。

下一根 5m K 开盘做空。

## Exit Logic

开仓后前 `6` 根 K 不执行策略退出。第 7 根 K 起开始执行 stop/target/trailing。

### Long

```text
initial_stop = entry_price - stop_atr * ATR14(signal_bar)
target = entry_price + tp_atr * ATR14(signal_bar)
trail_stop = max(initial_stop, previous_peak - trail_atr * ATR14(current_bar))
```

V2 的 `tp_atr=99`，历史上固定止盈不会触发，实际由 trailing stop 平仓。

### Short

```text
initial_stop = entry_price + stop_atr * ATR14(signal_bar)
target = entry_price - tp_atr * ATR14(signal_bar)
trail_stop = min(initial_stop, previous_trough + trail_atr * ATR14(current_bar))
```

## Live Trailing Implementation

交易所原生 trailing stop 通常使用百分比 callback，不能精确表达本策略的 ATR trailing 规则。因此实盘建议由策略程序维护 reduce-only stop-market 订单。

实盘流程：

1. K0 收盘确认信号。
2. K1 开盘成交。
3. 本地状态记录 `entry_price`、`entry_ts`、`entry_atr`、`side`、`bars_held`、`peak/trough`。
4. 前 6 根 K 不挂策略退出单，或只挂独立灾难保护单。
5. 第 6 根 K 收盘后，计算第一张 trailing stop，并提交 reduce-only stop-market。
6. 每根 5m K 收盘后更新 peak/trough 和 ATR14，若 stop 需要向有利方向移动，则 cancel/replace。
7. stop 成交后立刻清理本地状态，并撤销任何残留 reduce-only 订单。
8. 程序重启时必须从交易所仓位和本地 SQLite/audit DB 恢复状态。

多头 stop 只能上移，空头 stop 只能下移。不能因为 ATR 变大而放宽已有 stop。

## Return Source

`HYPE-5M-PBTR` 的收益来源不是高胜率小止盈，而是：

1. HYPE `5m` 趋势恢复存在可交易惯性。
2. 回踩/反抽 EMA21 后重新站回趋势方向，过滤了纯追高/追空。
3. `min_hold_bars=6` 给趋势恢复留出时间，避免 5m 噪声过早止损。
4. `trail_atr=0.75` 及时锁住浮盈，使大量小趋势恢复交易变成正期望。
5. V2 删除固定止盈后，让更大的顺风路径由 trailing stop 接管，提高 payoff。
6. 多空都有效，说明收益不是单纯来自一段上涨行情。

主要风险：

- 该策略高度依赖 HYPE 的 5m 波动和趋势恢复结构。
- 年化受高频复利放大，不可直接当作实盘收益承诺。
- 执行滑点、订单限频、reduce-only 订单管理和异常恢复会显著影响结果。
- V2 胜率低于 V1，实盘体验会更波动。

## Current Decision

当前建议：

1. `HYPE-5M-PBTR-V1` 作为胜率体验基线 dry-run。
2. `HYPE-5M-PBTR-V2.1-clean` 作为 V2 的首选简化表达，用于后续解释、实现和 dry-run 对照。
3. `HYPE-5M-PBTR-V2.1A` 作为高收益候选 dry-run，但需要接受胜率下降和周度波动增加。
4. `HYPE-5M-PBTR-V3` 作为独立高频候选 dry-run，不替代 V2.1A；先用小资金或 paper 跑 `300-500` 笔。
5. `V3-lite = V2.1A + dir_htf >= 0` 作为 V3 的低风险对照，验证“至少高周期同向”是否能保留大部分收益。
6. `HYPE-5M-PBTR-V2.1B` 作为 clean-plus 候选，可用于验证去掉 ROC 后是否保持行为稳定。
7. `HYPE-5M-PBTR-V2.1C-ADX14` 作为更温和的稳定体验候选；`V2.1C-HTF` 作为更严格但收益牺牲更大的对照。
8. V2/V2.1/V3 系列都不应直接大资金上线，先跑 `300-500` 笔。

V2 实盘验收线：

- `300` 笔后净胜率 `>=54%`。
- payoff `>=2.0`。
- profit factor `>=1.5`。
- 多头和空头都不能单边失效。
- 实际滑点若超过回测假设 `2x`，必须重新压测。

V3 高频验收线：

- `300-500` 笔后 profit factor `>=1.8`。
- payoff `>=2.2`。
- 净胜率允许低至 `47%-50%`，但不能持续低于 `47%`。
- `dir_htf<=0` 桶不能单独失效。
- 必须单独记录开仓滑点、限价错过、订单失败、maker/taker 占比和重启恢复事件。

## Reports

- `ablations/hype-5m-r05732-strategy-ablation-2026-06-23.md`
- `research-notes/hype-5m-pullback-trail-v2-combo-test-2026-06-23.md`
- `ablations/hype-5m-pullback-trail-v2-live-cost-ablation-slices-2026-06-23.md`
- `ablations/hype-5m-pullback-trail-v21-live-cost-variants-2026-06-23.md`
- `diagnostics/hype-5m-pbtr-final-filter-dir-htf-diagnostic-2026-06-24.md`
- `diagnostics/hype-5m-pbtr-v21a-remove-final-htf-live-cost-2026-06-24.md`
- `diagnostics/hype-5m-pbtr-v3-ablation-audit-2026-06-24.md`

## Reproduction

- `archive/scripts/research/ablate_hype_5m_r05732.py`
- `archive/scripts/research/test_hype_5m_r05732_v2_combos.py`
- `archive/scripts/research/research_hype_5m_pbtr_v2_live_cost_ablation_slices.py`
- `archive/scripts/research/research_hype_5m_pbtr_v21_live_cost_variants.py`
- `reports/hype_5m_r05732_ablation.json`
- `reports/hype_5m_r05732_v2_combo_test.json`
- `reports/hype_5m_pbtr_v2_live_cost_ablation_slices.json`
- `reports/hype_5m_pbtr_v21_live_cost_variants.json`
- `reports/hype_5m_pbtr_v21a_remove_final_htf_live_cost_diagnostic.json`
- `reports/hype_5m_pbtr_v3_ablation_audit.json`
- `reports/hype_5m_pbtr_v3_audit_metrics.json`

