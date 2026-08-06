# SOX-1D-MA7-Separated-Trend-Transfer

- Alias：`SOX-1D-MA7-ST-XFER`
- 市场/周期：Yahoo Finance `^SOX` PHLX Semiconductor price index，交易所 session `1d`
- 机制：把 `HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 的固定 SMA7 多空参数零调参迁移到 SOX 指数。
- 当前状态：`explore / not promoted / not live-ready`；全历史 direct transfer 失败。

## 边界

- `^SOX` 是不可直接交易的价格指数；本研究不是 SOXX ETF、期货或期权回测。
- 主结果没有虚构手续费、滑点、借券或融资成本，只能解释为价格路径诊断。

## 入口

- [主账](sox-1d-ma7-st-xfer-core-ledger.md)
- [决策记录](decision-log.md)
- [零调参迁移合同](specs/sox-1d-ma7-v1-transfer-contract-2026-08-05.md)
- [全历史诊断](diagnostics/sox-1d-ma7-v1-transfer-2026-08-05.md)
- [SMA5 零调参替换诊断](diagnostics/sox-1d-sma5-substitution-2026-08-05.md)
- [复现脚本](scripts/research_sox_1d_ma7_v1_transfer.py)
- [机器证据](artifacts/README.md)
