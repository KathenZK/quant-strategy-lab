# TRX-1H-Adaptive-Regime 主账

## 家族身份

- Full family name：`TRX-1H-Adaptive-Regime`
- Short id：`TRX-1H-AR`
- Market：Binance USD-M Futures `TRXUSDT` perpetual
- Timeframe：`1h`

## 当前状态

`NO-GO / diagnostic versions registered / not promoted / not live-ready`。

2026-07-03 两阶段搜索、持续 regime 上界和 live-feasibility 审计均为 `0` hard-gate 命中。按后续研究指令，领先观察值登记为 `TRX-1H-Adaptive-Regime-V1base`，并在全参数消融后把删参干净版登记为 `TRX-1H-Adaptive-Regime-V2`。两者都只是 diagnostic baseline / clean baseline，不是 candidate。

## 当前边界

| Scope | Annual multiple | Return | Max DD | Win rate | Trades | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| prefit | `5.189x` | `+1355.40%` | `-19.84%` | `87.50%` | `96` | annual `<10x` |
| locked OOS | `0.844x` | `-4.12%` | `-11.42%` | `75.00%` | `8` | loss, annual `<10x`, insufficient trades |
| full | `4.077x` | `+1295.38%` | `-19.84%` | `86.54%` | `104` | annual `<10x`; OOS failed |

领先观察值：`ENS__TRX_1H_AR_N131875__TRX_1H_AR_N129128`，仅由 prefit score 选择。证据见 `research-notes/trx-1h-ar-search-conclusion-2026-07-03.md`、`live-specs/trx-1h-ar-live-feasibility-2026-07-03.md` 和 `ablations/trx-1h-ar-v1base-full-parameter-ablation-2026-07-03.md`。

## V1base 规则

`TRX-1H-Adaptive-Regime-V1base` 固定为双组件 ensemble：

- `TRX_1H_AR_N131875`：`macd_flip`，`MACD(34,89,13)`，both sides；`ADX 12-28`、`RVOL>=1.5`、`ATR<=200 bps`、directional `ROC12>=-100 bps`、距 `EMA377<=1000 bps`、`12h` trend 同向、MACD turn；fixed `TP=2 ATR / SL=4 ATR / hold<=168h / cooldown=3h / 4x`。
- `TRX_1H_AR_N129128`：`stoch_reversal`，long-only，`Stoch(21)` 阈值 `25/85`；`ADX<=30`、`RVOL>=1.0`、`ROC3>=-200 bps`、body 同向；trailing `initial SL=5 ATR / activation=3 ATR / trail=1.25 ATR / hold<=168h / cooldown=24h / 3x`。
- 冲突处理：两组件按 prefit score 冻结优先级合并，单仓、不加仓。

## V2 Clean 规则

`TRX-1H-Adaptive-Regime-V2` 是 V1base 的删参干净版；全参数消融覆盖 `78` 个字段槽，分类为 `33 active_tunable / 27 baseline_fixed_remove / 12 contract_fixed / 6 neutral_fixed_remove`。V2 移除 `33` 个 baseline/neutral fixed 字段，保留 `45` 个 active/contract 字段；当前行为边界与 V1base 等价，仍为 `NO-GO`。

V2 clean 参数面：

- `macd_flip` 保留：`cooldown_bars`、`ema_htf`、`entry_delay_bars`、`exit_kind`、`fixed_leverage`、`htf_mode`、`macd_fast`、`macd_signal`、`macd_slow`、`max_adx`、`max_atr_bps`、`max_dist_ema_bps`、`max_hold_bars`、`min_adx`、`min_dir_roc_bps`、`min_rvol`、`name`、`require_macd_turn`、`roc_window`、`side_mode`、`sizing_kind`、`sl_atr`、`style`、`tp_atr`。
- `stoch_reversal` 保留：`cooldown_bars`、`ema_htf`、`entry_delay_bars`、`exit_kind`、`fixed_leverage`、`indicator_window`、`max_adx`、`max_hold_bars`、`min_dir_roc_bps`、`min_rvol`、`name`、`require_body_dir`、`roc_window`、`side_mode`、`sizing_kind`、`sl_atr`、`style`、`threshold_high`、`threshold_low`、`trail_activation_atr`、`trail_atr`。

## 版本表

| Version | Status | Metrics | Evidence | Live readiness |
| --- | --- | --- | --- | --- |
| `TRX-1H-Adaptive-Regime-V1base` | diagnostic baseline / not promoted | full `4.077x annual / -19.84% DD / 86.54% win / 104 trades`; locked OOS `0.844x annual / -4.12% return / -11.42% DD / 75.00% win / 8 trades` | `research-notes/trx-1h-ar-search-conclusion-2026-07-03.md`; `live-specs/trx-1h-ar-live-feasibility-2026-07-03.md`; `artifacts/trx_1h_adaptive_regime_refine_2026-07-03.json` | `NO-GO / not live-ready` |
| `TRX-1H-Adaptive-Regime-V2` | clean-equivalent diagnostic baseline / not promoted | same behavior boundary as V1base; V2 clean ablation coverage `45/45`; recent slices: `1d/7d` no trades, `1m -10.12%`, `3m -4.12%`, `6m +12.80%`, `1y +45.18%`; execution replay violations `0` | `ablations/trx-1h-ar-v1base-full-parameter-ablation-2026-07-03.md`; `ablations/trx-1h-ar-v2-strict-ablation-slices-2026-07-03.md`; `artifacts/trx_1h_ar_v1base_full_ablation_2026-07-03.json`; `artifacts/trx_1h_ar_v2_strict_ablation_slices_2026-07-03.json` | `NO-GO / not live-ready` |
