# HYPE-5M-PBTR-V3.3.1 combo overlay search 2026-06-27

Family id：`HYPE-5M-PBTR`

本报告把组合式风控 overlay 加到全量 V3.3.1 信号：入场即 emergency stop；达到浮盈阈值后把 stop 推到 entry 附近或小盈利；更高浮盈后启动 range10 trailing；若前几根 K 没有达到最小正向推进则 time exit。

样本统一裁剪到本地 1m/5m 重叠区间，以便比较 5m/1m 悲观和乐观口径。

## Prescreen Top 20

| config | mode | trades | total | win | PF | payoff | max_dd |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `em1p25__be1p0__lock0p0__ts2p0__td1p0__fail5_0p3` | `5m_conservative` | `3190` | `-99.92%` | `14.11%` | `0.285` | `1.736` | `-99.92%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p0__fail5_0p3` | `5m_conservative` | `3315` | `-99.93%` | `21.90%` | `0.281` | `1.000` | `-99.93%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p0__fail5_0p5` | `5m_conservative` | `3292` | `-99.93%` | `14.06%` | `0.278` | `1.698` | `-99.93%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p0__fail5_0p5` | `5m_conservative` | `3415` | `-99.94%` | `21.38%` | `0.272` | `1.001` | `-99.94%` |
| `em1p25__be1p0__lock0p25__ts1p5__td1p0__fail5_0p3` | `5m_conservative` | `3408` | `-99.94%` | `36.94%` | `0.270` | `0.461` | `-99.94%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p0__fail3_0p3` | `5m_conservative` | `3392` | `-99.94%` | `12.91%` | `0.268` | `1.810` | `-99.94%` |
| `em1p25__be1p0__lock0p25__ts1p5__td1p0__fail5_0p5` | `5m_conservative` | `3496` | `-99.95%` | `35.84%` | `0.264` | `0.473` | `-99.95%` |
| `em1p25__be1p0__lock0p25__ts2p0__td1p0__fail5_0p3` | `5m_conservative` | `3354` | `-99.94%` | `35.63%` | `0.264` | `0.477` | `-99.94%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p0__fail3_0p3` | `5m_conservative` | `3509` | `-99.95%` | `19.75%` | `0.260` | `1.056` | `-99.95%` |
| `em1p25__be1p0__lock0p25__ts2p0__td1p0__fail5_0p5` | `5m_conservative` | `3442` | `-99.94%` | `34.49%` | `0.256` | `0.487` | `-99.94%` |
| `em1p0__be1p0__lock0p0__ts2p0__td1p0__fail5_0p3` | `5m_conservative` | `3679` | `-99.96%` | `11.72%` | `0.255` | `1.925` | `-99.96%` |
| `em1p0__be1p0__lock0p0__ts1p5__td1p0__fail5_0p3` | `5m_conservative` | `3805` | `-99.97%` | `18.27%` | `0.255` | `1.140` | `-99.97%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p5__fail5_0p3` | `5m_conservative` | `3096` | `-99.92%` | `14.31%` | `0.254` | `1.520` | `-99.92%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p0__fail3_0p5` | `5m_conservative` | `3547` | `-99.95%` | `13.14%` | `0.254` | `1.678` | `-99.95%` |
| `em1p25__be1p0__lock0p25__ts1p5__td1p0__fail3_0p3` | `5m_conservative` | `3592` | `-99.96%` | `33.69%` | `0.253` | `0.498` | `-99.96%` |
| `em1p0__be1p0__lock0p0__ts2p0__td1p0__fail5_0p5` | `5m_conservative` | `3743` | `-99.97%` | `11.70%` | `0.252` | `1.900` | `-99.97%` |
| `em1p0__be1p0__lock0p0__ts1p5__td1p0__fail5_0p5` | `5m_conservative` | `3867` | `-99.97%` | `18.05%` | `0.251` | `1.141` | `-99.97%` |
| `em1p0__be1p0__lock0p0__ts2p0__td1p0__fail3_0p3` | `5m_conservative` | `3781` | `-99.97%` | `11.27%` | `0.251` | `1.979` | `-99.97%` |
| `em1p0__be1p0__lock0p0__ts1p5__td1p0__fail3_0p3` | `5m_conservative` | `3905` | `-99.97%` | `17.54%` | `0.251` | `1.180` | `-99.97%` |
| `em1p0__be1p0__lock0p25__ts1p5__td1p0__fail5_0p3` | `5m_conservative` | `3894` | `-99.97%` | `31.20%` | `0.248` | `0.546` | `-99.97%` |

## 四口径复核 Top 30

| config | mode | trades | total | win | PF | payoff | max_dd |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `em1p25__be1p0__lock0p0__ts2p0__td1p5__fail5_0p3` | `1m_optimistic` | `2893` | `-99.31%` | `18.80%` | `0.443` | `1.913` | `-99.32%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p5__fail5_0p3` | `1m_conservative` | `2893` | `-99.31%` | `18.77%` | `0.443` | `1.915` | `-99.32%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p5__fail5_0p3` | `1m_optimistic` | `2945` | `-99.36%` | `22.68%` | `0.437` | `1.490` | `-99.36%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p5__fail5_0p3` | `1m_conservative` | `2945` | `-99.36%` | `22.65%` | `0.437` | `1.491` | `-99.37%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p5__fail5_0p5` | `1m_optimistic` | `2996` | `-99.44%` | `18.52%` | `0.429` | `1.885` | `-99.45%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p5__fail5_0p5` | `1m_conservative` | `2996` | `-99.44%` | `18.49%` | `0.428` | `1.886` | `-99.45%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p5__fail5_0p5` | `1m_optimistic` | `3048` | `-99.48%` | `22.05%` | `0.421` | `1.488` | `-99.49%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p5__fail3_0p3` | `1m_optimistic` | `3098` | `-99.51%` | `17.30%` | `0.421` | `2.010` | `-99.52%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p5__fail5_0p5` | `1m_conservative` | `3048` | `-99.49%` | `22.01%` | `0.420` | `1.489` | `-99.49%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p5__fail3_0p3` | `1m_conservative` | `3098` | `-99.52%` | `17.27%` | `0.420` | `2.012` | `-99.52%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p0__fail5_0p3` | `1m_optimistic` | `3040` | `-99.57%` | `18.95%` | `0.419` | `1.791` | `-99.57%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p0__fail5_0p3` | `1m_conservative` | `3040` | `-99.57%` | `18.91%` | `0.416` | `1.785` | `-99.58%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p5__fail3_0p3` | `1m_optimistic` | `3150` | `-99.55%` | `20.76%` | `0.414` | `1.581` | `-99.55%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p5__fail3_0p3` | `1m_conservative` | `3150` | `-99.55%` | `20.73%` | `0.414` | `1.582` | `-99.56%` |
| `em1p25__be1p0__lock0p25__ts2p0__td1p5__fail5_0p3` | `1m_optimistic` | `3085` | `-99.55%` | `35.88%` | `0.411` | `0.734` | `-99.56%` |
| `em1p25__be1p0__lock0p25__ts2p0__td1p5__fail5_0p3` | `1m_conservative` | `3085` | `-99.56%` | `35.85%` | `0.410` | `0.734` | `-99.56%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p0__fail5_0p5` | `1m_optimistic` | `3138` | `-99.64%` | `18.64%` | `0.408` | `1.779` | `-99.64%` |
| `em1p25__be1p0__lock0p25__ts1p5__td1p5__fail5_0p3` | `1m_optimistic` | `3100` | `-99.58%` | `36.16%` | `0.406` | `0.718` | `-99.58%` |
| `em1p25__be1p0__lock0p25__ts1p5__td1p5__fail5_0p3` | `1m_conservative` | `3100` | `-99.58%` | `36.13%` | `0.406` | `0.718` | `-99.59%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p0__fail5_0p5` | `1m_conservative` | `3138` | `-99.65%` | `18.61%` | `0.406` | `1.774` | `-99.65%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p0__fail5_0p3` | `1m_optimistic` | `3183` | `-99.68%` | `26.45%` | `0.405` | `1.126` | `-99.68%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p0__fail5_0p3` | `1m_conservative` | `3183` | `-99.68%` | `26.30%` | `0.403` | `1.130` | `-99.69%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p5__fail3_0p5` | `1m_optimistic` | `3267` | `-99.63%` | `17.29%` | `0.401` | `1.917` | `-99.64%` |
| `em1p25__be1p0__lock0p25__ts2p0__td1p5__fail5_0p5` | `1m_optimistic` | `3173` | `-99.62%` | `34.73%` | `0.400` | `0.753` | `-99.62%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p5__fail3_0p5` | `1m_conservative` | `3267` | `-99.64%` | `17.26%` | `0.400` | `1.919` | `-99.64%` |
| `em1p25__be1p0__lock0p25__ts2p0__td1p5__fail5_0p5` | `1m_conservative` | `3173` | `-99.62%` | `34.70%` | `0.400` | `0.753` | `-99.62%` |
| `em1p25__be1p0__lock0p25__ts1p5__td1p5__fail5_0p5` | `1m_optimistic` | `3188` | `-99.64%` | `35.04%` | `0.396` | `0.735` | `-99.64%` |
| `em1p0__be1p0__lock0p0__ts2p0__td1p5__fail5_0p3` | `1m_optimistic` | `3368` | `-99.71%` | `15.38%` | `0.396` | `2.180` | `-99.71%` |
| `em1p25__be1p0__lock0p25__ts1p5__td1p5__fail5_0p5` | `1m_conservative` | `3188` | `-99.64%` | `35.01%` | `0.396` | `0.735` | `-99.64%` |
| `em1p0__be1p0__lock0p0__ts2p0__td1p5__fail5_0p3` | `1m_conservative` | `3368` | `-99.71%` | `15.35%` | `0.396` | `2.182` | `-99.72%` |

## Robust

| config | min_trades | min_total | min_pf | worst_dd |
| --- | ---: | ---: | ---: | ---: |
| `em1p25__be1p0__lock0p0__ts2p0__td1p0__fail5_0p3` | `3040` | `-99.92%` | `0.285` | `-99.92%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p0__fail5_0p3` | `3183` | `-99.93%` | `0.281` | `-99.93%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p0__fail5_0p5` | `3138` | `-99.93%` | `0.278` | `-99.93%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p0__fail5_0p5` | `3279` | `-99.94%` | `0.272` | `-99.94%` |
| `em1p25__be1p0__lock0p25__ts1p5__td1p0__fail5_0p3` | `3298` | `-99.94%` | `0.270` | `-99.94%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p0__fail3_0p3` | `3242` | `-99.94%` | `0.268` | `-99.94%` |
| `em1p25__be1p0__lock0p25__ts1p5__td1p0__fail5_0p5` | `3388` | `-99.95%` | `0.264` | `-99.95%` |
| `em1p25__be1p0__lock0p25__ts2p0__td1p0__fail5_0p3` | `3216` | `-99.94%` | `0.264` | `-99.94%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p0__fail3_0p3` | `3384` | `-99.95%` | `0.260` | `-99.95%` |
| `em1p25__be1p0__lock0p25__ts2p0__td1p0__fail5_0p5` | `3305` | `-99.94%` | `0.256` | `-99.94%` |
| `em1p0__be1p0__lock0p0__ts2p0__td1p0__fail5_0p3` | `3515` | `-99.96%` | `0.255` | `-99.96%` |
| `em1p0__be1p0__lock0p0__ts1p5__td1p0__fail5_0p3` | `3671` | `-99.97%` | `0.255` | `-99.97%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p5__fail5_0p3` | `2893` | `-99.92%` | `0.254` | `-99.92%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p0__fail3_0p5` | `3415` | `-99.95%` | `0.254` | `-99.95%` |
| `em1p25__be1p0__lock0p25__ts1p5__td1p0__fail3_0p3` | `3485` | `-99.96%` | `0.253` | `-99.96%` |
| `em1p0__be1p0__lock0p0__ts2p0__td1p0__fail5_0p5` | `3580` | `-99.97%` | `0.252` | `-99.97%` |
| `em1p0__be1p0__lock0p0__ts1p5__td1p0__fail5_0p5` | `3734` | `-99.97%` | `0.251` | `-99.97%` |
| `em1p0__be1p0__lock0p0__ts2p0__td1p0__fail3_0p3` | `3623` | `-99.97%` | `0.251` | `-99.97%` |
| `em1p0__be1p0__lock0p0__ts1p5__td1p0__fail3_0p3` | `3774` | `-99.97%` | `0.251` | `-99.97%` |
| `em1p0__be1p0__lock0p25__ts1p5__td1p0__fail5_0p3` | `3782` | `-99.97%` | `0.248` | `-99.97%` |
| `em1p25__be1p0__lock0p25__ts2p0__td1p0__fail3_0p3` | `3407` | `-99.95%` | `0.247` | `-99.95%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p5__fail5_0p5` | `2996` | `-99.94%` | `0.246` | `-99.94%` |
| `em1p25__be1p0__lock0p0__ts1p5__td1p0__fail3_0p5` | `3544` | `-99.96%` | `0.246` | `-99.96%` |
| `em1p0__be1p0__lock0p25__ts1p5__td1p0__fail5_0p5` | `3839` | `-99.97%` | `0.245` | `-99.97%` |
| `em1p0__be1p0__lock0p25__ts1p5__td1p0__fail3_0p3` | `3877` | `-99.97%` | `0.243` | `-99.97%` |
| `em1p25__be1p0__lock0p25__ts1p5__td1p0__fail3_0p5` | `3638` | `-99.96%` | `0.241` | `-99.96%` |
| `em1p0__be1p0__lock0p25__ts2p0__td1p0__fail5_0p3` | `3693` | `-99.97%` | `0.239` | `-99.97%` |
| `em1p0__be1p0__lock0p0__ts1p5__td1p0__fail3_0p5` | `3913` | `-99.98%` | `0.239` | `-99.98%` |
| `em1p0__be1p0__lock0p0__ts2p0__td1p0__fail3_0p5` | `3774` | `-99.97%` | `0.239` | `-99.97%` |
| `em1p25__be1p0__lock0p0__ts2p0__td1p5__fail3_0p3` | `3098` | `-99.94%` | `0.239` | `-99.94%` |

## 结论

四口径最佳为 `em1p25__be1p0__lock0p0__ts2p0__td1p0__fail5_0p3`：min trades `3040`，min total `-99.92%`，min PF `0.285`，worst max drawdown `-99.92%`。

结论：这套组合式 overlay 不能救活全量 V3.3.1。它确实把亏损腿更早截断，但全量原始信号质量太差，绝大多数交易没有足够顺风延续来触发保本推进或盈利 trailing，最后变成大量小亏/止损，PF 最高也只有 `0.285`。

这进一步支持前一轮 rescue 结论：不能试图用 overlay 拯救全量双向高频 V3.3.1；有效方向只能是先过滤成低频高质量事件源，例如 deep pullback long-only + 动量/spread 过滤，再单独设计退出。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3-1_combo_overlay.py`
- JSON：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_combo_overlay_2026-06-27.json`
- prescreen CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_combo_overlay_prescreen_2026-06-27.csv`
- full CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_combo_overlay_full_2026-06-27.csv`
- robust CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_combo_overlay_robust_2026-06-27.csv`
- top trades CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3-1_combo_overlay_top_trades_2026-06-27.csv`
