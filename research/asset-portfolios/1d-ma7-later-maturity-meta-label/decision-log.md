# BIN-1D-MA7-LMML 决策记录

## 2026-08-10 — 另立 later-maturity meta-label 家族

决定不把 HYPE V6 的 fixed-rule probe 失败当作终点，也不在已 `HARD-GATE-FAILED` 的 DAPML 标签上继续微调。新研究线改为预测 V6-style root 成熟后的直接成本后 probe 经济性，训练与选择仅使用 HYPE 上线前的 BTC/ETH/BNB/SOL/TRX；详见 [P0/P1 合同](specs/binance-1d-ma7-lmml-p0-p1-contract-2026-08-10.md) 与 [原始失败归因](../../hype/1d-ma7-asymmetric-body-trend/diagnostics/hype-1d-ma7-v6-missed-trend-attribution-2026-08-10.md)。

## 2026-08-10 — P1 pooled maturity snapshot 失败且 HYPE 保持锁定

1,448 个事件的 nested LOAO/time 结果只有 2/5 资产和 10/20 外层折为正，Spearman `−0.003`、cluster bootstrap `61.78%`；决定不保存模型、不读取 HYPE，并转入 materially new 的逐小时 root hazard timing。证据见 [P1 失败诊断](diagnostics/binance-1d-ma7-lmml-p1-development-2026-08-10.md)。
