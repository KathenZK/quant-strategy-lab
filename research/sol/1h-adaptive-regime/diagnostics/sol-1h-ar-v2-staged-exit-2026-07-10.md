# SOL-1H-Adaptive-Regime-V2 分段止盈与失效退出诊断 - 2026-07-10

## 结论

本轮验证第一目标部分止盈、剩余仓位延伸目标、次 K 生效保本 stop，以及持仓后快速动量失效次根 open 退出。所有选择只使用 train/validation/prefit；reused holdout 不参与排序。

- Donchian staged variants 通过门槛：`346`。
- VWAP staged variants 通过门槛：`628`。
- 组合后通过门槛：`1669`；冻结审计集：`100`。
- prefit-only 选中观察：`ENS__DON_STAGE_S11_F0.67_T4_SL4_H120_L3_BE1__VWAP_STAGE_S11_F0.5_T2_SL3_H18_L1.5_BE0_none`。

## 对照

| Strategy | Prefit ann | Prefit DD | Prefit win | Reused holdout ann | Holdout DD | Holdout win | Full ann | Full DD | Full win | Full trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `first redesign` | `3.7789x` | `-17.41%` | `88.46%` | `0.7568x` | `-10.04%` | `50.00%` | `3.0520x` | `-17.41%` | `86.36%` | `110` |
| `staged-exit selected` | `3.1860x` | `-17.41%` | `90.00%` | `0.7284x` | `-15.69%` | `60.00%` | `2.6188x` | `-17.41%` | `88.42%` | `95` |

## 选中机制

- mechanism：`ensemble:staged_partial_take+next_bar_breakeven+staged_partial_take`。
- Donchian policy：`DON_STAGE_S11_F0.67_T4_SL4_H120_L3_BE1`。
- VWAP policy：`VWAP_STAGE_S11_F0.5_T2_SL3_H18_L1.5_BE0_none`。
- full 最大单笔亏损 `-9.17%`，平均盈利 `2.78%`，平均亏损 `-4.31%`，payoff `0.644`。

## 标准近期分片（锚定数据集末端，仅审计）

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `last_1d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `last_7d` | `0.0020x` | `-11.19%` | `-15.69%` | `33.33%` | `3` | `0.186` |
| `last_1m` | `0.3824x` | `-7.59%` | `-15.69%` | `60.00%` | `5` | `0.474` |
| `last_3m` | `0.7284x` | `-7.59%` | `-15.69%` | `60.00%` | `5` | `0.474` |
| `last_6m` | `1.5824x` | `25.69%` | `-15.69%` | `88.89%` | `18` | `2.723` |
| `last_1y` | `1.9207x` | `91.98%` | `-17.41%` | `86.36%` | `44` | `3.689` |

## 执行假设

- 每个 exit tranche 单独计 fee、slippage 和 funding。
- 同 K stop 与任一 target 同时触发时，对剩余仓位按 stop-first。
- 第一目标命中后，保本 stop 从下一根 K 才生效，不使用同 K 内不可知顺序。
- failure exit 只在完整 K 闭合确认，下一根 open 市价退出。
- partial exit 后 MAE 仍按完整 exposure 计入，属于保守回撤估计。

## 研究边界

- 本轮沿用已揭盲 reused holdout，只能形成 diagnostic observation，不能登记版本或 promotion。
- 若结构改善，应冻结参数并等待新增 fresh forward trades；不得继续用 reused holdout 倒选 policy。

## 机器证据

- `artifacts/sol_1h_ar_v2_staged_exit_2026-07-10.json`
- `artifacts/sol_1h_ar_v2_staged_exit_candidates_2026-07-10.csv`
- `artifacts/sol_1h_ar_v2_staged_exit_selected_trades_2026-07-10.csv`

复现：

```bash
uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_v2_staged_exit.py
```
