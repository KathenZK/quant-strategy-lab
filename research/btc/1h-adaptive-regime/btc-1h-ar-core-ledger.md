# BTC-1H-Adaptive-Regime 主账

## 家族身份

- Full family name：`BTC-1H-Adaptive-Regime`
- Short id：`BTC-1H-AR`
- 市场：Binance USD-M Futures `BTCUSDT` perpetual
- 周期：`1h`

## 当前状态

`V1 registered diagnostic baseline；V2 registered paper-audit observation；not promoted / not live-ready`。

## 版本表

| Version | Identity | Status | Prefit annual / DD / win | Reused holdout annual / DD / win | Evidence | Live-readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `BTC-1H-Adaptive-Regime-V1` | Keltner breakout + CCI reversal prefit-frozen ensemble | diagnostic baseline / NO-GO | `2.82x` / `-18.68%` / `68.29%` | `0.17x` / `-42.73%` / `38.46%` | `canonical-specs/btc-1h-ar-v1-baseline-spec.md`；`artifacts/btc_1h_ar_v1_config_2026-07-02.json` | not live-ready；不生成 live spec |
| `BTC-1H-Adaptive-Regime-V2` | V1 clean surface scaled frontier：Keltner breakout + CCI reversal ensemble，曝光统一缩放至 Keltner `1.8x`、CCI `2.7x` | paper-audit observation / forward-test required | `3.18x` / `-13.99%` / `84.85%` | `1.52x` / `-13.48%` / `81.82%` | `research-notes/btc-1h-ar-v1-scaled-frontier-audit-2026-07-02.md`；`artifacts/btc_1h_ar_v1_scaled_frontier_audit_2026-07-02.json` | not live-ready；需要新增 forward trades、production runner 与实盘可执行审计 |

V1 是用户明确要求登记的研究基线。版本登记不代表 promotion，也不覆盖原始硬门槛和 reused holdout 失败。

V2 是用户明确要求登记的微调观察版。版本登记只固定研究身份和参数，不代表 candidate、paper-live、dry-run、handoff 或 live promotion。

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

## Promotion 门槛

必须同时通过：最近三个月 locked OOS、年化权益倍率 `>=10.0x`、胜率 `>=50%`、最大回撤 `<20%`、K+2/成本压力、参数邻域、时间切片、bootstrap、订单时序、保护单、重启恢复、missing-bar fail-closed、交易所对账和 kill switch 审计。
