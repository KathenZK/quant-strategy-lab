# HYPE-15M-MII 干净参数演化 2026-06-29

Family：`HYPE-15M-Multi-Indicator-Intraday`（alias：`HYPE-15M-MII`）

## 结论

本轮先根据 V1 全参数消融收缩配置，再对仍有信息量的参数做确定性多目标演化。搜索同时惩罚高回撤、低胜率、低交易支持、后半段或 Last90 亏损，并使用 purge 后的季度切片降低边界污染。

- 唯一候选数：`7926`；risk-feasible：`201`；Pareto：`78`。
- 原始 `>=2000%` 年化目标通过：`0/7926`。
- 同时超过 clean baseline 年化、回撤和胜率：`162`。
- 所有结果仍是同一历史样本上的二次优化，不是未见过的 forward OOS，因此不得直接 promotion。

## 参数清理

### 删除出配置的 dormant 字段

`min_adx14=0`、`min_h4_dir_spread=-99`、`min_dir_ret16/48/96=-99`、`max_atr_ratio96_672=99`、`min_previous_signal_age=0`、`max_churn192=999`、`cooldown_bars=0` 等字段在 V1 中等价于关闭，干净配置不再序列化它们。

### 冻结而不继续搜索

- `MACD(12,26,9)`：替代周期在消融中显著恶化，固定为 V1 周期。
- `ATR96`：替代窗口均未改善收益/回撤/近期稳定性，固定为 `96`。
- `max_atr_pct96=2.8%`：样本内放宽没有改变交易，但它是未来极端波动 guardrail，不因 dormant 就删除。
- `side=both`：作为策略行为固定，不再当作优化旋钮。
- 替代 signal family、trailing exit、ADX/H4/ret48/cooldown 等探针没有形成更好的 V1 邻域，本轮不带入。

### 继续演化

RSI 周期与阈值、ATR96 下限、RVOL96、可选 1h 方向确认、可选 directional RSI14 band、TP、SL、最长持仓，以及独立的 exposure 风险层。

## 数据与搜索

- 数据：`2025-05-30T10:30:00+00:00` 到 `2026-06-26T04:00:00+00:00`，`37607` 根闭合 K；data-quality gate `True`。
- 种群 `520`，代数 `16`，elite `130`，seed `20260630`。
- 固定成本：每次成交手续费 `0.1000%`，每次成交滑点 `0.0400%`，round-trip `0.2800%`；资金费未计入。
- 执行：V1 修正版 next-open、open-gap、timeout-open 和单仓时序。

## Clean Baseline

| 名称 | 年化 | 回撤 | 胜率 | 笔/日 | PF | 后半段年化 | Last90 年化 | 正收益季度 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `clean_rsi7_30_60_atrmin60_rvol0_h10_rsi14b0_tp90_sl280_hold16_x1p5` | `18.66%` | `-31.84%` | `75.28%` | `0.919` | `1.106` | `-33.00%` | `-41.44%` | `2/4` |

## 演化领先版本

| 名称 | 年化 | 回撤 | 胜率 | 笔/日 | PF | 后半段年化 | Last90 年化 | 正收益季度 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp120_sl450_hold16_x2` | `323.57%` | `-18.67%` | `78.99%` | `0.608` | `1.925` | `268.02%` | `245.66%` | `4/4` |

| 参数 | 值 |
| --- | ---: |
| `RSI window` | `7` |
| `RSI long cross` | `40.0` |
| `RSI short cross` | `55.0` |
| `ATR96 lower` | `0.0075` |
| `RVOL96 lower` | `1.0` |
| `1h direction confirm` | `False` |
| `directional RSI14 band` | `False` |
| `take profit` | `0.012` |
| `stop` | `0.045` |
| `max hold bars` | `16` |
| `exposure` | `2.0` |
| `MACD periods` | `(12, 26, 9)` |
| `ATR window` | `96` |
| `max ATR guardrail` | `0.028` |

## 多目标代表

### Risk-feasible 年化最高

| 名称 | 年化 | 回撤 | 胜率 | 笔/日 | PF | 后半段年化 | Last90 年化 | 正收益季度 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp120_sl450_hold16_x2` | `323.57%` | `-18.67%` | `78.99%` | `0.608` | `1.925` | `268.02%` | `245.66%` | `4/4` |

### 高胜率代表

| 名称 | 年化 | 回撤 | 胜率 | 笔/日 | PF | 后半段年化 | Last90 年化 | 正收益季度 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `clean_rsi7_40_60_atrmin105_rvol0_h10_rsi14b0_tp75_sl450_hold32_x1p5` | `58.06%` | `-12.30%` | `94.62%` | `0.332` | `2.401` | `51.42%` | `57.34%` | `4/4` |

### 低回撤代表

| 名称 | 年化 | 回撤 | 胜率 | 笔/日 | PF | 后半段年化 | Last90 年化 | 正收益季度 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `clean_rsi7_40_60_atrmin105_rvol0_h10_rsi14b0_tp120_sl450_hold32_x0p75` | `55.79%` | `-5.98%` | `91.60%` | `0.304` | `2.857` | `49.97%` | `38.85%` | `4/4` |

## Pareto Top

| 名称 | 年化 | 回撤 | 胜率 | 笔/日 | PF | 后半段年化 | Last90 年化 | 正收益季度 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp120_sl450_hold16_x2` | `323.57%` | `-18.67%` | `78.99%` | `0.608` | `1.925` | `268.02%` | `245.66%` | `4/4` |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp120_sl450_hold16_x1p75` | `256.76%` | `-16.44%` | `78.99%` | `0.608` | `1.925` | `215.29%` | `197.93%` | `4/4` |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp120_sl360_hold16_x1p75` | `207.51%` | `-18.44%` | `78.24%` | `0.610` | `1.754` | `247.39%` | `220.39%` | `4/4` |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp120_sl320_hold16_x1p75` | `200.13%` | `-17.86%` | `77.50%` | `0.613` | `1.728` | `217.89%` | `240.45%` | `4/4` |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp120_sl450_hold16_x1p5` | `199.71%` | `-14.18%` | `78.99%` | `0.608` | `1.925` | `169.46%` | `156.31%` | `4/4` |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp105_sl450_hold16_x1p75` | `176.49%` | `-16.18%` | `80.91%` | `0.615` | `1.786` | `190.86%` | `236.05%` | `4/4` |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp120_sl450_hold24_x1p75` | `234.66%` | `-19.96%` | `82.55%` | `0.600` | `1.795` | `169.96%` | `124.29%` | `4/4` |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp120_sl360_hold16_x1p5` | `163.93%` | `-15.92%` | `78.24%` | `0.610` | `1.754` | `192.53%` | `172.59%` | `4/4` |
| `clean_rsi7_40_60_atrmin75_rvol0p75_h10_rsi14b0_tp120_sl450_hold16_x1p5` | `208.03%` | `-17.67%` | `80.71%` | `0.648` | `1.860` | `80.09%` | `171.26%` | `4/4` |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp120_sl320_hold16_x1p5` | `158.43%` | `-15.41%` | `77.50%` | `0.613` | `1.728` | `171.18%` | `187.01%` | `4/4` |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp105_sl450_hold16_x1p5` | `140.63%` | `-13.95%` | `80.91%` | `0.615` | `1.786` | `151.08%` | `183.49%` | `4/4` |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp120_sl450_hold16_x1p25` | `151.15%` | `-11.90%` | `78.99%` | `0.608` | `1.925` | `129.75%` | `120.10%` | `4/4` |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp120_sl450_hold24_x1p5` | `184.32%` | `-17.25%` | `82.55%` | `0.600` | `1.795` | `136.55%` | `101.45%` | `4/4` |
| `clean_rsi7_40_55_atrmin75_rvol1_h10_rsi14b0_tp105_sl450_hold32_x1p75` | `170.57%` | `-19.98%` | `87.39%` | `0.608` | `1.698` | `134.46%` | `101.82%` | `3/4` |
| `clean_rsi9_40_60_atrmin75_rvol0p75_h10_rsi14b0_tp90_sl320_hold32_x2` | `135.68%` | `-17.23%` | `87.34%` | `0.605` | `1.625` | `123.87%` | `159.84%` | `3/4` |

## 状态判断

- 本轮可以产生更干净、更平衡的诊断版本，但不能据此声称已有可实盘策略。
- 数据截止早于审计日，且所有可用历史都已参与过 V1 搜索；没有真正 untouched forward holdout。
- 没有 tick/盘口级 stop-market、资金费、真实滑点、runner、重启恢复、订单对账和 kill switch。
- 任何领先版本都必须先做局部消融、参数扰动和新增 forward 数据复核，之后才能讨论版本提升。

## 产物

- 脚本：`research/hype/15m-multi-indicator-intraday/scripts/research_hype_15m_mii_clean_evolution.py`
- JSON：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_clean_evolution_2026-06-29.json`
- 全排名：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_clean_evolution_ranking_2026-06-29.csv`
- Pareto：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_clean_evolution_pareto_2026-06-29.csv`
- 时间切片：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_clean_evolution_slices_2026-06-29.csv`
