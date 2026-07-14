# HYPE-1H-Adaptive-Regime 核心研究台账

Family：`HYPE-1H-Adaptive-Regime`

Alias：`HYPE-1H-AR`

Created：2026-07-02

## 边界

`HYPE-1H-Adaptive-Regime` 是 Binance USD-M Futures `HYPEUSDT` perpetual `1h` 自适应市场状态研究线。它独立于 `HYPE-15M-Multi-Indicator-Intraday`、`HYPE-EMA-Crossover`、`HYPE-EMA-Trend-Breakout`、`HYPE-5M-Pullback-Trail` 和其他 HYPE 家族。

本台账中的 `V1`、`V2`、`V3`、`V4` 只在 `HYPE-1H-Adaptive-Regime` 家族内有效。裸版本号不具有策略身份。

## 当前状态

- 当前登记版本：`HYPE-1H-Adaptive-Regime-V4`。
- 当前状态：`diagnostic pruned tuned baseline / NO-GO / not live-ready / not promoted`。
- 家族实盘判断：`NO-GO`。
- 原因：2026-07-10 精确联合状态机审计推翻了旧的“两腿独立模拟后合并”近似指标；V4 精确 base reused holdout 已降至 `9.0210x`，K+2 为 `7.8530x / -25.04%`，8 bps/fill 为 `14.1032x / -22.46%`。2026-07-13 的 `2,400` 个 VWAP 确认式第三腿严格搜索中，精确三腿联合门槛通过数为 `0`。此外仍没有生产 runner、重启恢复、交易所订单/仓位对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。
- 下一决策门：若继续增加第三腿，应转向与 VWAP/Stoch 不同的信息源或事件机制，并继续使用精确联合增量门槛；不得围绕已揭示失败对照追参。

## 数据与成本口径

- Exchange：Binance。
- Market：USD-M perpetual。
- Symbol：`HYPEUSDT`。
- Timeframe：`1h`。
- 数据：标准 raw/normalized 数据湖，闭合 K `2025-05-30 10:00 UTC` 至 `2026-07-02 02:00 UTC`，共 `9,545` 根。
- 数据质量：missing `0`、duplicate `0`、critical null `0`、OHLCV violation `0`、raw/normalized mismatch `0`、normalized unclosed `0`。
- 资金费：历史资金费 `2,385` 条，按逐笔持仓区间计入。
- 成本：手续费 `0.001/fill`，滑点 `4 bps/fill`。
- 执行：闭合 K 信号，下一根 `1h` open 市价入场；单仓不重叠；同刻冲突 DI-cross 优先；stop-first；gap-open stop 按 open 成交。
- 计分起点：指标 warmup 后 `2025-07-14 10:00 UTC`。

## 版本规则

| 版本 | 说明 |
| --- | --- |
| `HYPE-1H-Adaptive-Regime-V1` | 第一版正式登记基线，来自 `DI-cross + Stoch-reversal` 最强冻结边界；不是 live/paper-live/dry-run/candidate/handoff。 |
| `HYPE-1H-Adaptive-Regime-V2` | V1 全字段消融后的干净等价版本，删除 dormant 或固定状态机字段；DI、Stoch 和 merged 逐笔交易签名与 V1 完全一致；不是 promotion。 |
| `HYPE-1H-Adaptive-Regime-V3` | V2 消融引导组合 `di_roc_off__stoch_th55` 的登记版；base K+1 明显增强，但 K+2/8bps 压力仍失败，不是 promotion。 |
| `HYPE-1H-Adaptive-Regime-V4` | V3 剪枝后 prefit 三场景微调的登记版；参数槽从 `34` 降至 `25`，base K+1 显著强于 V3，但 K+2/8bps 回撤仍超 `20%`。 |
| 后续版本 | 只有在冻结参数、保留数据质量证据、完成 live-executable 审计并写入本主账后，才可登记为新的 `Vx`；高年化但压力失败的 tune 只能记录为 rejected diagnostic。 |

## 版本台账

| Version | Status | Core idea | Evidence | Decision |
| --- | --- | --- | --- | --- |
| `HYPE-1H-Adaptive-Regime-V1` | diagnostic baseline / NO-GO / not live-ready | `DI-cross` 趋势腿 + `Stoch-reversal` 反转腿，闭合 K 信号、K+1 open 入场；DI fixed ATR bracket，Stoch ATR trailing；固定权益名义仓位，DI 优先合并单仓。 | `specs/hype-1h-ar-v1-baseline-spec.md`；`ablations/hype-1h-ar-v1-full-parameter-ablation-2026-07-02.md`；`diagnostics/hype-1h-adaptive-regime-boundary-audit-2026-07-01.md` | Current full `9.6838x`、`-19.64%` 最大回撤、`78.26%` 胜率、`69` 笔；reused holdout `5.1305x`。未达 `10.0x` 硬门槛，压力测试缺缓冲，维持 `NO-GO`。 |
| `HYPE-1H-Adaptive-Regime-V2` | clean equivalent diagnostic baseline / NO-GO / not live-ready | 保留 V1 两条腿真实生效参数，删除 `40` 个 dormant 或固定状态机字段槽；策略行为与 V1 完全相同。 | `specs/hype-1h-ar-v2-clean-baseline-spec.md`；`ablations/hype-1h-ar-v2-full-parameter-ablation-2026-07-02.md`；`notes/hype-1h-ar-v2-active-parameter-tune-2026-07-02.md`；`diagnostics/hype-1h-ar-v2-tune-frontier-live-audit-2026-07-02.md`；`notes/hype-1h-ar-v2-live-robust-prefit-tune-2026-07-02.md`；`notes/hype-1h-ar-v2-window-backtest-2026-07-02.md` | 与 V1 逐笔等价，current full 仍为 `9.6838x / -19.64% / 78.26% / 69 trades`。V2 clean `34` 字段槽全参数消融中，完整 current full + reused holdout target-like 通过 `0` 行；普通微调 `19,600` 组与扩大稳健预拟合 `640,000` 组均未形成更优实盘版本，维持 `NO-GO`。 |
| `HYPE-1H-Adaptive-Regime-V3` | diagnostic baseline / NO-GO / not live-ready | V2 消融引导组合：DI 关闭方向化 ROC 下限过滤（`min_dir_roc_bps=-10000`），Stoch 将 `threshold_high` 从 `60` 收紧到 `55`。 | `specs/hype-1h-ar-v3-baseline-spec.md`；`notes/hype-1h-ar-v2-ablation-combo-retest-2026-07-06.md`；`ablations/hype-1h-ar-v3-full-parameter-ablation-2026-07-06.md` | Current full `15.0530x / -19.11% / 79.73% / 74 trades`；reused holdout `9.0300x / -19.11% / 76.47% / 17 trades`，仍低于 `10x` 硬门槛；K+2 current full `3.0574x / -31.93%`，8bps current full `9.4070x / -28.40%`，维持 `NO-GO`。 |
| `HYPE-1H-Adaptive-Regime-V4` | diagnostic pruned tuned baseline / NO-GO / not live-ready | V3 剪枝后 `25` 参数槽微调：DI `min_adx=10`、`require_body_dir=false`、`sl_atr=4.5`；Stoch `min_adx=0`、`max_atr_bps=500`、`macd_slow=55`、`cooldown_bars=36`，并保留 `threshold_high=55`。 | [`specs/hype-1h-ar-v4-pruned-tuned-baseline-spec.md`](specs/hype-1h-ar-v4-pruned-tuned-baseline-spec.md)；[`notes/hype-1h-ar-v3-prune-and-tune-2026-07-07.md`](notes/hype-1h-ar-v3-prune-and-tune-2026-07-07.md)；[`diagnostics/hype-1h-ar-v4-execution-pressure-optimization-2026-07-10.md`](diagnostics/hype-1h-ar-v4-execution-pressure-optimization-2026-07-10.md)；[`notes/hype-1h-ar-v4-vwap-third-leg-search-2026-07-13.md`](notes/hype-1h-ar-v4-vwap-third-leg-search-2026-07-13.md) | 精确联合回放 current full `20.9748x / -19.11% / 80.00% / 75 trades`；reused holdout `9.0210x / -19.11%`。K+2 `7.8530x / -25.04%`，8bps `14.1032x / -22.46%`；VWAP 确认式第三腿联合门槛 `0/2,400`，不登记 V5，维持 `NO-GO`。 |

## V1 / V2 / V3 / V4 冻结指标

| Window | Annual multiple | Annual return | Max DD | Win rate | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V1/V2 Prefit | `11.6665x` | `+1066.65%` | `-16.93%` | `79.25%` | `53` | `7.267` |
| V1/V2 Reused holdout | `5.1305x` | `+413.05%` | `-19.64%` | `75.00%` | `16` | `4.342` |
| V1/V2 Current full | `9.6838x` | `+868.38%` | `-19.64%` | `78.26%` | `69` | `6.486` |
| V3 Prefit | `17.4864x` | `+1648.64%` | `-16.93%` | `80.70%` | `57` | `8.288` |
| V3 Reused holdout | `9.0300x` | `+803.00%` | `-19.11%` | `76.47%` | `17` | `5.521` |
| V3 Current full | `15.0530x` | `+1405.30%` | `-19.11%` | `79.73%` | `74` | `7.549` |
| V4 Reused holdout（精确联合） | `9.0210x` | `+802.10%` | `-19.11%` | `73.68%` | `19` | `3.701` |
| V4 Current full（精确联合） | `20.9748x` | `+1997.48%` | `-19.11%` | `80.00%` | `75` | `8.006` |

V1 与 V2 的 DI component trade signature、Stoch component trade signature、merged trade signature 均为 exact equal。

## V2 最近窗口复核

| Window | Trades | Win rate | Total return | Max DD | Annual multiple |
| --- | ---: | ---: | ---: | ---: | ---: |
| 最近 7 天 | `1` | `100.00%` | `+3.91%` | `-0.56%` | `7.3908x` |
| 最近 30 天 | `8` | `87.50%` | `+36.09%` | `-16.37%` | `42.5963x` |
| 最近 90 天 | `17` | `70.59%` | `+42.11%` | `-19.64%` | `4.1624x` |
| 最近 180 天 | `35` | `71.43%` | `+165.21%` | `-19.64%` | `7.2364x` |
| 最近 365 天 | `69` | `78.26%` | `+795.75%` | `-19.64%` | `9.6838x` |

滚动 `7d` 切片共 `50` 个，其中 `11` 个零交易窗口；`30d` 切片交易数中位数 `5`，最少 `2`、最多 `10`。短窗口年化只作形状诊断，不作 promotion 依据。

## V2 全参数消融摘要

`ablations/hype-1h-ar-v2-full-parameter-ablation-2026-07-02.md` 覆盖 V2 clean 配置接口的 `34` 个字段槽：DI-cross `15` 个，Stoch-reversal `19` 个；共输出 `98` 行（含 baseline 与两条 leg_removed 诊断行），coverage missing fields 为 `0`。

单字段消融结果：

- Prefit 同时提高年化、降低回撤且胜率 `>=50%`：`1` 行。
- Current full 同时提高年化、降低回撤且胜率 `>=50%`：`13` 行。
- 完整 current full + reused holdout target-like 通过：`0` 行。

因此本轮消融只提供参数敏感性证据，不创建 `V2.1` 或 `V3`，也不改变 `NO-GO / not live-ready` 状态。

## V2 消融引导组合复测

`notes/hype-1h-ar-v2-ablation-combo-retest-2026-07-06.md` 只复测 V2 全参数消融提示的少量组合：DI `4` 个候选 × Stoch `4` 个候选，共 `16` 个组合，并对每个组合执行 base K+1、K+2 延迟和 8 bps/fill 滑点压力。

结果：

- Base K+1 target gate 通过：`0/16`。
- K+2 与 8bps 同时通过：`0/16`。
- 最佳 base 组合：`di_roc_off__stoch_th55`（等价方向还有 `di_roc12_off__stoch_th55`），current full `15.0530x`、最大回撤 `-19.11%`、胜率 `79.73%`、`74` 笔；reused holdout `9.0300x`、最大回撤 `-19.11%`。
- 同一最佳组合在 K+2 下 current full 仅 `3.0574x`、最大回撤 `-31.93%`；8bps 下 current full `9.4070x`、最大回撤 `-28.40%`。

当时结论：base 口径下有明显样本内/已解锁后段改善，但 holdout 年化仍低于 `10x`，延迟和滑点压力下回撤穿越 `20%`；因此不能创建 promotion 版本。2026-07-06 用户要求将最佳 base 组合登记为 V3，故 V3 只作为 diagnostic baseline 记录，不改变 `NO-GO / not live-ready` 状态。

## V3 全参数消融与时间片复核

`ablations/hype-1h-ar-v3-full-parameter-ablation-2026-07-06.md` 覆盖 V3 clean 配置接口 `34` 个字段槽；输出 `98` 行，coverage missing fields 为 `0`。

结果：

- Current full 同时提高年化、降低回撤且胜率 `>=50%`：`9` 行。
- 完整 current full + reused holdout target-like 通过：`5` 行。
- 最近 90 天：`18` 笔、胜率 `72.22%`、总收益 `+60.83%`、最大回撤 `-19.11%`。
- 最近 180 天：`36` 笔、胜率 `72.22%`、总收益 `+200.15%`、最大回撤 `-19.11%`。
- 滚动 `30d` 切片 `11/11` 正收益，交易数中位数 `6`；滚动 `7d` 切片 `50` 个中 `9` 个零交易窗口。

这些结果说明 V3 在 base 口径和时间片形状上优于 V2，但仍未修复延迟/滑点压力失败；不改变 `NO-GO / not live-ready` 状态。

## V3 参数剪枝与预拟合微调

`notes/hype-1h-ar-v3-prune-and-tune-2026-07-07.md` 验证了 V3 的 `34` 个字段槽中 `9` 个在当前数据上 dormant，可整体移除且逐笔交易路径与 V3 exact equal（DI、Stoch、merged 三层签名一致）：

- DI 移除：`ema_htf`、`max_adx`、`roc_window`、`min_dir_roc_bps`、`max_dist_ema_bps`、`max_aligned_funding_bps`。
- Stoch 移除：`ema_htf`、`max_dist_ema_bps`；`sl_atr` 固化为 `4.0` 安全兜底（3-6 ATR 变体全 path-equal，从未触发）。
- 剪枝后剩 `25` 个字段槽（DI `9` + Stoch `16`）。

剪枝后微调只用 prefit 选参（DI 网格 `972` × Stoch 网格 `6,144`，单腿达标取 top，组合 `169` 个，前 `17` 名跑 K+1/K+2/8bps 三场景 prefit 稳健排名，冻结前 `5` 名后揭示）：

- 冻结最佳组合 base K+1 current full `22.8128x / -19.11% / 81.08% / 74 trades`，reused holdout `13.0662x / -19.11%`，三项都优于 V3。
- 但同一组合 K+2 current full `8.7014x / -23.56%`，8bps current full `15.3677x / -22.46%`，回撤仍穿越 `20%`。
- 结论：剪枝方向成立，已按用户要求登记为 V4 diagnostic baseline；它不是 promotion，不改变 `NO-GO / not live-ready`。

以上是 2026-07-07 的旧近似回放历史记录；2026-07-10 精确联合状态机审计已将其指标 supersede。

## V4 精确状态机与执行压力优化

`diagnostics/hype-1h-ar-v4-execution-pressure-optimization-2026-07-10.md` 发现旧 ensemble 先独立模拟两腿、再合并，导致被另一腿挡掉的虚拟交易仍错误触发单腿持仓/冷却并压掉后续信号。精确单账户联合回放在 base/K+2/8bps 三个场景均多出 `1` 笔真实 Stoch 空单：

- Base K+1 current full：`20.9748x / -19.11% / 80.00% / 75 trades`；reused holdout `9.0210x / -19.11% / 73.68% / 19 trades`。
- K+2 current full：`7.8530x / -25.04%`。
- 8bps current full：`14.1032x / -22.46%`。

压力优先搜索覆盖 DI `223` 个风险变体、Stoch `589` 个风险变体和 `930` 个精确 ensemble；`431` 个组合通过 prefit 三场景 gate，但冻结前 `12` 名没有任何一行在 reused holdout/current full 同时让三个场景回撤小于 `20%`，完整 target pass 为 `0`。

后验机制诊断确认：DI 降至 `2.5x`、Stoch 硬止损收至 `2 ATR`、Stoch 最长持仓缩至 `6h`，可得到 base `14.3901x / -14.20%`、K+2 `7.9815x / -19.64%`、8bps `11.2061x / -18.71%`。该方向修复回撤，但 K+2 与后段年化不足，只作为风险预算方向，不登记 V5。

## V1 机制摘要

### 腿 A：DI-cross

- 信号：`+DI14 - -DI14` 零轴交叉。
- 过滤：`12 <= ADX14 <= 36`、`RVOL48 >= 2`、`ATR14/close <= 250 bps`、方向化 `ROC24 >= -200 bps`、距 `EMA89 <= 750 bps`、方向与闭合 `12h` EMA regime、K 线实体和最后已知 funding 一致。
- 退出：入场后立即放 `TP=1.5 ATR14`、`SL=4.0 ATR14`，最长 `18` 根 `1h` K。
- 权益暴露：固定 `3.0x`。

### 腿 B：Stoch-reversal

- 信号：`Stoch(21)` K/D 在超卖或超买区反向交叉。
- 过滤：`ADX14 >= 12`、`RVOL48 >= 1`、`200 <= ATR14/close <= 400 bps`、距 `EMA55 <= 2500 bps`、`MACD(8,21,5)` 转向确认。
- 退出：入场后立即放 `SL=4.0 ATR14`，闭合 K 后按 `trail_activation=1.0 ATR`、`trail=1.0 ATR` 更新 trailing stop，最长 `8` 根 `1h` K。
- 权益暴露：固定 `2.0x`；出场后冷却 `24` 根。

## 复现

```bash
uv run python research/hype/1h-adaptive-regime/scripts/fetch_hype_binance_1h.py --refresh
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v1_full_ablation.py
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v2_clean_tune.py
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v2_window_backtest.py
```

## 约束提醒

后续任何 agent 如果按用户要求“登记为 Vx / 记录为 Vx / 写成 Vx”，必须更新本文件的版本规则、版本台账和当前状态；只写 version spec、research note 或 decision log 不算完成版本登记。
