# SOX-1D-MA7-Asset-Specific-Search

- Alias：`SOX-1D-MA7-AS-SEARCH`
- 市场/周期：Yahoo Finance `^SOX` PHLX Semiconductor price index，交易所 session `1d`
- 机制：先零调参测试 BTC/ETH 共享 SMA7 参数；失败后固定 `SMA7/ATR7` 搜索 SOX 专属多空参数。
- 当前状态：`explore / not promoted / not live-ready`；MA7 搜索找到绝对正收益候选，MA20 零调参替换改善跨年代回撤但仍无长期超额。

## 边界

- `^SOX` 是不可直接交易的价格指数；本研究不是 SOXX ETF、期货或期权回测。
- 2021+ 后段未参与本次选择，但 SOX 历史此前已被研究，只能称 researcher-exposed holdout。

## 入口

- [主账](sox-1d-ma7-as-search-core-ledger.md)
- [决策记录](decision-log.md)
- [搜索合同](specs/sox-1d-ma7-asset-specific-search-contract-2026-08-05.md)
- [诊断报告](diagnostics/sox-1d-ma7-asset-specific-search-2026-08-05.md)
- [MA20 零调参替换诊断](diagnostics/sox-1d-ma20-substitution-2026-08-05.md)
- [复现脚本](scripts/search_sox_1d_ma7_asset_specific.py)
- [机器证据](artifacts/README.md)
