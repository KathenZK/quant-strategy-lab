# HYPE-15M-TB-MII-ENS-V2 Runner Replay 全样本对拍 2026-07-09

Status：

```text
combo replay trade-path parity PASS / equity parity PASS within declared funding gap / continuous dry-run runtime still blocked / live blocked / not live-ready
```

本报告完成 V2 live validation spec 验证门禁第 3 条（组合 replay gate）的交易路径部分。它不解除 live-executable blocker。

## Source

- Runner repo: `/Users/ZK/OpenCode/quant-runner`，commit `53e4b6d`（含第二轮对齐修复：MII open 型出场顺序、逐 K mark-to-market、公共指标复用、warmup 2500）。
- Runner command:

```bash
cargo run -- replay-dry-run --config configs/dryrun.toml \
  --name hype-tb-mii-ens-v2-validation --limit 38900 --end-ts 2026-07-08T05:30:00Z
```

- 对照目标：[hype_15m_tb_mii_ensemble_backtest_v39_v14_2026-07-09_trades.csv](../artifacts/hype_15m_tb_mii_ensemble_backtest_v39_v14_2026-07-09_trades.csv) 中 `variant = single_v39_priority_k1` 的 291 笔（研究脚本 `research_hype_15m_tb_mii_ensemble_backtest.py --trend v39 --mii v14`，标准数据湖）。
- 数据源说明：runner 侧为 Binance USD-M 公共 kline 分页拉取（37,165 根闭合 15m K）；研究侧为标准数据湖。两侧 291 笔的 entry/exit 价格最大相对差 `4.33e-16`，可视为同一数据。

## Observation Window / Runner Config

```text
replay_start_ts = 2025-06-16T02:30:00+00:00   # 与组合评估起点一致
replay_end_ts   = 2026-07-08T05:30:00+00:00   # 与数据湖末尾一致
bars_replayed   = 37165
symbol = HYPE/USDT:USDT, timeframe = 15m
trend = ema_tb_v39 (K+2, warmup 1600), mii = mii_v14 (K+1)
preempt_secondary = true, global_position_limit = 1
```

## 逐笔路径对拍结果

对比字段：`entry_ts`、`exit_ts`、`side`、`leg`、`exit_reason`（映射后）、`entry_price`、`exit_price`、`allocation`。

```text
python trades = 291, rust trades = 291
path mismatches = 0
entry_price / allocation：精确一致
exit_price 最大相对差 = 4.33e-16
```

出场原因逐类计数一致（runner 词表 -> 研究词表映射）：

| runner | research | 笔数 |
| --- | --- | ---: |
| `target` | `take_profit` | 235 |
| `stop_market` | `stop_loss` | 20 |
| `time_open` | `max_hold` | 23 |
| `indicator_exit` | `indicator_exit` | 10 |
| `preempted_by_v39` | `preempted_by_v39` | 3 |

样本内没有出现 gap 型出场（`stop_gap_open` / `target_gap_or_open`），因此 runner bracket 与研究引擎在 gap 记价上的已声明差异本轮未被触发。

## 逐笔收益与权益对拍

- MII 腿 184 笔：`trade_return` 最大绝对差 `6.66e-16`（engine-exact，两侧口径均不含 funding）。
- V39 腿 107 笔：`trade_return` 最大绝对差 `0.0048`、平均 `0.0024`，全部来自 runner smoke 路径不计 funding（研究侧 V39 腿含 funding）。
- 整体指标：

| 指标 | runner replay（无 funding） | 研究引擎（含 V39 funding） |
| --- | ---: | ---: |
| 总收益 | `+69593.14%` | `+68192.54%` |
| 最大回撤 | `-27.85%` | `-28.01%` |
| 胜率 | `82.82%` | `82.82%` |
| 交易数 | `291`（V39 `107` + V1.4 `184`） | `291`（V39 `107` + V1.4 `184`） |
| preempt | `3` | `3` |

- 近期窗口（与 [V2 6m/3m 审计 CSV](../artifacts/hype_15m_tb_mii_ens_v2_recent_6m_3m_trade_audit_2026-07-09.csv) 对照）：
  - `6m`：`137` 笔 / 胜率 `83.21%` / V39 `68` + V1.4 `69` / preempt `2` —— 全部一致。
  - `3m`：`72` 笔 / 胜率 `80.56%` / V39 `35` + V1.4 `37` / preempt `1` —— 全部一致。

## Artifacts

- Runner replay 逐笔导出：[hype_15m_tb_mii_ens_v2_runner_replay_parity_trades_2026-07-09.csv](../artifacts/hype_15m_tb_mii_ens_v2_runner_replay_parity_trades_2026-07-09.csv)
- 对拍摘要：[hype_15m_tb_mii_ens_v2_runner_replay_parity_summary_2026-07-09.json](../artifacts/hype_15m_tb_mii_ens_v2_runner_replay_parity_summary_2026-07-09.json)

## 结论与剩余 blocker

结论：`single_v39_priority_k1` 组合状态机在 runner replay 中与研究引擎**逐笔路径完全一致**（291 笔、腿分布、preempt 3 次、出场原因、价格、allocation 全对上）；权益差异完全由已声明的 funding 缺口解释（V39 腿 funding 未计入 runner smoke 路径）。验证门禁第 3 条（组合 replay gate）的路径部分判定 PASS。

不因本报告解除的 blocker（live pilot 前仍必须完成）：

- 连续 dry-run/live runtime 未实现：V39 K+2 pending open 执行、MII K+1 执行、组合层状态持久化（`active_leg` / `preempt_in_progress` 等）。
- live preempt 原子流程（撤保护单 -> reduce-only 平仓 -> 确认 flat -> 开 V39）未实现。
- 保护单、重启恢复、missing-bar fail-closed、kill switch、notional cap、日亏损限制未实现。
- V39 腿真实 funding 记账未实现。
- 与 V35 live service 的账户隔离约束未落实（必须停 V35 或独立 subaccount）。

下一步顺序（若用户坚持小资金 pilot）：实现连续 runtime 执行链与状态恢复 -> shadow/dry-run 观察窗口产出差异报告 -> live-executable 审计 -> 用户显式批准后小 notional pilot。
