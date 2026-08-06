# Decision Log

## 2026-08-05 — HYPE 日线 V1 迁移至 BTC 周 K

决定：按用户要求把固定 SMA7/ATR7 多空状态机迁移至 Binance `BTCUSDT` 周 K；bar-transfer 与 clock-equivalent 均为 `-21.72%`、MDD `-29.61%`，long-only / short-only 分别 `-30.82% / -8.38%`，半周相位仍亏损。Direct transfer 判定失败，状态保持 `explore / not promoted / not live-ready`，不登记版本、不在已揭示 BTC 周线历史上调参。证据：[周线诊断](diagnostics/btc-1w-ma7-v1-transfer-2026-08-05.md) · [机器摘要](artifacts/btc_1w_ma7_v1_transfer_summary_2026-08-05.json)。
