# BNB-1H-Adaptive-Regime-V2 消融引导微调 - 2026-07-07

## 结论

在 V2 clean 参数上做消融引导微调。选参只使用 train/validation/prefit；locked OOS 已在 V1 搜索时揭盲，本轮对唯一首选组合复用该窗口，结果只作为观察值，不支持 promotion。

- Leg 采样：`ema_pullback` `2000`、`wick_reject` `1600`；每侧取 top `40` 组成 `1600` 个 ensemble。
- prefit gate（收益更高、回撤更小、胜率更高，均相对 V2 prefit `2.20x / -18.66% / 87.04%`）通过：`168`。

## 首选结果

- 首选：`BNB_1H_AR_V2_EMA_PULLBACK_T00405` + `BNB_1H_AR_V2_WICK_REJECT_T01080`（prefit-only gate + score 选出，唯一一次 reused OOS 揭盲）。
- train：`2.95x` / `242.90%` / `-16.65%` / `88.89%` / `72`。
- validation：`4.58x` / `110.05%` / `-18.24%` / `90.62%` / `32`。
- prefit：`3.37x` / `620.27%` / `-18.24%` / `89.42%` / `104`。
- reused locked OOS（观察值）：`1.22x` / `5.08%` / `-15.53%` / `81.25%` / `16`。
- full：`2.94x` / `656.84%` / `-18.24%` / `88.33%` / `120`。
- 实际最大暴露 `2.5x`，未触及 `3x` 硬上限；merge priorities `2.4458 / 1.6307`。

## 相对 V2 的参数变化

- `ema_pullback`：`ema_slow` `89 -> 144`；出场 `fixed(tp 3.0 / sl 5.0)` -> `trailing(tp 3.0 / sl 5.0 / activation 2.0 ATR / trail 1.5 ATR)`；`max_hold_bars` `168 -> 240`；`cooldown_bars` `6 -> 12`；`fixed_leverage` `2.0 -> 2.5`。
- `wick_reject`：`threshold_low` `0.35 -> 0.40`；`threshold_high` `0.85 -> 0.75`；`min_adx` `24 -> 28`；`max_hold_bars` `72 -> 48`；`fixed_leverage` `0.75 -> 1.0`。
- 其余字段与 V2 相同；完整配置见 `../artifacts/bnb_1h_ar_v2_micro_tune_2026-07-07.json`。

## 口径

- Market：Binance USD-M Futures `BNBUSDT` perpetual `1h`；数据与 V1/V2 冻结一致（UTC 至 `2026-07-03`），未刷新。
- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，逐笔计入 funding；杠杆硬上限 `<=3x`。
- Gate：train/validation/prefit 回撤均需优于 V2 prefit DD，prefit 胜率 `>= 87.04%`，prefit 年化 `> 2.2025x`，validation trades `>= 15`。

## Promotion 边界

reused OOS 属于二次读取，任何微调结果都不能凭此标记 candidate/paper-live/live；如需推进，必须等新的 forward 数据形成真正未读 OOS 或走完整重新冻结流程。

## 产物

- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v2_micro_tune_2026-07-07.json`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v2_micro_tune_legs_2026-07-07.csv`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v2_micro_tune_ensembles_2026-07-07.csv`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v2_micro_tune_preferred_trades_2026-07-07.csv`
