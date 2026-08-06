# BTC-1W-MA7-Asymmetric-Body-Trend

- Full family name：`BTC-1W-MA7-Asymmetric-Body-Trend`
- Alias：`BTC-1W-MA7-ABT`
- Market：Binance USD-M `BTCUSDT` perpetual
- Timeframe：anchored `1w`；主相位周一 `00:00 UTC`
- Mechanism：把 `HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 的 SMA7/ATR7 多空状态机零调参迁移至周 K
- Status：`explore / not promoted / not live-ready`；direct transfer 已判定失败

本家族是独立周线诊断，不是 BTC 日线迁移的升级，也不继承 HYPE V1 的登记或 live-readiness。

## 入口

- [主账](btc-1w-ma7-abt-core-ledger.md)
- [决策记录](decision-log.md)
- [周线迁移合同](specs/btc-1w-ma7-v1-transfer-contract-2026-08-05.md)
- [回测诊断](diagnostics/btc-1w-ma7-v1-transfer-2026-08-05.md)
- [产物说明](artifacts/README.md)
- [复现脚本](scripts/research_btc_1w_ma7_v1_transfer.py)
