# HYPE-5M-PBTR-V6.2.1 实盘可行性深度审计 2026-06-30

Family id：`HYPE-5M-PBTR`

审计对象：`HYPE-5M-PBTR-V6.2.1`，即 long `EMA21/55 + htf_spread>=0 + dir_ret192_bps>=788.123 + TP2.5/SL7/timeout36`，short `EMA34/144 + dir_ret48_bps>=400 + TP1.5/SL2/timeout48`，组合层严格单仓、同根 long 优先。

## 结论

未发现明确未来函数或旧 V3/V4 那类 delayed trailing / crossed stale stop 价格成交问题。信号在第 `t` 根 5m K 收盘后确认，最早第 `t+1` 根 open 入场；EMA、ATR、HTF spread 和 `dir_ret` 特征均可由 `t` 及以前闭合 K 计算。

但该策略仍不能直接视为生产 live-ready。主要剩余风险是实盘订单层：入场成交后 TP/SL 是否能立即、幂等、成对维护；单边成交后是否能可靠取消另一边；timeout 市价平仓和重启恢复是否与回测一致；以及 short leg OOS 样本仍很小。若 bracket 晚一根 5m K 才生效，回测收益小幅下降、回撤变差但仍保持正期望，这说明策略没有完全依赖入场 K 的不可成交瞬间，但入场 K 风险仍需要 paper/live-dry-run 记录。

## 数据与未来函数检查

- 数据范围：`2025-05-30T10:30:00+00:00` 到 `2026-06-30T06:15:00+00:00`，`113998` 根 5m K。
- 缺口/重复/非法 OHLC：missing `0`，duplicate `0`，invalid OHLC `0`。
- 关键字段空值：`{"close": 0, "high": 0, "low": 0, "open": 0, "quote_volume": 0, "trade_count": 0, "volume": 0}`。
- 截断重算因果性检查：`91` 个 feature-point 对比，失败 `0` 个。

检查方式：对多个历史索引只保留该索引及以前的数据，重新计算 `EMA/ATR/HTF/ret/volume ratio`，再与全量计算在同一索引的值比较。若全量结果依赖未来数据，这里会出现差异。

## Baseline 执行读数

| 口径 | 交易数 | 总收益 | PF | 平均每笔 | 胜率 | payoff | DD | 退出分布 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `baseline_stop_first` | `220` | `1054.07%` | `1.813` | `1.23%` | `64.55%` | `0.996` | `-22.35%` | `{"stop_market": 19, "target": 129, "time_open": 72}` |
| `target_first_same_bar` | `220` | `1054.07%` | `1.813` | `1.23%` | `64.55%` | `0.996` | `-22.35%` | `{"stop_market": 19, "target": 129, "time_open": 72}` |
| `target_gap_open_fill` | `220` | `1054.07%` | `1.813` | `1.23%` | `64.55%` | `0.996` | `-22.35%` | `{"stop_market": 19, "target": 129, "time_open": 72}` |
| `bracket_delay_1bar` | `220` | `1030.87%` | `1.803` | `1.22%` | `64.55%` | `0.990` | `-23.73%` | `{"stop_gap_open": 2, "stop_market": 17, "target": 128, "target_gap_or_open": 1, "time_open": 72}` |

baseline 采用当前研究口径：入场 bar 起 TP/SL 已经存在；同一根同时触达 TP/SL 时按 stop first；stop 开盘穿越按 open 市价退出；target 开盘穿越按目标价成交。

## 价格穿越与同 K 风险

- baseline 退出分布中 stop gap open 为 `0` 笔，target gap/open 为 `0` 笔。
- 同一根 K 同时触达 TP/SL 的交易 `0` 笔；当前 baseline 已按 stop first，`target_first_same_bar` 口径总收益 `1054.07%`，与 baseline 相同，说明当前不是靠 target-first 乐观顺序赚钱。
- 入场 K 内触及任一 bracket 的交易 `3` 笔，其中 entry-bar target `1` 笔、entry-bar stop `2` 笔。
- 若 bracket 延迟到下一根 5m K 才生效，交易数 `220`、总收益 `1030.87%`、PF `1.803`、DD `-23.73%`。收益小幅下降、回撤变差，但未崩塌为负。
- target gap/open 改成 open 成交后，总收益 `1054.07%`、PF `1.813`；与 baseline 接近，说明没有明显依赖 target gap 按较差/较好价格的错配。

## 最短持仓样本

| signal_ts | side | reason | bars | ret_3x | first_stop | first_target | entry_bar_stop | entry_bar_target |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| `2026-02-03 19:05:00+00:00` | `-1` | `stop_market` | `1` | `-7.46%` | `0.0` | `nan` | `True` | `False` |
| `2025-10-29 18:35:00+00:00` | `-1` | `stop_market` | `1` | `-6.57%` | `0.0` | `nan` | `True` | `False` |
| `2026-05-22 18:30:00+00:00` | `-1` | `target` | `1` | `2.48%` | `nan` | `0.0` | `False` | `True` |
| `2026-02-05 15:15:00+00:00` | `-1` | `target` | `2` | `4.86%` | `nan` | `1.0` | `False` | `False` |
| `2026-02-03 18:45:00+00:00` | `-1` | `target` | `2` | `5.28%` | `nan` | `1.0` | `False` | `False` |

这些样本用于排查“开仓后马上按不可达价格平仓”的问题。V6.2.1 的短持仓多来自入场后已有 bracket 被触发；如果实盘 runner 在入场成交后不能立即挂出 reduce-only bracket，必须用 `bracket_delay_1bar` 或真实 dry-run 偏差而不是 baseline 收益做判断。

## 代码级审计

- `load_closed_frame()` 会剔除未闭合 K，并检查 5m 连续性。
- `build_signal()` 使用当前闭合 K 的 OHLC、EMA、ATR 和 HTF spread；入场固定在 `sig_i + 1` 的 open。
- `dir_ret48_bps/dir_ret192_bps` 来自 `close / close.shift(window) - 1`，不是未来收益。
- TP/SL 使用 `ATR14(signal_bar)`，即信号 K 已闭合时可得；没有用入场后 K 的 ATR 调参。
- 组合单仓用 `blocked_until = exit_i`，持仓中出现的新信号被阻塞，不叠仓。
- 当前回测仍是 OHLC bar replay，无法知道同一根 K 内 tick 级先后顺序；同 K TP/SL 已保守 stop first，但 entry-bar order latency 需要 paper/live 日志验证。

## 实盘结论

状态维持为 `dry-run / tiny-notional live audit candidate`，不升级为 production sizing。上线前必须至少记录 `30-50` 笔：信号生成时间、入场订单回报、TP/SL 下单时间与 order id、单边成交后的撤单、timeout 市价单、重启恢复、实际滑点和 SQLite 复盘口径。若真实 runner 出现 bracket 下单延迟、撤单失败或 timeout 偏差，应按 `bracket_delay_1bar` 甚至更保守口径重新评估。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_2_1_live_feasibility_audit.py`
- summary：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-2-1_live_feasibility_summary_2026-06-30.csv`
- trades：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-2-1_live_feasibility_trades_2026-06-30.csv`
- causality：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-2-1_feature_causality_2026-06-30.csv`
- JSON：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-2-1_live_feasibility_2026-06-30.json`
