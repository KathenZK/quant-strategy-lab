# HYPE-5M-Micro-Scalp-V1.3 ATR 动态杠杆回测 2026-07-01

Family id：`HYPE-5M-Micro-Scalp`

在 V1.3 信号、固定 `tp_bps=110` / `sl_bps=400` 不变的前提下，只改变账户杠杆层。

## 动态杠杆规则

- `ATR14%` 取信号 K 的 `atr_pct_bps`（bps）。
- `atr_pct_bps <= 35.0` → `3.0x`；`atr_pct_bps >= 90.5` → `1.0x`；中间线性插值。
- 高波动降杠杆、低波动升杠杆；clip `[1.0x, 3.0x]`。
- `max_atr_pct_bps` 锚点取 V1.3 成交信号 ATR 的 P90 = `90.5 bps`。
- 信号 ATR 分布：中位 `54.7` bps，P25 `46.0`，P75 `68.4` bps。
- 成本：fee `0.001`/fill，slippage `4.0 bps`/fill；杠杆放大 `net_ret_1x` 与路径内 `mae_1x`，不模拟 maintenance margin / 强平。

- 数据：`2025-05-30 10:30:00+00:00` → `2026-06-30 06:15:00+00:00`，`113998` 根 K。

## 全样本对比

| variant | trades | avg lev | ann | 总收益 | maxDD | PF | win | avg trade | worst | VAL PF | FWD PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `fixed_3x` | `180` | `3.000x` | `4.89x` | `458.10%` | `-29.67%` | `1.934` | `85.00%` | `104.89 bps` | `-12.74%` | `5.081` | `10.245` |
| `atr_dynamic_2x_3x` | `180` | `2.575x` | `3.80x` | `324.60%` | `-26.34%` | `1.891` | `85.00%` | `87.28 bps` | `-12.00%` | `6.150` | `9.361` |
| `fixed_2x` | `180` | `2.000x` | `2.98x` | `227.11%` | `-19.90%` | `1.934` | `85.00%` | `69.93 bps` | `-8.49%` | `5.081` | `10.245` |
| `atr_dynamic_1x_3x` | `180` | `2.149x` | `2.92x` | `219.74%` | `-23.49%` | `1.834` | `85.00%` | `69.66 bps` | `-11.30%` | `8.410` | `8.338` |
| `fixed_1x` | `180` | `1.000x` | `1.76x` | `84.28%` | `-9.96%` | `1.934` | `85.00%` | `34.96 bps` | `-4.25%` | `5.081` | `10.245` |

## 结论

- V1.3 固定 `1x` 基线：ann `1.76x`，maxDD `-9.96%`。
- ATR 动态 `1x-3x`：平均杠杆 `2.149x`，ann `2.92x`，maxDD `-23.49%`。
- 相对固定 `3x`：动态杠杆通常降低回撤，但也降低收益；本实验仅为杠杆层诊断，不构成 live-ready 或实盘仓位建议。

## 产物

- 脚本：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_3_atr_dynamic_leverage.py`
- Summary CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_3_atr_dynamic_leverage_summary_2026-07-01.csv`
- JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_3_atr_dynamic_leverage_2026-07-01.json`
