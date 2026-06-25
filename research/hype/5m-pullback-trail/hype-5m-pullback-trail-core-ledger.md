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
- 数据范围：本地数据湖全量，约 `2025-05-30 10:30 UTC` 到 `2026-06-25 05:50 UTC`。
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
| V4 | 来自 V3.3 样本内增强组合；严格 live-realistic trailing 口径下不再作为实盘交接版本。 |
| V5 | executable-first 修复批次；V5/V5.1/V5.2 均未形成可交接生产版本。 |
| V6 | 当前可实盘表达的 paper 候选：强动量多头回踩恢复 + 入场即固定 bracket + 时间退出。 |
| 后缀  | 若后续只是改变过滤强度或执行保护，可用 V6.x；若改变核心机制，再升 V7。           |

文件命名规则：后续新建文件若包含带小数点的版本号，必须用连字符保留层级，例如 `HYPE-5M-PBTR-V3.2` 写作 `v3-2`，不要写成 `v32`，避免和未来 `V32` 混淆。


## Version Table


| 版本                | 核心变化                                                                                                | 状态                              | 全样本交易  | 年化        | 胜率       | payoff | 最大回撤     | 最差切片胜率   | 结论                                |
| ----------------- | --------------------------------------------------------------------------------------------------- | ------------------------------- | ------ | --------- | -------- | ------ | -------- | -------- | --------------------------------- |
| `HYPE-5M-PBTR-V1` | R05732 基线：`pullback_buffer=0.0025`，`tp_atr=1.875`，`stop_atr=0.75`，`dir_htf>=0.688442`               | live dry-run candidate          | `1341` | `14.97x`  | `54.29%` | `2.37` | `-7.77%` | `52.74%` | 实盘成本下收益仍为正，但胜率体验弱于旧默认成本口径。            |
| `HYPE-5M-PBTR-V2` | 同步微调：`pullback_buffer=0.01`，删除固定止盈，`stop_atr=0.5`，`roc_window=96`，`min_efficiency=0`，`dir_htf>=0.5` | research live-dry-run candidate | `2519` | `181.87x` | `52.44%` | `2.77` | `-7.01%` | `50.49%` | 实盘成本下仍明显优于 V1，频率和收益提高但胜率下降。 |
| `HYPE-5M-PBTR-V2.1-clean` | V2 实盘成本口径简化：固定/移除不生效参数，保留核心入场与 ATR trailing exit。                                      | preferred simplified V2 expression | `2521` | `181.96x` | `52.44%` | `2.77` | `-7.01%` | 见报告 | 与 V2 实盘成本表现几乎一致，适合作为新解释/实现基线。 |
| `HYPE-5M-PBTR-V2.1A` | 在 V2.1-clean 上放开 RSI 上下界。                                                                      | live monitor only                | `3146` | `352.15x` | `51.40%` | `2.64` | `-6.62%` | 见报告 | 严格 live-realistic 口径 PF 降至 `0.54`；本地 dry-run ledger 与即时 1ATR 止盈审计均未修复旧 stop 价入账问题，不应扩仓。 |
| `HYPE-5M-PBTR-V2.1B` | 在 V2.1-clean 上去掉 `min_dir_roc`。                                                                  | clean-plus candidate            | `2537` | `185.51x` | `52.38%` | `2.77` | `-7.01%` | 见报告 | 低风险进一步简化，收益略升，行为接近 V2.1-clean。 |
| `HYPE-5M-PBTR-V2.1C-HTF` | 在 V2.1-clean 上提高最终 `dir_htf` 阈值到 `0.688442`。                                                  | stable candidate                | `1823` | `71.37x`  | `53.70%` | `2.85` | `-7.27%` | 见报告 | 胜率和盈亏比提高，但交易数和收益显著下降，回撤略变差。 |
| `HYPE-5M-PBTR-V2.1C-ADX14` | 在 V2.1-clean 上加入 `min_adx=14`。                                                               | stable candidate                | `2351` | `153.61x` | `53.08%` | `2.79` | `-7.01%` | 见报告 | 更温和的稳定版，胜率提高且回撤不变，收益低于 clean。 |
| `HYPE-5M-PBTR-V3` | 独立高频候选：在 V2.1A 上移除 final `dir_htf` 过滤。                                                        | high-frequency research candidate | `9108` | `1544745.29x` | `48.39%` | `2.75` | `-7.95%` | 见诊断 | 交易数约为 V2.1A 的 `2.9x`，收益极高但执行敏感性显著提高；只适合小资金 dry-run。 |
| `HYPE-5M-PBTR-V3.1` | V3 上将 `min_hold_bars` 从 `6` 提高到 `9`。                                                        | high-frequency research candidate | `7263` | `212733795.80x` | `55.43%` | `3.38` | `-10.03%` | 见诊断 | 样本内显著增强胜率/PF，但回撤扩大；必须先小资金或 paper 验证。 |
| `HYPE-5M-PBTR-V3.2` | V3.1 上删除剩余无贡献/负贡献入场过滤器，仅保留方向、pullback、min-hold 和 trailing。                             | preferred clean V3 expression | `8025` | `1324019761.54x` | `55.66%` | `3.31` | `-8.69%` | 见诊断 | 参数更简洁，收益和回撤均优于 V3.1；先作为 paper/dry-run 首选表达验证。 |
| `HYPE-5M-PBTR-V3.3` | V3.2 的最小复现表达：删除所有兼容/关闭/保护/基本不触发参数，退出仅保留 `min_hold + ATR trailing`。 | archived research candidate | `8027` | `1327928815.51x` | `55.66%` | `3.31` | `-8.69%` | 见诊断 | 严格 live-realistic PF 降至 `0.58`；即时 TP 网格最佳 `2.5ATR` PF 仅 `0.615`，不再作为交接版本。 |
| `HYPE-5M-PBTR-V4` | V3.3 有效单因子增强项组合：`EMA9/96 + stop_atr=0.25 + trail_atr=0.5 + min_hold_bars=18`。 | paper-live audit candidate | `5053` | `28884173450807.53x` | `72.95%` | `7.39` | `-11.27%` | 见审计 | 样本内显著强于 V3.3，但高度依赖锁仓期和 stop 成交质量；只能 paper-live/极小资金审计。 |
| `HYPE-5M-PBTR-V6` | 可执行修复版：`EMA21/55` 多头回踩恢复 + `dir_ret192_bps>=788.123` + 入场即 `TP=3ATR/SL=7ATR` + `36` 根 K 超时。 | paper audit candidate | `147` | `1.70x` | `59.86%` | `1.15` | `-11.28%` | OOS PF `1.45` | 放弃旧 `min_hold + trailing` 成交假设，当前只允许 paper audit / 极小资金 dry-run，不是生产 sizing 版本。 |

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

### V3.1: Min Hold 9

Canonical name：`HYPE-5M-PBTR-V3.1`

来源报告：`diagnostics/hype-5m-pbtr-v31-min-hold-9-2026-06-24.md`。

交易路径图：`artifacts/hype-5m-pbtr-v31-min-hold-9-trade-path-2026-06-24.html`。

相对 V3：

```text
min_hold_bars = 9
```

不改变：

```text
final dir_htf filter = disabled
EMA21/EMA96
pullback_resume
pullback_buffer = 0.01
min_dir_rsi = 0
max_dir_rsi = 100
stop_atr = 0.5
tp_atr = 99
trail_atr = 0.75
```

表现：

| 交易数 | 累计收益 | 年化 | 胜率 | payoff | profit factor | 最大回撤 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `7263` | `+73027584242.88%` | `212733795.80x` | `55.43%` | `3.38` | `4.20` | `-10.03%` |

结论：V3.1 在样本内显著优于 V3，交易数减少但胜率、payoff 和 PF 同时提高；主要代价是风险释放更晚，最大回撤扩大到约 `-10%`。由于 V3.1 来自 V3 消融中的样本内强增强项，不能直接替代 V3 生产化，只能作为高收益研究候选进入小资金/paper dry-run。

### V3.2: Clean Entry Filters

Canonical name：`HYPE-5M-PBTR-V3.2`

来源报告：`diagnostics/hype-5m-pbtr-v32-clean-entry-filters-2026-06-24.md`。

全参数消融：`ablations/hype-5m-pbtr-v32-full-parameter-ablation-2026-06-24.md`。

相对 V3.1：

```text
min_regime_age = 0
min_dir_roc = -99
max_chop = 100
```

已失活或保持删除：

```text
final dir_htf filter = disabled
dir_rsi = 0/100
max_dist_ema = 99
min_dir_cmf = -99
require_htf = false
```

保留：

```text
EMA21/EMA96 direction
pullback_resume
pullback_buffer = 0.01
stop_atr = 0.5
tp_atr = 99
trail_atr = 0.75
min_hold_bars = 9
```

表现：

| 交易数 | 累计收益 | 年化 | 胜率 | payoff | profit factor | 最大回撤 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `8025` | `+511233263595.07%` | `1324019761.54x` | `55.66%` | `3.31` | `4.15` | `-8.69%` |

结论：V3.2 达成参数简化目标，入场侧只保留方向和 pullback/resume 结构，样本内相对 V3.1 交易数增加、胜率略升、回撤改善，PF 仅小幅下降。它更适合作为 V3.1 的干净表达进入 paper/dry-run，但仍必须验证新增交易在真实执行中的滑点、订单失败和容量影响。

全参数消融补充：

- 恢复 `final_htf`、`min_regime_age`、`min_dir_roc`、`max_chop`、`RSI`、`CMF`、`MACD/OBV/HTF require` 等旧入场过滤器，整体都降低总收益；V3.2 不应加回这些过滤器。
- 换入场形态会显著降收益，说明核心入场仍是 `pullback_resume`。
- 删除 `min_hold` 或 trailing 会显著破坏表现，说明收益仍来自 `min_hold + ATR trailing` 的路径管理。
- `trail_atr=0.5`、`min_hold_bars=12`、`stop_atr=0.25` 是下一轮 V3.3 研究候选，不在本轮直接替代 V3.2。

### V3.3: Minimal Live Spec

Canonical name：`HYPE-5M-PBTR-V3.3`

来源报告：`diagnostics/hype-5m-pbtr-v3-3-minimal-2026-06-24.md`。

实盘规格：`live-specs/hype-5m-pbtr-v3-3-live-spec.md`。

全参数消融：`ablations/hype-5m-pbtr-v3-3-full-parameter-ablation-2026-06-24.md`。

相对 V3.2，V3.3 删除所有已经证明无贡献、仅兼容保留、关闭、有限值保护或基本不触发的参数：

```text
side_mode / entry_style / donchian / roc_window
regime_age / breakout_buffer / max_dist_ema
ROC / RSI / ADX / CHOP / RVOL / CMF / MACD / OBV / HTF / efficiency filters
tp_atr / max_hold_bars / exit_ema / cooldown_bars / final_dir_htf_filter
```

保留的最小策略表达：

```text
EMA21/EMA96 direction
pullback_buffer = 0.01
stop_atr = 0.5
trail_atr = 0.75
min_hold_bars = 9
```

表现：

| 交易数 | 累计收益 | 年化 | 胜率 | payoff | profit factor | 最大回撤 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `8027` | `+512839871573.17%` | `1327928815.51x` | `55.66%` | `3.31` | `4.15` | `-8.69%` |

结论：V3.3 与 V3.2 的样本内行为几乎一致，仅因移除旧代码中额外 NaN 预热保护多出 `2` 笔交易；这证明 V3.2 live spec 中的兼容/关闭/保护项可以从实盘交接文档中完全移除。后续同事实盘复现优先按 V3.3，而不是 V3.2 的大参数表。

全参数消融补充：

- V3.3 的 6 个参数都是真正参与行为的参数，不能再像 V3.2 兼容项那样继续删除。
- `min_hold_bars=0/3/6` 明显破坏表现，其中 `min_hold_bars=0` 使策略接近归零；`min_hold_bars` 是核心路径参数。
- `trail_atr=1.0/1.5/2.0` 明显削弱收益；`trail_atr=0.5` 是有效样本内增强候选，但需要组合消融和 paper-live 验证。
- `trail_atr=0` 虽数学结果极强，但会把 stop 贴到前高/前低，属于不可实盘复现的退化边界，必须剔除。
- `stop_atr=0.25`、`min_hold_bars=12/18` 也是样本内增强候选，但都属于更激进/更紧的退出路径，不能直接替代 V3.3。

### V4: Combo Candidate Live-Viability Audit

Canonical name：`HYPE-5M-PBTR-V4`

组合测试：`diagnostics/hype-5m-pbtr-v3-4-combo-candidates-2026-06-24.md`。

实盘可行性审计：`diagnostics/hype-5m-pbtr-v4-live-viability-audit-2026-06-24.md`。

组合测试来自 V3.3 全参数消融中的有效单因子增强项，排除：

```text
trail_atr = 0      # 不可实盘复现的退化边界
min_hold_bars = 24 # 样本内回撤过大
```

当前最强实用候选：

```text
ema_fast = 9
ema_slow = 96
pullback_buffer = 0.01
stop_atr = 0.25
trail_atr = 0.5
min_hold_bars = 18
```

表现：

| 交易数 | 累计收益 | 年化 | 胜率 | payoff | profit factor | 最大回撤 | 最差切片 PF |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `5053` | `+21205868389324788.00%` | `28884173450807.53x` | `72.95%` | `7.39` | `19.92` | `-11.27%` | `16.59` |

实盘可行性审计补充：

- V4 入场只依赖 EMA、K 线和 ATR，不是不可计算策略。
- V4 基础压力下仍能承受较高额外成本；例如 `entry_slippage=3x` 后 PF 仍约 `9.64`，`stop_extra=20bps` 后 PF 仍约 `5.53`。
- 但 V4 几乎完全依赖 stop/trailing stop 成交，stop 出场占比约 `99.98%`。
- `stop_atr=0.25` 的初始止损非常紧，初始止损距离中位数约 `10.30 bps`。
- 前 `18` 根 K 的锁仓期内，约 `98.89%` 的交易曾触及 `0.25 ATR` 初始止损。
- 若实盘从开仓即挂 `0.25 ATR` 保护止损，反事实回测会变成 PF `0.17`、最大回撤约 `-100%`。

结论：V4 不是明显的回测代码幻觉，但它确实依赖一个关键执行假设：开仓后前 `18` 根 K 不按 `0.25 ATR` 保护止损出场。它可以进入 paper-live / 极小资金 dry-run，但不能直接生产；必须先定义锁仓期保护风控，并审计真实 stop 滑点、保护止损触发率和订单失败率。

### V6: Live-Executable Momentum Pullback Bracket

Canonical name：`HYPE-5M-PBTR-V6`

候选发现：`diagnostics/hype-5m-pbtr-v6-live-executable-search-2026-06-25.md`。

稳健性复核：`diagnostics/hype-5m-pbtr-v6-candidate-robustness-2026-06-25.md`。

全参数消融：`ablations/hype-5m-pbtr-v6-full-parameter-ablation-2026-06-25.md`。

V6 是 `HYPE-5M-PBTR` 的核心机制切换版本：它不再使用旧 `min_hold_bars + ATR trailing`，而是把 V3.3 类 pullback 触发器降级为事件源，再用强动量过滤选择高质量多头事件，并使用入场即可挂单表达的固定 bracket 和时间退出。

参数：

| 参数 | 值 |
| --- | --- |
| `timeframe` | `5m` |
| `side_mode` | `long` |
| `ema_fast` | `21` |
| `ema_slow` | `55` |
| `pullback_buffer` | `0.01` |
| `require_candle` | `false` |
| `htf_threshold` | `0.5` |
| `quality_filter` | `dir_ret192_bps >= 788.123` |
| `tp_atr` | `3.0` |
| `sl_atr` | `7.0` |
| `trail_atr` | `0.0` |
| `time_exit_bars` | `36` |

信号：

```text
ema_fast = EMA(close, 21)
ema_slow = EMA(close, 55)
htf_spread = EMA(close, 96) - EMA(close, 384)
dir_ret192_bps = (close / close.shift(192) - 1) * 10000

long trend:
  ema_fast > ema_slow

pullback:
  low <= ema_fast * (1 + 0.01)

reclaim:
  close > ema_fast

quality:
  htf_spread >= 0.5
  dir_ret192_bps >= 788.123
```

第 `t` 根 5m K 收盘后才确认信号，最早在第 `t+1` 根 K 的 open 入场。连续同向信号仍做去重，单策略单仓，不叠仓。

退出：

```text
entry_price = next_open with observed entry slippage
atr = ATR14(signal_bar)
target = entry_price + 3.0 * atr
stop = entry_price - 7.0 * atr
timeout = entry_bar + 36 bars
```

入场后立即可以提交 reduce-only TP/SL。若某根 K 同时触及 TP 和 SL，回测按保守 stop first。若到 `36` 根 K 仍未触发 TP/SL，则按到期 open 市价退出。V6 不使用 trailing stop。

表现：

| 区间 | 交易数 | 总收益 | PF | 胜率 | payoff | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| full | `147` | `+76.43%` | `1.72` | `59.86%` | `1.15` | `-11.28%` |
| IS `2025-05-30 -> 2026-03-01` | `92` | `+46.40%` | `1.75` | `58.70%` | `1.23` | `-11.28%` |
| VAL `2026-03-01 -> 2026-06-01` | `45` | `+18.07%` | `1.72` | `62.22%` | `1.04` | `-7.94%` |
| OOS `2026-06-01 -> 2026-06-25 05:55 UTC` | `10` | `+2.07%` | `1.45` | `60.00%` | `0.96` | `-3.38%` |

退出分布：

```text
target = 73
time_open = 72
stop_market = 2
```

全参数消融结论：

- 删除 `dir_ret192_bps >= 788.123` 后全样本 `617` 笔、收益 `-63.06%`、PF `0.81`、最大回撤 `-66.09%`；事件质量过滤是 V6 的生死线。
- `quality_window=192` 是当前唯一通过的动量窗口；`48/96/384` 均失败。
- `side_mode=long` 是核心；`short` 亏损，`both` 回撤扩大且平均每笔过薄。
- `EMA21/55` 是当前最稳趋势定义；EMA 变体没有通过 robust gate。
- `pullback_buffer=0.005/0.015` 仍通过但收益明显下降；`0.01` 保留为 V6 主定义。
- `htf_threshold=0/0.25/0.5` 均通过，`0.5` 暂因解释性保留。
- `TP=2.5ATR` 也通过，`TP=4/5/6ATR` 全样本更高但 OOS 交易数不足；V6 暂保留 `3ATR`。
- `SL=6/8/10ATR` 与 `7ATR` 行为接近，说明 stop 不是单点过拟合；过紧的 `3ATR` 失败。
- 加回 trailing 会显著降收益；V6 不应回到旧 trailing 状态机。
- `time_exit_bars=24` 仍通过但收益下降；`36` 保留为主定义。

结论：V6 是当前最干净的可执行修复方向，但它仍只是 paper audit candidate。生产 sizing 前必须先有 paper runner 记录全部原始触发、拒绝原因、接受信号、虚拟订单、真实盘口可成交性、重启恢复和 order idempotency。

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
3. `HYPE-5M-PBTR-V2.1A` 已进入实盘/实盘 dry-run，但严格 live-realistic 口径失效；不应扩仓，只能极小资金监控并用真实成交日志重新验收。
4. `HYPE-5M-PBTR-V3` 作为独立高频候选 dry-run，不替代 V2.1A；先用小资金或 paper 跑 `300-500` 笔。
5. `HYPE-5M-PBTR-V3.1` 作为 V3 的 `min_hold_bars=9` 高收益研究候选，不替代 V3；先用小资金或 paper 跑 `300-500` 笔，重点观察回撤是否扩张。
6. `HYPE-5M-PBTR-V3.2` 作为 V3.1 的 clean 表达保留历史记录。
7. `HYPE-5M-PBTR-V3.3` 作为 V3.2 的最小复现表达进入 paper/dry-run；同事实盘交接优先使用 V3.3 live spec。
8. `HYPE-5M-PBTR-V4` 记录自原 V3.4-candidate；样本内显著强于 V3.3，但严格 live-realistic 口径已失效，不应进入直接 paper-live 交接。
9. `HYPE-5M-PBTR-V6` 正式记录为当前最可执行的 paper audit candidate。它放弃旧 `min_hold_bars + trailing`，使用强动量多头回踩恢复、入场即固定 bracket、36 根 K 时间退出；下一步优先写 paper audit runner。
10. `V3-lite = V2.1A + dir_htf >= 0` 作为 V3 的低风险对照，验证“至少高周期同向”是否能保留大部分收益。
11. `HYPE-5M-PBTR-V2.1B` 作为 clean-plus 候选，可用于验证去掉 ROC 后是否保持行为稳定。
12. `HYPE-5M-PBTR-V2.1C-ADX14` 作为更温和的稳定体验候选；`V2.1C-HTF` 作为更严格但收益牺牲更大的对照。
13. V2/V2.1/V3/V3.1/V3.2/V3.3/V4/V6 系列都不应直接大资金上线；V6 的下一步不是直接真钱生产，而是 paper runner 和 walk-forward 阈值固化。

V2 实盘验收线：

- `300` 笔后净胜率 `>=54%`。
- payoff `>=2.0`。
- profit factor `>=1.5`。
- 多头和空头都不能单边失效。
- 实际滑点若超过回测假设 `2x`，必须重新压测。

V3/V3.1/V3.2/V3.3/V4 高频验收线：

- `300-500` 笔后 profit factor `>=1.8`。
- payoff `>=2.2`。
- 净胜率允许低至 `47%-50%`，但不能持续低于 `47%`。
- `dir_htf<=0` 桶不能单独失效。
- 必须单独记录开仓滑点、限价错过、订单失败、maker/taker 占比和重启恢复事件。
- V3.1 额外要求：实盘/paper 最大闭合权益回撤不能显著劣于 V3，同期回撤若超过 `1.5x` 应暂停升级。
- V3.2 额外要求：新增交易不能单独失效；paper 中新增交易子集 PF 若低于 `1.5`，应回退到 V3.1。
- V3.3 额外要求：paper-live 交易流应与 V3.2 参考实现基本一致；若实盘复现少算/多算大量信号，优先检查 EMA/ATR 预热、K 线收盘确认和连续同向信号去重。
- V4 额外要求：必须单独审计 `stop_atr=0.25`、`trail_atr=0.5` 和前 `18` 根 K 锁仓期的真实风控；若从开仓即挂保护止损导致大面积扫损，或不挂保护止损导致尾部风险不可接受，应回退 V3.3。

V6 paper audit 验收线：

- 至少连续 `30-50` 笔 paper 订单后再评估是否进入极小资金。
- paper 订单必须记录所有原始触发、质量过滤拒绝原因、接受信号、TP/SL/timeout 虚拟成交、真实盘口可成交性和订单维护事件。
- `30-50` 笔后 PF 应保持 `>=1.2`，平均每笔应保持 `>0`，最大闭合权益回撤不应超过回测级别的 `1.5x`。
- 若 `dir_ret192_bps` 阈值附近的 walk-forward 固化无法维持正期望，V6 不进入真钱。

## Reports

- `ablations/hype-5m-r05732-strategy-ablation-2026-06-23.md`
- `research-notes/hype-5m-pullback-trail-v2-combo-test-2026-06-23.md`
- `ablations/hype-5m-pullback-trail-v2-live-cost-ablation-slices-2026-06-23.md`
- `ablations/hype-5m-pullback-trail-v21-live-cost-variants-2026-06-23.md`
- `diagnostics/hype-5m-pbtr-v21a-live-realistic-audit-2026-06-24.md`
- `diagnostics/hype-5m-pbtr-final-filter-dir-htf-diagnostic-2026-06-24.md`
- `diagnostics/hype-5m-pbtr-v21a-remove-final-htf-live-cost-2026-06-24.md`
- `diagnostics/hype-5m-pbtr-v3-ablation-audit-2026-06-24.md`
- `diagnostics/hype-5m-pbtr-v31-min-hold-9-2026-06-24.md`
- `artifacts/hype-5m-pbtr-v31-min-hold-9-trade-path-2026-06-24.html`
- `diagnostics/hype-5m-pbtr-v32-clean-entry-filters-2026-06-24.md`
- `ablations/hype-5m-pbtr-v32-full-parameter-ablation-2026-06-24.md`
- `live-specs/hype-5m-pbtr-v3-2-live-spec.md`
- `diagnostics/hype-5m-pbtr-v3-3-minimal-2026-06-24.md`
- `live-specs/hype-5m-pbtr-v3-3-live-spec.md`
- `ablations/hype-5m-pbtr-v3-3-full-parameter-ablation-2026-06-24.md`
- `diagnostics/hype-5m-pbtr-v33-reinit-trailing-2026-06-24.md`
- `diagnostics/hype-5m-pbtr-v3-4-combo-candidates-2026-06-24.md`
- `diagnostics/hype-5m-pbtr-v4-live-viability-audit-2026-06-24.md`
- `diagnostics/hype-5m-pbtr-fixed-bracket-search-2026-06-24.md`
- `diagnostics/hype-5m-pbtr-reset-bracket-search-2026-06-24.md`
- `diagnostics/hype-5m-pbtr-reset-bracket-maxhold48-2026-06-24.md`
- `diagnostics/hype-5m-pbtr-v6-live-executable-search-2026-06-25.md`
- `diagnostics/hype-5m-pbtr-v6-candidate-robustness-2026-06-25.md`
- `ablations/hype-5m-pbtr-v6-full-parameter-ablation-2026-06-25.md`

## Reproduction

- `research/hype/families/5m-pullback-trail/scripts/ablate_hype_5m_r05732.py`
- `research/hype/families/5m-pullback-trail/scripts/test_hype_5m_r05732_v2_combos.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v2_live_cost_ablation_slices.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v21_live_cost_variants.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v21a_live_realistic_audit.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v31_min_hold_9.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v32_clean_entry_filters.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v32_full_ablation.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3_minimal.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3_full_ablation.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_reinit_trailing.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-4_combo_candidates.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v4_live_viability_audit.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_fixed_bracket_search.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_reset_bracket_search.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_reset_bracket_maxhold48.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_live_executable_search.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_candidate_robustness.py`
- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_full_ablation.py`
- `artifacts/hype_5m_r05732_ablation.json`
- `artifacts/hype_5m_r05732_v2_combo_test.json`
- `artifacts/hype_5m_pbtr_v2_live_cost_ablation_slices.json`
- `artifacts/hype_5m_pbtr_v6_live_executable_search.json`
- `artifacts/hype_5m_pbtr_v6_candidate_robustness.csv`
- `artifacts/hype_5m_pbtr_v6_full_ablation.json`
- `artifacts/hype_5m_pbtr_v21_live_cost_variants.json`
- `artifacts/hype_5m_pbtr_v21a_live_realistic_audit.json`
- `artifacts/hype_5m_pbtr_v21a_remove_final_htf_live_cost_diagnostic.json`
- `artifacts/hype_5m_pbtr_v3_ablation_audit.json`
- `artifacts/hype_5m_pbtr_v3_audit_metrics.json`
- `artifacts/hype_5m_pbtr_v31_min_hold_9.json`
- `artifacts/hype_5m_pbtr_v32_clean_entry_filters.json`
- `artifacts/hype_5m_pbtr_v32_full_ablation.json`
- `artifacts/hype_5m_pbtr_v3-3_minimal.json`
- `artifacts/hype_5m_pbtr_v3-3_full_ablation.json`
- `artifacts/hype_5m_pbtr_v33_reinit_trailing.json`
- `artifacts/hype_5m_pbtr_v3-4_combo_candidates.json`
- `artifacts/hype_5m_pbtr_v4_live_viability_audit.json`
- `artifacts/hype_5m_pbtr_fixed_bracket_search.json`
- `artifacts/hype_5m_pbtr_reset_bracket_search.json`
- `artifacts/hype_5m_pbtr_reset_bracket_maxhold48.json`
