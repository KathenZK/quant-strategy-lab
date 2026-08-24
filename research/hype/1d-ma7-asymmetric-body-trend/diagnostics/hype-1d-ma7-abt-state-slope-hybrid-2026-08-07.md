# HYPE-1D-MA7 状态边界 × V2斜率混合诊断

> 状态：`explore / diagnostic-only / not promoted / not live-ready`。V2 不变，不登记新版本。

## 结论

按[首次运行前冻结合同](../specs/hype-1d-ma7-abt-state-slope-hybrid-contract-2026-08-07.md)，把三状态候选的 persistent regime 与 V2 的斜率、非对称边界组合，并另测恢复 V2 风险层的版本。

结果明确失败：

| 变体 | 全期净收益 | MDD | Sharpe | 交易 | 胜率 | PF | 暴露率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 登记 V2 | `+322.59%` | `-26.81%` | `2.35` | 19 | `63.2%` | `8.53` | `41.55%` |
| `HYBRID_CORE` | `-38.33%` | `-70.95%` | `-0.08` | 39 | `30.8%` | `0.72` | `78.17%` |
| `HYBRID_V2_RISK` | `-43.19%` | `-61.08%` | `-0.37` | 33 | `27.3%` | `0.64` | `53.05%` |

V2 的优势不只是 slope。**reclaim 同时承担“趋势事件新鲜度”过滤。** persistent regime 中即使 slope 仍符合方向，价格也可能已经运行多日、处于趋势后半段；允许每天重新入场会把方向确认变成追涨杀跌。

## 冻结变体

- `HYBRID_CORE`：long `+0.25/-0.75×ATR7` 非对称边界、short slope exit，使用 V2 long 1 日/short 2 日 `0.02×ATR7` slope；不要求 reclaim，不设保护与 cooldown。
- `HYBRID_V2_RISK`：CORE 加回 V2 long `1.5×ATR7` trailing、short `1.5×ATR7` hard / `4×ATR7` trailing、max hold 与 `2/5d` cooldown；不做 V2 特有 trailing 反手。

## 分期、压力与延迟

| 变体 | Prefit | 后90日 flat-start | `8 bps` | 延迟一天 | `12h` |
| --- | ---: | ---: | ---: | ---: | ---: |
| V2 | `+141.19%` | `+75.21%` | `+316.37%` | `+135.36%` | `+14.50%` |
| CORE | `-49.96%` | `+11.78%` | `-40.27%` | `-71.03%` | `-76.36%` |
| V2风险层 | `-46.62%` | `+6.44%` | `-44.70%` | `-51.35%` | `-72.66%` |

两种混合版本均在 prefit、压力、延迟和 `12h` 失败；后90日的小幅盈利不能覆盖早期持续亏损。

## Reclaim 新鲜度归因

逐笔检查混合入场是否同时满足原 V2 reclaim：

| 变体 | 总入场 | 通过 V2 reclaim | 未通过 |
| --- | ---: | ---: | ---: |
| CORE | 39 | 8 | 31 |
| V2风险层 | 33 | 3 | 30 |

CORE 中：

- 8 笔通过 V2 reclaim 的 long 合计 PnL `+0.232`；
- 10 笔不通过 reclaim 的 long 合计 PnL `-0.160`；
- 21 笔 short 全部不通过 V2 reclaim，仅 4 胜，合计 PnL `-0.456`；
- CORE short 的14日中位顺向收益为 `-3.37%`，说明 slope 通过不等于 entry timing 有优势。

`slope`回答“MA7当前往哪个方向走”，`reclaim`回答“这是一个新发生、可定义起点的穿越事件吗”。本轮只保留前者，导致持续处于边界外的老趋势反复获得入场资格。

## 风险层作用

V2风险层不是完全无效：

- 暴露率由 `78.17%` 降到 `53.05%`；
- MDD由 `-70.95%` 改善到 `-61.08%`；
- 延迟场景由 `-71.03%` 改善到 `-51.35%`。

但它不能修复错误入场：

- 33 笔中有17笔 protective exit；
- short protective stop 4 笔全部亏损，合计 PnL约 `-0.290`；
- cooldown 令直接反手数从14降到0，却仍有30笔入场不满足 V2 reclaim；
- 主收益进一步从 `-38.33%` 降到 `-43.19%`。

风险层只能限制错误仓位的损失，不能把没有优势的 persistent entry 变成有效信号。

## 近期、滚动与相位

| 变体 | `1m` | `3m` | `6m` | `1y` | 90日滚动盈利 | 有效相位盈利 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V2 | `+17.52%` | `+75.21%` | `+67.21%` | `+299.15%` | `12/12` | `19/23` |
| CORE | `+8.19%` | `+23.05%` | `-28.52%` | `-38.71%` | `6/12` | `2/23` |
| V2风险层 | `-3.39%` | `+6.44%` | `-9.75%` | `-43.11%` | `3/12` | `1/23` |

CORE 相位中位收益 `-47.36%`，风险层为 `-57.77%`；相位 8 因缺 `2026-08-06 08:00 UTC` terminal open 记 unavailable。

## 回答研究问题

1. 状态边界 + slope 没有兼顾 V3 覆盖和 V2 精度；它保留了方向过滤，却丢失了 V2 的事件新鲜度。
2. V2风险层能改善回撤和暴露，但无法修复 persistent regime 的坏入场。
3. 图中“已经越界但不开仓”不是单纯实现缺陷；历史上强制补齐这些机会后，大部分新增入场质量较差。
4. 若以后继续，应测试“一次边界穿越只允许一次入场”的 armed epoch，而不是让持续位于边界外的每一天都拥有重入资格。本轮不事后追加该机制。

## 决策

- `HYBRID_CORE` 和 `HYBRID_V2_RISK` 均不采纳、不登记；
- 保留 V2 的 reclaim、slope、保护和状态；
- 不根据本次已揭示结果追加边界、斜率或 cooldown 调参；
- 交互式路径保留用于检查39笔 persistent entry。

## 证据

- [机器摘要](../artifacts/hype_1d_ma7_state_slope_hybrid_2026-08-07_summary.json)
- [分期/压力/延迟指标](../artifacts/hype_1d_ma7_state_slope_hybrid_2026-08-07_metrics.csv)
- [近期切片](../artifacts/hype_1d_ma7_state_slope_hybrid_2026-08-07_recent.csv)
- [90日滚动](../artifacts/hype_1d_ma7_state_slope_hybrid_2026-08-07_rolling_90d.csv)
- [24相位](../artifacts/hype_1d_ma7_state_slope_hybrid_2026-08-07_phase24.csv)
- [最新延伸](../artifacts/hype_1d_ma7_state_slope_hybrid_2026-08-07_latest.csv)
- [入场质量](../artifacts/hype_1d_ma7_state_slope_hybrid_2026-08-07_entry_quality.csv)
- [CORE交易](../artifacts/hype_1d_ma7_state_slope_hybrid_2026-08-07_hybrid_core_trades.csv)与[路径](../artifacts/hype_1d_ma7_state_slope_hybrid_2026-08-07_hybrid_core_path.csv)
- [风险层交易](../artifacts/hype_1d_ma7_state_slope_hybrid_2026-08-07_hybrid_v2_risk_trades.csv)与[路径](../artifacts/hype_1d_ma7_state_slope_hybrid_2026-08-07_hybrid_v2_risk_path.csv)
- [CORE交互式HTML](../artifacts/hype_1d_ma7_state_slope_hybrid_core_trade_path_2026-08-07.html)
- [复现脚本](../scripts/audit_hype_1d_ma7_abt_state_slope_hybrid.py)
