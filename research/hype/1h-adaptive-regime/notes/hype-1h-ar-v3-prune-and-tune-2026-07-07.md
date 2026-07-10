# HYPE-1H-Adaptive-Regime-V3 参数剪枝与预拟合微调 - 2026-07-07

> **Superseded 指标警告（2026-07-10）**：本报告采用“先独立模拟两腿、再合并”的近似 ensemble 回放。精确单账户联合状态机发现该方法会让被挡掉的虚拟交易错误触发单腿持仓/cooldown，并压掉后续信号。V4 精确 current full 已修正为 `20.9748x / -19.11% / 80.00% / 75 trades`，reused holdout 为 `9.0210x`；详见 `diagnostics/hype-1h-ar-v4-execution-pressure-optimization-2026-07-10.md`。本报告其余数字只保留为历史搜索证据，不再作为 live runner 事实源。

## 结论

V3 的 `34` 个字段槽中有 `9` 个在当前数据上 dormant：DI 腿 `ema_htf`、`max_adx`、`roc_window`、`min_dir_roc_bps`、`max_dist_ema_bps`、`max_aligned_funding_bps`；Stoch 腿 `ema_htf`、`max_dist_ema_bps`、`sl_atr`。全部移除后逐笔交易路径与 V3 exact equal（DI、Stoch、merged 三层签名一致），剪枝后剩 `25` 个字段槽（DI `9` + Stoch `16`）。

微调只用 prefit 选参：DI 网格 `972`、Stoch 网格 `6144`，单腿 prefit 达标后取 top `12` 组合成 `169` 个 ensemble，前 `17` 名再跑 K+1/K+2/8bps 三场景 prefit 稳健排名，冻结前 `5` 名后才揭示 reused holdout 与 current full。

## V3 基线（对照）

| Window | Annual | DD | Win | Trades |
| --- | ---: | ---: | ---: | ---: |
| Prefit | `17.4864x` | `-16.93%` | `80.70%` | `57` |
| Reused holdout | `9.0300x` | `-19.11%` | `76.47%` | `17` |
| Current full | `15.0530x` | `-19.11%` | `79.73%` | `74` |

## 冻结揭示组合

| Combo | Robust prefit min annual | Base full annual | Base full DD | Base full win | Holdout annual | Holdout DD | K+2 full/DD | 8bps full/DD | 超越 V3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `di_cross_00178__stoch_reversal_04786` | 16.3191x | 20.9796x | -19.11% | 80.82% | 9.0300x | -19.11% | 8.0071x / -27.63% | 14.1499x / -28.40% | yes |
| `di_cross_00178__stoch_reversal_05554` | 16.3191x | 20.9796x | -19.11% | 80.82% | 9.0300x | -19.11% | 8.0071x / -27.63% | 14.1499x / -28.40% | yes |
| `di_cross_00205__stoch_reversal_04786` | 16.3191x | 22.8128x | -19.11% | 81.08% | 13.0662x | -19.11% | 8.7014x / -23.56% | 15.3677x / -22.46% | yes |
| `di_cross_00205__stoch_reversal_05554` | 16.3191x | 22.8128x | -19.11% | 81.08% | 13.0662x | -19.11% | 8.7014x / -23.56% | 15.3677x / -22.46% | yes |
| `di_cross_00172__stoch_reversal_04783` | 15.1605x | 20.6777x | -16.93% | 78.08% | 10.1462x | -13.05% | 6.6828x / -30.95% | 12.2145x / -33.51% | no |

## 剪枝证据

- DI/Stoch/merged 三层签名等价：`{'di_path_equal': True, 'stoch_path_equal': True, 'merged_path_equal': True}`。
- DI 移除：`ema_htf`、`max_adx`、`roc_window`、`min_dir_roc_bps`、`max_dist_ema_bps`、`max_aligned_funding_bps`。
- Stoch 移除：`ema_htf`、`max_dist_ema_bps`；`sl_atr` 固化为 `4.0` 安全兜底（3-6 ATR 变体全 path-equal，从未触发）。

## 方法与防过拟合边界

- 选参只使用 prefit（训练段），并要求 K+1、K+2、8bps 三场景 prefit 同时 DD 不破 `20%`、胜率 `>=50%`。
- Reused holdout 只在冻结排名后揭示，仅作诊断，不参与选参；它不是 untouched OOS。
- 本轮不改变 promotion 状态；任何登记需另行完成 live-executable 审计。

## 机器证据

- JSON：`artifacts/hype_1h_ar_v3_prune_and_tune_2026-07-07.json`
- 单腿 CSV：`artifacts/hype_1h_ar_v3_prune_and_tune_legs_2026-07-07.csv`
- 组合 CSV：`artifacts/hype_1h_ar_v3_prune_and_tune_combos_2026-07-07.csv`

复现：

```bash
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v3_prune_and_tune.py
```
