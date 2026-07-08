# HYPE-15M-MII-V1.4 参数规格（非实盘批准）2026-07-08

Family：`HYPE-15M-Multi-Indicator-Intraday`（alias：`HYPE-15M-MII`）

Version：`HYPE-15M-MII-V1.4`

Parent version：`HYPE-15M-MII-V1.3`

Status：`aggressive diagnostic observation / not implemented in runner / not dry-run / not live-ready`

## 结论

`HYPE-15M-MII-V1.4` 是按用户指定登记的新观察版本。它完全沿用 `HYPE-15M-MII-V1.3` 的 RSI/MACD/ATR bracket/成本/`2.5x` 暴露，只把成交量过滤从：

```text
min_rvol96 = 1.0
```

下调为：

```text
min_rvol96 = 0.85
```

该版本来自 `2026-07-08` 的 RVOL 定向网格与细网格诊断。它是进取观察候选，不是 live、paper-live、dry-run 或 handoff。若要进入 runner dry-run，必须另行修改 `/Users/ZK/OpenCode/quant-runner` 配置或策略参数，并完成指标/信号/交易路径对拍。

## 身份与边界

| 项 | 值 |
| --- | --- |
| Full family name | `HYPE-15M-Multi-Indicator-Intraday` |
| Alias | `HYPE-15M-MII` |
| Version | `HYPE-15M-MII-V1.4` |
| Parent version | `HYPE-15M-MII-V1.3` |
| Exchange | `Binance` |
| Market | `USD-M perpetual` |
| Symbol | `HYPEUSDT` / `HYPE/USDT:USDT` |
| Timeframe | `15m` |
| Runner status | 尚未实现为独立 runner 配置 |
| Current dry-run version | `HYPE-15M-MII-V1.3` |
| Core ledger | `../hype-15m-mii-core-ledger.md` |
| Main evidence | `../research-notes/hype-15m-mii-v1-3-rvol-grid-2026-07-08.md`、`../research-notes/hype-15m-mii-v1-3-rvol-fine-grid-2026-07-08.md` |

不要用裸 `V1.4` 判断策略身份；它只在 `HYPE-15M-MII` 家族内有效。

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
| `min_rvol96` | `0.85` | `V1.4` 唯一相对 `V1.3` 的参数变化。 |
| `h1_confirm` | `false` | 不启用 1h 方向确认。 |
| `rsi14_band` | `false` | 不启用 RSI14 区间过滤。 |
| `cooldown_bars` | `0` | 无额外冷却；单仓状态阻止重叠开仓。 |

### 出场、暴露与成本

| 参数 | 值 | 说明 |
| --- | ---: | --- |
| `exit_kind` | `atr_fixed_bracket` | 入场时设置一次性固定 TP/SL。 |
| `atr_window_for_exit` | `96` | 使用信号 K 的 `ATR96%`。 |
| `tp_atr_mult` | `1.25` | 止盈距离为 `1.25 * ATR96%`。 |
| `sl_atr_mult` | `5.0` | 止损距离为 `5.0 * ATR96%`。 |
| `timeout_bars` | `24` | 最长持有 24 根 `15m` K，约 6 小时。 |
| `same_bar_priority` | `stop_first` | 同一根 K 同时触发止盈止损时按止损优先。 |
| `exposure` | `2.5` | 固定 `2.5x` 权益暴露。 |
| `fee_rate_per_fill` | `0.001` | Binance 研究成本：每 fill `0.1000%`。 |
| `slippage_per_fill` | `0.0004` | Binance 研究滑点：每 fill `4 bps`。 |
| `round_trip_cost` | `0.0028` | 一进一出合计成本：`0.28%`。 |
| `funding` | 未计入 | 永续资金费仍是实盘前 blocker。 |

## 回测摘要

标准数据湖口径（`2025-05-30T10:30:00Z` 到 `2026-07-08T05:30:00Z`，quality gate `True`）：

| 入场 | 交易数 | 总收益 | 最大回撤 | 胜率 | Profit Factor |
| --- | ---: | ---: | ---: | ---: | ---: |
| `K+1` | `232` | `978.36%` | `-24.70%` | `84.91%` | `2.237` |
| `K+2` | `239` | `535.54%` | `-38.30%` | `83.26%` | `1.780` |

Recent Binance API K+1：

| 窗口 | 交易数 | 总收益 | 最大回撤 | 胜率 |
| --- | ---: | ---: | ---: | ---: |
| `最近90d` | `46` | `51.61%` | `-19.78%` | `86.96%` |
| `最近30d` | `16` | `0.49%` | `-16.46%` | `81.25%` |
| `最近7d/72h/24h` | `0` | `0.00%` | `0.00%` | `0.00%` |

## 决策

- `V1.4` 登记为 `V1.3 + min_rvol96=0.85` 的进取观察版本。
- `V1.4` 的优势是 K+1 全样本收益、K+2 延迟压力和 recent 90d 都强于 `rvol0.9` 与 `V1.3 baseline`。
- `V1.4` 的代价是 K+1 全样本最大回撤从 `V1.3 baseline` 的 `-22.01%` 扩大到 `-24.70%`。
- `V1.4` 不能解决最近几天不开单的问题，因为最近 `7d/72h/24h` 仍无交易。
- `V1.4` 不是当前 quant-runner dry-run 版本；当前 dry-run 仍是 `HYPE-15M-MII-V1.3`。

## TP/SL 倍数复核

`2026-07-08` 追加 `V1.4` 专项出场网格：保持 `min_rvol96=0.85`、`hold=24` 和其它参数不变，只扫描 `tp_atr_mult/sl_atr_mult`。结果显示没有候选同时改善 K+1/K+2 的收益、回撤和胜率。

| 配置 | K+1 总收益 | K+1 回撤 | K+1 胜率 | K+2 总收益 | K+2 回撤 | K+2 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `tp1p25_sl5` | `978.36%` | `-24.70%` | `84.91%` | `535.54%` | `-38.30%` | `83.26%` |
| `tp1p5_sl5` | `788.01%` | `-41.83%` | `79.30%` | `765.94%` | `-39.02%` | `78.88%` |
| `tp1p25_sl4p5` | `883.76%` | `-23.89%` | `84.55%` | `405.48%` | `-39.70%` | `82.08%` |

结论：`V1.4` 暂不改变 `tp_atr_mult=1.25` 和 `sl_atr_mult=5.0`。该结构确实是“小止盈、宽止损、高胜率”，但在当前网格里仍是最稳的联合折中；更高 TP 或更窄 SL 会牺牲 K+1/K+2 联合形状。

## 上线前硬性 blocker

即便后续要把 `V1.4` 加入 dry-run，也必须先补齐：

- 与 Python 研究脚本对拍 `RSI7`、`MACD`、`ATR96%`、`RVOL96`、最终信号和逐笔交易路径。
- 资金费回放。
- 盘口级 market/stop-market 滑点审计。
- K+2/K+3 和更差滑点压力测试。
- 重启恢复、交易所对账、missing-bar fail-closed 和 kill switch。
- 独立 OOS 或足够长的 forward 观察。
