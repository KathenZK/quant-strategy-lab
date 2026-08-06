# HYPE-1H-Multi-Mechanism-Trend-Following-V3 调优冻结规格

- 状态：`registered / HARD-GATE-FAILED / not promoted / not live-ready`。
- 冻结时点：locked OOS 揭示前；揭示后禁止修改或据其追参。
- clean config SHA256：`9f3c9ae1...89e0b`；engine config SHA256：`fe21b8fc...3b777`。

## 冻结参数

`entry_window=120`、`ema_fast=96`、`ema_slow=168`、`atr_window=48`、`rvol_min=0.75`、`momentum_threshold_atr=2.0`、`sl_atr=4.0`、`tp_atr=1.25`、`trail_activation_atr=0.75`、`trail_atr=2.0`、`cooldown_bars=18`、`leverage=2.5`。

## 规则

- `close[t]-close[t-120]` 以 ATR48 归一化，上穿 `+2 ATR` 做多、下穿 `-2 ATR` 做空；方向须与 EMA96/168 排列一致，RVOL48 至少 `0.75`。
- 信号在闭合 1h K 确认，下一根 open 入场；单净仓。
- 初始 stop `4 ATR`；TP `1.25 ATR`；浮盈达 `0.75 ATR` 后按有利极值回撤 `2 ATR` 更新下一 bar stop；出场冷却 `18h`。
- 固定 `2.5x`；fee `0.001/fill`、slippage `4 bps/fill`、真实 funding；stop-first、gap-open。

最终指标和失败门禁见 [V3 最终审计](../diagnostics/hype-1h-mmtf-v3-final-audit-2026-07-22.md)。
