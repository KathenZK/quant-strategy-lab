# HYPE-5M-PBTR-V3.3 解锁重置 trailing 回测 2026-06-24

Family id：`HYPE-5M-PBTR`

本报告测试 V3.3 的方案 2：锁仓期只观察，不把锁仓期峰谷带入 trailing；第 `10` 根 5m K 开始重新初始化 stop，再按 reduce-only stop-market 继续管理。

## 回测口径

- 入场、成本、信号仍沿用 `HYPE-5M-PBTR-V3.3`：`EMA21/EMA96 + pullback_buffer=0.01 + stop_atr=0.5 + trail_atr=0.75 + min_hold_bars=9`。
- 锁仓期内不挂策略 stop，本报告不额外模拟账户级 emergency stop。
- `trail_only_unlock_open`：第 `10` 根 K 开盘用当前开盘价作为新 trailing 锚点，初始 stop 距离为 `0.75 ATR`。
- `trail_only_prev_close`：第 `10` 根 K 开盘前用上一根已收盘 K 的 close 作为新 trailing 锚点，初始 stop 距离为 `0.75 ATR`。
- `stop_and_trail_unlock_open`：第 `10` 根 K 开盘用当前开盘价作为锚点，同时重新启用 `0.5 ATR` 初始 stop 和 `0.75 ATR` trailing。

## 结果对比

| 口径 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `原始回测` | `8027` | `1327928815.51x` | `55.66%` | `4.15` | `3.31` | `-8.69%` |
| `严格 live-realistic` | `8024` | `0.00x` | `38.43%` | `0.58` | `0.94` | `-100.00%` |
| `trail only / unlock open` | `7191` | `0.00x` | `39.94%` | `0.61` | `0.91` | `-100.00%` |
| `trail only / prev close` | `7191` | `0.00x` | `39.91%` | `0.60` | `0.91` | `-100.00%` |
| `stop + trail / unlock open` | `7321` | `0.00x` | `39.79%` | `0.61` | `0.92` | `-100.00%` |

## 可执行性诊断

- `trail only / unlock open` 解锁可正常挂 dormant stop `100.00%`；解锁即市价退出 `0.00%`；后续 stop-market `86.05%`；后续 gap 市价退出 `13.95%`。
- `trail only / unlock open` 解锁 stop 距离初始化锚点 bps：P10 `17.89`，P50 `31.03`，P90 `53.19`；盈利周 `3/56`，盈利月 `1/14`。
- `trail only / prev close` 解锁可正常挂 dormant stop `100.00%`；解锁即市价退出 `0.00%`；后续 stop-market `86.12%`；后续 gap 市价退出 `13.88%`。
- `trail only / prev close` 解锁 stop 距离初始化锚点 bps：P10 `17.88`，P50 `31.02`，P90 `53.15`；盈利周 `3/56`，盈利月 `1/14`。
- `stop + trail / unlock open` 解锁可正常挂 dormant stop `100.00%`；解锁即市价退出 `0.00%`；后续 stop-market `90.90%`；后续 gap 市价退出 `9.10%`。
- `stop + trail / unlock open` 解锁 stop 距离初始化锚点 bps：P10 `11.96`，P50 `20.67`，P90 `35.38`；盈利周 `2/56`，盈利月 `1/14`。

## 结论

`unlock_open` 作为重新初始化锚点可以消除“解锁即 stop 已穿越”的不可挂单问题，但当前 V3.3 参数下，重新初始化后的 trailing 仍无法恢复原始回测优势。`trail_atr=0.75` 在解锁后独立运行时过于贴近噪声，结果仍为 PF 小于 1。

`prev_close` 锚点更保守、更接近开盘前已知信息；本次样本中它同样没有产生解锁即市价退出，但表现仍不达标。`stop + trail / unlock open` 更紧，也没有改善。

因此，方案 2 的机制方向是正确的：它修复了不可执行成交假设；但不能直接沿用 V3.3 的 `stop_atr=0.5 / trail_atr=0.75 / min_hold_bars=9` 参数。下一步应在该可执行状态机上重新搜索更宽的 `trail_atr`、可选的 emergency stop，以及更短的 `min_hold_bars`。

## 产物

- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v33_reinit_trailing.py`
- JSON：`reports/hype_5m_pbtr_v33_reinit_trailing.json`
- 汇总 CSV：`reports/hype_5m_pbtr_v33_reinit_trailing_summary.csv`
- 交易诊断 CSV：`reports/hype_5m_pbtr_v33_reinit_trailing_trade_diagnostics.csv`
- rolling CSV：`reports/hype_5m_pbtr_v33_reinit_trailing_rolling.csv`
- weekly CSV：`reports/hype_5m_pbtr_v33_reinit_trailing_weekly.csv`
- monthly CSV：`reports/hype_5m_pbtr_v33_reinit_trailing_monthly.csv`
