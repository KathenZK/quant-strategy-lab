# ASTERUSDT 原版 HYPE V35 诊断

> 迁移说明：本文由 legacy Cursor Canvas `aster-binance-original-v35-diagnostic.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Cross-asset / transfer legacy Canvas。

使用 Binance ASTERUSDT 15m 数据直接跑原版 HYPE V35：long+short、动态仓位、TP5/SL7、ADX/timeout 退出。

Source: Binance FAPI · 2026-04-01 00:00 UTC → 2026-06-18 07:45 UTC · 7,520 bars · warmup 后从 2026-04-17 16:00 UTC 开始。

> **结论**
> 原版 V35 不适合 ASTER。B0 亏损 -39.41%，远差于买入持有 -2.09%；主要拖累来自空头，8 笔 short 合计 -41.34%，胜率只有 12.5%。

## 结果对照

| 版本 | 收益 | MDD | 交易 | 胜率 | TP / SL / 指标退出 | 多空贡献 |
| --- | --- | --- | --- | --- | --- | --- |
| B0 原版 HYPE V35 | -39.41% | -45.35% | 37 | 51.35% | 19 / 13 / 5 | long +19.33%，short -41.34% |
| B0w 原版去周末 | -29.00% | -31.64% | 18 | 50.00% | 9 / 7 / 2 | long +2.16%，short -22.94% |
| B&H 同窗口买入持有 | -2.09% | -23.44% | - | - | - | ASTER 同窗口小幅下跌 |

## 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/fetch_binance_perp_symbol_data.py | Binance FAPI 分页下载脚本 |
| data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/date=2026-04-01/symbol=aster_usdt_usdt.parquet | ASTERUSDT 15m OHLCV |
| data/normalized/funding_rates/exchange=binance/market_type=perp/date=2026-04-01/symbol=aster_usdt_usdt.parquet | ASTERUSDT funding |
| reports/aster_binance_hype_v35_original_summary.json | 原版 HYPE V35 诊断摘要 |
| reports/aster_binance_hype_v35_original_trades.csv | 原版 HYPE V35 交易明细 |
