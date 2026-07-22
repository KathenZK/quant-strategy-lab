# BTC-15M-Keltner-Trend-Breakout 首轮冻结搜索最终诊断

- 日期：`2026-07-20`
- 研究身份：`BTC-15M-KTB-INITIAL-FROZEN-SEARCH-2026-07-20`
- 市场：Binance USD-M Futures `BTCUSDT` perpetual，原生 `15m`
- 状态结论：`explore / not promoted / not live-ready`

## 结论

本轮没有找到合适的 BTC `15m` Keltner 趋势策略。`630` 组冻结配置中，validation 正收益项为 `0`，train 与 validation 同时正收益项也为 `0`；因此不存在可进入候选层的参数高原。

冻结近失项在一次诊断 holdout 中继续亏损，双倍成本、方向拆分、邻域和近期主要切片也没有修复结论。本轮不登记 V1，不创建 research spec 或 live spec，不进入 runner；停止围绕相同信号与退出族扩大参数网格。

## 数据、切分与执行合同

[数据质量产物](../artifacts/btc_15m_keltner_data_quality_2026-07-20.json)复核了标准数据湖：

- OHLCV：`2024-07-14T00:00:00Z` 至 `2026-07-17T14:30:00Z`，`70,427` 根已闭合 `15m` K；
- funding：同市场官方历史 funding，`2,201` 条，最大间隔 `8h`；
- 连续性、重复、关键空值、OHLC、市场身份、closed-bar 与 funding 检查全部通过，DQ blocker 为 `0`。

冻结切分按 UTC 左闭右开：

- train：`2024-07-17T14:45:00Z` 至 `2025-07-17T14:45:00Z`；
- validation：`2025-07-17T14:45:00Z` 至 `2026-01-17T14:45:00Z`；
- diagnostic holdout：`2026-01-17T14:45:00Z` 至 `2026-07-17T14:45:00Z`。

该 holdout 没有被本脚本搜索读取，但同一日历窗口已在其他 BTC 家族研究中暴露，因此只称为 diagnostic OOS，不冒充 untouched future OOS。

执行固定为：

- `15m` 收盘确认首次越过 Keltner 上/下轨，下一根 `15m` open 市价成交；
- 可选最后已闭合 `1h` EMA trend / slope regime，不读取未闭合高周期 K；
- 固定 `1.0x` allocation，单仓、不加仓；
- fee `0.001`/fill、adverse slippage `4 bps`/fill，逐事件计入历史 funding；
- gap 穿越 stop 按更差 open，bar 内 stop/TP 冲突按 `stop-first`；
- midline 指标退出在下一根 open 执行，trailing stop 只使用上一根已闭合状态。

## 冻结搜索空间

搜索空间在运行前由脚本哈希冻结，共 `630` 组：

- Keltner EMA：`10 / 20 / 40`；
- Wilder ATR：`10 / 20`；
- 通道倍数：`1.5 / 2.0 / 2.5`；
- regime：无高周期过滤，或 `1h EMA 12/48、24/96、48/192`，各含 EMA-only 与 EMA+slope；
- 退出：midline、两档 ATR trailing、两档 ATR bracket；
- 方向：基础搜索固定双向，holdout 后仅做 long-only / short-only 诊断。

[候选明细](../artifacts/btc_15m_keltner_search_candidates_2026-07-20.csv)显示：

| 项目 | 数量 / 最佳值 |
| --- | ---: |
| 总配置 | `630` |
| train 正收益 | `2` |
| validation 正收益 | `0` |
| train 与 validation 同正 | `0` |
| 完整 development gate 通过 | `0` |
| 最佳 validation 收益 | `-8.40%` |
| train 正收益项中的最佳 validation | `-10.47%` |

三类退出的最佳 validation 分别为：bracket `-8.40%`、trailing `-8.78%`、midline `-10.80%`。高周期 EMA / EMA+slope 过滤的最佳 validation 均为 `-8.40%`，无高周期过滤最佳为 `-24.49%`。这说明失败不只是某一个退出参数或是否增加 EMA regime 的问题。

## 冻结近失项

由于没有通过项，[冻结选择](../artifacts/btc_15m_keltner_frozen_selection_2026-07-20.json)只保存 `diagnostic_near_miss`：

- Keltner：EMA `10`、ATR `10`、倍数 `2.5`；
- `1h` regime：EMA `48/192` + slow EMA `4h` slope 同向；
- 退出：`2.5 ATR` stop、`4 ATR` take-profit、最长 `64` 根；
- 双向、固定 `1.0x`。

| 窗口 | 收益 | MDD | 交易数 | 胜率 | PF |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | `+7.70%` | `-11.97%` | `99` | `48.48%` | `1.144` |
| validation | `-10.47%` | `-11.81%` | `48` | `35.42%` | `0.639` |
| train，2x 成本 | `-16.93%` | `-25.41%` | `99` | `42.42%` | `0.765` |
| validation，2x 成本 | `-23.42%` | `-23.46%` | `48` | `31.25%` | `0.332` |

其轻微参数邻域共有 `9` 项，train/validation 同正比例为 `0%`。近失项不是 candidate，不能因 train 单窗盈利升级。

## 一次诊断 holdout

[holdout 揭示](../artifacts/btc_15m_keltner_holdout_reveal_2026-07-20.json)结果：

| 口径 | 收益 | MDD | 交易数 | 胜率 | PF |
| --- | ---: | ---: | ---: | ---: | ---: |
| 双向标准成本 | `-7.38%` | `-9.97%` | `42` | `38.10%` | `0.748` |
| 双向 2x 成本 | `-17.70%` | `-18.28%` | `42` | `35.71%` | `0.484` |
| long-only | `-2.91%` | `-8.21%` | `14` | `35.71%` | `0.691` |
| short-only | `-4.60%` | `-7.32%` | `28` | `39.29%` | `0.774` |

同窗 BTC buy-and-hold 为 `-33.72% / MDD -39.15%`。策略少亏于持有只说明降低了市场暴露，仍输给 `0%` cash 基准，不构成可交易 alpha。

固定参数 development 30 日窗口审计为 `6/17` 个正收益窗口，正收益比例 `35.29%`。近期独立 flat-reset 切片：

| 切片 | 收益 | 交易数 | PF |
| --- | ---: | ---: | ---: |
| `1d` | `0.00%` | `0` | `0.000` |
| `7d` | `0.00%` | `0` | `0.000` |
| `1m` | `-5.21%` | `8` | `0.267` |
| `3m` | `-4.27%` | `18` | `0.670` |
| `6m` | `-7.38%` | `42` | `0.748` |
| `1y` | `-17.08%` | `90` | `0.693` |

## 决策

本轮失败具有跨窗口、跨退出、跨 regime、双倍成本、方向拆分和邻域一致性，不支持继续围绕通道周期、倍数、止损或 EMA 周期做局部扩搜。

如果未来重开，必须先提出机制级变化，例如“突破后首次回踩并 reclaim 再入场”或“波动压缩—扩张事件 + Keltner 确认”，重新冻结搜索空间和未来 OOS；不能继续使用本轮近失项作为 seed 放宽门禁。若新机制的核心已不是 Keltner 趋势突破，应创建新的策略家族。

复现入口见[脚本说明](../scripts/README.md)，状态同步见[主账](../btc-15m-keltner-trend-breakout-core-ledger.md)与[决策记录](../decision-log.md)。
