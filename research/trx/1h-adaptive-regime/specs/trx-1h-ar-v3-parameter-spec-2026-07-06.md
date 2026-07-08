# TRX-1H-Adaptive-Regime-V3 参数说明 - 2026-07-06

## 版本身份

`TRX-1H-Adaptive-Regime-V3` 是基于 `TRX-1H-Adaptive-Regime-V2` clean 参数面和 V2 全参数消融结果微调后的登记版本。V3 不是 live/paper-live/dry-run/handoff 版本；它仍是 diagnostic version。

- Market：Binance USD-M Futures `TRXUSDT` perpetual
- Timeframe：`1h`
- 成本：fee `0.001/fill`，adverse slippage `4 bps/fill`，实际 Binance funding
- 信号与成交：闭合 `1h` K 产生信号，下一根 open 入场
- Selection：只使用 train/validation/prefit；reused holdout 与近期分片仅冻结后审计

## V3 指标边界

| Window | Annual / Return / DD / Win / Trades |
| --- | --- |
| `train` | `8.1557x` / `+819.38%` / `-17.17%` / `90.91%` / `55` |
| `validation` | `6.0130x` / `+177.62%` / `-11.17%` / `100.00%` / `29` |
| `prefit` | `7.3305x` / `+2452.42%` / `-17.17%` / `94.05%` / `84` |
| `reused_holdout` | `1.0834x` / `+2.02%` / `-15.23%` / `77.78%` / `9` |
| `current_full` | `5.6863x` / `+2503.89%` / `-17.17%` / `92.47%` / `93` |

标准近期分片：

| Slice | Annual / Return / DD / Win / Trades |
| --- | --- |
| `last_1d` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_7d` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_1m` | `1.5230x` / `+3.52%` / `-1.56%` / `100.00%` / `2` |
| `last_3m` | `1.0834x` / `+2.02%` / `-15.23%` / `77.78%` / `9` |
| `last_6m` | `3.2850x` / `+80.29%` / `-15.23%` / `91.30%` / `23` |
| `last_1y` | `2.9135x` / `+191.14%` / `-15.71%` / `91.84%` / `49` |

## 参数总览

V3 仍是双组件 ensemble：`macd_flip` 与 `stoch_reversal`。两组件按 prefit priority 处理冲突，单仓、不加仓。

### MACD flip 参数

| 参数 | V3 值 | V2 值 | 作用 | V3 相对 V2 的变化 |
| --- | ---: | ---: | --- | --- |
| `ema_htf` | `89` | `377` | 高周期/趋势 EMA 参考长度，用于过滤大方向状态。 | 从慢速长期趋势改为更快的中期趋势，提升对 regime 切换的响应。 |
| `roc_window` | `6` | `12` | 计算 directional ROC 的回看窗口。 | 缩短动量确认窗口，更敏感地捕捉方向变化。 |
| `macd_fast` | `34` | `34` | MACD 快线 EMA 周期。 | 不变，仍使用较慢快线过滤噪声。 |
| `macd_slow` | `89` | `89` | MACD 慢线 EMA 周期。 | 不变，保持原趋势尺度。 |
| `macd_signal` | `13` | `13` | MACD signal 平滑周期。 | 不变，保持 histogram turn 的平滑尺度。 |
| `min_adx` | `20.0` | `12.0` | 入场所需最低 ADX，过滤趋势强度不足的行情。 | 提高下限，只在更明确趋势中交易。 |
| `max_adx` | `24.0` | `28.0` | 允许的最高 ADX，避免过度拥挤或极端趋势状态。 | 收窄 ADX 带宽，减少过热趋势入场。 |
| `min_rvol` | `0.0` | `1.5` | 最低相对成交量过滤。 | 移除成交量门槛，避免错过低量但有效的趋势翻转。 |
| `max_atr_bps` | `150.0` | `200.0` | 允许入场的最高 ATR bps，限制波动率环境。 | 更严格过滤高波动时段，降低回撤。 |
| `min_dir_roc_bps` | `-100.0` | `-100.0` | 顺方向 ROC 的最低容忍值。 | 不变，仍允许轻微反向动量。 |
| `max_dist_ema_bps` | `10000.0` | `1000.0` | 价格距离参考 EMA 的最大 bps。 | 基本放开距离限制，避免过早排除强趋势延伸。 |
| `htf_mode` | `h12` | `h12` | 使用的高周期 regime 模式。 | 不变，仍用 `12h` regime 过滤。 |
| `require_macd_turn` | `False` | `True` | 是否要求 MACD histogram 转向。 | 放宽 turn 要求，使信号不必等待额外转向确认。 |
| `tp_atr` | `2.0` | `2.0` | fixed exit 的止盈距离，以 ATR 倍数计。 | 不变，保持 `2 ATR` 止盈。 |
| `sl_atr` | `5.0` | `4.0` | fixed exit 的保护止损距离，以 ATR 倍数计。 | 放宽止损，减少正常波动触发止损。 |
| `max_hold_bars` | `120` | `168` | 最长持仓 K 数，单位为 `1h` bar。 | 缩短最长持仓，减少老化仓位暴露。 |
| `cooldown_bars` | `3` | `3` | 平仓后冷却 K 数。 | 不变，保持短冷却。 |
| `entry_delay_bars` | `1` | `1` | 信号后延迟几根 K 入场。 | 不变，保持闭合 K 后下一根 open 入场。 |
| `fixed_leverage` | `5.0` | `4.0` | fixed sizing 下的名义杠杆。 | 提高 MACD leg 杠杆，放大高胜率趋势腿收益。 |

### Stochastic reversal 参数

| 参数 | V3 值 | V2 值 | 作用 | V3 相对 V2 的变化 |
| --- | ---: | ---: | --- | --- |
| `side_mode` | `both` | `long` | 允许交易方向。 | 从只做多改为多空双向，提高 regime 覆盖。 |
| `ema_htf` | `233` | `55` | 高周期/趋势 EMA 参考长度。 | 从短中期参考改为更慢趋势参考，减少局部噪声。 |
| `indicator_window` | `21` | `21` | Stochastic 计算窗口。 | 不变，保持同一震荡尺度。 |
| `threshold_low` | `25.0` | `25.0` | Stochastic 低位阈值，用于多头反转触发。 | 不变。 |
| `threshold_high` | `90.0` | `85.0` | Stochastic 高位阈值，用于空头/高位反转触发。 | 提高高位阈值，只在更极端高位触发。 |
| `roc_window` | `3` | `3` | directional ROC 回看窗口。 | 不变，保留短周期方向过滤。 |
| `max_adx` | `24.0` | `30.0` | 允许反转策略入场的最高 ADX。 | 更严格过滤强趋势，避免逆势接刀。 |
| `min_rvol` | `1.0` | `1.0` | 最低相对成交量过滤。 | 不变，仍要求基本成交活跃度。 |
| `min_dir_roc_bps` | `-300.0` | `-200.0` | 顺方向 ROC 最低容忍值。 | 放宽到 `-300 bps`，允许更深回撤后的反转。 |
| `require_body_dir` | `True` | `True` | 是否要求 K 线实体方向与交易方向一致。 | 不变，仍要求 candle body 确认。 |
| `sl_atr` | `6.0` | `5.0` | trailing exit 的初始保护止损距离。 | 放宽初始止损，减少反转初期噪声止损。 |
| `trail_activation_atr` | `3.0` | `3.0` | 浮盈达到多少 ATR 后启动 trailing。 | 不变。 |
| `trail_atr` | `2.0` | `1.25` | trailing stop 跟踪距离。 | 放宽 trailing，给反转趋势更多延展空间。 |
| `max_hold_bars` | `120` | `168` | 最长持仓 K 数，单位为 `1h` bar。 | 缩短最长持仓，减少久拖仓位。 |
| `cooldown_bars` | `6` | `24` | 平仓后冷却 K 数。 | 大幅缩短冷却，提高可交易频率。 |
| `entry_delay_bars` | `2` | `1` | 信号后延迟几根 K 入场。 | 增加一根延迟，降低反转信号过早入场风险。 |
| `fixed_leverage` | `3.5` | `3.0` | fixed sizing 下的名义杠杆。 | 小幅提高反转腿杠杆。 |

## V2 与 V3 的核心区别

| 维度 | V2 | V3 | 影响 |
| --- | --- | --- | --- |
| 版本来源 | V1 的 clean-equivalent 参数版本 | V2 消融引导微调后的登记版本 | V3 不再与 V1/V2 逐交易等价，是新的 tuned diagnostic version。 |
| 选参方式 | 删除 dormant/neutral 字段，不改变交易路径 | 在 V2 clean 参数面上基于 train/validation/prefit 微调 | V3 改变实际交易路径。 |
| MACD leg | 较慢趋势过滤、要求 MACD turn、`4x` 杠杆 | 更快 HTF、放宽 turn、收紧 ADX/ATR、`5x` 杠杆 | V3 更主动捕捉趋势机会，并用波动/ADX 控制风险。 |
| Stochastic leg | long-only、较短 EMA 参考、宽 ADX、较紧 trailing、冷却 `24h` | both sides、慢 EMA 参考、更严 ADX、更宽 trailing、冷却 `6h`、延迟 `2h` | V3 增加空头覆盖，降低强趋势逆势风险，提高交易频率。 |
| current full | `4.0772x / +1295.38% / -19.84% DD / 86.54% win / 104 trades` | `5.6863x / +2503.89% / -17.17% DD / 92.47% win / 93 trades` | V3 满足本次 full 目标：收益更高、胜率 `>80%`、DD `<20%`。 |
| reused holdout | `0.8445x / -4.12% / -11.42% DD / 75.00% win / 8 trades` | `1.0834x / +2.02% / -15.23% DD / 77.78% win / 9 trades` | V3 holdout 收益转正、DD 仍 <20%，但胜率未达到 80%。 |
| live readiness | `NO-GO` | `NO-GO` | V3 登记不等于 promotion；仍缺 fresh forward OOS 与 production runner。 |

## 研究边界

V3 是登记版本，但不是 promotion。主要原因：

- reused holdout 已在早期研究中揭盲，不能作为 fresh OOS。
- reused holdout 胜率 `77.78%`，未达到本次 `80%` 目标。
- 当前没有 TRX production runner、重启恢复、交易所 reconciliation、缺 K fail-closed、kill switch 与保护单监控证据。
- 如需讨论 candidate/paper-live/live，必须等待新增 forward trades，并完成 live-executable 审计。

## 机器证据

- `artifacts/trx_1h_ar_v3_config_2026-07-06.json`
- `artifacts/trx_1h_ar_v2_ablation_guided_tune_2026-07-06.json`
- `artifacts/trx_1h_ar_v2_ablation_guided_tune_candidates_2026-07-06.csv`
- `artifacts/trx_1h_ar_v2_ablation_guided_tune_trades_2026-07-06.csv`
- `artifacts/trx_1h_ar_v2_ablation_guided_tune_slices_2026-07-06.csv`
- `artifacts/trx_1h_ar_v2_ablation_guided_tune_execution_audit_2026-07-06.csv`

复现：

```bash
uv run python research/trx/1h-adaptive-regime/scripts/trx_1h_ar_v3.py
uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_v2_ablation_guided_tune.py
```
