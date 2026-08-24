# HYPE V3 日线跌破 MA7 反手诊断

> 日期：2026-08-07。结论：**行为实现正确，但历史表现显著失败；不采纳、不登记、不修改V3。**

## 机制

候选不再把long trailing stop当成做空信号：trailing只平多到空仓。只有仍持有long，且前一日`close >= SMA7`、当日`close < SMA7`，才在下一日open平多并反手short；short随后沿用V3退出与保护。

本轮没有私自增加“最少持有N日”。实际6次反手前的long分别持有`4/2/5/1/2/6`日；若“一段时间”要定义成硬阈值，应另立合同，而不是事后选择N。

## 主结果

数据为Binance USD-M `HYPEUSDT` perpetual accepted `1h`聚合UTC日K，冻结历史`2025-05-31`至`2026-07-30`；手续费`0.001/fill`、不利滑点`4 bps/fill`、真实event-time funding、约`1x`。

| 变体 | 净收益 | MDD | Sharpe | PF | 交易 | 含义 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| V3 control | +350.85% | -26.81% | 2.436 | 8.836 | 19 | 当前登记V3 |
| trailing只平仓 | +306.41% | -26.44% | 2.400 | 12.593 | 13 | 删除原7次trailing反手 |
| 日线跌破MA7反手 | **+20.81%** | **-37.23%** | **0.573** | **1.342** | 22 | 本次候选 |

因此旧R-S02确实被删除，但用日线cross替代后，相对“trailing只平仓”少`285.60`个百分点，相对V3少`330.04`个百分点。问题不是成本：候选turnover和成本都低于V3，主要损失来自错误状态切换。

## 六次日线反手

| short开仓 | 反手前long持有/收益 | MA下方距离 | MA7向下斜率/ATR | short结果 | 退出 |
| --- | ---: | ---: | ---: | ---: | --- |
| 2025-07-02 | 4日 / +0.33% | 0.321 ATR | -0.0485 | -9.48% | hard stop |
| 2025-08-29 | 2日 / -6.88% | 0.048 ATR | -0.2976 | +5.27% | slope exit |
| 2026-03-06 | 5日 / -2.50% | 0.140 ATR | -0.3070 | -1.83% | slope exit |
| 2026-03-30 | 1日 / -4.37% | 0.503 ATR | +0.0109 | -2.13% | hysteresis exit |
| 2026-05-17 | 2日 / -5.51% | 0.063 ATR | +0.0071 | -12.27% | hard stop |
| 2026-07-09 | 6日 / +0.58% | 0.452 ATR | -0.3245 | +0.46% | slope exit |

6笔反手short只有2笔盈利，合计动态净PnL为`-0.2361`个初始权益单位。更关键的是，**6笔全部不满足V3自然short所需的向下斜率`>=0.02×ATR7`**；其中2笔还未达到`0.1×ATR7` entry buffer。也就是说，它们都是被V3入场质量层有意拒绝的cross。

## 输在哪里

第一，收盘刚到MA7下方不等于下跌趋势已经形成。6个cross发生时，4个MA7仍明显向上，另外2个向下幅度也不足`0.02×ATR7`。

第二，直接cross同时取消了long的`0.75×ATR7`容错。它把正常回踩变成平多反手，提前截断了多笔后来继续上涨的long：

- `2025-06-28` long在trailing只平仓控制中为`+21.88%`；候选在7月2日只保留`+0.33%`，随后反手short再亏`-9.48%`。
- `2026-03-01` long控制为`+21.11%`；候选变成long `-2.50%`加short `-1.83%`。
- `2026-05-15` long控制为`+47.01%`；候选变成long `-5.51%`加short `-12.27%`。

第三，候选把反手入场和V3原short退出接在一起，却跳过short入场slope；这造成“MA仍向上时开空、下一天又被slope exit/hard stop平掉”的结构冲突。

## 稳健性

- `8 bps`：`+18.72%`；
- 额外延迟一天：`-16.83%`；
- `12h`日界：`+4.22%`；
- flat-start最后90日：`-2.13%`；
- 最近`3m/6m`路径：`-2.13% / -23.38%`；
- 12个90日滚动窗口仅7个为正，中位`+1.84%`、最差`-25.73%`；V3为12/12正、中位`+36.80%`；
- 最新数据上的23个有效日界相位为13正10负，中位`+2.98%`、最差`-38.69%`；V3为22正1负、中位`+47.75%`。

相位是检查项而非硬门禁，但这里与主路径、延迟、滚动和近期窗口共同指向同一失败结论。

## 决定

不把该机制写入V3，也不登记新版本。若目标只是修正“插针trailing不应该自动反手”，当前证据支持的最小改法是**trailing只平仓**：它仍有`+306.41%`、MDD`-26.44%`，明显优于直接日线cross反手；但它同样是身份级变化，若要登记需由用户另行明确命名。

## 证据

- [冻结合同](../specs/hype-1d-ma7-abt-v3-daily-ma7-cross-reversal-contract-2026-08-07.md)
- [机器摘要](../artifacts/hype_1d_v3_daily_ma7_cross_reversal_2026-08-07_summary.json)
- [指标与压力](../artifacts/hype_1d_v3_daily_ma7_cross_reversal_2026-08-07_metrics.csv)
- [候选逐笔交易](../artifacts/hype_1d_v3_daily_ma7_cross_reversal_2026-08-07_daily_cross_reversal_trades.csv)
- [近期切片](../artifacts/hype_1d_v3_daily_ma7_cross_reversal_2026-08-07_recent.csv)
- [90日滚动](../artifacts/hype_1d_v3_daily_ma7_cross_reversal_2026-08-07_rolling_90d.csv)
- [24相位](../artifacts/hype_1d_v3_daily_ma7_cross_reversal_2026-08-07_phase24.csv)
- [完整交易路径HTML](../artifacts/hype_1d_ma7_abt_v3_daily_ma7_cross_reversal_trade_path_2026-08-07.html)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v3_daily_ma7_cross_reversal.py)
- [绘图脚本](../scripts/render_hype_1d_ma7_abt_v3_daily_ma7_cross_reversal_trade_path.py)
