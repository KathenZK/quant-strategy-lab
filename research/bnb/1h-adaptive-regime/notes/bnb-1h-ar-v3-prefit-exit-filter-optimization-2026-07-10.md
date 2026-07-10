# BNB-1H-Adaptive-Regime-V3 prefit-only exit/filter 优化诊断 - 2026-07-10

## 结论

本次只研究 V3 附近的 exit/trailing 与过滤强度，不读取、不排序、不报告 reused locked OOS 指标；任何 prefit 入场但出场跨入 OOS 的候选都从选择集中剔除。

- Leg 采样：`ema_pullback` `6000`、`wick_reject` `6000`；每侧 top `60` 组成 ensemble surface。
- 最大暴露约束：`<= 2.5x`，避免用简单加杠杆掩盖结构问题。
- 因 prefit/OOS 边界跨越被剔除：`ema_pullback` `0`，`wick_reject` `760`，ensemble `0`。

## Prefit-only 首选观察值

- 首选：`BNB_1H_AR_V3_EMA_PULLBACK` + `BNB_1H_AR_V3_WICK_REJECT_EF05613`。
- train：`3.17x` / `271.66%` / `-16.65%` / `86.89%` / `61`。
- validation：`4.76x` / `114.13%` / `-18.24%` / `89.29%` / `28`。
- prefit：`3.58x` / `695.84%` / `-18.24%` / `87.64%` / `89`。
- 相对 V3 prefit：annual `+0.21x`，DD `+0.00 pct`，win `-1.78 pct`，trades `-15`。
- 该结果只是下一轮 forward/re-freeze 的候选设计，不登记为 V4，不可 promotion。

## 参数变化

相对 V3：
- `ema_pullback`：无变化。
- `wick_reject`：`threshold_high` `0.75` -> `0.85`；`band_k` `0.5` -> `0.75`；`tp_atr` `1.0` -> `1.25`；`sl_atr` `5.0` -> `4.0`；`max_hold_bars` `48` -> `24`；`fixed_leverage` `1.0` -> `1.25`。

## 口径

- Market：Binance USD-M Futures `BNBUSDT` perpetual `1h`。
- 数据：沿用 V1/V2/V3 冻结数据；本诊断的排序窗口只到 `oos_start` 前。
- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，逐笔计入 funding。
- Gate：train/validation/prefit 均为正收益；prefit trades `>=70`、validation trades `>=15`；三段 max DD 均需 `>-20%`；validation/prefit win 均需 `>=80%`；max exposure `<=2.5x`。

## Promotion 边界

本报告不含 reused locked OOS 指标，因此不能声称优于 V3 的 OOS 表现。若要把某个观察值登记为新版本，必须先决定是否重开冻结流程或等待新的未读 forward 数据。

## 产物

- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v3_prefit_exit_filter_tune_2026-07-10.json`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v3_prefit_exit_filter_tune_legs_2026-07-10.csv`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v3_prefit_exit_filter_tune_ensembles_2026-07-10.csv`
