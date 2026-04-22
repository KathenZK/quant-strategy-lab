from __future__ import annotations

import pandas as pd

from signal_lab.research.lab import FactorDiagnostics


def _series_to_bullets(series: pd.Series, *, precision: int = 4) -> str:
    lines = []
    for index, value in series.items():
        lines.append(f"- `{index}`: {value:.{precision}f}")
    return "\n".join(lines)


def render_factor_report(name: str, diagnostics: FactorDiagnostics) -> str:
    summary = diagnostics.summary
    quantile_table = diagnostics.quantile_returns.round(6).to_string() if not diagnostics.quantile_returns.empty else "No quantile returns available."
    if diagnostics.walk_forward.empty:
        walk_forward = "No walk-forward windows available."
    else:
        walk_forward_frame = diagnostics.walk_forward.copy()
        numeric_columns = walk_forward_frame.select_dtypes(include="number").columns
        walk_forward_frame[numeric_columns] = walk_forward_frame[numeric_columns].round(6)
        walk_forward = walk_forward_frame.to_string(index=False)
    turnover_mean = float(diagnostics.turnover.mean()) if not diagnostics.turnover.empty else 0.0
    return f"""# Factor Report: {name}

## Summary
- Mean Rank IC: {summary.mean_rank_ic:.4f}
- Positive Rank IC Ratio: {summary.positive_rank_ic_ratio:.4f}
- Top Minus Bottom Mean Return: {summary.top_minus_bottom_mean:.4f}
- Mean Quantile Turnover: {turnover_mean:.4f}

## Decay
{_series_to_bullets(diagnostics.decay)}

## Quantile Returns
{quantile_table}

## Walk Forward
{walk_forward}
"""
