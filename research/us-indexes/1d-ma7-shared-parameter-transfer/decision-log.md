# Decision Log

## 2026-08-05

决定：把 BTC/ETH 共享日线 `SMA7/ATR7` 参数零调参应用于 Yahoo `^GSPC` 与 `^IXIC`。S&P 500 / Nasdaq Composite 全历史 combined 分别为 `+18.77%/+91.43%`，但 `10 bps/fill` 后为 `-48.26%/-12.38%`，且远逊各自 buy-and-hold；两者 short-only 都长期亏损。保持 `explore / not promoted / not live-ready`，不登记、不依据指数结果调参。证据：[诊断报告](diagnostics/us-indexes-1d-ma7-shared-parameter-transfer-2026-08-05.md) · [迁移合同](specs/us-indexes-1d-ma7-shared-parameter-transfer-contract-2026-08-05.md) · [机器摘要](artifacts/us_indexes_1d_ma7_shared_parameter_transfer_summary_2026-08-05.json)。
