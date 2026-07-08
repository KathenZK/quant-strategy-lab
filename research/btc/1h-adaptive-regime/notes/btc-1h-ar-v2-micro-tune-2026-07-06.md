# BTC-1H-Adaptive-Regime-V2 微调观察 - 2026-07-06

## 结论

基于 V2 全参数消融的前沿方向，执行受约束 micro-tune。选参只读取 train/validation/prefit；reused holdout 已解锁，只作冻结后复用审计。

网格共 `7200` 组，满足“prefit 年化高于 V2、train/validation/prefit 胜率均 >=80%、回撤均 <20%”的组合 `3852` 组。

当前首选观察为 `BTC-1H-AR-V2-MICRO-TUNE-2026-07-06`。2026-07-06 按用户要求，该观察已在 `btc-1h-ar-core-ledger.md` 登记为 `BTC-1H-Adaptive-Regime-V3`；此次登记只固定版本身份和参数，不标记 live-ready。

## V2 基线 vs 微调观察

| Window | V2 annual / return / DD / win / trades | Micro-tune annual / return / DD / win / trades |
| --- | --- | --- |
| `train` | `3.6068x` / `288.08%` / `-13.99%` / `86.49%` / `37` | `7.3797x` / `727.16%` / `-12.87%` / `91.18%` / `34` |
| `validation` | `2.5108x` / `68.88%` / `-10.29%` / `82.76%` / `29` | `4.3990x` / `132.38%` / `-10.80%` / `82.76%` / `29` |
| `prefit` | `3.1773x` / `555.39%` / `-13.99%` / `84.85%` / `66` | `6.1574x` / `1822.15%` / `-12.87%` / `87.30%` / `63` |
| `reused_holdout` | `1.5232x` / `11.05%` / `-13.48%` / `81.82%` / `11` | `1.8998x` / `17.34%` / `-17.47%` / `81.82%` / `11` |
| `current_full` | `2.8817x` / `627.83%` / `-13.99%` / `84.42%` / `77` | `5.2669x` / `2155.40%` / `-17.47%` / `86.49%` / `74` |

## 冻结参数

### Keltner leg

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
- `fixed_leverage` = `2.4`

### CCI leg

- `ema_htf` = `377`
- `indicator_window` = `20`
- `threshold_high` = `125.0`
- `max_adx` = `40.0`
- `min_rvol` = `1.25`
- `min_atr_bps` = `75.0`
- `max_atr_bps` = `600.0`
- `max_dist_ema_bps` = `750.0`
- `tp_atr` = `5.5`
- `sl_atr` = `1.5`
- `max_hold_bars` = `72`
- `cooldown_bars` = `0`
- `fixed_leverage` = `3.5`

## 选择边界

- 本轮不改变 `style`、`side_mode`、`entry_delay_bars`、`exit_kind` 或 `sizing_kind` 等合同字段。
- 本轮没有新增 forward trades，也没有 production runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 或真实 stop-market 滑点证据。
- 已按用户要求登记为 `BTC-1H-Adaptive-Regime-V3`；当前仍只是 diagnostic micro-tune observation，不是 candidate、paper-live 或 live-ready。

## 机器证据

- `artifacts/btc_1h_ar_v2_micro_tune_2026-07-06.json`
- `artifacts/btc_1h_ar_v2_micro_tune_grid_2026-07-06.csv`
- `artifacts/btc_1h_ar_v2_micro_tune_selected_trades_2026-07-06.csv`

复现：

```bash
uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v2_micro_tune.py
```
