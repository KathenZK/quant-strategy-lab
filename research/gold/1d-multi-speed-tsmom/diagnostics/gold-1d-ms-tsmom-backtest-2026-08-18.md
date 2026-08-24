# GOLD-1D-Multi-Speed-TSMOM 黄金多速度 TSMOM 回测（2026-08-18）

- Family：`GOLD-1D-Multi-Speed-TSMOM`（`GOLD-1D-MS-TSMOM`）
- 状态：`explore / not promoted / not live-ready`
- 市场：Stooq `GC.F` Gold-COMEX continuous futures，session-date `1d`
- Raw 数据：`1985-10-01T00:00:00+00:00` → `2021-12-24T00:00:00+00:00`；回测只保留到最后完整月 `2021-11-30T00:00:00+00:00`
- 有效回测：`1986-11-03T00:00:00+00:00` → `2021-11-30T00:00:00+00:00`，共 `8861` 个日收益
- 成本：`0 bps` 对照 + 单边每单位目标仓位换手 `2 bps` 主口径；无单独 roll 成交成本
- 最近切片只作事后审计，不参与任何参数选择

## 结论

Composite 在 `2 bps` 主口径下 CAGR `0.49%`、年化算术收益 `0.81%`、实现波动 `8.08%`、Sharpe `0.101`、最大回撤 `-32.37%`、正收益月份比例 `47.51%`。
三个单速度中历史 Sharpe 最高的是 `12M`；该比较只是固定分支归因，不构成选择或调参。

结果只能视为长期历史形态诊断：主数据虽通过价格序列机械检查，但仍为 `raw_unaccepted`，且截止 2021 年。连续合约换月映射、roll adjustment、结算价语义和显式换月交易成本未核验，因此本轮不登记版本、不支持当前可交易性或 live-ready 结论。

## 全区间四分支 × 两成本版本

| 分支 | 单边成本 bps | CAGR | 年化收益 | 年化波动 | Sharpe | Sortino | 最大回撤 | Calmar | 日胜率 | 正收益月 | 年换手 | 毛总收益 | 净总收益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Composite` | `0` | 0.59% | 0.92% | 8.08% | 0.114 | 0.154 | -31.34% | 0.019 | 50.85% | 47.51% | 5.27 | 23.13% | 23.13% |
| `12M` | `0` | 3.14% | 3.64% | 10.60% | 0.344 | 0.482 | -30.39% | 0.103 | 51.33% | 51.54% | 3.05 | 195.41% | 195.41% |
| `1M` | `0` | -0.94% | -0.38% | 10.61% | -0.036 | -0.048 | -57.30% | -0.016 | 50.42% | 47.03% | 9.48 | -28.21% | -28.21% |
| `3M` | `0` | -1.07% | -0.51% | 10.61% | -0.048 | -0.066 | -50.54% | -0.021 | 49.99% | 45.13% | 5.41 | -31.38% | -31.38% |
| `Composite` | `2` | 0.49% | 0.81% | 8.08% | 0.101 | 0.136 | -32.37% | 0.015 | 50.84% | 47.51% | 5.27 | 23.13% | 18.66% |
| `12M` | `2` | 3.07% | 3.58% | 10.60% | 0.338 | 0.474 | -30.80% | 0.100 | 51.33% | 51.54% | 3.05 | 195.41% | 189.17% |
| `1M` | `2` | -1.13% | -0.57% | 10.61% | -0.053 | -0.072 | -59.44% | -0.019 | 50.41% | 47.03% | 9.48 | -28.21% | -32.83% |
| `3M` | `2` | -1.17% | -0.61% | 10.61% | -0.058 | -0.080 | -50.97% | -0.023 | 49.97% | 45.13% | 5.41 | -31.38% | -33.93% |

说明：年化收益为日均净收益 × `252`；CAGR 使用实际日历跨度；Sharpe/Sortino 的无风险利率为 0。日胜率为正日收益比例，正收益月按月复利收益大于 0 统计。

## 最近区间（Composite，2 bps，audit-only）

| 窗口 | 净收益 | 最大回撤 | Sharpe | 换手 |
| --- | ---: | ---: | ---: | ---: |
| `1d` | 0.12% | 0.00% | n/a | 0.000 |
| `7d` | 0.10% | -0.05% | 4.902 | 0.000 |
| `1m` | 0.06% | -1.39% | 0.216 | 0.448 |
| `3m` | -0.33% | -2.67% | -0.216 | 1.364 |
| `6m` | -5.30% | -6.67% | -1.591 | 3.126 |
| `1y` | -4.58% | -6.67% | -0.890 | 4.264 |

## 分年份（Composite，2 bps）

| 年 | 净收益 | 最大回撤 | 换手 |
| --- | ---: | ---: | ---: |
| `1986`* | 0.09% | -1.24% | 0.153 |
| `1987` | 5.59% | -3.41% | 3.419 |
| `1988` | -3.70% | -8.00% | 6.646 |
| `1989` | -0.25% | -8.31% | 2.917 |
| `1990` | -2.08% | -8.24% | 5.682 |
| `1991` | -5.18% | -7.54% | 5.438 |
| `1992` | -0.02% | -7.14% | 7.439 |
| `1993` | 2.91% | -8.05% | 5.358 |
| `1994` | -7.11% | -7.89% | 7.444 |
| `1995` | -3.84% | -8.39% | 12.795 |
| `1996` | -0.24% | -13.96% | 11.611 |
| `1997` | 12.14% | -8.43% | 6.251 |
| `1998` | -7.88% | -10.42% | 5.061 |
| `1999` | -11.40% | -19.96% | 5.834 |
| `2000` | -2.68% | -5.91% | 5.111 |
| `2001` | -2.25% | -6.23% | 3.815 |
| `2002` | 9.15% | -7.11% | 3.629 |
| `2003` | 6.86% | -8.90% | 3.910 |
| `2004` | -3.30% | -11.82% | 4.106 |
| `2005` | 3.33% | -9.61% | 8.726 |
| `2006` | 12.54% | -7.36% | 2.184 |
| `2007` | 11.31% | -4.64% | 3.597 |
| `2008` | -2.24% | -12.41% | 3.174 |
| `2009` | 2.21% | -6.41% | 3.630 |
| `2010` | 12.39% | -4.64% | 1.953 |
| `2011` | 6.08% | -8.25% | 4.096 |
| `2012` | -2.92% | -3.82% | 4.801 |
| `2013` | 12.23% | -5.79% | 2.579 |
| `2014` | -11.15% | -14.25% | 7.628 |
| `2015` | -5.08% | -8.08% | 6.443 |
| `2016` | -9.58% | -11.43% | 4.673 |
| `2017` | -5.73% | -8.75% | 6.863 |
| `2018` | 4.21% | -4.76% | 5.344 |
| `2019` | 4.06% | -6.86% | 5.485 |
| `2020` | 10.74% | -7.57% | 2.787 |
| `2021`* | -3.58% | -6.67% | 4.247 |

`*` 表示有效样本的首年或末年，不是完整自然年。

## 无未来函数检查

- `1M/3M/12M` 只在每月最后一根可见日线收盘后计算。
- 月末当日收益仍由旧仓位承担；新目标仓位经 `shift(1)` 后从下一交易日收益开始生效。
- 波动率输入先 `shift(1)`，所以月末 `sigma_ann` 不含月末当日收益；EWMA `com=60`、`adjust=False`。
- 四个分支共享 12M warmup 后的同一有效样本，避免用不同起点比较。

## 数据质量

- 保留 raw rows `9154`；price null `0`、重复 `0`、非法 OHLC `0`、机械价格 blocker `0`。
- Volume null `7`；Open Interest null `8`；它们不参与本策略计算。
- Yahoo `GC=F` Kaggle v2 候选有 `441` 行 OHLC 不自洽，已拒绝作为主数据且没有静默修补。
- Stooq `GC.F` 仍缺逐合约/换月/日历/闭合字段核验，`accepted_for_strategy_evidence=false`。

## 证据与复现

- 固定配置：[../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-config.json](../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-config.json)
- 数据审计：[../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-data-audit.json](../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-data-audit.json)
- 汇总：[../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-summary.json](../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-summary.json)
- 指标：[../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-metrics.csv](../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-metrics.csv)
- 月末信号：[../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-month-end-signals.csv](../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-month-end-signals.csv)
- 日路径：[../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-daily-paths.csv](../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-daily-paths.csv)
- 年度结果：[../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-yearly-returns.csv](../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-yearly-returns.csv)
- 分月结果：[../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-monthly-returns.csv](../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-monthly-returns.csv)
- 最近切片：[../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-recent-slices.csv](../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-recent-slices.csv)
- Composite episodes：[../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-episodes.csv](../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-episodes.csv)
- 交互图：[../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-interactive.html](../artifacts/gold-1d-ms-tsmom-baseline-2026-08-18-interactive.html)
- 回测脚本：[../scripts/research_gold_1d_multi_speed_tsmom.py](../scripts/research_gold_1d_multi_speed_tsmom.py)
- 图表脚本：[../scripts/render_gold_1d_multi_speed_tsmom.py](../scripts/render_gold_1d_multi_speed_tsmom.py)

```bash
.venv/bin/python research/gold/1d-multi-speed-tsmom/scripts/fetch_gold_gc_stooq_snapshot.py --run-date 2026-08-18
.venv/bin/python research/gold/1d-multi-speed-tsmom/scripts/research_gold_1d_multi_speed_tsmom.py --run-date 2026-08-18 --allow-untrusted
.venv/bin/python research/gold/1d-multi-speed-tsmom/scripts/render_gold_1d_multi_speed_tsmom.py --run-date 2026-08-18
```

## 状态

`explore / not promoted / not live-ready`。本轮不登记版本；要重开 promotion 讨论，先更换为当前、可核验 roll mapping 的官方或逐合约期货数据。
