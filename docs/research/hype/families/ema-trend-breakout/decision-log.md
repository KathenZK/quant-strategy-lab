# HYPE-EMA-TB Decision Log

This is the family-level reading path for HYPE EMA trend-breakout research.

## Current Boundary

- This family is research/specification material.
- Active package code contains only data and research dataset infrastructure.
- Use the canonical specs plus current data lake to regenerate backtests when needed.

## Version Notes

- `HYPE-EMA-TB-V2P`: early 15m trend breakout with 1h confirmation.
- `HYPE-EMA-TB-V30`: baseline aligned trend-family checkpoint.
- `HYPE-EMA-TB-V34`: high-return low-drawdown candidate.
- `HYPE-EMA-TB-V35`: timeout-relaxed candidate.
- `HYPE-EMA-TB-V36`: Binance signal, Hyperliquid execution variant.

## Research Batch Notes

- `hype-5m-indicator-ensemble-search.md`: Binance HYPE perpetual 5m indicator-combination search over `2025-06-01` to `2026-06-01`. No single raw or refined strategy hit `20x annualized / >=80% win / >-20% DD`; a one-position ensemble of refined high-win-rate EMA/Bollinger reversion legs did hit the full-period target. Treat as a research candidate with material overfit risk, not a promoted live version.
- `ensemble-specs/README.md`: 将当前全部 `7` 个 `target_pass=True` 的 HYPE Binance `5m` one-position ensemble 组合写成中文实盘代码规格文档。每份文档都记录了指标公式、信号生成、开仓、持有、平仓、子腿参数，以及删除子腿、杠杆、单仓执行门槛三类消融实验。它们共享同一批精筛子腿，只是子腿数量和杠杆不同；仍应视为研究候选，而不是 promoted live version。

## Evidence Policy

Use family docs first, Cursor Canvas ledgers second, and archived scripts/code only for reproduction archaeology.
