# HYPE-1D-MA7-ABT-V7.1 持仓效率（ER）诊断合同

> 冻结日期：2026-08-20。状态：`diagnostic-only / not promoted / not live-ready`。本合同不修改已登记 V7.1，也不授权调整 live runner。

## 1. 问题

TPR 已证明：用 `signed_ER7` 硬过滤 natural reclaim **入场**会删掉高价值趋势，不能重跑。本轮只问另一件事：

> 在 exact V7.1 已经持有多头时，7 日 Kaufman 效率能不能区分“趋势仍在推进”和“路径已经变乱”，从而决定该不该让 OAPP 完成两日确认？

8 月事件（`2026-08-09` 开多，`2026-08-16` OAPP 全平）只作已揭示定位样本，不能当 clean OOS。

## 2. 数据与控制

- Market：Binance USD-M `HYPEUSDT` perpetual。
- 信号：完整 UTC `1d` close；保护仍用真实 `1h`；funding 用 Binance event-time。
- Cost：`0.001/fill + 4bps/fill`；压力 `8bps/fill`。
- 唯一控制：exact `HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1`，`1x`、单仓、非加仓。
- Canonical：`2025-05-31` 至 `2026-08-06 00:00 UTC`，必须复现 `+711.04% / -18.40% / 20笔`。
- 扩展窗：同一起点至运行时最后一个完整 UTC 日；8 月路径已揭示，只作 diagnostic。
- 入场、native MA7、`1.5ATR` trail、空头 RSI、short cooldown `3d`、PEHC_294、成本与执行顺序全部不变。

## 3. 第 0 层：只测量，不改成交

在读取任何候选收益前，先用控制路径计算当时已知量（只用已收盘日 K，lookback 固定 7，不搜 14/20）：

```
ER7 = |close_t - close_{t-7}| / Σ_{i=t-6..t}|close_i - close_{i-1}|
signed_ER7 = +1 × (close_t - close_{t-7}) / 同一路径长度   # 仅多头持仓日
slope_atr = (SMA7_t - SMA7_{t-1}) / ATR7_t
Δslope_atr = slope_atr_t - slope_atr_{t-1}
pullback_atr = (持仓最高收盘 - close) / ATR7
days_since_highest_close
```

SMA14/SMA30 斜率正负只记账，不入规则。分母非正或输入非有限则记为非有限（fail closed）。

持仓日：该日 close 时刻账户仍为该笔多头，即 `entry_ts < close_ts` 且 `exit_ts >= close_ts`。盘中保护平仓不得使用该日尚未发生的收盘。

标签（可重叠，用于叙述；分界只用下面冻结的两组）：

1. Canonical 成熟 OAPP 信号日：控制路径中 `long_mfe_fraction_trail_exit` 的多头，其确认数达到 2 的那一个持仓日。
2. 事件日：`2026-08-14` 与 `2026-08-15` 两根完整日；分界统计只用 `2026-08-15`。
3. 其余持仓日：是否在同一笔交易里、该日之后仍出现更高的持仓最高收盘。
4. 最终因 `protective_stop` 或 `ma7_hysteresis_exit` 结束的多头上的持仓日。

### 3.1 预冻结分界

设 `T_median` 为 canonical 成熟 OAPP 信号日 `ER7` 的中位数。若成熟信号日不足 8 个，或 `2026-08-15` 的 `ER7` 非有限，第 0 层失败，**禁止**进入第 1 层。

分开标准（必须同时成立）：

```
ER7(2026-08-15) > T_median
```

含义：误锁日的路径效率必须严格高于历史上那些“好锁”当天的效率中位。分不开则停，不发明新阈值，不改成 signed ER、不改 lookback。

## 4. 第 1 层：唯一候选 `ER-gated OAPP`

仅当第 0 层分开后才运行。阈值冻结为同一 `T_median`（只来自 canonical 成熟 OAPP 日，不用 8 月日反推）。对照臂只有：exact V7.1、`ER-gated OAPP`、long OAPP off。

规则：

1. 原 OAPP 激活条件不变：`0.5×ATR7` 峰值浮盈、`10%` 回吐、毛利 `>0.28%`。
2. 原条件不成立时确认数归零。
3. 原条件成立且确认数为 0 时，确认数记为 1（第一日**不**看 ER）。
4. 原条件成立且确认数 ≥1 时，仅当 `ER7` 有限且 `ER7 < T_median` 才加一；否则保持原确认数。相等不加一。`ER7` 非有限不得加一。
5. 确认数达到 2 时，下一 UTC open 全平，原因仍为 `long_mfe_fraction_trail_exit`。
6. 不与 RR、ZPF、R7H、半仓锁盈叠加；不改 PEHC 触发条件。

## 5. 判定

- 第 0 层失败：`LAYER0_NOT_SEPARABLE / KEEP V7.1`。ER 不能解释 8 月过早锁盈。
- 第 1 层若仍在 `2026-08-16` 以 OAPP 离场：未解决本问题。
- Canonical 若收益低于控制，或真实 `1h` MDD 坏过 `-20%`，或弱于控制的收益且回撤同时恶化：`NO-GO`。
- 即使 canonical 改善，8 月反事实若只持有到数据终点，只能写 terminal-censored，不得当成已实现收益，也不得登记 V7.2 或改 runner。
- 本轮最多 `KEEP V7.1` / `SHADOW ER-GATE` / `NO-GO`。禁止把 ER 改回入场过滤。

## 6. 明确不做

TrendScore 连乘、ER 窗口网格、MA14/30 交易规则、HH/HL 摆动点、N 根内必须新高、ER 动态杠杆、交易路径 HTML。
