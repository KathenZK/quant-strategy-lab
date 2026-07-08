# BNB-1H-Adaptive-Regime-V3 参数规格 - 2026-07-07

## 版本身份

- Version：`BNB-1H-Adaptive-Regime-V3`
- Short id：`BNB-1H-AR-V3`
- Market：Binance USD-M Futures `BNBUSDT` perpetual
- Timeframe：`1h`
- 状态：`tuned diagnostic observation / not promoted / not live-ready`
- 来源：`BNB-1H-Adaptive-Regime-V2` 消融引导微调的唯一首选组合。
- Evidence：`../notes/bnb-1h-ar-v2-micro-tune-2026-07-07.md`
- 重要边界：locked OOS 在 V1/V2 阶段已揭盲，本版本的 OOS 结果是 reused observation，不能作为 promotion 依据。

## 杠杆倍数

- 当前实际最大杠杆：`2.5x`。
- `ema_pullback` component 使用固定 `2.5x`。
- `wick_reject` component 使用固定 `1.0x`。
- 策略是单仓 merge，同一时间只保留一个 component 的 trade，因此组合最大实际暴露为 `2.5x`，低于用户约束的 `3x` 上限。

## 指标

| Window | Annual | Return | Max DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| train | `2.95x` | `242.90%` | `-16.65%` | `88.89%` | `72` | `4.025` |
| validation | `4.58x` | `110.05%` | `-18.24%` | `90.62%` | `32` | `5.400` |
| prefit | `3.37x` | `620.27%` | `-18.24%` | `89.42%` | `104` | `4.430` |
| reused locked OOS | `1.22x` | `5.08%` | `-15.53%` | `81.25%` | `16` | `1.343` |
| full | `2.94x` | `656.84%` | `-18.24%` | `88.33%` | `120` | `3.737` |

## Ensemble 参数

| 参数 | 当前值 | 作用 |
| --- | --- | --- |
| `component_a` | `ema_pullback` | 趋势回踩恢复组件，负责在 EMA 趋势背景下寻找回踩后继续同向的入场。 |
| `component_b` | `wick_reject` | 影线反转组件，负责在长影线拒绝后寻找短线反转/修复入场。 |
| `priority_ema_pullback` | `2.445774012147314` | 合并两个 component 的交易时使用的优先级；同一时段冲突时优先保留较高优先级交易。 |
| `priority_wick_reject` | `1.6307399812929821` | `wick_reject` 的 merge 优先级。 |
| `position_merge` | single-position | 单仓机制，不叠加仓位；两个 component 同时触发时只执行优先级更高者。 |

## Component A：`ema_pullback` 参数逐项解释

| 参数 | 当前值 | 作用 |
| --- | ---: | --- |
| `style` | `ema_pullback` | 信号家族；使用 EMA 快慢线定义趋势，并在价格回踩/恢复时入场。 |
| `side_mode` | `both` | 允许做多和做空。趋势向上时只产生 long，趋势向下时只产生 short。 |
| `ema_fast` | `55` | 快 EMA；用于判断趋势方向，也作为回踩参考线。 |
| `ema_slow` | `144` | 慢 EMA；与 `ema_fast` 比较决定趋势方向。V3 从 V2 的 `89` 调到 `144`，让趋势定义更慢、更稳。 |
| `pullback_atr` | `-0.25` | 回踩距离阈值，单位 ATR。多头要求低点触及 `ema_fast - 0.25 * ATR` 附近并收回快线，空头相反。负值使信号要求价格更充分地穿过快线后恢复。 |
| `ema_htf` | `377` | 高阶 EMA 过滤参考。与 `max_dist_ema_bps` 共同限制价格离长期均线太远时不追。 |
| `max_dist_ema_bps` | `300.0` | 价格距离 `ema377` 的最大允许距离，单位 bps；超过约 `3%` 不入场。 |
| `min_rvol` | `1.0` | 最小相对成交量，过滤低流动性/低确认度信号。 |
| `min_atr_bps` | `50.0` | 最小 ATR 波动率，单位 bps；过滤波动过低的环境。 |
| `exit_kind` | `trailing` | 出场类型。V3 使用 trailing 出场，而不是 V2 的固定 TP/SL。 |
| `tp_atr` | `3.0` | 初始/保护性止盈距离，单位 ATR；用于 bracket 目标价。 |
| `sl_atr` | `5.0` | 初始止损距离，单位 ATR；定义保护性 stop。 |
| `trail_activation_atr` | `2.0` | 浮盈达到 `2 ATR` 后启动 trailing stop。 |
| `trail_atr` | `1.5` | trailing stop 与最新有利价格之间的距离，单位 ATR。 |
| `max_hold_bars` | `240` | 单笔最长持仓 K 数；`240` 根 1h 等于最多约 10 天。 |
| `cooldown_bars` | `12` | 平仓后冷却 12 根 1h K，避免连续重复入场。 |
| `entry_delay_bars` | `1` | 信号 K 闭合后下一根 K 的 open 入场；这是 live-executable 时序边界，不可删除。 |
| `sizing_kind` | `fixed` | 使用固定杠杆，不按 stop distance 动态风险预算。 |
| `fixed_leverage` | `2.5` | 本 component 每笔交易固定 `2.5x` 名义暴露。 |

## Component B：`wick_reject` 参数逐项解释

| 参数 | 当前值 | 作用 |
| --- | ---: | --- |
| `style` | `wick_reject` | 信号家族；通过上下影线和收盘位置识别拒绝/反转形态。 |
| `side_mode` | `both` | 允许做多和做空。下影线拒绝触发 long，上影线拒绝触发 short。 |
| `threshold_low` | `0.40` | 收盘位置低阈值。上影线拒绝做空时要求 close position 不高于 `0.40`，说明收盘靠近 K 线下方。 |
| `threshold_high` | `0.75` | 收盘位置高阈值。下影线拒绝做多时要求 close position 不低于 `0.75`，说明收盘靠近 K 线上方。 |
| `band_k` | `0.5` | 影线最小长度，单位 ATR。下影线或上影线至少达到 `0.5 ATR` 才算拒绝信号。 |
| `min_adx` | `28.0` | 最小 ADX，要求市场有足够方向性/波动结构，过滤弱趋势噪音。 |
| `min_rvol` | `2.0` | 最小相对成交量，要求影线拒绝伴随成交活跃度。 |
| `htf_mode` | `h12` | 高周期方向过滤；信号方向必须与闭合 `12h` regime spread 同向。 |
| `exit_kind` | `fixed` | 使用固定 TP/SL bracket 出场。 |
| `tp_atr` | `1.0` | 止盈距离，单位 ATR。wick reversal component 更短线，止盈较近。 |
| `sl_atr` | `5.0` | 止损距离，单位 ATR。 |
| `max_hold_bars` | `48` | 单笔最长持仓 48 根 1h K，最多约 2 天。 |
| `cooldown_bars` | `24` | 平仓后冷却 24 根 1h K，避免影线信号过度密集。 |
| `entry_delay_bars` | `1` | 信号 K 闭合后下一根 K 的 open 入场；live-executable 时序边界。 |
| `sizing_kind` | `fixed` | 使用固定杠杆。 |
| `fixed_leverage` | `1.0` | 本 component 每笔交易固定 `1.0x` 名义暴露。 |

## 完整可执行配置变更摘要

相对 V2：

- `ema_pullback`：`ema_slow 89 -> 144`；`exit_kind fixed -> trailing`；`trail_activation_atr 2.0`；`trail_atr 1.5`；`max_hold_bars 168 -> 240`；`cooldown_bars 6 -> 12`；`fixed_leverage 2.0 -> 2.5`。
- `wick_reject`：`threshold_low 0.35 -> 0.40`；`threshold_high 0.85 -> 0.75`；`min_adx 24 -> 28`；`max_hold_bars 72 -> 48`；`fixed_leverage 0.75 -> 1.0`。
- 其余 V2 clean 参数不变。

## 执行与成本口径

- 数据：Binance USD-M Futures `BNBUSDT` perpetual `1h`，沿用 V1/V2 冻结数据，UTC 至 `2026-07-03`。
- 入场：闭合 K 产生信号，下一根 `1h` open 市价成交。
- 出场：入场后 bracket 立即生效；同 K 双触发 stop-first；open 穿 stop 按 open 成交。
- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill。
- Funding：逐笔计入 Binance 历史 funding。

## Promotion 边界

V3 是微调观察版本。虽然 full 与 reused locked OOS 指标均优于 V2，但 reused OOS 属于二次读取，不能作为 promotion 证据。V3 当前禁止标记为 candidate、paper-live、dry-run、handoff 或 live；需要新的 forward 数据或重新冻结流程验证。
