# BIN-1H-CSLGBM 决策日志

- 2026-07-17：建立独立家族 `Binance-1H-Cross-Sectional-LightGBM-Selector`。本地现有 Binance perpetual `1h` 数据仅覆盖 BTC/ETH/SOL/BNB/TRX/HYPE 六币，不能代表全市场；决定先枚举 Binance Vision 历史 USDT perpetual 合约并补齐数据，再做因子和模型。锁定 `2026-04-01 00:00 <= ts < 2026-07-01 00:00 UTC` 为最近三个完整月 OOS；该窗口不得参与因子、模型、阈值或组合选择。研究状态保持 `explore / not promoted / not live-ready`。
- 2026-07-17：官方历史清单确认 793 个合约历史并集、139 个历史退市/移出当前清单合约，三类月归档共 58,719 个 ZIP。全量 checksum 同步开始后，重叠对拍发现旧 CCXT 文件的 `quote_volume`、`trade_count` 和 taker 字段不可信；规定 OHLC 必须与 Vision 一致，成交量结构字段以官方 Vision 修复并保留旧 source。详见[数据清单诊断](diagnostics/binance-usdm-history-inventory-2026-07-17.md)。
