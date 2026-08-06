# Decision Log

## 2026-08-05 — 日线 V1 迁移至 4H

决定：建立独立 `HYPE-4H-MA7-Asymmetric-Body-Trend` 家族，同时审计日线 V1 数字直接转为 4H bar 和仅保持 max-hold/cooldown 日历时间两种合同；两者 combined 分别为 `-67.72% / -2.61%`，后者在 `8 bps`、额外延迟、相位、short-only 和超额收益上均失败，因此保持 `explore / not promoted / not live-ready`，不登记版本、不继续迁移日线参数。证据：[迁移合同](specs/hype-4h-ma7-source-v1-transfer-contract-2026-08-05.md) · [迁移诊断](diagnostics/hype-4h-ma7-source-v1-transfer-2026-08-05.md)。
