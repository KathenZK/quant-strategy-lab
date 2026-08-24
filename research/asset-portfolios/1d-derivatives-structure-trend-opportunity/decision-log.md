# BIN-1D-DSTO 决策记录

## 2026-08-10 — 从稀疏 maturity event 改为每日全锚点

DSML 失败来自官方 metrics 与稀疏 LMML events 的交集不足，而不是 derivatives information 已被经济检验否定；决定保留同一官方独立信息源，彻底删除 MA7 root，改用共同覆盖期每日全锚点和固定 5 日 long/flat/short 结果，以约六千样本完成 strict OOF full-versus-price-control。HYPE 继续锁定；详见 [P0/P1 合同](specs/binance-1d-dsto-p0-p1-contract-2026-08-10.md) 与 [DSML P0 诊断](../1d-ma7-derivatives-structure-meta-label/diagnostics/binance-1d-ma7-dsml-p0-capacity-2026-08-10.md)。

## 2026-08-10 — 原 full-field P0 因官方源内容缺陷失败

6,385 个日包身份完整但 positioning/taker 大段 null，另有缺行、错位与重复 timestamp，决定原合同 fail closed；在未读取 label/收益时冻结只接受精确 OI 端点并叠加已审计 funding 的 P0R，详见 [源质量诊断](diagnostics/binance-1d-dsto-p0-source-quality-2026-08-10.md) 与 [P0R 合同](specs/binance-1d-dsto-p0r-oi-funding-contract-2026-08-10.md)。

## 2026-08-10 — 原 OI + Funding P1 裁决（后续撤回）

P0R 通过但 full OOF 亏损、覆盖不足，且相对 price control 的 utility delta bootstrap 通过概率仅 `0.24%`；决定不保存模型、不读取 HYPE，并关闭本 family 的 fixed-5d OI/funding 路线，详见 [P1 失败诊断](diagnostics/binance-1d-dsto-p1-oi-funding-development-2026-08-10.md)。

## 2026-08-10 — 撤回 P1 增量裁决

复核发现 market aggregate 在 held-asset split 前预计算，且五资产 inner fold 只能留下2 peers、无法满足冻结`>=3`；因此撤回“OI/funding 负增量”的裁决，将 P1 标记为 invalidated evidence 并让脚本 fail closed。已揭示历史不得修后重称 OOS；详见 [P1 复核更正](diagnostics/binance-1d-dsto-p1-oi-funding-development-2026-08-10.md)。
