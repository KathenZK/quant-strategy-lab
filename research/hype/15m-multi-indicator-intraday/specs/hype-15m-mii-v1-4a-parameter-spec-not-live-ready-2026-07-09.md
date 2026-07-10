# HYPE-15M-MII-V1.4A 参数规格（非实盘批准）2026-07-09

Family：`HYPE-15M-Multi-Indicator-Intraday`（alias：`HYPE-15M-MII`）

Version：`HYPE-15M-MII-V1.4A`

Parent version：`HYPE-15M-MII-V1.4`

Status：`recent-window TP/SL observation / not implemented in runner / not dry-run / not live-ready`

## 结论

`HYPE-15M-MII-V1.4A` 是按用户指定登记的 `V1.4` 出场参数观察变体。它完全沿用 `V1.4` 的入场、过滤、成本和 `2.5x` 权益暴露，只把 ATR bracket 从：

```text
tp_atr_mult = 1.25
sl_atr_mult = 5.0
```

改为：

```text
tp_atr_mult = 1.40
sl_atr_mult = 3.0
```

`V1.4A` 的最近 `90d/30d` K+1 表现优于 `V1.4 baseline`，且最差单笔更浅；但全样本 K+1 收益、回撤和胜率明显弱于 `V1.4 baseline`，最近 `7d/72h/24h` 仍然 `0` 笔。它是近期窗口观察参数，不是 live、paper-live、dry-run 或 handoff。

## 身份与边界

| 项 | 值 |
| --- | --- |
| Full family name | `HYPE-15M-Multi-Indicator-Intraday` |
| Alias | `HYPE-15M-MII` |
| Version | `HYPE-15M-MII-V1.4A` |
| Parent version | `HYPE-15M-MII-V1.4` |
| Exchange | `Binance` |
| Market | `USD-M perpetual` |
| Symbol | `HYPEUSDT` / `HYPE/USDT:USDT` |
| Timeframe | `15m` |
| Runner status | 尚未实现为独立 runner 配置 |
| Current dry-run version | `HYPE-15M-MII-V1.3` |
| Core ledger | [`../hype-15m-mii-core-ledger.md`](../hype-15m-mii-core-ledger.md) |
| Dry-run validation spec | [`../live-specs/hype-15m-mii-v1-4a-dry-run-validation-spec-not-live-ready-2026-07-10.md`](../live-specs/hype-15m-mii-v1-4a-dry-run-validation-spec-not-live-ready-2026-07-10.md) |
| Main evidence | [`../notes/hype-15m-mii-v1-4-tp-sl-neighborhood-2026-07-09.md`](../notes/hype-15m-mii-v1-4-tp-sl-neighborhood-2026-07-09.md) |

不要用裸 `V1.4A` 判断策略身份；它只在 `HYPE-15M-MII` 家族内有效。`V1.4A` 不是 `V1.4 baseline`，也不是当前 quant-runner dry-run 版本。

## 参数总表

### 信号与过滤

| 参数 | 值 | 说明 |
| --- | ---: | --- |
| `side` | `both` | 多空双向。 |
| `rsi_window` | `7` | 反转信号使用 `RSI(7)`。 |
| `rsi_long_cross` | `40.0` | `RSI7` 从下向上穿越 `40` 触发多头候选。 |
| `rsi_short_cross` | `60.0` | `RSI7` 从上向下穿越 `60` 触发空头候选。 |
| `macd_fast` | `12` | MACD 快 EMA span。 |
| `macd_slow` | `26` | MACD 慢 EMA span。 |
| `macd_signal` | `9` | MACD signal EMA span。 |
| `min_dir_macd` | `0.0` | 方向化 `MACD histogram` 必须非负。 |
| `min_atr_pct96` | `0.0075` | 仅当 `ATR96% >= 0.75%` 时允许交易。 |
| `max_atr_pct96` | `0.028` | 仅当 `ATR96% <= 2.80%` 时允许交易。 |
| `min_rvol96` | `0.85` | 沿用 `V1.4`。 |
| `h1_confirm` | `false` | 不启用 1h 方向确认。 |
| `rsi14_band` | `false` | 不启用 RSI14 区间过滤。 |
| `cooldown_bars` | `0` | 无额外冷却；单仓状态阻止重叠开仓。 |

### 出场、暴露与成本

| 参数 | 值 | 说明 |
| --- | ---: | --- |
| `exit_kind` | `atr_fixed_bracket` | 入场时设置一次性固定 TP/SL。 |
| `atr_window_for_exit` | `96` | 使用信号 K 的 `ATR96%`。 |
| `tp_atr_mult` | `1.40` | 止盈距离为 `1.40 * ATR96%`。 |
| `sl_atr_mult` | `3.0` | 止损距离为 `3.0 * ATR96%`。 |
| `timeout_bars` | `24` | 最长持有 24 根 `15m` K，约 6 小时。 |
| `same_bar_priority` | `stop_first` | 同一根 K 同时触发止盈止损时按止损优先。 |
| `exposure` | `2.5` | 固定 `2.5x` 权益暴露。 |
| `fee_rate_per_fill` | `0.001` | Binance 研究成本：每 fill `0.1000%`。 |
| `slippage_per_fill` | `0.0004` | Binance 研究滑点：每 fill `4 bps`。 |
| `round_trip_cost` | `0.0028` | 一进一出合计成本：`0.28%`。 |
| `funding` | 未计入 | 永续资金费仍是实盘前 blocker。 |

## 回测摘要

标准数据湖口径（`2025-05-30T10:30:00Z` 到 `2026-07-08T05:30:00Z`，quality gate `True`）：

| 配置 | 入场 | 交易数 | 总收益 | 最大回撤 | 胜率 | Profit Factor | 最差单笔 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1.4 baseline` | `K+1` | `232` | `978.36%` | `-24.70%` | `84.91%` | `2.237` | `-13.656%` |
| `V1.4A` | `K+1` | `235` | `584.90%` | `-32.85%` | `78.72%` | `1.735` | `-10.971%` |
| `V1.4 baseline` | `K+2` | `239` | `535.54%` | `-38.30%` | `83.26%` | `1.780` | `-13.656%` |
| `V1.4A` | `K+2` | `238` | `637.85%` | `-34.58%` | `79.83%` | `1.749` | `-11.650%` |

Recent Binance API（`2026-07-09` 报告口径）：

| 配置 | 入场 | 窗口 | 交易数 | 总收益 | 最大回撤 | 胜率 | Profit Factor | 最差单笔 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1.4 baseline` | `K+1` | `最近90d` | `46` | `51.61%` | `-19.78%` | `86.96%` | `1.911` | `-13.656%` |
| `V1.4A` | `K+1` | `最近90d` | `45` | `78.82%` | `-19.58%` | `84.44%` | `2.437` | `-9.108%` |
| `V1.4 baseline` | `K+1` | `最近30d` | `15` | `16.65%` | `-12.34%` | `86.67%` | `2.308` | `-10.176%` |
| `V1.4A` | `K+1` | `最近30d` | `15` | `27.09%` | `-8.64%` | `86.67%` | `3.842` | `-6.386%` |
| `V1.4 baseline` | `K+2` | `最近90d` | `47` | `49.74%` | `-21.88%` | `87.23%` | `1.848` | `-13.656%` |
| `V1.4A` | `K+2` | `最近90d` | `46` | `67.07%` | `-21.49%` | `82.61%` | `2.115` | `-9.108%` |
| `V1.4 baseline` | `K+2` | `最近30d` | `15` | `15.92%` | `-12.39%` | `86.67%` | `2.242` | `-10.176%` |
| `V1.4A` | `K+2` | `最近30d` | `15` | `19.30%` | `-8.69%` | `80.00%` | `2.673` | `-6.386%` |

Recent Binance API 最近 `24h/72h/7d`：`V1.4A` 与 `V1.4 baseline` 均为 `0` 笔。

## 决策

- `V1.4A` 登记为 `V1.4 + TP=1.4*ATR96 / SL=3.0*ATR96` 的近期窗口观察变体。
- 优势：recent API K+1 最近 `90d/30d` 总收益从 `51.61%/16.65%` 提升到 `78.82%/27.09%`，最差单笔从 `-13.656%/-10.176%` 变浅到 `-9.108%/-6.386%`。
- 风险：全样本 K+1 总收益从 `978.36%` 降到 `584.90%`，最大回撤从 `-24.70%` 加深到 `-32.85%`，胜率从 `84.91%` 降到 `78.72%`。
- `V1.4A` 没有解决最近一周不开单：recent API 最近 `7d/72h/24h` 仍为 `0` 笔。
- `V1.4A` 不替换 `V1.4 baseline`，不进入 runner dry-run，不进入 promotion 状态。

## 上线前硬性 blocker

若后续要把 `V1.4A` 加入 runner dry-run 或 live validation，必须先补齐：

- 与 Python 研究脚本对拍 `RSI7`、`MACD`、`ATR96%`、`RVOL96`、最终信号和逐笔交易路径。
- 确认 runner 参数能区分 `V1.4 baseline` 与 `V1.4A`，尤其是 `tp_atr_mult/sl_atr_mult`。
- 资金费回放。
- 盘口级 market/stop-market 滑点审计。
- K+2/K+3 和更差滑点压力测试。
- 重启恢复、交易所对账、missing-bar fail-closed 和 kill switch。
- 独立 OOS 或足够长的 forward 观察。
