# HYPE-1D-MA7-ABT-V6 迁移至 BTC/ETH 诊断

## 结论

把当前 `HYPE-1D-MA7-Asymmetric-Body-Trend-V6`（`PEHC_294`，固定 `1x`）零调参迁移到 BTC/ETH 后，**不成立为可迁移策略**。

- BTC 完整 `729d` 小亏：`-3.28%`，MDD `-42.33%`，PF `0.966`，49 笔。
- ETH 完整 `729d` 为正：`+67.39%`，但 MDD `-36.73%`，最近 `1y` 为 `-28.23%`，且额外延迟一天转为 `-35.01%`。
- HYPE V6 共同窗口 `425d` 上，BTC `-8.46%`、ETH `-3.81%`，两者都为负。
- BTC `12h` 相位仍为负；ETH `12h` 相位从 `+67.39%` 降至 `+8.85%`，仅约 UTC 主相位的 `13%`。

因此，本轮只保留为 `diagnostic-only / not promoted / not live-ready`，不登记 BTC/ETH V6，不修改 HYPE V6，不推进 runner。

## 口径

- 来源版本：`HYPE-1D-MA7-ABT-V6` / `PEHC_294`，配置 SHA256 `b155a35133224e77266ba0c22fb84ba1657ab89212a700e9f551b3fa3431af00`。
- 机制：完整继承 V5/OAPP 与 V4 `MA_ONLY` 状态机；PEHC shadow expiry `8d`、`next_utc_open` handoff、无额外 slope / chase 限制。
- 迁移原则：BTC/ETH 零调参；不按目标资产重搜参数。
- 数据：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual `1h` 聚合 UTC `1d`。
- 窗口：完整 `2024-07-31` 至 `2026-07-30 UTC`；共同窗口 `2025-05-31` 至 `2026-07-30 UTC`。
- 成本：每 fill fee `0.001`，主滑点 `4 bps/fill`，压力滑点 `8 bps/fill`，实际 funding 仅持仓期间结算。
- 数据质量：BTC/ETH `1h` 与 funding 审计 blocker 均为 `0`。

## 主要结果

| Asset | Window | Return | MDD | PF | Trades | Buy & Hold | Excess |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC | Full `729d` | `-3.28%` | `-42.33%` | `0.966` | 49 | `-17.38%` | `+14.10pp` |
| BTC | HYPE common `425d` | `-8.46%` | `-25.59%` | `0.835` | 29 | `-42.77%` | `+34.31pp` |
| ETH | Full `729d` | `+67.39%` | `-36.73%` | `1.272` | 54 | `-51.15%` | `+118.54pp` |
| ETH | HYPE common `425d` | `-3.81%` | `-36.73%` | `0.966` | 33 | `-29.53%` | `+25.72pp` |

`excess` 为相对同窗 `1x` buy-and-hold 的成本后差值。BTC/ETH 都能跑赢 buy-and-hold，但 BTC 绝对亏损，ETH 的收益主要来自更早窗口，不能通过当前窗口稳定性检查。

## 稳健性

| Asset | Full base | `8 bps` | Extra delay 1d | Funding off |
| --- | ---: | ---: | ---: | ---: |
| BTC | `-3.28%` | `-7.00%` | `+32.89%` | `-1.51%` |
| ETH | `+67.39%` | `+60.37%` | `-35.01%` | `+70.70%` |

- BTC 对延迟方向敏感：额外延迟变正，说明 UTC 主路径并非稳定优势。
- ETH 对延迟极端敏感：base 为正，但晚一天执行即大幅亏损。
- Funding 不是主要成败因素；funding-off 后 BTC 仍亏，ETH 仍正。

## Phase 与近期切片

| Asset | UTC phase | 12h phase | Recent 1y | Recent 6m | Recent 3m |
| --- | ---: | ---: | ---: | ---: | ---: |
| BTC | `-3.28%` | `-3.39%` | `-12.95%` | `-2.40%` | `+1.59%` |
| ETH | `+67.39%` | `+8.85%` | `-28.23%` | `-12.71%` | `-1.15%` |

ETH 的完整窗口收益被最近一年否定，BTC 的完整与最近一年均为负。

滚动 `180d` 窗口：

- BTC：`4/10` 个窗口为正，后半段多数为负。
- ETH：`7/10` 个窗口为正，但最近三个窗口中两个为负，最近 `180d` 为 `-11.02%`。

## PEHC 行为

- BTC full：`5` 次 shadow start，`4` 次 handoff opportunity，`3` 次 handoff accept。
- ETH full：`7` 次 shadow start，`6` 次 handoff opportunity，`5` 次 handoff accept。

PEHC 在 BTC/ETH 上确实发生，并非完全休眠；问题是 handoff 与 V5/OAPP 组合后仍未形成足够稳定的目标资产 edge。

## 决定

1. 不登记 `BIN-1D-MA7-ST-XFER-V6` 或任何 BTC/ETH V6 版本。
2. 不把 ETH full 正收益解释为可迁移成功，因为共同窗口、recent slices、延迟与相位都未过。
3. 不修改 HYPE V6；HYPE V6 仍是 `registered / shadow-only / not promoted / not live-ready`。
4. 不在 BTC/ETH 已揭示历史上继续微调 V6 参数；若继续研究，应另立非零调参合同或等待 clean prospective。

## 证据

- [机器摘要](../artifacts/binance_1d_ma7_abt_v6_transfer_btc_eth_2026-08-10.json)
- [指标表](../artifacts/binance_1d_ma7_abt_v6_transfer_btc_eth_2026-08-10_metrics.csv)
- [近期切片](../artifacts/binance_1d_ma7_abt_v6_transfer_btc_eth_2026-08-10_recent.csv)
- [12h 相位](../artifacts/binance_1d_ma7_abt_v6_transfer_btc_eth_2026-08-10_phase.csv)
- [滚动 `180d`](../artifacts/binance_1d_ma7_abt_v6_transfer_btc_eth_2026-08-10_rolling_180d.csv)
- [交易记录](../artifacts/binance_1d_ma7_abt_v6_transfer_btc_eth_2026-08-10_trades.csv)
- [权益路径](../artifacts/binance_1d_ma7_abt_v6_transfer_btc_eth_2026-08-10_path.csv)
- [复现脚本](../scripts/research_binance_1d_ma7_abt_v6_transfer.py)
