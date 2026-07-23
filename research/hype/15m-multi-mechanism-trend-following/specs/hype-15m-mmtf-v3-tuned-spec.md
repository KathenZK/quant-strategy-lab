# HYPE-15M-MMTF-V3 冻结规格

## 身份与状态

- 状态：`registered / HARD-GATE-FAILED / not promoted / not live-ready`
- Clean config SHA256：`bf2fff5f72e036fb15758f96419d0b14745f526439195aa71f0bd153b07f887e`
- Engine config SHA256：`2f9a7ab658df2d0fa58ce9f7e4095e3092fb34d5e28b20f7235fd6604c925561`
- locked OOS 揭示后禁止继续调参。

## 冻结参数

`ema_fast=24`、`ema_slow=384`、`atr_window=14`、`adx_min=26`、`rvol_min=1.0`、`keltner_atr=1.25`、`sl_atr=8`、`tp_atr=0.75`、`max_hold_bars=24`、`leverage=3`、`trend_exit_window=null`。

信号、成本和成交时序与 [V1 规格](hype-15m-mmtf-v1-original-baseline-spec.md)相同；V3 使用 clean adapter，不包含 V1 已证明 dormant 的 trailing、breakeven、cooldown 与无关窗口。

## 证据

- [clean tune](../diagnostics/hype-15m-mmtf-v2-clean-tune-2026-07-22.md)
- [prefit robustness](../artifacts/hype_15m_mmtf_v3_prefit_robustness_2026-07-22.json)
- [locked OOS reveal](../artifacts/hype_15m_mmtf_v3_locked_oos_reveal_2026-07-22.json)

