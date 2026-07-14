# HYPE-15M-TB-MII-ENS-V2 临近 TP Runtime 对齐

日期：2026-07-14

## 状态

```text
dry-run open trade / entry parity matched / close reconciliation pending / keep current rules
```

本报告回写 `hype-tb-mii-ens-dry-run` 第一笔 V39 趋势腿持仓的线上生命周期证据，并与 `HYPE-EMA-TB-V35/V39` 研究回放及临近 TP 保护线反事实对齐。该交易截至最新快照仍 open，因此本报告只完成 entry/MFE parity 和反事实退出核对，不能声称完成实际 close/fill reconciliation。

## 来源与观察窗口

- Runner host：`47.80.57.36`。
- Platform ledger：`/home/admin/quant-runner/state/platform/platform.sqlite3`。
- 数据表：`trades`、`strategy_health`、`events`。
- 观察窗口：`2026-07-13T14:15:00Z` signal 至 `2026-07-14T07:45:02Z` 最新 cycle。
- Runner config：`/home/admin/quant-runner/configs/dryrun.toml`，实例 `hype-tb-mii-ens-dry-run`，`mode=dry_run`。
- 稳定事件 ID：`HYPE-15M-TB-MII-ENS-V2-ema_tb_v39-2026-07-13T14:15:00+00:00`。
- 快照 JSON：[hype_15m_tb_mii_ens_v2_near_tp_runtime_snapshot_2026-07-14.json](../artifacts/hype_15m_tb_mii_ens_v2_near_tp_runtime_snapshot_2026-07-14.json)。
- 研究报告：[HYPE-EMA-TB V35/V39 临近止盈保护线复测](../../15m-ema-trend-breakout/notes/hype-ema-tb-v35-v39-near-tp-floor-diagnostic-2026-07-14.md)。

## Runner 实际持仓

| 字段 | 值 |
| --- | --- |
| Strategy / leg | `hype-tb-mii-ens-dry-run / ema_tb_v39` |
| Side | short |
| Signal | `2026-07-13T14:15:00Z` |
| Entry | `2026-07-13T14:45:00Z @ 64.156` |
| Entry reference | `current_contract_price` |
| Quantity / notional | `0.467 / 29.960852 USDT` |
| Allocation | `3.0` |
| Entry ATR672 | `0.3422410714285733` |
| TP / SL | `62.44479464285714 / 66.55168750000001` |
| Order IDs | entry `1` / TP `2` / stop `3` |
| 最大 MFE | `4.838694529232205 ATR` |
| 首次达到最大 MFE | `2026-07-13T21:45:01Z` |
| 最新 cycle | `2026-07-14T07:45:02Z`，`bars_held=67`，`event=holding` |
| 实际 close | 无；仍 open |
| Fee / realized PnL | 无；dry-run ledger 尚未平仓 |

`strategy_health` 在最新快照为 `ok / position_open=1`，`last_bar_ts=2026-07-14T07:30:00Z`；没有 pending open exit，`weak_bars=0`。

## 研究预期与实际对齐

标准数据湖截至 `2026-07-14T03:00:00Z`，V35 与 V39 对该信号给出相同 entry path：

| 字段 | Runner dry-run | V39 研究回放 | 差异 |
| --- | ---: | ---: | ---: |
| Signal timestamp | `14:15Z` | `14:15Z` | match |
| Entry timestamp | `14:45Z` | `14:45Z` | match |
| Entry price | `64.156` | `64.153` | `+0.003`（约 `0.47 bps`） |
| Entry ATR672 | `0.3422410714285733` | `0.34224107142857135` | 浮点误差级 |
| TP | `62.4447946` | `62.4417946` | 由 entry price 差异解释 |
| SL | `66.5516875` | `66.5486875` | 由 entry price 差异解释 |
| 最大 MFE | `4.8386945ATR` | `4.8299288ATR` | `0.00877ATR` |

结论：信号时间、入场时间和 ATR 对齐；entry price 使用实时 contract reference，相对 K2 candle open 差 `0.003`，足以解释 TP/SL 和 MFE 的小偏移。当前没有实际 close，close timestamp、exit price、fee、slippage 和 PnL 的最终对齐仍 pending。

## 保护线反事实

| 规则 | 本次路径 | 长期结果 |
| --- | --- | --- |
| Base `5ATR TP` | 截至研究数据末尾和 runtime 最新快照均保持 open | V39 full `+9969.45% / -23.46%` |
| `4.75 -> lock 4.25` | `2026-07-13T21:45Z @ 62.6984754` 平仓，约 `+6.62%`；无冷却时 `22:00Z @ 62.907` 再次做空 | V39 full 降至 `+7417.48%`，maxDD 不改善 |
| `4.75 -> 4.25 + cd16` | 锁住本次 `+6.62%` 且阻止立即重入 | post-hoc；V39 full `+5308.74%`、maxDD `-24.21%`，否决 |
| `4.90 -> lock 4.40` | runtime MFE `4.8387`，不会触发 | V39 full `+8562.77%`，仍有收益成本且不解决本次问题 |
| 固定 TP `4.75` | `2026-07-13T21:30Z @ 62.5273549`，约 `+7.49%` | V39 full `+5679.64%`，maxDD 恶化到 `-32.57%`，否决 |

## Keep / Stop / Adjust

- Keep：保持当前 V39 趋势腿 `5ATR TP / 7ATR SL` 和现有状态机；本次不修改 runner 配置或保护单。
- Stop：不推进固定 `4.75ATR` TP、全局 near-TP floor 或固定 16 根冷却。
- Adjust：仅保留新的研究假设——floor 退出后等待同向趋势 episode 完整 reset 再允许同向重入；先做全路径回放，不进入 runner。
- Follow-up：该实际持仓平仓后必须补充本报告，写入 actual exit timestamp/price/reason、dry-run fee/slippage、order/event ID、realized PnL，并完成 close match/mismatch 结论。

本报告不改变 V2 状态：`production dry-run active / live disabled / not promoted / not live-ready`。
