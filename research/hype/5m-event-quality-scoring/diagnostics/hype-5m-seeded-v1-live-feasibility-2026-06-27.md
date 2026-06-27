# HYPE-5M-Event-Quality-Scoring Seeded V1 Live Feasibility Audit

生成日期：`2026-06-27`

> Superseded：后续 `diagnostics/hype-5m-seeded-v1-strict-seed-audit-2026-06-27.md` 已完成严格 anti-leakage seed-generation 审计，结果为 `-61.16%`，PF `0.843`，最大回撤 `-65.94%`。因此本报告中的 “research lead / paper-audit lead” 仅代表 strict audit 前的固定 seed-universe 状态；V1 当前已下调为 fixed seed-universe diagnostic。

## 结论

- V1 candidate：`no_wick_no_breakout__cfg_side_88_12__q80`。
- 诊断窗口：`2025-06-26 04:20:00+00:00` 到 `2026-06-26 04:20:00+00:00`。
- 固定 seed universe 回放：`549` 笔，收益 `287.61%`，PF `1.425`，单笔 `26.33 bps`，最大回撤 `-16.30%`。
- 近 90 天：`112` 笔，收益 `24.59%`，PF `1.303`，最大回撤 `-16.30%`。
- 近 30 天：`51` 笔，收益 `46.29%`，PF `2.209`，最大回撤 `-5.24%`。

结论：`Seeded V1` 可以登记为当前 research lead / paper-audit lead，但**不能直接实盘，也不应直接 paper-live**。原因不是回放指标差，而是 seed-selection 前视、paper-runner 缺失、真实下单保护窗口、成本压力和重启恢复还没有完成审计。

## V1 仍然依赖打分系统

- 事件源集合：`bb_revert`、`macd_flip`、`trend_rsi_snapback`、`vwap_revert`。
- 移除事件源：`wick_reject`、`micro_breakout`。
- score：`0.875 * cfg_mean + 0.125 * side_mean`。
- 分位门槛：`q80`，每个月只交易当月测试事件中高于历史训练 score 第 80 分位的事件。
- 同一 signal bar 多事件冲突时只保留最高分；持仓期间和 cooldown 内跳过后续事件。

## 成本压力

| extra roundtrip cost | trades | ret | PF | avg bps | DD |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `0.0 bps` | 549 | 287.61% | 1.425 | 26.33 | -16.30% |
| `2.5 bps` | 549 | 238.00% | 1.379 | 23.83 | -17.46% |
| `5.0 bps` | 549 | 194.73% | 1.334 | 21.33 | -18.61% |
| `10.0 bps` | 549 | 124.08% | 1.247 | 16.33 | -20.87% |
| `15.0 bps` | 549 | 70.34% | 1.166 | 11.33 | -23.07% |
| `20.0 bps` | 549 | 29.47% | 1.090 | 6.33 | -29.74% |
| `30.0 bps` | 549 | -25.24% | 0.951 | -3.67 | -43.93% |
| `50.0 bps` | 549 | -75.11% | 0.719 | -23.67 | -78.11% |
| `75.0 bps` | 549 | -93.73% | 0.500 | -48.67 | -94.09% |

## 执行路径特征

- 持仓 bars：mean `38.24`，median `27.0`，p90 `82.2`，max `145`。
- 单笔最差：`-4.06%`；单笔最好：`5.44%`。

### Exit Reasons

| reason | trades | ret | PF | avg bps | DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| `target_limit` | 231 | 4939.00% | inf | 171.84 | 0.00% |
| `time_open` | 187 | -6.65% | 0.941 | -2.92 | -20.44% |
| `stop_market` | 131 | -91.76% | 0.000 | -188.48 | -91.76% |

### Styles

| style | trades | ret | PF | avg bps | DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| `bb_revert` | 91 | 87.70% | 2.637 | 70.85 | -7.65% |
| `macd_flip` | 95 | 51.73% | 1.757 | 46.05 | -13.04% |
| `vwap_revert` | 201 | 34.05% | 1.224 | 16.53 | -16.35% |
| `trend_rsi_snapback` | 162 | 1.53% | 1.033 | 1.93 | -21.53% |

## 月度

| month | trades | ret | PF | avg bps | DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2025_06_partial` | 8 | 2.49% | 1.915 | 31.38 | -1.79% |
| `2025_07` | 44 | 11.39% | 1.442 | 25.97 | -4.66% |
| `2025_08` | 58 | 7.19% | 1.226 | 13.02 | -10.66% |
| `2025_09` | 49 | 23.12% | 2.334 | 43.46 | -6.00% |
| `2025_10` | 53 | 22.20% | 1.515 | 40.60 | -13.22% |
| `2025_11` | 50 | 11.84% | 1.378 | 24.38 | -9.97% |
| `2025_12` | 44 | 2.36% | 1.095 | 7.15 | -15.27% |
| `2026_01` | 42 | 18.36% | 1.834 | 41.49 | -5.48% |
| `2026_02` | 47 | 1.08% | 1.052 | 3.91 | -9.73% |
| `2026_03` | 47 | 25.52% | 2.161 | 49.54 | -3.33% |
| `2026_04` | 25 | -9.99% | 0.514 | -40.80 | -10.13% |
| `2026_05` | 37 | 1.34% | 1.072 | 4.77 | -10.99% |
| `2026_06` | 45 | 34.24% | 1.944 | 68.48 | -5.24% |

## Live-Feasibility Gate

- Data quality：通过已有数据湖检查；但本审计使用固定历史 seed universe，不是从零滚动生成 seed 的严格 OOS。
- Signal timing：回测使用 closed-bar signal + next-open entry，方向正确；实盘需要验证 K 线 close 后计算、下 market order 的延迟是否仍被 `10.73 bps` entry slippage 覆盖。
- Entry fill：回测按 next open 加 entry slippage；真实成交不是保证 next open，必须 paper-runner 对账。
- Protection：回测假设入场后立即存在固定 TP/SL bracket；真实系统存在 entry fill 到 bracket 下单确认之间的无保护窗口，尚未审计。
- Stop behavior：回测使用 stop-first 和 open 穿越按 open 成交，这是保守方向；但真实 stop-market 滑点和 Binance 触发语义仍需实测。
- Fees/slippage：当前 edge 能承受一定额外成本，但额外 `30-50 bps` roundtrip 成本会显著降低收益；仓位放大后 slippage 未建模。
- Restart recovery：未实现/未验证 live runner 状态恢复、已挂订单查询、孤儿单撤单、重复入场保护。
- Missing data：数据湖历史无缺口；实盘缺 K、延迟 K、WebSocket/API 不一致处理未验证。
- Kill switch：尚未定义 max daily loss、max drawdown stop、连续亏损冷却、仓位降档。

## Decision

- 记录为：`HYPE-5M-Event-Quality-Scoring-Seeded-V1`。
- 当前状态：`research lead / paper-audit lead`。
- 不允许状态：`live-ready`、`paper-live-ready`、`dry-run handoff`。
- 下一步必须完成：seed-generation anti-leakage、paper-runner dry-run 对账、真实 order-maintenance 审计、成本/滑点压力、drawdown-control ablation。

## 产物

- JSON：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v1_live_feasibility_2026-06-27.json`
- Stress：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v1_live_feasibility_stress_2026-06-27.csv`
- Monthly：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v1_live_feasibility_monthly_2026-06-27.csv`
- Style：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v1_live_feasibility_style_2026-06-27.csv`
- Reasons：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_seeded_event_quality_v1_live_feasibility_reasons_2026-06-27.csv`
