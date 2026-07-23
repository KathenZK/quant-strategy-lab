# HYPE-1H-Multi-Mechanism-Trend-Following-V2 Clean-Equivalent 规格

- 状态：`registered clean-equivalent / NO-GO / not promoted / not live-ready`。
- 身份：V1 全消融后删除 8 个机制选择、fixed-disabled 或 path-equal 槽；成交、资金费、成本和权益路径与 V1 完全一致。
- 逐笔 SHA256：V1/V2 均为 `f70a8ea2...224b`；clean config SHA256 为 `00fc75b6...042e4`。

## 12 参数 clean interface

`entry_window=120`、`ema_fast=96`、`ema_slow=120`、`atr_window=48`、`rvol_min=0.75`、`momentum_threshold_atr=2.0`、`sl_atr=4.0`、`tp_atr=1.5`、`trail_activation_atr=0.75`、`trail_atr=2.5`、`cooldown_bars=24`、`leverage=2.0`。

固定合同：双向 time-series momentum、EMA regime 开启、trend-exit/timeout/breakeven 关闭；K+1 open、单净仓、fee `0.001/fill`、slippage `4 bps/fill`、真实 funding、stop-first 与 gap-open。

证据：[消融报告](../ablations/hype-1h-mmtf-v1-full-ablation-2026-07-22.md) · [clean tune JSON](../artifacts/hype_1h_mmtf_v2_clean_tune_2026-07-22.json)
