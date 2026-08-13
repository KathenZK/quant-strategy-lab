# HYPE V3 强制反手确认修正合同

> 冻结时间：2026-08-07（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

登记V3的long trailing-stop反手跳过short的MA7位置、buffer和slope确认，导致R-S02与R-S12在当时可知MA7上方开空，且7笔中5笔只持有1日。本轮只修正反手确认，不搜索参数、不追溯改写V3。

## 冻结变体

### `V3_CONTROL`

登记V3：long trailing stop平仓后，在下一根真实`1h` open无条件反手short。

### `MA_ONLY`

1. long trailing stop仍按V3原规则平多；
2. 在拟反手的真实`1h` open，只读取上一完整UTC日的`SMA7`；
3. 仅当该`1h open < SMA7`时反手short；
4. 若不满足，保持flat，不重新做多；
5. 反手成功后仍沿用V3 short的hard stop、`0.75×ATR7`迟滞、slope exit、trailing、max hold与cooldown。

### `MA_AND_SLOPE`

在`MA_ONLY`基础上，再要求上一完整日满足V3自然short的向下斜率：

`(SMA7[t-2] - SMA7[t]) / ATR7[t] >= 0.02`

不额外要求reclaim或`0.10×ATR7` entry buffer；trailing stop事件本身作为反手事件源。

## 执行边界

- trailing止损已经成交后，反手确认失败只能保持flat，不能假设原long仍存在；
- 若trailing在UTC日最后一小时触发，下一日open再用当时最近完整日MA7检查；
- MA7与slope只使用已闭合日K，禁止使用反手当日未来close；
- 平多与成功开空分别计手续费`0.001/fill`和`4 bps/fill`不利滑点；
- Binance USD-M `HYPEUSDT` perpetual，accepted `1h`聚合UTC日K、真实event-time funding、约`1x`。

## 输出

- prefit、最后90日flat-start、full；
- `8 bps`、额外延迟一天、零funding、`12h`；
- 最近`1d/7d/1m/3m/6m/1y`、90日滚动、24日界相位、最新延伸；
- 反手触发、获准、拒绝次数和逐笔路径；
- 收益、MDD、Sharpe、PF、交易数、成本、funding与简化破产。

## 判定

- `MA_ONLY`必须消除所有MA7上方反手；若仍大量次日slope退出，只算位置修复，不算状态机完整修复；
- `MA_AND_SLOPE`用于检验入场/退出确认一致性，不能因交易数少而直接宣称稳健；
- 任一候选均为post-reveal诊断，不自动登记V4、不修改V3、不推进runner。
