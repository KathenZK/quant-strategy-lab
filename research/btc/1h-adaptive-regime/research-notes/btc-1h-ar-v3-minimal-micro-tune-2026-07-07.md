# BTC-1H-Adaptive-Regime-V3 最小表面微调 - 2026-07-07

## 结论

在 V3 参数必要性审计得到的最小等价表面（19 个必要参数，8 个非必要槽位已固定为中和值）上执行受约束微调。选参只读取 train/validation/prefit；两腿杠杆冻结为 V3 值，避免用曝光缩放伪装结构改善；reused holdout 不参与选参。

腿级变体 Keltner `486` 组、CCI `1728` 组，按腿 prefit score 截断为 `96`/`256` 后组合网格 `24576` 组。同时满足“prefit 年化更高、回撤更小、胜率更高（三项均严格优于 V3）且 train/validation 胜率 >=80%、回撤 <20%、同正”的组合为 `0` 组；退化为 Pareto 口径（年化严格更高、回撤与胜率不劣于 V3）的组合为 `8` 组。

实际选择层级：`pareto_annual_up_dd_win_not_worse`。首选观察 `BTC-1H-AR-V3-MINIMAL-MICRO-TUNE-2026-07-07`（未登记新版本，not live-ready）。

## V3 基线 vs 最小表面微调

| Window | V3 annual / return / DD / win / trades | Micro-tune annual / return / DD / win / trades |
| --- | --- | --- |
| `train` | `7.3797x` / `727.16%` / `-12.87%` / `91.18%` / `34` | `7.5382x` / `745.95%` / `-12.87%` / `91.18%` / `34` |
| `validation` | `4.3990x` / `132.38%` / `-10.80%` / `82.76%` / `29` | `4.3990x` / `132.38%` / `-10.80%` / `82.76%` / `29` |
| `prefit` | `6.1574x` / `1822.15%` / `-12.87%` / `87.30%` / `63` | `6.2430x` / `1865.80%` / `-12.87%` / `87.30%` / `63` |
| `reused_holdout` | `1.8998x` / `17.34%` / `-17.47%` / `81.82%` / `11` | `1.8998x` / `17.34%` / `-17.47%` / `81.82%` / `11` |
| `current_full` | `5.2669x` / `2155.40%` / `-17.47%` / `86.49%` / `74` | `5.3303x` / `2206.62%` / `-17.47%` / `86.49%` / `74` |

## 选中参数（最小表面，19 个必要参数）

### Keltner leg

- `indicator_window` = `20`
- `band_k` = `2.0`
- `min_adx` = `40.0`
- `min_rvol` = `1.25`
- `htf_mode` = `h4`
- `tp_atr` = `1.5`
- `sl_atr` = `5.0`
- `fixed_leverage` = `2.4`

### CCI leg

- `ema_htf` = `377`
- `indicator_window` = `20`
- `threshold_high` = `125.0`
- `max_adx` = `40.0`
- `min_rvol` = `1.25`
- `min_atr_bps` = `75.0`
- `max_dist_ema_bps` = `700.0`（V3：`750.0`）
- `tp_atr` = `5.5`
- `sl_atr` = `1.5`
- `max_hold_bars` = `96`（V3：`72`）
- `fixed_leverage` = `3.5`

## 选择边界

- 微调发生在最小等价表面上；被移除的 8 个槽位保持中和值，不参与搜索。
- 杠杆冻结为 V3 值（Keltner `2.4x`、CCI `3.5x`），收益差异来自信号/出场结构而非曝光。
- 本轮没有新增 forward trades，也没有 production runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 或真实 stop-market 滑点证据。
- 若要登记为新版本，需要另行确认；当前只是 diagnostic micro-tune observation。

## 机器证据

- `artifacts/btc_1h_ar_v3_minimal_micro_tune_2026-07-07.json`
- `artifacts/btc_1h_ar_v3_minimal_micro_tune_grid_2026-07-07.csv`
- `artifacts/btc_1h_ar_v3_minimal_micro_tune_selected_trades_2026-07-07.csv`

复现：

```bash
uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v3_minimal_micro_tune.py
```
