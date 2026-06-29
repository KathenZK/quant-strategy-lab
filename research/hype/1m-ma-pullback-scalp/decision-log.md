# HYPE-1M-MA-Pullback-Scalp 决策日志

家族 id：`HYPE-1M-MA-Pullback-Scalp`

## 当前边界

- 这是一个独立的 Binance HYPEUSDT perpetual `1m` moving-average pullback scalp 研究家族。
- 它不是 `HYPE-1M-EMA-Crossover` 的版本，因为入场是 pullback-end structure confirmation，而不是 EMA cross event timing。
- 它不是 `HYPE-5M-Micro-Scalp` 的版本，因为 timeframe、signal mechanics、cost sensitivity 和 holding-time assumptions 都不同。
- 研究结论必须保存在本目录下，持久 JSON/CSV 证据放入 `artifacts/`。
- 在完成 order timing、bracket maintenance、restart behavior、cost sensitivity 与 paper/live-dry-run reconciliation 审计前，本家族任何策略都不能称为 live-ready。

## 研究批次

- Initial scaffold：`scripts/research_hype_1m_ma_pullback_scalp.py` 实现 two-MA pullback structure pattern，采用 closed-bar signals、next-open entries、fixed TP/SL brackets、stop-first same-bar ordering 和 max-hold timeout。
- `diagnostics/hype-1m-ma-pullback-scalp-search-2026-06-26.md`：首次 executable search。在 Binance HYPEUSDT perpetual `1m` 上测试 `6,740` 个配置，覆盖 `reclaim`、`platform_break` 和 `engulf_reclaim` 触发器；数据质量通过，包含 `134,184` 根连续 K 线，raw/normalized OHLCV alignment mismatch counts 全部为 `0`，且没有 missing/duplicate/OHLCV hard violations。结果：paper candidate passes 为 `0`。在 `>=60` 笔交易条件下，盈利配置为 `0`；在 `>=1` 笔/天条件下，全样本最高年化倍数只有 `0.57x`。样本数足够的最佳得分行为 `HYPE_1M_MA_PBS_R03037`，`platform_break` long，EMA `13/89`，TP/SL/hold `260/130/30`，`72` 笔，年化 `0.73x`，PF `0.769`，胜率 `45.83%`，maxDD `-10.30%`，recent 30d `-2.62%`。

## 当前决策

- 不提升这个精确 two-MA pullback scalp 形态到 paper-live 或 live，结论为 no-go。
- 该策略可以写成规则并回测，但在可用 HYPEUSDT `1m` 样本上，当前证据不支持说它盈利或具备 real-capital ready 条件。
