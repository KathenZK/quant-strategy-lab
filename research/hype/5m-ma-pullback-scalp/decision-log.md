# HYPE-5M-MA-Pullback-Scalp 决策日志

家族 id：`HYPE-5M-MA-Pullback-Scalp`

## 当前边界

- 这是一个独立的 Binance HYPEUSDT perpetual `5m` moving-average pullback scalp 研究家族。
- 它不是 `HYPE-5M-Micro-Scalp` 的版本，因为入场机制明确是 slow/fast MA pullback-end structure confirmation，而不是广泛指标搜索。
- 它不是 `HYPE-5M-Pullback-Trail` 的版本，因为出场是固定 TP/SL brackets，而不是 ATR trailing-stop state machines。
- 研究结论必须保存在本目录下，持久 JSON/CSV 证据放入 `artifacts/`。
- 在完成 order timing、bracket maintenance、restart behavior、cost sensitivity 与 paper/live-dry-run reconciliation 审计前，本家族任何策略都不能称为 live-ready。

## 研究批次

- Initial scaffold：`scripts/research_hype_5m_ma_pullback_scalp.py` 实现 two-MA pullback structure pattern，采用 closed-bar signals、next-open entries、fixed TP/SL brackets、stop-first same-bar ordering 和 max-hold timeout。
- `diagnostics/hype-5m-ma-pullback-scalp-search-2026-06-26.md`：首次 executable search。在 Binance HYPEUSDT perpetual `5m` 上测试 `6,740` 个配置，覆盖 `reclaim`、`platform_break` 和 `engulf_reclaim` 触发器；数据质量通过，包含 `112,822` 根连续 K 线，raw/normalized OHLCV alignment mismatch counts 全部为 `0`，且没有 missing/duplicate/OHLCV hard violations。结果：`2` 个 paper candidate pass。样本数最好的 candidate 是 `HYPE_5M_MA_PBS_R03072`：`reclaim`，both sides，EMA `21/144`，TP/SL/hold `180/160/45`，`138` 笔，年化 `1.13x`，PF `1.158`，胜率 `52.90%`，maxDD `-12.64%`，recent 30d `0.90%`。
- `diagnostics/hype-5m-ma-pullback-scalp-robustness-2026-06-26.md`：围绕两个 paper candidate 行做 local parameter-neighborhood robustness。测试 `840` 个邻域配置；`14` 个通过 robust gate，`9` 个通过 robust + monthly gate。得分最高且 monthly-pass 的邻域为 `HYPE_5M_MA_PBS_R03072__nb_0370`：`reclaim`，both sides，EMA `13/89`，TP/SL/hold `260/160/45`，`76` 笔，年化 `1.12x`，PF `1.233`，胜率 `50.00%`，maxDD `-13.59%`，recent 30d `6.39%`。

## 当前决策

- 本家族有 audit candidates，但没有 live-ready strategy。
- 优先将 `HYPE_5M_MA_PBS_R03072__base` 作为第一个 audit 起点，因为它的样本数更高（`138` 笔）且通过了邻域测试；将 `HYPE_5M_MA_PBS_R03072__nb_0370` 作为得分更高的邻域对照。
- 不要称它为高频 scalp：存活 candidate 的频率只有约 `0.15-0.35` 笔/天。
- 未完成 per-trade path review、order-maintenance audit、restart/idempotency checks 和 paper/live-dry-run reconciliation 前，不要提升。
