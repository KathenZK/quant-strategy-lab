# US-Indexes-1D-MA7-Shared-Parameter-Transfer

- Alias：`USI-1D-MA7-SP-XFER`
- 市场/周期：Yahoo `^GSPC` S&P 500 与 `^IXIC` Nasdaq Composite，America/New_York session `1d`
- 机制：把 BTC/ETH 搜索冻结的共享 `SMA7/ATR7` 多空状态机原样应用于两个美股价格指数。
- 当前状态：`explore / not promoted / not live-ready`；零成本 combined 为正但无超额，示意成本后均失败。

## 边界

- 两个序列都是不可直接交易的 price index；不是 SPY、QQQ、期货、期权或 total-return index。
- 本家族只做零调参迁移，不根据美股指数结果调整参数。

## 入口

- [主账](us-indexes-1d-ma7-sp-xfer-core-ledger.md)
- [决策记录](decision-log.md)
- [迁移合同](specs/us-indexes-1d-ma7-shared-parameter-transfer-contract-2026-08-05.md)
- [诊断报告](diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md)
- [复现脚本](scripts/audit_us_indexes_1d_ma7_shared_params.py)
- [机器证据](artifacts/README.md)
