# BTC/ETH共享MA7参数对齐HYPE窗口复算

## 结论

裁决：`TRANSFER_FAIL / diagnostic-only / not promoted / not live-ready`。

按用户要求，将此前 BTC/ETH development 选出的共享 `SMA7/ATR7` 参数原样应用到 HYPE，并尽量对齐当前 HYPE fresh API 诊断窗口。Binance public API 返回 `HYPEUSDT` 原始日K `439` 根（`2025-05-30` 至 `2026-08-11`），但 `2025-05-30` 只有 14 根小时K，不满足旧 shared engine 对 stop / funding 的完整 24h 路径要求；本轮实际用于回测的是第一个完整 UTC 日开始的 `438d`：`2025-05-31` 至 `2026-08-11`，terminal open 为 `2026-08-12 00:00 UTC`。

结果没有改善：combined 仍为 `-65.15%`，MDD `-73.47%`，14 笔交易，PF `0.29`；long-only `-24.12%`，short-only `-59.45%`。同期 buy-and-hold（计同源 funding 与双边成本）为 `+52.01%`。这说明之前记忆里的 BTC/ETH 通用 MA7 参数不能解释 HYPE 的正收益，也不能替代 HYPE V7.1。

## 数据与执行

- 数据源：Binance futures public API，`HYPEUSDT` USD-M perpetual。
- 原始对齐窗口：`2025-05-30` 至 `2026-08-11`，`439` 根闭合日K。
- 可执行完整窗口：`2025-05-31` 至 `2026-08-11`，`438` 根完整 UTC 日K；terminal open `2026-08-12 00:00 UTC`。
- 小时线质量：`10527` 根，连续、无重复、无 OHLC blocker；首个半日只作为 raw source 记录，不进入回测。
- 成本：fee `0.001/fill`，base slippage `4 bps/fill`，stress slippage `8 bps/fill`；funding 使用 Binance fundingRate event-time。
- 参数来源：BTC/ETH shared 参数由 2026-08-05 的 BTC/ETH development-only 搜索固定；本轮不读取 HYPE 调参。

## 回测结果

| Variant | Net | MDD | Sharpe | PF | Trades | Win | 8bps Net | +1d Lag |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Combined | `-65.15%` | `-73.47%` | `-1.38` | `0.29` | `14` | `21.43%` | `-65.56%` | `-54.70%` |
| Long-only | `-24.12%` | `-47.43%` | `-0.48` | `0.53` | `7` | `28.57%` | `-24.55%` | `-26.84%` |
| Short-only | `-59.45%` | `-61.71%` | `-1.65` | `0.05` | `9` | `11.11%` | `-59.77%` | `-44.63%` |
| Buy-and-hold | `+52.01%` | - | - | - | - | - | - | - |

`8 bps` 压力和额外一天信号延迟都没有改变结论：亏损来自信号/状态机不适配，而不是执行成本或某个末端交易。

## 近期切片

| Variant | 1d | 7d | 1m | 3m | 6m | 1y |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Combined | `0.00%` | `0.00%` | `0.00%` | `-34.47%` | `-29.07%` | `-69.93%` |
| Long-only | `0.00%` | `0.00%` | `0.00%` | `-8.70%` | `+5.68%` | `-34.54%` |
| Short-only | `0.00%` | `0.00%` | `0.00%` | `-28.22%` | `-32.88%` | `-59.45%` |

最近 `1d/7d/1m` 为 `0%` 是因为没有持仓与交易，不是策略转好。新增到 `2026-08-12` terminal open 的数据没有新增 closed trade，因此 full-window 净值与旧 local 复算保持一致。

## 读数

- BTC/ETH shared 参数的核心节奏是慢斜率与宽迟滞：long 依赖 `5d` MA7 斜率、`0.25 ATR` reclaim、2 日迟滞退出；short 依赖 `pullback_reclaim`、`1.5 ATR` hard stop、`5 ATR` trailing 和 10 日 max hold。
- HYPE V7.1 的历史正收益来自更快的 HYPE-specific reclaim / OAPP / PEHC / RSI6 short take-profit 结构；同为 `SMA7` 并不代表 entry、hold、exit 参数可共用。
- 与当前 HYPE Top30 fresh API 诊断里的 `HYPEUSDT` V7.1 读数（`+257.97%`）相比，BTC/ETH shared 参数同窗为 `-65.15%`，方向完全相反；这支持“BTC/ETH shared 不是 HYPE 通用替代版本”的旧结论。
- 本轮不登记版本、不推进 runner、不作为 live spec 或 dry-run 依据。

## 证据

- [fresh aligned机器证据](../artifacts/binance_ma7_shared_params_on_hype_fresh_aligned_2026-08-12.json)
- [fresh aligned指标表](../artifacts/binance_ma7_shared_params_on_hype_fresh_aligned_2026-08-12_metrics.csv)
- [fresh aligned近期切片](../artifacts/binance_ma7_shared_params_on_hype_fresh_aligned_2026-08-12_recent.csv)
- [fresh aligned逐笔交易](../artifacts/binance_ma7_shared_params_on_hype_fresh_aligned_2026-08-12_trades.csv)
- [fresh aligned权益路径](../artifacts/binance_ma7_shared_params_on_hype_fresh_aligned_2026-08-12_path.csv)
- [SHA256](../artifacts/binance_ma7_shared_params_on_hype_fresh_aligned_2026-08-12.sha256)
- [复算脚本](../scripts/audit_shared_ma7_params_on_hype_fresh_window.py)
- [旧HYPE control诊断](binance-ma7-shared-params-on-hype-2026-08-05.md)
