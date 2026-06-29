# HYPE-1M-EMA-Crossover 决策日志

家族名称：`HYPE-1M-EMA-Crossover`

历史别名：`HYPE-1M-EMA-X`

## 当前边界

- 这是一个独立的 HYPE 策略家族，用于 Binance HYPEUSDT `1m` EMA cross 研究。
- 它不是 `HYPE-EMA-Crossover` / `15m-ema-crossover` 的子版本。
- 它还不是 live-approved strategy line。
- 在 forward validation 和 live execution audits 完成前，其第一个 candidate 必须仅视为 paper-live。

## 研究批次记录

- `research_hype_1m_ema_crossover_live_search.py`：首次 Binance HYPEUSDT `1m` EMA cross 搜索，覆盖 `2026-03-25` 到 `2026-06-25`。它测试了 live-executable next-bar entries、fixed take-profit、trailing take-profit、hard stops、保守 same-candle stop priority、cost assumptions 和 common filters。
- `2026-06-26`：将首个 `1m` 数据集从 downloader cache 提升到标准数据湖，然后刷新到 `2026-06-26 04:23:00 UTC`：raw 和 normalized candles 位于 `data/raw|normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1m/date=*/symbol=hype_usdt_usdt.parquet`，search feature factors 位于 `data/features/factor=*/version=hype_1m_ema_crossover_live_search_2026_06_25/...`。
- `2026-06-27`：`research_hype_1m_ema_deviation_take_profit.py` 测试用户要求的 short-cycle EMA cross 形态（`8/21`、`13/48`、`21/55`、`21/72`、`21/96`、`30/120`），包含 ATR-normalized fast-EMA deviation arming、high/low-water drawdown exits、exhaustion confirmation 和 staged partial take-profit。数据质量在 `134,184` 根连续 Binance HYPEUSDT `1m` K 线上通过，范围为 `2026-03-25 00:00:00 UTC` 到 `2026-06-26 04:23:00 UTC`，但通过 paper gate 的行数为 `0`。
- `2026-06-27`：`research_hype_1m_ema_v35_filter_overlay.py` 将 `HYPE-EMA-Trend-Breakout-V35` strength filters 迁移到 `1m` EMA cross + deviation take-profit 形态上：closed 15m EMA96/384 direction、15m ADX28、15m volume_surge、closed 1h confirmation，以及 relaxed/early-ADX variants。该 overlay 相比未过滤 short-cycle cross 显著降噪，但 paper-gate rows 仍为 `0`。最佳全样本行仅接近持平到 `+1.05%`，且未通过 forward/recent slices；`EMA21/96` 正收益行只有 `2` 笔交易。

## 候选记录

- `HYPE-1M-EMA-Crossover-TRAIL-144-1597`：第一个优先 paper-live candidate。它使用 EMA144/EMA1597 cross entries、ADX/ret60/ATR/cooldown filters、`1.4%` hard stop、`1.4%` trailing activation、`1.8%` trail distance，以及 `1,440` bar max hold。`2x` exposure 版本达到用户要求的 `20x` annualized factor，并且回撤低于 `3x` search winner。
- `HYPE-1M-EMA-Crossover-FIXED-233-1597`：次要 fixed take-profit 参考。它交易更少，并需要更高 exposure 才能达到收益目标，因此优先级低于 trailing candidate。
- `HYPE-1M-EMA-Crossover-DEVIATION-TP-SHORT-CYCLE`：no-go diagnostic，不是 candidate。用户要求的 `EMA21/96` 子集在加杠杆前已经显著为负；其最佳测试行为 `1x` 全样本收益约 `-74%`，forward 和 recent slices 也为负。结果支持把 deviation 保留为 exit-state 概念，但不支持在当前 cost model 下将 short-cycle EMA cross chasing 作为独立 candidate。
- `HYPE-1M-EMA-Crossover-V35-FILTER-OVERLAY`：no-go diagnostic，不是 candidate。V35-style 15m/1h trend-quality filters 有助于压制虚假 1m crosses，但 `HYPE-EMA-Trend-Breakout-V35` 的盈利机制仍是 15m trend-breakout entry 加 ATR bracket，而不是 1m cross 本身。

## 实盘可行性门槛

在任何超过 paper-live 的 promotion 之前：

- 增加 funding-rate accounting。
- 不改参数，在更晚的 forward window 上重跑。
- 在 `2026-06-25` 收盘后重跑，确保最后一天不是 partial。
- 审计真实 Binance account fee tier 和成交中的 live slippage。
- 实现 restart recovery、reduce-only protective orders、duplicate-order/idempotency handling、missing-data behavior，以及 emergency flat/kill switch。
