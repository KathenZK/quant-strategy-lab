# CSI300-1D-HYPE-MA7-V7.1-Transfer

- Alias：`CSI300-1D-HM7-XFER`
- 市场/周期：沪深 300 价格指数 `000300`，上海/深圳常规交易 session `1d`
- 机制：把 `HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1` 固定参数零调参迁移到沪深 300 日 K；止损、forced short 与 PEHC 使用日 OHLC 适配。
- 当前状态：`explore / not promoted / not live-ready`；四年零成本仅略高于指数买持，`10 bps/fill` 后显著失去超额，近期 `3m/6m/1y` 均亏损，裁决 `TRANSFER_FAIL`。

## 边界

- `000300` 是不可直接下单的价格指数；本研究不是 `510300` ETF、`IF` 股指期货或 total-return index。
- 只有日 K，不能恢复 V7.1 原版 `1h` 保护与 PEHC 的盘中先后；结果是迁移诊断，不是 exact parity。
- 东方财富数据保持 `raw_unaccepted`，不得支持版本登记、promotion 或 live-ready 结论。

## 入口

- [主账](csi300-1d-hm7-xfer-core-ledger.md)
- [决策记录](decision-log.md)
- [零调参迁移合同](specs/csi300-1d-hype-ma7-v7-1-transfer-contract-2026-08-17.md)
- [四年回测诊断](diagnostics/csi300-1d-hype-ma7-v7-1-transfer-2026-08-17.md)
- [复现脚本](scripts/research_csi300_1d_hype_ma7_v7_1_transfer.py)
- [机器证据](artifacts/README.md)
