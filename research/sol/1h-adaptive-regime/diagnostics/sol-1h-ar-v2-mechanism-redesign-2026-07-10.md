# SOL-1H-Adaptive-Regime-V2 机制改造诊断 - 2026-07-10

## 结论

本实验把 V2 的问题视为收益结构与 regime 失效，而不是继续做原参数邻域微调。所有候选只使用 train/validation/prefit 排序；最近三个月已在 V1 阶段揭盲，本次只作 reused-holdout 审计。

- Donchian 机制变体通过 prefit 基础门槛：`139`。
- VWAP 机制变体通过 prefit 基础门槛：`1443`。
- 组合后通过基础门槛：`2474`；冻结审计集：`100`。
- prefit-only 选中观察：`ENS__DON_FIXED_both_L3_TP1_SL4_H72__VWAP_FIXED_short_none_L1.5_TP1.5_SL2_H18`。

## V2 收益结构诊断

- V2 full 区间最大单笔亏损 `-14.36%`，平均盈利 `1.75%`，平均亏损 `-6.89%`，payoff `0.253`。
- V2 full 区间 stop exits `5`，timeout exits `3`；高胜率由小 TP 累积，少数 stop 构成主要尾部风险。
- 最近三个月两笔亏损均来自 VWAP short；Donchian 腿为 `2/2` 盈利。两笔 VWAP short 在信号时均出现 `roc6 > 0`、短 MACD histogram > 0、`PDI > MDI`，说明慢速 `h12` 空头 regime 尚未翻转时，快速反弹已经发生。

## 基线与选中观察

| Strategy | Prefit ann | Prefit DD | Prefit win | Reused holdout ann | Holdout DD | Holdout win | Full ann | Full DD | Full win | Full trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V2 baseline` | `2.4392x` | `-17.41%` | `95.41%` | `0.6992x` | `-15.69%` | `66.67%` | `2.0662x` | `-17.41%` | `93.91%` | `115` |
| `prefit-only selected` | `3.7789x` | `-17.41%` | `88.46%` | `0.7568x` | `-10.04%` | `50.00%` | `3.0520x` | `-17.41%` | `86.36%` | `110` |

## 选中机制

- strategy mechanism：`ensemble:donchian_fixed_payoff+vwap_tail_compression`。
- Donchian：`DON_FIXED_both_L3_TP1_SL4_H72`。
- VWAP：`VWAP_FIXED_short_none_L1.5_TP1.5_SL2_H18`；gate `none`。
- full 最大单笔亏损 `-14.36%`，平均盈利 `3.07%`，平均亏损 `-4.98%`，payoff `0.616`。

## 标准近期分片（锚定数据集末端，仅审计）

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `last_1d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `last_7d` | `0.0234x` | `-6.95%` | `-10.04%` | `33.33%` | `3` | `0.271` |
| `last_1m` | `0.4294x` | `-6.71%` | `-10.04%` | `50.00%` | `6` | `0.532` |
| `last_3m` | `0.7568x` | `-6.71%` | `-10.04%` | `50.00%` | `6` | `0.532` |
| `last_6m` | `1.5402x` | `24.01%` | `-17.29%` | `81.82%` | `22` | `1.840` |
| `last_1y` | `2.1992x` | `119.80%` | `-17.41%` | `84.31%` | `51` | `2.843` |

## 研究边界

- reused holdout 已被用于提出快速反转 veto 假设，因此本实验不能产生 promotion 或新版本。
- 只有 prefit-only 选择在新增 fresh forward trades 上继续成立，并通过延迟、成本、订单状态机和恢复审计，才允许进入下一阶段。
- 本报告不把 reused-holdout 表现最好的候选倒选为结果。

## 机器证据

- `artifacts/sol_1h_ar_v2_mechanism_redesign_2026-07-10.json`
- `artifacts/sol_1h_ar_v2_mechanism_redesign_candidates_2026-07-10.csv`
- `artifacts/sol_1h_ar_v2_mechanism_redesign_selected_trades_2026-07-10.csv`

复现：

```bash
uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_v2_mechanism_redesign.py
```
