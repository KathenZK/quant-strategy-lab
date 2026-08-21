# HYPE 1D MA7 裸 Cross + 趋势健康出场诊断合同

> 冻结日期：2026-08-20。状态：`independent diagnostic / explore / not promoted / not live-ready`。不修改 V7.1，不登记新版本，不改 runner。

## 1. 问题

SNC02 已证明：昨日收盘在 SMA7 反侧、今日收盘穿到目标侧、同向斜率 `>=0.02×ATR7`、下一 UTC open 开仓，能抓住 `2026-08-09` 多头，但扩展窗为 `+32.56%/-50.79%`，因为只能等镜像合格 cross 才纠错。

本轮唯一新问题：同一入场是否能用用户提出的四类**持仓健康**规则做止盈止损，在不搜索阈值的前提下降低裸核左尾，同时尽量保住 8 月趋势。

## 2. 控制与候选

- 控制：exact [`SNC02`](hype-1d-ma7-symmetric-naked-cross-slope-diagnostic-contract-2026-08-20.md)。扩展窗必须复现约 `+32.56% / -50.79%`。
- 唯一候选 `SNC02-THX`：入场与 SNC02 完全相同；**持仓中忽略反向合格 cross**；只按下列健康规则出场；平仓后回到 flat，直到出现新的 SNC02 信号。
- 不叠加 OAPP、PEHC、V7.1 迟滞、1.5ATR trail、RSI、半仓、RR、ER 入场过滤。
- 不搜 ER 窗口、斜率天数、ATR 倍数或“N 日未创新高”。

## 3. `SNC02-THX` 冻结出场

入场后在完整 UTC 日 close 评估（非有限则 fail-closed，记 `health_nonfinite`），下一 UTC open 市价平：

1. **趋势成果 / 结构**：日线 close 跌破（多）或升破（空）已确认的 swing 更高低 / 更低高。确认方式：入场价视为第一峰；其后先出现反向 close，再创新极值时，把这段回撤极值锁成 `confirmed_hl/hh`；之后 close 穿越该锁定价即破坏。未确认前本条沉默。
2. **效率 / 动量**：`signed_ER7 = side × (close_t-close_{t-7}) / Σ_{i=t-6..t}|Δclose| <= 0`。lookback 固定 7，不另设 ER 下限。
3. **速度破坏**：持仓方向的 `slope_atr = side × (SMA7_t-SMA7_{t-1}) / ATR7_t <= 0`。
4. **速度衰减**：方向斜率仍为正，但连续 2 个完整持仓日 `side_slope[t] < side_slope[t-1]`。
5. **趋势成果 / 恢复**：距入场后最高收盘（多）或最低收盘（空）已连续 `>=7` 个完整日没有创新极值。

同日多条日线健康规则只记一条原因，优先级：结构破坏 → ER 非正 → 斜率非正 → 斜率衰减 → 7 日未创新极值 → 非有限。

6. **回撤结构（执行层）**：用已完成小时的持仓最高价（多）或最低价（空），`1h` 触及 `±3.0×` 最近已收盘日 `ATR7` 则市价平。跳空按该小时 open，触及按止损价。同一根 1h 先检查止损，再更新极值。这是用户“回撤 3ATR 可能破坏趋势”的唯一倍数，不用 0.5/1.0/1.5 网格。

若某日 close 同时健康失败且出现反向 SNC02 信号：下一 open **先按健康原因平仓，再按该反向信号开仓**（同一 open 两笔 fill）。仅健康失败、无新信号则只平到 flat。

## 4. 数据与成本

与 SNC02 相同：Binance USD-M `HYPEUSDT`，UTC `1d` 信号，真实 `1h` 与 funding，`0.001/fill + 4bps/fill`，压力 `8bps` 与额外 `1d` lag。lag 只延迟日线信号与日线健康出场；`3ATR` 的 1h 止损不延迟。

Canonical：`2025-05-31` 至 `2026-08-06`。扩展至数据末端。最近切片 `1d/7d/1m/3m/6m/1y` 只作审计。

## 5. 判定

- 主比较是相对 SNC02 的收益与真实 `1h` MDD，以及 `2026-08-09` 多头是否仍被过早打掉。
- MDD 仍坏过 `-20%` 则风险门失败，不得替换 V7.1，也不得登记。
- 8 月若只持有到 terminal，标 terminal-censored。
- 本轮最多 `KEEP SNC02 CONTROL` / `NO-GO THX` / `SHADOW THX`；禁止把四项再拆开搜阈值。
