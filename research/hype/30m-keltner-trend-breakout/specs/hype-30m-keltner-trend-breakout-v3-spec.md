# HYPE-30M-Keltner-Trend-Breakout-V3 参数规格

版本：`HYPE-30M-Keltner-Trend-Breakout-V3`

相对 parent：`HYPE-30M-Keltner-Trend-Breakout-V2.1`

历史研究别名：损失-regime 过滤候选 / 前称 `V2.2 candidate`

状态：`registered / not promoted / not live-ready`

用途：冻结研究侧版本身份；不是 runner handoff，不是 live spec。

## 市场与数据

| 项 | 值 |
| --- | --- |
| Exchange | Binance |
| Market | USDM perpetual |
| Symbol | `HYPEUSDT` |
| 基础数据 | `1m` closed OHLCV |
| 信号周期 | `30m` |
| 趋势周期 | `1h` |
| 标准相位 | `30m :00/:30`，`1h` 整点 |
| 时区 | UTC |
| 冻结研究样本 | `2025-05-30 10:30` 至 `2026-07-13 06:06 UTC` |

完整 raw/normalized data lake 与 cache 已完成零差异对拍。`30m` 必须由完整 30 根 `1m` 聚合，`1h` 必须由完整 60 根 `1m` 聚合；残缺 bar 丢弃。

## 冻结参数

| 参数 | V3 |
| --- | ---: |
| Keltner EMA | `10` |
| Keltner ATR RMA | `10` |
| Keltner multiplier | `2.0` |
| 1h EMA fast | `16` |
| 1h EMA slow | `44` |
| 1h slow slope lag | `5` |
| Leverage ATR RMA | `84` |
| ATR target | `0.027` |
| Minimum leverage floor | 无 |
| Maximum leverage | `3.0x` |
| Entry ATR cap | `ATR84 / next_open <= 1.25%` |
| Close location min | 方向化 `>= 0.65` |
| Take profit | `10%` |
| Stop loss | `2.5%` |
| Maximum hold | `30` 根 30m |

EMA 使用 `ewm(alpha=2/(n+1), adjust=False, min_periods=n)`；ATR 使用 Wilder RMA：`ewm(alpha=1/n, adjust=False, min_periods=n)`。

## 相对 V2.1 的变化

V3 = V2.1 + 两个入场过滤：

1. 低波动 regime：`ATR84(signal_bar) / next_30m_open <= 0.0125`
2. 突破收盘质量：多头 `(close-low)/(high-low) >= 0.65`；空头 `(close-low)/(high-low) <= 0.35`

其余信号、ATRVT 杠杆、固定 TP/SL、`hold=30`、成本与执行时序与 V2.1 相同。

## 信号规则

```text
mid     = EMA10(close_30m)
atr10   = RMA10(TR_30m)
upper   = mid + 2.0 * atr10
lower   = mid - 2.0 * atr10

ema_fast = EMA16(close_1h)
ema_slow = EMA44(close_1h)
slope    = ema_slow[t] - ema_slow[t-5]

long_regime  = ema_fast > ema_slow and slope > 0
short_regime = ema_fast < ema_slow and slope < 0

entry_atr_pct = RMA84(TR_30m)[signal_bar] / next_30m_open
close_location = (close_30m - low_30m) / (high_30m - low_30m)

long_signal  = long_regime
               and close_30m > upper
               and entry_atr_pct <= 0.0125
               and close_location >= 0.65

short_signal = short_regime
               and close_30m < lower
               and entry_atr_pct <= 0.0125
               and close_location <= 0.35
```

每根 `30m` 信号 bar 只读取最近一根已收盘 `1h` bar。两个新增过滤只使用已收盘信号 bar 及更早数据。

## 杠杆与仓位

```text
raw_leverage = 0.027 / entry_atr_pct
leverage     = min(raw_leverage, 3.0)
notional     = equity_at_entry * leverage
```

无 minimum leverage floor；未来高波动下允许仓位低于 `1.0x`。杠杆在入场时冻结，持仓期间不动态调整。

## 执行与退出

- `30m` 收盘确认信号，下一根 `30m` open 入场。
- 有持仓时忽略新信号；无冷却、无加仓。
- 入场后立即挂固定 TP/SL。
- 多头：`TP=entry×1.10`，`SL=entry×0.975`。
- 空头：`TP=entry×0.90`，`SL=entry×1.025`。
- 入场 bar 起检查 bracket；同 bar TP/SL 冲突时 SL 优先。
- 若 open 已越过 stop，按 open 再加不利滑点成交，不按陈旧 stop 价成交。
- `i-entry_i >= 30` 时在该 bar close 退出。

## 成本口径

| 项 | 值 |
| --- | ---: |
| 手续费 | `0.001/fill` |
| 不利滑点 | `0.0004/fill` |
| Funding | Binance 历史 funding，计入 |

## 冻结研究指标

样本：`2025-05-30 10:30` 至 `2026-07-13 06:06 UTC`。

| 指标 | V3 |
| --- | ---: |
| Return | `+6328.98%` |
| MDD | `-22.68%` |
| Sharpe | `5.05` |
| Trades | `78` |
| Win rate | `67.95%` |
| Profit factor | `4.31` |
| Average leverage | `2.72x` |
| Worst trade | `-8.46%` |
| TP / SL / time / window end | `8 / 16 / 53 / 1` |

相对同样本 V2.1 刷新基线（`+4522.03% / MDD -25.84% / 胜率 56.14% / 114 笔`）：

- 胜率提高 `11.81pp`；
- MDD 改善 `3.17pp`；
- 收益提高约 `+1807pp`；
- SL 次数从 `38` 降至 `16`。

## 门禁状态

- 数据质量、Gate 0/1/2、Gate 5、Gate 3 Monte Carlo：通过或改善通过。
- Gate 6 启动时间：失败；CAGR CV `0.585`。
- Gate 7 30m 相位：失败；非原生/原生中位 CAGR 比约 `13.80%`。
- Gate 4 与 live-executable runner 运维部分：未完成。
- Holdout：仅 2 笔亏损交易，不足以支撑 live-ready。

因此 V3 只登记研究身份，不进入 `audit`、`live spec`、`dry-run` 或 `live`。

## 证据

- [损失 Regime 过滤优化](../notes/hype-30m-k2-v2-1-loss-regime-filter-optimization-2026-07-13.md)
- [V2.1 规格](hype-30m-keltner-trend-breakout-v2-1-spec.md)
- [研究脚本](../scripts/research_hype_30m_k2_v2_1_loss_regime_filters.py)
- [汇总 JSON](../artifacts/hype_30m_k2_v2_1_loss_regime_filters_2026-07-13.json)
- [V3 逐笔交易](../artifacts/hype_30m_k2_v2_1_loss_regime_filter_trades_2026-07-13.csv)
