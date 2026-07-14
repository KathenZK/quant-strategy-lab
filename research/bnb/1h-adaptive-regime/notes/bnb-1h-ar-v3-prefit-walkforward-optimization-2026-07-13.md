# BNB-1H-Adaptive-Regime-V3 prefit walk-forward 优化 - 2026-07-13

## 结论

本轮只使用 prefit 数据，未计算、未排序、未持久化 reused locked OOS 指标。搜索冻结 V3 的杠杆（EMA `2.5x`、wick `1.0x`）和 merge priority，只分阶段研究 exit/trailing 与过滤强度。

- base K+1 V3（同一边界净化口径）：`3.05x` / `-18.24%` DD / `89.11%` win / `101` trades。
- K+2 V3：`1.36x` / `-31.04%` DD / `79.21%` win / `101` trades。
- 8bps V3：`2.64x` / `-18.42%` DD / `87.25%` win / `102` trades。
- 最终组合评估 `49` 个，通过三场景 + 四时间块 gate `0` 个。

没有候选在不提高杠杆的前提下同时改善年化并通过 K+2、8bps 与 inner walk-forward gate；本轮不产生 V4 候选。继续扩大同一参数面只会增加过拟合风险，应停止参数微调并等待 fresh forward。

- 最高分 near-miss：K+1 `3.83x` / `-22.92%` DD / `84.75%` win / `118` trades；K+2 `3.44x` / `-22.49%` DD / `84.62%` win / `117` trades；8bps `3.50x` / `-23.32%` DD / `83.90%` win / `118` trades。
- near-miss EMA 变化：`{"cooldown_bars": 6, "ema_htf": 377, "max_dist_ema_bps": 500.0, "max_hold_bars": 240, "min_atr_bps": 75.0, "min_rvol": 0.8, "sl_atr": 5.0, "trail_activation_atr": 2.5, "trail_atr": 1.75}`。
- near-miss wick 变化：`{"band_k": 0.5, "cooldown_bars": 24, "max_hold_bars": 48, "min_adx": 28.0, "min_rvol": 1.5, "sl_atr": 5.0, "threshold_high": 0.8, "threshold_low": 0.4, "tp_atr": 1.25}`。
- 它显著修复 K+2 收益，但三场景回撤仍超过 `20%`，因此不是候选。

## 搜索协议

- Stage A：EMA trailing/stop/hold/cooldown；不动信号与杠杆。
- Stage B：EMA 长周期距离、成交量和波动过滤；不动 exit 与杠杆。
- Stage C：wick fixed TP/SL/hold/cooldown；不动过滤与杠杆。
- Stage D：wick 影线阈值、ADX、相对成交量；不动 exit 与杠杆。
- 各坐标面先独立筛选；若单轴没有直接过完整 gate，仅保留 robust score 最靠前的少量诊断种子做一次受限合装，最终组合 gate 不放宽。
- 入选场景：base K+1、delay K+2、8bps/fill；三者均需通过收益、交易数、`<20%` DD、胜率和最大暴露 gate。
- 四个 chronological 90d prefit validation block；每个 block 前保留 10d gap，要求四个 block 均有足够交易、至少三个为正、最差 block DD `<20%`。这些 block 参与选参，不是 fresh OOS。
- prefit 末端按 `entry_delay + max_hold + 1` 小时做 entry purge，避免任何候选依赖 OOS 内退出。

## 分阶段结果

| Phase | Base shortlist | Robust pass | Retained |
| --- | ---: | ---: | ---: |
| `ema_exit` | `144` | `0` | `6` |
| `ema_filter` | `54` | `0` | `6` |
| `wick_exit` | `24` | `0` | `6` |
| `wick_filter` | `162` | `0` | `6` |
| `ema_combined` | `49` | `0` | `6` |
| `wick_combined` | `49` | `0` | `6` |

## K+2 风险归因

| Scenario | Component | Annual | DD | Win | Trades |
| --- | --- | ---: | ---: | ---: | ---: |
| `base_k1` | `ema_pullback` | `2.39x` | `-18.24%` | `82.69%` | `52` |
| `base_k1` | `wick_reject` | `1.20x` | `-7.13%` | `92.73%` | `55` |
| `delay_k2` | `ema_pullback` | `1.28x` | `-34.12%` | `75.47%` | `53` |
| `delay_k2` | `wick_reject` | `0.93x` | `-17.98%` | `78.85%` | `52` |
| `slip_8bps` | `ema_pullback` | `2.11x` | `-18.42%` | `79.25%` | `53` |
| `slip_8bps` | `wick_reject` | `1.17x` | `-8.80%` | `92.73%` | `55` |

- K+2 下 EMA 腿是主要回撤来源，但 wick 腿也从盈利降为亏损；这不是单腿 exit 参数可以完全修复的问题。
- 9 个方向组合均未通过。最稳方向为 EMA `long` + wick `both`：K+1 `2.26x` / `-14.63%` DD / `90.48%` win / `84` trades；K+2 `1.25x` / `-28.06%` DD / `80.49%` win / `82` trades。
- 方向过滤降低了回撤和收益，却没有恢复 K+2 `<20%` DD，因此不作为候选。

## 后续优化判断

1. 停止扩大 trailing、TP/SL、ADX、影线阈值和成交量网格；这些坐标已无候选通过。
2. 下一项可检验机制应是 live-executable 的信号新鲜度：在实际 entry open 检查价格相对 signal close/ATR 的漂移，或在 K+2 时要求最后一根已闭合 K 仍保持趋势/regime；不满足则取消过期信号。
3. 新鲜度机制必须单独开结构实验，只用 prefit inner walk-forward + K+1/K+2/8bps 三场景；自由度限制为少量离散阈值，不与 exit/filter 再做高维联合。
4. 若该结构实验仍不能把 K+2 DD 压回 `<20%` 且保持正向年化，就停止历史调参，保留 V3 等 fresh forward。

## Near-miss 机械降风险压力

| EMA leverage | K+1 annual / DD | K+2 annual / DD | 8bps annual / DD | Pass |
| ---: | --- | --- | --- | --- |
| `2.50x` | `3.83x` / `-22.92%` | `3.44x` / `-22.49%` | `3.50x` / `-23.32%` | `False` |
| `2.25x` | `3.45x` / `-20.99%` | `3.12x` / `-20.40%` | `3.17x` / `-21.25%` | `False` |
| `2.00x` | `3.10x` / `-19.04%` | `2.81x` / `-18.29%` | `2.86x` / `-19.29%` | `False` |
| `1.75x` | `2.77x` / `-17.07%` | `2.53x` / `-16.15%` | `2.58x` / `-17.30%` | `False` |

`2.25x` 仍略穿回撤边界；`2.0x` 回撤合格但没有严格改善 V3 K+1 年化。不会继续搜索 `2.1x/2.15x` 等贴门槛杠杆。

## 数据与执行口径

- Market：Binance USD-M Futures `BNBUSDT` perpetual `1h`。
- 数据：UTC `2024-07-03T06:00:00+00:00` 至 `2026-07-03T05:00:00+00:00`；closed K rows `17520`；missing/duplicate=`0/0`。
- 数据质量：source=`{'binance_futures_kline_api': 17520}`；critical nulls=`0`；raw/normalized mismatch=`0`；OHLCV violations=`0`。
- Funding 固定读取家族 artifact `bnb_binance_funding_history_2y.csv`：rows `2190`，UTC `2024-07-03T08:00:00.001000+00:00` 至 `2026-07-03T00:00:00+00:00`；不依赖会被其他周期抓取覆盖的共享 funding 湖。
- 选参边界：`2024-08-17 06:00:00+00:00` 至 `2026-04-03 06:00:00+00:00`，不读取后段指标。
- 成本：base fee `0.001`/fill + `4 bps`/fill；压力场景为 K+2 或 `8 bps`/fill；均计入历史 funding。
- 执行：闭合 K 信号、下一根或 K+2 open 成交；stop-first；open 穿 stop 按 open；trailing 当前 K 更新、下一根生效。
- trailing 模式下引擎不设置固定 target，因此 `ema_pullback.tp_atr=3.0` 不参与 V3 trailing 出场，也不作为本轮搜索轴。

## Prefit chronological validation 时间块

| Block | Expanding IS end | Gap | Validation block |
| --- | --- | --- | --- |
| `wf_oos_1` | `2025-03-29 06:00:00+00:00` | `2025-03-29 06:00:00+00:00 -> 2025-04-08 06:00:00+00:00` | `2025-04-08 06:00:00+00:00 -> 2025-07-07 06:00:00+00:00` |
| `wf_oos_2` | `2025-06-27 06:00:00+00:00` | `2025-06-27 06:00:00+00:00 -> 2025-07-07 06:00:00+00:00` | `2025-07-07 06:00:00+00:00 -> 2025-10-05 06:00:00+00:00` |
| `wf_oos_3` | `2025-09-25 06:00:00+00:00` | `2025-09-25 06:00:00+00:00 -> 2025-10-05 06:00:00+00:00` | `2025-10-05 06:00:00+00:00 -> 2026-01-03 06:00:00+00:00` |
| `wf_oos_4` | `2025-12-24 06:00:00+00:00` | `2025-12-24 06:00:00+00:00 -> 2026-01-03 06:00:00+00:00` | `2026-01-03 06:00:00+00:00 -> 2026-04-03 06:00:00+00:00` |

## Promotion 边界

本轮只能产生 prefit-only 设计建议。无论是否有候选通过，都不得读取 reused OOS 回头选参，也不得据此登记 candidate、dry-run、handoff 或 live。下一次有效验证必须使用 fresh forward，或在正式 re-freeze 协议下重新建立未读 OOS。

## 产物

- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v3_prefit_walkforward_tune_2026-07-13.json`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v3_prefit_walkforward_phases_2026-07-13.csv`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v3_prefit_walkforward_final_2026-07-13.csv`
