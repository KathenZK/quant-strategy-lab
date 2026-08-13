# HYPE 4H MA7-RSI6 非对称反转合同（2026-08-06）

## 身份

- Family：`HYPE-4H-MA7-RSI6-Asymmetric-Reversal`
- Alias：`HYPE-4H-MA7-RSI6-AR`
- 市场：Binance USD-M `HYPEUSDT` perpetual
- 周期：UTC `4h`
- 状态：`explore / not promoted / not live-ready`
- 机制：SMA7 上方从空仓进入多头；多头跌破 SMA7 且最近三根 RSI6 曾经超过 70 时反手为空头；空头在 RSI6 低于 30 后平仓等待。
- 防串线：不是始终持仓的 `HYPE-4H-MA7-Close-Reversal`，也不是 `HYPE-4H-MA7-ABT` 的 slope / ATR reclaim 搜索。

## 指标

- `SMA7[t] = mean(close[t-6:t])`。
- `RSI6` 使用 TradingView/Wilder 口径：
  - `delta[t] = close[t] - close[t-1]`；
  - gain/loss 的首个六期均值使用简单平均；
  - 后续使用 `RMA[t] = (RMA[t-1] * 5 + value[t]) / 6`；
  - `RSI = 100 - 100 / (1 + avg_gain / avg_loss)`。
- 所有指标只读取已经闭合的 `4h` K。

## 冻结状态机

信号在日历索引 `t` 的 `4h` 收盘产生，最早在 `t+1` 的 `4h` open 成交：

1. `flat -> long`：`close[t] > SMA7[t]`。
2. `long -> short`：同时满足：
   - `close[t] < SMA7[t]`；
   - `max(RSI6[t-2], RSI6[t-1], RSI6[t]) > 70`。
3. `short -> flat`：`RSI6[t] < 30`。
4. 其他情况保持原状态。

补充约束：

- “过去三根大于过 70”定义为最近三根中至少一根严格 `> 70`，包含刚闭合的信号 K。
- 多头跌破 SMA7 但最近三根没有 RSI6 `> 70` 时继续持多，不平仓。
- 空头只由 RSI6 `< 30` 平仓；即使收盘重新站上 SMA7，也继续持空。
- 平空后的同一 open 不反手做多；先进入 flat，后续某根收盘满足 `close > SMA7` 才在再下一根 open 做多。
- 相等不触发：`close == SMA7`、`RSI6 == 70`、`RSI6 == 30` 均保持原状态。
- 单仓、非加仓；成交后按权益建立约 `1x`，成交间数量固定。
- 无 hard stop、trailing stop、buffer、cooldown 或 max hold。

## 数据与成本

- 从标准数据湖已接受的连续闭合 `1h` K 聚合；每根 `4h` 必须恰由四根连续 `1h` 组成。
- 手续费 `0.001/fill`，基准不利滑点 `4 bps/fill`，压力滑点 `8 bps/fill`。
- funding 使用 Binance 实际事件时间和费率，以事件小时 open 近似名义。
- 多空直接反手按平旧仓和开新仓两次 fill；terminal open 强制平仓。
- 策略没有交易所驻留保护单，是独立 `not live-ready` blocker。

## 审计

- 全期 base、`8 bps/fill`、额外延迟一根 `4h`；
- `fee=0/slippage=0` 且保留 funding 的 gross 解释项；
- 从数据终点精确回推最后 `120d` 的 flat-start 切片；
- 最近 `1d/7d/1m/3m/6m/1y`；
- `90d` 窗口、`30d` 步长；
- 从真实 `1h` 重聚合 `0h/1h/2h/3h` 四个相位；
- 同成本和 funding 的 `1x` buy-and-hold；
- 按 long / short 拆分已平仓交易贡献。

## 判定纪律

- 本轮只有用户明确给出的 `SMA7 / RSI6 / 70 / 30 / 3 bars`，不搜索参数。
- 所有历史均已被研究者查看；最后 `120d` 只作审计，不是 clean OOS。
- 不根据结果事后更改 RSI 公式、三根语义、阈值、平空后动作或 MA 类型。
- 本轮不登记版本、不创建 live spec、不推进 runner。
