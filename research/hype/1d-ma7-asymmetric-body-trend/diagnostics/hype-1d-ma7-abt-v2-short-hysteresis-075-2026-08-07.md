# HYPE-1D-MA7-ABT-V2 空头迟滞 0.75 诊断

> 日期：2026-08-07。状态：`explore / diagnostic-only / not promoted / not live-ready`。这是已揭示历史上的单参数诊断，V2 保持不变。

## 结论

只把V2空头MA7迟滞退出从`0.25×ATR7`放宽为`0.75×ATR7`后，主历史净收益由`+322.59%`升至`+350.85%`，MDD保持`-26.81%`，Sharpe由`2.35`升至`2.44`。结果方向正面，但额外延迟一天从V2的`+135.36%`降至`+104.25%`，且实际改善只来自prefit中的2笔空单延后2日退出；不能把已揭示历史上的改良直接写回V2。

登记V2主路径的short hard stop触发为`0次`。`0.75`变体同样为`0次`，short trailing stop也为`0次`；分别关闭short hard stop或trailing stop后，19笔交易和全部主指标逐位不变。

## 冻结变更

- 对照：short `exit_buffer_atr=0.25`；
- 变体：只改short `exit_buffer_atr=0.75`；
- short slope exit仍为`SMA7[t] >= SMA7[t-1]`；
- hard stop仍为`entry + 1.5×ATR7`；
- trailing仍为`lowest_close + 4×ATR7`；
- 其余V2参数、成本、funding、真实`1h`保护路径和强制反手不变。

冻结合同见[空头迟滞0.75诊断合同](../specs/hype-1d-ma7-abt-v2-short-hysteresis-075-contract-2026-08-07.md)。

## 主结果

| 检查 | V2 `0.25` | short `0.75` | 观察 |
| --- | ---: | ---: | --- |
| 全期净收益 | `+322.59%` | `+350.85%` | `+28.26pp` |
| MDD | `-26.81%` | `-26.81%` | 不变 |
| Sharpe | `2.35` | `2.44` | 改善 |
| Profit factor | `8.53` | `8.84` | 改善 |
| 交易数 | `19` | `19` | 不变 |
| `8 bps/fill` | `+316.37%` | `+344.23%` | 改善 |
| 额外延迟一天 | `+135.36%` | `+104.25%` | 明显恶化 |
| `12h`日界 | `+14.50%` | `+35.33%` | 改善；MDD由`-48.23%`收窄至`-41.01%` |
| prefit | `+141.19%` | `+157.31%` | 改善集中于早期历史 |
| 后90日flat-start | `+75.21%` | `+75.21%` | 完全不变 |

最近`1d/7d/1m/3m/6m`逐位不变；`1y`因早期差异的复利传递，从`+299.15%`变为`+325.84%`。12个90日滚动窗口仍全部为正，中位收益由`+34.32%`升至`+36.80%`，最低收益和最差MDD均不变。

## 逐笔变化

主路径仍为8笔long、11笔short。short退出计数从：

```text
V2：迟滞 6，斜率 4，保护stop 0，终点 1
0.75：迟滞 2，斜率 8，保护stop 0，终点 1
```

四笔交易的退出标签从迟滞转为斜率，但只有两笔实际延后：

- `2025-09-20`入场short：`2025-09-29`迟滞退出改为`2025-10-01`斜率退出，单笔净收益`+13.93% -> +17.59%`；
- `2025-11-21`入场short：`2025-11-27`迟滞退出改为`2025-11-29`斜率退出，单笔净收益`+3.35% -> +6.82%`；
- `2025-12-06`与`2026-01-30`入场的两笔只改变同一退出日上的规则归属，不改变成交价。

因此`+28.26pp`组合收益改善，本质上来自两笔早期空单各多持有2日及其后复利，不是更大的样本覆盖。

## Hard stop 与 trailing stop

登记V2主路径11笔short中：

- short hard stop命中：`0次`；
- short trailing stop命中：`0次`；
- short `protective_stop`总命中：`0次`。

`0.75`变体仍是三项均`0次`。关闭hard stop、关闭trailing stop两个归因对照的全期净收益都精确为`+350.8464159893%`，19笔路径不变。这说明在UTC主路径里，`1.5×ATR7` hard stop与`4×ATR7` trailing都只是未咬合的后备保护，真正控制空头退出的是MA7斜率和迟滞。

## 相位与风险解释

最新accepted数据上的23个有效日界相位中：

- V2：19正4负，中位`+29.56%`，最差`-34.11%`，最差MDD`-69.04%`；
- `0.75`：22正1负，中位`+47.75%`，最差`-11.75%`，最差MDD`-55.11%`。

相位检查明显改善，但它不是强制门禁，也不能抵消参数是在已揭示路径上提出和验证的事实。更关键的负面证据是一天额外延迟：变体少1笔long，收益比V2低`31.11pp`、MDD多`4.99pp`，说明更宽迟滞会让退出、cooldown与下一次入场的时序交互更敏感。

## 决定

`0.75`是值得冻结后观察的候选，但当前不修改V2、不登记新版本。若后续要采用，应先定义新的prospective观察起点；不能把本次已揭示历史上的两笔改善当作clean OOS。

## 证据

- [机器摘要](../artifacts/hype_1d_v2_short_hysteresis_075_2026-08-07_summary.json)
- [分期、压力与延迟指标](../artifacts/hype_1d_v2_short_hysteresis_075_2026-08-07_metrics.csv)
- [V2逐笔交易](../artifacts/hype_1d_v2_short_hysteresis_075_2026-08-07_v2_control_trades.csv)
- [`0.75`逐笔交易](../artifacts/hype_1d_v2_short_hysteresis_075_2026-08-07_short_exit_075_trades.csv)
- [近期切片](../artifacts/hype_1d_v2_short_hysteresis_075_2026-08-07_recent.csv)
- [90日滚动窗口](../artifacts/hype_1d_v2_short_hysteresis_075_2026-08-07_rolling_90d.csv)
- [24相位检查](../artifacts/hype_1d_v2_short_hysteresis_075_2026-08-07_phase24.csv)
- [最新延伸](../artifacts/hype_1d_v2_short_hysteresis_075_2026-08-07_latest.csv)
