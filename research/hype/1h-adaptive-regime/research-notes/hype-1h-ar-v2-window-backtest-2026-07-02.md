# HYPE-1H-Adaptive-Regime-V2 窗口/滚动切片复核 - 2026-07-02

## 结论

- 本次复核不改变 `HYPE-1H-Adaptive-Regime-V2` 状态：`NO-GO / not live-ready / not promoted`。
- `current_full` 为 `9.6838x` 年化权益倍率、`78.26%` 胜率、`-19.64%` 最大回撤、`69` 笔。
- 最近一年窗口按 V2 canonical 可交易起点 `2025-07-14 10:00 UTC` 截断，实际覆盖 `352.7` 天；该窗口 `69` 笔、胜率 `78.26%`。

## 口径

- 市场：Binance USD-M Futures `HYPEUSDT` perpetual。
- 周期：`1h` closed-only K 线。
- 数据范围：`2025-05-30T10:00:00+00:00` 到 `2026-07-02T02:00:00+00:00`，normalized rows `9545`，missing `0`，duplicate `0`。
- 执行：闭合 K 信号，下一根 `1h` open 入场；DI fixed bracket，Stoch trailing；同刻冲突 DI 优先。
- 成本：`0.001` fee/fill、`4 bps` slippage/fill，并计入 funding。
- 窗口统计按 `entry_ts` 归属；年化倍数在短窗口里只作形状诊断，不作 promotion 依据。

## 最近窗口

| Window | UTC range | Days | Trades | Win rate | Total return | Max DD | Annual multiple |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `current_full` | 2025-07-14 10:00 UTC -> 2026-07-02 03:00 UTC | 352.7 | 69 | 78.26% | 795.75% | -19.64% | 9.6838x |
| `last_7d` | 2026-06-25 03:00 UTC -> 2026-07-02 03:00 UTC | 7.0 | 1 | 100.00% | 3.91% | -0.56% | 7.3908x |
| `last_30d` | 2026-06-02 03:00 UTC -> 2026-07-02 03:00 UTC | 30.0 | 8 | 87.50% | 36.09% | -16.37% | 42.5963x |
| `last_90d` | 2026-04-03 03:00 UTC -> 2026-07-02 03:00 UTC | 90.0 | 17 | 70.59% | 42.11% | -19.64% | 4.1624x |
| `last_180d` | 2026-01-03 03:00 UTC -> 2026-07-02 03:00 UTC | 180.0 | 35 | 71.43% | 165.21% | -19.64% | 7.2364x |
| `last_365d` | 2025-07-14 10:00 UTC -> 2026-07-02 03:00 UTC | 352.7 | 69 | 78.26% | 795.75% | -19.64% | 9.6838x |

## 滚动窗口摘要

| Rolling slice | Windows | Zero-trade | Positive | Trades median/min/max | Median win rate | Worst/Best return |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `rolling_7d_step7d` | 50 | 11 | 33 | 1.0/0/4 | 100.00% | -3.73% / 25.18% |
| `rolling_30d_step30d` | 11 | 0 | 10 | 5.0/2/10 | 80.00% | -1.70% / 47.81% |
| `rolling_90d_step30d` | 9 | 0 | 9 | 18.0/11/24 | 75.00% | 38.12% / 156.71% |
| `rolling_180d_step30d` | 6 | 0 | 6 | 37.5/34/42 | 77.38% | 137.00% / 339.07% |

## 机器证据

- JSON：`artifacts/hype_1h_ar_v2_window_backtest_2026-07-02.json`
- 最近窗口 CSV：`artifacts/hype_1h_ar_v2_recent_windows_2026-07-02.csv`
- 滚动窗口 CSV：`artifacts/hype_1h_ar_v2_rolling_windows_2026-07-02.csv`
- 逐笔交易 CSV：`artifacts/hype_1h_ar_v2_window_backtest_trades_2026-07-02.csv`

复现：

```bash
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v2_window_backtest.py
```

滚动明细共 `76` 行，CSV 中保留每个切片的交易数、胜率、收益、回撤和多空笔数。
