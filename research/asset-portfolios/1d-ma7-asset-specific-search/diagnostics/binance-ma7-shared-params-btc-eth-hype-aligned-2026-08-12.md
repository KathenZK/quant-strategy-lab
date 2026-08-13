# BTC/ETH共享MA7参数在HYPE对齐窗口的BTC/ETH复算

## 结论

裁决：`ASSET_SPECIFIC_EDGE_RETAINED / diagnostic-only / not promoted / not live-ready`。

用户追问“BTC/ETH shared 参数是不是全周期赚钱、但 HYPE 对齐周期不赚钱”。本轮把问题拆清楚：同一组 BTC/ETH shared `SMA7/ATR7` 参数，截取与 HYPE fresh 诊断相同的完整 UTC 日窗口（`2025-05-31` 至 `2026-08-11`，terminal open `2026-08-12 00:00 UTC`），分别回测 `BTCUSDT` 与 `ETHUSDT`。

答案是：在 BTC/ETH 上，HYPE 对齐窗口仍赚钱；亏损只发生在把这组参数迁移到 HYPE 时。

## 对齐窗口结果

| Target | Combined Net | MDD | Sharpe | PF | Trades | 8bps Net | +1d Lag | Buy-and-hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `BTCUSDT` | `+48.86%` | `-14.78%` | `1.74` | `3.28` | `15` | `+47.12%` | `+89.78%` | `-43.28%` |
| `ETHUSDT` | `+55.29%` | `-27.02%` | `1.32` | `2.36` | `10` | `+54.06%` | `+102.70%` | `-30.73%` |
| `HYPEUSDT` control | `-65.15%` | `-73.47%` | `-1.38` | `0.29` | `14` | `-65.56%` | `-54.70%` | `+52.01%` |

这里的 `HYPEUSDT control` 来自同日 fresh aligned 复算，用同一 shared 参数、同一完整日口径，但目标资产换成 HYPE。

## 读数

- “之前是赚钱的”这个记忆是对的：BTC/ETH shared 参数在原 full 窗口赚钱，在 HYPE 对齐窗口的 BTC/ETH 子样本也仍赚钱。
- 失败不是因为 HYPE 对齐时间段整体不适合 shared MA7；同一时间段里 BTC 与 ETH 都显著跑赢各自 buy-and-hold。
- 失败来自资产迁移：HYPE 的路径、波动和反转节奏不适合 BTC/ETH shared 参数；HYPE V7.1 的正收益来自 HYPE-specific 状态机，而不是这组通用 shared 参数。
- 本轮只澄清归因，不登记版本、不 promotion、不推进 runner。

## 证据

- [BTC aligned机器证据](../artifacts/binance_ma7_shared_params_on_btc_hype_aligned_2026-08-12.json)
- [ETH aligned机器证据](../artifacts/binance_ma7_shared_params_on_eth_hype_aligned_2026-08-12.json)
- [BTC aligned指标表](../artifacts/binance_ma7_shared_params_on_btc_hype_aligned_2026-08-12_metrics.csv)
- [ETH aligned指标表](../artifacts/binance_ma7_shared_params_on_eth_hype_aligned_2026-08-12_metrics.csv)
- [SHA256](../artifacts/binance_ma7_shared_params_btc_eth_hype_aligned_2026-08-12.sha256)
- [HYPE aligned control诊断](binance-ma7-shared-params-on-hype-fresh-aligned-2026-08-12.md)
- [复算脚本](../scripts/audit_shared_ma7_params_on_hype_fresh_window.py)
