# HYPE-30M-Keltner-Trend-Breakout-V2.1 参数规格

版本：`HYPE-30M-Keltner-Trend-Breakout-V2.1`

历史来源别名：`K2-FQ-V2-ATRVT-OFF-PRUNED-TUNED`

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
| 数据范围 | `2025-05-30 10:30` 至 `2026-07-10 06:43` |

完整 raw/normalized data lake 与 cache 已完成零差异对拍。`30m` 必须由完整 30 根 `1m` 聚合，`1h` 必须由完整 60 根 `1m` 聚合；残缺 bar 丢弃。

## 冻结参数

| 参数 | V2.1 |
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
| Take profit | `10%` |
| Stop loss | `2.5%` |
| Maximum hold | `30` 根 30m |

EMA 使用 `ewm(alpha=2/(n+1), adjust=False, min_periods=n)`；ATR 使用 Wilder RMA：`ewm(alpha=1/n, adjust=False, min_periods=n)`。

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

long_signal  = long_regime and close_30m > upper
short_signal = short_regime and close_30m < lower
```

每根 `30m` 信号 bar 只读取最近一根已收盘 `1h` bar。V2.1 相对外部 V2 移除了：

- `close_1h > ema_slow` / `close_1h < ema_slow`：历史逐笔等价的冗余条件；
- `not opposite_regime`：fast/slow regime 已互斥，属于逻辑死条件。

## 杠杆与仓位

```text
entry_atr_pct = RMA84(TR_30m)[signal_bar] / next_30m_open
raw_leverage  = 0.027 / entry_atr_pct
leverage      = min(raw_leverage, 3.0)
notional      = equity_at_entry * leverage
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

ATR10/ATR84 动态 TP/SL 已完成 433 组诊断，没有配置同时提高胜率、降低 MDD并满足收益保留约束；动态 bracket 不属于 V2.1，固定 TP/SL 继续冻结。

## 成本口径

| 项 | 值 |
| --- | ---: |
| 手续费 | `0.001/fill` |
| 不利滑点 | `0.0004/fill` |
| Funding | Binance 历史 funding，计入 |

手续费按实际成交名义收取；开仓、TP、SL、time exit 均施加方向不利滑点。

## 冻结研究指标

| 指标 | V2.1 |
| --- | ---: |
| Return | `+4638.01%` |
| MDD | `-25.84%` |
| Sharpe | `4.22` |
| Trades | `113` |
| Win rate | `56.64%` |
| Profit factor | `2.76` |
| Average leverage | `2.48x` |
| Worst trade | `-8.46%` |
| TP / SL / time | `10 / 38 / 65` |

相对严格 V2 基线：

- 净交易数 `114 → 113`，但不是简单删除一笔；
- 108 笔保持相同 entry timestamp，出现 5 个 V2.1 新入口、6 个 V2 旧入口消失；
- 共同入口中 72/108 笔杠杆发生变化；
- Return 保留 `96.09%`，MDD 改善 `2.13pp`，胜率提高 `1.37pp`。

## 门禁状态

- 数据质量、Gate 0/1/2、Gate 5：通过。
- Gate 3 Monte Carlo：失败；交易重排 MDD p05 `-40.85%`，差于门槛 `-38.77%`。
- Gate 6 启动时间：失败；CAGR CV `0.917`。
- Gate 7 相位：失败；30m 非原生/原生中位 CAGR 比 `9.72%`。
- Gate 4 与 live-executable runner 运维部分：未完成。

因此 V2.1 只登记研究身份，不进入 `audit`、`live spec`、`dry-run` 或 `live`。

## 证据

- [全参数消融与微调报告](../notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md)
- [ATR 动态 TP/SL 诊断](../notes/hype-30m-k2-v2-1-dynamic-atr-bracket-2026-07-10.md)
- [严格门禁报告](../notes/hype-30m-k2-strict-validation-gates-2026-07-10.md)
- [研究脚本](../scripts/research_hype_30m_k2_v2_full_ablation_and_tune.py)
- [汇总 JSON](../artifacts/hype_30m_k2_v2_full_ablation_tune_2026-07-10.json)
- [V2.1 逐笔交易](../artifacts/hype_30m_k2_v2_tuned_trades_2026-07-10.csv)
