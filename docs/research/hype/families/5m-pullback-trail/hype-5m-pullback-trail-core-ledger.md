# HYPE-5M-PBTR 5m Pullback-Trail Core Ledger

Ledger id：`HYPE-5M-PBTR`

Parent routing family：`HYPE-EMA-TB`

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
- 手续费：单边 `0.04%`，开平合计 `0.08%`。
- 滑点：开仓 `0.01%`，平仓 `0.01%`。
- 杠杆：当前研究统一按 `1x`。
- 仓位：单策略单仓，不叠仓。
- 回撤口径：`HYPE-5M-PBTR` 主账使用真实开仓到实际平仓路径 MAE/MFE。

## Version Rules

| 层级 | 说明 |
| --- | --- |
| V1 | 第一版可实盘观察基线，来自 `HYPE_PP_R05732__dir_htf_ge_0.688442`。 |
| V2 | 基于 V1 全参数消融后的同步微调版本。 |
| 后缀 | 若后续只是改变过滤强度或执行保护，可用 V2A/V2B；若改变核心机制，再升 V3。 |

## Version Table

| 版本 | 核心变化 | 状态 | 全样本交易 | 年化 | 胜率 | payoff | 最大回撤 | 最差切片胜率 | 结论 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `HYPE-5M-PBTR-V1` | R05732 基线：`pullback_buffer=0.0025`，`tp_atr=1.875`，`stop_atr=0.75`，`dir_htf>=0.688442` | live dry-run candidate | `1340` | `29.07x` | `59.18%` | `2.58` | `-7.70%` | `58.29%` | 胜率体验更好，频率中等，适合作为第一版基线。 |
| `HYPE-5M-PBTR-V2` | 同步微调：`pullback_buffer=0.01`，删除固定止盈，`stop_atr=0.5`，`roc_window=96`，`min_efficiency=0`，`dir_htf>=0.5` | research live-dry-run candidate | `2515` | `548.67x` | `57.46%` | `2.79` | `-6.85%` | `56.23%` | 频率和收益显著提高，胜率略降；建议与 V1 并行 dry-run。 |

## V1 Specification

Canonical name：`HYPE-5M-PBTR-V1`

Source candidate：`HYPE_PP_R05732__dir_htf_ge_0.688442`

参数：

| 参数 | 值 |
| --- | ---: |
| `side_mode` | `both` |
| `ema_fast` | `21` |
| `ema_slow` | `96` |
| `entry_style` | `pullback_resume` |
| `pullback_buffer` | `0.0025` |
| `roc_window` | `48` |
| `min_regime_age` | `3` |
| `max_regime_age` | `2000` |
| `max_dist_ema` | `0.06` |
| `min_dir_roc` | `-0.01` |
| `min_dir_rsi` | `55` |
| `max_dir_rsi` | `72` |
| `max_chop` | `62` |
| `min_efficiency` | `0.025` |
| `stop_atr` | `0.75` |
| `tp_atr` | `1.875` |
| `trail_atr` | `0.75` |
| `min_hold_bars` | `6` |
| `max_hold_bars` | `576` |
| `final_filter` | `dir_htf >= 0.688442` |

表现：

| 切片 | 交易数 | 年化 | 胜率 | payoff | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: |
| full | `1340` | `29.07x` | `59.18%` | `2.58` | `-7.70%` |
| 2025-05-30~2025-09-01 | `350` | `22.98x` | `59.43%` | `2.22` | `-4.10%` |
| 2025-09-01~2025-12-01 | `350` | `113.91x` | `58.29%` | `3.17` | `-4.16%` |
| 2025-12-01~2026-03-01 | `173` | `9.75x` | `58.96%` | `2.74` | `-7.70%` |
| 2026-03-01~2026-06-01 | `328` | `13.82x` | `58.54%` | `2.37` | `-3.30%` |
| 2026-06-01~2026-06-23 | `139` | `530.16x` | `62.59%` | `2.19` | `-4.34%` |

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

| 参数 | 值 |
| --- | ---: |
| `side_mode` | `both` |
| `ema_fast` | `21` |
| `ema_slow` | `96` |
| `entry_style` | `pullback_resume` |
| `pullback_buffer` | `0.01` |
| `roc_window` | `96` |
| `min_regime_age` | `3` |
| `max_regime_age` | `2000` |
| `max_dist_ema` | `0.06` |
| `min_dir_roc` | `-0.01` |
| `min_dir_rsi` | `55` |
| `max_dir_rsi` | `72` |
| `max_chop` | `62` |
| `min_efficiency` | `0` |
| `stop_atr` | `0.5` |
| `tp_atr` | `99.0` |
| `trail_atr` | `0.75` |
| `min_hold_bars` | `6` |
| `max_hold_bars` | `576` |
| `final_filter` | `dir_htf >= 0.5` |

表现：

| 切片 | 交易数 | 年化 | 胜率 | payoff | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: |
| full | `2515` | `548.67x` | `57.46%` | `2.79` | `-6.85%` |
| 2025-05-30~2025-09-01 | `622` | `210.32x` | `56.91%` | `2.43` | `-5.64%` |
| 2025-09-01~2025-12-01 | `658` | `3290.48x` | `56.23%` | `3.08` | `-5.14%` |
| 2025-12-01~2026-03-01 | `391` | `237.61x` | `60.87%` | `2.95` | `-6.85%` |
| 2026-03-01~2026-06-01 | `607` | `137.91x` | `57.00%` | `2.61` | `-5.42%` |
| 2026-06-01~2026-06-23 | `237` | `184639.47x` | `57.81%` | `2.96` | `-4.39%` |

频率：

- 全样本约 `6.47` 笔/天，`45.29` 笔/周，`196.92` 笔/月。
- forward 约 `10.69` 笔/天。

交易结构：

- 多头：`1364` 笔，胜率 `56.96%`，payoff `2.69`，profit factor `3.57`。
- 空头：`1151` 笔，胜率 `58.04%`，payoff `2.90`，profit factor `4.01`。
- 退出：全部为 trailing stop，因为固定止盈被等效删除。
- 平均持仓：`7.22` 根 5m K，约 `36.1` 分钟。

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
2. `HYPE-5M-PBTR-V2` 作为主收益候选 dry-run。
3. V2 不应直接大资金上线，先跑 `300-500` 笔。

V2 实盘验收线：

- `300` 笔后净胜率 `>=54%`。
- payoff `>=2.0`。
- profit factor `>=1.5`。
- 多头和空头都不能单边失效。
- 实际滑点若超过回测假设 `2x`，必须重新压测。

## Reports

- `hype-5m-r05732-strategy-ablation-2026-06-23.md`
- `hype-5m-pullback-trail-v2-combo-test-2026-06-23.md`

## Reproduction

- `archive/scripts/research/ablate_hype_5m_r05732.py`
- `archive/scripts/research/test_hype_5m_r05732_v2_combos.py`
- `reports/hype_5m_r05732_ablation.json`
- `reports/hype_5m_r05732_v2_combo_test.json`
