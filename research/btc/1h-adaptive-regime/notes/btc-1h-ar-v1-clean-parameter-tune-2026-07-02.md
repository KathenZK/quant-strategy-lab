# BTC-1H-Adaptive-Regime-V1 Clean 参数微调 - 2026-07-02

## 结论

本轮在全参数消融后的 27 个 active clean 参数上做 prefit-only 搜索。冻结候选选择规则为 `prefit_strict_improvement_k2_slip8_all_windows_gate_then_robust_score`；reused holdout 在冻结后才读取，不参与排序。

- 每腿随机样本：`150000`；保留 Keltner/CCI：`350` / `350`。
- 组合评估：`122500`；可评分：`68348`；prefit 严格改善观察：`809`。
- 完成 K+2 + 8 bps 预拟合稳健审计：`500` 个；其中严格改善候选：`500`。
- 严格改善且 K+2/8 bps 在 train、validation、prefit 全部正收益、胜率 >=50%、DD<20%：`15` 个。

## V1 与冻结微调观察

| Window | V1 annual | V1 DD | V1 win | Tune annual | Tune DD | Tune win | Tune trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.5774x` | `-15.13%` | `68.00%` | `3.4918x` | `-16.64%` | `84.38%` | `32` |
| `validation` | `3.3339x` | `-18.68%` | `68.75%` | `3.5867x` | `-18.06%` | `75.86%` | `29` |
| `prefit` | `2.8204x` | `-18.68%` | `68.29%` | `3.5247x` | `-18.06%` | `80.33%` | `61` |
| `reused_holdout` | `0.1695x` | `-42.73%` | `38.46%` | `0.6026x` | `-26.07%` | `54.55%` | `11` |
| `current_full` | `1.9412x` | `-42.73%` | `64.21%` | `2.7875x` | `-30.96%` | `76.39%` | `72` |

## 冻结参数

### Keltner clean

- `indicator_window` = `20`
- `band_k` = `2.0`
- `roc_window` = `12`
- `min_adx` = `40.0`
- `min_rvol` = `0.6`
- `max_atr_bps` = `150.0`
- `min_dir_roc_bps` = `-200.0`
- `htf_mode` = `h4`
- `max_aligned_funding_bps` = `8.0`
- `tp_atr` = `1.25`
- `sl_atr` = `4.5`
- `max_hold_bars` = `168`
- `cooldown_bars` = `24`
- `fixed_leverage` = `4.0`

### CCI clean

- `ema_htf` = `377`
- `indicator_window` = `20`
- `threshold_high` = `75.0`
- `max_adx` = `100.0`
- `min_rvol` = `2.0`
- `min_atr_bps` = `75.0`
- `max_atr_bps` = `600.0`
- `max_dist_ema_bps` = `10000.0`
- `tp_atr` = `6.0`
- `sl_atr` = `2.5`
- `max_hold_bars` = `72`
- `cooldown_bars` = `12`
- `fixed_leverage` = `3.0`

## 延迟与成本审计

| Scenario | Prefit annual | Prefit DD | Prefit win | Reused holdout annual | Reused holdout DD | Current full annual | Current full DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `base_k1` | `3.5247x` | `-18.06%` | `80.33%` | `0.6026x` | `-26.07%` | `2.7875x` | `-30.96%` |
| `delay_k2` | `2.8660x` | `-19.27%` | `77.05%` | `0.9278x` | `-16.00%` | `2.4672x` | `-20.92%` |
| `delay_k3` | `1.7076x` | `-38.37%` | `72.88%` | `0.9358x` | `-22.09%` | `1.5765x` | `-38.37%` |
| `slip_8bps` | `3.3323x` | `-18.37%` | `80.33%` | `0.5572x` | `-26.86%` | `2.6276x` | `-31.78%` |
| `slip_12bps` | `2.9510x` | `-24.69%` | `78.69%` | `0.5134x` | `-27.70%` | `2.3392x` | `-32.65%` |
| `fee12_slip8` | `3.1626x` | `-18.68%` | `80.33%` | `0.5221x` | `-27.56%` | `2.4895x` | `-32.53%` |
| `double_cost` | `2.5638x` | `-21.95%` | `75.41%` | `0.4019x` | `-30.33%` | `2.0043x` | `-35.43%` |

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
