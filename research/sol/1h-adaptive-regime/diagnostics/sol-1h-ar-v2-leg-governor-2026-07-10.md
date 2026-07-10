# SOL-1H-Adaptive-Regime-V2 腿级风险治理诊断 - 2026-07-10

## 结论

本轮测试把 VWAP 作为可暂停的 satellite leg：每笔交易完成后，若发生 stop 或任意亏损，则按预设 bars 暂停新 VWAP 入场；Donchian core 不受影响。选择只使用 train/validation/prefit。

- Donchian candidates：`18`；VWAP governor candidates：`370`；ensemble candidates：`6648`。
- prefit-only 选中：`ENS__DON_GOV_L3_TP1_SL4_H72__VWAP_GOV_L1.5_TP1.5_SL2_H18_CD0_none`。
- 选中 governor：trigger `none`，cooldown `0` bars。

## 选中观察

- prefit：annual `3.7789x`，DD `-17.41%`，win `88.46%`，trades `104`。
- reused holdout：annual `0.7568x`，return `-6.71%`，DD `-10.04%`，win `50.00%`，trades `6`。
- full：annual `3.0520x`，DD `-17.41%`，win `86.36%`，trades `110`。

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

- governor 只使用已完成交易结果，在线可表达；没有使用未来信息。
- reused holdout 已揭盲，不能用于选择 cooldown 或登记新版本。
- 若 prefit-only 选中的 governor 没有改善 reused holdout，只能说明该治理机制不足；不得倒选 holdout 最优 cooldown。

## 机器证据

- `artifacts/sol_1h_ar_v2_leg_governor_2026-07-10.json`
- `artifacts/sol_1h_ar_v2_leg_governor_candidates_2026-07-10.csv`
- `artifacts/sol_1h_ar_v2_leg_governor_selected_trades_2026-07-10.csv`

复现：

```bash
uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_v2_leg_governor.py
```
