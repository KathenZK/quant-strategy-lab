# HYPE-30M K2-FQ-V2-ATRVT-OFF 全参数消融与精简微调

日期：2026-07-10

对象：`K2-FQ-V2-ATRVT-OFF`

研究候选：`K2-FQ-V2-ATRVT-OFF-PRUNED-TUNED`

状态：`explore / not promoted / not live-ready`

## 结论

全逻辑消融、13 个数值参数逐项扫描、时间分离 beam 微调和候选稳健性复测完成。找到一个同时满足“胜率提高、MDD 降低、全样本收益保留至少 70%”的精简候选：

| 指标 | 原 V2 严格基线 | 精简微调候选 | 变化 |
| --- | ---: | ---: | ---: |
| Return | `+4827.01%` | `+4638.01%` | `-189.00pp`，保留 `96.09%` |
| MDD | `-27.97%` | `-25.84%` | 改善 `2.13pp` |
| Sharpe | `4.05` | `4.22` | `+0.17` |
| Trades | `114` | `113` | `-1` |
| Win rate | `55.26%` | `56.64%` | `+1.37pp` |
| Profit factor | `2.59` | `2.76` | `+0.17` |
| Avg leverage | `2.66x` | `2.48x` | `-0.17x` |
| Worst trade | `-8.46%` | `-8.46%` | 不变 |
| TP / SL / time | `10 / 39 / 65` | `10 / 38 / 65` | 少 1 次 SL |

候选改善不是通过放宽 stop 或缩短持仓制造的：TP `10%`、SL `2.5%`、`hold=30` 均保持不变。主要来自更快的 1h slow regime、稍长 slope 确认和更低 ATR 风险预算。

该候选仍不能 promotion：Gate 3 交易重排尾部、Gate 6 启动时间、Gate 7 30m 相位继续失败；最新 holdout 只有 1 笔亏损交易，证据不足。

## 成本与数据

- Binance USDM perpetual `HYPEUSDT`。
- `1m` 闭合 K 线重采样为 `30m` / `1h`。
- UTC：`2025-05-30 10:30` 至 `2026-07-10 06:43`。
- 手续费：`0.001/fill`。
- 不利滑点：`0.0004/fill`。
- Binance 历史 funding：计入。
- 数据质量：完整 raw/normalized/cache 对拍通过。

## 选择协议

- Prefit：特征就绪至 `2026-01-31 00:00 UTC`。
- Gap：`2026-01-31` 至 `2026-02-14`。
- Validation：`2026-02-14` 至 `2026-06-30`。
- Holdout：`2026-06-30` 至数据末端。
- Beam width：`10`。
- 最终硬约束：全样本胜率高于基线、MDD 小于基线、收益至少保留 `70%`、validation 收益为正。

这不是严格意义的真正 OOS：原外部策略及本家族研究已经使用过大部分历史。时间切分仅用于降低本轮微调的直接过拟合风险。

## 移除的冗余项

### 1. `close > ema_slow` / `close < ema_slow`

从 1h regime 中移除。原始与候选参数下均逐笔完全等价：

```text
旧 long regime  = fast > slow and close > slow and slope > 0
新 long regime  = fast > slow and slope > 0

旧 short regime = fast < slow and close < slow and slope < 0
新 short regime = fast < slow and slope < 0
```

在当前 Keltner 突破事件上，该 close guard 没有改变任何 entry、exit、方向、杠杆或指标。

### 2. `not opposite_regime`

从信号表达式中移除。`fast > slow` 与 `fast < slow` 不可能同时成立，因此 long signal 再检查 `not short_regime`、short signal 再检查 `not long_regime` 是逻辑死条件。

### 3. `min_leverage=1.0`

移除最小杠杆 floor，候选使用无下限风险预算（实现常量 `0.0`）。逐项扫描 `0.0 / 0.5 / 1.0 / 1.25` 在全样本均完全等价，说明历史入场的 raw leverage 从未低于 `1.25x`。

移除后若未来遇到更高波动，仓位可以低于 1x，只会降低风险，不会强迫账户维持最低 1x 暴露。

原外部复现脚本仍保留旧规则，以保证同事规格可复现；精简逻辑只用于本研究候选。

## 保留的部件

| 消融 | Return | MDD | Win rate | 结论 |
| --- | ---: | ---: | ---: | --- |
| 完整基线 | `+4827.01%` | `-27.97%` | `55.26%` | 对照 |
| 去 1h slope | `+4131.61%` | `-27.97%` | `54.24%` | slope 有正贡献 |
| 去 fast-vs-slow | `+2667.43%` | `-34.93%` | `51.91%` | EMA 方向条件重要 |
| 去整个 1h regime | `+625.70%` | `-42.22%` | `44.38%` | regime 是核心过滤 |
| 去 Keltner breakout | `-99.97%` | `-99.98%` | `35.27%` | breakout 是核心 alpha |
| 固定 1x | `+304.60%` | `-14.88%` | `55.26%` | 动态 sizing 是收益来源，不能删 |
| 固定历史平均杠杆 | `+2664.44%` | `-35.32%` | `55.26%` | ATR sizing 明显改善路径 |
| 去 3x cap | `+8638.01%` | `-31.59%` | `55.26%` | 收益上升但风险加深，cap 必须保留 |
| 去 TP | `+1586.93%` | `-52.61%` | `54.05%` | TP 有风险与收益贡献 |
| 去 SL | `+1182.14%` | `-64.47%` | `60.36%` | 胜率虚高但 worst trade `-44.76%`，不可接受 |
| 去 time exit | `+2927.74%` | `-49.74%` | `34.34%` | time exit 必须保留 |

特别注意：移除 SL 会把胜率提高到 `60.36%`，但同时把 MDD 放大到 `-64.47%`。这证明不能把“更高胜率”单独作为优化目标。

## 全参数逐项敏感性

| 参数 | 扫描范围 | 主要发现 |
| --- | --- | --- |
| Keltner EMA | `8–12` | `10` 明显最佳；偏离后收益最低仅 `+337.04%` |
| Keltner ATR | `8–12` | `9–10` 较好，窗口 9 胜率最高；候选保守保留 10 |
| Keltner multiplier | `1.8–2.2` | `2.0` 是明显中心，偏离会显著加深 MDD |
| 1h EMA fast | `12–20` | `14–16` 稳定；候选保留 16 |
| 1h EMA slow | `40–56` | `44` 同时提高收益与胜率 |
| 1h slope lag | `2–6` | `5` 优于原 4；去 slope 会退化 |
| leverage ATR | `72–120` | 敏感性较低，但复用 ATR10 会使收益降至 `+2947.27%`，独立慢 ATR 仍应保留 |
| ATR target | `2.4%–3.6%` | 越低 MDD 越小；`2.7%` 在收益保留与风险间更平衡 |
| min leverage | `0–1.25x` | 全部逐项等价，已移除 |
| max leverage | `2.25–3.25x` | 明显控制收益/MDD；候选保留 `3.0x` |
| TP | `8%–12%` | 原 `10%` 最稳定 |
| SL | `2%–3%` | 更宽 SL 可提高胜率但加深 MDD；保留 `2.5%` |
| hold | `24–36` | 短 hold 可提高胜率但收益/MDD综合不如 30；保留 30 |

## 精简微调候选参数

| 参数 | 原 V2 | 候选 | 决策 |
| --- | ---: | ---: | --- |
| Keltner EMA | `10` | `10` | 保留 |
| Keltner ATR | `10` | `10` | 保留 |
| Keltner multiplier | `2.0` | `2.0` | 保留 |
| 1h EMA fast | `16` | `16` | 保留 |
| 1h EMA slow | `48` | `44` | 微调 |
| 1h slope lag | `4` | `5` | 微调 |
| leverage ATR | `96` | `84` | 微调 |
| ATR target | `3.0%` | `2.7%` | 降低风险预算 |
| minimum leverage | `1.0x` | 无 | 移除 |
| maximum leverage | `3.0x` | `3.0x` | 保留 |
| TP | `10%` | `10%` | 保留 |
| SL | `2.5%` | `2.5%` | 保留 |
| max hold | `30` | `30` | 保留 |

候选 regime：

```text
long_regime  = ema_fast16 > ema_slow44 and (ema_slow44[t] - ema_slow44[t-5]) > 0
short_regime = ema_fast16 < ema_slow44 and (ema_slow44[t] - ema_slow44[t-5]) < 0
```

候选杠杆：

```text
raw_leverage = 0.027 / (ATR84_30m / entry_open)
leverage = min(raw_leverage, 3.0)
```

## 时间分离结果

| Window | 原 V2 | 候选 |
| --- | ---: | ---: |
| Prefit Return | `+765.27%` | `+742.98%` |
| Prefit MDD | `-27.97%` | `-25.84%` |
| Prefit Win rate | `53.52%` | `54.93%` |
| Validation Return | `+596.91%` | `+577.08%` |
| Validation MDD | `-21.65%` | `-19.65%` |
| Validation Win rate | `64.10%` | `65.79%` |
| Holdout Return | `-2.86%` | `-2.86%` |
| Holdout Trades | `1` | `1` |

Validation 同样实现胜率提高、MDD 降低、收益小幅下降。Holdout 只有 1 笔 time exit 亏损，不能据此判断候选优劣。

44 组滚动 OOS 的正收益占比为 `95.45%`、零交易窗口 `0`；候选窗口收益中位数 `+34.46%`，原 V2 为 `+32.35%`。

## 最近分片

| Window | Candidate Return | Candidate MDD |
| --- | ---: | ---: |
| `1d` | `0.00%` | `0.00%` |
| `7d` | `-2.86%` | `-10.12%` |
| `1m` | `+28.95%` | `-14.40%` |
| `3m` | `+301.33%` | `-14.40%` |
| `6m` | `+1068.00%` | `-23.85%` |
| `1y` | `+4018.81%` | `-23.85%` |

## 候选门禁复测

| 门禁 | 结果 | 证据 |
| --- | --- | --- |
| Gate 2 rolling OOS | 通过 | 44 组，正收益 `95.45%`，收益中位数 `+34.46%` |
| Gate 3 Monte Carlo | **失败** | K 线扰动 100% 盈利、bootstrap p05 `+845.52%`；但交易重排 MDD p05 `-40.85%`，差于候选 1.5×门槛 `-38.77%` |
| Gate 5 significance | 通过 | PSR `1.0000`，DSR(N=1000) `0.9672` |
| Gate 6 start time | **失败** | 23 个起跑点均盈利，但 CAGR CV `0.917` |
| Gate 7 phase | **失败** | 30m 非原生/原生中位 CAGR 比 `9.72%`，CV `1.335`；1h 相位通过 |

候选改善了统计显著性，但未解决当前家族最关键的 30m 边界依赖，也未彻底解决交易排列后的回撤尾部。

## 决策

保留 `K2-FQ-V2-ATRVT-OFF-PRUNED-TUNED` 为 **精简微调观察值**，不覆盖外部 V2 严格基线，不登记正式版本，不进入 runner。

后续最值得做的不是继续在原生 `:00/:30` 相位追收益，而是研究如何让非原生 30m 相位收敛；否则继续微调容易强化已有的相位选择偏差。

## 证据

- 研究脚本：[../scripts/research_hype_30m_k2_v2_full_ablation_and_tune.py](../scripts/research_hype_30m_k2_v2_full_ablation_and_tune.py)
- 汇总：[../artifacts/hype_30m_k2_v2_full_ablation_tune_2026-07-10.json](../artifacts/hype_30m_k2_v2_full_ablation_tune_2026-07-10.json)
- 全逻辑消融：[../artifacts/hype_30m_k2_v2_full_ablation_2026-07-10.csv](../artifacts/hype_30m_k2_v2_full_ablation_2026-07-10.csv)
- 参数敏感性：[../artifacts/hype_30m_k2_v2_parameter_sensitivity_2026-07-10.csv](../artifacts/hype_30m_k2_v2_parameter_sensitivity_2026-07-10.csv)
- Beam 路径：[../artifacts/hype_30m_k2_v2_tuning_beam_2026-07-10.csv](../artifacts/hype_30m_k2_v2_tuning_beam_2026-07-10.csv)
- Finalists：[../artifacts/hype_30m_k2_v2_tuning_finalists_2026-07-10.csv](../artifacts/hype_30m_k2_v2_tuning_finalists_2026-07-10.csv)
- 候选逐笔：[../artifacts/hype_30m_k2_v2_tuned_trades_2026-07-10.csv](../artifacts/hype_30m_k2_v2_tuned_trades_2026-07-10.csv)
- Rolling OOS：[../artifacts/hype_30m_k2_v2_tuning_rolling_oos_2026-07-10.csv](../artifacts/hype_30m_k2_v2_tuning_rolling_oos_2026-07-10.csv)
- Monte Carlo：[../artifacts/hype_30m_k2_v2_tuning_monte_carlo_2026-07-10.csv](../artifacts/hype_30m_k2_v2_tuning_monte_carlo_2026-07-10.csv)
- Start time：[../artifacts/hype_30m_k2_v2_tuning_start_time_2026-07-10.csv](../artifacts/hype_30m_k2_v2_tuning_start_time_2026-07-10.csv)
- Phase：[../artifacts/hype_30m_k2_v2_tuning_phase_2026-07-10.csv](../artifacts/hype_30m_k2_v2_tuning_phase_2026-07-10.csv)
- Stress：[../artifacts/hype_30m_k2_v2_tuning_stress_2026-07-10.csv](../artifacts/hype_30m_k2_v2_tuning_stress_2026-07-10.csv)
