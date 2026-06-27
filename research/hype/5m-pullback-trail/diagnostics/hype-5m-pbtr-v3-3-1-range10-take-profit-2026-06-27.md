# HYPE-5M-PBTR-V3.3.1 range10 take-profit overlay 2026-06-27

Family id：`HYPE-5M-PBTR`

本报告测试一个线上可执行的早停止盈 overlay：开仓后持续轮询，若浮盈已经达到信号 K 最近 10 根 5m K 的平均振幅，则立刻 reduce-only 市价平仓，不再进入后续 stop-arm / trailing 流程。

回测近似：5m 口径用 5m OHLC 判断是否触达目标；1m 口径用本地 1m OHLC 判断是否触达目标。触达后按目标价再扣平仓滑点和手续费。

注意：由于本地 1m 数据从 `2026-03-25` 才开始，本报告统一裁剪到 5m/1m 重叠区间，避免无 1m 覆盖的早期样本低估轮询触发率。

本次使用 1m 数据：`True`。

## 结果

| 口径 | 交易数 | 累计收益 | 年化 | 胜率 | PF | payoff | 最大回撤 | TP exit | deadline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `5m_conservative_range10_take_profit` | `2421` | `-96.90%` | `0.00x` | `53.12%` | `0.564` | `0.498` | `-96.91%` | `50.68%` | `37.38%` |
| `5m_optimistic_range10_take_profit` | `2489` | `-97.06%` | `0.00x` | `50.94%` | `0.557` | `0.536` | `-97.09%` | `48.81%` | `30.49%` |
| `1m_conservative_range10_take_profit` | `2462` | `-97.36%` | `0.00x` | `51.26%` | `0.548` | `0.521` | `-97.39%` | `49.11%` | `33.27%` |
| `1m_optimistic_range10_take_profit` | `2489` | `-97.06%` | `0.00x` | `50.94%` | `0.557` | `0.536` | `-97.09%` | `48.81%` | `30.49%` |

## 诊断

- `1m_conservative`：TP exit `49.11%`；deadline `33.27%`；stop-market `17.42%`；gap 市价 `0.20%`；target bps P10/P50/P90 `18.932/35.987/66.314`。
- `1m_optimistic`：TP exit `48.81%`；deadline `30.49%`；stop-market `20.57%`；gap 市价 `0.12%`；target bps P10/P50/P90 `18.927/35.952/66.154`。
- `5m_conservative`：TP exit `50.68%`；deadline `37.38%`；stop-market `11.48%`；gap 市价 `0.45%`；target bps P10/P50/P90 `18.929/36.030/66.628`。
- `5m_optimistic`：TP exit `48.81%`；deadline `30.49%`；stop-market `20.57%`；gap 市价 `0.12%`；target bps P10/P50/P90 `18.927/35.952/66.154`。

## 结论

最佳口径为 `5m_conservative_range10_take_profit`：交易 `2421` 笔，累计收益 `-96.90%`，PF `0.564`，最大回撤 `-96.91%`。

range10 早停止盈把约一半交易提前平仓，胜率提升到约 `51%-53%`，但单笔平均赢利被压得过小，payoff 只有约 `0.50-0.54`。四个口径 PF 都只有约 `0.55-0.56`，总收益和最大回撤仍接近归零。

结论：这个 5 秒轮询早停止盈 overlay 不能救回原始 V3.3.1。它更像是把尾部亏损换成大量过早止盈，改善胜率观感但破坏盈亏比。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3-1_range10_take_profit.py`
- JSON：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_range10_take_profit_2026-06-27.json`
- 汇总 CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_range10_take_profit_summary_2026-06-27.csv`
- 交易 CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_range10_take_profit_trades_2026-06-27.csv`
- 诊断 CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_range10_take_profit_diagnostics_2026-06-27.csv`
