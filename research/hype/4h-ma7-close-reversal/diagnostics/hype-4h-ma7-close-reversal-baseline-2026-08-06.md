# HYPE 4H MA7 收盘反手基准（2026-08-06）

## 结论

“闭合 4H 站上 SMA7 则下一期开盘做多，闭合跌破则下一期开盘直接反手做空”的原始规则显著失败。

全期成本后收益 `-90.01%`、MDD `-91.66%`、PF `0.65`。策略在 `432.67d` 内产生 `556` 次方向反转和 `1,114` 次 fill；即使把 fee 和 slippage 都设为 `0`、仅保留实际 funding，仍为 `-52.34%`。因此失败不只是交易成本问题，MA7 附近的频繁假突破和下一期开盘的滞后反手本身没有形成正 edge。

该基准保持 `explore / not promoted / not live-ready`，不登记版本，不在已揭示历史上追加 buffer、确认或止损参数来挽救。

## 冻结机制

1. `SMA7[t]` 使用七根完整 `4h` close。
2. `close[t] > SMA7[t]`：`t+1` 的 `4h` open 目标为 `+1x`。
3. `close[t] < SMA7[t]`：`t+1` 的 `4h` open 目标为 `-1x`。
4. 第一个有效信号后始终持仓；跨线时同一 open 先平旧仓、再开反向仓，按两次 fill。
5. 无 buffer、无连续确认、无 stop、无 cooldown、无 max hold。

这才是用户图示的单均线 close-regime flip，不是 [HYPE-4H-MA7-ABT](../../4h-ma7-asymmetric-body-trend/README.md) 的 pullback-reclaim 参数策略。完整定义见[冻结合同](../specs/hype-4h-ma7-close-reversal-contract-2026-08-06.md)。

## 数据与执行

- Binance USD-M `HYPEUSDT` perpetual。
- 标准数据湖闭合 `1h`：`2025-05-30 10:00` 至 `2026-08-06 07:00 UTC`；原生相位形成 `2,596` 根完整 `4h`，策略 terminal open 为 `2026-08-06 04:00 UTC`。
- 每根 `4h` 严格由四根连续 `1h` 聚合；缺口、重复、非法 OHLC 与 raw/normalized blocker 为 `0`。
- 手续费 `0.001/fill`、不利滑点 `4 bps/fill`；压力滑点 `8 bps/fill`。
- funding 使用 Binance 实际事件时间和费率，仅在持仓期间结算。
- 收盘确认后下一根 `4h` open 执行；无盘中穿越成交或未来函数。
- 小时内 high/low 顺序未知，MDD 使用 favorable-to-adverse 保守 envelope。

## 全期结果

| 场景 | 收益 | MDD | PF | 交易 / fills |
| --- | ---: | ---: | ---: | ---: |
| Base | `-90.01%` | `-91.66%` | `0.65` | `557 / 1,114` |
| `8 bps/fill` | `-93.61%` | `-94.56%` | `0.60` | `557 / 1,114` |
| 额外延迟一根 `4h` | `-66.20%` | `-78.76%` | `0.86` | `557 / 1,114` |
| Gross：fee/slippage 为 `0` | `-52.34%` | `-73.61%` | `0.87` | `557 / 1,114` |
| Buy-and-hold | `+57.13%` | `-70.54%` | — | `1 / 2` |

- Win rate `30.70%`，多头/空头交易 `279 / 278`。
- 曝险 `99.73%`；反手 `556` 次。
- 累计交易成本为初始权益的 `40.84%`；该口径随权益缩小，不等同于从 gross 收益简单减去 40.84 个百分点。
- 额外延迟后损失变小但仍显著为负，只说明反手时点高度敏感，不构成可交易优势。

## 最后 120 日

最后 `120d` 精确锚定数据终点：

| 场景 | 收益 | MDD | PF | 交易 / fills |
| --- | ---: | ---: | ---: | ---: |
| Base | `-17.05%` | `-55.48%` | `0.93` | `155 / 310` |
| `8 bps/fill` | `-26.74%` | `-58.36%` | `0.88` | `155 / 310` |
| 额外延迟一根 `4h` | `+8.99%` | `-33.28%` | `1.04` | `155 / 310` |
| Gross：fee/slippage 为 `0` | `+28.07%` | `-43.93%` | `1.11` | `155 / 310` |
| Buy-and-hold | `+44.99%` | `-34.25%` | — | `1 / 2` |

近期 gross 有正方向信号，但默认成本把它变为 `-17.05%`，且仍显著落后持有。不能根据已揭示结果事后选择延迟一根或改成 gross 口径。

## 单腿、相位与时间稳定性

| Route | 全期 | 最后 120 日 |
| --- | ---: | ---: |
| Combined | `-90.01%` | `-17.05%` |
| Long-only | `-52.80%` | `+14.38%` |
| Short-only | `-78.83%` | `-27.48%` |

- 四个整点相位 `0h/1h/2h/3h` 分别为 `-90.01% / -95.42% / -85.28% / -78.08%`，全部失败。
- 12 个滚动 `90d` 窗口仅 `2` 个为正；最差 `-66.59%`。
- 最近 `1d/7d/1m/3m/6m/1y` 为 `+0.42% / +1.70% / +0.49% / -15.19% / -42.69% / -81.16%`；近期短切片不能推翻长期失败。
- Long-only 最近 `120d` 为正只是事后单腿观察；全期仍亏 `-52.80%`，不能据此选择。

## 为什么图上看起来有效、交易却失败

1. MA7 平滑后自然贴近价格，视觉上能描述趋势，但描述不等于预测下一根收益。
2. 在单边段中反手方向正确；在 MA7 附近横盘时却会连续来回反手。
3. 信号必须等 `4h` 收盘，成交又在下一期开盘，趋势拐点的视觉位置早于真实可成交位置。
4. 一次反手包含平仓和反向开仓两次 fill；`556` 次反手把局部噪声放大为大量 turnover。
5. 全期 gross 也亏 `-52.34%`，说明不能只靠降低手续费解决。

## 决策

- 原始 MA7 close-reversal 基准失败，不登记、不优化同一已揭示历史。
- 如果下一步研究“避免 MA7 附近反复打脸”，buffer、连续确认、最短持仓或 flat zone 都属于新的预冻结机制，不是本基准的参数修补。
- 无 hard stop 或交易所驻留保护仍是独立 live-readiness blocker。

## 证据

- [机器摘要](../artifacts/hype_4h_ma7_close_reversal_summary_2026-08-06.json)
- [场景指标](../artifacts/hype_4h_ma7_close_reversal_metrics_2026-08-06.csv)
- [多空单腿](../artifacts/hype_4h_ma7_close_reversal_components_2026-08-06.csv)
- [相位审计](../artifacts/hype_4h_ma7_close_reversal_phase_2026-08-06.csv)
- [滚动 90 日](../artifacts/hype_4h_ma7_close_reversal_rolling_90d_2026-08-06.csv)
- [近期切片](../artifacts/hype_4h_ma7_close_reversal_recent_2026-08-06.csv)
- [逐笔交易](../artifacts/hype_4h_ma7_close_reversal_trades_2026-08-06.csv)
- [权益路径](../artifacts/hype_4h_ma7_close_reversal_path_2026-08-06.csv)
- [复现脚本](../scripts/research_hype_4h_ma7_close_reversal.py)
