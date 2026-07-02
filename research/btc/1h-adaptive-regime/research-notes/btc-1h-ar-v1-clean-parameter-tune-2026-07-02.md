# BTC-1H-Adaptive-Regime-V1 Clean 参数微调 - 2026-07-02

## 结论

本轮在全参数消融后的 27 个 active clean 参数上做 prefit-only 搜索。冻结候选选择规则为 `prefit_strict_improvement_then_robust_score`；reused holdout 在冻结后才读取，不参与排序。

- 每腿随机样本：`150000`；保留 Keltner/CCI：`350` / `350`。
- 组合评估：`122500`；可评分：`68348`；prefit 严格改善观察：`809`。
- 完成 K+2 + 8 bps 预拟合稳健审计：`500` 个；其中严格改善候选：`500`。

## V1 与冻结微调观察

| Window | V1 annual | V1 DD | V1 win | Tune annual | Tune DD | Tune win | Tune trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.5774x` | `-15.13%` | `68.00%` | `4.1255x` | `-15.48%` | `86.49%` | `37` |
| `validation` | `3.3339x` | `-18.68%` | `68.75%` | `2.7620x` | `-11.44%` | `82.76%` | `29` |
| `prefit` | `2.8204x` | `-18.68%` | `68.29%` | `3.5850x` | `-15.48%` | `84.85%` | `66` |
| `reused_holdout` | `0.1695x` | `-42.73%` | `38.46%` | `1.5899x` | `-14.98%` | `81.82%` | `11` |
| `current_full` | `1.9412x` | `-42.73%` | `64.21%` | `3.2179x` | `-15.48%` | `84.42%` | `77` |

## 冻结参数

### Keltner clean

- `indicator_window` = `20`
- `band_k` = `2.0`
- `roc_window` = `24`
- `min_adx` = `40.0`
- `min_rvol` = `1.25`
- `max_atr_bps` = `200.0`
- `min_dir_roc_bps` = `-200.0`
- `htf_mode` = `h4`
- `max_aligned_funding_bps` = `4.0`
- `tp_atr` = `1.5`
- `sl_atr` = `5.0`
- `max_hold_bars` = `240`
- `cooldown_bars` = `0`
- `fixed_leverage` = `2.0`

### CCI clean

- `ema_htf` = `377`
- `indicator_window` = `20`
- `threshold_high` = `125.0`
- `max_adx` = `45.0`
- `min_rvol` = `1.25`
- `min_atr_bps` = `75.0`
- `max_atr_bps` = `600.0`
- `max_dist_ema_bps` = `750.0`
- `tp_atr` = `4.5`
- `sl_atr` = `1.5`
- `max_hold_bars` = `72`
- `cooldown_bars` = `48`
- `fixed_leverage` = `3.0`

## 延迟与成本审计

| Scenario | Prefit annual | Prefit DD | Prefit win | Reused holdout annual | Reused holdout DD | Current full annual | Current full DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `base_k1` | `3.5850x` | `-15.48%` | `84.85%` | `1.5899x` | `-14.98%` | `3.2179x` | `-15.48%` |
| `delay_k2` | `2.7434x` | `-21.77%` | `80.30%` | `1.7549x` | `-15.66%` | `2.5853x` | `-21.77%` |
| `delay_k3` | `1.7106x` | `-27.99%` | `74.63%` | `2.3098x` | `-14.62%` | `1.7802x` | `-27.99%` |
| `slip_8bps` | `3.4513x` | `-15.80%` | `84.85%` | `1.5306x` | `-15.09%` | `3.0979x` | `-15.80%` |
| `slip_12bps` | `3.1895x` | `-16.15%` | `83.33%` | `1.4731x` | `-15.20%` | `2.8784x` | `-16.15%` |
| `fee12_slip8` | `3.3234x` | `-16.15%` | `84.85%` | `1.4734x` | `-15.21%` | `2.9830x` | `-16.15%` |
| `double_cost` | `2.8565x` | `-17.89%` | `83.33%` | `1.2646x` | `-15.69%` | `2.5635x` | `-17.89%` |

## 研究边界

- 此结果是 V1 clean surface 的 tuned observation，不自动登记为 V1.1/V2。
- reused holdout 已在 V1 研究中解锁，只能用于失败审计，不能作为新鲜 OOS。
- 只有在收益更高、回撤更小、胜率适中之外，同时通过 K+2、成本压力、参数邻域和新增 forward trades，才允许讨论 promotion。

## 机器证据

- `artifacts/btc_1h_ar_v1_clean_tune_2026-07-02.json`
- `artifacts/btc_1h_ar_v1_tune_keltner_pool_2026-07-02.csv`
- `artifacts/btc_1h_ar_v1_tune_cci_pool_2026-07-02.csv`
- `artifacts/btc_1h_ar_v1_tune_pairs_2026-07-02.csv`
- `artifacts/btc_1h_ar_v1_tune_selected_trades_2026-07-02.csv`

复现：

```bash
uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v1_clean_tune.py
```
