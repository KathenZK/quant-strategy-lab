# HYPE 1D MA7 原始趋势状态机消融

> 日期：2026-08-09。角色：researcher-exposed development ablation；所有邻域均只用于因果归因，不允许替换[冻结合同](../specs/hype-1d-ma7-original-trend-state-machine-contract-2026-08-09.md)的主值。

## 1. 核心 OAT

| 变体 | 净收益 | MDD | 交易 | 相对 A 的解释 |
| --- | ---: | ---: | ---: | --- |
| `A_CORE` | `-33.52%` | `-57.28%` | 50 | 冻结控制 |
| `CORE_NO_SLOPE` | `+18.47%` | `-55.12%` | 28 | slope exit 与反手 slope 都删除；最高但仍高 MDD、short 腿亏损 |
| `CORE_NO_SLOPE_EXIT` | `+8.79%` | `-55.12%` | 28 | 只删除持仓 slope exit；显示单日 slope exit 是主要 churn 来源 |
| `CORE_SLOPE_005` | `-3.37%` | `-43.00%` | 60 | 更高 slope 门槛降低 MDD但增加交易与成本，仍亏损 |
| `CORE_SLOPE_002` | `-31.72%` | `-53.54%` | 55 | 邻域没有稳定平台 |
| `CORE_ATR_050` | `-30.74%` | `-62.85%` | 52 | 小幅改善收益但尾部更差 |
| `CORE_ATR_100` | `-63.81%` | `-74.50%` | 54 | 更宽迟滞显著恶化 |
| `CORE_ZERO_TOLERANCE` | `-56.97%` | `-77.96%` | 64 | 无迟滞频繁翻转 |
| `CORE_NO_ARM` | `-54.15%` | `-61.91%` | 54 | armed 等待本身有贡献 |
| `CORE_NCROSS_2` | `-54.45%` | `-65.83%` | 52 | 多日前置没有提高质量 |
| `CORE_NCROSS_3` | `-66.65%` | `-74.12%` | 47 | 多日前置进一步恶化 |

归因：fresh cross 与 armed/迟滞不是主失败源；最大问题是严格单日 slope 同号作为每日持仓门。删除 slope 的正结果只是一项 post-reveal 诊断，必须以新合同重做压力、相位、CPCV 和 prospective，不能登记。

## 2. RSI 邻域

| 变体 | 净收益 | MDD | Short PnL | Short 平均回吐 | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| `D_BOTH_RSI` (`3/30/70`) | `-8.54%` | `-50.27%` | `+0.1068` | `10.05%` | 冻结主值 |
| `RSI_DAYS_2` | `-19.13%` | `-49.48%` | `+0.1481` | `8.73%` | 锁利更快但组合收益更差 |
| `RSI_DAYS_4` | `-9.51%` | `-51.11%` | `-0.0118` | `11.62%` | short 腿转负 |
| `RSI_EXIT_25` | `-33.52%` | `-57.28%` | `-0.1915` | `12.48%` | 无止盈触发，退化为 A |
| `RSI_EXIT_35` | `-23.36%` | `-52.37%` | `+0.1519` | `8.96%` | short 改善但组合更差 |
| `RSI_OB_65` / `RSI_OB_75` | `-8.54%` | `-50.27%` | `+0.1068` | `10.05%` | 与 D 完全相同，overbought 模块无成交 |

`3d / RSI6<30` 在这组预登记邻域里是组合损失最小者，但没有形成宽平台，且 `8 bps` 为负；不能把“局部最好”解释为参数验证通过。

## 3. RSI 模块接受矩阵

| 条件 | B vs A | C vs A | D vs B |
| --- | --- | --- | --- |
| 主路径有增量 | PASS：`+24.98pp` | FAIL：逐笔相同 | FAIL：逐笔相同 |
| MDD 至少改善 2pp或收益改善 | PASS：`+7.01pp` | FAIL | FAIL |
| `8 bps` 仍为正 | FAIL：`-12.54%` | FAIL：`-36.15%` | FAIL：`-12.54%` |
| 额外延迟仍为正 | PASS：`+6.48%` | FAIL：`-2.25%` | PASS但无组合增量 |
| 多数 rolling 不恶化 | PASS：6 改善/3 相同/3 恶化 | 无增量 | 无增量 |
| short giveback 降低且 short 腿不负 | PASS | 不适用 | 与 B 相同 |
| 最终接受 | **REJECT** | **DORMANT / insufficient events** | **REJECT** |

## 4. Overbought 事件漏斗

| 条件 | 事件数 |
| --- | ---: |
| raw fresh down-cross | 49 |
| 任意日已有连续 3 日 `RSI6>70` 记忆 | 23 |
| fresh down-cross 且此前连续 3 日 `RSI6>70` | 1 |
| 再要求当日 short slope `<0` | 0 |
| 再要求当时持有 long | 0 |

当前数据只能判定 C dormant，不能判定 overbought 机制本身无效。若扩大样本，必须先冻结资产/时期与漏斗，再看收益。

## 5. 保护臂消融

E 在 A/C 上触发 9 次，在 B/D 上触发 8 次；两组的收益/MDD分别从 `-33.52%/-57.28%` 恶化至 `-64.10%/-74.91%`，以及从 `-8.54%/-50.27%` 恶化至 `-27.52%/-60.50%`。固定入场 ATR stop 不是该机制的有效尾部保护。

## 6. 机器证据

- [核心 OAT](../artifacts/hype_1d_ma7_original_trend_2026-08-09_core_sensitivity.csv)
- [RSI 邻域](../artifacts/hype_1d_ma7_original_trend_2026-08-09_rsi_sensitivity.csv)
- [A–D 主指标](../artifacts/hype_1d_ma7_original_trend_2026-08-09_metrics.csv)
- [压力](../artifacts/hype_1d_ma7_original_trend_2026-08-09_stress.csv)与[E 保护](../artifacts/hype_1d_ma7_original_trend_2026-08-09_protection.csv)
- [诊断总报告](../diagnostics/hype-1d-ma7-original-trend-state-machine-2026-08-09.md)
