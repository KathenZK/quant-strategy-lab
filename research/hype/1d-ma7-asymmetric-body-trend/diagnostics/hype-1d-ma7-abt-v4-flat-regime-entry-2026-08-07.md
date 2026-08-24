# HYPE V4 Flat Regime Entry 诊断

> 日期：2026-08-07。结论：按“flat时当前收盘在MA7一侧且方向slope通过即可入场”的多空对称定义，全期为`-42.91%`、MDD`-73.01%`；不修改V4。

## 口径

- 市场：Binance USD-M `HYPEUSDT` perpetual；accepted `1h`聚合UTC日K；
- 主历史：`2025-05-31`至`2026-07-30 UTC`；最新延伸另行审计；
- 成本：每fill手续费`0.001`、基准不利滑点`4 bps`、真实event-time funding；
- 仓位：约`1x`、固定数量、单仓、不加仓；
- 最近`1d/7d/1m/3m/6m/1y`仅作审计，不用于选择；
- 全部结果为post-reveal机制诊断，不是clean OOS。

冻结定义见[诊断合同](../specs/hype-1d-ma7-abt-v4-flat-regime-entry-contract-2026-08-07.md)。候选不要求前一日cross/reclaim：flat且cooldown归零时，long只要求`close>MA7`与V4 long slope，short只要求`close<MA7`与V4 `2d` short slope；两侧入场buffer均为0。

## 主结果

| 变体 | 净收益 | MDD | Sharpe | PF | 交易数 | 暴露 |
|---|---:|---:|---:|---:|---:|---:|
| `V4_CONTROL` | `+411.23%` | `-26.81%` | `2.669` | `13.516` | 17 | `42.02%` |
| `FLAT_REGIME_ENTRY` | `-42.91%` | `-73.01%` | `-0.370` | `0.751` | 40 | `59.62%` |

候选产生28次自然regime入场信号，其中只有4次也满足原V4 reclaim；其余24次都是V4刻意过滤的“已在MA7一侧、但不是fresh event”的入场。

## 图中2025-06路径

多空对称规则先改变了图中原本的flat状态：

1. 原L01于6月13日trailing退出并拒绝MA7上方反手；
2. 6月15日收盘`41.193 > MA7 41.008`，long `1d` slope为`+0.2314`，因此候选于6月16日open重新做多；
3. 6月17日价格跌到MA7下方，但short `2d` slope未通过；
4. 6月18日short slope通过时，账户仍持有6月16日long，不满足本合同冻结的“flat才自然入场”；
5. 该long直到6月19日21:00才trailing退出并按V4 MA_ONLY反手short。

新long亏`-13.10%`；21:00反手short至6月28日再亏`-1.30%`，并错过V4原本6月28日建立、盈利`+21.88%`的long。

因此，用户澄清的“long也一样”会先让策略在6月16日重新做多。若真实意图是“short条件确认时，即使当前持long也要次日open平多反手short”，那属于另一种`target-side reversal`状态机，不是本轮flat-only入场。

## 交易质量

- V4 long：8笔、5胜、平均`+13.63%`；候选long：16笔、5胜、平均`-0.76%`；
- V4 short：9笔、7胜、平均`+8.27%`；候选short：24笔、8胜、平均`-0.89%`。

失败不是交易成本造成，而是取消freshness后大量震荡期重复入场；V4原本的reclaim在这里承担了低频事件过滤作用。

## 稳健性

| 检查 | V4 | Flat regime |
|---|---:|---:|
| `8 bps` | `+404.59%` | `-44.73%` |
| 额外延迟1日 | `+109.85%` | `-19.00%` |
| `12h`日界 | `+35.33%` | `-50.06%` |
| 最后90日flat-start | `+75.21%` | `-12.63%` |
| 90日滚动正窗口 | `12/12` | `4/12` |
| 90日滚动中位 | `+37.02%` | `-23.64%` |
| 有效相位为正 | `21/23` | `0/23` |
| 相位中位 | `+38.35%` | `-45.95%` |

最近分片为`1m +7.86%`、`3m -11.50%`、`6m -47.61%`、`1y -37.52%`；最新延伸为`-41.60%`、MDD`-73.01%`。

## 决定

1. “当前位于MA7一侧且slope通过即可入场”的持续regime已按多空对称方式完成；
2. 它不是上一轮的pending-cross逻辑，也确实允许前一日与当前日连续处于MA7同侧；
3. 该机制显著增加交易、降低多空精度，所有23个有效日界相位均亏损；
4. 登记V4保持不变，不登记新版本、不推进promotion；
5. 用户随后确认相反regime应直接平仓反手；该独立状态迁移已在[target-side诊断](hype-1d-ma7-abt-v4-target-side-regime-2026-08-07.md)中完成。

## 证据

- [冻结合同](../specs/hype-1d-ma7-abt-v4-flat-regime-entry-contract-2026-08-07.md)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v4_flat_regime_entry.py)
- [机器摘要](../artifacts/hype_1d_v4_flat_regime_entry_2026-08-07_summary.json)
- [分期/压力/延迟](../artifacts/hype_1d_v4_flat_regime_entry_2026-08-07_metrics.csv)
- [近期切片](../artifacts/hype_1d_v4_flat_regime_entry_2026-08-07_recent.csv)
- [90日滚动](../artifacts/hype_1d_v4_flat_regime_entry_2026-08-07_rolling_90d.csv)
- [24相位](../artifacts/hype_1d_v4_flat_regime_entry_2026-08-07_phase24.csv)
- [最新延伸](../artifacts/hype_1d_v4_flat_regime_entry_2026-08-07_latest.csv)
