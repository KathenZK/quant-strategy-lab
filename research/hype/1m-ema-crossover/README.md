# HYPE-1M-EMA-Crossover

- Full family name：`HYPE-1M-EMA-Crossover`（历史别名：`HYPE-1M-EMA-X`）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `1m`
- 机制：`1m` EMA 金叉/死叉，live-executable 时序（next-bar 入场、固定/trailing TP）。
- 当前状态：`diagnostic / dry-run candidate only`；当前首选规则 `HYPE-1M-EMA-Crossover-TRAIL-144-1597`（试验 sizing `2x`、硬上限 `3x`）；未完成 forward 验证、funding/滑点审计与 runner 重启/幂等检查前不得 live。

## 边界

- 与 `HYPE-EMA-Crossover`（`15m` V14-V17 线）分家族：周期、信号频率、成本敏感度和 runner 状态机都不同，不要因同用 EMA cross 合并。
- 命名用 `HYPE-1M-EMA-Crossover-TRAIL-144-1597` 这类完整规则名；本家族尚无正式本地版本表，避免裸 `V1`。

## 入口

- 决策记录（兼任 interim ledger）：`decision-log.md`
- 首轮 live-executable 搜索：`diagnostics/hype-1m-ema-crossover-live-search-2026-06-25.md`
- 偏离止盈状态机诊断：`diagnostics/hype-1m-ema-deviation-take-profit-2026-06-27.md`
- V35 过滤器迁移诊断：`diagnostics/hype-1m-ema-v35-filter-overlay-2026-06-27.md`

## 数据口径

- 标准数据湖：`data/{raw,normalized}/ohlcv/exchange=binance/market_type=perp/timeframe=1m/.../symbol=hype_usdt_usdt.parquet`；旧 `data/cache/hype_1m_ema_crossover_live_search/` 仅为原始下载缓存，新研究一律读标准路径。

脚本在 `scripts/`，被报告引用的 JSON/CSV 在 `artifacts/`。
