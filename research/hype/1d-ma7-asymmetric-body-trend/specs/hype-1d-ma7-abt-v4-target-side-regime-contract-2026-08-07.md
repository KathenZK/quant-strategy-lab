# HYPE V4 Target-Side Regime 诊断合同

> 冻结时间：2026-08-07（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 用户确认

用户明确选择：

> 当short条件确认但当前持有long时，下一日open平多并立即反手short；long方向完全对称。

本轮在[flat regime合同](hype-1d-ma7-abt-v4-flat-regime-entry-contract-2026-08-07.md)基础上增加目标侧状态迁移，不搜索参数、不追溯修改登记V4。

## 冻结变体

### `V4_CONTROL`

登记V4。

### `TARGET_SIDE_REGIME`

每日收盘后只用已闭合UTC日K计算下一日目标侧：

- long target：`close[t] > SMA7[t]`，且V4 long方向slope通过；
- short target：`close[t] < SMA7[t]`，且V4 short `2d` slope达到`0.02`；
- 两侧入场buffer均为0，不要求前一日cross/reclaim；
- 若当前flat且cooldown为0，于`t+1` open进入target；
- 若当前持有target同侧，继续持仓并沿用V4退出/保护；
- 若当前持有target反侧，于`t+1` open先平原仓，再以同一open立即反手target；该状态反转不执行退出cooldown；
- 平仓与新开仓分别计手续费和不利滑点；
- 若价格侧别与slope不能形成target，不新增动作，当前仓继续按V4原退出规则管理；
- intraday long trailing stop后的MA_ONLY反手、short保护、迟滞、max hold与普通退出cooldown均保留。

不允许long/short同时持有，不加仓，不因target同侧每天重新调仓。

## 执行与数据

- Binance USD-M `HYPEUSDT` perpetual；accepted `1h`聚合UTC日K与真实event-time funding；
- 历史主路径截止`2026-07-30 04:00 UTC`，最新延伸使用运行时已接受数据；
- 约`1x`、固定数量、单仓；
- 手续费`0.001/fill`、基准不利滑点`4 bps/fill`；
- target只能由已闭合日K生成，于下一日open执行，禁止使用当日未来close；
- 同一open反手记录两次fill，下一方向当日intraday保护立即生效。

## 输出与判定

- prefit、最后90日flat-start、full；
- `8 bps`、额外延迟一天、零funding、`12h`日界；
- 最近`1d/7d/1m/3m/6m/1y`、90日滚动、24日界相位、最新延伸；
- 目标侧直接反手次数、逐笔交易和相对V4路径变化；
- 收益、MDD、Sharpe、PF、交易数、成本、funding与简化破产。

该变体属于post-reveal机制诊断。结果不能直接登记V5或推进promotion。
