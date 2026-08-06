# HYPE-1D-MA7-ABT 多空分离趋势候选观察规格

## 身份与证据角色

- 家族：`HYPE-1D-MA7-Asymmetric-Body-Trend`
- 研究分支：`separated-trend-search`
- 市场：Binance USD-M Futures `HYPEUSDT` perpetual
- 周期：UTC `1d`
- 核心：固定 `SMA7`，多头和空头使用独立的 reclaim、斜率、退出和保护参数。
- 身份状态：这是已揭示历史上的 `post-reveal candidate observation`，不是 `V1`、不是 registered version，也不是 promotion freeze。
- 主状态：`explore / not promoted / not live-ready`

该分支不继承初始“MA7 不穿过实体”规则的失败证据；它保留固定 `SMA7` 趋势思想，但用方向确认、迟滞退出和 ATR 保护替代逐次穿越翻仓。

## 数据、指标与成本

- 数据：标准数据湖 Binance `HYPEUSDT` perpetual `1h`，聚合完整 UTC 日 K。
- 样本：`2025-05-31 00:00` 至 `2026-07-30 00:00 UTC`，共 `425d`。
- `SMA7[t] = mean(close[t-6], ..., close[t])`。
- `ATR7`：日线 true range 的 7 日简单移动平均。
- 手续费：每次成交名义的 `0.001`。
- 基准滑点：每次成交 `4 bps` 不利滑点；压力测试 `8 bps`。
- funding：按实际 Binance funding timestamp 与 rate、仅在真实持仓区间结算；名义价格使用事件所在 `1h` K 的 open 近似。
- 仓位：单仓、非加仓；每次入场按成交后权益建立约 `1x` 目标，持仓期间数量不变。

## 多头规则

在日 `t` 收盘后，以下条件同时成立时，于 `t+1` 日 open 做多：

1. `close[t] > SMA7[t]`；
2. `close[t-1] <= SMA7[t-1]`，即价格从 MA7 下方或线上 reclaim；
3. `(SMA7[t] - SMA7[t-1]) / ATR7[t] >= 0.02`；
4. 当前空仓且冷却期结束。

多头退出与保护：

- 收盘退出：若 `close[t] < SMA7[t] - 0.75 * ATR7[t]`，在 `t+1` 日 open 平仓；
- trailing stop：以持仓后的最高日收盘为锚，保护价为 `highest_close - 1.5 * ATR7`；只在当日收盘后更新，下一日才生效；
- `max_hold_days = 90`；
- 退出后冷却 `2d`；
- `hard_stop_atr = 0`：首个持仓日没有固定 hard stop，这是 live-readiness blocker。

## 空头规则

在日 `t` 收盘后，以下条件同时成立时，于 `t+1` 日 open 做空：

1. `close[t] < SMA7[t] - 0.10 * ATR7[t]`；
2. `close[t-1] >= SMA7[t-1]`，即从 MA7 上方或线上向下 reclaim；
3. `(SMA7[t-2] - SMA7[t]) / ATR7[t] >= 0.02`；
4. 当前空仓且冷却期结束。

空头退出与保护：

- 收盘退出：若 `close[t] > SMA7[t] + 0.25 * ATR7[t]`，在 `t+1` 日 open 平仓；
- 斜率退出：若 `SMA7[t] >= SMA7[t-1]`，在 `t+1` 日 open 平仓；
- hard stop：入场价上方 `1.5 * ATR7`，入场后当日即有效；
- trailing stop：以持仓后的最低日收盘为锚，保护价为 `lowest_close + 4.0 * ATR7`；当日收盘后更新、下一日生效；
- `max_hold_days = 20`；
- 退出后冷却 `5d`。

## 状态机与成交时序

1. 日 open 先按前一完整日信号处理已有仓位退出。
2. 冷却为零且空仓时再检查入场；若多空信号同时成立，多头优先。
3. 选中候选的入场全部来自前一完整日 close，因此在下一 UTC 日 open 成交；搜索空间中的“观察本日 open 后做空”模式采用下一根 `1h` open，但本候选未使用该模式。
4. trailing stop 不使用当日 high/low 事后回填；当日收盘计算的新保护价只能从下一日开始触发。
5. 任一 `1h` open 跳空穿越保护价时按该小时实际 open 成交；小时内触发时按保护价成交，再计不利滑点与手续费。
6. 退出、保护触发或到期后不得在冷却期内立即重开。
7. funding 按事件 timestamp 与实际持仓区间相交结算；日内止损只承担止损前已发生的事件，`01:00` 才入场的 open-regime 不承担此前 `00:00` 事件。

## 搜索与选择口径

- 固定 `SMA7`，不搜索均线长度。
- 随机种子 `20260804`；多头和空头各抽样 `20,000` 组。
- 第一阶段只使用 `2025-05-31` 至 `2026-05-01` prefit，按全段、前后半段、prefit 最后 `90d`、`8 bps` 和额外延迟一天共同排名。
- 各方向保留 `120` 组稳健候选，再对前 `20 × 20 = 400` 个多空组合做 prefit 排名。
- 本文候选是揭示最后 `90d` 后，从候选前沿再次筛出的第 `041` 个组合，因此最后 `90d` 不是 clean OOS，不能用于 promotion claim。

## 证据与未完成项

- [搜索与验证报告](../diagnostics/hype-1d-ma7-abt-separated-trend-search-2026-08-04.md)
- [机器摘要](../artifacts/hype_1d_ma7_separated_summary_2026-08-04.json)
- [搜索脚本](../scripts/search_hype_1d_ma7_separated_trend.py)
- [家族主账](../hype-1d-ma7-abt-core-ledger.md)

未完成：clean prospective OOS / CPCV、更多日界相位与起跑点、长仓首日保护、拒单/断流/重启恢复、runner parity、线上逐笔对账。
