# BTC 多周期趋势 Campaign 历史前沿复现规格

## 0. 身份与状态

- Family：`Binance-MTF-Pullback-Trend-Campaign`（`BIN-MTF-PTC`）。
- Candidate：`BTC weekly-monthly-consensus / 24h continuation / pullback-restart / 3-layer no-half-reduce frontier`。
- 状态：**research frontier only / hard-gate-failed / not registered / not promoted / not live-ready**。
- 本规格用于独立复现历史结果与执行语义，不授权下单、dry-run 或 prospective。
- Historical locked evaluation 未运行；不得用该区间修参数。

## 1. 市场、数据与可见性

- Venue：Binance USD-M perpetual。
- Symbol：`BTC/USDT:USDT`。
- 基础数据：官方 15m OHLCV 与实际 funding rate，UTC。
- 只接受 closed 15m bars；当前审计 cutoff `2026-08-03 11:45 UTC`。
- 每小时必须恰有四根 15m bar。聚合：open first、high max、low min、close last；1h 索引从 hour-open 向后移动一小时，表示最早可见 close 时点。
- 任一缺口、重复、关键 null、非法 OHLC、raw/normalized 不一致为 fail-closed blocker。
- funding 以结算 timestamp 对齐；entry timestamp 当次结算发生在 next-open entry 之前，因此 entry bar 不收该次 funding；此前已持仓 lot 收取。

## 2. 历史治理

Development expanding folds：

1. train `<=2020-12-31 23:59:59 UTC`，evaluate 2021；
2. train `<=2021-12-31 23:59:59 UTC`，evaluate 2022；
3. train `<=2022-12-31 23:59:59 UTC`，evaluate 2023。

每 fold 的 meter train end 再 purge 14d。Revealed diagnostic validation 为 `2024-01-01 <= ts <= 2025-06-30 23:59:59 UTC`。Historical locked evaluation `>=2025-07-01` 未运行且不得作为本规格绩效。

## 3. 24h continuation meter

### 3.1 Decision clock

仅在 UTC hour `%4==0` 的完整 1h visible timestamp 生成 candidate feature row。

### 3.2 基础量

令 `c_t` 为可见 1h close，`r_t=log(c_t)-log(c_{t-1})`，`onset=24`：

```text
past_rms_t = RMS(r, 720h) shifted by 24h
impulse_t = log(c_t) - log(c_{t-24})
direction_t = sign(impulse_t)
r_log_t = past_rms_t * sqrt(24)
scaled_move = abs(impulse_t) / (past_rms_t * sqrt(24))
```

只有 `scaled_move>=0.5` 且 direction 非零进入 candidate 集。

### 3.3 特征

```text
efficiency = abs(impulse) / sum(abs(hourly returns over 24h))
jump_concentration = max(abs(hourly return over 24h)) / sum(abs(hourly returns over 24h))
path_r2 = corr([0..24], log closes over 25 points)^2
acceleration = direction * (recent_12h_move - prior_12h_move) / (past_rms*sqrt(24))
atr_expansion = mean(TR_pct,12h) / median(TR_pct,168h)
directional_rsi = direction * (RSI14-50)/50
```

RSI 使用 simple rolling mean gains/losses；它只描述路径位置。

### 3.4 Label 与模型

训练标签 horizon `72h`：从 candidate 后第一个完整 1h path 开始，先触及：

```text
favorable = candidate_close * exp(direction * r_log)
adverse   = candidate_close * exp(-direction * 0.5 * r_log)
```

先 favorable 为 1，先 adverse 为 0；同一 1h 同时触及按 0；未触及或路径不完整为 unresolved，不进入训练。

模型：`StandardScaler + LogisticRegression(C=1.0,max_iter=2000)`。阈值为 development train probability 的 q80。任何 refit 只使用目标评估段开始前的允许训练数据。

## 4. 高周期方向先验

Candidate 必须同时满足：

```text
direction * (log(c_t)-log(c_{t-168})) > 0
direction * (log(c_t)-log(c_{t-672})) > 0
```

即过去 7d 与 28d 价格变化同向，且均与当前 24h impulse 同向。只有 probability `>=q80 threshold` 的 candidate 可以发起 Probe 或 Add attempt。

## 5. Candidate → Pullback → Restart

### 5.1 Impulse origin

```text
origin = 1h close at candidate_ts - 24h
candidate_close = 1h close at candidate_ts
ATR = mean true range over last 24 complete 1h bars
```

### 5.2 1h pullback

从 candidate 后等待最多 24h：

- running extreme：Long 取新 high，Short 取新 low；
- pullback depth 至少 `0.50*ATR`；
- depth 不得超过从 origin 到 running extreme 的 50%；
- Long 1h close `<=origin` 或 Short 1h close `>=origin` 立即失效；
- 超过最大 depth 失效。

### 5.3 15m restart

Pullback armed 后：

- 最近两根 closed 15m 不再出现新的 pullback extreme；
- Long close 高于此前四根 15m high 的最大值；Short close 低于此前四根 low 的最小值；
- close 位于本 bar 顺势半区；
- 下一根 15m open 发 market order。

Base fill：`raw_open*(1+side*0.0004)`。Stress fill 使用 `0.0008`。

### 5.4 Structure stop

```text
Long stop  = pullback extreme - 0.25*ATR1h(24)
Short stop = pullback extreme + 0.25*ATR1h(24)
```

若 stop 不在 fill 的不利方向，取消。失败 attempt 在 candidate 当下未知：必须占用 pending 槽直到实际结构失效或 24h expiry；高分反方向 candidate 可取消。

## 6. Campaign lots

### 6.1 Probe

- 请求完整 stop-out risk：entry equity 的 `0.25%`。
- Quantity denominator 包含 entry fee、stop adverse fill、exit fee：

```text
stop_fill = stop * (1-side*slippage)
loss_per_unit = side*(entry_fill-stop_fill) + fee*(entry_fill+stop_fill)
requested_qty = entry_equity*0.0025/loss_per_unit
qty = min(requested_qty, 3*entry_equity/entry_fill)
```

Fee `0.001` per fill。

### 6.2 Add eligibility

以 Probe initial fill 和 initial stop 定义 `initial_R=abs(fill-stop)`。Campaign MFE 由 closed 15m 后可见 high/low 更新：

- Add-1：MFE `>=0.5R`；
- Add-2：MFE `>=1R`；
- Add-3：MFE `>=2R`。

达到门槛只写 `eligible_after=next 15m open`。下一次符合第 3–5 节的同方向强 candidate 才发起该层 attempt。每层最多两次 attempt；第二次失败关闭该层和更高层。

### 6.3 Add execution

- 成交时 liquidation equity 必须高于 campaign entry equity；亏损中禁止 add；
- 每层请求 `0.25%` entry-equity risk，使用自己的 fill/stop；
- 所有 lot projected stop-out equity 不得低于 entry equity 的 `99.1%`；hard floor `99.0%`；
- effective leverage `sum(abs(qty)*mark)/liquidation_equity <=3x`；
- 风险空间不足时 partial add，不得放宽 stop。

### 6.4 Stops

- 每个 lot 独立 stop；stop 永不放宽；
- Campaign 已达 +2R 时，新 add 的 causal structure stop 可收紧旧 lot stop，但 Long 新 stop 必须在当前价格以下、Short 在当前价格以上；
- 本 frontier **不执行 half-MFE giveback reduction**；新增 lots 与 Probe 一起由各自 stop 或 336h timeout 管理。

## 7. 持仓维护与退出

- 入场 24h 后若 campaign 从未达到 +1R：下一 15m open 全退；
- 入场 336h：下一 15m open 全退；
- 无固定 TP；
- 高分反方向 candidate：取消 pending add，关闭后续 add 权限；当前 frontier 历史中未形成有意义的 added-lot reduction 增量；
- funding 后重算 projected stop-out equity；低于 operational floor 时在同一 open 对 added lots LIFO partial/full trim；无法恢复且低于 hard floor 时全退并记录 blocker。

## 8. 同 bar 冲突顺序

每根 15m：

1. 已持仓 funding settlement；
2. 各 lot gap stop，按 open adverse fill；
3. 24h validation / 336h timeout / pending risk reduction；
4. 当前可见 4h continuation decision；
5. pending Add/Probe execution；
6. 各 lot intrabar stop；
7. 若仍持仓，更新 closed-bar MFE/MAE/eligibility/pending state；
8. 计算 liquidation equity。

Stop 与同 bar favorable extreme 冲突时 stop 优先。任何 lot 在该 bar stop 后不得使用该 bar 后续 high/low。退出同 bar 禁止重新入场。

## 9. 账本与指标

必须输出：

- 每个 campaign：candidate/entry/exit、side、entry/exit equity、initial fill/stop、MFE/MAE R、attempt counts、fees、funding、hold、net PnL/R、exit reason；
- 每个 action：score、plan、expiry、entry、eligibility、add、stop、risk trim、exit；
- 每根 15m：balance、liquidation equity、bar 内 adverse equity、side、quantity、mark；
- total return、annual multiple、MDD、intrabar MDD、daily Sharpe、PF、win rate、skew、top-1/top-3 concentration、max leverage、max projected stop risk、risk violations；
- direction/year/fold/cost attribution。

## 10. 历史参考值（不是上线承诺）

- Development 2021/2022/2023：三折全正，合并 `+12.7049%`；stress `+10.2077%`。
- Revealed diagnostic validation base：`+11.3016%`，annual `1.0741x`，MDD `-7.2269%`，intrabar `-9.5822%`，PF `1.8696`，47 campaigns，max leverage `0.7293x`。
- Stress：`+9.3252%`，annual `1.0613x`，intrabar MDD `-9.1577%`。
- Top-1/top-3 gross-profit concentration：`72.63%/95.98%`，因此 hard gate failed。

## 11. 验收与禁止事项

复现必须满足：数据 blocker 0、测试通过、同一参数得到接近参考值、risk violation 0。以下任一行为使结果无效：

- 使用未闭合 1h/15m；
- 在 candidate 当下预知未来 attempt 会失败；
- 只按平仓点算 MDD；
- 用 planned risk 乘 R 代替真实 quantity/fee/funding；
- 同 bar 先用 high 授予资格再用更早的 low 成交；
- 删除 2025、short 或最大亏损路径；
- 根据 historical locked evaluation 修改参数；
- 把 research frontier 描述成可上线策略。

## 12. 非复现依赖附录

仓库内核、生成脚本和历史证据索引见 [家族 README](../README.md) 与 [最终研究报告](../diagnostics/binance-mtf-ptc-goal-final-report-2026-08-03.md)。即使没有仓库，本规格前 11 节也应足以独立实现。
