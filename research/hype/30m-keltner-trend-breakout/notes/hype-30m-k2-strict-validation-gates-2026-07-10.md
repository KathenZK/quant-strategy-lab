# HYPE-30M K2-FQ-V2-ATRVT-OFF 严格门禁审计

日期：2026-07-10

策略家族：`HYPE-30M-Keltner-Trend-Breakout`

审计对象：`K2-FQ-V2-ATRVT-OFF` 外部规格观察值

状态迁移目标：无；本次只按项目 Gate 0–7 与 live-executable 规则做严格诊断。

结论：`explore / not promoted / not live-ready`

## 总结

该策略在手续费 `0.001/次成交`、不利滑点 `0.0004/次成交`、实际 Binance funding、next-open 入场、stop gap-open 按开盘价成交的严格口径下，仍得到 `+4827.01%` 历史复利收益。数据修复后 headline 与交易路径不变，但仍不能覆盖其余门禁失败：

- 数据质量前置已通过：完整历史已写入标准 raw/normalized data lake，冲突 closed bar 已按 Binance API 终值修复，cache/lake 零差异。
- Gate 3 失败：交易重排后的 MDD p05 为 `-45.80%`，超过历史 MDD 1.5 倍门槛 `-41.95%`，最坏达到 `-64.14%`。
- Gate 5 失败：保守按 `N=1000` 历史试验估计时 DSR 为 `0.9413 < 0.95`。
- Gate 6 失败：23 个起跑点虽全部盈利，但年化收益 CV 为 `0.869`，路径离散过大。
- Gate 7 失败：30m 非原生相位中位 CAGR 仅为原生相位的 `7.70%`，远低于默认 `60%` 门槛，跨相位 CV 为 `1.462`。
- Gate 4 与 live-executable 未完成：研究回放无法证明拒单、保护单失败、断流恢复、重启对账、missing-bar fail-closed 与 kill switch。

因此不得登记为本仓库正式版本，不得进入 `audit`、`live spec`、`dry-run` 或 `live`。

## 数据与成本

- 交易所 / 市场：Binance USDM perpetual。
- 标的：`HYPEUSDT`。
- 基础周期：`1m` 闭合 K 线；重采样为 `30m` 信号与 `1h` regime。
- UTC 范围：`2025-05-30 10:30` 至 `2026-07-10 06:43`。
- 行数：`584414`。
- cache 连续性：缺失 `1m` bar 为 `0`，重复 timestamp 为 `0`，OHLC 违规为 `0`。
- 手续费：每次成交名义的 `0.001`。
- 滑点：开仓、TP、SL、time exit 均按方向施加 `0.0004` 不利滑点。
- funding：`2434` 条 Binance 历史 funding，覆盖 `2025-05-30 12:00` 至 `2026-07-10 04:00 UTC`，已计入。
- 止损：若 bar open 已越过 stop，按 open 再加不利滑点成交；不按陈旧 stop 价回填。

## 严格 headline

| 指标 | 结果 |
| --- | ---: |
| Return | `+4827.01%` |
| MDD | `-27.97%` |
| Sharpe | `4.05` |
| Trades | `114` |
| Win rate | `55.26%` |
| Profit factor | `2.59` |
| Avg leverage | `2.66x` |
| Worst trade | `-8.46%` |
| TP / SL / time | `10 / 39 / 65` |
| funding PnL（账户权益绝对贡献求和） | `-2.77%` |

与未计 funding 口径相比，收益从 `+4926.12%` 降至 `+4827.01%`，MDD 从 `-27.66%` 加深至 `-27.97%`。

## 最近分片

| Window | Return | MDD |
| --- | ---: | ---: |
| `1d` | `0.00%` | `0.00%` |
| `7d` | `-2.86%` | `-10.12%` |
| `1m` | `+31.69%` | `-15.71%` |
| `3m` | `+308.77%` | `-15.71%` |
| `6m` | `+1219.02%` | `-26.97%` |
| `1y` | `+4183.69%` | `-27.78%` |

分片锚定数据末端，不用于参数选择。最近 `7d` 为负，`1d` 无交易。

## 门禁结果

| 门禁 | 结论 | 关键证据 |
| --- | --- | --- |
| 数据质量前置 | 通过 | raw/normalized/cache 均为 `584414` 行，完整覆盖回测区间；零缺口、零重复、零 OHLC/空值问题、零字段差异 |
| Gate 0 超额收益 | 通过 | 动态杠杆策略相对 buy-and-hold 日频 IR `2.33`；固定 1x IR `0.29`；1x 收益 `+304.60%`，buy-and-hold `+112.75%` |
| Gate 1 消融 | 通过 | 去掉 1h regime 后收益降至 `+625.70%`、MDD `-42.22%`；只留 regime 则 `-99.97%`；去掉 SL 后 worst trade `-44.76%` |
| Gate 2 滚动 OOS | 通过 | `44` 组 `60d IS + 10d gap + 30d OOS` 周滚动窗口；正收益 `95.5%`；零交易窗口 `0`；收益中位数 `+32.35%` |
| Gate 3 Monte Carlo | **失败** | K 线扰动与参数邻域均保持盈利，但交易重排 MDD p05 `-45.80%`、最坏 `-64.14%` |
| Gate 4 压力测试 | **未完成** | 研究侧量化压力通过；runner 拒单、断流、保护单失败、重启恢复与 kill switch 无证据 |
| Gate 5 统计显著性 | **失败** | PSR `1.0000`；DSR：`N=100` 为 `0.9890`、`N=500` 为 `0.9615`、`N=1000` 为 `0.9413`；历史试验数无完整台账 |
| Gate 6 启动时间 | **失败** | 23 个起跑点全部盈利，但 CAGR CV `0.869 > 0.5`；结果高度依赖起跑时段 |
| Gate 7 相位 | **失败** | 30m 非原生/原生中位 CAGR 比 `0.077 < 0.60`，CV `1.462 > 0.5`；1h `{0,30}` 相位单独通过 |
| live-executable | **未完成** | next-open、gap stop、SL-first、bracket delay 已回放；OCO/reduce-only、拒单、重启、missing-bar 与 kill switch 未验证 |

## 数据质量修复记录

修复前标准 data lake 只覆盖 `2026-03-25 00:00` 至 `2026-06-26 04:23 UTC`，且 cache 缺少 `vwap`。2026-07-10 已将完整 API cache 标准化后按 407 个 UTC 日分区原子写入 raw/normalized 两层，并补齐 `vwap`。

修复前 cache 与 data lake 重叠区在 `2026-06-25 08:46 UTC` 有一根冲突 bar：

- cache：`high=63.581`、`close=63.567`、`volume=6404.81`、`quote_volume=406978.32864`、`trade_count=1117`；
- data lake：`high=63.561`、`close=63.521`、`volume=1644.34`、`quote_volume=104484.73984`、`trade_count=328`；
- 旧 data lake 行标记 `is_closed=True`、source=`fapi_rest`，但数值表现为提前截取的未完成 bar。

Binance FAPI 在 bar 闭合后重新查询返回 cache 数值，因此以 cache 终值覆盖旧行。修复后 raw/normalized 各 `584414` 行且逐字节一致；cache/lake 时间键全部双向覆盖，OHLCV/quote volume/trade count/vwap 差异单元格为 `0`；缺失 bar、重复 timestamp、OHLC 违规、关键空值、非闭合 bar 均为 `0`。

修复后重新跑全部门禁，headline 与交易路径不变，数据质量前置从失败改为通过。

## 执行压力

| 变体 | Return | MDD | Worst trade |
| --- | ---: | ---: | ---: |
| 严格基线 | `+4827.01%` | `-27.97%` | `-8.46%` |
| 全成交滑点 10 bps | `+3228.70%` | `-33.22%` | `-8.63%` |
| 全成交滑点 20 bps | `+1995.38%` | `-34.64%` | `-8.93%` |
| 止损额外滑点 20 bps | `+3925.12%` | `-29.87%` | `-9.04%` |
| 入场延迟 1 根 30m | `+1292.27%` | `-38.22%` | `-8.49%` |
| bracket 延迟 1 根 30m | `+3312.76%` | `-44.40%` | `-30.13%` |

bracket 延迟仅一根 bar 就把 worst trade 从 `-8.46%` 放大至 `-30.13%`，并产生 3 次 stop gap-open。保护单必须在入场后立即成功挂出；否则应 fail closed 或立即 reduce-only 平仓。

## 相位判断

30m 相位失败不是轻微退化：

- 原生相位 20 个起跑点的中位 CAGR：`6335.73%`；
- 非原生相位中位 CAGR：`487.56%`；
- 非原生 / 原生比：`7.70%`；
- 非原生 MDD / 原生 MDD：`1.376`；
- 跨相位 CAGR CV：`1.462`。

1h regime 的 `{0,30}` 分钟相位通过：非原生 / 原生中位 CAGR 比 `68.09%`、MDD ratio `0.952`、CV `0.268`。因此主要边界依赖来自 `30m` Keltner 信号切分，不是 `1h` regime。

## 状态建议

保持 `explore / not promoted / not live-ready`。下一步若继续研究，优先级应是：

1. 查明 30m 原生边界效应是否有可解释的收线订单流依据，否则视为相位选择偏差；
2. 建立家族历史 trials 台账，再计算可信 DSR；
3. 降低交易重排后的回撤尾部，重新跑 Monte Carlo；
4. 不要在当前 OFF 参数上直接写 live spec 或交给 runner。

## 证据

- 门禁脚本：[../scripts/research_hype_30m_k2_strict_validation_gates.py](../scripts/research_hype_30m_k2_strict_validation_gates.py)
- 数据修复脚本：[../scripts/repair_hype_1m_standard_data_lake.py](../scripts/repair_hype_1m_standard_data_lake.py)
- 数据修复证据：[../artifacts/hype_1m_standard_data_lake_repair_2026-07-10.json](../artifacts/hype_1m_standard_data_lake_repair_2026-07-10.json)
- 汇总 JSON：[../artifacts/hype_30m_k2_strict_validation_gates_2026-07-10.json](../artifacts/hype_30m_k2_strict_validation_gates_2026-07-10.json)
- 门禁表：[../artifacts/hype_30m_k2_strict_gate_summary_2026-07-10.csv](../artifacts/hype_30m_k2_strict_gate_summary_2026-07-10.csv)
- 严格逐笔：[../artifacts/hype_30m_k2_strict_trades_2026-07-10.csv](../artifacts/hype_30m_k2_strict_trades_2026-07-10.csv)
- OOS：[../artifacts/hype_30m_k2_strict_rolling_oos_2026-07-10.csv](../artifacts/hype_30m_k2_strict_rolling_oos_2026-07-10.csv)
- 消融：[../artifacts/hype_30m_k2_strict_ablation_2026-07-10.csv](../artifacts/hype_30m_k2_strict_ablation_2026-07-10.csv)
- Monte Carlo：[../artifacts/hype_30m_k2_strict_monte_carlo_2026-07-10.csv](../artifacts/hype_30m_k2_strict_monte_carlo_2026-07-10.csv)
- 参数邻域：[../artifacts/hype_30m_k2_strict_parameter_neighborhood_2026-07-10.csv](../artifacts/hype_30m_k2_strict_parameter_neighborhood_2026-07-10.csv)
- 压力测试：[../artifacts/hype_30m_k2_strict_stress_2026-07-10.csv](../artifacts/hype_30m_k2_strict_stress_2026-07-10.csv)
- 起跑点：[../artifacts/hype_30m_k2_strict_start_time_2026-07-10.csv](../artifacts/hype_30m_k2_strict_start_time_2026-07-10.csv)
- 相位：[../artifacts/hype_30m_k2_strict_phase_2026-07-10.csv](../artifacts/hype_30m_k2_strict_phase_2026-07-10.csv)
