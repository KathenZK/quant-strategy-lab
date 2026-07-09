# HYPE-5M-PBTR-V6.2.1 Runner 观察：2026-06 已知信号窗口 runtime/research 对拍

日期：2026-07-09

策略：`HYPE-5M-PBTR-V6.2.1`

结论：**match**。6 月已知 baseline 成交窗口内，quant-runner 信号引擎与 research 可行性审计成交清单逐笔一致；当前线上 7 月无成交更像是市场无信号，不是 6 月口径实现偏差。

## Runner 配置

| 字段 | 值 |
| --- | --- |
| runner | quant-runner `hype_pullback` |
| dry-run name | `hype-pullback-dry-run` |
| live name | `hype-pullback-live` |
| kind | `hype_pullback` |
| strategy_id | `HYPE-5M-PBTR-V6.2.1` |
| mode | dry-run replay（对拍）/ 线上 dry-run + live 服务仍在跑 |
| symbol | `HYPE/USDT:USDT` |
| timeframe | `5m` |
| leverage | `1` |
| dry_run_notional_usdt | `10` |
| config | `configs/dryrun.toml` |
| data_source | Binance futures public closed klines |

## 观察窗口与来源

- Research 源：[`artifacts/hype_5m_pbtr_v6-2-1_live_feasibility_trades_2026-06-30.csv`](../artifacts/hype_5m_pbtr_v6-2-1_live_feasibility_trades_2026-06-30.csv)，过滤 `mode=baseline_stop_first` 且 `signal_ts` 落在 `2026-06`
- Runtime 源命令：

```bash
quant-runner replay-dry-run \
  --config configs/dryrun.toml \
  --name hype-pullback-dry-run \
  --limit 15000 \
  --start-ts 2026-06-01T00:00:00Z \
  --end-ts 2026-06-30T06:15:00Z
```

- Runtime 导出：[`artifacts/hype_5m_pbtr_v6-2-1_runtime_replay_trades_2026-06.json`](../artifacts/hype_5m_pbtr_v6-2-1_runtime_replay_trades_2026-06.json)
- 对拍表：[`artifacts/hype_5m_pbtr_v6-2-1_runtime_research_parity_2026-06.csv`](../artifacts/hype_5m_pbtr_v6-2-1_runtime_research_parity_2026-06.csv)
- 对拍字段：`signal_ts`、`side`、`entry_ts`、`exit_ts`、`reason`、`entry_price`、由 research `raw_exit_price` 还原的 exit（含 exit slippage）、`net_ret_1x`

## 汇总

| 项 | Research | Runtime | 结论 |
| --- | ---: | ---: | --- |
| 成交笔数 | 16 | 16 | match |
| 仅 research 有 | 0 | — | — |
| 仅 runtime 有 | — | 0 | — |
| 字段 mismatch | 0 | 0 | match |
| 窗口内 signal_count | — | 29 | 含被单仓 lockout 抑制的信号 |
| 1x total_return | — | `+4.32%` | replay 汇总 |
| 1x PF | — | `1.560` | replay 汇总 |
| 1x win_rate | — | `62.5%` | replay 汇总 |
| 1x max_dd | — | `-3.75%` | replay 汇总 |

## 逐笔结论

16/16 笔 `MATCH`：

| signal_ts | side | entry_ts | exit_ts | reason |
| --- | ---: | --- | --- | --- |
| 2026-06-01T07:00:00+00:00 | +1 | 07:05 | 10:05 | time_open |
| 2026-06-05T00:35:00+00:00 | -1 | 00:40 | 01:00 | target |
| 2026-06-05T05:30:00+00:00 | -1 | 05:35 | 05:50 | target |
| 2026-06-05T16:20:00+00:00 | -1 | 16:25 | 17:25 | target |
| 2026-06-08T11:50:00+00:00 | +1 | 11:55 | 12:55 | target |
| 2026-06-08T14:25:00+00:00 | +1 | 14:30 | 17:30 | time_open |
| 2026-06-11T18:50:00+00:00 | +1 | 18:55 | 21:55 | time_open |
| 2026-06-15T06:40:00+00:00 | +1 | 06:45 | 07:10 | target |
| 2026-06-15T07:45:00+00:00 | +1 | 07:50 | 08:40 | target |
| 2026-06-15T09:40:00+00:00 | +1 | 09:45 | 10:05 | target |
| 2026-06-15T11:05:00+00:00 | +1 | 11:10 | 14:10 | time_open |
| 2026-06-16T10:05:00+00:00 | +1 | 10:10 | 10:25 | target |
| 2026-06-16T11:05:00+00:00 | +1 | 11:10 | 14:10 | time_open |
| 2026-06-17T22:45:00+00:00 | -1 | 22:50 | 2026-06-18T00:30 | stop_market |
| 2026-06-26T03:25:00+00:00 | -1 | 03:30 | 03:45 | stop_market |
| 2026-06-29T21:10:00+00:00 | +1 | 21:15 | 21:45 | target |

## 与线上现状的关系

- 阿里云 `hype-pullback-dry-run` / `hype-pullback-live` 自 7 月初起 cycle 全是 `no_signal`，无 open/close。
- 同口径对 `2026-07-01 -> 2026-07-09` 再 replay：`signal_count=0`、`trade_count=0`。
- 因此 7 月空仓与本次 6 月对拍一致：**实现口径能复现 research；当前窗口只是没有触发信号。**

## 费用 / 滑点

本报告对拍的是 research 与 runtime 的同一成本模型（fee `4.1466 bps/fill`、entry slip `+10.73 bps`、exit slip `-2.64 bps`），不是线上真实成交偏差。线上真实 fill/fee/slippage 仍待首笔 dry-run/live 成交后单独审计。

## 事件

- 无拒单、无缺 K、无 cycle_error。
- 对拍使用本地增强后的 `replay-dry-run` 输出（补了 trade 明细与 `start_ts/end_ts` 过滤）；不影响线上已部署二进制的信号逻辑本身。

## keep / stop / adjust

- **keep**：继续 dry-run / 极小 notional live 观察。
- **不升级**：本报告只证明 6 月已知窗口信号引擎对拍通过，**不满足**完整 forward-test / 真实订单生命周期验收。
- **下一步**：等待线上出现真实信号后，再对 open/close/fill 做 runtime-vs-research 成交对账。
