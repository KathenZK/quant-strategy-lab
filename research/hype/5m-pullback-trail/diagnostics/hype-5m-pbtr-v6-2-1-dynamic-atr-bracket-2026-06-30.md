# HYPE-5M-PBTR-V6.2.1 动态 ATR TP/SL 回测 2026-06-30

Family id：`HYPE-5M-PBTR`

用户问题：V6.2.1 是否是固定止盈止损；如果改成根据 ATR 波动率动态调整 TP/SL 会怎样。

回答：V6.2.1 当前是入场即固定 bracket。TP/SL 距离用信号 K 的 ATR14 算出后，在持仓期间不再随 ATR 改变。本报告测试四种 live-executable 动态 ATR bracket：每根 K 先用当时已挂的 bracket 判断是否成交，若没有成交，才在该 K 收盘后用已收盘 ATR 更新下一根 K 可用的 TP/SL。

## 动态定义

- `entry_anchor_dynamic_atr`：TP/SL 始终锚定入场价，但距离使用最新已收盘 ATR，可放宽止损。
- `entry_anchor_no_widen_stop`：TP 锚定入场价并随 ATR 变；SL 锚定入场价但只能变紧，不能放宽。
- `close_reset_dynamic_atr`：每根收盘后围绕该根 close 用最新 ATR 重设下一根的 TP/SL，可放宽止损。
- `close_reset_no_widen_stop`：TP 围绕 close 重设，SL 只允许向有利方向移动。

表格中的 `stop widen` 表示实际发生过止损放宽的交易数；`no_widen_stop` 模式应为 `0`。

每种模式扫描 `TP scale = 0.75/1.0/1.25/1.5`、`SL scale = 0.75/1.0/1.25`。scale 作用于 V6.2.1 原始参数：long `TP2.5/SL7`，short `TP1.5/SL2`。

## Baseline

| label | trades | total | PF | avg | win | DD | reasons |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `baseline_fixed_entry_atr` | `220` | `1054.07%` | `1.813` | `1.23%` | `64.55%` | `-22.35%` | `{"stop_market": 19, "target": 129, "time_open": 72}` |

## 同参数动态对照

| 变体 | mode | TP scale | SL scale | trades | total | PF | avg | win | DD | OOS PF | short PF | amend | stop widen | pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `close_reset_dynamic_atr__tp1p0__sl1p0` | `close_reset_dynamic_atr` | `1.00` | `1.00` | `173` | `304.06%` | `1.511` | `1.00%` | `53.18%` | `-42.33%` | `1.992` | `1.054` | `36.0` | `169` | `False` |
| `close_reset_no_widen_stop__tp1p0__sl1p0` | `close_reset_no_widen_stop` | `1.00` | `1.00` | `174` | `409.43%` | `1.610` | `1.12%` | `52.30%` | `-33.11%` | `2.430` | `1.347` | `36.0` | `0` | `True` |
| `entry_anchor_dynamic_atr__tp1p0__sl1p0` | `entry_anchor_dynamic_atr` | `1.00` | `1.00` | `223` | `843.34%` | `1.729` | `1.12%` | `65.47%` | `-25.98%` | `2.296` | `1.667` | `13.0` | `209` | `True` |
| `entry_anchor_no_widen_stop__tp1p0__sl1p0` | `entry_anchor_no_widen_stop` | `1.00` | `1.00` | `224` | `776.28%` | `1.692` | `1.08%` | `64.73%` | `-25.19%` | `2.296` | `1.540` | `12.5` | `0` | `True` |

## Top By Total Return

| 变体 | mode | TP scale | SL scale | trades | total | PF | avg | win | DD | OOS PF | short PF | amend | stop widen | pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `entry_anchor_dynamic_atr__tp1p5__sl1p0` | `entry_anchor_dynamic_atr` | `1.50` | `1.00` | `190` | `1124.81%` | `1.870` | `1.47%` | `58.42%` | `-29.89%` | `1.486` | `1.480` | `22.0` | `186` | `True` |
| `entry_anchor_dynamic_atr__tp1p5__sl1p25` | `entry_anchor_dynamic_atr` | `1.50` | `1.25` | `190` | `1036.68%` | `1.819` | `1.43%` | `59.47%` | `-25.48%` | `1.338` | `1.394` | `25.0` | `187` | `True` |
| `entry_anchor_dynamic_atr__tp1p25__sl1p25` | `entry_anchor_dynamic_atr` | `1.25` | `1.25` | `201` | `1002.66%` | `1.799` | `1.33%` | `62.69%` | `-22.99%` | `1.242` | `1.522` | `18.0` | `195` | `True` |
| `entry_anchor_no_widen_stop__tp1p5__sl1p25` | `entry_anchor_no_widen_stop` | `1.50` | `1.25` | `190` | `977.70%` | `1.798` | `1.40%` | `58.95%` | `-33.01%` | `1.355` | `1.289` | `25.0` | `0` | `True` |
| `entry_anchor_no_widen_stop__tp1p25__sl1p25` | `entry_anchor_no_widen_stop` | `1.25` | `1.25` | `201` | `953.09%` | `1.781` | `1.30%` | `62.19%` | `-30.27%` | `1.258` | `1.412` | `18.0` | `0` | `True` |
| `entry_anchor_dynamic_atr__tp1p25__sl1p0` | `entry_anchor_dynamic_atr` | `1.25` | `1.00` | `202` | `924.74%` | `1.771` | `1.29%` | `61.39%` | `-27.02%` | `1.379` | `1.622` | `17.5` | `195` | `True` |
| `entry_anchor_no_widen_stop__tp1p5__sl1p0` | `entry_anchor_no_widen_stop` | `1.50` | `1.00` | `191` | `914.25%` | `1.776` | `1.36%` | `57.59%` | `-29.56%` | `1.502` | `1.323` | `21.0` | `0` | `True` |
| `close_reset_dynamic_atr__tp0p75__sl1p25` | `close_reset_dynamic_atr` | `0.75` | `1.25` | `203` | `882.65%` | `1.838` | `1.28%` | `61.08%` | `-20.25%` | `1.635` | `1.708` | `21.0` | `189` | `True` |
| `entry_anchor_no_widen_stop__tp1p0__sl1p25` | `entry_anchor_no_widen_stop` | `1.00` | `1.25` | `222` | `856.68%` | `1.734` | `1.13%` | `66.22%` | `-29.96%` | `2.101` | `1.454` | `14.0` | `0` | `True` |
| `entry_anchor_dynamic_atr__tp1p0__sl1p25` | `entry_anchor_dynamic_atr` | `1.00` | `1.25` | `222` | `849.51%` | `1.730` | `1.13%` | `66.67%` | `-27.56%` | `2.101` | `1.577` | `14.0` | `209` | `True` |
| `entry_anchor_dynamic_atr__tp1p0__sl1p0` | `entry_anchor_dynamic_atr` | `1.00` | `1.00` | `223` | `843.34%` | `1.729` | `1.12%` | `65.47%` | `-25.98%` | `2.296` | `1.667` | `13.0` | `209` | `True` |
| `close_reset_no_widen_stop__tp0p75__sl1p25` | `close_reset_no_widen_stop` | `0.75` | `1.25` | `203` | `800.12%` | `1.800` | `1.23%` | `59.61%` | `-24.44%` | `1.887` | `1.573` | `20.0` | `0` | `True` |
| `entry_anchor_no_widen_stop__tp1p0__sl1p0` | `entry_anchor_no_widen_stop` | `1.00` | `1.00` | `224` | `776.28%` | `1.692` | `1.08%` | `64.73%` | `-25.19%` | `2.296` | `1.540` | `12.5` | `0` | `True` |
| `entry_anchor_no_widen_stop__tp1p25__sl1p0` | `entry_anchor_no_widen_stop` | `1.25` | `1.00` | `203` | `764.05%` | `1.694` | `1.20%` | `60.59%` | `-26.68%` | `1.395` | `1.470` | `17.0` | `0` | `True` |
| `close_reset_dynamic_atr__tp0p75__sl1p0` | `close_reset_dynamic_atr` | `0.75` | `1.00` | `203` | `740.89%` | `1.771` | `1.20%` | `60.10%` | `-23.87%` | `1.630` | `1.468` | `21.0` | `189` | `True` |

## Top By PF

| 变体 | mode | TP scale | SL scale | trades | total | PF | avg | win | DD | OOS PF | short PF | amend | stop widen | pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `entry_anchor_dynamic_atr__tp1p5__sl1p0` | `entry_anchor_dynamic_atr` | `1.50` | `1.00` | `190` | `1124.81%` | `1.870` | `1.47%` | `58.42%` | `-29.89%` | `1.486` | `1.480` | `22.0` | `186` | `True` |
| `close_reset_dynamic_atr__tp0p75__sl1p25` | `close_reset_dynamic_atr` | `0.75` | `1.25` | `203` | `882.65%` | `1.838` | `1.28%` | `61.08%` | `-20.25%` | `1.635` | `1.708` | `21.0` | `189` | `True` |
| `entry_anchor_dynamic_atr__tp1p5__sl1p25` | `entry_anchor_dynamic_atr` | `1.50` | `1.25` | `190` | `1036.68%` | `1.819` | `1.43%` | `59.47%` | `-25.48%` | `1.338` | `1.394` | `25.0` | `187` | `True` |
| `close_reset_no_widen_stop__tp0p75__sl1p25` | `close_reset_no_widen_stop` | `0.75` | `1.25` | `203` | `800.12%` | `1.800` | `1.23%` | `59.61%` | `-24.44%` | `1.887` | `1.573` | `20.0` | `0` | `True` |
| `entry_anchor_dynamic_atr__tp1p25__sl1p25` | `entry_anchor_dynamic_atr` | `1.25` | `1.25` | `201` | `1002.66%` | `1.799` | `1.33%` | `62.69%` | `-22.99%` | `1.242` | `1.522` | `18.0` | `195` | `True` |
| `entry_anchor_no_widen_stop__tp1p5__sl1p25` | `entry_anchor_no_widen_stop` | `1.50` | `1.25` | `190` | `977.70%` | `1.798` | `1.40%` | `58.95%` | `-33.01%` | `1.355` | `1.289` | `25.0` | `0` | `True` |
| `entry_anchor_no_widen_stop__tp1p25__sl1p25` | `entry_anchor_no_widen_stop` | `1.25` | `1.25` | `201` | `953.09%` | `1.781` | `1.30%` | `62.19%` | `-30.27%` | `1.258` | `1.412` | `18.0` | `0` | `True` |
| `entry_anchor_no_widen_stop__tp1p5__sl1p0` | `entry_anchor_no_widen_stop` | `1.50` | `1.00` | `191` | `914.25%` | `1.776` | `1.36%` | `57.59%` | `-29.56%` | `1.502` | `1.323` | `21.0` | `0` | `True` |
| `entry_anchor_dynamic_atr__tp1p25__sl1p0` | `entry_anchor_dynamic_atr` | `1.25` | `1.00` | `202` | `924.74%` | `1.771` | `1.29%` | `61.39%` | `-27.02%` | `1.379` | `1.622` | `17.5` | `195` | `True` |
| `close_reset_dynamic_atr__tp0p75__sl1p0` | `close_reset_dynamic_atr` | `0.75` | `1.00` | `203` | `740.89%` | `1.771` | `1.20%` | `60.10%` | `-23.87%` | `1.630` | `1.468` | `21.0` | `189` | `True` |
| `entry_anchor_no_widen_stop__tp1p0__sl1p25` | `entry_anchor_no_widen_stop` | `1.00` | `1.25` | `222` | `856.68%` | `1.734` | `1.13%` | `66.22%` | `-29.96%` | `2.101` | `1.454` | `14.0` | `0` | `True` |
| `entry_anchor_dynamic_atr__tp1p0__sl1p25` | `entry_anchor_dynamic_atr` | `1.00` | `1.25` | `222` | `849.51%` | `1.730` | `1.13%` | `66.67%` | `-27.56%` | `2.101` | `1.577` | `14.0` | `209` | `True` |
| `entry_anchor_dynamic_atr__tp1p0__sl1p0` | `entry_anchor_dynamic_atr` | `1.00` | `1.00` | `223` | `843.34%` | `1.729` | `1.12%` | `65.47%` | `-25.98%` | `2.296` | `1.667` | `13.0` | `209` | `True` |
| `close_reset_no_widen_stop__tp1p25__sl1p0` | `close_reset_no_widen_stop` | `1.25` | `1.00` | `169` | `510.61%` | `1.702` | `1.27%` | `50.89%` | `-31.69%` | `2.531` | `1.662` | `36.0` | `0` | `True` |
| `entry_anchor_no_widen_stop__tp1p25__sl1p0` | `entry_anchor_no_widen_stop` | `1.25` | `1.00` | `203` | `764.05%` | `1.694` | `1.20%` | `60.59%` | `-26.68%` | `1.395` | `1.470` | `17.0` | `0` | `True` |

## Robust Pass 动态版本

| 变体 | mode | TP scale | SL scale | trades | total | PF | avg | win | DD | OOS PF | short PF | amend | stop widen | pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `entry_anchor_dynamic_atr__tp1p5__sl1p0` | `entry_anchor_dynamic_atr` | `1.50` | `1.00` | `190` | `1124.81%` | `1.870` | `1.47%` | `58.42%` | `-29.89%` | `1.486` | `1.480` | `22.0` | `186` | `True` |
| `entry_anchor_dynamic_atr__tp1p5__sl1p25` | `entry_anchor_dynamic_atr` | `1.50` | `1.25` | `190` | `1036.68%` | `1.819` | `1.43%` | `59.47%` | `-25.48%` | `1.338` | `1.394` | `25.0` | `187` | `True` |
| `entry_anchor_dynamic_atr__tp1p25__sl1p25` | `entry_anchor_dynamic_atr` | `1.25` | `1.25` | `201` | `1002.66%` | `1.799` | `1.33%` | `62.69%` | `-22.99%` | `1.242` | `1.522` | `18.0` | `195` | `True` |
| `entry_anchor_no_widen_stop__tp1p5__sl1p25` | `entry_anchor_no_widen_stop` | `1.50` | `1.25` | `190` | `977.70%` | `1.798` | `1.40%` | `58.95%` | `-33.01%` | `1.355` | `1.289` | `25.0` | `0` | `True` |
| `entry_anchor_no_widen_stop__tp1p25__sl1p25` | `entry_anchor_no_widen_stop` | `1.25` | `1.25` | `201` | `953.09%` | `1.781` | `1.30%` | `62.19%` | `-30.27%` | `1.258` | `1.412` | `18.0` | `0` | `True` |
| `entry_anchor_dynamic_atr__tp1p25__sl1p0` | `entry_anchor_dynamic_atr` | `1.25` | `1.00` | `202` | `924.74%` | `1.771` | `1.29%` | `61.39%` | `-27.02%` | `1.379` | `1.622` | `17.5` | `195` | `True` |
| `entry_anchor_no_widen_stop__tp1p5__sl1p0` | `entry_anchor_no_widen_stop` | `1.50` | `1.00` | `191` | `914.25%` | `1.776` | `1.36%` | `57.59%` | `-29.56%` | `1.502` | `1.323` | `21.0` | `0` | `True` |
| `close_reset_dynamic_atr__tp0p75__sl1p25` | `close_reset_dynamic_atr` | `0.75` | `1.25` | `203` | `882.65%` | `1.838` | `1.28%` | `61.08%` | `-20.25%` | `1.635` | `1.708` | `21.0` | `189` | `True` |
| `entry_anchor_no_widen_stop__tp1p0__sl1p25` | `entry_anchor_no_widen_stop` | `1.00` | `1.25` | `222` | `856.68%` | `1.734` | `1.13%` | `66.22%` | `-29.96%` | `2.101` | `1.454` | `14.0` | `0` | `True` |
| `entry_anchor_dynamic_atr__tp1p0__sl1p25` | `entry_anchor_dynamic_atr` | `1.00` | `1.25` | `222` | `849.51%` | `1.730` | `1.13%` | `66.67%` | `-27.56%` | `2.101` | `1.577` | `14.0` | `209` | `True` |
| `entry_anchor_dynamic_atr__tp1p0__sl1p0` | `entry_anchor_dynamic_atr` | `1.00` | `1.00` | `223` | `843.34%` | `1.729` | `1.12%` | `65.47%` | `-25.98%` | `2.296` | `1.667` | `13.0` | `209` | `True` |
| `close_reset_no_widen_stop__tp0p75__sl1p25` | `close_reset_no_widen_stop` | `0.75` | `1.25` | `203` | `800.12%` | `1.800` | `1.23%` | `59.61%` | `-24.44%` | `1.887` | `1.573` | `20.0` | `0` | `True` |
| `entry_anchor_no_widen_stop__tp1p0__sl1p0` | `entry_anchor_no_widen_stop` | `1.00` | `1.00` | `224` | `776.28%` | `1.692` | `1.08%` | `64.73%` | `-25.19%` | `2.296` | `1.540` | `12.5` | `0` | `True` |
| `entry_anchor_no_widen_stop__tp1p25__sl1p0` | `entry_anchor_no_widen_stop` | `1.25` | `1.00` | `203` | `764.05%` | `1.694` | `1.20%` | `60.59%` | `-26.68%` | `1.395` | `1.470` | `17.0` | `0` | `True` |
| `close_reset_dynamic_atr__tp0p75__sl1p0` | `close_reset_dynamic_atr` | `0.75` | `1.00` | `203` | `740.89%` | `1.771` | `1.20%` | `60.10%` | `-23.87%` | `1.630` | `1.468` | `21.0` | `189` | `True` |
| `close_reset_no_widen_stop__tp0p75__sl1p0` | `close_reset_no_widen_stop` | `0.75` | `1.00` | `205` | `609.75%` | `1.682` | `1.11%` | `58.54%` | `-23.23%` | `2.028` | `1.454` | `20.0` | `0` | `True` |
| `entry_anchor_no_widen_stop__tp0p75__sl1p25` | `entry_anchor_no_widen_stop` | `0.75` | `1.25` | `241` | `516.82%` | `1.612` | `0.85%` | `71.78%` | `-34.21%` | `1.980` | `1.404` | `9.0` | `0` | `True` |
| `entry_anchor_dynamic_atr__tp0p75__sl1p0` | `entry_anchor_dynamic_atr` | `0.75` | `1.00` | `242` | `515.20%` | `1.611` | `0.84%` | `71.49%` | `-30.47%` | `2.148` | `1.672` | `9.0` | `214` | `True` |
| `close_reset_no_widen_stop__tp1p25__sl1p0` | `close_reset_no_widen_stop` | `1.25` | `1.00` | `169` | `510.61%` | `1.702` | `1.27%` | `50.89%` | `-31.69%` | `2.531` | `1.662` | `36.0` | `0` | `True` |
| `entry_anchor_dynamic_atr__tp0p75__sl1p25` | `entry_anchor_dynamic_atr` | `0.75` | `1.25` | `241` | `479.61%` | `1.587` | `0.83%` | `72.20%` | `-29.09%` | `1.980` | `1.528` | `9.0` | `214` | `True` |

## 最佳收益版本月份

最佳收益版本：`entry_anchor_dynamic_atr__tp1p5__sl1p0`。最差月份 `2026-02`：`-6.96%` / PF `0.945`；最好月份 `2026-01`：`189.23%` / PF `5.243`。

## 结论

本轮未找到收益、PF 和回撤同时稳健优于固定 bracket baseline 的动态 ATR 版本。

动态 ATR bracket 没有发现未来函数：订单更新只发生在上一根 K 收盘之后，下一根 K 才使用新 TP/SL。但动态重挂会显著增加真实订单维护复杂度，尤其是允许 stop widening 的模式会把风险边界往外放，实盘上比固定 bracket 更难审计。除非后续有明确优于 baseline 的稳健结果，否则 `HYPE-5M-PBTR-V6.2.1` 默认仍应保留固定入场 ATR bracket。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_2_1_dynamic_atr_bracket.py`
- summary：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-2-1_dynamic_atr_bracket_summary_2026-06-30.csv`
- slices：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-2-1_dynamic_atr_bracket_slices_2026-06-30.csv`
- sides：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-2-1_dynamic_atr_bracket_sides_2026-06-30.csv`
- monthly：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-2-1_dynamic_atr_bracket_monthly_2026-06-30.csv`
- trades：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-2-1_dynamic_atr_bracket_trades_2026-06-30.csv`
- JSON：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-2-1_dynamic_atr_bracket_2026-06-30.json`
