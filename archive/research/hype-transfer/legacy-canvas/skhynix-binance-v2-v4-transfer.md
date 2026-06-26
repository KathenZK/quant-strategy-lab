# SKHYNIXUSDT HYPE V35 Transfer 诊断

> 迁移说明：本文由 legacy Cursor Canvas `skhynix-binance-v2-v4-transfer.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Cross-asset / transfer legacy Canvas。

已从 Binance FAPI 拉取 SKHYNIXUSDT 15m 与 funding。该合约历史很短，当前只有 2026-06-02 之后的数据，因此本页只作为 V2/V4 可迁移性早期诊断。

Source: Binance FAPI · 15m · 2026-06-02 03:00 UTC → 2026-06-18 07:45 UTC · 1,556 bars · warmup 672 bars。

> **结论**
> 当前样本太短，结果不能作为生产判断。初步看，SKHYNIX 这段趋势里直接买入持有为正，但 HYPE V35 transfer 信号追在不好的位置；原版 V35、V2、V4 都亏损，V4 动态仓位只是把亏损压小。

## V2 / V4 对照

| 版本 | 设置 | 收益 | MDD | 交易 | 胜率 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| B0 | 原版 HYPE V35 | -27.13% | -27.13% | 3 | 0.00% | long 3 笔全亏；stop_loss 2 / indicator_exit 1 |
| B0w | 原版 HYPE V35 去周末 | -26.56% | -26.56% | 2 | 0.00% | long 2 笔全止损 |
| V2 | fixed 3x regular+overnight | -25.09% | -25.09% | 1 | 0.00% | stop_loss 1 |
| V4 | dynamic target 1.25% / max3 regular+overnight | -11.39% | -11.39% | 1 | 0.00% | stop_loss 1；实际杠杆 1.28x |
| B&H | 同窗口买入持有 | +27.67% | -13.97% | - | - | 2026-06-09 03:00 UTC 起算 |

## 数据限制

拉取窗口请求从 2026-04-01 开始，但 Binance 实际返回最早时间为 2026-06-02 03:00 UTC，说明 SKHYNIXUSDT 是更晚开始交易的新品种。用 MU 的 1600 warmup 会没有回测窗口，因此本次使用 ATR672 最低可用 warmup。

## 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/fetch_binance_perp_symbol_data.py | Binance FAPI 分页下载脚本 |
| scripts/research_skhynix_binance_v2_v4_transfer.py | SKHYNIX V2/V4 对照回测脚本 |
| archive/reports/legacy/skhynix_binance_hype_v35_transfer_v2_v4_summary.json | 结构化摘要 |
| archive/reports/legacy/skhynix_binance_hype_v35_original_summary.json | 原版 HYPE V35 诊断摘要 |
| archive/reports/legacy/skhynix_binance_hype_v35_original_trades.csv | 原版 HYPE V35 交易明细 |
| archive/reports/legacy/skhynix_binance_hype_v35_transfer_v2_v4_trades.csv | 交易明细 |
| data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/date=2026-04-01/symbol=skhynix_usdt_usdt.parquet | SKHYNIXUSDT 15m OHLCV |
