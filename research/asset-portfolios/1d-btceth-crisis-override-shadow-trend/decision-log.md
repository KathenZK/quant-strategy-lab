# BIN-1D-BE-COST Decision Log

## 2026-08-12 — P0 家族与合同冻结

- CBCT P1 最大 ordered drawdown 位于 2022-06 至 2022-11，包含 bear-rally long 与反弹期 short 的跨交易方向错配。
- DASE 静态分散仍为 `-34.34%`；agreement/disagreement 无稳定动态路由信息。
- 冻结账户级 crisis override：仅用两资产 EMA side+slope 的确认状态，危机中替换为 `0.5x+0.5x` short basket。
- 不搜索价格跌幅/波动阈值，不增加 gross，不恢复中断旧仓；结果前固定12个状态配置。

## 2026-08-12 — P0 HARD-GATE-FAILED；research line closed

- 最佳 `EMA200/slope60/confirm3`：base `23.1321x/-35.22%`，stress `22.6556x/-35.22%`，delay `7.2746x/-37.00%`。
- 三次crisis episodes修复2022并增益，但实际override exits为0；新的风险瓶颈是2020-10至2021-02盈利BTC long中的`-35.22%`持仓内回吐。
- 更快EMA配置双劣；按合同关闭，不读取audit/prospective。[P0裁决](diagnostics/binance-1d-be-cost-p0-2026-08-12.md)
