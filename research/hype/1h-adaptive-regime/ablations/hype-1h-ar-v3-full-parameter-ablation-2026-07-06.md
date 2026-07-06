# HYPE-1H-Adaptive-Regime-V3 全参数消融与时间片复核 - 2026-07-06

## 结论

`HYPE-1H-Adaptive-Regime-V3` 按用户要求登记为 V3 diagnostic baseline，来源为 V2 消融引导组合 `di_roc_off__stoch_th55`。

本轮以 V3 为 baseline，覆盖 clean 配置接口 `34` 个字段槽：DI-cross `15` 个，Stoch-reversal `19` 个；输出 `98` 行，coverage missing fields 为 `0`。

V3 current full 为 `15.0530x`、DD `-19.11%`、胜率 `79.73%`、`74` 笔；reused holdout 为 `9.0300x`、DD `-19.11%`。

单字段消融中 current full 同时提高年化、降低回撤且胜率 `>=50%` 的行数为 `9`；完整 current full + reused holdout target-like 通过行数为 `5`。

结论：V3 比 V2 baseline 明显更强，但 reused holdout 年化仍低于 `10x`，且前序 K+2/8bps 组合压力已失败；仍维持 `NO-GO / not live-ready / not promoted`。

## V3 参数

### DI-cross

```text
ema_htf=89
min_adx=12.0
max_adx=36.0
min_rvol=2.0
max_atr_bps=250.0
roc_window=24
min_dir_roc_bps=-10000.0
max_dist_ema_bps=750.0
htf_mode=h12
require_body_dir=True
max_aligned_funding_bps=8.0
tp_atr=1.5
sl_atr=4.0
max_hold_bars=18
fixed_leverage=3.0
```

### Stoch-reversal

```text
indicator_window=21
threshold_low=25.0
threshold_high=55.0
ema_htf=55
min_adx=12.0
min_rvol=1.0
min_atr_bps=200.0
max_atr_bps=400.0
max_dist_ema_bps=2500.0
macd_fast=8
macd_slow=21
macd_signal=5
require_macd_turn=True
sl_atr=4.0
trail_activation_atr=1.0
trail_atr=1.0
max_hold_bars=8
cooldown_bars=24
fixed_leverage=2.0
```

## V3 当前数据复现

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Prefit | `17.4864x` | `747.10%` | `-16.93%` | `80.70%` | `57` | `8.288` |
| Reused holdout | `9.0300x` | `61.90%` | `-19.11%` | `76.47%` | `17` | `5.521` |
| Current full | `15.0530x` | `1271.47%` | `-19.11%` | `79.73%` | `74` | `7.549` |

## 最近窗口

| Window | Trades | Win | Return | DD | Annual |
| --- | ---: | ---: | ---: | ---: | ---: |
| `last_7d` | `1` | `100.00%` | `3.91%` | `-0.56%` | `7.3908x` |
| `last_30d` | `8` | `87.50%` | `43.70%` | `-16.37%` | `82.6096x` |
| `last_90d` | `18` | `72.22%` | `60.83%` | `-19.11%` | `6.8789x` |
| `last_180d` | `36` | `72.22%` | `200.15%` | `-19.11%` | `9.3027x` |
| `last_365d` | `74` | `79.73%` | `1271.47%` | `-19.11%` | `15.0530x` |

## 滚动窗口摘要

| Rolling slice | Windows | Zero-trade | Positive | Trades median/min/max | Median win | Worst/Best return |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `rolling_7d_step7d` | `50` | `9` | `36` | `2.0/0/4` | `100.00%` | `-2.73% / 25.18%` |
| `rolling_30d_step30d` | `11` | `0` | `11` | `6.0/2/10` | `80.00%` | `1.61% / 47.81%` |
| `rolling_90d_step30d` | `9` | `0` | `9` | `19.0/12/26` | `75.00%` | `38.12% / 195.51%` |
| `rolling_180d_step30d` | `6` | `0` | `6` | `41.0/36/45` | `78.64%` | `172.30% / 474.66%` |

## Top current full 单字段改善诊断

| Label | Current annual | Current DD | Current win | Current trades | Reused holdout annual | Reused holdout DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `di_cross__require_body_dir__False` | `16.3684x` | `-19.11%` | `80.00%` | `75` | `13.0662x` | `-19.11%` |
| `stoch_reversal__macd_fast__12` | `16.2191x` | `-19.11%` | `78.08%` | `73` | `9.0300x` | `-19.11%` |
| `stoch_reversal__macd_slow__55` | `16.2191x` | `-19.11%` | `78.08%` | `73` | `9.0300x` | `-19.11%` |
| `stoch_reversal__macd_slow__89` | `16.2191x` | `-19.11%` | `78.08%` | `73` | `9.0300x` | `-19.11%` |
| `stoch_reversal__min_adx__0p0` | `16.1764x` | `-19.11%` | `79.73%` | `74` | `9.0300x` | `-19.11%` |
| `stoch_reversal__min_adx__8p0` | `16.1764x` | `-19.11%` | `79.73%` | `74` | `9.0300x` | `-19.11%` |
| `stoch_reversal__macd_slow__26` | `15.6107x` | `-19.11%` | `79.45%` | `73` | `9.0300x` | `-19.11%` |
| `stoch_reversal__cooldown_bars__48` | `15.5836x` | `-16.93%` | `80.30%` | `66` | `18.2270x` | `-10.10%` |
| `stoch_reversal__ema_htf__233` | `15.1242x` | `-19.11%` | `80.82%` | `73` | `9.2198x` | `-19.11%` |

## Promotion 边界

- V3 是用户指定登记的 diagnostic baseline，不是 live、paper-live、dry-run、candidate 或 handoff。
- Reused holdout 已解锁，本轮消融不能把后段结果重新包装为 untouched OOS。
- 后续若要继续，只能基于冻结后的新增 forward trades、K+2/滑点压力、真实 stop-market 滑点、生产 runner、重启恢复、交易所对账和 kill switch 证据推进。

## 机器证据

- JSON：`artifacts/hype_1h_ar_v3_full_ablation_2026-07-06.json`
- 行级 CSV：`artifacts/hype_1h_ar_v3_full_ablation_rows_2026-07-06.csv`
- 字段级 CSV：`artifacts/hype_1h_ar_v3_full_ablation_fields_2026-07-06.csv`
- 窗口 CSV：`artifacts/hype_1h_ar_v3_full_ablation_windows_2026-07-06.csv`
- 滚动窗口 CSV：`artifacts/hype_1h_ar_v3_rolling_windows_2026-07-06.csv`

复现：

```bash
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v3_full_ablation.py
```
