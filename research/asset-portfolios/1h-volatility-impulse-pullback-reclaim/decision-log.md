# BIN-1H-VIPR 决策记录

## 2026-08-10 — 更换 root 来源与经济目标

LMML 与 RHT 已分别否定 daily MA7 maturity snapshot 和逐小时 first-hit；决定按 RHT 预冻结失败转向，改用原生 `1h` volatility-normalized impulse/breakout root、显式 pullback/reclaim 与固定 bracket/timeout，并在揭示结果前冻结八个透明配置和近一年 holdout。证据见 [RHT P1 失败诊断](../1h-ma7-root-hazard-timing/diagnostics/binance-1h-ma7-rht-p1-development-2026-08-10.md) 与 [P0/P1 合同](specs/binance-1h-vipr-p0-p1-contract-2026-08-10.md)。

## 2026-08-10 — 八配置全资产失败，holdout 不揭示

八配置虽有 1,561–3,618 笔 development 成交，但 mean 全负、PF 仅 `0.645–0.720`，五资产和全部 180 日块均无正结果；决定按合同停止本机制，保留 locked holdout 未揭示，下一轮只允许引入 OI/positioning/taker/basis 等独立信息。证据见 [P1 development 失败诊断](diagnostics/binance-1h-vipr-p1-development-2026-08-10.md)。
