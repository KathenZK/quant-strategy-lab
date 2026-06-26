# HYPE-15M-MII 表面改善参数组合优化 2026-06-26

Family id：`HYPE-15M-MII`

## 结论

本轮把全参数消融里“表面改善最大”的单因子组合成网格测试，目标是寻找年化收益高于基线且最大回撤不差于基线的优化版本。结果没有找到可同时满足这两个目标、交易形态和最近稳定性的组合。

- 测试组合数：`595`（含基线）。
- 收益高于基线且回撤不差于基线：`0/594`。
- 完整 optimization gate 通过：`0/594`。

因此这次组合优化仍不能把该策略提升为 candidate；更高收益通常来自放大止盈或保留更多波动交易，但回撤同步变差。更低回撤通常来自加过滤，但收益和交易频率明显下降。

## 数据与口径

- 数据：`data/cache/hypeusdt_15m_fapi.csv`，`2025-05-30 10:30:00+00:00` 到 `2026-06-25 13:45:00+00:00`，`37550` 根 `15m` K。
- 数据质量：缺口 `0`，重复 timestamp `0`，关键空值 `0`，非法 OHLC `0`。
- 限制：仍是 cache reproduction，缺少 `quote_volume/trade_count/vwap/source/is_closed`；不得按标准数据湖 promotion 结果使用。
- 成本：每边手续费 `0.0500%`，每边滑点 `0.0250%`，round-trip `0.1500%`。
- 执行：闭合 K 产生信号，下一根 open 入场；固定 TP/SL intrabar 检查；同根 TP/SL 保守按 stop first；单仓不重叠。

## 基线

| 年化 | 回撤 | 胜率 | 笔数 | 笔/日 | PF | 后半段年化 | Last90 年化 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `141.92%` | `-18.88%` | `76.90%` | `368` | `0.941` | `1.475` | `29.89%` | `-5.26%` |

## 严格通过组合

无。

## 收益更高且回撤更小的组合

无。

## 样本内收益最高的组合

| 组合 | 年化 | 回撤 | 胜率 | 笔数 | 笔/日 | PF | 后半段年化 | Last90 年化 | OOS 笔数 | 目标通过 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rsi7_30_60__fixed_tp1p2_sl2p8_hold16__baseline_filter__x1p5` | `174.81%` | `-23.24%` | `71.26%` | `348` | `0.890` | `1.470` | `65.38%` | `45.86%` | `32` | `False` |
| `bb_reversion_w48_k1p5__fixed_tp1p2_sl2p8_hold16__baseline_filter__x1p5` | `153.01%` | `-19.94%` | `71.29%` | `303` | `0.775` | `1.493` | `34.83%` | `124.44%` | `25` | `False` |

## 回撤最低的组合

| 组合 | 年化 | 回撤 | 胜率 | 笔数 | 笔/日 | PF | 后半段年化 | Last90 年化 | OOS 笔数 | 目标通过 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rsi14_30_60__fixed_tp0p9_sl2p8_hold16__min_rvol96_0p75__min_h1_dir_spread_0p0__x1p0` | `15.92%` | `-4.65%` | `83.67%` | `49` | `0.125` | `2.228` | `14.01%` | `18.99%` | `6` | `False` |
| `rsi14_30_60__fixed_tp1p2_sl2p8_hold8__min_rvol96_0p75__min_h1_dir_spread_0p0__x1p0` | `7.65%` | `-4.90%` | `59.62%` | `52` | `0.133` | `1.440` | `2.77%` | `-1.77%` | `7` | `False` |
| `bb_reversion_w48_k1p5__fixed_tp1p2_sl2p8_hold8__min_rvol96_0p75__min_h1_dir_spread_0p0__x1p0` | `14.26%` | `-5.19%` | `61.54%` | `65` | `0.166` | `1.653` | `10.08%` | `15.82%` | `9` | `False` |
| `rsi14_30_60__fixed_tp1p2_sl2p8_hold8__min_rvol96_0p75__min_dir_rsi14_48p0__max_dir_rsi14_78p0__x1p0` | `11.46%` | `-5.19%` | `70.27%` | `37` | `0.095` | `2.059` | `10.89%` | `12.68%` | `4` | `False` |
| `rsi14_30_60__fixed_tp1p2_sl2p8_hold8__min_dir_rsi14_48p0__max_dir_rsi14_78p0__x1p0` | `14.15%` | `-5.19%` | `70.73%` | `41` | `0.105` | `2.225` | `11.85%` | `12.68%` | `4` | `False` |
| `rsi7_30_60__fixed_tp1p2_sl2p8_hold8__min_rvol96_0p75__min_dir_rsi14_48p0__max_dir_rsi14_78p0__x1p0` | `19.89%` | `-5.24%` | `67.65%` | `68` | `0.174` | `1.931` | `25.35%` | `20.26%` | `8` | `False` |
| `rsi7_30_60__fixed_tp0p9_sl2p8_hold16__min_rvol96_0p75__min_dir_rsi14_48p0__max_dir_rsi14_78p0__x1p0` | `17.62%` | `-5.24%` | `79.71%` | `69` | `0.176` | `1.802` | `17.20%` | `14.68%` | `8` | `False` |
| `rsi7_30_60__fixed_tp1p2_sl2p8_hold16__min_rvol96_0p75__min_dir_rsi14_48p0__max_dir_rsi14_78p0__x1p0` | `27.01%` | `-5.28%` | `74.63%` | `67` | `0.171` | `2.137` | `29.77%` | `38.42%` | `7` | `False` |
| `rsi7_30_60__fixed_tp1p2_sl1p8_hold16__min_dir_rsi14_48p0__max_dir_rsi14_78p0__x1p0` | `18.07%` | `-5.36%` | `68.09%` | `94` | `0.240` | `1.410` | `20.22%` | `27.26%` | `11` | `False` |
| `bb_reversion_w48_k1p5__fixed_tp1p2_sl1p8_hold16__min_dir_rsi14_48p0__max_dir_rsi14_78p0__x1p0` | `13.16%` | `-5.51%` | `70.69%` | `58` | `0.148` | `1.515` | `1.62%` | `14.71%` | `4` | `False` |
| `rsi7_30_60__fixed_tp0p9_sl2p8_hold16__min_rvol96_1p0__min_atr_pct96_0p009__x1p0` | `20.64%` | `-5.62%` | `87.50%` | `64` | `0.164` | `1.958` | `10.82%` | `19.90%` | `8` | `False` |
| `rsi14_30_60__fixed_tp0p9_sl2p8_hold16__min_rvol96_0p75__min_h1_dir_spread_0p0__x1p25` | `20.19%` | `-5.80%` | `83.67%` | `49` | `0.125` | `2.228` | `17.73%` | `24.25%` | `6` | `False` |
| `rsi7_30_60__fixed_tp1p2_sl2p8_hold16__min_dir_rsi14_48p0__max_dir_rsi14_78p0__x1p0` | `30.13%` | `-5.81%` | `71.74%` | `92` | `0.235` | `1.802` | `31.60%` | `35.30%` | `11` | `False` |
| `rsi14_30_60__fixed_tp1p2_sl1p8_hold16__min_dir_rsi14_48p0__max_dir_rsi14_78p0__x1p0` | `3.10%` | `-5.83%` | `64.29%` | `42` | `0.107` | `1.155` | `-1.97%` | `5.15%` | `4` | `False` |
| `bb_reversion_w48_k1p5__fixed_tp0p9_sl2p8_hold16__min_rvol96_0p75__min_h1_dir_spread_0p0__x1p0` | `25.67%` | `-5.87%` | `82.81%` | `64` | `0.164` | `2.785` | `18.28%` | `28.68%` | `8` | `False` |

## 折中排序最高组合

- 组合：`bb_reversion_w48_k1p5__fixed_tp1p2_sl2p8_hold16__baseline_filter__x1p5`。
- 年化 `153.01%`，最大回撤 `-19.94%`，胜率 `71.29%`，交易 `303` 笔，`0.775` 笔/日。
- 它没有通过优化目标：`return_and_dd_pass=False`，`recent_pass=True`，`trade_shape_pass=True`。

## 时间稳定性摘要

- 最差月：`2025-07`，年化 `-67.86%`，总收益 `-9.19%`。
- 基线最差滚动 `90d`：`rolling_90d_011_20260326_20260624`，年化 `-7.29%`，总收益 `-1.85%`，回撤 `-15.55%`。

## 参数结论

- `TP=1.2%` 是最接近“收益提高”的单因子，但和其他过滤组合后很难同时保持基线回撤与交易频率。
- `rvol`、`min_atr`、`h1`、`RSI band` 可以降低回撤或提高 PF，但本质是减少交易；组合后收益通常低于基线。
- `BB reversion` 和 trailing 出口改善了最近窗口，但全样本回撤或胜率不足，不能作为优化版。
- 更高杠杆不是优化，只是放大收益和回撤；本轮目标是收益更高且回撤更小，因此不把加杠杆当作解决方案。

## 产物

- 脚本：`research/hype/15m-multi-indicator-intraday/scripts/research_hype_15m_mii_surface_combo_optimization.py`
- JSON：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_surface_combo_optimization_2026-06-26.json`
- 汇总 CSV：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_surface_combo_optimization_summary_2026-06-26.csv`
- 验证切片 CSV：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_surface_combo_optimization_slices_2026-06-26.csv`
- 滚动切片 CSV：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_surface_combo_optimization_rolling_2026-06-26.csv`
- 月切片 CSV：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_surface_combo_optimization_monthly_2026-06-26.csv`
