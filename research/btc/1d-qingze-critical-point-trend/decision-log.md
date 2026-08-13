# Decision Log

## 2026-08-07 — 参数搜索锁定验证

结论：20,000 组参数的 development rank 1 从 `+21.94%` 衰减到锁定 validation `-0.55%`，且收益集中于少数 A 类大趋势单；判定 holdout failed，不登记、不事后改选 validation 更好的候选，当前 validation 此后视为已暴露。

证据：[搜索合同](specs/btc-1d-qz-cpt-parameter-search-contract-2026-08-07.md) · [搜索与验证诊断](diagnostics/btc-1d-qz-cpt-parameter-search-validation-2026-08-07.md) · [机器摘要](artifacts/btc_1d_qingze_parameter_search_summary_2026-08-07.json)

## 2026-08-07

结论：把用户提供的青泽方法操作化为 BTC 日线诊断后，SMA60 基线仅录得 `+0.88%`、MDD `-13.38%` 和 11 笔交易，且 B 类信号为 0；由于 20 日持仓量过滤器缺少历史覆盖，本结果不算完整还原，不登记版本、不推进 promotion。

证据：[基线合同](specs/btc-1d-qz-cpt-baseline-contract-2026-08-07.md) · [回测诊断](diagnostics/btc-1d-qz-cpt-baseline-2026-08-07.md) · [机器摘要](artifacts/btc_1d_qingze_critical_point_summary_2026-08-07.json)
