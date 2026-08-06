# Binance-1D-MA7-ST-XFER 冻结迁移合同

## 身份与证据角色

- 家族：`Binance-1D-MA7-Separated-Trend-Transfer`
- Alias：`BIN-1D-MA7-ST-XFER`
- 目标资产：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual
- 周期：UTC `1d`
- 来源：HYPE 第 `041` 组 post-reveal observation；[原始规格](../../../hype/1d-ma7-asymmetric-body-trend/specs/hype-1d-ma7-abt-separated-trend-observation-2026-08-04.md)。
- 迁移约束：不根据 BTC/ETH 历史改参数、筛资产或改规则；目标资产结果只作为 direct-transfer diagnostic。
- 状态：`explore / not promoted / not live-ready`；不是 registered version。

## 数据与成本

- 输入：标准数据湖 Binance perpetual `1h` closed candles，聚合完整 UTC 日 K。
- 可比窗口：`2024-07-31 00:00` 至 `2026-07-30 00:00 UTC`，`729d`；起点由完整 funding 覆盖决定。
- HYPE 共同窗口：`2025-05-31 00:00` 至 `2026-07-30 00:00 UTC`，`425d`。
- `SMA7`：最近七个完整日收盘价的简单移动平均。
- `ATR7`：日线 true range 的七日简单移动平均。
- 手续费：每次成交名义的 `0.001`。
- 基准/压力滑点：每次成交 `4 bps` / `8 bps` 不利滑点。
- funding：按实际 timestamp/rate、仅在真实持仓区间结算；名义使用事件所在 `1h` K 的 open。
- 仓位：固定约 `1x`、单仓、非加仓，持仓期间数量不变。

## 冻结多头

日 `t` 收盘后同时满足下列条件，于 `t+1` UTC open 做多：

1. `close[t] > SMA7[t]`；
2. `close[t-1] <= SMA7[t-1]`；
3. `(SMA7[t] - SMA7[t-1]) / ATR7[t] >= 0.02`；
4. 当前空仓且两日冷却结束。

退出：`close[t] < SMA7[t] - 0.75 * ATR7[t]` 时次开退出；另有 `highest_close - 1.5 * ATR7` 的次日生效 trailing stop、`90d` 最长持仓。`hard_stop_atr=0`，首持仓日无固定 hard stop。

## 冻结空头

日 `t` 收盘后同时满足下列条件，于 `t+1` UTC open 做空：

1. `close[t] < SMA7[t] - 0.10 * ATR7[t]`；
2. `close[t-1] >= SMA7[t-1]`；
3. `(SMA7[t-2] - SMA7[t]) / ATR7[t] >= 0.02`；
4. 当前空仓且五日冷却结束。

退出：`close[t] > SMA7[t] + 0.25 * ATR7[t]` 或 `SMA7[t] >= SMA7[t-1]` 时次开退出；另有入场即生效的 `1.5 * ATR7` hard stop、`lowest_close + 4.0 * ATR7` 次日生效 trailing stop和 `20d` 最长持仓。

## 成交时序

1. 日 open 先处理前一完整日产生的退出，再处理入场；多空信号同时成立时多头优先。
2. trailing stop 只以已完成日的 close 更新，更新后的保护价从下一日生效。
3. `1h` open 跳空穿越保护价时按该小时 open 成交；小时内触发按保护价成交，再计滑点与手续费。
4. funding 只结算入场后、退出前发生的实际事件。

## 冻结审计

- 主结果：组合、多头、空头分别审计完整 `729d` 与 HYPE 共同 `425d`。
- 稳健性：`8 bps`、额外延迟一天、最近 `1d/7d/1m/3m/6m/1y`、滚动 `180d`、UTC/12h 日界。
- 所有近期与滚动窗口仅用于 audit，不用于参数选择。
- 引擎固定为 [研究脚本](../scripts/research_binance_1d_ma7_separated_trend_transfer.py)中声明的来源 SHA256。
