# Binance-1D-MA7-Asset-Specific-Search

- Alias：`BIN-1D-MA7-AS-SEARCH`
- 市场/周期：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual，UTC `1d`；`HYPEUSDT` 与美股价格指数仅作共享参数零调参 control
- 机制：固定 `SMA7/ATR7`，分别搜索 BTC、ETH 多空状态机，并选择一组 BTC/ETH 共享参数
- 当前状态：`V1 registered / not promoted / not live-ready`

本家族承接零调参迁移失败后的用户指定 target-asset search；它不是原迁移家族的版本升级，所有历史均已揭示，不产生 clean OOS。`V1` 只登记 BTC/ETH shared 参数身份，不代表 HYPE 可迁移或 runner 授权。

## 入口

- [主账](binance-1d-ma7-as-search-core-ledger.md)
- [决策记录](decision-log.md)
- [冻结搜索合同](specs/binance-btc-eth-1d-ma7-search-contract-2026-08-05.md)
- [V1规格](specs/binance-1d-ma7-as-search-v1-spec.md)
- [搜索与诊断报告](diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md)
- [平多即反手空合同](specs/binance-ma7-long-exit-short-reversal-contract-2026-08-06.md)与[诊断](diagnostics/binance-ma7-long-exit-short-reversal-2026-08-06.md)
- [共享参数应用于 HYPE](diagnostics/binance-ma7-shared-params-on-hype-2026-08-05.md)
- [共享参数对齐 HYPE fresh 窗口复算](diagnostics/binance-ma7-shared-params-on-hype-fresh-aligned-2026-08-12.md)
- [共享参数在 BTC/ETH 的 HYPE 对齐窗口复算](diagnostics/binance-ma7-shared-params-btc-eth-hype-aligned-2026-08-12.md)
- [BTC/ETH策略最近1至4年横向排名](diagnostics/binance-btceth-recent-horizon-ranking-2026-08-13.md)
- [共享参数应用于 S&P 500 / Nasdaq Composite](../../us-indexes/1d-ma7-shared-parameter-transfer/diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md)
- [复现脚本](scripts/search_binance_btc_eth_1d_ma7_asset_specific.py)
- [机器证据](artifacts/README.md)
- [BTC V1交易路径](artifacts/binance_ma7_shared_params_v1_btc_trade_path_2026-08-12.html)
- [ETH V1交易路径](artifacts/binance_ma7_shared_params_v1_eth_trade_path_2026-08-12.html)
