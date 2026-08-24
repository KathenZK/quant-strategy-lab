# BIN-1D-MA7-ALTA 决策记录

## 2026-08-10 — 以未见时间窗终局审计 maturity substrate

QUML 已证明 pooled historical ranking、absolute/quantile calibration 与 inner 选择均不可迁移；决定不补第三组历史资产，而在 outcome 尚未读取的 `2025-05-31` 后时间窗先检验 `take_all`，并只保留一个无网格 asset-local fixed policy 对照。详见 [P0/P1 合同](specs/binance-1d-ma7-alta-p0-p1-contract-2026-08-10.md) 与 [QUML 失败诊断](../1d-ma7-quantile-utility-meta-label/diagnostics/binance-1d-ma7-quml-p1-development-2026-08-10.md)。

## 2026-08-10 — 未见时间窗证伪 maturity substrate

21 资产 `1,341` 个未见事件的 `take_all` mean `-0.1207%`、PF `0.829`，asset×90d bootstrap 正概率仅 `0.16%`且95%区间全负；固定 asset-local policy 更差。决定按合同关闭同一 maturity event 定义上的 selector/threshold/model 搜索，local 相对少亏不得解释成 alpha，HYPE 继续锁定。详见 [P1 诊断](diagnostics/binance-1d-ma7-alta-p1-temporal-audit-2026-08-10.md)。

## 2026-08-10 — 收窄 ALTA 终局解释

QUML 后续复核为 invalidated evidence，不改变 ALTA 在此前未读时间窗上的 `take_all` 结果；但 ALTA 只证伪无条件 substrate edge。按合同关闭已揭示数据上的同 substrate 调参继续有效，不能外推成 OI/flow 等所有未来独立信息均无效；详见 [ALTA诊断](diagnostics/binance-1d-ma7-alta-p1-temporal-audit-2026-08-10.md) 与 [QUML更正](../1d-ma7-quantile-utility-meta-label/diagnostics/binance-1d-ma7-quml-p1-development-2026-08-10.md)。
