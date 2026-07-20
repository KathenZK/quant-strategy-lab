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

## Current State

- 当前版本：`HYPE-5M-PBTR-V6.2.1`。
- 状态：`live / tiny-live-pilot`，并行保留独立 `dry-run` 实例；两者均由当前 manifest 授权。
- tiny-live-pilot 授权截至 `2026-09-24T00:00:00Z` 复核，资金边界为专用子账户余额且不得未记录增资。
- 当前已通过研究/runtime 信号 parity；真实成交生命周期、保护单、重启恢复与滑点证据仍是生产 sizing blocker。
- 下一决策门：结合最新 [runner tracking](runner-tracking/hype-5m-pbtr-runner-2026-07-11.md) 复核 tiny-live-pilot，决定保持、停止或调整；不得把并行 dry-run 写成降级。

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
| V1  | 第一版历史基线，来自 `HYPE_PP_R05732__dir_htf_ge_0.688442`；strict live audit 后不再是可实盘观察候选。 |
| V2  | 基于 V1 全参数消融后的同步微调版本。                                 |
| V2.1 | 基于 V2 实盘成本消融后的参数简化和候选分支；不改变 `HYPE-5M-PBTR` 核心机制。       |
| V3 | 独立高频候选：来自 `V2.1A`，移除 final `dir_htf` 过滤；不直接替代 V2.1A。       |
| V4 | 来自 V3.3 样本内增强组合；严格 live-realistic trailing 口径下不再作为实盘交接版本。 |
| V3.3.1 | V3.3 的实盘 stop-arm retry overlay 记录版；修复订单可审计性，但历史 pre-dry-run 诊断未通过。 |
| V5 | executable-first 修复批次；V5/V5.1/V5.2 均未形成可交接生产版本。 |
| V6 | 当前可实盘表达的 paper 候选：强动量多头回踩恢复 + 入场即固定 bracket + 时间退出。 |
| V6.1 | V6 的 sizing/exit 变体：`TP=2.5ATR` + fixed `3x`，不改变核心入场机制。 |
| V6.2.1 | V6.2 的 long-leg HTF 阈值变体：long `htf_spread >= 0`，short leg 不变；用于 dry-run / 极小资金观察。 |
| 后缀  | 若后续只是改变过滤强度或执行保护，可用 V6.x；若改变核心机制，再升 V7。           |

文件命名规则：后续新建文件若包含带小数点的版本号，必须用连字符保留层级，例如 `HYPE-5M-PBTR-V3.2` 写作 `v3-2`，不要写成 `v32`，避免和未来 `V32` 混淆。


## Version Table


| 版本                | 核心变化                                                                                                | 状态                              | 全样本交易  | 年化        | 胜率       | payoff | 最大回撤     | 最差切片胜率   | 结论                                |
| ----------------- | --------------------------------------------------------------------------------------------------- | ------------------------------- | ------ | --------- | -------- | ------ | -------- | -------- | --------------------------------- |
| `HYPE-5M-PBTR-V1` | R05732 基线：`pullback_buffer=0.0025`，`tp_atr=1.875`，`stop_atr=0.75`，`dir_htf>=0.688442`               | historical pre-dry-run finding / not live-ready | `1358` | `14.91x`  | `54.20%` | `2.37` | `-7.77%` | 见诊断 | 旧 stop-price fill 口径仍赚钱；strict live-realistic PF `0.637`、总收益 `-87.29%`，不能作为回退上线版本。            |
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
| `HYPE-5M-PBTR-V3.3.1` | V3.3 + 实盘 stop-arm retry overlay：第 7 根尝试挂 stop，穿越时重试，第 10 根兜底市价。 | historical pre-dry-run finding / not live-ready | `8426` | `0.00x` | `40.17%` | `0.86` | `-100.00%` | 见诊断 | 1m 乐观口径 PF `0.580`；修复进程崩溃和审计问题，但保守/乐观 PF 均低于 `1`，上一单平仓价、五类入场过滤、退出 overlay、轻量 ML 事件质量筛选和 armed 后加仓均无效。 |
| `HYPE-5M-PBTR-V4` | V3.3 有效单因子增强项组合：`EMA9/96 + stop_atr=0.25 + trail_atr=0.5 + min_hold_bars=18`。 | registered / not promoted | `5053` | `28884173450807.53x` | `72.95%` | `7.39` | `-11.27%` | 见审计 | 样本内显著强于 V3.3，但高度依赖锁仓期和 stop 成交质量；不得直接进入 dry-run 或 live。 |
| `HYPE-5M-PBTR-V6` | 可执行修复版：`EMA21/55` 多头回踩恢复 + `dir_ret192_bps>=788.123` + 入场即 `TP=3ATR/SL=7ATR` + `36` 根 K 超时。 | registered / not promoted | `147` | `1.70x` | `59.86%` | `1.15` | `-11.28%` | OOS PF `1.45` | 放弃旧 `min_hold + trailing` 成交假设；未进入 dry-run，不是生产 sizing 版本。 |
| `HYPE-5M-PBTR-V6.1` | V6 sizing/exit 变体：`TP=2.5ATR/SL=7ATR/timeout=36`，fixed `3x`。 | registered sizing observation / not promoted | `157` | 见诊断 | `63.69%` | `1.01` | `-25.63%` | 见诊断 | 回测总收益 `+408.95%`、PF `1.773`；收益漂亮但 sizing 风险高，不是生产版本。 |
| `HYPE-5M-PBTR-V6.2` | V6.1 long-only + short rank2：long `EMA21/55 TP2.5/SL7/tx36`，short `EMA34/144 TP1.5/SL2/tx48`，组合严格单仓。 | registered / not promoted / not live-ready | `210` | 见诊断 | `64.76%` | `0.96` | `-22.38%` | OOS PF `1.439` | 由 `combo_short_rank2` 固化；总收益 `+833.71%`、PF `1.771`，但 short OOS 只有 `5` 笔。只允许 1x 或极小 notional 验证，不是生产版本。 |
| `HYPE-5M-PBTR-V6.2.1` | V6.2 的 long `htf_spread >= 0` 变体：long `EMA21/55 TP2.5/SL7/tx36`，short 仍为 V6.2 short rank2，组合严格单仓。 | live / tiny-live-pilot / forward-test required | `219` | 见诊断 | `64.38%` | `1.00` | `-22.35%` | OOS PF `1.439` | 来自 V6.2 full ablation 的 `long_htf_threshold_0p0`；fixed `3x` 总收益 `+1022.25%`、PF `1.804`，但 short OOS 仍只有 `5` 笔。2026-07-10 追认既有 tiny-notional live，截止 2026-07-24 复核；不是生产 sizing，仍缺真实成交生命周期验收。 |

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

strict live audit：`diagnostics/hype-5m-pbtr-v1-strict-live-audit-2026-06-27.md`。

更新到 `2026-06-26 04:15 UTC` 的严格可执行复核结果：

| 口径 | 交易数 | 总收益 | 年化 | 胜率 | PF | payoff | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `legacy stop-price fill` | `1358` | `+1713.55%` | `14.91x` | `54.20%` | `2.806` | `2.372` | `-7.77%` |
| `live-realistic` | `1357` | `-87.29%` | `0.15x` | `39.50%` | `0.637` | `0.976` | `-88.27%` |
| `entry protective stop` | `1852` | `-94.87%` | `0.06x` | `21.00%` | `0.510` | `1.918` | `-94.98%` |

结论：V1 旧口径确实赚钱，但严格 live-realistic 口径不赚钱。解锁时 stop 可正常挂上的比例只有 `31.47%`，`68.53%` 需要解锁市价退出；锁仓期曾触及初始 stop 的比例 `73.54%`，开仓即保护也会把 PF 压到 `0.510`。因此 V1 不是被后续版本简单“改坏”后才失效，V1 机制本身已经依赖 crossed/stale stop 或 target 的不可实盘成交假设，不能作为回退上线版本。

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

### V3.3.1: Retry-Arm Overlay

Canonical name：`HYPE-5M-PBTR-V3.3.1`

基础报告：`diagnostics/hype-5m-pbtr-v33-retry-arm-2026-06-26.md`。

上一单平仓价过滤测试：`diagnostics/hype-5m-pbtr-v3-3-1-prev-exit-filter-2026-06-27.md`。

no-initial-stop + pullback buffer 网格：`diagnostics/hype-5m-pbtr-v3-3-1-no-initial-stop-buffer-grid-2026-06-27.md`。

rescue search：`diagnostics/hype-5m-pbtr-v3-3-1-rescue-search-2026-06-27.md`。

rescue neighborhood：`diagnostics/hype-5m-pbtr-v3-3-1-rescue-neighborhood-2026-06-27.md`。

range10 早停止盈：`diagnostics/hype-5m-pbtr-v3-3-1-range10-take-profit-2026-06-27.md`。

combo overlay search：`diagnostics/hype-5m-pbtr-v3-3-1-combo-overlay-2026-06-27.md`。

filter directions：`diagnostics/hype-5m-pbtr-v3-3-1-filter-directions-2026-06-27.md`。

ML event quality：`diagnostics/hype-5m-pbtr-ml-event-quality-2026-06-27.md`。

armed-after pyramiding：`diagnostics/hype-5m-pbtr-v3-3-1-armed-pyramiding-2026-06-27.md`。

pb=0.005 + arm4：`diagnostics/hype-5m-pbtr-v3-3-1-pb005-arm4-2026-06-27.md`。

V3.3.1 是 V3.3 的实盘执行 overlay 记录版，不改变原始入场信号和 trailing 公式，只改变 stop arming 的线上状态机：

```text
第 1-6 根：不挂策略 trailing stop。
第 7 根开始：按原 trailing 规则计算 desired_stop 并尝试挂 reduce-only STOP_MARKET。
若 Binance 返回 -2021 / Order would immediately trigger：记录 stop_arm_rejected，并按短间隔 retry。
每根 5m K 收盘后仍按原 trailing 规则只允许收紧 stop。
第 9 根收盘后仍未 arm：第 10 根处理周期 reduce-only 市价平仓。
一旦 arm 成功：回到原 trailing stop 维护路径。
```

retry-arm 近似回测结果：

| 口径 | 交易数 | 胜率 | PF | payoff | 最大回撤 | armed | deadline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `5m_conservative` | `8344` | `40.33%` | `0.583` | `0.862` | `-100.00%` | `41.69%` | `58.31%` |
| `5m_optimistic` | `8752` | `39.41%` | `0.566` | `0.871` | `-100.00%` | `55.06%` | `44.94%` |
| `1m_conservative` | `8389` | `40.04%` | `0.574` | `0.860` | `-100.00%` | `43.96%` | `56.04%` |
| `1m_optimistic` | `8426` | `40.17%` | `0.580` | `0.863` | `-100.00%` | `45.10%` | `54.90%` |

上一单平仓价过滤规则：

```text
第一笔交易：无上一笔平仓价，允许入场。
后续 long：entry_price > previous_exit_price 才允许入场。
后续 short：entry_price < previous_exit_price 才允许入场。
比较使用含成本的模拟成交 entry_price / exit_price。
```

过滤测试结果：

| 口径 | 交易数 | 胜率 | PF | payoff | 最大回撤 | filter reject |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `5m_conservative_prev_exit_filter` | `6587` | `40.06%` | `0.581` | `0.869` | `-100.00%` | `39.09%` |
| `5m_optimistic_prev_exit_filter` | `6758` | `38.86%` | `0.560` | `0.881` | `-100.00%` | `40.35%` |
| `1m_conservative_prev_exit_filter` | `6613` | `39.69%` | `0.568` | `0.863` | `-100.00%` | `39.10%` |
| `1m_optimistic_prev_exit_filter` | `6612` | `39.75%` | `0.571` | `0.866` | `-100.00%` | `39.57%` |

结论：V3.3.1 修复的是实盘 stop-arm 失败时的进程稳定性、重试行为和审计字段，不修复 V3.3 原始优势依赖 stale/crossed stop 成交的问题。上一单平仓价过滤减少约 `39%-40%` 候选入场，但 PF 没有改善，仍不应提升为 paper/live 候选。

附加诊断：去掉初始止损价 floor 后，正向或轻微负向 `pullback_buffer` 大多仍为亏损结构；`pullback_buffer=-0.0100` 在四个 retry-arm 近似口径下均为正收益且 PF `>1`，其中 5m 乐观为 `37` 笔、累计收益 `+9.27%`、PF `1.477`、最大回撤 `-10.30%`。但该区域交易数极少，`-0.0125` 已转亏，`-0.0150` 只剩 `7` 笔，`-0.0200` 只剩 `1` 笔。因此这只能作为极严格深回踩事件质量线索，不是 V3.3.1 的可提升版本。

rescue search 进一步确认，V3.3.1 的可执行线索不在原始高频双向信号，而在低频 long-only 深回踩子集：

| 门槛 | 代表配置 | 四口径最少交易 | 四口径最差收益 | 四口径最差 PF | 最差回撤 |
| --- | --- | ---: | ---: | ---: | ---: |
| `>=30` | `pullback_buffer=-0.0075`、long-only、`ret192>=250`、`spread<=225` | `35` | `+16.93%` | `2.207` | `-4.58%` |
| `>=50` | `pullback_buffer=-0.0060`、long-only、`ret192>=250`、`spread<=150`、`close_pos>=0.55` | `53` | `+14.44%` | `1.602` | `-8.77%` |
| `>=60` | `pullback_buffer=-0.0060`、long-only、`ret192>=200`、`spread<=125` | `61` | `+9.66%` | `1.318` | `-9.14%` |

这些结果把“救活方向”从旧 V3.3.1 改写为事件质量筛选线索：深回踩、只做多、要求 16h 方向动量和 EMA spread 不过宽。样本仍只有几十笔到六十余笔，不能直接提升为 paper/live；下一步若继续，应做 walk-forward 阈值固化和月度切片，而不是扩大原始 V3.3.1 双向高频策略。

range10 早停止盈测试显示，开仓后若浮盈达到信号 K 最近 10 根 5m K 的平均振幅就提前平仓，不能修复原始 V3.3.1。5m/1m 重叠样本中，该 overlay 让约 `49%-51%` 交易提前止盈，胜率提升到约 `51%-53%`，但 payoff 降到约 `0.50-0.54`，四口径 PF 只有约 `0.55-0.56`，累计收益约 `-97%`。结论是它改善胜率观感但破坏盈亏比，不作为后续 rescue 方向。

组合式 overlay（入场即 emergency stop、浮盈后推保本、更高浮盈后 range10 trailing、早期无推进则 time exit）在全量 V3.3.1 上也失败。5m/1m 重叠样本中，四口径最优配置仍只有 min PF `0.285`、min total `-99.92%`、worst drawdown `-99.92%`。这说明全量原始信号质量太低，单靠退出 overlay 会变成大量小亏/止损，不能把噪声信号变成正期望。

昨晚实盘复盘提出的五类入场过滤方向也不能救回全量 V3.3.1。反抽实体强度、EMA21 斜率同向、回踩深度上限、ATR 稳定、1h EMA 大周期确认，以及少量组合过滤，在 `2026-03-25 00:00 UTC` 到 `2026-06-26 04:15 UTC` 的 1m/5m 重叠样本四口径复核中，全部 min PF 低于 `1`。最强 `combo_ret_spread` 最少 `690` 笔、min total `-66.01%`、min PF `0.634`；`ret192_same_ge_250` 最少 `879` 笔、min PF `0.633`。这些过滤能降噪，但仍是稳定负期望，只能作为低频 rescue 子集的特征，不是上线修复。

ML event-quality 测试也没有救回全量 V3.3.1。该实验对 `21451` 个 V3.3.1 触发事件生成 strict retry-arm 独立标签，使用 walk-forward `numpy` logistic/ridge 模型预测 `positive_net`、`bad_unlock`、`trailing_positive` 和 clipped `net_ret_1x`，每月只用历史训练，再选择 top `5%/10%/20%/30%` 事件做单仓 exact replay。最强 robust 行为 `ml_top_20pct` 四口径 min PF `0.585`、min total `-98.35%`、最少 `549` 笔；单口径最高 PF 为 `0.659`。模型确实把 trailing-positive rate 从 baseline 的 `27.35%` 小幅提高到最高 `29.61%`，但 bad unlock/deadline 仍约 `60%-62%`，说明“增加 trailing/armed 概率”不是充分目标。全量 V3.3.1 不应继续靠 ML 阈值救援；若继续 ML，只能转向 deep pullback long-only + 强动量/spread 的低频事件质量路线。

armed-after pyramiding 测试显示，“trailing/armed 后给盈利订单加杠杆”也不能救回全量 V3.3.1。网格覆盖 `add_mult=0.25/0.5/1.0`、stop cushion `0.1/0.3/0.5/0.8 ATR`、最大追价 `0.5/1.0/1.5 ATR`，并区分 stop 已锁利润的 `lock` 与仅 armed 后浮盈的 `nolock`。四口径 robust 最强配置等同不加仓 baseline，min PF `0.565`、min total `-96.92%`、worst drawdown `-96.99%`；宽松 `nolock` 虽能提高加仓触发率，但加仓腿平均收益仍为负。结论是新增腿以更差价格进场、共用同一 trailing stop，回打时会稀释原仓利润；该方向不应作为 rescue 或扩仓依据。

`pullback_buffer=0.005` 且第 4 根开始 stop-arm 的变体同样失败。它把 1m/5m 重叠样本原始信号数从 `5098` 降到 `4667`（`-8.45%`），但因更早 armed、平均持仓缩短，实际单仓交易数反而增加 `+7.81%` 到 `+16.93%`。armed 率提高约 `18.68%-20.49%`、deadline 率下降，但四口径 PF 全面变差，最差为 1m conservative `0.476`。结论是提前 trailing 能减少部分裸露/超时退出，却更早把噪声波动变成 stop 退出，不是 V3.3.1 rescue 方向。

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

结论：V6 是当前最干净的可执行修复方向之一，但它仍只是 registered / not promoted。生产 sizing 前必须先有 dry-run runner 记录全部原始触发、拒绝原因、接受信号、虚拟订单、真实盘口可成交性、重启恢复和 order idempotency。

### V6.1: TP2.5 Fixed-3x Sizing Variant

Canonical name：`HYPE-5M-PBTR-V6.1`

sizing 诊断：`diagnostics/hype-5m-pbtr-v6-tp25-sizing-2026-06-27.md`。

交易路径图：`diagnostics/hype-5m-pbtr-v6-1-trade-paths-2026-06-27.md`；HTML artifact：`artifacts/hype_5m_pbtr_v6-1_trade_paths_2026-06-27.html`。

TP 触发后 trailing 测试：`diagnostics/hype-5m-pbtr-v6-1-tp-trigger-trailing-2026-06-27.md`。

short-only 组合搜索：`diagnostics/hype-5m-pbtr-v6-1-short-combo-search-2026-06-27.md`。

V6.1 不改变 V6 的入场机制，只把 `tp_atr` 从 `3.0` 改为 `2.5`，并采用 fixed `3x` sizing：

```text
side_mode = long
ema_fast / ema_slow = 21 / 55
pullback_buffer = 0.01
quality_filter = dir_ret192_bps >= 788.123
tp_atr = 2.5
sl_atr = 7.0
trail_atr = 0.0
time_exit_bars = 36
leverage = fixed 3x
```

表现：

| 交易数 | 总收益 | 胜率 | PF | payoff | 最大回撤 | 单笔最差 | 单笔最好 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `157` | `+408.95%` | `63.69%` | `1.773` | `1.011` | `-25.63%` | `-14.81%` | `+9.23%` |

退出分布：

```text
target = 87
time_open = 68
stop_market = 2
```

结论：V6.1 在回测上比 V6 原始 1x 表达收益更高，且 `TP=2.5ATR` 的 1x 回撤低于 `TP=3ATR`；但 fixed `3x` 把最大回撤扩大到约 `-25.63%`，单笔最差接近 `-14.81%`。V6.1 只能作为 registered sizing observation，必须先验证真实盘口滑点、bracket 维护、超时平仓和连续 `30-50` 笔 dry-run 偏差；不能直接生产 sizing。

TP 触发后 trailing overlay 未改善 V6.1。将 `2.5ATR` 从固定止盈改成 trailing trigger，并扫描 `lock_atr=0/1/1.5/2/2.5`、`trail_atr=1/1.5/2/2.5/3/4`、`max_hold=36/72/144` 后，收益最高行为为 `trigger2.5_lock2.5_trail2.5_max36`，总收益 `+364.32%`、最大回撤 `-27.70%`，仍弱于固定止盈基线 `+408.95%` / `-25.63%`。该结果说明 V6.1 的 edge 更像是强动量后吃一段 `2.5ATR` 目标，而不是持续持有趋势右尾；暂不把 trailing overlay 纳入 V6.1。

short-only 组合搜索找到了可研究线索。宽网格保留 `255596` 条 short 候选，top 组合几乎都依赖 `dir_ret48_bps>=400` 的快速下跌动量。收益最高的 `combo_short_rank1` 为 `212` 笔、总收益 `+973.56%`、PF `1.776`、最大回撤 `-28.69%`；更均衡的 `combo_short_rank2` 为 `210` 笔、总收益 `+833.71%`、PF `1.771`、最大回撤 `-22.38%`，相对 V6.1 long-only 同时提高收益并降低回撤。但 short-only 自身验证样本很小，`combo_short_rank2` 的 short 侧只有 `53` 笔、OOS `5` 笔；要求 `VAL>=5/OOS>=10` 后只剩 `2` 个 short 候选，组合回撤反而扩大到约 `-50.20%` 和 `-33.82%`。原始搜索时先列为 watchlist；后续按用户要求，经 V6.2 全参数消融后将 `combo_short_rank2` 固化为 `HYPE-5M-PBTR-V6.2` paper/live-dry-run 候选。

### V6.2: Single-Position Long/Short Bracket Combo

Canonical name：`HYPE-5M-PBTR-V6.2`

来源搜索：`diagnostics/hype-5m-pbtr-v6-1-short-combo-search-2026-06-27.md`。全参数消融：`ablations/hype-5m-pbtr-v6-2-full-parameter-ablation-2026-06-28.md`。

按用户要求，`combo_short_rank2` 在全参数消融后正式记录为 V6.2。V6.2 不是生产版本，而是可进入 paper / 极小资金 live-dry-run 的候选：

```text
long leg:
  EMA21/55 pullback_reclaim
  pullback_buffer = 0.01
  htf_threshold = 0.5
  quality = dir_ret192_bps >= 788.123
  TP = 2.5 ATR14
  SL = 7 ATR14
  timeout = 36 bars

short leg:
  EMA34/144 pullback_reclaim
  pullback_buffer = 0.0
  htf_threshold = None
  quality = dir_ret48_bps >= 400
  TP = 1.5 ATR14
  SL = 2 ATR14
  timeout = 48 bars

combo:
  one-position-only
  same-bar priority = long_first
  baseline sizing = fixed 3x in backtest
```

表现：

| 交易数 | 总收益 | 胜率 | PF | payoff | 最大回撤 | 单笔最差 | 单笔最好 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `210` | `+833.71%` | `64.76%` | `1.771` | `0.963` | `-22.38%` | `-14.81%` | `+21.47%` |

分边贡献：

| side | trades | total | DD | PF | avg |
| --- | ---: | ---: | ---: | ---: | ---: |
| long | `157` | `+408.95%` | `-25.63%` | `1.773` | `+1.15%` |
| short | `53` | `+83.46%` | `-13.38%` | `1.764` | `+1.29%` |

消融结论：测试 `75` 个单因子/组合/sizing 变体，`40` 个通过 V6.2 robust gate。long leg 有可用邻域，尤其 `htf_threshold=0/0.25/None/0.75`、`EMA21/96`、`SL=8/10ATR` 仍通过；但 short leg 的 entry/filter 很脆，所有 `short_entry` 和 `short_filter` 变体都没有通过 gate，说明 `EMA34/144 + pb=0 + dir_ret48>=400` 不能随意放宽。sizing 风险是主要实盘限制：`1x` 总收益 `+122.88%`、最大回撤 `-7.50%`、最差单笔 `-4.94%`；`2x` 为 `+369.33%/-14.93%`；`3x` 为 `+833.71%/-22.38%`；`4x` 虽到 `+1654.47%` 但回撤 `-29.73%`、最差单笔 `-19.75%`。因此小额实盘应从 `1x` 或极小 notional 起步。

执行可行性：V6.2 没有旧 V3/V4 的 delayed trailing stop 穿越问题；它是下一根 open 入场后立即固定 bracket，回测按开盘穿越 stop 用 open 退出，同根 TP/SL 同时触达按 stop first。真实风险转移到 TP/SL reduce-only 订单维护、单边成交后取消另一边、timeout 市价平仓、重启恢复、滑点/跳空和 short leg 样本偏少。必须先 paper / 极小资金记录 `30-50` 笔订单偏差，不应直接生产 sizing。

### V6.2.1: V6.2 Long HTF Threshold 0 Variant

Canonical name：`HYPE-5M-PBTR-V6.2.1`

来源：V6.2 full parameter ablation 的 `long_htf_threshold_0p0` 行。

专项全参数消融：`ablations/hype-5m-pbtr-v6-2-1-full-parameter-ablation-2026-06-29.md`。

实盘可行性专项审计：`diagnostics/hype-5m-pbtr-v6-2-1-live-feasibility-audit-2026-06-30.md`。

实盘复现规格：`live-specs/hype-5m-pbtr-v6-2-1-live-spec.md`。

动态 ATR TP/SL 测试：`diagnostics/hype-5m-pbtr-v6-2-1-dynamic-atr-bracket-2026-06-30.md`。

V6.2.1 只改变 V6.2 的 long leg HTF 阈值：

```text
long leg:
EMA21/55
pullback_buffer = 0.01
htf_spread = EMA96 - EMA384
htf_spread >= 0
dir_ret192_bps >= 788.123
TP = 2.5 ATR14
SL = 7 ATR14
timeout = 36 bars

short leg:
same as V6.2 short rank2
EMA34/144
pullback_buffer = 0.0
dir_ret48_bps >= 400
TP = 1.5 ATR14
SL = 2 ATR14
timeout = 48 bars

combo:
one-position-only
long_first on same signal bar
```

fixed `3x` ablation 结果：`219` 笔、总收益 `+1022.25%`、PF `1.804`、胜率 `64.38%`、payoff `0.998`、最大回撤 `-22.35%`、OOS `15` 笔 / PF `1.439`、short `53` 笔 / PF `1.764`。它比 V6.2 基线增加 `9` 笔交易并提高总收益，回撤几乎不变。

2026-06-29 专项消融补充：本轮以 V6.2.1 为 baseline，重跑与 V6.2 相同的 `75` 个单因子/组合/sizing 变体，除 baseline 外 `37/74` 个通过 robust gate。把 long HTF 阈值收紧回 `0.5` 会退回 V6.2 的 `210` 笔、`+833.71%`、PF `1.771`；完全删除 long HTF 过滤为 `220` 笔、`+895.91%`、PF `1.745`、最大回撤 `-24.10%`，弱于 `htf_spread>=0`。`long_tp_atr=4.0` 为 `191` 笔、`+876.75%`、PF `1.781`，仍不替换 `TP=2.5ATR`。最高的未通过 gate 正收益行是 `short_htf_threshold_0p5`，总收益 `+1146.53%`、PF `1.970`，但 short OOS 只有 `3` 笔，不作为替换候选。

2026-06-30 实盘可行性审计补充：在当前已闭合数据湖范围 `2025-05-30T10:30Z` 到 `2026-06-30T06:15Z` 上，未发现明确未来函数、同 K TP/SL 乐观顺序、或旧 V3/V4 delayed trailing crossed stale stop 价格成交问题。截断重算 `EMA/ATR/HTF/ret/volume ratio` 共 `91` 个 feature-point，失败 `0` 个；baseline fixed `3x` 为 `220` 笔、总收益 `+1054.07%`、PF `1.813`、最大回撤 `-22.35%`，退出分布为 target `129`、time_open `72`、stop_market `19`，baseline 没有 stop/target open-gap 退出，也没有同根 TP/SL 同触发。若假设 bracket 延迟一根 5m K 才生效，仍为 `220` 笔、总收益 `+1030.87%`、PF `1.803`、最大回撤 `-23.73%`；说明策略不完全依赖入场 K 的不可成交瞬间，但入场 K 内有 `3` 笔触及 bracket，真实 runner 必须记录下单延迟、reduce-only bracket 成对维护、单边成交撤单和 timeout 市价平仓偏差。

2026-06-30 交接规格补充：为同事实盘观察创建 `live-specs/hype-5m-pbtr-v6-2-1-live-spec.md`。该 spec 将 long/short leg 参数、EMA/ATR/HTF/dir_ret 公式、相邻信号抑制、组合单仓、入场即 TP/SL bracket、timeout open、持久化字段、重启恢复和 `30-50` 笔订单审计 gate 写成单文件复现规格；实现方应按该 spec 复现，不应继承旧 V2/V3/V4 delayed trailing 或 min-hold 逻辑。

2026-06-30 动态 ATR TP/SL 测试补充：V6.2.1 默认不是 trailing，也不是持仓中动态重算 TP/SL；它是入场时用信号 K `ATR14` 一次性计算固定 bracket。本轮测试 `entry_anchor_dynamic_atr`、`entry_anchor_no_widen_stop`、`close_reset_dynamic_atr`、`close_reset_no_widen_stop` 四类可执行动态 ATR bracket，并扫描 `TP scale=0.75/1.0/1.25/1.5`、`SL scale=0.75/1.0/1.25`。当前数据湖 fixed baseline 为 `220` 笔、`+1054.07%`、PF `1.813`、DD `-22.35%`；最高收益动态行为 `entry_anchor_dynamic_atr__tp1p5__sl1p0` 为 `190` 笔、`+1124.81%`、PF `1.870`，但 DD 扩大到 `-29.89%`，且 `186` 笔实际发生止损放宽。最好的低回撤动态行 `close_reset_dynamic_atr__tp0p75__sl1p25` 为 `+882.65%`、PF `1.838`、DD `-20.25%`，收益低于 baseline。结论：没有动态版本在收益、PF、回撤三者上同时稳健优于固定 bracket；默认继续保留 fixed entry-ATR bracket。

实盘状态：V6.2.1 进入 quant-runner `hype_pullback` 的默认实现，但状态只允许 dry-run / 极小 notional live audit。原因是收益提升主要来自 long HTF 阈值放宽，short leg 的 OOS 仍只有 `5` 笔，且 fixed `3x` 的历史最大回撤约 `-22%`；本地默认配置使用 `1x` 和小 notional，先验证真实 bracket 下单、单边成交后撤单、timeout、重启恢复和 SQLite 复盘口径。2026-07-09 已完成 2026-06 已知信号窗口 runtime/research 对拍（`16/16 MATCH`）；当前 runner 状态与后续未部署 execution 迁移见 [最新 runner tracking](runner-tracking/hype-5m-pbtr-runner-2026-07-11.md)。真实成交生命周期仍待首笔线上信号后验收。

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

1. `HYPE-5M-PBTR-V6.2.1` 是唯一当前 promotion 版本：`live / tiny-live-pilot`，并行 `dry-run`；不得把 fixed `3x` 回测口径解释为获批生产 sizing。
2. V1-V4 是旧 delayed-trailing / stale-stop 历史证据；V6/V6.1/V6.2 是当前机制的研究演化，均不覆盖 V6.2.1 的 manifest 身份。
3. June baseline runtime/research parity 为 `16/16 MATCH`；真实 fill、bracket 生命周期、重启恢复和滑点仍决定 tiny-live-pilot 后续去留。
4. 版本级历史参数、验收线与失败证据保留在上文及链接的 diagnostics/ablations，不再在 Current Decision 重复叙述。

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

V6 audit 验收线：

- 至少连续 `30-50` 笔 paper 订单后再评估是否进入极小资金。
- paper 订单必须记录所有原始触发、质量过滤拒绝原因、接受信号、TP/SL/timeout 虚拟成交、真实盘口可成交性和订单维护事件。
- `30-50` 笔后 PF 应保持 `>=1.2`，平均每笔应保持 `>0`，最大闭合权益回撤不应超过回测级别的 `1.5x`。
- 若 `dir_ret192_bps` 阈值附近的 walk-forward 固化无法维持正期望，V6 不进入真钱。

## Reports

- `ablations/hype-5m-r05732-strategy-ablation-2026-06-23.md`
- `notes/hype-5m-pullback-trail-v2-combo-test-2026-06-23.md`
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
- `diagnostics/hype-5m-pbtr-v33-retry-arm-2026-06-26.md`
- `diagnostics/hype-5m-pbtr-v3-3-1-prev-exit-filter-2026-06-27.md`
- `diagnostics/hype-5m-pbtr-v6-1-short-combo-search-2026-06-27.md`
- `ablations/hype-5m-pbtr-v6-2-full-parameter-ablation-2026-06-28.md`
- `ablations/hype-5m-pbtr-v6-2-1-full-parameter-ablation-2026-06-29.md`
- `diagnostics/hype-5m-pbtr-v6-2-1-live-feasibility-audit-2026-06-30.md`
- `live-specs/hype-5m-pbtr-v6-2-1-live-spec.md`
- `diagnostics/hype-5m-pbtr-v6-2-1-dynamic-atr-bracket-2026-06-30.md`

## Reproduction

- `research/hype/5m-pullback-trail/scripts/ablate_hype_5m_r05732.py`
- `research/hype/5m-pullback-trail/scripts/test_hype_5m_r05732_v2_combos.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v2_live_cost_ablation_slices.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v21_live_cost_variants.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v21a_live_realistic_audit.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v31_min_hold_9.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v32_clean_entry_filters.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v32_full_ablation.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3_minimal.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3_full_ablation.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_reinit_trailing.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-4_combo_candidates.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v4_live_viability_audit.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_fixed_bracket_search.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_reset_bracket_search.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_reset_bracket_maxhold48.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_live_executable_search.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_candidate_robustness.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_full_ablation.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_retry_arm.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3-1_prev_exit_filter.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_1_short_combo_search.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_2_full_ablation.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_2_1_full_ablation.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_2_1_dynamic_atr_bracket.py`
- `research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_2_1_live_feasibility_audit.py`
- `artifacts/hype_5m_r05732_ablation.json`
- `artifacts/hype_5m_r05732_v2_combo_test.json`
- `artifacts/hype_5m_pbtr_v2_live_cost_ablation_slices.json`
- `artifacts/hype_5m_pbtr_v6_live_executable_search.json`
- `artifacts/hype_5m_pbtr_v6_candidate_robustness.csv`
- `artifacts/hype_5m_pbtr_v6_full_ablation.json`
- `artifacts/hype_5m_pbtr_v6-1_short_search_summary_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v6-1_short_combo_extended_summary_2026-06-27.csv`
- `artifacts/hype_5m_pbtr_v6-2_full_ablation_2026-06-28.json`
- `artifacts/hype_5m_pbtr_v6-2_full_ablation_summary_2026-06-28.csv`
- `artifacts/hype_5m_pbtr_v6-2-1_full_ablation_2026-06-29.json`
- `artifacts/hype_5m_pbtr_v6-2-1_full_ablation_summary_2026-06-29.csv`
- `artifacts/hype_5m_pbtr_v6-2-1_live_feasibility_2026-06-30.json`
- `artifacts/hype_5m_pbtr_v6-2-1_live_feasibility_summary_2026-06-30.csv`
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
- `artifacts/hype_5m_pbtr_v33_retry_arm_2026-06-26.json`
- `artifacts/hype_5m_pbtr_v3-3-1_prev_exit_filter_2026-06-27.json`
