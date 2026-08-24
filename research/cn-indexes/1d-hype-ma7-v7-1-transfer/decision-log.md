# Decision Log

## 2026-08-17 — 沪深 300 四年零调参迁移失败

决定：`HYPE-1D-MA7-ABT-V7.1` 日 K 适配在沪深 300 上零成本仅比买持高 `0.18pp`，`10 bps/fill` 后超额降为 `-12.08pp`，且最近 `3m/6m/1y` 均亏损；记为 `TRANSFER_FAIL / explore / not promoted / not live-ready`，不登记版本、不按已揭示数据调参。证据：[四年回测诊断](diagnostics/csi300-1d-hype-ma7-v7-1-transfer-2026-08-17.md) · [机器结果](artifacts/csi300_1d_hype_ma7_v7_1_transfer_2026-08-17.json)。
