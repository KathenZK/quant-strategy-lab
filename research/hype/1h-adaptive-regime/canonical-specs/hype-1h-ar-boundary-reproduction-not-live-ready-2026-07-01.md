# HYPE-1H-Adaptive-Regime 边界组合复现规格（不可实盘）

> 版本路由：本边界已于 2026-07-02 正式登记为 `HYPE-1H-Adaptive-Regime-V1`；当前数据与指标以 `hype-1h-ar-v1-baseline-spec.md` 为准。本文件保留 2026-07-01 的原始搜索冻结证据。

## 身份与状态

- Full family name：`HYPE-1H-Adaptive-Regime`。
- Family id：`HYPE-1H-AR`。
- Diagnostic id：`ENS__HYPE_1H_AR_N026857__HYPE_1H_AR_N090440`。
- 状态：`NO-GO / diagnostic boundary only / not live-ready / not promoted`。

这份文档用于逐字段复现本轮最强边界组合，不是 live、paper-live、dry-run、candidate 或 handoff 规格。精确 full 年化权益倍率为 `9.73334x`，没有达到 `10.0x`；locked holdout 仅 `5.21508x`，且回撤已经到 `-19.6426%`。

## 1. 数据

- Exchange：Binance。
- Market：USD-M Futures perpetual。
- Symbol：`HYPEUSDT`（标准 symbol：`HYPE/USDT:USDT`）。
- Timeframe：`1h`。
- 闭合 K 范围：`2025-05-30 10:00:00 UTC` 至 `2026-07-01 07:00:00 UTC`。
- 行数：`9,526`；missing `0`；duplicate `0`；raw/normalized mismatch `0`。
- 资金费：`2,380` 条，逐笔持仓区间计入。
- 抓取与审计：`scripts/fetch_hype_binance_1h.py`。
- normalized 数据湖：`data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1h/date=*/symbol=hype_usdt_usdt.parquet`。

只有已闭合 K 可以进入指标。数据缺口、重复、未闭合 K、关键字段空值、OHLC 违规或来源未知时必须 fail closed。

## 2. 时间切分

- 指标 warmup 后研究起点：`2025-07-14 10:00:00 UTC`。
- Train：起点至 `2026-01-23 23:18:00 UTC`。
- Validation：上述时间至 `2026-04-13 03:39:00 UTC`。
- Locked holdout：上述时间至 `2026-07-01 08:00:00 UTC`。

第一轮随机搜索、第二轮 Pareto 邻域搜索和 ensemble 选择只使用 train + validation；holdout 只在 finalists 冻结后解锁。不得使用本次 holdout 继续调参后再把它称为 OOS。

## 3. 公共指标定义

- `TR = max(high-low, abs(high-prev_close), abs(low-prev_close))`。
- `ATR14`：对 `TR` 使用 Wilder EWMA，`alpha=1/14`，`adjust=False`。
- `ADX14/+DI14/-DI14`：Wilder DM/TR 口径，`alpha=1/14`。
- `RVOL48 = volume / SMA(volume, 48)`。
- `ROCn_bps = (close / close.shift(n) - 1) * 10000`。
- `body_atr = (close-open) / ATR14`。
- `Stoch K(21) = 100 * (close-LL21)/(HH21-LL21)`；`D = SMA(K, 3)`。
- `MACD(8,21,5) hist = EMA8(close)-EMA21(close)-EMA5(MACD line)`。
- `12h spread = EMA12(12h close)/EMA48(12h close)-1`；只对完整闭合的 `12h` K 计算，按其可用时间向 `1h` K backward 对齐。
- 信号 K 的可用时间是该 K 结束时刻；入场使用下一根 `1h` K 的 open。

## 4. 腿 A：DI-cross

配置 id：`HYPE_1H_AR_N026857`。

### 4.1 原始信号

- `spread = +DI14 - -DI14`。
- `spread` 从 `<=0` 上穿 `>0`：`direction=+1`。
- `spread` 从 `>=0` 下穿 `<0`：`direction=-1`。

### 4.2 信号 K 过滤

方向变量记为 `d`（long `+1`，short `-1`），所有条件同时成立：

- `12 <= ADX14 <= 36`。
- `RVOL48 >= 2.0`。
- `0 <= ATR14/close*10000 <= 250`。
- `d * ROC24_bps >= -200`。
- `abs(close/EMA89-1)*10000 <= 750`。
- `d * 12h_spread >= 0`。
- `d * body_atr > 0`。
- `d * last_known_funding_rate * 10000 <= 8`。

### 4.3 入场与退出

- 信号 K 闭合后的下一根 `1h` open 市价入场。
- 入场不利滑点：`4 bps`。
- 入场完成后立刻挂保护：
  - `TP = entry + d * 1.5 * signal_ATR14`。
  - `SL = entry - d * 4.0 * signal_ATR14`。
- 最长持仓 `18` 根 `1h` K；超时在第 `18` 根后的 open 市价退出。
- 固定权益名义暴露 `3.0x`。
- 无额外 cooldown。

## 5. 腿 B：Stoch-reversal

配置 id：`HYPE_1H_AR_N090440`。

### 5.1 原始信号

- `cross = StochK21 - StochD21`。
- `cross` 从 `<=0` 上穿 `>0` 且 `K<=25`：`direction=+1`。
- `cross` 从 `>=0` 下穿 `<0` 且 `K>=60`：`direction=-1`。

### 5.2 信号 K 过滤

- `ADX14 >= 12`。
- `RVOL48 >= 1.0`。
- `200 <= ATR14/close*10000 <= 400`。
- `abs(close/EMA55-1)*10000 <= 2500`。
- `d * (MACD_hist_t - MACD_hist_t-1) > 0`，MACD 为 `(8,21,5)`。
- 本腿没有有效方向收益、HTF 和 funding 限制。

### 5.3 入场、保护止损与 trailing

- 下一根 `1h` open 市价入场，入场不利滑点 `4 bps`。
- 初始 stop 立即生效：`SL = entry - d * 4.0 * signal_ATR14`。
- activation：持仓后的最佳价格相对 entry 的有利移动达到 `1.0 * signal_ATR14`。
- activation 后，只有在一根持仓 K 完全闭合后才计算新 stop：
  - long：`new_stop = max(old_stop, best_closed_high - 1.0*signal_ATR14)`；
  - short：`new_stop = min(old_stop, best_closed_low + 1.0*signal_ATR14)`。
- 新 stop 从下一根 K 开始生效，不能用同一根 K 的 high 更新后再用同一根 K 的 low 触发。
- 最长持仓 `8` 根 `1h` K；之后 open 退出。
- 固定权益名义暴露 `2.0x`。
- 退出后 cooldown `24` 根 `1h` K。

## 6. 组合与冲突

- 每条腿先独立生成可执行交易流。
- 同一时间只允许一个仓位，不加仓、不反手叠加。
- 所有候选按 `entry_i` 排序；重叠时保留先入场交易。
- 同一 `entry_i` 冲突时按冻结 prefit score：
  - DI-cross：`3.0946604699883618`；
  - Stoch-reversal：`3.086767275227531`；
  - 因而 DI-cross 优先。
- 被现有持仓覆盖的另一条腿信号直接丢弃，不延后补入。

## 7. 成交、费用和保守顺序

- 每次 fill 手续费：filled notional 的 `0.001`。
- 每次 fill 不利滑点：`0.0004`。
- stop 被 open 穿越：按该 open，再施加退出不利滑点；不得按旧 stop 价成交。
- 同一根 K 同时触及 stop 与 target：按 stop-first。
- 资金费：`entry_ts <= funding_ts < exit_ts` 的实际 Binance funding rate 求和；long 对正 funding 付费，short 对正 funding 收费。
- TP/SL 距离使用信号 K 已知的 `ATR14` 冻结，不在持仓中重算。

## 8. 冻结结果

| Window | Annual multiple | Total return | Max DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | `12.5196x` | `+281.63%` | `-16.93%` | `84.21%` | `38` | `7.019` |
| Validation | `9.8178x` | `+64.08%` | `-11.35%` | `66.67%` | `15` | `8.027` |
| Locked holdout | `5.2151x` | `+43.05%` | `-19.64%` | `75.00%` | `16` | `4.342` |
| Full | `9.7333x` | `+795.75%` | `-19.64%` | `78.26%` | `69` | `6.486` |

## 9. 不可实盘原因

- Full 精确年化倍率 `<10x`；locked holdout 远低于 `10x`。
- K+2 延迟：holdout 年化 `0.175x`、回撤 `-36.77%`。
- 滑点从 `4 bps` 增到 `8 bps`：holdout 年化 `2.156x`、回撤 `-33.12%`。
- `164` 行单腿/active-field 消融中，完整 full + holdout target pass 为 `0`。
- 最大初始 stop 距离约 `15.90%`，其中一次超过当前 `PERCENT_PRICE` `15%` 上界，真实条件单接受性需要订单级验证。
- 没有 production runner、restart recovery、exchange reconciliation、missing-bar fail-closed、kill switch 或真实 stop-market 滑点证据。

因此该组合只保留为研究边界。禁止仅因 `9.73x` 显示为一位小数后接近 `10x` 而提升状态。

## 10. 复现命令

```bash
uv run python research/hype/1h-adaptive-regime/scripts/fetch_hype_binance_1h.py --refresh
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_adaptive_regime_search.py --random-configs 120000 --prefit-keep 500 --holdout-keep 200
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_adaptive_regime_refine.py --neighbors 180000 --prefit-keep 700 --holdout-keep 260
uv run python research/hype/1h-adaptive-regime/scripts/audit_hype_1h_adaptive_regime_boundary.py
```
