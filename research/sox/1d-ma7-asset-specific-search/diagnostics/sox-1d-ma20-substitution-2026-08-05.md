# SOX 日线 MA20 零调参替换诊断

## 结论

保持 SOX development-selected 的多空参数和 `ATR7` 不变，只把信号均线从 `SMA7` 换成 `SMA20` 后：

- Combined 全历史由 `+200.29%` 降为 `+162.47%`；
- MDD 从 `-93.47%` 显著改善到 `-60.62%`；
- 2010 年前 backward 从 `-79.36%` 改善为 `+3.78%`；
- 交易数从 `447` 降到 `271`，`10 bps/fill` 后从 `+22.79%` 改善到 `+52.69%`；
- 2021+ researcher-exposed holdout 为 `+77.33%`，低于 MA7 的 `+111.06%`，但示意摩擦后仍为 `+63.38%`。

MA20 明显缓和了 MA7 的早期崩溃和交易磨损，但没有形成长期超额：全历史 buy-and-hold 为 `+9,725.06%`，MA20 combined 年化仅约 `3.04%`。额外延迟一 session 后全历史变为 `+355.26%`，也说明时序敏感性很强。保持 `explore / not promoted / not live-ready`，不登记。

## 冻结替换

- 唯一变化：`SMA7` 改为 `SMA20`。
- `ATR7`、多空参数、入场/退出模式、ATR buffer、hard/trailing stop、max-hold、cooldown 和多头优先级全部不变。
- 参数仍来自 MA7 的 2010–2020 development 搜索；没有根据 MA20 结果重选。
- 完整条件见 [MA20 替换合同](../specs/sox-1d-ma20-substitution-contract-2026-08-05.md)。
- 数据仍为 Yahoo `^SOX` `1994-05-04` 至 `2026-08-04`；指数不可直接交易，主结果为零成本路径诊断。

## Combined：MA7 与 MA20

| Window | MA7 | MA7 MDD | MA20 | MA20 MDD | MA20 `10 bps/fill` | MA20 延迟一 session | Buy-and-hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2010 年前 backward | `-79.36%` | `-93.47%` | `+3.78%` | `-56.71%` | `-21.35%` | `+58.40%` | `+202.20%` |
| 2010–2020 development | `+584.29%` | `-28.31%` | `+41.60%` | `-39.17%` | `+17.97%` | `+48.56%` | `+675.23%` |
| 2021+ exposed holdout | `+111.06%` | `-32.21%` | `+77.33%` | `-38.06%` | `+63.38%` | `+92.20%` | `+319.38%` |
| Full | `+200.29%` | `-93.47%` | `+162.47%` | `-60.62%` | `+52.69%` | `+355.26%` | `+9,725.06%` |

MA20 full 的 Sharpe 为 `0.250`、profit factor 为 `1.205`、年化因子为 `1.0304`、暴露率约 `33.88%`。它降低了交易频率和极端回撤，却把 development 收益压缩得非常明显。

## 单腿

| Variant | Backward | Development | 2021+ holdout | Full | Full MDD | Full `10 bps/fill` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MA20 long-only | `-27.69%` | `+83.94%` | `+37.95%` | `+81.81%` | `-81.27%` | `+26.84%` |
| MA20 short-only | `+47.51%` | `-38.76%` | `-0.32%` | `-9.96%` | `-58.24%` | `-25.59%` |

单独看，原 long-only 参数在 MA20 上仍有严重 backward 回撤；原 short-only 参数只在 2010 年前有效，2010 后失去 edge。Combined 使用的是配对搜索中的另一组 long/short 参数，其交互结果优于这两个独立最优单腿，不能把单腿收益直接相加。

## 稳定性

| Variant | 正收益年度 | 年度中位 | 正收益滚动三年 | 三年中位 | 最差三年 |
| --- | ---: | ---: | ---: | ---: | ---: |
| MA20 combined | `18/33` | `+2.24%` | `19/30` | `+12.29%` | `-42.78%` |
| MA20 long-only | `15/33` | `-1.09%` | `16/30` | `+5.91%` | `-53.65%` |
| MA20 short-only | `12/33` | `-3.06%` | `11/30` | `-4.20%` | `-29.91%` |

MA7 combined 是 22/33 个年度和 20/30 个滚动三年为正，最差三年 `-82.34%`。因此 MA20 改善了最差窗口深度，但没有提高正收益窗口命中率。

最近 `1m/3m/6m/1y` 的 MA20 combined 分别为 `-4.93%/-12.11%/+11.34%/+29.30%`；近期短窗口并不一致。

## 判定

MA20 比 MA7 更平滑，确实降低了交易频率、成本侵蚀和跨年代灾难，但仍不能视为通过：

1. full CAGR 约 `3.04%`，远低于 buy-and-hold 约 `15.29%`；
2. MDD `-60.62%` 仍不可接受；
3. backward 在示意摩擦后转为 `-21.35%`；
4. 一 session 延迟导致收益大幅变化，时序敏感；
5. 年度命中率低于 MA7；
6. `^SOX` 不可直接交易，且没有 clean prospective OOS。

因此 MA20 只保留为风险形态更平滑的零调参 observation，不登记、不 promotion。

## 证据

- [机器摘要](../artifacts/sox_1d_ma20_substitution_summary_2026-08-05.json)
- [窗口指标](../artifacts/sox_1d_ma20_substitution_metrics_2026-08-05.csv)
- [逐年窗口](../artifacts/sox_1d_ma20_substitution_calendar_years_2026-08-05.csv)
- [滚动三年](../artifacts/sox_1d_ma20_substitution_rolling_3y_2026-08-05.csv)
- [近期切片](../artifacts/sox_1d_ma20_substitution_recent_2026-08-05.csv)
- [完整交易](../artifacts/sox_1d_ma20_substitution_trades_2026-08-05.csv)
- [复现脚本](../scripts/audit_sox_1d_ma20_substitution.py)
