# BIN-1D-MA7-BPML 决策记录

## 2026-08-10 — 以长历史 Basis/Premium 重返冻结 Maturity Target

LMML 的局部价格 snapshot 无稳定排序，DSML 的 positioning/taker 官方历史不足，DSTO 的 OI+funding 又在充足 daily anchors 上显著落后 price control；决定使用从 2020 年起完整可列出的官方 premium/mark/index `1h` 月包，回到冻结 `1,448` 个 LMML 事件检验拥挤度增量。合同在完整下载和经济结果前冻结，HYPE 继续锁定；详见 [P0/P1 合同](specs/binance-1d-ma7-bpml-p0-p1-contract-2026-08-10.md)。

## 2026-08-10 — Basis 结果前按冻结 Event 结构校准 Lag Stress 容量

冻结 events 仅 `79.70%` 存在仍早于原 exit 的 `z_lag1`，缺失来自一日后 probe 已结束而非 basis 数据缺口；在未读取 basis 或模型经济结果时，把 lag 可执行率门从机制上不可能的 `90%` 改为 `75%`，其 mean/PF 门不变，详见 [P0/P1 合同](specs/binance-1d-ma7-bpml-p0-p1-contract-2026-08-10.md)。

## 2026-08-10 — 官方单根缺口改为逐 Event Fail-Closed

948 个官方月包身份下载完成后、读取 label 或模型结果前，发现 BTC premium `2020-12-01 23:00 UTC` 原包缺一根；决定保留缺口事实并把 gapful 拼接降为 cache，禁止补值，改由每个 target/peer event 的连续 `744h` 窗口逐项准入，原 P0 容量门不降低，详见 [P0/P1 合同](specs/binance-1d-ma7-bpml-p0-p1-contract-2026-08-10.md)。

## 2026-08-10 — 原 30 日 P0 失败并冻结 14 日 P0R

逐 event `744h` 准入只保留 `1,233/1,448（85.15%）`，原 `>=1,300 / >=90%` 门失败且未运行模型；source-only 预审显示连续 14 日 reference 可保留 `1,335（92.20%）`、每资产 `>=227`、多空 `718/617`，因此在不降低原容量门且未读取 outcome 时冻结 P0R，详见 [P0R 合同](specs/binance-1d-ma7-bpml-p0r-14d-basis-contract-2026-08-10.md) 与 [原容量证据](artifacts/p0_data_2026-08-10/p0_original_30d_capacity.json)。

## 2026-08-10 — Basis/Premium P1 失败并关闭 Maturity Meta-Label

P0R 通过，但 full `19/20` folds 无合格 inner choice、唯一 OOF trade `-1.5633%`，basis-only/control 均 `20/20 NO_SELECTION`，full-control bootstrap `P(Δutility>0)=0`；决定不保存模型、不读取 HYPE，并关闭本 family，详见 [P0/P1 失败诊断](diagnostics/binance-1d-ma7-bpml-p1-development-2026-08-10.md)。

## 2026-08-10 — 修正空仓双改善与单 Fold Importance 口径

初版汇总会把零交易相对负 baseline 计作 dual-improvement，并让单 fold permutation 满足 importance；已把 dual-improvement 增加每资产至少 15 笔约束、importance 增加至少 15 folds 约束后重生成证据，P1 结论不变，见 [最终 summary](artifacts/p1_development_2026-08-10/p1_summary.json)。
