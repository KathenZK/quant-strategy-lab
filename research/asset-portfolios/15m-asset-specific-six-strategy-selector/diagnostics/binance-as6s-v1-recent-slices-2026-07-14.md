# BIN-15M-AS6S-V1 近期切片审计（2026-07-14）

## 口径

- 版本：`Binance-15M-Asset-Specific-Six-Strategy-Selector-V1`（`BIN-15M-AS6S-V1`）。
- 路线：九腿、全局单仓、`nonpreemptive`，账户缩放 `0.75`。
- 市场：Binance USD-M Futures perpetual；币种为 BTC、ETH、SOL、BNB、TRX、HYPE。
- 组合周期：资产专属 `15m / 1h` 混合信号；闭合信号 K 后下一根 open 入场。
- 数据终点：`2026-07-14T09:00:00Z`；所有切片均锚定该终点。
- 成本：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、Binance 实际历史 funding。
- 交易归属：`entry_ts >= window_start` 且 `exit_ts < window_end`；六个标准切片起点均无跨界持仓。
- 用途：仅为登记时点的 reused-data 审计，不参与参数、腿或路线选择，不替代未来最终 OOS。

## 结果

| Window | UTC Range | Return | Win Rate | Trades | Max DD |
| --- | --- | ---: | ---: | ---: | ---: |
| 最近 1 天 | `[2026-07-13 09:00, 2026-07-14 09:00)` | `0.00%` | N/A | `0` | `0.00%` |
| 最近 1 周 | `[2026-07-07 09:00, 2026-07-14 09:00)` | `-5.06%` | `33.33%` | `3` | `-6.25%` |
| 最近 1 月 | `[2026-06-14 09:00, 2026-07-14 09:00)` | `+4.75%` | `75.00%` | `12` | `-6.25%` |
| 最近 3 月 | `[2026-04-14 09:00, 2026-07-14 09:00)` | `+42.32%` | `92.50%` | `40` | `-6.25%` |
| 最近半年 | `[2026-01-14 09:00, 2026-07-14 09:00)` | `+111.71%` | `91.58%` | `95` | `-10.44%` |
| 最近 1 年 | `[2025-07-14 09:00, 2026-07-14 09:00)` | `+364.53%` | `90.96%` | `188` | `-12.37%` |

最近一周与最近一月胜率低于用户设定的 `80%` 目标，其中一周只有 `3` 笔，统计证据很弱但亏损是真实的。三个月、半年和一年切片的胜率均高于 `90%`。这些近期切片已被看到，因此只能作为 reused diagnostic；V1 是否最终通过仍由 `[2026-07-14T09:00Z, 2026-10-14T09:00Z)` 的未来 OOS 一次性判定。

## 证据

- 结构化结果：[../artifacts/binance_15m_as6s_v1_recent_slices_2026-07-14.json](../artifacts/binance_15m_as6s_v1_recent_slices_2026-07-14.json)
- 组合交易路径：[../artifacts/binance_hybrid_asset_specific_account_trades_2026-07-14.csv](../artifacts/binance_hybrid_asset_specific_account_trades_2026-07-14.csv)
- 冻结机器清单：[../artifacts/binance_as6s_future_oos_freeze_2026-07-14.json](../artifacts/binance_as6s_future_oos_freeze_2026-07-14.json)
- 复现脚本：[../scripts/audit_binance_as6s_v1_recent_slices.py](../scripts/audit_binance_as6s_v1_recent_slices.py)
