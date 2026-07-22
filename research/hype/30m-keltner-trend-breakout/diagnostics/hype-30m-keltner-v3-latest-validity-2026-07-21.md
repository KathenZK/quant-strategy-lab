# HYPE 30m Keltner V3 最新有效性审计（2026-07-21）

## 结论

`HYPE-30M-Keltner-Trend-Breakout-V3` 在冻结点后的结果暂时为正，但未来样本只有 2 笔干净平仓，不能据此 promotion：

- clean prospective：`+18.11% / -7.26% MaxDD / 2 笔 / 50% 胜率`；
- 连续持仓口径：`+28.34% / -7.26% MaxDD / 3 笔`，其中包含冻结点前已入场的空头；
- 最近 `1d`：无交易；
- 最新全历史拼接：`+8186.92% / -22.68% MaxDD / 80 笔`，但绝大部分仍是历史选择样本，不能当作新 OOS 证据。

V3 暂未出现失效证据，但原有 30m 非原生相位门禁失败、跨周期迁移失败、close-location 风险贡献未证明和 runner 可执行性未完成均未被这 2 笔交易解决。状态保持 `registered / not promoted / not live-ready`。

## 审计对象

- 版本：`HYPE-30M-Keltner-Trend-Breakout-V3`。
- 参数：完全沿用冻结规格，没有参数搜索或事后调整。
- 冻结点：`2026-07-13 06:07 UTC`。
- clean prospective 起始事件：标签为 `2026-07-13 06:00 UTC` 的 30m bar；该 bar 在 `06:30 UTC` 闭合，之后才可能于下一根 open 入场。
- 成本：手续费 `0.001/fill`、不利滑点 `0.0004/fill`、实际 Binance funding。
- 执行：30m 收盘确认、下一根 30m open 入场；入场 bar 起固定 `10% TP / 2.5% SL`，stop-first，`hold=30`。

## 数据与输入对账

- 市场：Binance USDM perpetual `HYPEUSDT`。
- 输入数据：闭合 `15m` K 线 `2025-05-30 10:30` 至 `2026-07-21 08:45 UTC`，共 `40,026` 根；标准数据湖截止 `08:00 UTC`，其后 3 根由 Binance Futures Kline API 小范围增量补齐。
- 数据质量：标准区间的缺失、重复、关键空值、无效 OHLCV、raw/normalized mismatch 均为 `0`；API 尾部与标准数据重叠 5 根，OHLCV、quote volume、trade count mismatch 全部为 `0`；补齐后缺口为 `0`。
- 30m/1h 输入按 UTC 原生边界聚合；最后完整 30m bar 标签为 `2026-07-21 08:30 UTC`。

全历史 15m API 刷新发生 `IncompleteRead`，且未进入写盘阶段；随后改用从标准数据终点前 1 小时开始的小范围 API 尾部拉取，成功补齐至本次 Binance server time 对应的最新闭合 15m bar。由于 30m/1h OHLCV 可由完整 15m bar 无损聚合，先执行冻结区间双输入对账：

- 共同 30m bars：`19,623`；
- open/high/low/close mismatch：全部 `0`；
- 78 笔交易的方向、入场时间、退出时间和退出原因：完全一致；
- 冻结指标双输入均为 `+6328.98% / -22.68% MaxDD / 78 笔 / 67.95% 胜率`。

只有标准区间、API 尾部重叠区和冻结 1m 输入均通过精确对账后，补齐后的 15m 聚合输入才用于本报告的未来延伸。新补的 3 根 15m bar 没有产生新增平仓、入场或未平仓仓位，增量交易结论不变。

## 冻结点后结果

### Clean prospective

从冻结点后的首个可处理 30m bar 开始，策略从空仓状态运行：

| Return | MaxDD | Sharpe | Trades | Win Rate | Profit Factor |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `+18.11%` | `-7.26%` | `7.25` | 2 | `50.00%` | `12.24` |

Sharpe 和 profit factor 受 2 笔样本严重失真，不应作稳定性证据。

| Direction | Entry UTC | Exit UTC | Exit | Return |
| --- | --- | --- | --- | ---: |
| long | `2026-07-15 03:30` | `2026-07-15 18:30` | `time_close` | `-1.64%` |
| short | `2026-07-16 17:00` | `2026-07-17 08:00` | `time_close` | `+20.08%` |

两笔均使用 `3.0x` 杠杆；没有 TP、SL、gap stop 或同 bar TP/SL 冲突。

### 连续持仓口径

完整历史回放在冻结点前已有一笔空头：

- 入场：`2026-07-13 05:00 UTC`；
- 退出：`2026-07-13 20:00 UTC`；
- 退出原因：`time_close`；
- 账户交易收益：`+6.47%`。

加上 clean prospective 的两笔后，冻结点至数据终点为 `+28.34% / -7.26% MaxDD / 3 笔 / 66.67% 胜率`。由于第一笔不是冻结点后从空仓生成，主判断仍采用 clean prospective。

## 最新完整回放

| Return | MaxDD | Sharpe | Trades | Win Rate | Profit Factor |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `+8186.92%` | `-22.68%` | `5.18` | 80 | `68.75%` | `4.53` |

与冻结样本相比增加 2 笔完整新交易；原冻结点被强制 `window_end` 的仓位在连续回放中自然持有至 `time_close`。完整回放只能用于检查实现连续性，不能把历史拟合部分重新解释为 OOS。

## 近期切片

| Window | Return | MaxDD | Closed Trades | Win Rate |
| --- | ---: | ---: | ---: | ---: |
| `1d` | `0.00%` | `0.00%` | 0 | - |
| `7d` | `+18.11%` | `-7.26%` | 2 | `50.00%` |
| `1m` | `+21.54%` | `-12.73%` | 6 | `50.00%` |
| `3m` | `+247.88%` | `-13.58%` | 22 | `63.64%` |
| `6m` | `+1381.70%` | `-13.58%` | 38 | `68.42%` |
| `1y` | `+6017.96%` | `-17.84%` | 72 | `69.44%` |

除冻结点后的 2 笔外，`1m` 及更长切片都包含参数选择前后的历史数据，不能作为纯未来样本。

## 决策

- 接受本次结果为“正向但样本不足”的 latest-validity observation。
- 不创建 V3.1/V4，不修改 V3 参数，不进入 `audit`、live spec、dry-run 或 live。
- 继续积累真正未来 OOS；不能用这 2 笔覆盖既有 30m 相位门禁失败。
- promotion 前仍需重新满足相位/稳健性门禁，并完成订单时序、stop-market/slippage、重启恢复、缺失数据、kill switch 和 runner 状态机 parity。

## 复现入口

- [最新审计脚本](../scripts/audit_hype_30m_keltner_v3_latest.py)
- [汇总 JSON](../artifacts/hype_30m_keltner_v3_latest_audit_2026-07-21.json)
- [逐笔交易](../artifacts/hype_30m_keltner_v3_latest_audit_2026-07-21_trades.csv)
- [权益曲线](../artifacts/hype_30m_keltner_v3_latest_audit_2026-07-21_equity.csv)
- [V3 冻结规格](../specs/hype-30m-keltner-trend-breakout-v3-spec.md)
