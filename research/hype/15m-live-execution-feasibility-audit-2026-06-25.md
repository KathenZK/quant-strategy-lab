# HYPE 15m 三家族实盘可执行性复审

日期：2026-06-25

## 结论摘要

本次复审对象是三个 HYPE 15m 策略家族：

- `HYPE-Candle-Count-Reversal`（`research/hype/15m-candle-count-reversal/`）
- `HYPE-EMA-Crossover`（`research/hype/15m-ema-crossover/`）
- `HYPE-EMA-Trend-Breakout`（`research/hype/15m-ema-trend-breakout/`）

核心结论：

| Family | 当前判断 | 高收益是否可直接当实盘预期 | 是否发现类似 `HYPE-5M-PBTR` lockout old-stop 穿价补成交问题 |
| --- | --- | --- | --- |
| `HYPE-Candle-Count-Reversal` | 降级为 execution-risk / diagnostic；不应 live-approved | 不可以。`V35 +8357.56%` 依赖 close 入场、close 提前退出、mark high/low 触发后按目标价成交，必须用 live-realistic runner 重跑 | 未发现同一类 lockout old-stop，但存在 stop/take 穿越后仍按 stop/take 价成交、close 成交和 early close 出场乐观风险 |
| `HYPE-EMA-Crossover` | 保持 research candidate；不应 live-approved | 不可以。`V17/V17.1` 时序相对干净，但样本只有 33 笔，且没有生产 runner / 重启恢复 / 真实订单审计 | 未发现同一类 lockout old-stop；脚本为信号收盘后下一根 open 入场、结构/预警退出下一根 open，硬止损用 intrabar high/low |
| `HYPE-EMA-Trend-Breakout` | 三者中实盘时序最完整；仍只可小资金/保守 sizing | 不可以把 `Binance V35 +6474.19%` 当预期。它已按 live-realistic 口径修正，但仍是样本内调参 + 交易所特化 | 旧 V30/V32 legacy 口径确有偏乐观；V35/V36 文档已修正为 K2 open、上一根 ATR、禁止同 K 再入 |

## 共同审计标准

本次只接受可由实盘 runner 复现的收益口径：

1. 信号只能使用已收盘 K 线。
2. 入场必须是明确的下一可成交时点，不能用已经知道收盘后的同根理想 close。
3. 收盘类退出必须下一根 open 或实际市价成交，不应按已知 close 理想成交。
4. stop/take 使用 high/low 触发时，不能默认穿越后仍精确按 stop/take 价成交；至少要按 stop-market + 额外滑点审计。
5. 同一根 K 内 stop/take 同时可触发时，应按 stop 优先或用更细粒度数据确认。
6. 必须覆盖订单保护、重启恢复、缺失数据、持仓对账和 kill switch。

本轮为文档与脚本审计；当前 workspace 未发现本地 HYPE 15m parquet 数据和 retained V17 artifact 文件，因此没有重跑全量 backtest。

## 1. HYPE-Candle-Count-Reversal

### 主要发现

`HYPE-CC-V35` 主表记录 `+8357.56% / -33.26% / 340 trades`，但它不应直接解释为实盘可复制收益。

关键执行风险：

- `hype-v21-reproducible-params.md` 明确写入场在本根 `close` 开仓；`hype-v35-reproducible-params.md` 的处理顺序也是每根 closed bar 末尾检查信号并入场，没有 next-open 可执行重跑结果。
- `V35` 的 `early_main`、`early_counter_opposite`、`early_counter_favorable` 都写为“按当前 close 平仓”。这是收盘后才确认的条件，实盘只能在下一 tick / 下一根 open 或实际市价成交，不能默认拿到已知 close。
- ATR 止盈止损用 `mark_high/mark_low` 触发，并按止盈/止损价成交；这对 stop-market 场景仍偏乐观。HYPE 插针或跳价时，真实成交可能劣于 stop price。
- `V35` 过拟合诊断已经显示核心参数高度敏感：`10/8`、`trend_window_bars=96`、双向 `12/9` 是主要样本外风险点；`target_atr_pct=0.006` 只是收益/回撤放大器。

### 与 pullback 问题的关系

这不是完全同一种 `min_hold/lockout` 后“价格早已穿越，却按旧 stop 价补成交”的错误；`HYPE-CC` 没有同类 protected interval。问题更基础：成交口径还没有被整体切换到 live-realistic，尤其是 close 入场/出场和 stop-market 穿越滑点。

### 当前决策

`HYPE-Candle-Count-Reversal` 全部高收益版本暂不得称为 live / paper-live candidate。下一步必须先做：

- close-entry vs next-open / delayed-open 对比；
- early close exit 改为 next-open 或 close+真实延迟成交；
- stop/take 从精确 stop price 改为 trigger-market slippage stress；
- 入场后立即挂保护单、重启恢复、持仓对账的 runner 规格。

在上述审计前，`V35 +8357.56%` 只能作为 legacy upper-bound / diagnostic。

## 2. HYPE-EMA-Crossover

### 主要发现

`HYPE-EMA-X-V17` / `V17.1` 的收益很高：

- `V17`: `+2910.74% / -17.79% / 33 trades`
- `V17.1`: `+3861.48% / -19.44% / 33 trades`

脚本层面没有看到 pullback 式旧 stop 补成交问题。`research_hype_v13_late_reentry.py` / `research_hype_v17_hybrid_ablation.py` 的执行顺序是：

- 当前 K 收盘生成 signal；
- 设置 `pending_entry`；
- 下一根 bar 的 `open` 成交；
- entry ATR 使用前一根已完成 K；
- hard stop 用持仓 K 的 high/low 触发；
- opposite cross / hard swing / warning confirm 等收盘确认后，在下一根 open 出场。

这比 `HYPE-CC` 的 close 口径干净，也没有 `HYPE-5M-PBTR` 那种 lockout 后按 stale stop 成交的问题。

### 主要风险

仍不能 live-approved：

- 当前 README 已明确写 `promoted research candidates, not live-approved production strategies`。
- `V17.1` 的提升主要来自 `hq_scale=1.1`，是 sizing/risk-budget 版本，不是新 alpha。
- 1Y 只有 33 笔交易，LQ 卫星只有 4 笔；胜率和回撤边界高度依赖少量样本。
- 没有看到与 `HYPE-EMA-TB-V35/V36` 同等级的 production runner spec、保护单恢复、实盘事件库审计。
- 硬止损仍按 high/low 触发后 stop price 成交；虽然 `V17/V17.1` 样本中 stop loss 为 0，但实盘不能因此忽略 stop-market 穿越。

### 当前决策

`HYPE-EMA-Crossover` 可保留为研究候选，但不得宣传为“实盘没问题”。下一步应补：

- retained artifacts 复原或重跑；
- full live-realistic audit report；
- stop-market stress；
- 小资金 dry-run / paper-live runner 状态机规格。

在这些完成前，`+2910%` / `+3861%` 应按 research slice 表现阅读，不当作实盘收益预期。

## 3. HYPE-EMA-Trend-Breakout

### 已修复的旧口径问题

这条线已经显式审过旧口径：

- `hype-trend-strategy-v30-spec.md` 记录 legacy `shift(1)+close[t]` 只能作为参考上限：`+2188.01% / -16.36%`；可执行 next-open 降为 `+456.51% / -34.30%`。
- `hype-v32-live-realistic-backtest.md` 记录旧 V32 `+4001.27%` 在 live-realistic 后降到 `+1650.74%`，原因是禁止同 K 回到 open 再入、使用上一根 ATR、指标退出下一根 open。

因此，`HYPE-EMA-TB` 的旧高收益确实曾包含明显偏乐观执行假设；这部分不能再当实盘基准。

### 当前 V35/V36 口径

`hype-trend-strategy-v35-spec.md` 和 `hype-trend-strategy-v36-spec.md` 已采用更严格的 live-realistic 规则：

- K0 close 确认信号；
- 跳过完整 K1；
- K2 open 入场；
- entry ATR 使用 K1 已完成 ATR；
- TP/SL 入场后挂保护单，持仓 K high/low 触发，stop 优先；
- indicator / timeout 退出为收盘确认、下一根 open 成交；
- 禁止同一根 K 平仓后再入。

这条线目前不是 pullback 同类问题。它也是三者中已有实盘执行证据最多的一条：`hype-v35-live-execution-audit.md` 记录 2 笔真实开仓均止盈、净 PnL `+20.5680 USDT`、处理延迟稳定期 P95 `5.76s`。

### 仍需折价的原因

`Binance V35 +6474.19%` 仍不能直接当实盘预期：

- 文档自己写明这是同样本消融选优后的组合，必然高估。
- 47% 左右交易触顶 3x；sizing 是收益放大器。
- Binance 原版遇到 2025-10-10 类 `-41%` 单根插针时，3x 杠杆可能扛不住。
- `V35` 在 Hyperliquid / OKX native 结果明显弱于 Binance；交易所特化很强。
- stop-market 实盘滑点仍可能劣于固定 stop price。

相对稳妥的锚不应是 Binance `+6474%`，而应参考：

- 保守 sizing 档 `0.012/0.010`: Binance `+1312.14% / -15.59%`；
- 或跨交易所更保守结果再打折；
- 若执行在 Hyperliquid，应优先参考 `V36` 跨所执行规格和 spread guard。

### 当前决策

`HYPE-EMA-Trend-Breakout` 可以保留为三者中优先继续实盘观察的方向，但必须使用 `V35/V36` live-realistic spec，而不是任何 legacy close / same-K-reentry 数字。实盘讨论必须附带保守 sizing、逐仓、保护单恢复、跨所价差保护和 kill switch。

## 最终回答口径

这三个策略不能统一回答“实盘真的没问题”。更准确的分级是：

1. `HYPE-Candle-Count-Reversal`: 目前最危险，高收益需要先重跑 live-realistic；现有 `+8357%` 不可信为实盘预期。
2. `HYPE-EMA-Crossover`: 没看到 pullback 同类穿价 bug，但只有 research candidate 级别；高收益需大幅折价，不能 live-approved。
3. `HYPE-EMA-Trend-Breakout`: 已经识别并修正旧执行口径，是三者里最接近可实盘的一条；但 Binance 高收益仍是样本内高估，实盘应按保守 sizing 和跨所/滑点压力结果折价。

