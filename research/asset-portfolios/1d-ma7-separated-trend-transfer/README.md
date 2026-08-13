# Binance-1D-MA7-Separated-Trend-Transfer

- Alias：`BIN-1D-MA7-ST-XFER`
- 市场/周期：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual，UTC `1d`
- 机制：把 HYPE 第 `041` 组固定 `SMA7` 多空分离 reclaim / 迟滞退出参数，以及后续 `HYPE-1D-MA7-ABT-V6` / `PEHC_294`，零调参迁移到 BTC、ETH。
- 当前状态：`explore / not promoted / not live-ready`；V1 组合直迁失败，short-only 仅保留诊断观察；V6 迁移共同窗口和近期切片不成立。

## 边界

- 本家族只回答 HYPE 参数能否原样跨资产迁移，不在 BTC/ETH 已揭示历史上重新搜索参数。
- 它不是无订单的 `BIN-1D-MA7DC`，也不是 MA7/MA30 加仓迁移家族。

## 入口

- [主账](binance-1d-ma7-st-xfer-core-ledger.md)
- [决策记录](decision-log.md)
- [冻结迁移合同](specs/binance-1d-ma7-separated-trend-transfer-contract-2026-08-05.md)
- [BTC/ETH 迁移诊断](diagnostics/binance-1d-ma7-separated-trend-transfer-2026-08-05.md)
- [HYPE V6 迁移诊断](diagnostics/binance-1d-ma7-abt-v6-transfer-btc-eth-2026-08-10.md)
- [研究脚本](scripts/research_binance_1d_ma7_separated_trend_transfer.py)
- [V6 迁移脚本](scripts/research_binance_1d_ma7_abt_v6_transfer.py)
- [机器证据](artifacts/README.md)
