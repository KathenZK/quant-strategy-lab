# HYPE-EMA-X V15 / V16 正式候选规则说明

本文解释 Cursor 主台账中的两个正式候选：

- `HYPE-EMA-X-V15`：高胜率 / 低回撤版
- `HYPE-EMA-X-V16`：高收益版

两者都来自 V17 trend-state search，但 Cursor 主台账版本号按正式候选重新编号。主台账文件是 `/Users/ZK/.cursor/projects/Users-ZK-OpenCode-quant-strategy-lab/canvases/hype-ema-crossover-evolution.canvas.tsx`；本文是 repo 内的规则说明镜像。

`HYPE-EMA-X-V17` 已在同一 Cursor 主台账中正式登记为 V15/V16 合体平衡版；`HYPE-EMA-X-V17.1` 也已登记为 V17 的仓位增强版。两者定义和全参数消融见 `v17-hybrid-ablation.md`。

## 一句话区别

`V15` 比 `V16` 多一个综合趋势质量过滤器，所以交易更少、胜率更高、回撤更低。

`V16` 只要求 ATR 不过热，不要求综合趋势分达到 7 分，所以交易更多、收益更高，但回撤也更高。

## 回测表现

| Version | Return | Final Equity | Max DD | Win Rate | Trades | Avg Trade | Median Trade | Worst Trade | Exit Reasons |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `V15` | `+2303.65%` | `24.04x` | `-17.79%` | `90.32%` | `31` | `+11.85%` | `+10.69%` | `-8.33%` | volume warning: 18, oscillator warning: 9, hard swing: 4 |
| `V16` | `+3202.92%` | `33.03x` | `-28.19%` | `86.84%` | `38` | `+10.64%` | `+10.31%` | `-12.85%` | volume warning: 21, oscillator warning: 11, hard swing: 5, stop loss: 1 |

## 共同数据与成本参数

| 参数 | 值 | 大白话作用 |
| --- | --- | --- |
| `symbol` | `HYPEUSDT` perpetual | 只研究 HYPE 永续合约。 |
| `timeframe` | `15m` | 每根 K 线是 15 分钟。 |
| `lookback` | latest 365 days | 当前 Cursor 台账指标用最近一年回测。 |
| `slippage` | `0.0005` | 每次成交按 0.05% 滑点惩罚，买更贵、卖更便宜。 |
| `trade_cost` | `0.00085` | 每次进出场按仓位扣 0.085% 成本。 |
| `max_allocation` | `3.0` | 最大 3 倍仓位。 |
| `long_target_atr_pct` | `0.016` | 做多时用 ATR 估算仓位，目标是让一次 ATR 波动约等于 1.6% 账户风险单位。 |
| `short_target_atr_pct` | `0.014` | 做空略保守，目标风险单位 1.4%。 |
| `allocation` | `min(3.0, target_atr_pct / atr_pct672)` | 波动越大仓位越小，波动越小仓位越大，但最多 3 倍。 |
| `atr_pct672` | `672` bars | 用 672 根 15m K 线估计慢速 ATR，主要用于仓位和止损。 |

## 共同核心指标

| 参数 | 值 | 大白话作用 |
| --- | --- | --- |
| `ema_fast` | `EMA96` | 快线，大约看 1 天趋势。 |
| `ema_slow` | `EMA384` | 慢线，大约看 4 天趋势。 |
| `ema_spread` | `EMA96 / EMA384 - 1` | 判断当前是多头趋势还是空头趋势。 |
| `regime` | `ema_spread > 0` long, `< 0` short | EMA96 在 EMA384 上方只找多，下面只找空。 |
| `regime_age` | bars since EMA spread sign change | 趋势已经走了多久；刚交叉是 0。 |
| `dir_dist_ema96` | direction-adjusted close/EMA96 distance | 价格离 EMA96 多远；越远越容易追高/追空。 |
| `atr_ratio96_672` | `atr_pct96 / atr_pct672` | 短期波动相对长期波动是否过热。 |
| `vol_surge192` | volume / 192-bar average - 1 | 成交量有没有放大。 |
| `ADX28` | 28-bar ADX | 趋势强度。 |
| `h1_*` | 1h resampled indicators shifted by 1 h | 1 小时级别确认，避免用未来数据。 |

## 基础信号识别

这一步先找“趋势方向上可能可以交易”的 K 线。它不是马上成交；满足信号后，下一根 K 线开盘才入场。

### 多头基础信号

同时满足：

| 条件 | 大白话 |
| --- | --- |
| `ema_spread > 0` | EMA96 在 EMA384 上方，只做多。 |
| `ADX28 >= 28` | 15m 趋势强度不能太弱。 |
| `vol_surge192 >= 0.25` | 成交量至少比 192 根均量高 25%。 |
| `h1_adx21 > 18` | 1h 级别也要有一点趋势强度。 |
| `h1_pdi21 > h1_mdi21` | 1h 上多头力量大于空头力量。 |

### 空头基础信号

同时满足：

| 条件 | 大白话 |
| --- | --- |
| `ema_spread < 0` | EMA96 在 EMA384 下方，只做空。 |
| `ADX28 >= 36` | 做空要求更强的 15m 趋势。 |
| `vol_surge192 >= 0.50` | 成交量至少比 192 根均量高 50%。 |
| `h1_ema_spread < 0` | 1h 级别也处于空头 EMA 状态。 |

## V15 额外信号过滤

`V15` 使用 `atr18_trend7` 过滤器。基础信号出现后，还必须同时满足：

| 参数 | 值 | 大白话作用 |
| --- | --- | --- |
| `atr_ratio96_672` | `<= 1.8` | 短期波动不能比长期波动热太多，避免在爆波动后追进去。 |
| `trend_score` | `>= 7 / 10` | 十个趋势质量条件至少过七个。 |

`trend_score` 的 10 个小项：

| 小项 | 过关条件 | 大白话 |
| --- | --- | --- |
| `ADX28` | `>= 28` | 趋势强度够。 |
| `dir_macd_hist` | `> 0` | MACD 柱子站在交易方向一边。 |
| `dir_aroon` | `> 0` | Aroon 显示近期高低点方向支持趋势。 |
| `dir_vortex` | `> 0` | Vortex 指标支持当前方向。 |
| `dir_obv_slope48` | `> 0` | OBV 量能趋势支持当前方向。 |
| `dir_cmf20` | `> -0.05` | CMF 资金流不能明显逆着方向。 |
| `chop14` | `<= 55` | 市场不能太震荡。 |
| `eff96_local` | `>= 0.18` | 过去 96 根 K 线的走势不能太绕，方向效率要够。 |
| `atr_ratio96_672` | `<= 1.8` | 波动不过热。 |
| `dir_dist_ema96` | `<= 0.08` | 价格离 EMA96 不超过 8%，避免追得太远。 |

## V16 额外信号过滤

`V16` 使用 `atr18` 过滤器。基础信号出现后，只额外要求：

| 参数 | 值 | 大白话作用 |
| --- | --- | --- |
| `atr_ratio96_672` | `<= 1.8` | 只过滤掉波动过热的行情，不再要求综合趋势分。 |

这就是 V16 比 V15 更进攻的原因：它放过了更多趋势信号。

## 普通买入规则

普通买入用于趋势早期。

| 参数 | 值 | 大白话作用 |
| --- | --- | --- |
| `entry_max_regime_age` | `128` bars | 只在 EMA 交叉后的前 128 根 15m K 线内正常入场，避免太晚追趋势。 |
| `entry_max_dist_ema96` | `0.08` | 入场时价格离 EMA96 不能超过 8%。 |
| `entry_min_rvol96` | `0` | 普通入场不额外要求 96 根相对成交量。 |
| `entry_max_move48` | `0` | 普通入场不额外限制 48 根涨跌幅。 |
| `reentry_mode` | `none` | 普通信号不要求突破确认。 |

买入执行：

- 当前 K 线收盘时发现信号。
- 下一根 K 线开盘买入或做空。
- 多头成交价加 `0.05%` 滑点；空头成交价减 `0.05%` 滑点。
- 入场时按仓位扣交易成本。

## Late Re-entry 买入规则

Late re-entry 用于趋势已经超过普通入场窗口，但之前同方向交易表现不错，允许再次进入。

### V15 late re-entry 参数

| 参数 | 值 | 大白话作用 |
| --- | --- | --- |
| `late_max_age` | `384` bars | EMA 交叉后最多 384 根 K 线内允许 late re-entry。 |
| `late_dist_ema96` | `0.075` | late 入场时离 EMA96 不能超过 7.5%。 |
| `cooldown_bars` | `12` | 上一笔出场后至少等 12 根 K 线。 |
| `min_prev_pnl` | `-0.03` | 上一笔最多允许小亏 3%，因为它可能只是提前被震出。 |
| `min_prev_mfe_atr` | `3.0` | 上一笔至少曾经跑出 3 ATR 浮盈，说明趋势曾经真实存在。 |
| `require_pullback` | `false` | 不强制必须回踩。 |

### V16 late re-entry 参数

| 参数 | 值 | 大白话作用 |
| --- | --- | --- |
| `late_max_age` | `384` bars | 同 V15。 |
| `late_dist_ema96` | `0.06` | late 入场时离 EMA96 不能超过 6%，比 V15 更怕追远。 |
| `cooldown_bars` | `16` | 上一笔出场后至少等 16 根 K 线。 |
| `min_prev_pnl` | `-0.03` | 同 V15。 |
| `min_prev_mfe_atr` | `4.0` | 上一笔至少曾经跑出 4 ATR 浮盈，比 V15 更严格。 |
| `require_pullback` | `false` | 不强制必须回踩。 |

Late re-entry 还必须满足：

- 当前方向必须和上一笔出场方向一样。
- 当前 EMA regime 必须和上一笔出场时的 regime 一样。
- 上一笔不能是 `stop_loss` 出场。
- 当前仍然要有基础信号；V15 还要过 `atr18_trend7`，V16 还要过 `atr18`。

## 持有规则

持仓后不设固定止盈。策略的核心假设是：如果趋势是真的，就尽量让利润奔跑。

持有期间持续记录：

| 参数 | 大白话作用 |
| --- | --- |
| `high_water` | 多头持仓后的最高价。 |
| `low_water` | 空头持仓后的最低价。 |
| `mfe_atr` | 这笔交易最多曾经赚过多少个 ATR。 |
| `hold_bars` | 持仓了多少根 15m K 线。 |

## 卖出规则

以下任意一条触发就卖出或平空。

### 1. 硬止损

| 参数 | 值 | 大白话作用 |
| --- | --- | --- |
| `stop_atr` | `8.0` | 亏损达到 8 个入场 ATR 就强制止损。 |
| `entry_atr` | previous-bar `atr_pct672` | 用入场前一根 K 线的慢速 ATR 定止损距离。 |

多头止损价：

`entry_price * (1 - 8 * entry_atr)`

空头止损价：

`entry_price * (1 + 8 * entry_atr)`

这是盘中止损，K 线最高/最低价碰到就算触发。

### 2. EMA 反向交叉

| 参数 | 值 | 大白话作用 |
| --- | --- | --- |
| `opposite_cross` | enabled | 多头持仓时 EMA96 跌回 EMA384 下方，或空头持仓时 EMA96 涨回 EMA384 上方，就认为大趋势反了。 |

触发后下一根 K 线开盘出场。

### 3. 硬趋势破坏

| 参数 | 值 | 大白话作用 |
| --- | --- | --- |
| `hard_exit_mode` | `swing96` | 用 96 根 K 线结构低点/高点判断趋势结构是否破坏。 |
| `hard_exit_bars` | `1` | 破位一次就出，不等第二次。 |

多头：

- 收盘价跌破前 96 根 K 线最低点，下一根开盘出场。

空头：

- 收盘价涨破前 96 根 K 线最高点，下一根开盘出场。

### 4. 利润后的预警确认出场

这一套用于保护已经跑出来的趋势利润。

先满足：

| 参数 | 值 | 大白话作用 |
| --- | --- | --- |
| `min_mfe_atr` | `4.0` | 这笔交易至少曾经赚过 4 ATR，才启动预警系统。 |
| `warning_source` | `either` | 成交量衰竭预警或振荡指标预警，任意一个都可以。 |
| `warning_exit_min_capture` | `0.35` | 出场时至少保住最大浮盈的 35%，否则不因为预警出。 |
| `confirm_mode` | `ema21` | 预警后还要跌破/涨破 EMA21 才确认出场。 |

成交量衰竭预警：

| 参数 | 值 | 大白话作用 |
| --- | --- | --- |
| `volume_warning_mode` | `no_mfi_div` | 不用 MFI 背离，只看爆量长影线或爆量无效推进。 |
| `exit_rvol` | `2.0` | 成交量达到 96 根均量的 2 倍。 |
| `wick_min` | `0.55` | 长影线至少占整根 K 线 55%。 |

多头成交量预警：

- 创 96 根新高，并且爆量、上影线很长、收盘位置不够强；或
- 爆量但 3 根 K 线实际推进很小，且收盘位置偏弱。

空头成交量预警：

- 创 96 根新低，并且爆量、下影线很长、收盘位置不够弱；或
- 爆量但 3 根 K 线实际推进很小，且收盘位置偏强。

振荡指标预警：

| 参数 | 值 | 大白话作用 |
| --- | --- | --- |
| `osc_min_score` | `2` | 3 个振荡警告里至少中 2 个。 |
| `osc_tf` | `1h` | 用 1 小时级别 RSI/KDJ/MACD。 |

多头振荡预警：

- 当前价格打到 96 根新高；
- `1h RSI >= 72`、`1h KDJ-J >= 100`、`1h MACD histogram 连续 2 根走弱` 中至少满足 2 个。

空头振荡预警：

- 当前价格打到 96 根新低；
- `1h RSI <= 28`、`1h KDJ-J <= 0`、`1h MACD histogram 连续 2 根走强` 中至少满足 2 个。

预警后确认出场：

- 多头：收盘价跌破 EMA21，且至少保住最大浮盈的 35%，下一根开盘卖出。
- 空头：收盘价涨破 EMA21，且至少保住最大浮盈的 35%，下一根开盘平空。

## 不启用的功能

| 参数 | 值 | 大白话 |
| --- | --- | --- |
| `take_profit` | disabled | 不固定止盈。 |
| `max_hold_bars` | disabled | 不按持仓时长强制退出。 |
| `fallback_adx` | `0` | 不用 ADX 走弱兜底退出。 |
| `segment_exit_mode` | `none` | 不启用中段 EMA/ADX 减速退出。 |
| `add_signal` | `none` | 不启用额外 late pullback/breakout/KDJ 补单信号。 |

## 参数总表

| 参数 | V15 | V16 | 作用 |
| --- | ---: | ---: | --- |
| `base_filter` | `atr18_trend7` | `atr18` | V15 多一道综合趋势质量过滤。 |
| `atr_ratio96_672` | `<= 1.8` | `<= 1.8` | 过滤波动过热。 |
| `trend_score` | `>= 7` | disabled | V15 要求 10 个趋势质量项至少过 7 个。 |
| `late_max_age` | `384` | `384` | late re-entry 最晚允许到 EMA 交叉后 384 根。 |
| `late_dist_ema96` | `0.075` | `0.06` | late re-entry 离 EMA96 的最大距离。 |
| `cooldown_bars` | `12` | `16` | 上一笔出场后等待多久才能 late re-entry。 |
| `min_prev_pnl` | `-0.03` | `-0.03` | 上一笔最多允许小亏 3%。 |
| `min_prev_mfe_atr` | `3.0` | `4.0` | 上一笔至少曾经跑出多少 ATR 浮盈。 |
| `stop_atr` | `8.0` | `8.0` | 硬止损距离。 |
| `warning_source` | `either` | `either` | 成交量或振荡预警任一可触发。 |
| `osc_min_score` | `2` | `2` | 3 个振荡警告至少满足 2 个。 |
| `warning_exit_min_capture` | `0.35` | `0.35` | 预警出场至少保住 35% 最大浮盈。 |
| `hard_exit_mode` | `swing96` | `swing96` | 96 根结构破位退出。 |
| `hard_exit_bars` | `1` | `1` | 结构破位一次就出。 |
| `entry_max_regime_age` | `128` | `128` | 普通入场只允许趋势早期。 |
| `entry_max_dist_ema96` | `0.08` | `0.08` | 普通入场不能离 EMA96 超过 8%。 |
| `allocation_scale` | `1.0` | `1.0` | 不额外降仓。 |
| `add_signal` | `none` | `none` | 不启用额外补单信号。 |
