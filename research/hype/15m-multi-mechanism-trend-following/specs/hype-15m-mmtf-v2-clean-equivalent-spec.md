# HYPE-15M-MMTF-V2 Clean-Equivalent 规格

- 状态：`registered / not promoted / not live-ready`
- 角色：V1 的 clean-equivalent；不提供新增收益证据。
- V1/V2 trade signature：`918fd1e59fb27ef6019fe6b3c09267511f1bb6cbbe26065ff980902c5abbcd20`
- Clean config SHA256：`4a3286429716b44958d3e890cb28c35752e06c5e42eff0ae75f9ade67a50fae2`

## Clean 参数

`ema_fast=24`、`ema_slow=384`、`atr_window=14`、`adx_min=26`、`rvol_min=1.0`、`keltner_atr=1.25`、`sl_atr=6`、`tp_atr=0.75`、`max_hold_bars=24`、`leverage=2`、`trend_exit_window=null`。

## 删除表面

删除 mechanism/direction selector、`entry_window`、`breakout_atr`、trailing activation/distance、breakeven、cooldown 与关闭状态下的 exit-window。adapter 映射仍为闭合 15m K 决策、K+1 open、stop-first、gap-open stop、fee/slippage/funding、单净仓。

## 证据

- [V1 消融](../ablations/hype-15m-mmtf-v1-full-ablation-2026-07-22.md)
- [clean adapter](../scripts/mmtf_v2.py)
- [等价与调优机器证据](../artifacts/hype_15m_mmtf_v2_clean_tune_2026-07-22.json)

