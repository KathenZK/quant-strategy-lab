# HYPE V4 Short Entry Timing 诊断

> 日期：2026-08-07。结论：两种改法都捕捉了2025-06-17后的下跌，但全历史均弱于登记V4；保留V4不变，不登记新版本。

## 口径

- 市场：Binance USD-M `HYPEUSDT` perpetual；accepted `1h`聚合UTC日K；
- 主历史：`2025-05-31`至`2026-07-30 UTC`；最新延伸另行审计；
- 成本：每fill手续费`0.001`、基准不利滑点`4 bps`、真实event-time funding；
- 仓位：约`1x`、固定数量、单仓、不加仓；
- 最近`1d/7d/1m/3m/6m/1y`仅作审计，不用于选择；
- 全部候选均为post-reveal机制诊断，不是clean OOS。

冻结定义见[诊断合同](../specs/hype-1d-ma7-abt-v4-short-entry-timing-contract-2026-08-07.md)。`SHORT_ENTRY_SLOPE_1D`只改自然short入场为`1d` slope，short退出仍为V4的`2d`；`PERSISTENT_CROSS_2D`保留`2d` slope，但fresh cross在价格持续位于MA7下方时保持armed，无天数过期。

## 主结果

| 变体 | 净收益 | MDD | Sharpe | PF | 交易数 | 暴露 |
|---|---:|---:|---:|---:|---:|---:|
| `V4_CONTROL` | `+411.23%` | `-26.81%` | `2.669` | `13.516` | 17 | `42.02%` |
| `SHORT_ENTRY_SLOPE_1D` | `+297.11%` | `-26.81%` | `2.359` | `6.439` | 17 | `36.85%` |
| `PERSISTENT_CROSS_2D` | `+70.27%` | `-34.63%` | `1.070` | `1.702` | 23 | `36.62%` |

两种改法都不是“没赚到图中那笔空单”，而是该空单及其后续仓位占用改变了整条交易路径。

## 情况一：自然short改为1日斜率

6月17日：

- `close=39.968`，`MA7=41.121`，price reclaim/buffer通过；
- `1d down-slope=+0.0790 >= 0.02`；
- `2d down-slope=-0.0277 < 0.02`。

因此该变体在6月18日open开short，6月28日按`ma7_slope_exit`退出，单笔`+8.41%`。但它在6月28日退出后进入short cooldown，错过V4同日建立、后来盈利`+21.88%`的long。这解释了“抓到下跌却降低组合收益”的第一处关键路径替换。

全期short从V4的9笔增至11笔，胜率由`7/9`降至`8/11`，平均每笔由`+8.27%`降至`+6.13%`；long从8笔降至6笔。它不是灾难性失效，但整体精度与后续long捕获均弱于V4。

该阈值修改不只影响2025-06一组交易。相对V4共出现8项路径变化：两次直接新增的1日slope信号是2025-06-18 short（`+8.41%`）和2026-07-02 short（`-7.59%`）；前者继续改变6月28日long与7月后续short，后者改变7月3日long、7月11日forced short和7月17日natural short。因此“只影响图中short和6月28日long”并不成立。

## 情况二：穿越保持armed，等待2日斜率

6月17日fresh cross被armed；6月18日收盘时：

- 价格仍低于entry buffer；
- `2d down-slope=+0.1597`，首次通过；
- 于6月19日open开short，6月28日退出，单笔`+7.23%`。

所以“不让穿越过期”在图中案例上完全按预期工作。但全期16次armed中14次确认、2次因重新站上MA7失效；确认等待为0日3次、1日5次、2日6次。它把原本只在fresh event当日允许的short扩展成更高覆盖率状态。

代价是short增至17笔，仅8笔盈利，平均每笔降至`+2.81%`；新增亏损包括`-13.00%`、`-11.05%`、`-7.75%`、`-7.09%`等。更重要的是，提前short占用仓位或触发cooldown，错过/推迟多笔long：

- 2025-06-28的`+21.88%` long被错过；
- 2025-08-27的`+10.28%` long被错过，替代long为`-5.97%`；
- 2026-03-01的`+21.11%` long被推迟，替代long只有`+9.20%`；
- 2026-05-15的`+47.01%` long被推迟，替代long只有`+5.28%`。

因此armed逻辑提升了空头召回率，却显著降低short精度，并通过单仓/cooldown继续损害long路径。

## 稳健性

| 检查 | V4 | 1日入场斜率 | 持续穿越 |
|---|---:|---:|---:|
| `8 bps` | `+404.59%` | `+291.93%` | `+67.20%` |
| 额外延迟1日 | `+109.85%` | `+94.50%` | `+21.06%` |
| `12h`日界 | `+35.33%` | `+31.36%` | `-22.15%` |
| 最后90日flat-start | `+75.21%` | `+52.93%` | `+9.79%` |
| 90日滚动正窗口 | `12/12` | `12/12` | `7/12` |
| 90日滚动最差 | `+15.02%` | `+2.36%` | `-24.56%` |
| 有效相位为正 | `21/23` | `19/23` | `14/23` |
| 相位中位 | `+38.35%` | `+33.07%` | `+9.22%` |

最近分片中，1日入场斜率的`1m/3m/6m/1y`均低于V4；持续穿越的`6m=-14.43%`。最新延伸主路径分别为V4`+398.84%`、1日斜率`+279.78%`、持续穿越`+66.24%`。

## 决定

1. 用户指出的逻辑成立：6月17日是明确穿越，完全可以在状态机里保持armed；该变体确实于6月19日开出预期short。
2. 历史结果否定的是“所有fresh cross都无限保持有效”，不是否定图中单笔。无限armed把一次过时风险转化成大量低精度short。
3. `1d`入场slope比无限armed更克制、滚动窗口仍全正，但主路径、最近期、日界相位和延迟均不优于V4。
4. 登记V4保持不变：自然short继续要求fresh reclaim与`2d` slope同日成立；本轮不登记V5、不推进promotion。

## 证据

- [冻结合同](../specs/hype-1d-ma7-abt-v4-short-entry-timing-contract-2026-08-07.md)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v4_short_entry_timing.py)
- [机器摘要](../artifacts/hype_1d_v4_short_entry_timing_2026-08-07_summary.json)
- [分期/压力/延迟](../artifacts/hype_1d_v4_short_entry_timing_2026-08-07_metrics.csv)
- [近期切片](../artifacts/hype_1d_v4_short_entry_timing_2026-08-07_recent.csv)
- [90日滚动](../artifacts/hype_1d_v4_short_entry_timing_2026-08-07_rolling_90d.csv)
- [24相位](../artifacts/hype_1d_v4_short_entry_timing_2026-08-07_phase24.csv)
- [最新延伸](../artifacts/hype_1d_v4_short_entry_timing_2026-08-07_latest.csv)
