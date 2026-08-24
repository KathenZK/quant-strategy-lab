# BIN-1D-BE-CPPR Decision Log

## 2026-08-12 — P0 家族与合同冻结

- COST修复2022后，最大风险转为最终高盈利BTC long中的`-35.22%`持仓内回吐。
- 冻结P1 risk-frontier已使用的`1ATR/20%/1d`信号，但把full exit改为单次partial bank；COST crisis与原`35%/2d`full protection不变。
- 只检验`25/50/75%`三种fraction；不搜新activation/giveback/confirm，不加仓、不按波动缩放。

## 2026-08-12 — P0 HARD-GATE-FAILED；research line closed

- 25%为`16.4626x/-31.87%`，75%为`6.6693x/-29.25%`；三臂均22次partial。
- partial单调降低风险但破坏趋势复利，未形成20x/20%前沿；按合同不插值、不加第二次partial。
- audit/prospective未读取，下一步仅允许独立profit-exit handoff continuity。[P0裁决](diagnostics/binance-1d-be-cppr-p0-2026-08-12.md)
