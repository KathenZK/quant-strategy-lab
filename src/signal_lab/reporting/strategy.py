from __future__ import annotations

from signal_lab.backtest.models import BacktestResult
from signal_lab.execution.session import PaperTradingResult


def render_backtest_report(name: str, result: BacktestResult) -> str:
    metrics_lines = "\n".join(f"- `{key}`: {value:.4f}" for key, value in result.metrics.items())
    tail = result.equity_curve.tail(5).round(6).to_string()
    return f"""# Backtest Report: {name}

## Metrics
{metrics_lines}

## Equity Tail
```text
{tail}
```
"""


def render_paper_trading_report(name: str, result: PaperTradingResult) -> str:
    last_equity = float(result.equity_curve.iloc[-1]) if not result.equity_curve.empty else 0.0
    funding = float(result.funding_cashflows.sum()) if not result.funding_cashflows.empty else 0.0
    return f"""# Paper Trading Report: {name}

## Summary
- Final Equity: {last_equity:.4f}
- Fill Count: {len(result.fills)}
- Funding Cashflow: {funding:.4f}
"""
