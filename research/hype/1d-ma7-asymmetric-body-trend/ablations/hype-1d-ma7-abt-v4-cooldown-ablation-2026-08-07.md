# HYPE V4 Cooldown 消融

> 日期：2026-08-07。结论：long cooldown在UTC主路径中零影响但无删除收益；short cooldown有明确防反复作用，不能删除。登记V4保持不变。

## 口径

- Binance USD-M `HYPEUSDT` perpetual；accepted `1h`聚合UTC日K；
- 主历史：`2025-05-31`至`2026-07-30 UTC`；约`1x`、固定数量、单仓；
- 每fill手续费`0.001`、基准不利滑点`4 bps`、真实event-time funding；
- 最近`1d/7d/1m/3m/6m/1y`仅作审计，不用于选择；
- 全部结果为post-reveal OAT，不是clean OOS。

冻结定义见[消融合同](../specs/hype-1d-ma7-abt-v4-cooldown-ablation-contract-2026-08-07.md)。

## 主结果

| 变体 | long/short cooldown | 净收益 | MDD | Sharpe | PF | 交易数 |
|---|---|---:|---:|---:|---:|---:|
| `V4_CONTROL` | `2d / 5d` | `+411.23%` | `-26.81%` | `2.669` | `13.516` | 17 |
| `NO_LONG_COOLDOWN` | `0d / 5d` | `+411.23%` | `-26.81%` | `2.669` | `13.516` | 17 |
| `NO_SHORT_COOLDOWN` | `2d / 0d` | `+303.19%` | `-26.81%` | `2.176` | `5.047` | 22 |
| `NO_BOTH_COOLDOWN` | `0d / 0d` | `+303.19%` | `-26.81%` | `2.176` | `5.047` | 22 |

## Long cooldown

在UTC主路径、`8 bps`、额外延迟一天、零funding、`12h`、最近切片、12个90日滚动和最新延伸中，去掉long 2日cooldown都逐笔等价。

24相位并非完全等价：正相位仍为`21/23`，但中位收益由`+38.35%`降至`+34.75%`。因此：

- 它在登记UTC路径上没有实际贡献；
- 删除它也没有任何收益或交易机会改善；
- “主路径零影响”不足以证明线上永远不需要它。

可以把long cooldown视为低活跃风险护栏，但没有证据支持为了简化而修改登记V4。

## Short cooldown

去掉short 5日cooldown新增5笔交易：

- 2025-10-22 short：`-14.21%`；
- 2025-10-24 long：`+3.38%`；
- 2025-11-02 forced short：`+1.37%`；
- 2025-12-25 long：`-4.71%`；
- 2026-01-01 forced short：`-7.95%`。

三笔明显亏损压过两笔小盈利，净收益少`108.04pp`，PF由`13.516`降至`5.047`。`12h`从`+35.33%`降至`-0.98%`，MDD由`-41.01%`扩大至`-63.11%`；24相位最差收益由`-14.97%`恶化至`-49.51%`，最差MDD由`-55.60%`恶化至`-73.47%`。

额外延迟一天反而由`+109.85%`升至`+165.40%`，说明cooldown并非所有场景都提高收益；但主路径、PF、`12h`尾部和最新延伸均支持保留。最后90日完全相同，差异集中在prefit。

## 决定

1. short cooldown有明确历史意义：阻止short退出后过快重入及其后续连锁交易，V4继续保留5日；
2. long cooldown主路径零影响，但删除没有收益且部分相位中位下降，V4继续保留2日；
3. 两侧同时删除在主路径上等价于只删除short cooldown，不采用；
4. 本轮不修改V4、不登记新版本、不推进promotion。

## 证据

- [冻结合同](../specs/hype-1d-ma7-abt-v4-cooldown-ablation-contract-2026-08-07.md)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v4_cooldown_ablation.py)
- [机器摘要](../artifacts/hype_1d_v4_cooldown_ablation_2026-08-07_summary.json)
- [分期/压力/延迟](../artifacts/hype_1d_v4_cooldown_ablation_2026-08-07_metrics.csv)
- [近期切片](../artifacts/hype_1d_v4_cooldown_ablation_2026-08-07_recent.csv)
- [90日滚动](../artifacts/hype_1d_v4_cooldown_ablation_2026-08-07_rolling_90d.csv)
- [24相位](../artifacts/hype_1d_v4_cooldown_ablation_2026-08-07_phase24.csv)
- [最新延伸](../artifacts/hype_1d_v4_cooldown_ablation_2026-08-07_latest.csv)
