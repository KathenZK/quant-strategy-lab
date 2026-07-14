# mk7-v8 回测窗口后 10.875 天 forward 审计

状态：`post-backtest-window forward audit / not pristine OOS / not promoted / not live-ready`

## 结论

冻结参数在 `2026-07-02T03:00:00Z` 至 `2026-07-13T00:00:00Z` 的 10.875 天窗口内：

| 口径 | 收益 | MDD | 胜率 | PF | 交易数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 延续完整账户状态（含跨边界 ETH 持仓） | `+0.0089%` | `-8.99%` | `75.00%` | `0.971` | `4` |
| 只看窗口内新入场、NAV 重置为1 | `-0.2221%` | `-8.99%` | `75.00%` | `0.971` | `4` |

窗口内策略基本持平。虽然 `3/4` 交易盈利，但一笔 BTC CCI 亏损抵消三笔小盈利，PF 低于1；这10.875天既没有延续样本内的高复利，也没有足够交易数否定长期策略。

## OOS 身份边界

该窗口严格位于外部规格的**回测终点**之后，参数和账户规则未在本窗口上搜索或调整。但外部 `mk7-v8` 文件冻结日期为 2026-07-12，因此不能证明作者在定稿前没有看过 `2026-07-02` 至 `2026-07-12` 的行情。

所以本报告称为“回测窗口后 forward slice”，不称为 pristine untouched OOS。真正位于规格冻结日之后的 `2026-07-12T00:00Z` 至 `2026-07-13T00:00Z` 为 `0` 笔、收益 `0%`。

## 数据更新与质量

所有组件统一截到最近完整公共日 `2026-07-13T00:00:00Z`：

- 六币 1h OHLCV：最后一根 open time 均为 `2026-07-12T23:00Z`；
- HYPE 1m、HYPE/BTC 15m、premium、CVD/flow：连续至 7月12日末；
- HYPE top-LSR 5m：至 `2026-07-12T23:55Z`，全历史保留16个已知孤立缺点；
- HYPE aggTrades：`409/409` 个日归档完整，截止 `2026-07-12`；
- 六币 funding：覆盖 OOS 终点之后，无 null/duplicate；
- HYPE 标准 1m raw/normalized 数据湖已更新至 `2026-07-13T12:18Z`，零缺口、逐字段一致。

更新六币滚动两年数据时发现抓取脚本会用“日中起始的部分首日”覆盖原完整日分区，导致 `2024-07-13` 前12小时丢失。已从 Binance API 重新抓取 TRX/SOL/ETH/BTC/BNB 该日 `24/24` 根，并同时修复 raw/normalized 分区；修复后再构造 OOS 输入并通过连续性检查。

完整数据证据：[`mk7_v8_oos_data_integrity_2026-07-13.json`](../artifacts/mk7_v8_oos_data_integrity_2026-07-13.json)。

## 冻结路径复核

OOS 运行从完整历史重新 warmup 和推进状态，而不是从7月2日冷启动：

- 回测终点前 raw 计数继续为六币 `44/82/74/89/54/62`、K2FQ `69`、MII `374`；
- 回测终点前入选仍为 `747`；
- 与冻结 CSV 逐笔比较，entry/exit/side 完全一致，exposure 最大差 `1.78e-15`、equity return 最大差 `9.89e-17`；
- funding 历史延长后，纯文本 CSV SHA 因亚 `1e-12` 浮点尾数发生变化；逐笔容差核验通过，不视为路径漂移。

## 窗口内交易

| Entry UTC | 组件 | 交易 | 方向 | 账户收益 |
| --- | --- | --- | --- | ---: |
| `2026-07-05 15:00` | 六币 | BNB Wick | short | `+1.1352%` |
| `2026-07-05 20:30` | K2FQ | HYPE K2FQ | long | `+0.4066%` |
| `2026-07-06 16:00` | 六币 | BTC CCI | long | `-3.7629%` |
| `2026-07-11 15:00` | 六币 | HYPE DI | long | `+2.1105%` |

组件分布：六币 `3`、K2FQ `1`、MII `0`。资产分布：BNB `1`、BTC `1`、HYPE `2`。

窗口起点仍有一笔 `2026-06-29` 入场、`2026-07-02 06:00` 出场的 ETH 六币仓位，因此“延续账户状态”与“新入场重置 NAV”收益相差约 `0.23pp`。

## 判断

1. 这段 forward 数据不支持继续宣传样本内百万倍曲线：近11天账户净收益基本为零，期间 MDD 接近9%。
2. 高胜率在该窗口没有转化为正 PF；小赢宽损结构仍然存在。
3. MII 在窗口内没有候选，短样本收益完全由六币与 K2FQ 决定。
4. 仅4笔交易，统计功效极低；当前结论应是“暂未延续高收益、亦不足以判死”，而不是 PASS 或 NO-GO。
5. 相位门仍失败、逐笔外部哈希仍未闭合，状态保持 `explore / not promoted / not live-ready`。

## 证据

- [OOS 汇总 JSON](../artifacts/mk7_v8_post_window_oos_2026-07-13.json)
- [OOS 入选交易 CSV](../artifacts/mk7_v8_post_window_selected_trades_2026-07-13.csv)
- [OOS 运行日志](../artifacts/mk7_v8_post_window_oos_run_2026-07-13.log)
- [OOS 数据完整性](../artifacts/mk7_v8_oos_data_integrity_2026-07-13.json)
- [OOS 审计脚本](../scripts/audit_mk7_v8_post_window_oos_2026_07_13.py)
