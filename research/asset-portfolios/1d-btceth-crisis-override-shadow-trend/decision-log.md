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

## 2026-08-14 — 登记 COST V1；不 promotion

- 按用户明确请求，将 P0 最佳增长路径登记为 `Binance-1D-BTCETH-Crisis-Override-Shadow-Trend-V1`（`BIN-1D-BE-COST-V1`）。
- 冻结 CBCT P1 growth shadow `entry20/exit10/EMA50/trail5ATR/confirm2/cooldown7/maxhold120 + 1ATR/35%/2d` 与 crisis `EMA200/slope60/confirm3`。
- 状态为 `registered / not promoted / not live-ready`；P0 `HARD-GATE-FAILED` 和 research line closed 均不变，audit/prospective 不读取、不回填。
- 新增[V1规格](specs/binance-1d-be-cost-v1-spec.md)及[完整交易路径 HTML](artifacts/binance_1d_be_cost_v1_trade_path_2026-08-14.html)；路径含 BTC/ETH 日K、各自 EMA50、权益、3段 crisis 和全部进出场连线。
