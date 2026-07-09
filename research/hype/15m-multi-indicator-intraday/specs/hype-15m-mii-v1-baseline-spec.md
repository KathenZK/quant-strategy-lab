# HYPE-15M-Multi-Indicator-Intraday-V1 基线规格

Family：`HYPE-15M-Multi-Indicator-Intraday`（alias：`HYPE-15M-MII`）

版本：`HYPE-15M-Multi-Indicator-Intraday-V1`

状态：`diagnostic baseline only / not live-ready`

## 一句话定义

V1 是 Binance HYPEUSDT perpetual `15m` 上的双向 RSI 反转策略：`RSI(7)` 向上重新越过 `30` 时做多、向下重新跌破 `60` 时做空，再用方向化 `MACD(12,26,9)` histogram 和 `ATR96` 波动区间过滤，下一根 open 入场，使用固定 TP/SL 和最长持仓退出。

## 版本边界

- V1 来自 `2026-06-25` 广泛搜索中的最佳综合结果，不是原始目标的达标结果。
- “记录为 V1”只表示冻结一个可复现研究基线，不表示 promotion 到 candidate、paper-live、dry-run 或 live。
- 本版本只属于 `HYPE-15M-Multi-Indicator-Intraday`，不能和 `HYPE-EMA-Crossover-V1`、`HYPE-EMA-Trend-Breakout-V1` 或其他 HYPE 家族的 V1 混用。

## 数据与成本

- 交易所：Binance USD-M futures。
- 标的：`HYPE/USDT:USDT`。
- 周期：`15m`。
- 数据：`data/raw|normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m/date=*/symbol=hype_usdt_usdt.parquet`。
- 研究只使用 `is_closed=true` 的 UTC K 线。
- 手续费：`0.1000%/fill`。
- 固定滑点：`0.0400%/fill`。
- round-trip 成本：`0.2800%`，在仓位暴露前从单笔原始收益扣除。
- 资金费：当前未计入，是实盘 promotion blocker。

## 指标定义

- `RSI(7)`：Wilder 风格指数平滑，`alpha=1/7`、`adjust=false`、`min_periods=7`。
- `MACD(12,26,9)`：`EMA12 - EMA26`，signal 为 MACD 的 `EMA9`，过滤值为 histogram。
- `ATR96 pct`：True Range 的 `96` 根简单滚动均值除以当前 close。
- 所有指标只使用信号 K 收盘时已经可见的数据。

## V1 参数

| 参数 | V1 值 | 作用 |
| --- | ---: | --- |
| `rsi_window` | `7` | RSI 周期。 |
| `rsi_low` | `30` | 多头从超卖区恢复的上穿阈值。 |
| `rsi_high` | `60` | 空头从高位回落的下穿阈值。 |
| `macd_fast` | `12` | MACD 快 EMA。 |
| `macd_slow` | `26` | MACD 慢 EMA。 |
| `macd_signal` | `9` | MACD signal EMA。 |
| `min_dir_macd_hist` | `0` | 多头 histogram `>=0`，空头 histogram `<=0`。 |
| `atr_window` | `96` | ATR pct 窗口。 |
| `min_atr_pct` | `0.006` | 波动下限 `0.60%`。 |
| `max_atr_pct` | `0.028` | 波动上限 `2.80%`。 |
| `take_profit_pct` | `0.009` | 固定止盈 `0.90%`。 |
| `stop_pct` | `0.028` | 固定止损 `2.80%`。 |
| `max_hold_bars` | `16` | 最长持有 `4` 小时。 |
| `side` | `both` | 多空双向。 |
| `cooldown_bars` | `0` | 没有额外冷却，但严格禁止持仓重叠。 |
| `exposure` | `1.5` | 回测权益暴露 `1.5x`。 |

## 信号与过滤

在闭合 K `t` 上：

- 多头原始信号：`RSI7[t] > 30` 且 `RSI7[t-1] <= 30`。
- 空头原始信号：`RSI7[t] < 60` 且 `RSI7[t-1] >= 60`。
- 多头 MACD 过滤：`MACD_hist[t] >= 0`。
- 空头 MACD 过滤：`MACD_hist[t] <= 0`。
- 双向 ATR 过滤：`0.006 <= ATR96[t] / close[t] <= 0.028`。

过滤全部通过后，在 K `t+1` 的 open 发出入场订单。若已有持仓，不能重叠开仓。

## 可执行退出时序

- 入场 open 后立即维护固定 TP/SL bracket。
- 每根完整持仓 K 先检查 open 是否穿越 stop；穿越时按 open 成交，再计固定成本。
- 同一根 K 同时触及 stop 和 target 时按 stop-first。
- 盘中 TP/SL 退出后，不允许回到该根 K 的 open 再开新仓；最早下一根 K 才能入场。
- 持满 `16` 根 K 后，在下一根 open 执行 timeout；不能先读取该根 high/low 再回到 open 成交。
- timeout 或 open gap 退出可在同一 open 先平后开，但 live runner 必须保证 reduce-only 平仓确认先于新仓。

## 标准数据湖复现指标

数据覆盖 `2025-05-30 10:30 UTC` 到 `2026-06-26 04:00 UTC`，共 `37,607` 根闭合 K；使用修正后的退出与单仓时序：

| 年化 | 总收益 | 年化倍数 | 最大回撤 | 胜率 | 交易数 | 笔/日 | PF | Last90 年化 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `18.66%` | `20.14%` | `1.187x` | `-31.84%` | `75.28%` | `360` | `0.919` | `1.106` | `-41.44%` |

## 状态与推进边界

V1 不能直接实盘，主要原因如下：

- 未达到原始 `>=2000%` 年化目标；在 `0.2800%` round-trip 成本下，回撤超过 `20%`，后半段与 Last90 均为负。
- 全参数消融 `0/62` 通过完整目标与稳定性 gate。
- 删除 MACD 过滤后策略严重亏损，说明结果依赖窄过滤组合。
- 没有生产 runner、订单状态恢复、missing-bar fail-closed、kill switch 和交易所对账。
- 没有 tick/盘口级 stop-market 回放、真实滑点样本和资金费统一核算。

完整证据：

- `../ablations/hype-15m-mii-v1-full-parameter-ablation-2026-06-29.md`
- `../diagnostics/hype-15m-mii-v1-live-feasibility-2026-06-29.md`
- `../scripts/research_hype_15m_mii_v1_full_ablation.py`
