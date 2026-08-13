# HYPE V4 Target-Side Regime 诊断

> 日期：2026-08-07。结论：按用户确认，反向regime出现时于下一日open平原仓并立即反手；图中6月路径被正确捕捉，但全期为`-44.31%`、MDD`-73.55%`，不修改V4。

## 口径

- 市场：Binance USD-M `HYPEUSDT` perpetual；accepted `1h`聚合UTC日K；
- 主历史：`2025-05-31`至`2026-07-30 UTC`；最新延伸另行审计；
- 成本：每fill手续费`0.001`、基准不利滑点`4 bps`、真实event-time funding；
- 仓位：约`1x`、固定数量、单仓、不加仓；
- 最近`1d/7d/1m/3m/6m/1y`仅作审计，不用于选择；
- 全部结果为post-reveal机制诊断，不是clean OOS。

冻结定义见[诊断合同](../specs/hype-1d-ma7-abt-v4-target-side-regime-contract-2026-08-07.md)：当前close位于MA7一侧且该方向V4 slope通过即形成target；若当前持反侧仓位，下一日open平仓并立即反手，不等待原仓退出。

## 主结果

| 变体 | 净收益 | MDD | Sharpe | PF | 交易数 | 直接反手 | 暴露 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `V4_CONTROL` | `+411.23%` | `-26.81%` | `2.669` | `13.516` | 17 | 0 | `42.02%` |
| `TARGET_SIDE_REGIME` | `-44.31%` | `-73.55%` | `-0.351` | `0.747` | 49 | 17 | `69.72%` |

## 图中2025-06路径

该机制严格实现了用户要求：

1. 6月15日close仍在MA7上且long slope通过，于6月16日open重开long；
2. 6月18日close仍在MA7下且short `2d` slope已通过；
3. 6月19日00:00平long并立即反手short，不再要求6月17日fresh cross，也不等待long trailing；
4. long亏`-4.68%`；short持有至6月28日，赚`+7.23%`；
5. 6月27日long target确认，6月28日open再由short反手long；该long至7月8日只赚`+4.60%`，而V4原6月28日long为`+21.88%`。

因此目标侧反手解决了图中的时序问题，但同一规则也会更早切断后续趋势仓。

## 全期交易质量

- 共49笔，17次目标侧直接反手，暴露由`42.02%`升至`69.72%`；
- long：22笔、7胜、平均`-1.00%`、中位`-4.62%`；
- short：27笔、10胜、平均`-0.50%`、中位`-3.33%`；
- V4原本为long `5/8`胜、平均`+13.63%`，short `7/9`胜、平均`+8.27%`。

失败来自持续regime在震荡期频繁切换，而不是漏掉6月short。取消reclaim freshness后，MA7侧别+slope不足以区分新趋势与旧趋势中的暂时反向。

## 稳健性

| 检查 | V4 | Target-side regime |
|---|---:|---:|
| `8 bps` | `+404.59%` | `-46.46%` |
| 额外延迟1日 | `+109.85%` | `-54.33%` |
| `12h`日界 | `+35.33%` | `-5.69%` |
| 最后90日flat-start | `+75.21%` | `+14.74%` |
| 90日滚动正窗口 | `12/12` | `4/12` |
| 90日滚动中位 | `+37.02%` | `-19.79%` |
| 有效相位为正 | `21/23` | `4/23` |
| 相位中位 | `+38.35%` | `-45.62%` |

最近分片为`1m +13.00%`、`3m +14.95%`、`6m -37.78%`、`1y -34.15%`；最新延伸为`-45.62%`、MDD`-73.55%`。

## 决定

1. 用户要求的“当前持反侧仓时，下一日open平仓并反手”已经完整实现；
2. 它确实在6月19日00:00建立预期short，但全期和稳健性明显失败；
3. 失败说明不能把“MA7侧别+slope”直接当作持续目标仓位；V4的reclaim freshness仍是主要精度来源；
4. 登记V4保持不变，不登记新版本、不推进promotion。

## 证据

- [冻结合同](../specs/hype-1d-ma7-abt-v4-target-side-regime-contract-2026-08-07.md)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v4_target_side_regime.py)
- [机器摘要](../artifacts/hype_1d_v4_target_side_regime_2026-08-07_summary.json)
- [分期/压力/延迟](../artifacts/hype_1d_v4_target_side_regime_2026-08-07_metrics.csv)
- [近期切片](../artifacts/hype_1d_v4_target_side_regime_2026-08-07_recent.csv)
- [90日滚动](../artifacts/hype_1d_v4_target_side_regime_2026-08-07_rolling_90d.csv)
- [24相位](../artifacts/hype_1d_v4_target_side_regime_2026-08-07_phase24.csv)
- [最新延伸](../artifacts/hype_1d_v4_target_side_regime_2026-08-07_latest.csv)
