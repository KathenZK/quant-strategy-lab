# BIN-1H-MHCSML 冻结研究契约（2026-07-18）

## 目标与状态边界

目标是在 Binance USD-M 动态全市场币池中寻找高收益、低回撤、高胜率且可复现的多因子机器学习组合。家族当前为 `explore / not promoted / not live-ready`；历史回测、V1 冻结或未来 OOS 通过均不自动授权 runner、dry-run 或 live。

因子数量不锁死。只有通过覆盖率、未来泄漏、稳定性、相关性和消融审计且能改善严格 OOF 组合效用的因子才进入冻结候选。

## 数据时间切分

| 分区 | UTC 范围 | 用途 | 是否允许选型 |
| --- | --- | --- | --- |
| 历史开发 | `< 2026-04-01 00:00` | nested rolling train/validation/OOF | 是，仅限时间序列门禁 |
| Reused holdout | `2026-04-01 00:00 <= ts < 2026-07-01 00:00` | 已揭示事故诊断、失败机制验证 | 不得作为独立 OOS 或唯一选型依据 |
| Freeze gap / 数据准备 | `2026-07-01 00:00 <= ts < 2026-07-19 00:00` | 只允许数据质量与无标签运行准备 | 禁止读取策略收益、标签和用其调参 |
| Prospective OOS | `2026-07-19 00:00 <= ts < 2026-10-19 00:00` | 冻结候选最终一次性验收 | 严禁选型；结束后只揭示一次 |

这里的 `ts` 是信号 K0 的 open time。最后一个合法信号为 `2026-10-18 20:00 UTC`，其 K1 入场及 48h 持有期到 `2026-10-20 21:00 UTC` 才完整结束；因此一次性绩效揭盲不得早于 `2026-10-20 21:05 UTC`。这只延后标签成熟和验收时间，不扩展选信号窗口。

Prospective OOS 隔离对象包括标签、逐腿收益、组合收益、胜率、回撤、IC、分组收益及任何可反推表现的统计。可在不读取目标的前提下检查文件存在性、键、重复、UTC、schema、闭合 bar 和数据缺口。

## 数据门禁

- 来源：Binance Vision monthly/daily archives 与官方 API；记录下载 URL/路径、checksum、月份和 source。
- 数据：OHLCV、mark price、funding、合约上市/退市与状态、币种/合约映射；必要时补 basis、盘口或衍生品字段，但不得伪造历史。
- 必查：时间连续性、重复键、空值、非法 OHLC、raw/normalized 对齐、quote volume/trade count/VWAP、mark/funding 时间语义、历史退市合约和 point-in-time universe。
- 任一关键 blocker 未解决时停止标签、模型和绩效结论。

## 标签和因子

Kline timestamp 为 bar open time。K0 闭合后计算特征，K1 open 入场，持有 `h` 小时后在 `K(h+1)` open 退出：

```text
gross_h = exit_open / entry_open - 1
long_net_h = gross_h - round_trip_cost - funding_sum_h
short_net_h = -gross_h - round_trip_cost + funding_sum_h
```

期限为 `4/8/12/24/48h`。Long Model 预测 `long_net` 或其横截面相对/超阈值目标；Short Model 直接预测 `short_net`，不得用 long score 的倒序替代；Tail Risk Model 至少覆盖 long/short MAE、未来最大不利波动、极端 squeeze/下跌和收益低分位数。

候选因子覆盖趋势、动量、反转、波动率、下行波动、流动性、成交量、taker flow、funding、mark premium/basis、横截面排名、市场广度、regime、上市年龄、跳空、偏度/尾部、短挤压和相关性拥挤。所有因子只读 K0 及更早数据。

## 模型、验证和组合

- 比较 LightGBM regression、quantile、classification、ranker，Ridge/ElasticNet 等线性模型及简单规则基线。
- 使用 nested rolling walk-forward、purge/embargo、OOF 预测和多随机种子；禁止随机切分和在同一窗口训练后评分。
- 研究 `4/8/12/24/48h` 持有期与 `4/8/12/24h` 决策频率，比较 long-only、short-only、long-short、可变 N 和置信度阈值。
- allocator 以预测净收益、低分位收益、尾部风险、流动性和集中度计算效用；没有正效用时必须空仓，不强制固定多空腿。
- 基础保守敞口先通过，之后才单独报告 3 倍杠杆；任何杠杆版本必须逐时 mark-to-market 并模拟维持保证金、强平和账户损失上限。

## 最终硬门槛

Prospective OOS 必须同时满足：

- 三个月累计收益 `>=18.92%` 且折算年化 `>=100%`；
- 最大回撤 `<=20%`；组合决策胜率 `>=55%`；Sharpe `>=1.5`；PF `>=1.30`；
- 至少 `45` 个有效组合决策和 `300` 条完成腿，至少 `2/3` 月份盈利；
- `1.5x` 成本下仍盈利且回撤 `<=25%`；
- 单一币种正利润贡献 `<=25%`，单月正利润贡献 `<=35%`；
- 多数历史 walk-forward 窗口盈利，因子分组收益稳定，尾部收益与 IC 方向一致；
- LightGBM 在相同 OOF/OOS、成本和组合口径下超过线性与规则基线。

任一门槛失败则记录 `HARD-GATE-FAILED`，状态保持 `not promoted / not live-ready`，不得选择性报告或通过杠杆放大达标。

## 冻结和交付

冻结必须包含数据 manifest、feature list、标签版本、训练窗口、模型参数/seed、模型文件 SHA、allocator、成本、决策频率、持有期、持仓/集中度/空仓规则、测试版本和代码 SHA。冻结后禁止更改上述任何一项；若更改则 prospective OOS 重新计时。

交付包括数据质量报告、收益口径测试、因子清单与消融、OOF 预测、模型/基线比较、逐腿和组合证据、压力测试、冻结 manifest/SHA、主账/decision log、一次性 OOS 报告及不依赖本仓库上下文的外部复现规格。
