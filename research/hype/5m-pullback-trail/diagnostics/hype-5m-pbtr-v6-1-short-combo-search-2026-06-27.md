# HYPE-5M-PBTR-V6.1 short combo search 2026-06-27

Family id：`HYPE-5M-PBTR`

本报告尝试搜索一个 short-only executable bracket 策略，并与 `HYPE-5M-PBTR-V6.1` long-only 策略组合。组合回放严格单仓：任意时刻只允许一笔持仓，持仓期间另一边信号跳过。

结论先行：可以搜索出 short-only 正 EV 线索，且和 V6.1 long-only 组合后收益明显提高；但 short 侧验证样本仍偏少，尤其 top 组合的 VAL/OOS 笔数不足以直接提升为实盘候选。当前最值得继续观察的是 `combo_short_rank2`：总收益从 V6.1 long-only 的 `408.95%` 提高到 `833.71%`，最大回撤从 `-25.63%` 降到 `-22.38%`，但 short-only 自身只有 `53` 笔、OOS 只有 `5` 笔。

## Short-Only Top

| rank | signal | exit | rule | trades | total | PF | avg | win | DD | IS PF | VAL PF | OOS trades | OOS PF | pass |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `1` | `pullback_reclaim_ema34_144_pb0.005_short_candle_htf0.5` | `tp2_sl3_tr0_tx48` | `dir_ret48_bps>=400` | `55` | `31.51%` | `1.783` | `0.52%` | `69.09%` | `-10.23%` | `1.731` | `∞` | `6` | `1.917` | `True` |
| `2` | `pullback_reclaim_ema34_144_pb0_short_nocandle_htfnone` | `tp1.5_sl2_tr0_tx48` | `dir_ret48_bps>=400` | `53` | `24.47%` | `1.764` | `0.43%` | `67.92%` | `-18.07%` | `1.774` | `1.444` | `5` | `1.791` | `True` |
| `3` | `pullback_reclaim_ema21_55_pb0_short_candle_htf0.5` | `tp3_sl5_tr0_tx36` | `dir_ret48_bps>=400` | `51` | `29.41%` | `1.742` | `0.54%` | `72.55%` | `-14.12%` | `1.587` | `∞` | `9` | `2.029` | `True` |
| `4` | `pullback_reclaim_ema21_96_pb0_short_candle_htf0.5` | `tp3_sl5_tr0_tx36` | `dir_ret48_bps>=400` | `51` | `29.41%` | `1.742` | `0.54%` | `72.55%` | `-14.12%` | `1.587` | `∞` | `9` | `2.029` | `True` |
| `5` | `pullback_reclaim_ema21_55_pb0_short_nocandle_htf0.5` | `tp3_sl5_tr0_tx36` | `dir_ret48_bps>=400` | `57` | `30.45%` | `1.717` | `0.49%` | `68.42%` | `-20.51%` | `1.426` | `∞` | `9` | `2.889` | `True` |
| `6` | `pullback_reclaim_ema21_96_pb0_short_nocandle_htf0.5` | `tp3_sl5_tr0_tx36` | `dir_ret48_bps>=400` | `57` | `30.45%` | `1.717` | `0.49%` | `68.42%` | `-20.51%` | `1.426` | `∞` | `9` | `2.889` | `True` |
| `7` | `pullback_reclaim_ema34_144_pb0.005_short_candle_htf0.5` | `tp2_sl3_tr0_tx36` | `dir_ret48_bps>=400` | `56` | `27.98%` | `1.715` | `0.46%` | `69.64%` | `-11.41%` | `1.715` | `∞` | `6` | `1.504` | `True` |
| `8` | `pullback_reclaim_ema34_144_pb0.005_short_candle_htf0.5` | `tp2_sl3_tr0_tx72` | `dir_ret48_bps>=400` | `55` | `27.75%` | `1.679` | `0.47%` | `69.09%` | `-10.23%` | `1.615` | `∞` | `6` | `1.917` | `True` |
| `9` | `pullback_reclaim_ema34_144_pb0_short_nocandle_htfnone` | `tp1.5_sl2_tr0_tx36` | `dir_ret48_bps>=400` | `54` | `21.46%` | `1.677` | `0.37%` | `66.67%` | `-17.66%` | `1.673` | `1.444` | `5` | `1.791` | `True` |
| `10` | `pullback_reclaim_ema34_144_pb0_short_nocandle_htfnone` | `tp1.5_sl2_tr0_tx12` | `dir_ret48_bps>=400` | `55` | `19.56%` | `1.676` | `0.34%` | `60.00%` | `-19.13%` | `1.607` | `1.444` | `5` | `2.874` | `True` |
| `11` | `pullback_reclaim_ema34_144_pb0_short_nocandle_htfnone` | `tp1.5_sl2_tr0_tx72` | `dir_ret48_bps>=400` | `53` | `20.76%` | `1.657` | `0.37%` | `67.92%` | `-18.07%` | `1.650` | `1.444` | `5` | `1.791` | `True` |
| `12` | `pullback_reclaim_ema34_144_pb0_short_nocandle_htfnone` | `tp1.5_sl2_tr0_tx24` | `dir_ret48_bps>=400` | `55` | `21.15%` | `1.641` | `0.36%` | `65.45%` | `-17.64%` | `1.633` | `1.444` | `5` | `1.791` | `True` |
| `13` | `pullback_reclaim_ema21_55_pb0_short_nocandle_htf0.5` | `tp2.5_sl4_tr0_tx36` | `dir_ret48_bps>=400` | `60` | `28.53%` | `1.608` | `0.45%` | `70.00%` | `-21.30%` | `1.436` | `∞` | `9` | `2.257` | `True` |
| `14` | `pullback_reclaim_ema21_96_pb0_short_nocandle_htf0.5` | `tp2.5_sl4_tr0_tx36` | `dir_ret48_bps>=400` | `60` | `28.53%` | `1.608` | `0.45%` | `70.00%` | `-21.30%` | `1.436` | `∞` | `9` | `2.257` | `True` |
| `15` | `pullback_reclaim_ema21_55_pb0_short_candle_htf0.5` | `tp5_sl8_tr0_tx36` | `dir_ret48_bps>=400` | `50` | `23.63%` | `1.589` | `0.46%` | `66.00%` | `-13.50%` | `1.272` | `∞` | `9` | `2.441` | `True` |

上表 `pass` 是第一轮宽松 gate。进一步要求 `VAL>=5`、`OOS>=10` 后只剩 `2` 个 short-only 候选；要求 `VAL>=10` 后为 `0` 个。因此 top short 的方向可用，但稳健性还不够。

## Sample Gate Check

| signal | exit | rule | trades | total | DD | PF | VAL trades | VAL PF | OOS trades | OOS PF |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `pullback_reclaim_ema34_144_pb0.015_short_nocandle_htf0` | `tp5_sl8_tr0_tx72` | `dir_ret48_bps>=400` | `103` | `32.70%` | `-23.60%` | `1.309` | `5` | `2.409` | `15` | `1.477` |
| `pullback_reclaim_ema34_144_pb0.015_short_nocandle_htf0` | `tp2_sl3_tr0_tx48` | `dir_ret48_bps>=400` | `145` | `24.00%` | `-20.46%` | `1.209` | `5` | `∞` | `25` | `1.171` |

## Single-Position Combo Top

| combo | short rank | trades | total | max DD | avg | win | PF | worst | best | short label |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `combo_short_rank1` | `1` | `212` | `973.56%` | `-28.69%` | `1.26%` | `65.09%` | `1.776` | `-15.09%` | `18.60%` | `pullback_reclaim_ema34_144_pb0.005_short_candle_htf0.5__tp2_sl3_tr0_tx48__dir_ret48_bps>=400` |
| `combo_short_rank5` | `5` | `214` | `932.54%` | `-29.18%` | `1.24%` | `64.95%` | `1.754` | `-18.41%` | `18.18%` | `pullback_reclaim_ema21_55_pb0_short_nocandle_htf0.5__tp3_sl5_tr0_tx36__dir_ret48_bps>=400` |
| `combo_short_rank6` | `6` | `214` | `932.54%` | `-29.18%` | `1.24%` | `64.95%` | `1.754` | `-18.41%` | `18.18%` | `pullback_reclaim_ema21_96_pb0_short_nocandle_htf0.5__tp3_sl5_tr0_tx36__dir_ret48_bps>=400` |
| `combo_short_rank3` | `3` | `208` | `903.80%` | `-37.40%` | `1.26%` | `65.87%` | `1.763` | `-20.31%` | `13.12%` | `pullback_reclaim_ema21_55_pb0_short_candle_htf0.5__tp3_sl5_tr0_tx36__dir_ret48_bps>=400` |
| `combo_short_rank4` | `4` | `208` | `903.80%` | `-37.40%` | `1.26%` | `65.87%` | `1.763` | `-20.31%` | `13.12%` | `pullback_reclaim_ema21_96_pb0_short_candle_htf0.5__tp3_sl5_tr0_tx36__dir_ret48_bps>=400` |
| `combo_short_rank7` | `7` | `213` | `894.41%` | `-33.38%` | `1.21%` | `65.26%` | `1.755` | `-15.09%` | `10.98%` | `pullback_reclaim_ema34_144_pb0.005_short_candle_htf0.5__tp2_sl3_tr0_tx36__dir_ret48_bps>=400` |
| `combo_short_rank8` | `8` | `212` | `887.49%` | `-29.13%` | `1.22%` | `65.09%` | `1.742` | `-15.09%` | `13.27%` | `pullback_reclaim_ema34_144_pb0.005_short_candle_htf0.5__tp2_sl3_tr0_tx72__dir_ret48_bps>=400` |
| `combo_short_rank2` | `2` | `210` | `833.71%` | `-22.38%` | `1.19%` | `64.76%` | `1.771` | `-14.81%` | `21.47%` | `pullback_reclaim_ema34_144_pb0_short_nocandle_htfnone__tp1.5_sl2_tr0_tx48__dir_ret48_bps>=400` |
| `combo_short_rank9` | `9` | `211` | `776.02%` | `-22.38%` | `1.14%` | `64.45%` | `1.747` | `-14.81%` | `9.23%` | `pullback_reclaim_ema34_144_pb0_short_nocandle_htfnone__tp1.5_sl2_tr0_tx36__dir_ret48_bps>=400` |
| `combo_short_rank12` | `12` | `212` | `766.46%` | `-22.38%` | `1.13%` | `64.15%` | `1.736` | `-14.81%` | `10.01%` | `pullback_reclaim_ema34_144_pb0_short_nocandle_htfnone__tp1.5_sl2_tr0_tx24__dir_ret48_bps>=400` |
| `combo_short_rank11` | `11` | `210` | `760.09%` | `-22.38%` | `1.14%` | `64.76%` | `1.741` | `-14.81%` | `11.90%` | `pullback_reclaim_ema34_144_pb0_short_nocandle_htfnone__tp1.5_sl2_tr0_tx72__dir_ret48_bps>=400` |
| `combo_short_rank10` | `10` | `212` | `738.22%` | `-26.04%` | `1.11%` | `62.74%` | `1.748` | `-14.81%` | `10.16%` | `pullback_reclaim_ema34_144_pb0_short_nocandle_htfnone__tp1.5_sl2_tr0_tx12__dir_ret48_bps>=400` |
| `V6.1_long_only` | `-1` | `157` | `408.95%` | `-25.63%` | `1.15%` | `63.69%` | `1.773` | `-14.81%` | `9.23%` | `` |

## Slice And Side Check

| combo | slice | trades | total | DD | PF | avg |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `V6.1_long_only` | `IS` | `99` | `197.52%` | `-25.63%` | `1.794` | `1.23%` |
| `V6.1_long_only` | `VAL` | `48` | `66.86%` | `-21.23%` | `1.846` | `1.16%` |
| `V6.1_long_only` | `OOS` | `10` | `2.52%` | `-5.76%` | `1.215` | `0.31%` |
| `combo_short_rank1` | `IS` | `147` | `444.29%` | `-28.69%` | `1.770` | `1.31%` |
| `combo_short_rank1` | `VAL` | `49` | `72.08%` | `-21.23%` | `1.893` | `1.20%` |
| `combo_short_rank1` | `OOS` | `16` | `14.62%` | `-8.28%` | `1.559` | `0.98%` |
| `combo_short_rank2` | `IS` | `144` | `404.46%` | `-22.38%` | `1.788` | `1.26%` |
| `combo_short_rank2` | `VAL` | `51` | `69.14%` | `-21.23%` | `1.826` | `1.12%` |
| `combo_short_rank2` | `OOS` | `15` | `9.43%` | `-11.06%` | `1.439` | `0.69%` |

| combo | side | trades | total | DD | PF | avg |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `combo_short_rank1` | `long` | `157` | `408.95%` | `-25.63%` | `1.773` | `1.15%` |
| `combo_short_rank1` | `short` | `55` | `110.94%` | `-23.60%` | `1.783` | `1.56%` |
| `combo_short_rank2` | `long` | `157` | `408.95%` | `-25.63%` | `1.773` | `1.15%` |
| `combo_short_rank2` | `short` | `53` | `83.46%` | `-13.38%` | `1.764` | `1.29%` |

## 结论

V6.1 long-only 基线为总收益 `408.95%`、最大回撤 `-25.63%`。本轮收益最高组合是 `combo_short_rank1`，总收益 `973.56%`、最大回撤 `-28.69%`；风险收益更均衡的是 `combo_short_rank2`，总收益 `833.71%`、最大回撤 `-22.38%`。

本报告生成时先把它列为观察线索，原因是 short-only 侧的核心过滤几乎都收敛到 `dir_ret48_bps>=400`，说明 edge 很可能来自少数快速下跌片段；top 组合的 short-only VAL/OOS 样本只有 `1~6` 笔。更宽样本的两个 short 候选虽然通过 `VAL>=5/OOS>=10`，但组合回撤分别达到 `-50.20%` 和 `-33.82%`，不适合替代 top2。后续已按用户要求对 `combo_short_rank2` 做全参数消融，并在 `ablations/hype-5m-pbtr-v6-2-full-parameter-ablation-2026-06-28.md` 中正式记录为 `HYPE-5M-PBTR-V6.2` paper/live-dry-run 候选。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_1_short_combo_search.py`
- short summary CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_short_search_summary_2026-06-27.csv`
- combo summary CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_short_combo_summary_2026-06-27.csv`
- combo trades CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_short_combo_trades_2026-06-27.csv`
- extended combo summary CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_short_combo_extended_summary_2026-06-27.csv`
- combo side breakdown CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_short_combo_side_breakdown_2026-06-27.csv`
- combo slice breakdown CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_short_combo_slice_breakdown_2026-06-27.csv`
- extended combo trades CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_short_combo_extended_trades_2026-06-27.csv`
- JSON：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_short_combo_search_2026-06-27.json`
