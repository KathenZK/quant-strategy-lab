# HYPE-15M-Pullback-Trail bracket 可执行搜索 2026-06-30

Family id：`HYPE-15M-Pullback-Trail`

本报告把 15m 回踩/恢复信号只当作事件源，放弃旧 V3.3 的 delayed trailing，重新搜索入场即可挂出的固定 TP/SL bracket 与 timeout 退出。

## 数据与执行口径

- 数据源：本地标准数据湖 Binance HYPEUSDT USD-M Futures `5m`，补齐后重采样为闭合 `15m`。
- 5m 范围：`2025-05-30 10:30:00+00:00` -> `2026-06-30 06:15:00+00:00`，行数 `113998`，缺口 `0`。
- 15m 范围：`2025-05-30 10:30:00+00:00` -> `2026-06-30 06:00:00+00:00`，行数 `37999`，缺口 `0`。
- 成本：手续费 `4.1466 bps/成交额`，入场滑点 `10.73 bps`，出场滑点 `-2.64 bps`。
- 信号：已收盘 15m K 确认，下一根 15m open 成交；持仓期间忽略新信号。
- 退出：入场后立即有 reduce-only TP/SL；同根同时触及按 stop first；开盘跳过 TP/SL 按 open/目标价保守处理；timeout 到期按开盘市价退出。

## 搜索规模

- prescreen 行数：`6959`。
- full refine 行数：`3531`。
- balanced pass：`60/3531`。

## 前排结果

| label | pass | 交易数 | 收益 | 年化 | 胜率 | PF | payoff | 回撤 | OOS交易 | OOS PF |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `ema21_96_pb0.015_long_nocandle__ret32>=600__tp2_sl4_tx24` | `True` | `70` | `39.56%` | `1.36x` | `62.86%` | `1.677` | `0.991` | `-12.49%` | `9` | `5.167` |
| `ema21_96_pb0.015_long_nocandle__ret32>=600__tp2.5_sl4_tx24` | `True` | `67` | `36.90%` | `1.34x` | `59.70%` | `1.637` | `1.105` | `-12.43%` | `9` | `2.971` |
| `ema21_96_pb0.015_long_nocandle__ret32>=600__tp2.5_sl7_tx24` | `True` | `67` | `35.52%` | `1.32x` | `59.70%` | `1.608` | `1.085` | `-12.57%` | `9` | `2.971` |
| `ema21_96_pb0.015_long_nocandle__ret32>=600__tp2_sl7_tx24` | `True` | `70` | `38.16%` | `1.35x` | `62.86%` | `1.646` | `0.973` | `-13.37%` | `9` | `5.167` |
| `ema21_96_pb0.015_long_nocandle__ret32>=600__tp2_sl3_tx24` | `True` | `70` | `32.56%` | `1.30x` | `61.43%` | `1.544` | `0.970` | `-10.32%` | `9` | `1.868` |
| `ema21_96_pb0.015_long_nocandle__ret32>=600__tp2.5_sl5_tx24` | `True` | `67` | `33.53%` | `1.31x` | `59.70%` | `1.567` | `1.058` | `-13.85%` | `9` | `2.971` |
| `ema21_96_pb0.015_long_nocandle__ret32>=600__tp2_sl5_tx24` | `True` | `70` | `36.14%` | `1.33x` | `62.86%` | `1.604` | `0.948` | `-14.64%` | `9` | `5.167` |
| `ema21_96_pb0.015_long_nocandle__ret32>=600__tp4_sl5_tx16` | `True` | `64` | `23.76%` | `1.22x` | `45.31%` | `1.552` | `1.873` | `-17.04%` | `7` | `1.966` |
| `ema21_96_pb0.015_long_nocandle__ret32>=600__tp4_sl7_tx16` | `True` | `64` | `23.76%` | `1.22x` | `45.31%` | `1.552` | `1.873` | `-17.04%` | `7` | `1.966` |
| `ema21_96_pb0.015_long_nocandle__ret32>=600__tp2.5_sl3_tx24` | `True` | `67` | `29.39%` | `1.27x` | `58.21%` | `1.499` | `1.076` | `-12.43%` | `9` | `1.399` |
| `ema21_96_pb0.015_long_nocandle__ret32>=600__tp4_sl4_tx16` | `True` | `64` | `23.38%` | `1.21x` | `45.31%` | `1.541` | `1.860` | `-17.30%` | `7` | `1.966` |
| `ema21_96_pb0.015_long_nocandle__ret32>=600__htf>=0__tp2_sl4_tx8` | `True` | `54` | `15.22%` | `1.14x` | `53.70%` | `1.538` | `1.326` | `-7.58%` | `7` | `5.771` |

## 最佳候选

- label：`ema21_96_pb0.015_long_nocandle__ret32>=600__tp2_sl4_tx24`
- signal：`ema21_96_pb0.015_long_nocandle`
- filter：`ret32>=600`
- exit：`tp2_sl4_tx24`
- full：`70` 笔，收益 `39.56%`，年化 `1.36x`，胜率 `62.86%`，PF `1.677`，payoff `0.991`，最大回撤 `-12.49%`。
- OOS `2026-06-01 -> latest`：`9` 笔，收益 `11.39%`，PF `5.167`，胜率 `77.78%`。
- 月度：盈利月 `9/14`；最差月 `2025-11` 收益 `-8.62%`。

### 最佳候选切片

| slice | 交易数 | 收益 | 胜率 | PF | payoff | 回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full` | `70` | `39.56%` | `62.86%` | `1.677` | `0.991` | `-12.49%` |
| `is_2025_05_30_to_2026_03_01` | `49` | `11.22%` | `57.14%` | `1.275` | `0.956` | `-12.49%` |
| `val_2026_03_01_to_2026_06_01` | `12` | `12.65%` | `75.00%` | `3.197` | `1.066` | `-7.26%` |
| `oos_2026_06_01_to_latest` | `9` | `11.39%` | `77.78%` | `5.167` | `1.476` | `-3.41%` |
| `slice_2025_05_30_to_2025_09_01` | `14` | `8.80%` | `64.29%` | `2.028` | `1.127` | `-6.94%` |
| `slice_2025_09_01_to_2025_12_01` | `18` | `-9.58%` | `38.89%` | `0.514` | `0.808` | `-12.48%` |
| `slice_2025_12_01_to_2026_03_01` | `17` | `13.06%` | `70.59%` | `1.841` | `0.767` | `-10.09%` |
| `slice_2026_03_01_to_2026_06_01` | `12` | `12.65%` | `75.00%` | `3.197` | `1.066` | `-7.26%` |

### 成本压力

| cost model | 交易数 | 收益 | 胜率 | PF | payoff | 回撤 | OOS收益 | OOS PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `observed_v33` | `70` | `39.56%` | `62.86%` | `1.677` | `0.991` | `-12.49%` | `11.39%` | `5.167` |
| `binance_default_10bp_fee_4bp_slip` | `71` | `28.51%` | `60.56%` | `1.483` | `0.966` | `-15.10%` | `9.81%` | `4.321` |
| `stress_10bp_fee_8bp_slip` | `70` | `20.46%` | `61.43%` | `1.356` | `0.852` | `-16.45%` | `9.27%` | `3.986` |
| `low_fee_4bp_fee_4bp_slip` | `71` | `39.92%` | `61.97%` | `1.676` | `1.029` | `-12.66%` | `10.99%` | `5.038` |

## 结论

本轮找到了满足宽松 balanced gate 的 bracket 候选，但它仍只能作为 audit 研究候选，原因是 OOS 样本较短，且参数来自同一资产同一历史窗口搜索。

后续若推进，应优先做 walk-forward 阈值固化和 audit runner，而不是直接写真钱 live spec。

## 产物

- 脚本：`research/hype/15m-pullback-trail/scripts/research_hype_15m_pbtr_bracket_search.py`
- JSON：`research/hype/15m-pullback-trail/artifacts/hype_15m_pbtr_bracket_search_2026-06-30.json`
- prescreen CSV：`research/hype/15m-pullback-trail/artifacts/hype_15m_pbtr_bracket_search_prescreen_2026-06-30.csv`
- summary CSV：`research/hype/15m-pullback-trail/artifacts/hype_15m_pbtr_bracket_search_summary_2026-06-30.csv`
- slices CSV：`research/hype/15m-pullback-trail/artifacts/hype_15m_pbtr_bracket_search_slices_2026-06-30.csv`
- monthly CSV：`research/hype/15m-pullback-trail/artifacts/hype_15m_pbtr_bracket_search_monthly_2026-06-30.csv`
- best trades CSV：`research/hype/15m-pullback-trail/artifacts/hype_15m_pbtr_bracket_search_best_trades_2026-06-30.csv`
- cost stress CSV：`research/hype/15m-pullback-trail/artifacts/hype_15m_pbtr_bracket_search_cost_stress_2026-06-30.csv`
