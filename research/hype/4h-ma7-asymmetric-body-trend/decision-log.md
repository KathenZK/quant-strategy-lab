# Decision Log

## 2026-08-05 — 日线 V1 迁移至 4H

决定：建立独立 `HYPE-4H-MA7-Asymmetric-Body-Trend` 家族，同时审计日线 V1 数字直接转为 4H bar 和仅保持 max-hold/cooldown 日历时间两种合同；两者 combined 分别为 `-67.72% / -2.61%`，后者在 `8 bps`、额外延迟、相位、short-only 和超额收益上均失败，因此保持 `explore / not promoted / not live-ready`，不登记版本、不继续迁移日线参数。证据：[迁移合同](specs/hype-4h-ma7-source-v1-transfer-contract-2026-08-05.md) · [迁移诊断](diagnostics/hype-4h-ma7-source-v1-transfer-2026-08-05.md)。

## 2026-08-06 — 原生 4H MA7 趋势搜索

决定：固定 `SMA7/ATR7` 搜索原生 4H 趋势状态机；合同纠错后冻结候选在 selection prefit / locked base / locked `8 bps` 为 `+284.22% / +10.23% / +7.55%`，但 locked 少于持有 `35.37` 个百分点、额外延迟转为 `-4.28%`，相位比例/CV 也失败，因此只保留有前景的历史观察值，不认定为合适策略、不登记版本，并停止在已打开 locked 历史上继续挑参。证据：[搜索合同](specs/hype-4h-ma7-native-trend-search-contract-2026-08-06.md) · [搜索诊断](diagnostics/hype-4h-ma7-native-trend-search-2026-08-06.md)。
