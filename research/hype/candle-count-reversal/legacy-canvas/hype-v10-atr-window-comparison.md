# HYPE V10 ATR Window Comparison

> 迁移说明：本文由 legacy Cursor Canvas `hype-v10-atr-window-comparison.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：HYPE-CC legacy Canvas。

Source: local Binance HYPE perpetual 15m data, mark-price high/low exits, funding included. Time range: 2025-05-30 10:30 UTC to 2026-05-13 06:15 UTC.

### 关键指标

| 指标 | 数值 |
| --- | --- |
| Best 1Y Return: V10 Original | +558.30% |
| Lowest 1Y Drawdown: TP/SL ATR288 | -33.41% |
| Best 3M Return: V10 Original | +300.18% |
| Best 3M Drawdown: V10 Original | -20.20% |

### Key Read

Changing both take-profit and stop-loss to ATR288 slightly lowers the available-year drawdown versus V10 original, but it gives up return in every tested window. V10 original remains the better balanced version unless the only goal is shaving a tiny amount off the one-year drawdown.

## Full Backtest Table

Annualized return is shown for comparison only; short windows can annualize to very large numbers. Stops / Takes are counted as stop exits divided by take-profit exits.

| Period | Strategy | Sizing ATR | Take ATR | Stop ATR | Return | Max DD | Ann. Return | Sharpe | Entries | Stops / Takes | Avg Abs Weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1周 | V10 原版 | ATR96 | ATR192 | ATR288 | +8.06% | -12.14% | +5582.58% | 4.49 | 7 | 2 / 4 | 1.43x |
| 1周 | 仅止损改 ATR192 | ATR96 | ATR192 | ATR192 | +8.06% | -12.14% | +5582.58% | 4.49 | 7 | 2 / 4 | 1.43x |
| 1周 | 全部 ATR192 | ATR192 | ATR192 | ATR192 | +7.40% | -13.52% | +4041.74% | 4.13 | 7 | 2 / 4 | 1.46x |
| 1周 | 止盈止损 ATR288 | ATR96 | ATR288 | ATR288 | +7.83% | -12.14% | +4996.82% | 4.39 | 7 | 2 / 4 | 1.43x |
| 1个月 | V10 原版 | ATR96 | ATR192 | ATR288 | +25.37% | -20.20% | +1466.30% | 3.37 | 21 | 7 / 13 | 1.25x |
| 1个月 | 仅止损改 ATR192 | ATR96 | ATR192 | ATR192 | +24.49% | -20.47% | +1336.42% | 3.28 | 21 | 7 / 13 | 1.25x |
| 1个月 | 全部 ATR192 | ATR192 | ATR192 | ATR192 | +19.63% | -21.97% | +785.67% | 2.76 | 21 | 7 / 13 | 1.26x |
| 1个月 | 止盈止损 ATR288 | ATR96 | ATR288 | ATR288 | +24.58% | -20.70% | +1349.66% | 3.29 | 21 | 7 / 13 | 1.24x |
| 3个月 | V10 原版 | ATR96 | ATR192 | ATR288 | +300.18% | -20.20% | +27600.28% | 6.09 | 71 | 20 / 50 | 1.09x |
| 3个月 | 仅止损改 ATR192 | ATR96 | ATR192 | ATR192 | +236.34% | -20.47% | +13589.86% | 5.63 | 74 | 22 / 51 | 1.06x |
| 3个月 | 全部 ATR192 | ATR192 | ATR192 | ATR192 | +255.11% | -21.97% | +16962.77% | 5.86 | 74 | 22 / 51 | 1.06x |
| 3个月 | 止盈止损 ATR288 | ATR96 | ATR288 | ATR288 | +266.19% | -20.70% | +19226.50% | 5.78 | 72 | 21 / 50 | 1.07x |
| 1年可用 | V10 原版 | ATR96 | ATR192 | ATR288 | +558.30% | -33.69% | +622.50% | 2.84 | 306 | 132 / 173 | 0.65x |
| 1年可用 | 仅止损改 ATR192 | ATR96 | ATR192 | ATR192 | +459.03% | -39.57% | +508.62% | 2.66 | 312 | 137 / 174 | 0.64x |
| 1年可用 | 全部 ATR192 | ATR192 | ATR192 | ATR192 | +531.44% | -36.61% | +591.60% | 2.80 | 312 | 137 / 174 | 0.64x |
| 1年可用 | 止盈止损 ATR288 | ATR96 | ATR288 | ATR288 | +515.81% | -33.41% | +573.65% | 2.76 | 307 | 133 / 173 | 0.64x |
