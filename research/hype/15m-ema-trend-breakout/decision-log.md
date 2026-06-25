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

- Binance HYPE `5m` pullback/trailing-stop research has moved to the independent `HYPE-5M-PBTR` family under `../5m-pullback-trail/`. Do not use this `HYPE-EMA-TB` decision log as the source of truth for `HYPE-5M-PBTR-V1/V2`.

## Evidence Policy

Use family docs first. Archived Cursor indexes and archived scripts/code are only for migration evidence or reproduction archaeology.
