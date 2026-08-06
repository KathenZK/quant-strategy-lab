# Decision Log

## 2026-08-05

决定：把已登记的 `HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 零调参迁移至 Yahoo `^SOX`；全历史 combined 在零成本下仍为 `-36.29%`、MDD `-76.58%`，长期超额与滚动稳定性失败。保持 `explore / not promoted / not live-ready`，不登记 SOX 版本、不在已揭示历史上调参；若改用 SOXX 或衍生品，另建可交易家族。证据：[全历史诊断](diagnostics/sox-1d-ma7-v1-transfer-2026-08-05.md) · [迁移合同](specs/sox-1d-ma7-v1-transfer-contract-2026-08-05.md) · [机器摘要](artifacts/sox_1d_ma7_v1_transfer_summary_2026-08-05.json)。

## 2026-08-05 — SMA5 替换

决定：保持 ATR7 与 V1 状态机不变、只把 SMA7 换成 SMA5 后，全历史 combined 从 `-36.29%` 改善至 `-11.73%`，但 MDD 仍为 `-74.45%`，示意 `10 bps/fill` 后为 `-61.81%`，short-only 为 `-83.55%`；继续保持 `explore / not promoted / not live-ready`，不登记、不搜索更多 SMA 长度。证据：[SMA5 诊断](diagnostics/sox-1d-sma5-substitution-2026-08-05.md)。

## 2026-08-05 — 后续专属搜索分家

决定：用户后续明确要求的 BTC/ETH 共享参数控制与 SOX 专属 MA7 搜索不改写本零调参家族，建立独立 `SOX-1D-MA7-Asset-Specific-Search` 家族；该搜索找到绝对正收益但未解决长期超额与稳定性。证据：[后续搜索诊断](../1d-ma7-asset-specific-search/diagnostics/sox-1d-ma7-asset-specific-search-2026-08-05.md)。
