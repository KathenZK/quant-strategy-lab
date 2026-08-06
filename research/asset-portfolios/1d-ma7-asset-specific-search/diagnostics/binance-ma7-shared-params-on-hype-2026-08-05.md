# BTC/ETH 共享 MA7 参数零调参应用于 HYPE

## 结论

BTC/ETH development 选出的共享参数原样应用到 HYPE 日 K 后**完全失败**：

| Variant | 净收益 | MDD | Sharpe | PF | 交易数 | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Combined | `-65.15%` | `-73.47%` | `-1.40` | `0.29` | `14` | `21.43%` |
| Long-only | `-24.12%` | `-47.43%` | `-0.48` | `0.53` | `7` | `28.57%` |
| Short-only | `-59.45%` | `-61.71%` | `-1.67` | `0.05` | `9` | `11.11%` |

同期 HYPE V1 为 `+293.20%`、MDD `-26.44%`；计相同成本与 funding 的 buy-and-hold 为 `+50.82%`。共享参数没有保留 HYPE 的多头或空头优势。

本观察只回答 BTC/ETH 共享参数能否零调参回到 HYPE；没有使用 HYPE 重新搜索或二次挑选。

## 冻结来源与执行

- 参数来源：[BTC/ETH 分资产与共享搜索机器摘要](../artifacts/binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json)，SHA256 `ecaf0d65ddc7ed114acd078656e7da948a6ed5399c1b6292d716fb91199031be`；
- Source engine SHA256：`c376f8bd1bae814b0ba53687380ee1060cf3cc3095ae815ebb0311ed1aef59e1`；
- HYPE 数据：accepted Binance USD-M `HYPEUSDT` perpetual `1h` 聚合完整 UTC 日 K；
- 窗口：`2025-05-31` 至 `2026-07-30 UTC` terminal open，`425d`；
- 成本：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、实际 event-time funding；压力滑点 `8 bps/fill`；
- 仓位：约 `1x`、单仓、非加仓；stop 使用真实 `1h` 路径。

## 成本与延迟

| Variant | Base | `8 bps` | +1 day lag |
| --- | ---: | ---: | ---: |
| Combined | `-65.15%` | `-65.56%` | `-54.70%` |
| Long-only | `-24.12%` | `-24.55%` | `-26.84%` |
| Short-only | `-59.45%` | `-59.77%` | `-44.63%` |

更高摩擦或执行延迟没有改变失败结论；亏损不是成本造成的。

## 相位

| 日界 | Combined | MDD | Trades |
| --- | ---: | ---: | ---: |
| `0h UTC` | `-65.15%` | `-73.47%` | `14` |
| `12h UTC` | `-70.24%` | `-74.01%` | `19` |

两个日界均大幅亏损。这里不存在“原生相位盈利、偏移相位失败”的模糊空间。

## 为什么共享参数在 HYPE 失败

### 多头

共享 long 使用 5 日 MA7 方向、`0.25 ATR` reclaim、连续两日 `MA7-1 ATR` 退出或 5 日斜率反转；没有 hard stop、trailing 或 max-hold。

在 BTC/ETH development 中，这种慢确认和宽迟滞减少噪声退出；在 HYPE 的高波动路径中，它会：

- 更晚确认快速趋势；
- 对剧烈反转反应较慢；
- 缺少 HYPE V1 的 `1.5 ATR` trailing 利润保护。

Long-only 只有 2/7 笔盈利，最终 `-24.12%`。

### 空头

共享 short 要求过去 5 日曾反弹到 `MA7+0.5 ATR`，随后重新跌到 `MA7-0.1 ATR` 下方；使用 `1.5 ATR` hard stop、`5 ATR` trailing 与 10 日 max-hold。

HYPE 的强动量反弹经常不是“反弹失败”，而是继续上冲。Short-only 9 笔只有 1 笔盈利，多数由 protective stop 退出，PF 仅 `0.05`。HYPE V1 的快速 2 日负斜率、1 日斜率反转退出与不同 entry timing 不能被共享 short 替代。

## 滚动与近期

滚动 `90d`、每 `30d` 前进：

- Combined：`3/12` 为正，最低 `-39.15%`；
- Long-only：`4/12` 为正，最低 `-25.80%`；
- Short-only：`0/12` 为正，最低 `-32.88%`。

最近：

| Variant | `1m` | `3m` | `6m` | `1y` |
| --- | ---: | ---: | ---: | ---: |
| Combined | `-11.26%` | `-39.34%` | `-38.60%` | `-69.93%` |
| Long-only | `0.00%` | `-8.70%` | `-8.52%` | `-34.54%` |
| Short-only | `-11.26%` | `-33.56%` | `-32.88%` | `-59.45%` |

## 判断

1. 固定 MA7 并不意味着 entry / hold / exit 参数可以跨资产共享。
2. BTC/ETH 共享参数更适合低速确认与宽迟滞；HYPE 需要的历史赢家是更快的 reclaim、短斜率和不同 trailing/退出结构。
3. 该结果也说明共享参数不是通用 MA7 策略，只是 BTC/ETH development 的共同候选。
4. 不根据 HYPE 结果修改共享参数；不登记、不 promotion。

## 证据

- [机器摘要](../artifacts/binance_ma7_shared_params_on_hype_summary_2026-08-05.json)
- [指标表](../artifacts/binance_ma7_shared_params_on_hype_metrics_2026-08-05.csv)
- [相位审计](../artifacts/binance_ma7_shared_params_on_hype_phase_2026-08-05.csv)
- [滚动 90 日](../artifacts/binance_ma7_shared_params_on_hype_rolling_90d_2026-08-05.csv)
- [近期切片](../artifacts/binance_ma7_shared_params_on_hype_recent_2026-08-05.csv)
- [逐笔交易](../artifacts/binance_ma7_shared_params_on_hype_trades_2026-08-05.csv)
- [组合路径](../artifacts/binance_ma7_shared_params_on_hype_path_2026-08-05.csv)
- [复现脚本](../scripts/audit_shared_ma7_params_on_hype.py)
