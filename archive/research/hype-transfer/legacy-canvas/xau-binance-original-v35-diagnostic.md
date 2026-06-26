# XAUUSDT 原版 HYPE V35 诊断

> 迁移说明：本文由 legacy Cursor Canvas `xau-binance-original-v35-diagnostic.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Cross-asset / transfer legacy Canvas。

使用 Binance XAUUSDT 15m 数据直接跑原版 HYPE V35：long+short、动态仓位、TP5/SL7、ADX/timeout 退出。

Source: Binance FAPI · 2026-04-01 00:00 UTC → 2026-06-18 07:45 UTC · 7,520 bars · warmup 后从 2026-04-17 16:00 UTC 开始。

> **结论**
> 原版 V35 在 XAU 上仍是亏损，但显著跑赢同窗口买入持有。和 MU/SKHYNIX 不同，XAU 的空头有正贡献：10 笔 short 合计 +3.40%，胜率 60%。

## 结果对照

| 版本 | 收益 | MDD | 交易 | 胜率 | TP / SL / 指标退出 | 多空贡献 |
| --- | --- | --- | --- | --- | --- | --- |
| B0 原版 HYPE V35 | -5.42% | -7.96% | 18 | 55.56% | 10 / 4 / 4 | long +0.24%，short +3.40% |
| B0w 原版去周末 | -4.00% | -7.96% | 17 | 58.82% | 10 / 4 / 3 | long +1.09%，short +3.40% |
| B&H 同窗口买入持有 | -11.83% | -17.17% | - | - | - | XAU 同窗口下跌 |

## 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/fetch_binance_perp_symbol_data.py | Binance FAPI 分页下载脚本 |
| data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/date=2026-04-01/symbol=xau_usdt_usdt.parquet | XAUUSDT 15m OHLCV |
| data/normalized/funding_rates/exchange=binance/market_type=perp/date=2026-04-01/symbol=xau_usdt_usdt.parquet | XAUUSDT funding |
| archive/reports/legacy/xau_binance_hype_v35_original_summary.json | 原版 HYPE V35 诊断摘要 |
| archive/reports/legacy/xau_binance_hype_v35_original_trades.csv | 原版 HYPE V35 交易明细 |
