# Decision Log

## 2026-08-05

决定：BTC/ETH 共享参数在 SOX 全历史 combined 为 `-2.96%`，依约触发固定 `SMA7/ATR7` 的 SOX 专属搜索；搜索候选虽在 2021+ exposed holdout 为 `+111.06%`、全历史为 `+200.29%`，但 2010 年前为 `-79.36%`、full MDD `-93.47%` 且远逊 buy-and-hold。保留 `explore / not promoted / not live-ready`，不登记版本。证据：[诊断报告](diagnostics/sox-1d-ma7-asset-specific-search-2026-08-05.md) · [搜索合同](specs/sox-1d-ma7-asset-specific-search-contract-2026-08-05.md) · [机器摘要](artifacts/sox_1d_ma7_asset_specific_search_summary_2026-08-05.json)。

## 2026-08-05 — MA20 替换

决定：保持 MA7 development-selected 状态机和 ATR7 不变、只换为 SMA20 后，combined 全历史 `+162.47%`、MDD `-60.62%`，2010 年前由 MA7 的 `-79.36%` 改善为 `+3.78%`；但年化仍约 `3.04%`、远逊 buy-and-hold，且有明显时序敏感性。保留为零调参 observation，不登记、不 promotion。证据：[MA20 诊断](diagnostics/sox-1d-ma20-substitution-2026-08-05.md) · [替换合同](specs/sox-1d-ma20-substitution-contract-2026-08-05.md)。
