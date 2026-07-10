# SOL-1H-Adaptive-Regime-V2 VWAP Arm-Confirm-Expire 状态机诊断 - 2026-07-10

## 结论

本轮把 VWAP 从偏离回穿即入场改成 `arm → confirm → expire`：arm 事件满足原 V2 慢周期过滤，随后等待快速动量重新与交易方向一致；confirm 使用闭合 K，下一根 open 入场。

- Donchian candidates：`18`；VWAP state-machine candidates：`35`；ensemble candidates：`582`。
- prefit-only 选中：`ENS__DON_SM_L3_TP1_SL4_H72__VWAP_SM_W3_roc6_macd_L1_TP1.5_SL1.5_H12`。
- VWAP mechanism：`vwap_arm_confirm_expire:roc6_macd:W3`；events `94`，confirmed `58`。

## 选中观察

- prefit：annual `2.3129x`，DD `-19.05%`，win `79.57%`，trades `93`。
- reused holdout：annual `1.1089x`，return `2.61%`，DD `-4.55%`，win `66.67%`，trades `3`。
- full：annual `2.0977x`，DD `-19.05%`，win `79.17%`，trades `96`。

## 标准近期分片（锚定数据集末端，仅审计）

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `last_1d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `last_7d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `last_1m` | `1.3683x` | `2.61%` | `-4.55%` | `66.67%` | `3` | `2.223` |
| `last_3m` | `1.1089x` | `2.61%` | `-4.55%` | `66.67%` | `3` | `2.223` |
| `last_6m` | `1.1498x` | `7.20%` | `-17.29%` | `75.00%` | `16` | `1.433` |
| `last_1y` | `1.7439x` | `74.33%` | `-17.89%` | `79.07%` | `43` | `2.976` |

## 研究边界

- state machine 在线可表达：arm/confirm 都只使用已闭合 K，订单在下一根 open 执行。
- reused holdout 已揭盲，不用于选择 confirm window 或 mode。
- 即使 reused holdout 改善，也只能冻结为 observation 并等待 fresh forward。

## 机器证据

- `artifacts/sol_1h_ar_v2_vwap_state_machine_2026-07-10.json`
- `artifacts/sol_1h_ar_v2_vwap_state_machine_candidates_2026-07-10.csv`
- `artifacts/sol_1h_ar_v2_vwap_state_machine_selected_trades_2026-07-10.csv`

复现：

```bash
uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_v2_vwap_state_machine.py
```
