# HYPE-1H-Adaptive-Regime-V2 消融引导组合复测 - 2026-07-06

## 结论

本轮只复测 V2 全参数消融提示的少量组合：DI `4` 个候选 × Stoch `4` 个候选，共 `16` 个组合；每个组合跑 base K+1、K+2 延迟和 8 bps/fill 滑点。

base K+1 target gate 通过 `0/16`；K+2 与 8bps 同时通过 `0/16`。

最佳 base 排名组合 `di_roc_off__stoch_th55`：current full `15.0530x`、DD `-19.11%`、胜率 `79.73%`；reused holdout `9.0300x`、DD `-19.11%`。

结论：如果只看 base K+1，`di_roc_off + stoch_th55` / `di_roc12_off + stoch_th55` 方向显著优于 V2 baseline；但 reused holdout 年化仍低于 `10x`，K+2 延迟或 8bps 滑点下也无法形成完整稳健通过，因此本轮仍不登记 `V2.1/V3`。

## 数据与口径

- 数据：Binance HYPEUSDT perpetual `1h` closed-only，`2025-05-30T10:00:00+00:00` 到 `2026-07-02T02:00:00+00:00`，rows `9545`。
- 当前评估终点：`2026-07-02T03:00:00+00:00`。
- 成本：base 为 `0.001` fee/fill + `4 bps` slippage/fill；压力为 K+2 延迟和 `8 bps` slippage/fill。
- 资金费：逐笔计入 Binance 历史 funding。
- Reused holdout 已解锁，只能用于诊断，不能重新包装为 untouched OOS。

## 组合排名

| Combo | Base annual | Base DD | Base win | Holdout annual | Holdout DD | K+2 full/DD | 8bps full/DD | Gates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `di_roc_off__stoch_th55` | 15.0530x | -19.11% | 79.73% | 9.0300x | -19.11% | 3.0574x / -31.93% | 9.4070x / -28.40% | - |
| `di_roc12_off__stoch_th55` | 15.0530x | -19.11% | 79.73% | 9.0300x | -19.11% | 3.0574x / -31.93% | 9.4070x / -28.40% | - |
| `di_roc12__stoch_th55` | 14.2081x | -19.11% | 80.56% | 9.0300x | -19.11% | 3.2505x / -31.93% | 8.9123x / -28.40% | - |
| `di_roc_off__stoch_th55_trail05` | 14.0590x | -17.94% | 82.67% | 8.3984x | -17.94% | 3.4933x / -31.28% | 8.5106x / -28.10% | - |
| `di_roc12_off__stoch_th55_trail05` | 14.0590x | -17.94% | 82.67% | 8.3984x | -17.94% | 3.4933x / -31.28% | 8.5106x / -28.10% | - |
| `di_roc12__stoch_th55_trail05` | 13.2699x | -17.94% | 83.56% | 8.3984x | -17.94% | 3.7140x / -31.28% | 8.0631x / -27.25% | - |
| `di_roc_off__stoch_trail05` | 12.9910x | -17.94% | 82.43% | 7.7879x | -17.94% | 3.2470x / -31.95% | 7.8754x / -28.10% | - |
| `di_roc12_off__stoch_trail05` | 12.9910x | -17.94% | 82.43% | 7.7879x | -17.94% | 3.2470x / -31.95% | 7.8754x / -28.10% | - |
| `di_roc_off__stoch_base` | 12.9357x | -19.11% | 79.45% | 7.0433x | -19.11% | 2.7648x / -32.21% | 8.0935x / -28.40% | - |
| `di_roc12_off__stoch_base` | 12.9357x | -19.11% | 79.45% | 7.0433x | -19.11% | 2.7648x / -32.21% | 8.0935x / -28.40% | - |
| `di_roc12__stoch_trail05` | 12.2619x | -17.94% | 83.33% | 7.7879x | -17.94% | 3.4521x / -31.95% | 7.4613x / -27.25% | - |
| `di_roc12__stoch_base` | 12.2096x | -19.11% | 80.28% | 7.0433x | -19.11% | 2.9395x / -32.21% | 7.6678x / -28.40% | - |
| `di_base__stoch_th55` | 11.2688x | -19.64% | 78.57% | 6.5776x | -19.64% | 2.4829x / -36.51% | 7.0740x / -33.12% | - |
| `di_base__stoch_th55_trail05` | 10.5247x | -17.94% | 81.69% | 6.1175x | -17.94% | 2.8370x / -35.91% | 6.4000x / -32.05% | - |
| `di_base__stoch_trail05` | 9.7252x | -17.94% | 81.43% | 5.6729x | -17.94% | 2.6369x / -36.53% | 5.9223x / -32.05% | - |
| `di_base__stoch_base` | 9.6838x | -19.64% | 78.26% | 5.1305x | -19.64% | 2.2453x / -36.77% | 6.0863x / -33.12% | - |

## Baseline 对照

`di_base__stoch_base`：current full `9.6838x`、DD `-19.64%`、胜率 `78.26%`；reused holdout `5.1305x`。

## 最近窗口提示

| Window | Trades | Win | Return | DD | Annual |
| --- | ---: | ---: | ---: | ---: | ---: |
| `last_7d` | `1` | `100.00%` | `3.91%` | `-0.56%` | `7.3908x` |
| `last_30d` | `8` | `87.50%` | `43.70%` | `-16.37%` | `82.6096x` |
| `last_90d` | `18` | `72.22%` | `60.83%` | `-19.11%` | `6.8789x` |
| `last_180d` | `36` | `72.22%` | `200.15%` | `-19.11%` | `9.3027x` |
| `last_365d` | `74` | `79.73%` | `1271.47%` | `-19.11%` | `15.0530x` |

## 机器证据

- JSON：`artifacts/hype_1h_ar_v2_ablation_combo_retest_2026-07-06.json`
- 组合 CSV：`artifacts/hype_1h_ar_v2_ablation_combo_retest_rows_2026-07-06.csv`
- 最近窗口 CSV：`artifacts/hype_1h_ar_v2_ablation_combo_retest_windows_2026-07-06.csv`

复现：

```bash
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v2_ablation_combo_retest.py
```
