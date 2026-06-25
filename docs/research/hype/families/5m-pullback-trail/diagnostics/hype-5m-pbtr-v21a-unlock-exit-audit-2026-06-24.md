# HYPE-5M-PBTR-V2.1A unlock exit 审计 2026-06-24

Family id：`HYPE-5M-PBTR`

本报告专门复核 V2.1A dry-run 中观察到的现象：多数交易似乎在 `min_hold_bars=6` 结束后，第 7 根 K 计算 trailing 后直接退出，短样本仍然赚钱。

## 对比口径

- `原始回测`：V2.1A 既有实盘成本回测。前 6 根 K 不触发退出，第 7 根起如果 stop 被触发，按计算出的 stop 价成交。
- `第7根开盘直接平仓`：信号入场后固定持有 6 根 K，第 7 根 K 开盘按市价平仓。
- `第7根开盘 trailing 判定`：第 7 根开盘前根据前 6 根 K 计算 active stop；若已经穿越，则按第 7 根开盘市价平仓，否则继续挂 stop-market。
- `第7根收盘 trailing 判定`：第 7 根收盘后用已收盘 K 计算 trailing；若 close 已穿越 active stop，则按 close 平仓。

## 全样本结果

| 口径 | 交易数 | 年化 | 总收益 | 胜率 | PF | payoff | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `原始回测` | `3146` | `352.15x` | `51249.39%` | `51.40%` | `2.79` | `2.64` | `-6.62%` |
| `第7根开盘直接平仓` | `3181` | `0.00x` | `-99.83%` | `38.26%` | `0.54` | `0.87` | `-99.84%` |
| `第7根开盘 trailing 判定` | `3145` | `0.00x` | `-99.84%` | `37.71%` | `0.54` | `0.88` | `-99.85%` |
| `第7根收盘 trailing 判定` | `2958` | `0.00x` | `-99.86%` | `36.51%` | `0.54` | `0.94` | `-99.86%` |

## 第7根原始 stop 子集

| 子集 | 交易数 | 平均单笔 1x 收益 | 胜率 | PF |
| --- | ---: | ---: | ---: | ---: |
| `original_stop_bars_held_7` | `2746` | `0.13%` | `45.88%` | `1.98` |
| `unlock_open_market_all` | `3145` | `-0.20%` | `37.71%` | `0.54` |
| `unlock_open_market_unlock_exit_only` | `2171` | `-0.51%` | `19.90%` | `0.17` |

原始回测中，第 7 根 K 触发 stop 的交易有 `2746` 笔，PF 接近 `1.98`。这解释了为什么 dry-run 看到大量第 7 根退出时会感觉像有 edge：研究回测里这个子集确实是赚钱的。

但关键差异是成交价格。原始回测假设第 7 根 bar 内触发后能按计算出的 stop 价成交；如果实盘是在第 7 根开盘或收盘发现“已经不能继续拿”，然后用当前市价/close 平仓，全样本 PF 只有约 `0.54`。

## 最近窗口

| 口径 | 窗口 | 交易数 | 收益 | 胜率 | PF | 最大回撤 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `normal_original` | `recent_1d` | `7` | `-0.60%` | `28.57%` | `0.38` | `-1.83%` |
| `normal_original` | `recent_2d` | `21` | `1.91%` | `42.86%` | `1.79` | `-1.83%` |
| `normal_original` | `recent_3d` | `26` | `2.76%` | `46.15%` | `1.98` | `-1.83%` |
| `normal_original` | `recent_7d` | `73` | `10.57%` | `46.58%` | `2.05` | `-5.83%` |
| `normal_original` | `recent_30d` | `413` | `150.11%` | `49.15%` | `2.83` | `-5.83%` |
| `fixed_unlock_open` | `recent_1d` | `7` | `-3.02%` | `0.00%` | `0.00` | `-3.38%` |
| `fixed_unlock_open` | `recent_2d` | `21` | `-3.49%` | `33.33%` | `0.47` | `-4.12%` |
| `fixed_unlock_open` | `recent_3d` | `26` | `-3.50%` | `34.62%` | `0.54` | `-4.12%` |
| `fixed_unlock_open` | `recent_7d` | `73` | `-18.24%` | `34.25%` | `0.43` | `-21.48%` |
| `fixed_unlock_open` | `recent_30d` | `415` | `-52.15%` | `38.31%` | `0.62` | `-54.51%` |
| `unlock_open_trail_market` | `recent_1d` | `7` | `-3.40%` | `14.29%` | `0.09` | `-3.77%` |
| `unlock_open_trail_market` | `recent_2d` | `21` | `-4.10%` | `38.10%` | `0.44` | `-4.50%` |
| `unlock_open_trail_market` | `recent_3d` | `26` | `-4.08%` | `38.46%` | `0.51` | `-4.51%` |
| `unlock_open_trail_market` | `recent_7d` | `73` | `-18.76%` | `31.51%` | `0.42` | `-22.85%` |
| `unlock_open_trail_market` | `recent_30d` | `414` | `-55.82%` | `35.99%` | `0.58` | `-57.80%` |
| `unlock_close_trail_market` | `recent_1d` | `7` | `-4.24%` | `0.00%` | `0.00` | `-4.55%` |
| `unlock_close_trail_market` | `recent_2d` | `21` | `-6.25%` | `23.81%` | `0.29` | `-6.55%` |
| `unlock_close_trail_market` | `recent_3d` | `26` | `-6.37%` | `30.77%` | `0.36` | `-6.68%` |
| `unlock_close_trail_market` | `recent_7d` | `71` | `-21.07%` | `28.17%` | `0.38` | `-26.12%` |
| `unlock_close_trail_market` | `recent_30d` | `383` | `-51.11%` | `38.12%` | `0.63` | `-54.02%` |

## 结论

你同事说的现象和原始回测是一致的：V2.1A 绝大多数原始退出确实发生在第 7 根，原因是第 7 根开始 trailing stop 生效并触发。

但“第 7 根计算完 trailing 后直接触发 stop”是否赚钱，取决于成交价：

- 如果按原始回测的 stop 价成交，第 7 根 stop 子集是赚钱的。
- 如果实盘只能在发现穿越后按第 7 根开盘、市价或收盘价平仓，历史回测是亏损的。

因此，14 笔 dry-run 盈利不能直接证明这个状态机已经可实盘。它可能是短样本，也可能是实盘 runner 的成交/判断时序与我们当前可执行回放仍有差异。下一步必须拿真实 14 笔的 entry、exit、signal_ts、bars_held、退出触发价、实际成交价和当时 active_stop 做逐笔对账。

## 产物

- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v21a_unlock_exit_audit.py`
- JSON：`reports/hype_5m_pbtr_v21a_unlock_exit_audit.json`
- 汇总 CSV：`reports/hype_5m_pbtr_v21a_unlock_exit_audit_summary.csv`
- 最近窗口 CSV：`reports/hype_5m_pbtr_v21a_unlock_exit_audit_recent.csv`
