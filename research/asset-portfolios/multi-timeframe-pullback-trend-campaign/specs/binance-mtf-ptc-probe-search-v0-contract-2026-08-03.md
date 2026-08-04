# BIN-MTF-PTC Probe Search V0 Contract（2026-08-03）

V0/V1 anchor diagnostics表明固定 24h/12h/4h onset + 默认回调并未普遍改善 entry。为避免在 validation 救参，本批次只在 development 内部切分做首次受治理搜索，再将每资产唯一胜出参数在原 validation 一次评估；locked historical evaluation 不运行。

## Inner split

- BTC/ETH：inner train 至 2022-12-31；inner evaluation 为 2023；
- HYPE：inner train 至 2025-08-31；inner evaluation 为 2025-09-01 至 2025-10-31；
- label/campaign boundary purge 14d。

## Search space

- onset：4/12/24h；
- development continuation-probability quantile：0.60/0.75/0.90；
- min pullback：0.25/0.50/0.75 ATR；
- max retrace：40/50/60%；
- restart lookback：1/2/4 closed 15m；
- structure stop buffer：0.25/0.50/1.00 ATR；
- wait 24h、no-new-required 2 固定。

每资产用固定 seed 从 Cartesian space 选 60 个组合，并强制包含用户 anchor。不是直到成功为止的自适应搜索。

## Probe-only executable audit

- one position per asset；overlap signals ignored；
- next 15m open adverse fill；真实 fee 10bps、slippage 4bps、funding；
- structure stop；24h 未 +1R validation exit；336h timeout；无固定 TP；
- 每 campaign risk 0.25%；逐笔复利；
- 同 bar 顺序冻结为：已持仓 funding settlement、gap stop、intrabar stop、scheduled validation/timeout；entry bar 不计该时点 funding，因为 next-open entry 排在 settlement 之后；同一 exit bar 不允许再次入场；
- quantity 由完整 stop-out loss 换算并受 `3x` effective leverage cap 约束；cap 导致的风险不足不得伪装成已用满 0.25%；
- MDD 至少按每根 15m close liquidation value 盯市，并另报 bar 内 adverse extreme 相对既有 peak 的保守回撤；
- 搜索排名为 inner-evaluation net log growth，任一盯市 MDD >20%、交易数不足、杠杆越界或风险越界均不可选。

每资产只选择一个参数组合，在原 validation 一次评估。Validation 失败后不得用同一批次重新搜索。
