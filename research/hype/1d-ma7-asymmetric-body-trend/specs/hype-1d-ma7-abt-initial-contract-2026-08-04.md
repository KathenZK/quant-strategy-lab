# HYPE-1D-MA7-ABT 初始研究合同（2026-08-04）

## 身份与范围

- Family：`HYPE-1D-MA7-Asymmetric-Body-Trend`（`HYPE-1D-MA7-ABT`）。
- 状态目标：只做 `explore` 初始诊断；本合同不登记版本、不产生 promotion 或 runner handoff。
- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 信号周期：UTC `1d`；额外用 `12:00 UTC` 日界做相位审计。
- 仓位：单账户只允许 `-1 / 0 / +1`；入场后目标 `1x` 权益，成交之间固定数量，无加仓。

## 数据与指标

- 输入为标准数据湖已闭合 `1h` K 线与实际 funding；日 K 仅由连续、恰好 `24` 根小时 K 聚合。
- 必须通过 timestamp 连续、唯一键、raw/normalized OHLCV/quote volume/trade count 对齐、关键空值、`is_closed`、OHLC 合法性和 source 检查。
- `SMA7_t = mean(close[t-6], ..., close[t])`，`min_periods=7`。
- 日 `t` 开盘只能读取 `SMA7_{t-1}` 和 `close_{t-1}`；日 `t` 收盘后才可读取 `SMA7_t` 与完整实体 `[min(open_t, close_t), max(open_t, close_t)]`。

## 基础状态机

每个日开盘先按旧数量结算到新 open 的 PnL 与期间实际 funding，再按以下顺序处理：

1. 若持有多单且 `close[t-1] < SMA7[t-1]`，在 `open[t]` 平多。
2. 若持有空单且前一日收盘生成了所选空头退出信号，在 `open[t]` 平空。
3. 退出后或原本空仓时：
   - 若 `close[t-1] > SMA7[t-1]`，在 `open[t]` 做多；
   - 否则观察到 `open[t] < SMA7[t-1]` 后，在 `t+1h` 的下一根小时 K open 做空；
   - 否则保持空仓。
4. 已有仓位但未触发其专属退出时，不因另一方向出现而越过原退出规则。
5. 等号不触发严格大于/小于条件；warmup 不足时保持空仓。

多头优先于空头；日 open 的退出先处理。字面版若平空后仍满足开盘低于 MA7，会保留“日 open 平空、下一根 `1h` open 重开同方向”的两次真实成交及成本，不把它净额消失。这样避免观察当日 open 后仍假定按同一个不可保证的 open 成交。

## 空头退出的三种冻结解释

用户原句“某一日收盘时 MA7 不穿过这个蜡烛图的实体部分则平仓”方向不唯一，因此初始诊断并列测试：

1. `literal_not_intersect`（首要字面版）：若 `SMA7_t` 不在闭区间 `[min(open_t, close_t), max(open_t, close_t)]` 内，生成平空。
2. `directional_body_above`（方向性反转版）：只有当整个实体位于 `SMA7_t` 上方，即 `min(open_t, close_t) > SMA7_t`，才生成平空。
3. `symmetric_close_above`（对称控制组）：若 `close_t > SMA7_t`，生成平空。

所有收盘信号都在下一可成交的日 open 执行；不得使用同一根尚未闭合 K 的最终 close 在该 close 价格事前成交。

## 成本、账本与风险

- 每次实际成交按成交名义收取手续费 `0.001` 与不利滑点 `4 bps`；压力测试为 `8 bps`。
- funding 使用数据湖实际 Binance 费率、按成交间固定数量结算；当前以结算区间末端日 open 近似 funding 名义价格，不声称逐 funding timestamp mark-price 精确。
- open 标记权益用于调仓；日内 high/low 计算保守 MDD 和有效杠杆上界。
- 原规则没有保护止损、紧急退出、断流处理或缺 bar 合同；这些是 live-readiness blocker，不在回测中猜补。
- 终点只平已有仓位，不允许新开仓。

## 冻结审计

- 全期与沿完整权益路径截取的最近 `1d/7d/1m/3m/6m/1y` 连续切片，全部锚定数据终点，不重置仓位或权益。
- 前段 / 最后 `90d` flat-start / 全期；最后 90 日已被研究者查看，只称 `researcher-exposed`。
- `90d` 窗口每 `30d` 滚动。
- long-only、short-only、三种空头退出解释。
- `8 bps` 滑点、额外一日延迟、零 funding 控制。
- 真实 `1h` 重聚合的 `0h/12h` 日界。
- `SMA5–SMA10` 邻域只作稳健性诊断，不用于把 MA7 事后换成赢家。
- 交易 bootstrap；同期计成本与实际 funding 的 `1x` buy-and-hold 基准。

## 判定

- 任一全期大幅亏损、近期主要切片持续为负、邻域/相位崩塌或缺少风险合同，均保持 `explore / not promoted / not live-ready`。
- 现有历史不能在揭示后继续调参并冒充 OOS；若改空头语义、MA 长度或加入保护规则，应视为 materially new mechanism 并重新冻结。

仓库内证据入口：[主账](../hype-1d-ma7-abt-core-ledger.md) · [报告](../diagnostics/hype-1d-ma7-abt-initial-validation-2026-08-04.md) · [脚本](../scripts/research_hype_1d_ma7_asymmetric_body_trend.py)。
