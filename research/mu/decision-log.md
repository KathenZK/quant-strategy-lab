# MU-HYPE-XFER 决策日志

## 2026-08-05 — 股票数据并入统一 raw OHLCV

Polygon/Yahoo MU 股票数据按 NASDAQ/equity/source 身份迁入统一 raw OHLCV，并删除旧 `data/external`；因标准字段、闭合状态、交易 session 和一条 Yahoo 非网格时间戳仍未审计完成，统一保持 `raw_unaccepted`，不得支持登记或 promotion。证据见 [`mu-equity-ohlcv-migration-2026-08-05.md`](diagnostics/mu-equity-ohlcv-migration-2026-08-05.md)。

## 2026-07-20 — V14 最新数据未确认前向有效性

补齐 Binance MUUSDT 15m 数据并修正 funding、费用、跳空止损和同 K TP/SL 口径后，V14 严格 ALL 为 `+198.53% / -29.46%`，但原截止点后的自然前向段为 `-4.83% / -18.16%` 且仅 2 笔；维持 `explore / not promoted / not live-ready`，不登记、不交接 runner。证据见 [`mu-hype-xfer-v14-latest-validity-2026-07-20.md`](diagnostics/mu-hype-xfer-v14-latest-validity-2026-07-20.md)。
