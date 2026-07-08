# BTC-1H-Adaptive-Regime 主账

## 家族身份

- Full family name：`BTC-1H-Adaptive-Regime`
- Short id：`BTC-1H-AR`
- 市场：Binance USD-M Futures `BTCUSDT` perpetual
- 周期：`1h`

## 当前状态

`V1 registered baseline；V2 registered audit observation；V3 registered micro-tune observation；V4 registered minimal-equivalent clean observation；not promoted / not live-ready`。

## 版本表

| Version | Identity | Status | Prefit annual / DD / win | Reused holdout annual / DD / win | Evidence | Live-readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `BTC-1H-Adaptive-Regime-V1` | Keltner breakout + CCI reversal prefit-frozen ensemble | diagnostic baseline / NO-GO | `2.82x` / `-18.68%` / `68.29%` | `0.17x` / `-42.73%` / `38.46%` | `canonical-specs/btc-1h-ar-v1-baseline-spec.md`；`artifacts/btc_1h_ar_v1_config_2026-07-02.json` | not live-ready；不生成 live spec |
| `BTC-1H-Adaptive-Regime-V2` | V1 clean surface scaled frontier：Keltner breakout + CCI reversal ensemble，曝光统一缩放至 Keltner `1.8x`、CCI `2.7x` | audit observation / forward-test required | `3.18x` / `-13.99%` / `84.85%` | `1.52x` / `-13.48%` / `81.82%` | `research-notes/btc-1h-ar-v1-scaled-frontier-audit-2026-07-02.md`；`ablations/btc-1h-ar-v2-full-parameter-ablation-2026-07-06.md`；`artifacts/btc_1h_ar_v1_scaled_frontier_audit_2026-07-02.json` | not live-ready；需要新增 forward trades、production runner 与实盘可执行审计 |
| `BTC-1H-Adaptive-Regime-V3` | V2 micro-tune：Keltner breakout + CCI reversal ensemble，Keltner `2.4x`、CCI `3.5x`，CCI 更高 TP、无冷却、较严 ADX 上限 | diagnostic micro-tune observation / forward-test required | `6.16x` / `-12.87%` / `87.30%` | `1.90x` / `-17.47%` / `81.82%` | `research-notes/btc-1h-ar-v2-micro-tune-2026-07-06.md`；`ablations/btc-1h-ar-v3-full-parameter-ablation-2026-07-06.md`；`research-notes/btc-1h-ar-v3-window-backtest-2026-07-06.md`；`artifacts/btc_1h_ar_v3_config_2026-07-06.json` | not live-ready；需要新增 forward trades、production runner 与实盘可执行审计 |
| `BTC-1H-Adaptive-Regime-V4` | V3 minimal-equivalent clean surface：只保留 `19` 个必要参数，`8` 个非必要槽位以中和值固定；与 V3 逐笔等价 | registered minimal-equivalent observation / forward-test required | `6.16x` / `-12.87%` / `87.30%` | `1.90x` / `-17.47%` / `81.82%` | `research-notes/btc-1h-ar-v3-param-necessity-2026-07-07.md`；`research-notes/btc-1h-ar-v4-window-backtest-2026-07-07.md`；`artifacts/btc_1h_ar_v4_config_2026-07-07.json` | not live-ready；需要新增 forward trades、production runner 与实盘可执行审计 |

V1 是用户明确要求登记的研究基线。版本登记不代表 promotion，也不覆盖原始硬门槛和 reused holdout 失败。

V2 是用户明确要求登记的微调观察版。版本登记只固定研究身份和参数，不代表 candidate、paper-live、dry-run、handoff 或 live promotion。

V3 是用户明确要求登记的 V2 micro-tune 观察版。版本登记只固定研究身份和参数，不代表 candidate、paper-live、dry-run、handoff 或 live promotion。

V4 是用户明确要求登记的 V3 参数干净版。版本登记只固定 V3 最小等价参数身份，不代表 candidate、paper-live、dry-run、handoff 或 live promotion；由于逐笔路径与 V3 完全一致，V4 不提供新增收益证据。

## V4 参数清单

V4 来源于 2026-07-07 V3 参数必要性审计：V3 clean surface 的 `27` 个 active 槽位中，`8` 个在 V3 冻结值下从不触发或已经关闭；移除后与 V3 逐笔交易签名完全一致。V4 因此只把 `19` 个必要参数登记为版本身份，执行内核仍以中和值固定被移除槽位，便于复现。

### Keltner breakout leg（8 个必要参数）

| Parameter | V4 value | 作用 |
| --- | ---: | --- |
| `indicator_window` | `20` | Keltner 中线和突破通道窗口；使用 `20` 根 `1h` 收盘价 rolling mean。 |
| `band_k` | `2.0` | 通道宽度倍数；收盘价突破 rolling mean ± `2.0 * ATR14` 触发突破候选。 |
| `min_adx` | `40.0` | 趋势强度下限；只保留 ADX14 >= `40.0` 的强趋势突破信号。 |
| `min_rvol` | `1.25` | 相对成交量下限；只保留 volume / 48h 均量 >= `1.25` 的信号。 |
| `htf_mode` | `h4` | 高周期趋势过滤；使用已闭合 `4h` EMA spread，要求方向与信号同向。 |
| `tp_atr` | `1.5` | 固定止盈距离；入场价朝盈利方向 `1.5 * ATR14(signal bar)` 设置 take-profit。 |
| `sl_atr` | `5.0` | 初始止损距离；入场价反向 `5.0 * ATR14(signal bar)` 设置 stop。 |
| `fixed_leverage` | `2.4` | 固定权益曝光倍数；每笔 Keltner 成交按 `2.4x` 放大 `1x` 净收益。 |

### CCI reversal leg（11 个必要参数）

| Parameter | V4 value | 作用 |
| --- | ---: | --- |
| `ema_htf` | `377` | 距离过滤使用的 EMA 周期；要求 close 距 EMA377 不超过 `max_dist_ema_bps`。 |
| `indicator_window` | `20` | CCI 计算窗口；用 `20` 根 `1h` typical price 生成 CCI20。 |
| `threshold_high` | `125.0` | CCI 反转阈值；CCI 上穿 `-125` 触发多头候选，本腿固定只做多。 |
| `max_adx` | `40.0` | 趋势强度上限；只保留 ADX14 <= `40.0` 的均值回归环境。 |
| `min_rvol` | `1.25` | 相对成交量下限；只保留 volume / 48h 均量 >= `1.25` 的反转信号。 |
| `min_atr_bps` | `75.0` | 波动率下限；过滤 ATR14 / close < `75 bps` 的低波动信号。 |
| `max_dist_ema_bps` | `750.0` | 价格偏离上限；只保留 close 距 EMA377 不超过 `750 bps` 的反转。 |
| `tp_atr` | `5.5` | 固定止盈距离；入场价朝盈利方向 `5.5 * ATR14(signal bar)` 设置 take-profit。 |
| `sl_atr` | `1.5` | 初始止损距离；入场价反向 `1.5 * ATR14(signal bar)` 设置 stop。 |
| `max_hold_bars` | `72` | 最长持仓 `72` 根 `1h`；到期按该 bar open 退出。 |
| `fixed_leverage` | `3.5` | 固定权益曝光倍数；每笔 CCI 成交按 `3.5x` 放大 `1x` 净收益。 |

### 被移除 / 中和值固定的槽位

- Keltner leg：`max_atr_bps -> 10000.0`、`min_dir_roc_bps -> -10000.0`、`roc_window` 随方向 ROC 过滤失效、`max_aligned_funding_bps -> 10000.0`、`max_hold_bars -> 100000`、`cooldown_bars -> 0`。
- CCI leg：`max_atr_bps -> 10000.0`、`cooldown_bars -> 0`。
- 上述移除只针对 V4/V3 当前冻结路径；这些槽位在其他参数组合或未来数据中不必然无效。
- 固定执行与组合口径同 V3：闭合 K 产生信号，下一根 `1h` open 入场，Binance `0.001` fee/fill、`4 bps` slippage/fill，计入历史资金费；组合为单仓、不加仓，冲突时按各腿 prefit leg score 优先。

## V3 参数清单

V3 继承 V2 的 clean interface 和固定执行合同，只调整 active 参数中的仓位、CCI 止盈、CCI 冷却和 CCI ADX 上限。选参规则只读取 train/validation/prefit：prefit 年化高于 V2，train/validation/prefit 胜率均 `>=80%`、回撤均 `<20%`，并在通过 gate 的组合中最大化 prefit 年化；reused holdout 不参与选参。

### Keltner breakout leg

| Parameter | V3 value | 作用 |
| --- | ---: | --- |
| `indicator_window` | `20` | Keltner 中线使用 `20` 根 `1h` 收盘价 rolling mean；同时决定突破通道的观察窗口。 |
| `band_k` | `2.0` | 通道宽度倍数；上轨/下轨为 rolling mean ± `2.0 * ATR14`，收盘价上穿/下穿触发多/空突破信号。 |
| `roc_window` | `24` | 方向动量过滤的回看窗口；用过去 `24` 根 `1h` 的 ROC 判断信号方向上的近期动量。 |
| `min_adx` | `40.0` | 趋势强度下限；只保留 ADX14 >= `40.0` 的强趋势突破信号。 |
| `min_rvol` | `1.25` | 相对成交量下限；只保留当前 volume / 48h 均量 >= `1.25` 的信号。 |
| `max_atr_bps` | `200.0` | 波动率上限；只允许 ATR14 / close <= `200 bps` 的信号，过滤过热波动。 |
| `min_dir_roc_bps` | `-200.0` | 信号方向 ROC 下限；多头看正向 ROC、空头看反向 ROC，允许最多 `-200 bps` 的逆向动量。 |
| `htf_mode` | `h4` | 高周期趋势过滤；使用已闭合 `4h` EMA12/EMA48 spread，要求方向与信号同向。 |
| `max_aligned_funding_bps` | `4.0` | 顺交易方向资金费上限；过滤多头资金费过高或空头资金费过高的拥挤信号。 |
| `tp_atr` | `1.5` | 固定止盈距离；入场价朝盈利方向 `1.5 * ATR14(signal bar)` 设置 take-profit。 |
| `sl_atr` | `5.0` | 初始止损距离；入场价反向 `5.0 * ATR14(signal bar)` 设置 stop。 |
| `max_hold_bars` | `240` | 最长持仓 `240` 根 `1h`；到期按该 bar open 退出。 |
| `cooldown_bars` | `0` | 本腿退出后不额外冷却；下一笔信号只受单仓 ensemble 冲突约束。 |
| `fixed_leverage` | `2.4` | 固定权益曝光倍数；每笔 Keltner 成交按 `2.4x` 放大 `1x` 净收益。 |

### CCI reversal leg

| Parameter | V3 value | 作用 |
| --- | ---: | --- |
| `ema_htf` | `377` | 距离过滤使用的 EMA 周期；要求 close 距离 EMA377 不超过 `max_dist_ema_bps`。 |
| `indicator_window` | `20` | CCI 计算窗口；用 `20` 根 `1h` typical price 生成 CCI20。 |
| `threshold_high` | `125.0` | CCI 反转阈值；CCI 上穿 `-125` 触发多头候选，下穿 `+125` 触发空头候选；本腿固定只做多。 |
| `max_adx` | `40.0` | 趋势强度上限；只保留 ADX14 <= `40.0` 的均值回归环境，比 V2 更严格。 |
| `min_rvol` | `1.25` | 相对成交量下限；只保留 volume / 48h 均量 >= `1.25` 的反转信号。 |
| `min_atr_bps` | `75.0` | 波动率下限；过滤 ATR14 / close < `75 bps` 的低波动信号。 |
| `max_atr_bps` | `600.0` | 波动率上限；过滤 ATR14 / close > `600 bps` 的极端波动信号。 |
| `max_dist_ema_bps` | `750.0` | 价格偏离上限；只保留 close 距 EMA377 不超过 `750 bps` 的反转。 |
| `tp_atr` | `5.5` | 固定止盈距离；入场价朝盈利方向 `5.5 * ATR14(signal bar)` 设置 take-profit，比 V2 放大利润目标。 |
| `sl_atr` | `1.5` | 初始止损距离；入场价反向 `1.5 * ATR14(signal bar)` 设置 stop。 |
| `max_hold_bars` | `72` | 最长持仓 `72` 根 `1h`；到期按该 bar open 退出。 |
| `cooldown_bars` | `0` | 本腿退出后不额外冷却；相比 V2 的 `48` 根冷却，允许更快接收下一次 CCI 反转信号。 |
| `fixed_leverage` | `3.5` | 固定权益曝光倍数；每笔 CCI 成交按 `3.5x` 放大 `1x` 净收益。 |

### 固定执行与组合口径

- Keltner leg 固定为 `style=keltner_break`、`side_mode=both`、`exit_kind=fixed`、`entry_delay_bars=1`、`sizing_kind=fixed`；闭合 K 产生信号，下一根 `1h` open 入场，固定 TP/SL，允许多空。
- CCI leg 固定为 `style=cci_reversal`、`side_mode=long`、`exit_kind=fixed`、`entry_delay_bars=1`、`sizing_kind=fixed`；闭合 K 产生信号，下一根 `1h` open 入场，固定 TP/SL，仅做多。
- 成本固定为 Binance `0.001` fee/fill、`4 bps` slippage/fill，并计入历史资金费。
- 组合为单仓、不加仓；两腿信号冲突时按各腿 prefit leg score 优先，已持仓期间忽略新信号。

## V2 参数清单

V2 继承 V1 clean interface，只暴露 `27` 个 active 参数；其余字段沿用 V1 clean hard-code。选择来源为第一次 prefit-only soft frontier：原曝光 Keltner `2.0x`、CCI `3.0x`，因 K+2 prefit DD 为 `-21.77%`，按 prefit K+2 回撤机械统一缩放 `0.90` 至 Keltner `1.8x`、CCI `2.7x`；reused holdout 未用于决定缩放。

### Keltner breakout leg

| Parameter | V2 value | 作用 |
| --- | ---: | --- |
| `indicator_window` | `20` | Keltner 中线使用 `20` 根 `1h` 收盘价 rolling mean；同时决定突破通道的观察窗口。 |
| `band_k` | `2.0` | 通道宽度倍数；上轨/下轨为 rolling mean ± `2.0 * ATR14`，收盘价上穿/下穿触发多/空信号。 |
| `roc_window` | `24` | 方向动量过滤的回看窗口；用 `24h` ROC 判断信号方向上的近期动量。 |
| `min_adx` | `40.0` | 趋势强度下限；只保留 ADX14 >= `40.0` 的强趋势突破信号。 |
| `min_rvol` | `1.25` | 相对成交量下限；只保留当前 volume / 48h 均量 >= `1.25` 的信号。 |
| `max_atr_bps` | `200.0` | 波动率上限；只允许 ATR14 / close <= `200 bps` 的信号，过滤过热波动。 |
| `min_dir_roc_bps` | `-200.0` | 信号方向 ROC 下限；多头看正向 ROC、空头看反向 ROC，允许最多 `-200 bps` 的逆向动量。 |
| `htf_mode` | `h4` | 高周期趋势过滤；使用已闭合 `4h` EMA12/EMA48 spread，要求方向与信号同向。 |
| `max_aligned_funding_bps` | `4.0` | 顺交易方向资金费上限；过滤多头资金费过高或空头资金费过高的拥挤信号。 |
| `tp_atr` | `1.5` | 固定止盈距离；入场价朝盈利方向 `1.5 * ATR14(signal bar)` 设置 take-profit。 |
| `sl_atr` | `5.0` | 初始止损距离；入场价反向 `5.0 * ATR14(signal bar)` 设置 stop。 |
| `max_hold_bars` | `240` | 最长持仓 `240` 根 `1h`；到期按该 bar open 退出。 |
| `cooldown_bars` | `0` | 本腿退出后不额外冷却；下一笔信号只受单仓 ensemble 冲突约束。 |
| `fixed_leverage` | `1.8` | 固定权益曝光倍数；每笔 Keltner 成交按 `1.8x` 放大 `1x` 净收益。 |

### CCI reversal leg

| Parameter | V2 value | 作用 |
| --- | ---: | --- |
| `ema_htf` | `377` | 距离过滤使用的 EMA 周期；要求 close 距离 EMA377 不超过 `max_dist_ema_bps`。 |
| `indicator_window` | `20` | CCI 计算窗口；用 `20` 根 `1h` typical price 生成 CCI20。 |
| `threshold_high` | `125.0` | CCI 反转阈值；CCI 上穿 `-125` 触发多头候选，下穿 `+125` 触发空头候选。 |
| `max_adx` | `45.0` | 趋势强度上限；只保留 ADX14 <= `45.0` 的均值回归环境。 |
| `min_rvol` | `1.25` | 相对成交量下限；只保留 volume / 48h 均量 >= `1.25` 的反转信号。 |
| `min_atr_bps` | `75.0` | 波动率下限；过滤 ATR14 / close < `75 bps` 的低波动信号。 |
| `max_atr_bps` | `600.0` | 波动率上限；过滤 ATR14 / close > `600 bps` 的极端波动信号。 |
| `max_dist_ema_bps` | `750.0` | 价格偏离上限；只保留 close 距 EMA377 不超过 `750 bps` 的反转。 |
| `tp_atr` | `4.5` | 固定止盈距离；入场价朝盈利方向 `4.5 * ATR14(signal bar)` 设置 take-profit。 |
| `sl_atr` | `1.5` | 初始止损距离；入场价反向 `1.5 * ATR14(signal bar)` 设置 stop。 |
| `max_hold_bars` | `72` | 最长持仓 `72` 根 `1h`；到期按该 bar open 退出。 |
| `cooldown_bars` | `48` | 本腿退出后冷却 `48` 根 `1h`，降低连续反转信号堆叠。 |
| `fixed_leverage` | `2.7` | 固定权益曝光倍数；每笔 CCI 成交按 `2.7x` 放大 `1x` 净收益。 |

### 固定执行与组合口径

- Keltner leg 固定为 `style=keltner_break`、`side_mode=both`、`exit_kind=fixed`、`entry_delay_bars=1`、`sizing_kind=fixed`；下一根 `1h` open 入场，固定 TP/SL，允许多空。
- CCI leg 固定为 `style=cci_reversal`、`side_mode=long`、`exit_kind=fixed`、`entry_delay_bars=1`、`sizing_kind=fixed`；下一根 `1h` open 入场，固定 TP/SL，仅做多。
- 成本固定为 Binance `0.001` fee/fill、`4 bps` slippage/fill，并计入历史资金费。
- 组合为单仓、不加仓；两腿信号冲突时按各腿 prefit score 优先，已持仓期间忽略新信号。

## V2 原观察记录

| Observation | Status | Prefit annual / DD / win | K+2 prefit annual / DD / win | Reused holdout annual / DD / win | Current full annual / DD / win | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| `BTC-1H-AR-V1-SCALED-FRONTIER-2026-07-02` | 已按用户要求登记为 `BTC-1H-Adaptive-Regime-V2` | `3.18x` / `-13.99%` / `84.85%` | `2.50x` / `-19.70%` / `80.30%` | `1.52x` / `-13.48%` / `81.82%` | `2.88x` / `-13.99%` / `84.42%` | 明显优于 V1；等待新增 forward trades 与 runner 审计；not live-ready |

观察参数与证据：`research-notes/btc-1h-ar-v1-scaled-frontier-audit-2026-07-02.md`、`artifacts/btc_1h_ar_v1_scaled_frontier_audit_2026-07-02.json`。

## 研究边界记录

| Boundary | Status | Prefit annual / DD / win | Locked OOS annual / DD / win | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `BTC-1H-AR-2026-07-02-prefit-frozen` | 已登记为 V1 | `2.82x` / `-18.68%` / `68.29%` | `0.17x` / `-42.73%` / `38.46%` | `diagnostics/btc-1h-adaptive-regime-search-2026-07-02.md`；`diagnostics/btc-1h-adaptive-regime-boundary-audit-2026-07-02.md` | `NO-GO`；不可实盘 |

搜索规模：`300,768` 组配置，`41,898` 组可评分，prefit hard-gate `0`；73 个 one-at-a-time 邻域变体 joint-gate `0`；bootstrap `10,000` 次 hard-shape 命中率 `0%`。

V1 后续研究：全消融覆盖 `78/78` 字段槽；clean interface 从 `78` 个原始槽缩为 `27` 个 active 参数且逐笔等价。clean tune 每腿 `150,000` 组、组合 `122,500` 组；`809` 个 prefit 严格改善观察，`15` 个通过 K+2/8 bps 全窗口 gate。最终缩放前沿有 `24/55` 邻域继续满足相对 V1 严格改善与 K+2 gate。

V2 全参数消融：`ablations/btc-1h-ar-v2-full-parameter-ablation-2026-07-06.md` 覆盖两腿全部 `78/78` 个 `StrategyConfig` 字段槽，生成 `205` 行 baseline/variant 证据；分类仍为 `27` active tunable、`12` contract fixed、`35` baseline fixed、`4` neutral fixed。相对 V2 基线，one-at-a-time prefit 严格改善行数为 `5`，但本轮不做组合搜索、不登记 V2.1、不改变 `not live-ready`。

V2 微调观察：`research-notes/btc-1h-ar-v2-micro-tune-2026-07-06.md` 基于 V2 消融前沿方向做 active 参数受约束网格。网格 `7,200` 组，`3,852` 组满足 prefit 年化高于 V2、train/validation/prefit 胜率均 `>=80%`、回撤均 `<20%`。当前首选观察 `BTC-1H-AR-V2-MICRO-TUNE-2026-07-06` 已按用户要求登记为 `BTC-1H-Adaptive-Regime-V3`：prefit `6.16x / -12.87% / 87.30%`，reused holdout `1.90x / -17.47% / 81.82%`，current full `5.27x / -17.47% / 86.49%`。该登记不改变 `not live-ready`。

V3 全参数消融：`ablations/btc-1h-ar-v3-full-parameter-ablation-2026-07-06.md` 覆盖两腿全部 `78/78` 个 `StrategyConfig` 字段槽，生成 `205` 行 baseline/variant 证据；分类仍为 `27` active tunable、`12` contract fixed、`35` baseline fixed、`4` neutral fixed。相对 V3 基线，同时满足 prefit 年化更高、回撤更小、train/validation/prefit 胜率均 `>=80%`、train/validation 同正且 validation DD<20% 的 one-at-a-time 严格改善行数为 `0`。本轮不做组合搜索；原“不登记 V4”的诊断口径后续已被用户指令覆盖，但不改变 `not live-ready`。

V3 多窗口回测：`research-notes/btc-1h-ar-v3-window-backtest-2026-07-06.md` 复用 V3 冻结参数，不引入新增 forward 数据。recent 90d 为 `1.91x / +17.34% / -17.47% / 81.82% / 11`，recent 30d 为 `1.29x / +2.13% / -17.47% / 75.00% / 4`，recent 7d 无交易；2026 YTD 为 `3.90x / +97.37% / -17.47% / 84.00% / 25`。这些窗口只用于风险画像，不能视为新鲜 OOS。

V3 参数必要性审计（2026-07-07）：`research-notes/btc-1h-ar-v3-param-necessity-2026-07-07.md` 对 `27` 个 clean active 槽位逐项中和验证。`8` 个槽位在 V3 冻结值下从不生效（Keltner `max_atr_bps`/`min_dir_roc_bps`/`roc_window`/`max_aligned_funding_bps`/`max_hold_bars`/`cooldown_bars=0`，CCI `max_atr_bps`/`cooldown_bars=0`），移除后与 V3 逐笔交易签名完全一致。最小等价表面为 `19` 个必要参数（Keltner `8`、CCI `11`），指标与 V3 逐字节相同；该表面已按用户要求登记为 `BTC-1H-Adaptive-Regime-V4`。

V3 最小表面微调（2026-07-07）：`research-notes/btc-1h-ar-v3-minimal-micro-tune-2026-07-07.md` 在 19 参数最小表面上做受约束网格（杠杆冻结为 V3 值）。腿级变体 Keltner `486`、CCI `1,728`，组合 `24,576` 组：没有组合能同时严格提升 prefit 年化、回撤、胜率三项；Pareto 口径（年化更高、回撤与胜率不劣）仅 `8` 组，首选 prefit `6.24x / -12.87% / 87.30%`（vs V3 `6.16x`，改善约 `+1.4%`，来自 CCI `max_hold_bars 72->96`、`max_dist_ema_bps 750->700`），reused holdout 与 V3 完全相同。结论：V4/V3 在其冻结邻域是局部最优，微调收益属噪声级别；不登记额外 V4.1/V5，不改变 `not live-ready`。

V4 多窗口回测（2026-07-07）：`research-notes/btc-1h-ar-v4-window-backtest-2026-07-07.md` 复用 V4 最小等价参数并验证与 V3 逐笔等价。canonical split 与 V3 完全一致：prefit `6.16x / -12.87% / 87.30% / 63`，reused holdout `1.90x / -17.47% / 81.82% / 11`，current full `5.27x / -17.47% / 86.49% / 74`；recent 30d `1.29x / +2.13% / -17.47% / 75.00% / 4`，recent 7d 无交易。该回测只是 V4 身份下的风险画像，不是新增 OOS。

## Promotion 门槛

必须同时通过：最近三个月 locked OOS、年化权益倍率 `>=10.0x`、胜率 `>=50%`、最大回撤 `<20%`、K+2/成本压力、参数邻域、时间切片、bootstrap、订单时序、保护单、重启恢复、missing-bar fail-closed、交易所对账和 kill switch 审计。
