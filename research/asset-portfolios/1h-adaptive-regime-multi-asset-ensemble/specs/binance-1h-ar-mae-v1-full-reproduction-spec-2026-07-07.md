# Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1 完整复现规格 - 2026-07-07

## 给同事 / AI 的使用说明

这份文件是 `Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1` 的完整复现规格。目标是：同事把本文件交给他的 AI 后，可以仅凭本文复现同一条 V1 交易路径、同一组近期分片指标和历史风险判断。

重要：本文件必须视为 standalone spec。文中出现的仓库路径只用于你在本仓库内快速校验，不是复现依赖；如果同事没有这些脚本或主账，也应该能仅凭本文的“数据 schema + 特征计算 + 信号逻辑 + 过滤器 + 出入场状态机 + 参数 JSON + 组合阻塞规则”重写实现。

最短复现命令：

```bash
uv run python research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_mae_single_position_backtest.py
```

复现脚本会输出并落盘：

- 汇总 JSON：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/artifacts/binance_1h_ar_mae_single_position_2026-07-07.json`
- 小时权益曲线：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/artifacts/binance_1h_ar_mae_single_position_equity_2026-07-07.csv`
- 中选交易：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/artifacts/binance_1h_ar_mae_single_position_trades_2026-07-07.csv`

## 版本身份

- Full version：`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1`
- Short id：`BIN-1H-AR-MAE-V1`
- Family：`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble`
- Market：Binance USD-M Futures perpetual
- Symbols：`TRXUSDT`、`SOLUSDT`、`HYPEUSDT`、`ETHUSDT`、`BTCUSDT`、`BNBUSDT`
- Timeframe：`1h`
- Status：`dry-run / not live-ready`（实际启用与 live/dry-run 模式以 quant-runner 为准）

`V1` 是一个账户级组合策略：六个已登记的单资产 `1h adaptive-regime` 策略同时生成候选交易，但全账户同一时间只允许一笔持仓。当前只授权 dry-run，不授权 live。

## 复现环境与数据边界

- 仓库根目录：`/Users/ZK/OpenCode/quant-strategy-lab`
- Python 入口：使用 `uv run python ...`
- 组合脚本：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_mae_single_position_backtest.py`
- 成分 loader 脚本：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py`
- 组合窗口：`2024-08-17T06:00:00Z -> 2026-07-02T03:00:00Z`
- HYPE sleeve 起点：`2025-07-14T10:00:00Z`，此前 HYPE 不参与候选交易。
- 费用：`0.001` fee/fill
- 滑点：`0.0004` adverse slippage/fill，即 `4 bps`
- Funding：每个 sleeve 逐笔计入 Binance 历史 funding。
- 数据质量：各成分家族 loader 自带数据质量校验；任一成分数据质量漂移或主账指标漂移，组合脚本应直接失败。

若脱离本仓库独立实现，需要提供同一批数据：

- 每个 symbol 一份闭合 `1h` candle 序列，字段至少包括：`ts`（UTC，K 线开盘时间）、`open`、`high`、`low`、`close`、`volume`、`quote_volume`、`trade_count`、`vwap`、`is_closed`。
- 每个 symbol 一份 funding 序列，字段至少包括：`ts`（UTC funding 时间）、`funding_rate`。
- Candle 必须无缺口、无重复、全部闭合、OHLC 合法；不要用未闭合 K 或本地缓存补洞。
- `ts` 语义：本策略在 K 线 `ts` 对应的闭合时刻看到信号，`entry_delay_bars=1` 表示在下一根 K 的 `open` 成交。

## 成分版本清单

V1 固定使用以下成分版本，不随未来单资产版本升级自动变化：

| Asset | Symbol | 成分版本 | 机制 | 成分主账 current-full 校验 |
| --- | --- | --- | --- | --- |
| TRX | `TRXUSDT` | `TRX-1H-Adaptive-Regime-V3` | `macd_flip + stoch_reversal` | `5.686x / -17.17% DD / 92.47% win / 93 trades` |
| SOL | `SOLUSDT` | `SOL-1H-Adaptive-Regime-V2` | `donchian_break + vwap_revert` | `2.07x / -17.41% DD / 93.91% win / 115 trades` |
| HYPE | `HYPEUSDT` | `HYPE-1H-Adaptive-Regime-V4` | `di_cross + stoch_reversal` | `22.8128x / -19.11% DD / 81.08% win / 74 trades` |
| ETH | `ETHUSDT` | `ETH-1H-Adaptive-Regime-V3` | `bb_break + rsi_reversal` | `3.3084x / -15.70% DD / 95.65% win / 46 trades` |
| BTC | `BTCUSDT` | `BTC-1H-Adaptive-Regime-V4` | `keltner_break + cci_reversal` | `5.27x / -17.47% DD / 86.49% win / 74 trades` |
| BNB | `BNBUSDT` | `BNB-1H-Adaptive-Regime-V3` | `ema_pullback + wick_reject` | `2.94x / -18.24% DD / 88.33% win / 120 trades` |

## 账户级组合规则

候选交易生成：

1. 每个 asset sleeve 先独立运行其家族冻结策略，得到各自已合并后的单资产交易路径。
2. 只保留 `sleeve["start"] <= trade.entry_ts < sleeve["end"]` 的交易。
3. 组合候选池为六个 sleeve 的交易并集；本次候选交易数应为 `522`。

账户级单仓选择：

1. 将候选交易按以下 key 排序：

```python
(
    trade.entry_ts,
    -TIE_PRIORITY[asset],
    trade.exit_ts,
)
```

2. `TIE_PRIORITY` 固定如下：

```json
{
  "HYPE": 22.8128,
  "TRX": 5.686,
  "BTC": 5.27,
  "ETH": 3.3084,
  "BNB": 2.94,
  "SOL": 2.07
}
```

3. 从排序后的候选池顺序扫描：
   - 如果当前没有持仓，选中该交易。
   - 选中交易后，设置 `blocked_until = trade.exit_ts`。
   - 若后续候选交易 `entry_ts <= blocked_until`，直接跳过。
   - 只有当 `entry_ts > blocked_until` 时，才允许开下一笔。
4. 新信号不会抢仓，不会提前平当前持仓。
5. 中选交易占用全账户权益，并按原 sleeve 冻结的 `fixed_leverage` / `exposure` 执行。
6. 阻塞只移除候选交易，不改变中选交易的 entry、exit、价格、费用、滑点或 funding。

选择统计应为：

```json
{
  "candidate_trades": 522,
  "selected_trades": 371,
  "skipped_blocked": 151,
  "same_hour_entry_ties": 22,
  "per_asset_candidates": {
    "TRX": 93,
    "SOL": 115,
    "HYPE": 74,
    "ETH": 46,
    "BTC": 74,
    "BNB": 120
  },
  "per_asset_selected": {
    "TRX": 70,
    "SOL": 78,
    "HYPE": 54,
    "ETH": 33,
    "BTC": 51,
    "BNB": 85
  },
  "avg_exposure": 2.5954177897574127,
  "max_exposure": 5.0,
  "median_hold_hours": 7.0,
  "in_position_hours_pct": 0.3555718028392128
}
```

重要近似：本 V1 复现脚本没有在跨资产阻塞后重新逐 K 重演各 sleeve 的 cooldown / 内部状态机。它是“先生成每个 sleeve 的冻结交易路径，再做账户级阻塞筛选”。因此它是 diagnostic backtest，不是可直接实盘的联合状态机。

## 权益曲线构造

中选交易按全账户权益复利：

```python
equity = 1.0
for asset, trade in selected:
    # 持仓中用 bar close 做 mark-to-market
    mark_return = close_i / trade.entry_price - 1.0
    equity_mark = equity * (1.0 + trade.exposure * trade.side * mark_return)

    # 出场时用 sleeve 冻结交易的 equity_ret 对齐，equity_ret 已包含费用、滑点和 funding
    equity *= 1.0 + trade.equity_ret
```

窗口指标使用权益曲线重定基：

- `total_return = final_equity - 1`
- `annual_multiple = final_equity ** (365.25 / days)`
- `max_dd = min(equity / equity.cummax() - 1)`

逐笔胜率和 PF 使用中选交易的 `trade.equity_ret`。

## 成分子策略通用逻辑

六个成分 sleeve 都基于同一个 `1h` adaptive-regime 引擎家族。若同事不直接调用仓库脚本，而是让 AI 独立实现，需要同时实现以下通用逻辑和后文每个 leg 的 style 逻辑。

### 特征计算

对每个 symbol 的闭合 `1h` OHLCV 数据，按 UTC 时间升序计算：

- `ATR14`：true range 的 EWMA，`alpha=1/14`，`min_periods=14`。
- `ATR48`：true range 的 `48` 根 rolling mean。
- `atr_bps = ATR14 / close * 10000`。
- `EMA`：对 close 计算各参数需要的 EMA，例如 `8/21/34/55/89/144/233/377` 等，`adjust=False`，`min_periods=span`。
- `RSI(window)`：用于 ETH RSI reversal。
- `ROC(window)_bps = close.pct_change(window) * 10000`。
- `RVOL48 = volume / rolling_mean(volume, 48)`。
- `body_atr = (close - open) / ATR14`。
- `close_pos = (close - low) / (high - low)`。
- `upper_wick_atr = (high - max(open, close)) / ATR14`。
- `lower_wick_atr = (min(open, close) - low) / ATR14`。
- `MACD(fast, slow, signal)`：`EMA_fast - EMA_slow`；histogram = MACD line - signal EMA。
- Bollinger z-score：`bb_z(window) = (close - rolling_mean(close, window)) / rolling_std(close, window, ddof=0)`。
- Donchian：`don_high(window) = high.shift(1).rolling(window).max()`；`don_low(window) = low.shift(1).rolling(window).min()`。注意使用上一根以前的数据，避免当前 K 泄漏。
- Stochastic：`K = 100 * (close - rolling_low) / (rolling_high - rolling_low)`，`D = rolling_mean(K, 3)`。
- CCI：typical price = `(high + low + close) / 3`；`CCI = (typical - rolling_mean(typical, window)) / (0.015 * mean_abs_deviation)`。
- VWAP deviation：rolling VWAP = `sum(typical * volume, window) / sum(volume, window)`；`vwap_dev_atr = (close - rolling_vwap) / ATR14`。
- `ADX14 / +DI14 / -DI14`：标准 Wilder ADX/DI。
- 高周期 regime：使用已闭合 `4h`、`12h`、`1D` K 的 EMA spread；在 `htf_mode` 为 `h4/h12/d1` 时，要求 `side * spread >= 0`。
- Funding：对每根信号 K，只使用到信号 K 下一根 open 前已经知道的最近 funding rate；过滤项使用 `side * last_funding_rate * 10000`。

关键指标的精确定义：

- RSI：

```python
delta = close.diff()
gain = delta.clip(lower=0.0)
loss = -delta.clip(upper=0.0)
avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
rsi = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss.replace(0.0, np.nan))
```

- ADX / DI：

```python
previous_close = close.shift(1)
true_range = max(high - low, abs(high - previous_close), abs(low - previous_close))
up = high.diff()
down = -low.diff()
plus_dm = where((up > down) & (up > 0), up, 0.0)
minus_dm = where((down > up) & (down > 0), down, 0.0)
atr = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
pdi14 = 100 * ewm(plus_dm, alpha=1/14, min_periods=14) / atr
mdi14 = 100 * ewm(minus_dm, alpha=1/14, min_periods=14) / atr
dx = 100 * abs(pdi14 - mdi14) / (pdi14 + mdi14)
adx14 = dx.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
```

- 高周期 regime：
  - 对 `4h`、`12h`、`1D` 以 `label="left", closed="left"` 重采样 OHLCV。
  - 每个高周期 bar 在 `bar_start + rule_offset` 后才可见。
  - 用高周期 close 计算 `EMA12` 与 `EMA48`，`spread = EMA12 / EMA48 - 1`。
  - 对每根 `1h` K，以 `known_ts = ts + 1h` 做 backward asof merge，只能拿到已闭合高周期 spread。

```python
bars = one_hour_frame.resample(rule, label="left", closed="left").agg({
    "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
}).dropna()
known_ts = bars.index + pd.Timedelta(rule)
ema12 = bars["close"].ewm(span=12, adjust=False, min_periods=12).mean()
ema48 = bars["close"].ewm(span=48, adjust=False, min_periods=48).mean()
spread = ema12 / ema48 - 1.0
```

### 信号生成 style 逻辑

先生成原始方向信号 `signal`，取值 `+1` long、`-1` short、`0` 无信号，然后再套 side 和过滤器。

- `macd_flip`：`MACD histogram` 上穿 `0` 做多，下穿 `0` 做空。
- `donchian_break`：close 上穿 `don_high(window)` 做多，下穿 `don_low(window)` 做空。
- `vwap_revert`：`vwap_dev_atr(window)` 上穿 `-band_k` 做多，下穿 `+band_k` 做空；再由 `side_mode` 限制方向。SOL V2 的 VWAP leg 为 `short`，因此只保留做空信号。
- `di_cross`：`+DI14 - -DI14` 上穿 `0` 做多，下穿 `0` 做空。
- `stoch_reversal`：`K-D` 上穿 `0` 且 `K <= threshold_low` 做多；`K-D` 下穿 `0` 且 `K >= threshold_high` 做空。
- `bb_break`：`bb_z(window)` 上穿 `+band_k` 做多，下穿 `-band_k` 做空。
- `rsi_reversal`：`RSI(window)` 上穿 `threshold_low` 做多，下穿 `threshold_high` 做空。
- `keltner_break`：`mid = rolling_mean(close, window)`；上轨 `mid + band_k * ATR14`，下轨 `mid - band_k * ATR14`；close 上穿上轨做多，下穿下轨做空。
- `cci_reversal`：`CCI(window)` 上穿 `-threshold_high` 做多，下穿 `+threshold_high` 做空；BTC V4 CCI leg 固定 `side_mode=long`，因此只保留做多信号。
- `ema_pullback`：趋势 `sign(EMA_fast - EMA_slow)`；多头要求趋势向上、`low <= EMA_fast + pullback_atr * ATR14`、`close > EMA_fast`、`close > open`；空头相反，要求趋势向下、`high >= EMA_fast - pullback_atr * ATR14`、`close < EMA_fast`、`close < open`。连续同向相邻信号只保留第一根。
- `wick_reject`：下影线拒绝做多：`lower_wick_atr >= band_k` 且 `close_pos >= threshold_high`；上影线拒绝做空：`upper_wick_atr >= band_k` 且 `close_pos <= threshold_low`。

### 通用过滤器

对每个非零原始信号，按参数逐项过滤：

1. `side_mode`：`long` 只保留 `+1`；`short` 只保留 `-1`；`both` 保留双向。
2. ADX：`min_adx <= ADX14 <= max_adx`。
3. RVOL：`RVOL48 >= min_rvol`。
4. ATR：`min_atr_bps <= atr_bps <= max_atr_bps`。
5. 方向动量：`side * ROC(roc_window)_bps >= min_dir_roc_bps`。
6. 长 EMA 距离：`abs(close / EMA(ema_htf) - 1) * 10000 <= max_dist_ema_bps`。
7. 高周期方向：若 `htf_mode != "none"`，要求 `side * htf_spread >= 0`。
8. MACD 转向：若 `require_macd_turn=true`，要求 `side * delta(MACD histogram) > 0`。
9. K 线实体方向：若 `require_body_dir=true`，要求 `side * body_atr > 0`。
10. Funding 拥挤过滤：`side * last_funding_rate * 10000 <= max_aligned_funding_bps`。

所有用到的特征必须为 finite；任一必要值为 NaN/inf，则该信号过滤掉。

### 单个 sleeve 内部交易执行

成分 sleeve 内部每个 leg 独立产生交易，再用该家族的 merge 规则合并成单资产交易路径。

每笔候选交易执行规则：

1. `entry_i = signal_i + entry_delay_bars`；即闭合信号 K 后，下一根或指定延迟后的 open 成交。
2. 如果 `entry_i >= len(frame)` 或 `entry_i <= blocked_until`，跳过。
3. 入场价：`entry_price = open[entry_i] * (1 + side * slippage)`。
4. 初始止损：`initial_stop = entry_price - side * sl_atr * ATR14(signal_i)`。
5. 若 `exit_kind == "fixed"`，止盈价：`target = entry_price + side * tp_atr * ATR14(signal_i)`。
6. 若 `exit_kind == "trailing"`，没有固定 target，只使用初始 stop + trailing stop。
7. 最长持仓：`timeout_i = entry_i + max_hold_bars`，到期按该 bar open 出场。
8. 每根持仓 K 内出场检查顺序：
   - 若 open 已穿 stop，按 open 出场，原因 `stop_gap_open`。
   - 若 fixed target 存在且 open 已穿 target，按 target 出场，原因 `target_gap_or_open`。
   - 若同一根 K 同时触及 stop 和 target，按 stop-first，原因 `both_hit_stop_first`。
   - 若只触及 stop，按 stop 出场，原因 `stop_market`。
   - 若只触及 target，按 target 出场，原因 `take_profit`。
   - 若 trailing，更新有利方向极值；当浮盈达到 `trail_activation_atr * ATR14(signal_i)` 后，用 `trail_atr * ATR14(signal_i)` 更新 trailing stop。
9. 出场价：`exit_price = raw_exit * (1 - side * slippage)`。
10. 价格收益：`price_ret = side * (exit_price / entry_price - 1)`。
11. 手续费：`fee_ret = fee_per_fill * (1 + exit_price / entry_price)`。
12. Funding：`funding_ret = -side * sum(funding_rate in [entry_ts, exit_ts))`。
13. `net_ret_1x = price_ret - fee_ret + funding_ret`。
14. 若 `sizing_kind == "fixed"`，`exposure = fixed_leverage`；V1 所有中选交易均来自 fixed sizing。
15. `equity_ret = exposure * net_ret_1x`。
16. 该 leg 内部成交后设置 `blocked_until = exit_i + cooldown_bars`。

### 单资产内部 ensemble 合并

每个 asset sleeve 内部先把两个 leg 的交易集合合并成单资产交易路径。通用合并规则：

```python
tagged = [(trade, left_priority) for trade in left] + [(trade, right_priority) for trade in right]
tagged.sort(key=lambda item: (item[0].entry_i, -item[1], item[0].exit_i))
selected = []
blocked_until = -1
for trade, priority in tagged:
    if trade.entry_i <= blocked_until:
        continue
    selected.append(trade)
    blocked_until = trade.exit_i
```

也就是说：单个 asset 内同一时间最多一笔；冲突时先按入场 K，入场相同时按 leg priority，已持仓期间其他 leg 信号跳过，不抢仓、不提前平仓。

## 各成分子策略逻辑说明

### TRX V3：MACD flip + Stochastic reversal

- MACD leg 用 `MACD(34,89,13)` histogram 零轴翻转作为趋势/动量切换信号，双向交易；过滤器要求 `ADX 20-24`、`ATR <= 150 bps`、方向 ROC6 不低于 `-100 bps`、价格不限制 EMA 距离（`10000 bps`）、且方向符合闭合 `12h` regime；固定止盈 `2 ATR`、止损 `5 ATR`、最长 `120h`、入场延迟 `1h`、暴露 `5x`。
- Stoch leg 用 `Stoch(21)` 的 `K-D` 反转交叉：低位上穿做多，高位下穿做空；双向交易；过滤器要求 `ADX <= 24`、`RVOL >= 1`、方向 ROC3 不低于 `-300 bps`、K 线实体同向、价格距 EMA233 不超过 `1500 bps`、funding 顺向拥挤不超过 `4 bps`（后两项继承自 TRX V1 基线）；使用 trailing exit，初始止损 `6 ATR`，浮盈 `3 ATR` 后用 `2 ATR` trailing，最长 `120h`，入场延迟 `2h`，暴露 `3.5x`。
- TRX sleeve 内部用 V3 clean wrapper 复现；优先级由成分脚本按 prefit leg score 计算。

### SOL V2：Donchian break + VWAP revert

- Donchian leg 是趋势突破：close 上穿上一段 `24h` Donchian high 做多，下穿 Donchian low 做空；过滤器要求 `ADX >= 36`、`RVOL >= 1`、`ATR >= 100 bps`、方向 ROC24 至少 `+100 bps`、funding 顺向拥挤不超过 `2 bps`；固定 TP `0.75 ATR`、SL `4 ATR`、最长 `120h`、暴露 `3x`。
- VWAP leg 是均值回归，但本版本只做空：`vwap_dev_atr(48)` 下穿 `+1.25 ATR` 触发做空候选；过滤器要求 `ATR >= 125 bps`、价格距 EMA89 不超过 `1000 bps`、方向符合闭合 `12h` regime、K 线实体同向、funding 顺向拥挤不超过 `1 bps`；固定 TP `0.75 ATR`、SL `3 ATR`、最长 `18h`、cooldown `3h`、暴露 `1.5x`。
- SOL sleeve 内部 leg priority 由高胜率搜索覆写后的 `prefit_score(train, validation, prefit)` 计算。

### HYPE V4：DI-cross + Stochastic reversal

- DI leg 是趋势方向切换：`+DI14 - -DI14` 上穿零做多，下穿零做空；过滤器要求 `ADX >= 10`、`RVOL >= 2`、`ATR <= 250 bps`、方向符合闭合 `12h` regime；不要求实体同向；固定 TP `1.5 ATR`、SL `4.5 ATR`、最长 `18h`、暴露 `3x`。
- Stoch leg 是高波动反转：`Stoch(21)` 低位上穿做多、高位下穿做空，阈值 `25/55`；过滤器要求 `RVOL >= 1`、`200 <= ATR <= 500 bps`，并要求 `MACD(8,55,5)` histogram 朝交易方向转向；trailing exit，安全初始止损 `4 ATR`，浮盈 `1 ATR` 后 `1 ATR` trailing，最长 `8h`，cooldown `36h`，暴露 `2x`。
- HYPE sleeve 内部冲突固定 DI 优先：`DI priority=1.0`，`Stoch priority=0.0`。

### ETH V3：BB break + RSI reversal

- BB break leg 是布林突破，V1 冻结路径只做多（`side_mode=long`，继承自 ETH V1 基线）：`bb_z(72)` 上穿 `+2.5` 做多；过滤器要求 `ADX >= 16`、`RVOL >= 3.5`、`75 <= ATR <= 250 bps`、方向 ROC24 至少 `+200 bps`、价格距 EMA55 不超过 `750 bps`、funding 顺向拥挤不超过 `8 bps`；固定 TP `3 ATR`、SL `5 ATR`、最长 `72h`、暴露 `1.5x`。
- RSI reversal leg 是极端 RSI 恢复/反转：`RSI7` 上穿 `5` 做多，下穿 `75` 做空；过滤器要求 `20 <= ADX <= 45`、`125 <= ATR <= 600 bps`、方向 ROC6 不低于 `-300 bps`、价格距 EMA233 不超过 `750 bps`、K 线实体同向（`require_body_dir=true`）、funding 顺向拥挤不超过 `2 bps`；固定 TP `2 ATR`、SL `3 ATR`、最长 `48h`、cooldown `24h`、暴露 `2.5x`。
- ETH sleeve 内部 priority 由成分 `simulate_clean` 的 prefit leg score 计算。

### BTC V4：Keltner break + CCI reversal

- Keltner leg 是强趋势突破：close 上穿/下穿 `rolling_mean(close,20) ± 2 * ATR14` 触发多/空；过滤器要求 `ADX >= 40`、`RVOL >= 1.25`、方向符合闭合 `4h` regime；V4 将 ATR 上限、方向 ROC、funding、最长持仓、cooldown 等字段中和固定；固定 TP `1.5 ATR`、SL `5 ATR`、暴露 `2.4x`。
- CCI leg 是 CCI 均值回归，但固定只做多：`CCI20` 上穿 `-125` 做多；过滤器要求 `ADX <= 40`、`RVOL >= 1.25`、`ATR >= 75 bps`、价格距 EMA377 不超过 `750 bps`；固定 TP `5.5 ATR`、SL `1.5 ATR`、最长 `72h`、暴露 `3.5x`。
- BTC V4 是 V3 的最小等价 clean surface；多个不生效字段以中和值固定，不改变交易路径。

### BNB V3：EMA pullback + Wick reject

- EMA pullback leg 是趋势回踩恢复：趋势由 `EMA55 - EMA144` 决定；多头要求趋势向上、低点回踩至 `EMA55 - 0.25 ATR` 附近并收回、收盘站上 EMA55 且阳线；空头相反；过滤器要求 `RVOL >= 1`、`ATR >= 50 bps`、价格距 EMA377 不超过 `300 bps`；使用 trailing exit，初始 SL `5 ATR`，浮盈 `2 ATR` 后 `1.5 ATR` trailing，最长 `240h`、cooldown `12h`、暴露 `2.5x`。
- Wick reject leg 是影线拒绝：下影线长度至少 `0.5 ATR` 且收盘位置 `>=0.75` 做多；上影线长度至少 `0.5 ATR` 且收盘位置 `<=0.40` 做空；过滤器要求 `ADX >= 28`、`RVOL >= 2`、方向符合闭合 `12h` regime；固定 TP `1 ATR`、SL `5 ATR`、最长 `48h`、cooldown `24h`、暴露 `1x`。
- BNB sleeve 内部 priority 固定为 EMA pullback `2.445774012147314`、wick reject `1.6307399812929821`。

## 成分参数总表

以下参数是 V1 复现所需的冻结参数。它们与上文“成分子策略通用逻辑”共同构成完整实现规格；仓库路径只作为本仓库内出处备注，不应作为 standalone 复现依赖。

### 固定字段补全规则

有些成分来自 clean surface，参数 JSON 只列出 active 字段；独立实现时必须按下表补齐固定字段：

| Asset / leg | style | side_mode | exit_kind | entry_delay_bars | sizing_kind | 固定说明 |
| --- | --- | --- | --- | ---: | --- | --- |
| TRX MACD | `macd_flip` | `both` | `fixed` | `1` | `fixed` | `min_atr_bps=0`、`max_aligned_funding_bps=10000`、`require_body_dir=false` |
| TRX Stoch | `stoch_reversal` | 参数内 `both` | `trailing` | 参数内 `2` | `fixed` | `min_adx=0`、`min_atr_bps=0`、`max_atr_bps=10000`、`max_dist_ema_bps=1500`、`max_aligned_funding_bps=4.0`、`htf_mode=none`、`require_macd_turn=false`、`tp_atr` 不生效 |
| SOL Donchian | `donchian_break` | `both` | `fixed` | `1` | `fixed` | 完整 engine config 已在 JSON 中列出 |
| SOL VWAP | `vwap_revert` | `short` | `fixed` | `1` | `fixed` | 完整 engine config 已在 JSON 中列出 |
| HYPE DI | `di_cross` | `both` | `fixed` | `1` | `fixed` | 完整 engine config 已在 JSON 中列出 |
| HYPE Stoch | `stoch_reversal` | `both` | `trailing` | `1` | `fixed` | 完整 engine config 已在 JSON 中列出 |
| ETH BB | `bb_break` | `long` | `fixed` | `1` | `fixed` | `min_atr_bps=75`、`max_atr_bps=250`、`htf_mode=none`、`require_macd_turn=false`、`require_body_dir=false` |
| ETH RSI | `rsi_reversal` | `both` | `fixed` | `1` | `fixed` | `min_rvol=0`、`max_atr_bps=600`、`max_aligned_funding_bps=2.0`、`htf_mode=none`、`require_macd_turn=false`、`require_body_dir=true` |
| BTC Keltner | `keltner_break` | `both` | `fixed` | `1` | `fixed` | `ema_fast=55`、`ema_slow=144`、`ema_htf=55`；完整有效字段见 JSON |
| BTC CCI | `cci_reversal` | `long` | `fixed` | `1` | `fixed` | `ema_fast=89`、`ema_slow=233`；完整有效字段见 JSON |
| BNB EMA pullback | `ema_pullback` | `both` | `trailing` | `1` | `fixed` | 完整 engine config 已在 JSON 中列出 |
| BNB Wick reject | `wick_reject` | `both` | `fixed` | `1` | `fixed` | 完整 engine config 已在 JSON 中列出 |

### TRX-1H-Adaptive-Regime-V3

仓库内出处备注（非 standalone 依赖）：

- Loader：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py::load_trx`
- 成分脚本：`research/trx/1h-adaptive-regime/scripts/trx_1h_ar_v3_clean.py`
- 成分版本：`TRX-1H-Adaptive-Regime-V3`

MACD flip leg：

```json
{
  "ema_htf": 89,
  "roc_window": 6,
  "macd_fast": 34,
  "macd_slow": 89,
  "macd_signal": 13,
  "min_adx": 20.0,
  "max_adx": 24.0,
  "min_rvol": 0.0,
  "max_atr_bps": 150.0,
  "min_dir_roc_bps": -100.0,
  "max_dist_ema_bps": 10000.0,
  "htf_mode": "h12",
  "require_macd_turn": false,
  "tp_atr": 2.0,
  "sl_atr": 5.0,
  "max_hold_bars": 120,
  "cooldown_bars": 3,
  "entry_delay_bars": 1,
  "fixed_leverage": 5.0
}
```

Stochastic reversal leg：

```json
{
  "side_mode": "both",
  "ema_htf": 233,
  "indicator_window": 21,
  "threshold_low": 25.0,
  "threshold_high": 90.0,
  "roc_window": 3,
  "max_adx": 24.0,
  "min_rvol": 1.0,
  "min_dir_roc_bps": -300.0,
  "require_body_dir": true,
  "sl_atr": 6.0,
  "trail_activation_atr": 3.0,
  "trail_atr": 2.0,
  "max_hold_bars": 120,
  "cooldown_bars": 6,
  "entry_delay_bars": 2,
  "fixed_leverage": 3.5
}
```

### SOL-1H-Adaptive-Regime-V2

仓库内出处备注（非 standalone 依赖）：

- Loader：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py::load_sol`
- 成分版本：`SOL-1H-Adaptive-Regime-V2`
- Ensemble 优先级：使用高胜率搜索覆写后的 `engine.prefit_score(train, validation, prefit)` 动态计算。

Donchian break leg：

```json
{
  "name": "SOL_1H_AR_HW_R132002",
  "style": "donchian_break",
  "side_mode": "both",
  "ema_fast": 144,
  "ema_slow": 233,
  "ema_htf": 377,
  "indicator_window": 24,
  "threshold_low": 25.0,
  "threshold_high": 75.0,
  "band_k": 1.5,
  "pullback_atr": 0.25,
  "roc_window": 24,
  "roc_threshold_bps": 50.0,
  "macd_fast": 34,
  "macd_slow": 89,
  "macd_signal": 13,
  "min_adx": 36.0,
  "max_adx": 100.0,
  "min_rvol": 1.0,
  "min_atr_bps": 100.0,
  "max_atr_bps": 10000.0,
  "min_dir_roc_bps": 100.0,
  "max_dist_ema_bps": 750.0,
  "htf_mode": "none",
  "require_macd_turn": true,
  "require_body_dir": false,
  "max_aligned_funding_bps": 2.0,
  "exit_kind": "fixed",
  "tp_atr": 0.75,
  "sl_atr": 4.0,
  "trail_activation_atr": 0.75,
  "trail_atr": 0.5,
  "max_hold_bars": 120,
  "cooldown_bars": 0,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 3.0,
  "risk_fraction": 0.01,
  "max_leverage": 2.5
}
```

VWAP revert leg：

```json
{
  "name": "SOL_1H_AR_HW_R243705",
  "style": "vwap_revert",
  "side_mode": "short",
  "ema_fast": 34,
  "ema_slow": 55,
  "ema_htf": 89,
  "indicator_window": 48,
  "threshold_low": 30.0,
  "threshold_high": 70.0,
  "band_k": 1.25,
  "pullback_atr": 0.25,
  "roc_window": 72,
  "roc_threshold_bps": 50.0,
  "macd_fast": 8,
  "macd_slow": 21,
  "macd_signal": 5,
  "min_adx": 0.0,
  "max_adx": 100.0,
  "min_rvol": 0.0,
  "min_atr_bps": 125.0,
  "max_atr_bps": 10000.0,
  "min_dir_roc_bps": -10000.0,
  "max_dist_ema_bps": 1000.0,
  "htf_mode": "h12",
  "require_macd_turn": false,
  "require_body_dir": true,
  "max_aligned_funding_bps": 1.0,
  "exit_kind": "fixed",
  "tp_atr": 0.75,
  "sl_atr": 3.0,
  "trail_activation_atr": 1.0,
  "trail_atr": 1.25,
  "max_hold_bars": 18,
  "cooldown_bars": 3,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 1.5,
  "risk_fraction": 0.01,
  "max_leverage": 1.5
}
```

### HYPE-1H-Adaptive-Regime-V4

仓库内出处备注（非 standalone 依赖）：

- Loader：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py::load_hype`
- 成分版本：`HYPE-1H-Adaptive-Regime-V4`
- 单资产内部 merge：`DI` 优先级 `1.0`，`Stoch` 优先级 `0.0`；同一时段冲突时 DI 优先。

DI engine config：

```json
{
  "name": "HYPE_1H_AR_V4_DI",
  "style": "di_cross",
  "side_mode": "both",
  "ema_fast": 8,
  "ema_slow": 55,
  "ema_htf": 89,
  "indicator_window": 20,
  "threshold_low": 20.0,
  "threshold_high": 80.0,
  "band_k": 0.5,
  "pullback_atr": 0.0,
  "roc_window": 24,
  "roc_threshold_bps": 25.0,
  "macd_fast": 8,
  "macd_slow": 21,
  "macd_signal": 5,
  "min_adx": 10.0,
  "max_adx": 100.0,
  "min_rvol": 2.0,
  "min_atr_bps": 0.0,
  "max_atr_bps": 250.0,
  "min_dir_roc_bps": -10000.0,
  "max_dist_ema_bps": 10000.0,
  "htf_mode": "h12",
  "require_macd_turn": false,
  "require_body_dir": false,
  "max_aligned_funding_bps": 10000.0,
  "exit_kind": "fixed",
  "tp_atr": 1.5,
  "sl_atr": 4.5,
  "trail_activation_atr": 1.0,
  "trail_atr": 1.0,
  "max_hold_bars": 18,
  "cooldown_bars": 0,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 3.0,
  "risk_fraction": 0.01,
  "max_leverage": 1.0
}
```

Stoch engine config：

```json
{
  "name": "HYPE_1H_AR_V4_STOCH",
  "style": "stoch_reversal",
  "side_mode": "both",
  "ema_fast": 8,
  "ema_slow": 55,
  "ema_htf": 55,
  "indicator_window": 21,
  "threshold_low": 25.0,
  "threshold_high": 55.0,
  "band_k": 0.5,
  "pullback_atr": 0.0,
  "roc_window": 12,
  "roc_threshold_bps": 25.0,
  "macd_fast": 8,
  "macd_slow": 55,
  "macd_signal": 5,
  "min_adx": 0.0,
  "max_adx": 100.0,
  "min_rvol": 1.0,
  "min_atr_bps": 200.0,
  "max_atr_bps": 500.0,
  "min_dir_roc_bps": -10000.0,
  "max_dist_ema_bps": 10000.0,
  "htf_mode": "none",
  "require_macd_turn": true,
  "require_body_dir": false,
  "max_aligned_funding_bps": 10000.0,
  "exit_kind": "trailing",
  "tp_atr": 1.0,
  "sl_atr": 4.0,
  "trail_activation_atr": 1.0,
  "trail_atr": 1.0,
  "max_hold_bars": 8,
  "cooldown_bars": 36,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 2.0,
  "risk_fraction": 0.01,
  "max_leverage": 1.0
}
```

### ETH-1H-Adaptive-Regime-V3

仓库内出处备注（非 standalone 依赖）：

- Loader：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py::load_eth`
- 成分脚本：`research/eth/1h-adaptive-regime/scripts/eth_1h_ar_v2_1_clean.py`
- 成分版本：`ETH-1H-Adaptive-Regime-V3`

BB break clean config（含硬编码字段）：

```json
{
  "ema_htf": 55,
  "indicator_window": 72,
  "band_k": 2.5,
  "roc_window": 24,
  "min_adx": 16.0,
  "min_rvol": 3.5,
  "min_atr_bps": 75.0,
  "min_dir_roc_bps": 200.0,
  "max_dist_ema_bps": 750.0,
  "max_aligned_funding_bps": 8.0,
  "tp_atr": 3.0,
  "sl_atr": 5.0,
  "max_hold_bars": 72,
  "fixed_leverage": 1.5
}
```

RSI reversal clean config：

```json
{
  "ema_htf": 233,
  "indicator_window": 7,
  "threshold_low": 5.0,
  "threshold_high": 75.0,
  "roc_window": 6,
  "min_adx": 20.0,
  "max_adx": 45.0,
  "min_atr_bps": 125.0,
  "min_dir_roc_bps": -300.0,
  "max_dist_ema_bps": 750.0,
  "tp_atr": 2.0,
  "sl_atr": 3.0,
  "max_hold_bars": 48,
  "cooldown_bars": 24,
  "fixed_leverage": 2.5
}
```

### BTC-1H-Adaptive-Regime-V4

仓库内出处备注（非 standalone 依赖）：

- Loader：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py::load_btc`
- 成分脚本：`research/btc/1h-adaptive-regime/scripts/btc_1h_ar_v4.py`
- 成分版本：`BTC-1H-Adaptive-Regime-V4`

Keltner engine config（含中和值固定字段）：

```json
{
  "indicator_window": 20,
  "band_k": 2.0,
  "roc_window": 24,
  "min_adx": 40.0,
  "min_rvol": 1.25,
  "max_atr_bps": 10000.0,
  "min_dir_roc_bps": -10000.0,
  "htf_mode": "h4",
  "max_aligned_funding_bps": 10000.0,
  "tp_atr": 1.5,
  "sl_atr": 5.0,
  "max_hold_bars": 100000,
  "cooldown_bars": 0,
  "fixed_leverage": 2.4
}
```

CCI engine config（含中和值固定字段）：

```json
{
  "ema_htf": 377,
  "indicator_window": 20,
  "threshold_high": 125.0,
  "max_adx": 40.0,
  "min_rvol": 1.25,
  "min_atr_bps": 75.0,
  "max_atr_bps": 10000.0,
  "max_dist_ema_bps": 750.0,
  "tp_atr": 5.5,
  "sl_atr": 1.5,
  "max_hold_bars": 72,
  "cooldown_bars": 0,
  "fixed_leverage": 3.5
}
```

### BNB-1H-Adaptive-Regime-V3

仓库内出处备注（非 standalone 依赖）：

- Loader：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py::load_bnb`
- 成分参数源：`research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v2_micro_tune_2026-07-07.json`
- 成分版本：`BNB-1H-Adaptive-Regime-V3`
- 单资产内部 merge priorities：`[2.445774012147314, 1.6307399812929821]`

EMA pullback leg：

```json
{
  "name": "BNB_1H_AR_V2_EMA_PULLBACK_T00405",
  "style": "ema_pullback",
  "side_mode": "both",
  "ema_fast": 55,
  "ema_slow": 144,
  "ema_htf": 377,
  "indicator_window": 14,
  "threshold_low": 0.0,
  "threshold_high": 100.0,
  "band_k": 0.0,
  "pullback_atr": -0.25,
  "roc_window": 12,
  "roc_threshold_bps": 0.0,
  "macd_fast": 12,
  "macd_slow": 26,
  "macd_signal": 9,
  "min_adx": 0.0,
  "max_adx": 100.0,
  "min_rvol": 1.0,
  "min_atr_bps": 50.0,
  "max_atr_bps": 10000.0,
  "min_dir_roc_bps": -10000.0,
  "max_dist_ema_bps": 300.0,
  "htf_mode": "none",
  "require_macd_turn": false,
  "require_body_dir": false,
  "max_aligned_funding_bps": 10000.0,
  "exit_kind": "trailing",
  "tp_atr": 3.0,
  "sl_atr": 5.0,
  "trail_activation_atr": 2.0,
  "trail_atr": 1.5,
  "max_hold_bars": 240,
  "cooldown_bars": 12,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 2.5,
  "risk_fraction": 0.01,
  "max_leverage": 1.0
}
```

Wick reject leg：

```json
{
  "name": "BNB_1H_AR_V2_WICK_REJECT_T01080",
  "style": "wick_reject",
  "side_mode": "both",
  "ema_fast": 21,
  "ema_slow": 144,
  "ema_htf": 55,
  "indicator_window": 14,
  "threshold_low": 0.4,
  "threshold_high": 0.75,
  "band_k": 0.5,
  "pullback_atr": 0.0,
  "roc_window": 12,
  "roc_threshold_bps": 0.0,
  "macd_fast": 12,
  "macd_slow": 26,
  "macd_signal": 9,
  "min_adx": 28.0,
  "max_adx": 100.0,
  "min_rvol": 2.0,
  "min_atr_bps": 0.0,
  "max_atr_bps": 10000.0,
  "min_dir_roc_bps": -10000.0,
  "max_dist_ema_bps": 100000.0,
  "htf_mode": "h12",
  "require_macd_turn": false,
  "require_body_dir": false,
  "max_aligned_funding_bps": 10000.0,
  "exit_kind": "fixed",
  "tp_atr": 1.0,
  "sl_atr": 5.0,
  "trail_activation_atr": 100000.0,
  "trail_atr": 100000.0,
  "max_hold_bars": 48,
  "cooldown_bars": 24,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 1.0,
  "risk_fraction": 0.01,
  "max_leverage": 1.0
}
```

## 期望复现结果

完整复现后，`artifacts/binance_1h_ar_mae_single_position_2026-07-07.json` 中关键字段应匹配：

```json
{
  "selection": {
    "candidate_trades": 522,
    "selected_trades": 371,
    "skipped_blocked": 151,
    "same_hour_entry_ties": 22
  },
  "portfolio_windows": {
    "full": {
      "total_return": 39997.48077136025,
      "annual_multiple": 287.0119873095173,
      "max_dd": -0.21432509786924225,
      "trades": 371,
      "win_rate": 0.9029649595687331,
      "profit_factor": 6.86244478871941
    },
    "reused_holdout": {
      "total_return": 0.6531227010452689,
      "annual_multiple": 7.668775716212575,
      "max_dd": -0.1978707715933925,
      "trades": 42,
      "win_rate": 0.7857142857142857,
      "profit_factor": 2.3099514371238765
    },
    "last_7d": {
      "total_return": 0.004589559404015953,
      "max_dd": -0.15919886664826977,
      "trades": 3
    },
    "last_1m": {
      "total_return": 0.5818212790113322,
      "max_dd": -0.15919886664826965,
      "trades": 19
    },
    "last_3m": {
      "total_return": 0.6601388609659042,
      "max_dd": -0.1978707715933926,
      "trades": 42
    },
    "last_6m": {
      "total_return": 10.893542680444234,
      "max_dd": -0.21432509786924214,
      "trades": 101
    },
    "last_1y": {
      "total_return": 133.15394114272962,
      "max_dd": -0.21432509786924225,
      "trades": 212
    }
  }
}
```

## 结论与验证注意事项

验证有效性时必须同时验证收益和失败边界：

1. V1 能复现高全期收益，但 full、`last_6m`、`last_1y` 最大回撤均为 `-21.43%`，穿破 `<20%` 硬门槛。
2. reused holdout 为正，但最大回撤 `-19.79%` 几乎贴线，且不是 fresh OOS。
3. V1 是冻结 sleeve 交易路径上的账户级阻塞筛选，不是完整联合状态机；promotion 前必须逐 K 重演跨资产阻塞后的 cooldown / 状态机。
4. 成分策略的历史研究失败与 live-readiness 缺口不会因组合或 dry-run 授权而消失。

因此，正确复现的当前判断应是：`dry-run / not live-ready`；历史回撤和执行缺口继续阻塞 live。
