# HYPE V4 ATR-Band Trend State Machine 诊断

> 日期：2026-08-07。结论：该状态机准确实现“MA7为趋势中心、±0.75×ATR7容错、方向slope确认、保护退出后cooldown可重入”，但全期为`-26.40%`、MDD`-55.19%`；不替代V4、不登记新版本。

## 口径

- Binance USD-M `HYPEUSDT` perpetual；accepted `1h`聚合UTC日K；
- 主历史：`2025-05-31`至`2026-07-30 UTC`；约`1x`、固定数量、单仓；
- 每fill手续费`0.001`、基准不利滑点`4 bps`、真实event-time funding；
- 最近`1d/7d/1m/3m/6m/1y`仅作审计，不用于选择；
- 全部结果为post-reveal机制诊断，不是clean OOS。

冻结机制见[诊断合同](../specs/hype-1d-ma7-abt-v4-band-state-machine-contract-2026-08-07.md)。

## 主结果

| 变体 | 净收益 | MDD | Sharpe | PF | 交易数 | 反手 | 保护退出 | cooldown重入 | 暴露 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `V4_CONTROL` | `+411.23%` | `-26.81%` | `2.669` | `13.516` | 17 | 0 | 7 | 0 | `42.02%` |
| `BAND_STATE_MACHINE` | `-26.40%` | `-55.19%` | `-0.002` | `0.832` | 28 | 7 | 20 | 6 | `66.43%` |

候选不再使用fresh reclaim，不再让trailing stop自行反手，也不使用V4的MA迟滞/slope/max-hold日线退出。方向只由完整ATR边界target决定，保护退出只转flat。

## 图中2025-06路径

候选对图中趋势的机械解释如下：

1. 6月10日long仍与V4相同，6月13日trailing退出，单笔`-3.67%`；
2. 6月17–18日虽已在MA7下方，但尚未跌出`MA7-0.75×ATR7`完整下边界；
3. 6月19日close `36.876 < lower 37.103`，short `2d` slope为`+0.2028`，首次形成完整short target；
4. 6月20日open `36.877`开short；
5. 6月29日close `39.775 > upper 39.535`且long slope为`+0.2147`，形成完整long target；
6. 6月30日open平short并反手long。

short从6月20日至30日亏`-7.83%`；随后long至7月17日赚`+12.27%`。

所以图中漏单被消除，但用户选择的`0.75×ATR7+slope`确认直到6月19日收盘才成立，实际入场已接近该段下跌低位；随后反弹触发对侧target，short最终亏损。这个结果不是回测遗漏，而是确认强度与入场延迟的直接代价。

## 失败位置

- 28笔中20笔由保护止损退出，说明“target仍成立时cooldown后可重入”反复暴露于同一方向的失败尝试；
- 6笔被归类为同方向cooldown重入；
- long为13笔、7胜、平均`+4.12%`；short为15笔、4胜、平均`-3.94%`、中位`-7.76%`；
- 保护退出只转flat解决了V4错误forced reversal，但取消V4日线退出后，失败short常一直持有到hard/trailing或很晚的对侧target；
- `0.75×ATR7`降低了MA附近翻转次数，却没有恢复V4 `reclaim`提供的“新事件时点”精度。

## 稳健性

| 检查 | V4 | ATR-band状态机 |
|---|---:|---:|
| `8 bps` | `+404.59%` | `-28.08%` |
| 额外延迟1日 | `+109.85%` | `-31.05%` |
| `12h`日界 | `+35.33%` | `-51.21%` |
| 最后90日flat-start | `+75.21%` | `-8.13%` |
| 90日滚动正窗口 | `12/12` | `6/12` |
| 90日滚动中位 | `+37.02%` | `+1.48%` |
| 90日滚动最差 | `+15.02%` | `-34.76%` |
| 有效相位为正 | `21/23` | `0/23` |
| 相位中位 | `+38.35%` | `-54.76%` |

最近分片为`1m -7.88%`、`3m -8.13%`、`6m -26.77%`、`1y -27.92%`；最新延伸为`-29.96%`、MDD`-55.19%`。

## 决定

1. 用户描述的目标已被明确编码，而不是按单张图手工补交易；
2. 状态机修复了“cross过期”和“保护止损决定反手方向”的语义问题；
3. 但`±0.75×ATR7+slope`完整确认过晚，且允许cooldown后同趋势重入造成大量保护退出；
4. 主路径、最后90日、滚动、延迟、`12h`与全部有效相位均不支持继续采用；
5. 登记V4保持不变，本候选只作失败诊断，不登记V5、不推进promotion。

## 证据

- [冻结合同](../specs/hype-1d-ma7-abt-v4-band-state-machine-contract-2026-08-07.md)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v4_band_state_machine.py)
- [完整交易路径HTML](../artifacts/hype_1d_ma7_abt_v4_band_state_machine_trade_path_2026-08-07.html)
- [机器摘要](../artifacts/hype_1d_v4_band_state_machine_2026-08-07_summary.json)
- [分期/压力/延迟](../artifacts/hype_1d_v4_band_state_machine_2026-08-07_metrics.csv)
- [近期切片](../artifacts/hype_1d_v4_band_state_machine_2026-08-07_recent.csv)
- [90日滚动](../artifacts/hype_1d_v4_band_state_machine_2026-08-07_rolling_90d.csv)
- [24相位](../artifacts/hype_1d_v4_band_state_machine_2026-08-07_phase24.csv)
- [最新延伸](../artifacts/hype_1d_v4_band_state_machine_2026-08-07_latest.csv)
