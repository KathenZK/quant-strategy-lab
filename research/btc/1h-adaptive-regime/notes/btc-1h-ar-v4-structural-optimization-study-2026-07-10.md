# BTC-1H-Adaptive-Regime-V4 结构优化研究 - 2026-07-10

## 结论

V4 的下一步不应继续扩大 Keltner/CCI 参数邻域。现有证据已经证明：

- V4 是 V3 的 `19` 参数最小等价面，`8` 个 active 槽位在当前路径上不生效；
- V3 全参数 one-at-a-time 严格改善为 `0`；
- 最小表面 `24,576` 组微调中，年化、回撤、胜率三项同时严格改善为 `0`；
- V2 -> V3 的主要跃升包含 Keltner/CCI 曝光从 `1.8x/2.7x` 提升到 `2.4x/3.5x`，不能把杠杆放大误认为新增 alpha；
- V4 prefit `6.16x / -12.87% / 87.30%`，但 reused holdout 仅 `1.90x / -17.47% / 81.82%`，最近 30 天只有 `4` 笔，策略仍低频且样本外衰减明显。

因此优化问题已经从“怎样调现有参数”变为：

1. 是否存在与 V4 低重叠、在 V4 空仓时段有正边际的第三腿；
2. 是否应把当前 ADX 软分区改成显式 regime router；
3. 是否应调整单仓冲突/出场/风险层，而不是继续提高固定杠杆。

本轮对原 30 万组搜索中保留下来的六类候选腿做了增量占用审计。结果显示，**没有任何现成候选可以直接登记为 V5**。下一阶段优先研究 `VWAP revert short-only`、`wick reject` 和 `MACD flip` 的结构化变体；`ema_pullback`、`DI cross`、`squeeze release` 不应以当前参数直接接入。

状态保持：`V4 registered / not promoted / not live-ready`。

## 基线与数据边界

- 市场：Binance USD-M Futures `BTCUSDT` perpetual。
- 周期：`1h`。
- 数据：`2024-07-02T10:00:00Z` 至 `2026-07-02T09:00:00Z`，`17,520` 根闭合 K；missing=`0`，duplicate=`0`。
- 成本：fee `0.001`/fill、slippage `4 bps`/fill、历史资金费。
- 执行：闭合 K 信号，下一根 open 市价入场；入场即有保护 stop/TP；stop-first；单仓、不加仓。
- `research_prefit`：截至 `2026-04-02T10:00:00Z`，可用于研究。
- `reused_holdout`：`2026-04-02T10:00:00Z` 至 `2026-07-02T10:00:00Z`，已经污染，只能作审计列。
- `untouched_forward`：应从 `2026-07-02T10:00:00Z` 之后开始锁定；当前即使补数也只有约 8 天，不足以作 promotion 判决。

## 为什么现有机制已到局部上限

### 当前“regime”只是软分区

V4 不是显式状态机：

- Keltner leg 要求 `ADX14 >= 40`；
- CCI leg 要求 `ADX14 <= 40`；
- 两腿独立生成交易，再按 prefit leg score 合并；
- 已持仓期间，另一腿新信号直接忽略。

这相当于 ADX≈40 的软分区 + 单仓抢占，不是带 hysteresis、neutral state 和转移规则的 regime router。其结构性问题是：

- regime 边界附近容易抖动；
- 没有显式“趋势 / 震荡 / 过渡压缩”三态；
- 新腿即使有信号，也可能大量被现有持仓挡住；
- prefit score 是静态全样本优先级，不能根据当下 regime 动态选择腿。

### 原搜索已经覆盖 16 类 style

2026-07-02 的 `300,768` 组搜索已经包含：

`ema_cross`、`macd_flip`、`donchian_break`、`bb_revert`、`bb_break`、`rsi_reversal`、`stoch_reversal`、`cci_reversal`、`williams_reversal`、`ema_pullback`、`keltner_break`、`squeeze_release`、`di_cross`、`vwap_revert`、`momentum_break`、`wick_reject`。

因此“新增现有 style”不是新发现。真正需要改变的是搜索目标：原搜索按单腿/ensemble 绝对 prefit score 排序；下一轮应固定 V4，只优化候选腿对 V4 的**边际贡献**。

## V4 新腿增量占用审计

### 方法

- 每种候选 style 取原搜索中 prefit score 最高的 retained single；
- 同时测试原始仓位合同和 `fixed 1x` 标准化版本；
- V4 冻结交易拥有绝对优先级，候选腿只能填充 V4 未占用的时段；
- 选取候选时不读取 reused holdout；
- 报告与 V4 入场重叠、被 V4 持仓挡住比例、增量交易和各窗口边际收益。

该测试只是诊断：它复用原搜索单腿，不是新参数搜索，也不构成候选版本。

### `fixed 1x` 结果

| Style | Prefit trades | ±3h entry overlap | Blocked by V4 | Added prefit trades | Prefit Δreturn | Validation Δreturn | Reused holdout Δreturn | Prefit ΔDD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `vwap_revert` | `74` | `9.68%` | `11.83%` | `60` | `+272.66%` | `+17.62%` | `-19.38%` | `+1.83pp` |
| `wick_reject` | `41` | `5.88%` | `9.80%` | `37` | `+174.19%` | `+3.03%` | `-1.97%` | `-0.21pp` |
| `di_cross` | `67` | `5.13%` | `16.67%` | `53` | `-143.57%` | `-41.91%` | `-11.25%` | `+0.20pp` |
| `squeeze_release` | `40` | `2.27%` | `11.36%` | `26` | `-485.96%` | `-19.00%` | `-3.16%` | `-4.05pp` |
| `macd_flip` | `43` | `5.88%` | `9.80%` | `28` | `-819.79%` | `+21.83%` | `+19.90%` | `-3.27pp` |
| `ema_pullback` | `47` | `10.00%` | `10.00%` | `32` | `-1192.26%` | `-55.95%` | `-27.90%` | `-7.34pp` |

### 结果解释

#### `vwap_revert`：首要研究线，但不能直接接入

`fixed 1x` 后：

- merged prefit：`6.68x / -11.04% / 90.24% / 123`；
- merged validation：`5.00x / -10.80% / 88.24% / 51`；
- reused holdout：`0.92x / -17.47% / 68.42% / 19`。

它与 V4 重叠低、prefit 边际明显，但 reused holdout 转为负收益。由于 reused holdout 不可用于回调参数，正确结论不是“用 holdout 调 VWAP”，而是：

- 把 `VWAP revert` 限定为 **short-only range leg**，补足 CCI 只做多的结构缺口；
- 搜索目标改为 validation 边际 + 低重叠 + 1x 正期望；
- 冻结后等待 untouched forward，不再读取 reused holdout 选参。

#### `wick_reject`：低复杂度备选

`fixed 1x` 后：

- merged prefit：`6.49x / -13.08% / 80.00% / 100`；
- reused holdout：`1.78x / -17.75% / 62.50% / 16`。

它提供低重叠交易和正 prefit 边际，但胜率明显下降、回撤略恶化。适合作为：

- 低杠杆、低优先级的过渡态/拒绝形态腿；
- 仅在 `ADX` 中间带或波动扩张失败后启用；
- 不适合作为全天候第三腿。

#### `macd_flip`：可能是 regime hedge，不是直接加法腿

`fixed 1x` 后：

- prefit 总收益相对 V4 大幅下降；
- validation `+21.83%`、reused holdout `+19.90%`；
- merged holdout annual 提升到 `3.56x`，但 prefit annual 降到 `4.37x`。

这说明它和 V4 的时间分布可能不同，适合研究为：

- 替换 Keltner 的趋势腿 A/B；
- 在 V4 历史弱 regime 中启用的 hedge/fallback；
- 不应直接全天候叠加。

#### 当前应降级的候选

- `ema_pullback`：prefit、validation、reused holdout 都明显拖累，当前参数直接淘汰；
- `di_cross`：低重叠但边际收益为负，当前参数直接淘汰；
- `squeeze_release`：增加回撤且三窗口边际弱，当前参数直接淘汰。

“当前参数淘汰”不等于机制永远无效，但它们不应成为下一轮第一优先级。

## 推荐的优化架构

### Phase 1：先改研究目标，不先改引擎

冻结 V4 两腿与曝光，建立 `V4 + one new leg` 的边际搜索：

1. 候选仅允许填充 V4 空仓，不抢占 V4；
2. 新腿先以 `fixed 1x` 筛选，禁止靠杠杆过 gate；
3. 目标函数以 validation/prefit 边际、重叠率、DD 和独特成交为主；
4. 每条腿必须报告：
   - unique entries；
   - blocked-by-V4 rate；
   - entry / holding overlap；
   - `PnL(V4 + leg) - PnL(V4)`；
   - leave-one-leg-out；
   - 最差月、MAE、CVaR；
   - K+2 / 8 bps 成本压力。

首批只搜索：

1. `vwap_revert short-only`；
2. `wick_reject` 低杠杆过渡态；
3. `macd_flip` 替换 Keltner，而不是直接加法。

### Phase 2：引入显式三态 regime router

只有 Phase 1 出现正边际腿，才改组合层：

- `trend`：ADX 高且 H4 同向；Keltner 或 MACD/Keltner 二选一；
- `range`：ADX 低；CCI long + VWAP short；
- `transition/compression`：ADX 中间带或波动状态切换；允许 wick reject，其他腿禁入；
- 使用 hysteresis，避免 ADX 在单阈值附近来回切换；
- regime 只用已闭合 `1h/4h` 特征，下一根 open 执行。

不建议立即做 preemption。V4 当前单仓忽略新信号虽然会损失机会，但 live 状态机简单；在第三腿尚未证明增量前引入强平让位，会把换仓成本和状态恢复复杂度混入 alpha 研究。

### Phase 3：再研究出场与风险层

当新腿通过 Phase 1/2 后，再单独消融：

- 趋势腿 fixed bracket vs bar-close 更新、次 K 生效的 trailing；
- 新腿 fixed sizing vs risk sizing；
- 账户总曝光 cap；
- 不允许 `min_hold` 期间无有效保护；
- 不允许同 K 看完高低点后回写 trailing stop。

仓位/出场必须和信号 alpha 分开评价。任何只靠提高 `fixed_leverage` 的提升不算结构优化。

## 新研究门槛

### Leg research gate

- train / validation 同正；
- validation DD `<20%`；
- validation trades `>=10`；
- prefit trades `>=25`；
- `fixed 1x` 净期望为正；
- 与 V4 任一腿的 ±3h entry overlap `<40%`；
- blocked-by-V4 rate `<70%`。

### V4 增量冻结 gate

- validation 边际收益 `>=0`；
- prefit 边际收益 `>0`；
- prefit DD 不比 V4 加深超过 `2pp`；
- 胜率不下降超过 `3pp`；
- unique added trades `>=8`；
- 新腿贡献至少 `10%` 边际净利，且不能集中在 1–2 笔；
- K+2 / 8 bps 下总收益至少保留 V4 的 `90%`，DD 不加深超过 `3pp`；
- 参数邻域通过率 `>=50%`。

### Forward gate

- `reused_holdout` 永久只作污染审计，不用于筛选；
- 候选冻结后锁定 `2026-07-02T10:00:00Z` 之后的 untouched forward；
- 至少等待 `90` 天且 `>=20` 笔独立成交，取更严格者；
- forward 总收益 `>0`、DD `<20%`、胜率 `>=50%`；
- 未满足样本量时不得登记 promotion 状态。

## 明确不做

- 不继续扩大 V4 的 `19` 参数邻域；
- 不再用年化倍率单目标排序；
- 不直接复制其他资产参数；
- 不把 Donchian/BB/RSI/Stoch/Williams 当成“新机制”换皮；
- 不提高杠杆冲 `10x`；
- 不用 reused holdout 回调新腿；
- 不在没有新腿增量证据前实现 preempt；
- 不迁移 PBTR lockout、ATRVT 动态杠杆或有泄漏风险的事件质量打分。

## 建议执行顺序

1. 冻结 V4 和当前数据哈希；
2. 实现 `VWAP revert short-only` 边际搜索；
3. 并行实现 `wick reject transition-only` 和 `MACD flip replace-Keltner` 小规模搜索；
4. 对最多三个 finalist 做 purged walk-forward / CPCV-lite、成本延迟、邻域和 bootstrap；
5. 若没有候选通过，停止“现有 16 style 加腿”路线；
6. 若有候选通过，冻结最多一个 observation，等待 untouched forward；
7. forward 通过后才讨论新版本和 production runner。

## 证据

- `artifacts/btc_1h_ar_v4_new_leg_increment_2026-07-10.json`
- `artifacts/btc_1h_ar_v4_new_leg_increment_rows_2026-07-10.csv`
- `artifacts/btc_1h_adaptive_regime_ranking_2026-07-02.csv`
- `diagnostics/btc-1h-adaptive-regime-search-2026-07-02.md`
- `diagnostics/btc-1h-adaptive-regime-boundary-audit-2026-07-02.md`
- `notes/btc-1h-ar-v3-param-necessity-2026-07-07.md`
- `notes/btc-1h-ar-v3-minimal-micro-tune-2026-07-07.md`
- `notes/btc-1h-ar-v4-window-backtest-2026-07-07.md`

复现：

```bash
uv run research/btc/1h-adaptive-regime/scripts/audit_btc_1h_ar_v4_new_leg_increment.py
```
