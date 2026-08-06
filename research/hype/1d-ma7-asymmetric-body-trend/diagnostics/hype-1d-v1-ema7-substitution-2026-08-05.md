# HYPE V1 EMA7 零调参替换诊断

## 结论

只把 `HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 的 `SMA7` 换成 `EMA7` 后，成本后组合仍为正，但显著弱于 V1：

- SMA7 V1：`+293.20%`，MDD `-26.44%`，13 笔；
- EMA7：`+35.93%`，MDD `-46.15%`，26 笔；
- EMA7 的 `8 bps/fill` 压力结果为 `+33.16%`，额外延迟一天为 `+68.59%`；
- EMA7 换 `12h` 日界后从 `+35.93%` 变为 `-19.34%`，相位符号翻转；
- EMA7 long-only / short-only 分别 `-30.94% / -17.89%`，组合正收益依赖多空互斥和优先级改变交易集合。

EMA7 没有替代 SMA7 V1 的证据基础，也没有解决相位、低样本和首日保护问题。它只是已揭示历史上的 indicator-substitution observation，不登记新版本，V1 身份保持 SMA7。

## 冻结替换

- EMA 定义：`EMA(span=7, adjust=False, min_periods=7)`。
- 仅替换所有入场、退出和斜率判断使用的 `SMA7`。
- `ATR7`、多空阈值、hard/trailing stop、最长持仓、冷却、多头优先级全部保持 V1。
- 市场/成本：Binance USD-M `HYPEUSDT` perpetual；手续费 `0.001/fill`，基准滑点 `4 bps/fill`，实际事件级 funding。
- 数据：`2025-05-31` 至 `2026-07-30 UTC` 的 425 个完整日；底层 `1h` 数据质量 blocker 为 `0`。

## 全窗口比较

| 指标 | 净收益 | MDD | Sharpe | PF | 交易数 | Long / Short |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SMA7 V1 | `+293.20%` | `-26.44%` | `2.35` | `12.41` | `13` | `8 / 5` |
| EMA7 | `+35.93%` | `-46.15%` | `0.72` | `1.25` | `26` | `21 / 5` |
| Buy-and-hold | `+50.82%` | — | — | — | — | — |

EMA7 的绝对收益为正，但比 buy-and-hold 低约 `14.88pp`，风险和换手均明显增加。

## 时间切分

| 指标/窗口 | Prefit `335d` | 最后 `90d` flat-start | 全期 |
| --- | ---: | ---: | ---: |
| SMA7 combined | `+143.70%` | `+61.35%` | `+293.20%` |
| EMA7 combined | `+15.59%` | `+17.60%` | `+35.93%` |
| EMA7 long-only | `-36.29%` | `+8.41%` | `-30.94%` |
| EMA7 short-only | `-3.45%` | `-14.95%` | `-17.89%` |

EMA7 的两个单腿全期都亏损；combined 不是单腿优势相加，而是多头优先、单仓互斥和冷却使部分亏损交易没有发生。该交互不应被解释成独立趋势因子。

## 成本与延迟

| 场景 | 净收益 | MDD | PF |
| --- | ---: | ---: | ---: |
| EMA7 基准 `4 bps` | `+35.93%` | `-46.15%` | `1.25` |
| EMA7 `8 bps` | `+33.16%` | `-46.36%` | `1.24` |
| EMA7 额外延迟一天 | `+68.59%` | `-53.43%` | `1.56` |

延迟后收益改善不代表可执行性更强，而是再次说明具体入场日对结果影响很大。

## 相位

| 方向 | UTC `0h` | `12h` | 判断 |
| --- | ---: | ---: | --- |
| Combined | `+35.93%` | `-19.34%` | 符号翻转，失败 |
| Long-only | `-30.94%` | `-10.63%` | 两相位均亏损 |
| Short-only | `-17.89%` | `-12.16%` | 两相位均亏损 |

EMA7 combined 的正收益完全不能通过 bar-alignment gate。

## 近期切片

| 方向 | `1d` | `7d` | `1m` | `3m` | `6m` | `1y` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Combined | `0.00%` | `-0.54%` | `-8.96%` | `+17.60%` | `+13.17%` | `+20.14%` |
| Long-only | `0.00%` | `-6.21%` | `-16.08%` | `+8.41%` | `-4.29%` | `-38.96%` |
| Short-only | `0.00%` | `-0.54%` | `-5.14%` | `-14.95%` | `-24.38%` | `-13.91%` |

最近一个月 combined 与两个单腿均为负。

## 滚动窗口

步长 `30d` 的 12 个 `90d` flat-start 窗口：

- SMA7 combined：`12/12` 为正，中位 `+33.58%`；
- EMA7 combined：`7/12` 为正，中位 `+8.29%`；
- EMA7 long-only：`6/12` 为正，中位 `+3.49%`；
- EMA7 short-only：`5/12` 为正，中位 `-4.91%`。

## 决策

1. `HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 继续固定 `SMA7`。
2. EMA7 不登记为 V1.1/V2，不推进 promotion。
3. 不在已揭示历史上继续搜索 EMA span 或重新调配 V1 阈值。

## 证据

- [机器摘要](../artifacts/hype_1d_v1_ema7_substitution_summary_2026-08-05.json)
- [指标表](../artifacts/hype_1d_v1_ema7_substitution_metrics_2026-08-05.csv)
- [近期切片](../artifacts/hype_1d_v1_ema7_substitution_recent_2026-08-05.csv)
- [日界相位](../artifacts/hype_1d_v1_ema7_substitution_phase_2026-08-05.csv)
- [滚动窗口](../artifacts/hype_1d_v1_ema7_substitution_rolling_90d_2026-08-05.csv)
- [EMA7 交易](../artifacts/hype_1d_v1_ema7_substitution_trades_2026-08-05.csv)
- [EMA7 路径](../artifacts/hype_1d_v1_ema7_substitution_path_2026-08-05.csv)
- [复现脚本](../scripts/audit_hype_1d_v1_ema7_substitution.py)
