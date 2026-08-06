# HYPE-4H-MA7-Asymmetric-Body-Trend

- Alias：`HYPE-4H-MA7-ABT`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `4h`
- 机制：把日线 V1 的固定 `SMA7/ATR7` 非对称 reclaim、迟滞退出和保护状态机零调参迁移到 4 小时。
- 当前状态：`explore / not promoted / not live-ready`；bar-transfer 与 clock-equivalent 均失败。

## 边界

- 这是独立 4H 家族，不是 `HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 的新版本。
- 不与 `HYPE-4H-Bollinger-Keltner-Squeeze-Breakout`、`HYPE-6H-RS4-Regime-Switch` 或其他 HYPE 趋势家族共享版本号。
- 当前结果是已揭示历史的 direct-transfer diagnostic，不是 OOS。

## 入口

- [主账](hype-4h-ma7-abt-core-ledger.md)
- [决策记录](decision-log.md)
- [迁移合同](specs/hype-4h-ma7-source-v1-transfer-contract-2026-08-05.md)
- [迁移诊断](diagnostics/hype-4h-ma7-source-v1-transfer-2026-08-05.md)
- [复现脚本](scripts/research_hype_4h_ma7_v1_transfer.py)
- [机器证据](artifacts/README.md)
