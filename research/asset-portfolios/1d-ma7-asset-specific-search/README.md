# Binance-1D-MA7-Asset-Specific-Search

- Alias：`BIN-1D-MA7-AS-SEARCH`
- 市场/周期：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual，UTC `1d`；`HYPEUSDT` 与美股价格指数仅作共享参数零调参 control
- 机制：固定 `SMA7/ATR7`，分别搜索 BTC、ETH 多空状态机，并选择一组 BTC/ETH 共享参数
- 当前状态：`explore / not promoted / not live-ready`

本家族承接零调参迁移失败后的用户指定 target-asset search；它不是原迁移家族的版本升级，所有历史均已揭示，不产生 clean OOS 或登记版本。

## 入口

- [主账](binance-1d-ma7-as-search-core-ledger.md)
- [决策记录](decision-log.md)
- [冻结搜索合同](specs/binance-btc-eth-1d-ma7-search-contract-2026-08-05.md)
- [搜索与诊断报告](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md)
- [共享参数应用于 HYPE](diagnostics/binance-ma7-shared-params-on-hype-2026-08-05.md)
- [共享参数应用于 S&P 500 / Nasdaq Composite](../../us-indexes/1d-ma7-shared-parameter-transfer/diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md)
- [复现脚本](scripts/search_binance_btc_eth_1d_ma7_asset_specific.py)
- [机器证据](artifacts/README.md)
