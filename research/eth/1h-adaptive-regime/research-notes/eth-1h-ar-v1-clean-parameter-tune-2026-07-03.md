# ETH-1H-Adaptive-Regime-V1 Clean 参数微调 - 2026-07-03

## 结论

本轮在全参数消融后的 29 个 active clean 参数上做 prefit-only 搜索。冻结候选选择规则为 `prefit_strict_improvement_k2_slip8_all_windows_gate_then_robust_score`；reused holdout 在冻结后才读取，不参与排序。

- 每腿随机样本：`150000`；保留 BB breakout/RSI：`350` / `350`。
- 组合评估：`122500`；可评分：`78921`；prefit 严格改善观察：`227`。
- 完成 K+2 + 8 bps 预拟合稳健审计：`500` 个；其中严格改善候选：`227`。
- 严格改善且 K+2/8 bps 在 train、validation、prefit 全部正收益、胜率 >=50%、DD<20%：`48` 个。

## V1 与冻结微调观察

| Window | V1 annual | V1 DD | V1 win | Tune annual | Tune DD | Tune win | Tune trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.8190x` | `-16.29%` | `72.46%` | `3.9228x` | `-13.90%` | `69.05%` | `42` |
| `validation` | `2.7959x` | `-11.43%` | `69.70%` | `2.9304x` | `-9.44%` | `72.22%` | `18` |
| `prefit` | `2.8109x` | `-16.29%` | `71.57%` | `3.5421x` | `-13.90%` | `70.00%` | `60` |
| `reused_holdout` | `0.5196x` | `-20.87%` | `14.29%` | `0.4378x` | `-20.08%` | `25.00%` | `4` |
| `current_full` | `2.2462x` | `-20.87%` | `67.89%` | `2.6832x` | `-26.23%` | `67.19%` | `64` |

## 冻结参数

### BB breakout clean

- `ema_htf` = `144`
- `indicator_window` = `32`
- `band_k` = `2.0`
- `roc_window` = `6`
- `min_adx` = `28.0`
- `min_rvol` = `2.5`
- `min_atr_bps` = `75.0`
- `min_dir_roc_bps` = `200.0`
- `max_dist_ema_bps` = `2500.0`
- `max_aligned_funding_bps` = `2.0`
- `tp_atr` = `3.0`
- `sl_atr` = `3.5`
- `max_hold_bars` = `36`
- `fixed_leverage` = `2.5`

### RSI clean

- `ema_htf` = `233`
- `indicator_window` = `21`
- `threshold_low` = `20.0`
- `threshold_high` = `60.0`
- `roc_window` = `3`
- `min_adx` = `8.0`
- `max_adx` = `36.0`
- `min_atr_bps` = `100.0`
- `min_dir_roc_bps` = `50.0`
- `max_dist_ema_bps` = `1000.0`
- `tp_atr` = `3.0`
- `sl_atr` = `2.0`
- `max_hold_bars` = `36`
- `cooldown_bars` = `3`
- `fixed_leverage` = `2.0`

## 延迟与成本审计

| Scenario | Prefit annual | Prefit DD | Prefit win | Reused holdout annual | Reused holdout DD | Current full annual | Current full DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `base_k1` | `3.5421x` | `-13.90%` | `70.00%` | `0.4378x` | `-20.08%` | `2.6832x` | `-26.23%` |
| `delay_k2` | `2.6914x` | `-17.86%` | `66.13%` | `0.5845x` | `-13.07%` | `2.1972x` | `-24.55%` |
| `delay_k3` | `2.5525x` | `-24.84%` | `65.57%` | `0.3528x` | `-23.92%` | `1.9625x` | `-33.83%` |
| `slip_8bps` | `3.2426x` | `-17.37%` | `70.00%` | `0.4310x` | `-20.40%` | `2.4801x` | `-26.80%` |
| `slip_12bps` | `3.1248x` | `-18.18%` | `70.00%` | `0.4242x` | `-20.72%` | `2.3967x` | `-27.36%` |
| `fee12_slip8` | `3.1436x` | `-17.98%` | `70.00%` | `0.4241x` | `-20.72%` | `2.4091x` | `-27.29%` |
| `double_cost` | `2.7762x` | `-20.37%` | `70.00%` | `0.3977x` | `-21.99%` | `2.1445x` | `-29.23%` |

## 研究边界

- 此结果是 V1 clean surface 的 tuned observation，不自动登记为 V1.1/V2。
- reused holdout 已在 V1 研究中解锁，只能用于失败审计，不能作为新鲜 OOS。
- 只有在收益更高、回撤更小、胜率适中之外，同时通过 K+2、成本压力、参数邻域和新增 forward trades，才允许讨论 promotion。

## 机器证据

- `artifacts/eth_1h_ar_v1_clean_tune_2026-07-03.json`
- `artifacts/eth_1h_ar_v1_tune_bb_break_pool_2026-07-03.csv`
- `artifacts/eth_1h_ar_v1_tune_rsi_pool_2026-07-03.csv`
- `artifacts/eth_1h_ar_v1_tune_pairs_2026-07-03.csv`
- `artifacts/eth_1h_ar_v1_tune_selected_trades_2026-07-03.csv`

复现：

```bash
uv run python research/eth/1h-adaptive-regime/scripts/research_eth_1h_ar_v1_clean_tune.py
```
