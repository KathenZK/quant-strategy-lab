# BIN-1H-MA7-RHT 决策记录

## 2026-08-10 — 从 maturity snapshot 转入逐小时 root timing

LMML 已证明单个 maturity 日快照没有跨资产排序能力；决定保留 daily soft MA7 cross 作为 root prior，但删除 buffer/slope maturity 门，改为 120 小时内逐根闭合 K 的 root-grouped landmark 与 first-hit 入场。HYPE 继续锁定；合同见 [P0/P1 非 HYPE hazard 合同](specs/binance-1h-ma7-rht-p0-p1-contract-2026-08-10.md)，前驱证据见 [LMML P1 失败诊断](../1d-ma7-later-maturity-meta-label/diagnostics/binance-1d-ma7-lmml-p1-development-2026-08-10.md)。

## 2026-08-10 — P1 反向排序，关闭 daily MA7 root prior

严格 OOF 仅接受 30 个 roots，主结果为负，root 内 probability/return 中位 Spearman `−0.406`，且 first-hit 相对同 root 立即入场平均少 `3.663pp`；决定按预冻结失败转向停止本家族，不解锁 HYPE。证据见 [P1 development 失败诊断](diagnostics/binance-1h-ma7-rht-p1-development-2026-08-10.md) 与 [机器产物](artifacts/README.md)。
