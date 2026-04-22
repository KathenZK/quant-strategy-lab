from __future__ import annotations

import pandas as pd


def compute_backtest_attribution(
    *,
    weights: pd.DataFrame,
    price_frame: pd.DataFrame,
    funding_rate: pd.DataFrame | None,
    fee_bps: float,
    slippage_bps: float,
) -> dict[str, float | str | None]:
    executed = weights.shift(1).fillna(0.0)
    asset_returns = price_frame.pct_change().fillna(0.0)
    gross_contribution = executed * asset_returns
    contribution_by_symbol = gross_contribution.sum(axis=0).sort_values(ascending=False)

    turnover_by_symbol = weights.diff().abs().fillna(weights.abs()).sum(axis=0)
    trading_cost_by_symbol = turnover_by_symbol * ((fee_bps + slippage_bps) / 10_000.0)

    funding_cost_by_symbol = pd.Series(0.0, index=weights.columns)
    if funding_rate is not None:
        aligned_funding = funding_rate.reindex_like(price_frame).fillna(0.0)
        funding_cost_by_symbol = -(executed * aligned_funding).sum(axis=0)

    gross_exposure = weights.abs().sum(axis=1)
    net_exposure = weights.sum(axis=1)

    def _pick(series: pd.Series, *, descending: bool) -> tuple[str | None, float]:
        if series.empty:
            return None, 0.0
        ranked = series.sort_values(ascending=not descending)
        return str(ranked.index[0]), float(ranked.iloc[0])

    top_symbol, top_contribution = _pick(contribution_by_symbol, descending=True)
    worst_symbol, worst_contribution = _pick(contribution_by_symbol, descending=False)
    top_trading_symbol, top_trading_cost = _pick(trading_cost_by_symbol, descending=True)
    top_funding_symbol, top_funding_cost = _pick(funding_cost_by_symbol, descending=True)

    return {
        "gross_return_sum": float(gross_contribution.sum(axis=1).sum()),
        "trading_cost_sum": float(trading_cost_by_symbol.sum()),
        "funding_cost_sum": float(funding_cost_by_symbol.sum()),
        "active_period_ratio": float((gross_exposure > 0).mean()),
        "avg_gross_exposure": float(gross_exposure.mean()),
        "avg_net_exposure": float(net_exposure.mean()),
        "avg_long_count": float((weights > 0).sum(axis=1).mean()),
        "avg_short_count": float((weights < 0).sum(axis=1).mean()),
        "top_symbol": top_symbol,
        "top_symbol_contribution": top_contribution,
        "worst_symbol": worst_symbol,
        "worst_symbol_contribution": worst_contribution,
        "top_trading_cost_symbol": top_trading_symbol,
        "top_trading_cost": top_trading_cost,
        "top_funding_cost_symbol": top_funding_symbol,
        "top_funding_cost": top_funding_cost,
    }
