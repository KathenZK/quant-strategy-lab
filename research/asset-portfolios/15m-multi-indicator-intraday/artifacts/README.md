# Artifacts（已清理）

本目录的中间产物与大体积数据已于 2026-08-04 磁盘清理时删除。
研究结论与版本身份以家族 README、core ledger、diagnostics、specs 与 decision-log 为准；需要复现时用 scripts/ 从数据湖重建。

---

# 研究产物

本目录保存 `Binance-15M-Multi-Indicator-Intraday-Transfer` 被诊断报告引用、或复现结论所需的 JSON/CSV 证据。

## 保留证据

- `binance_15m_mii_btc_eth_constrained_search_2026-06-30.json`：BTC/ETH 受约束微调搜索摘要、数据质量、搜索空间和 Top finalists。
- `binance_15m_mii_btc_eth_constrained_search_ranking_2026-06-30.csv`：完整 Stage1 asset-config 排名，共 `69,122` 行。
- `binance_15m_mii_btc_eth_constrained_search_finalists_2026-06-30.csv`：每个资产 Top `250` 配置的全样本、前后半段、Last90 和最近 30 天综合结果。
- `binance_15m_mii_btc_eth_constrained_search_slices_2026-06-30.csv`：finalists 的 K+1/K+2 分窗口明细。
