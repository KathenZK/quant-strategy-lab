# BIN-1D-MA7-TFML 决策记录

## 2026-08-10 — 从 Binary Maturity Selector 转入原生 Taker-Flow Expected Utility

BPML 证明 public basis 不能让 binary maturity classifier 稳定选出经济事件，后验无条件 OOF 还显示 classification AUC 与收益排序错位；决定保留冻结 event/outcome，改用未被既有实验覆盖的原生 5m taker-buy quote flow，并直接回归 `z_8bps`，以相同 Ridge price control 隔离 flow 增量，详见 [P0/P1 合同](specs/binance-1d-ma7-tfml-p0-p1-contract-2026-08-10.md)。

## 2026-08-10 — 五资产 Universal Flow P1 失败并禁止 P2/HYPE

Full 171 笔 mean `+0.0997%` / PF `1.187` 且 4/5 资产为正，但仅 `7/20` folds 正、bootstrap `75.80%`、full-control 增量通过概率 `60.88%`，TRX 明显反向；决定不按结果删资产或降门，不保存模型、不运行 P2、不读取 HYPE，详见 [P0/P1 失败诊断](diagnostics/binance-1d-ma7-tfml-p1-development-2026-08-10.md)。

## 2026-08-10 — 用八个未见资产检验异质性而非删除 TRX

在未读取 XRP/DOGE/ADA/LINK/LTC/DOT/AVAX/UNI outcome 前，冻结相同 event/target/features/model/policy，只把旧五资产用于训练、八个 fresh assets 用于 32 个 outer folds；详见 [P0E/P1E 合同](specs/binance-1d-ma7-tfml-p0e-p1e-universe-expansion-contract-2026-08-10.md)。

## 2026-08-10 — 原 Fresh P1E 裁决（后续撤回）

P0E 通过，但 Full mean `-0.0681%` / PF `0.900`，price control mean `+0.1664%` / PF `1.257`，common OOF flow delta `-0.04392%/event` 且 `P(Δ>0)=0.84%`；决定关闭 TFML、不保存模型、不进入 P2/HYPE，详见 [Fresh-Universe 失败诊断](diagnostics/binance-1d-ma7-tfml-p1e-fresh-universe-2026-08-10.md)。

## 2026-08-10 — 撤回 P1/P1E Flow 增量裁决

复核发现 market aggregates 在 held split 前全局预计算；五资产 P1 还因 nested inner 仅剩2 peers而无法满足冻结`>=3`。因此 P1/P1E 均改为 invalidated evidence并fail closed；P0 native-flow容量保留，但P0E price/funding内嵌generator源码未保留，P0E整体另有provenance blocker。撤回flow正/负增量归因，已揭示 outcome 不得修后重称 OOS。证据：[P1 更正](diagnostics/binance-1d-ma7-tfml-p1-development-2026-08-10.md) · [P1E 更正](diagnostics/binance-1d-ma7-tfml-p1e-fresh-universe-2026-08-10.md)。
