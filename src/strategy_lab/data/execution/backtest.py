from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class ExecutionAssumptions:
    fee_bps: float = 5.0
    slippage_bps: float = 2.0
    starting_cash: float = 100_000.0


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_abs_weight: float = 0.20
    max_gross_leverage: float = 1.0
    max_net_exposure: float = 1.0
    min_dollar_volume: float = 0.0
    max_funding_rate_abs: float | None = None
    max_drawdown: float | None = None


@dataclass(slots=True)
class RiskManager:
    limits: RiskLimits

    def apply_weights(
        self,
        weights: pd.Series,
        *,
        dollar_volume_row: pd.Series | None = None,
        funding_rate_row: pd.Series | None = None,
        current_drawdown: float | None = None,
    ) -> pd.Series:
        constrained = weights.fillna(0.0).astype(float).copy()

        if current_drawdown is not None and self.limits.max_drawdown is not None and current_drawdown <= -abs(self.limits.max_drawdown):
            return pd.Series(0.0, index=constrained.index, name=weights.name)

        constrained = constrained.clip(lower=-self.limits.max_abs_weight, upper=self.limits.max_abs_weight)

        if dollar_volume_row is not None:
            aligned_volume = dollar_volume_row.reindex(constrained.index).fillna(0.0)
            constrained[aligned_volume < self.limits.min_dollar_volume] = 0.0

        if funding_rate_row is not None and self.limits.max_funding_rate_abs is not None:
            aligned_funding = funding_rate_row.reindex(constrained.index).fillna(0.0).abs()
            constrained[aligned_funding > self.limits.max_funding_rate_abs] = 0.0

        gross = constrained.abs().sum()
        if gross > self.limits.max_gross_leverage and gross > 0:
            constrained *= self.limits.max_gross_leverage / gross

        net = constrained.sum()
        if abs(net) > self.limits.max_net_exposure and net != 0:
            target_net = self.limits.max_net_exposure * (1 if net > 0 else -1)
            constrained -= (net - target_net) / len(constrained)
            gross = constrained.abs().sum()
            if gross > self.limits.max_gross_leverage and gross > 0:
                constrained *= self.limits.max_gross_leverage / gross
        return constrained.rename(weights.name)


@dataclass(slots=True)
class BacktestResult:
    equity_curve: pd.Series
    period_returns: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    trading_costs: pd.Series
    funding_costs: pd.Series
    metrics: dict[str, float] = field(default_factory=dict)


def _max_drawdown(equity_curve: pd.Series) -> float:
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1.0
    return float(drawdown.min())


def _periods_per_year(index: pd.Index) -> float:
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 2:
        return 252.0
    deltas = index.to_series().diff().dropna()
    if deltas.empty:
        return 252.0
    seconds = deltas.dt.total_seconds().median()
    if pd.isna(seconds) or seconds <= 0:
        return 252.0
    return float((365.0 * 24.0 * 60.0 * 60.0) / seconds)


def _result_metrics(period_returns: pd.Series, equity_curve: pd.Series, turnover: pd.Series) -> dict[str, float]:
    periods_per_year = _periods_per_year(period_returns.index)
    mean_return = float(period_returns.mean())
    volatility = float(period_returns.std(ddof=0))
    downside = period_returns[period_returns < 0]
    downside_vol = float(downside.std(ddof=0)) if not downside.empty else 0.0
    sharpe = 0.0 if volatility == 0 else mean_return / volatility * np.sqrt(periods_per_year)
    sortino = 0.0 if downside_vol == 0 else mean_return / downside_vol * np.sqrt(periods_per_year)
    max_dd = _max_drawdown(equity_curve)
    annualized_return = (
        float((equity_curve.iloc[-1] ** (periods_per_year / max(len(equity_curve), 1))) - 1.0)
        if not equity_curve.empty
        else 0.0
    )
    calmar = 0.0 if max_dd == 0 else annualized_return / abs(max_dd)
    return {
        "cumulative_return": float(equity_curve.iloc[-1] - 1.0) if not equity_curve.empty else 0.0,
        "annualized_return": annualized_return,
        "volatility": volatility * np.sqrt(periods_per_year),
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "avg_turnover": float(turnover.mean()) if not turnover.empty else 0.0,
    }


@dataclass(slots=True)
class PortfolioBacktester:
    assumptions: ExecutionAssumptions = ExecutionAssumptions()
    risk_limits: RiskLimits = RiskLimits()
    risk_manager: RiskManager = field(init=False)

    def __post_init__(self) -> None:
        self.risk_manager = RiskManager(self.risk_limits)

    def run(
        self,
        *,
        target_weights: pd.DataFrame,
        price_frame: pd.DataFrame,
        dollar_volume: pd.DataFrame | None = None,
        funding_rate: pd.DataFrame | None = None,
    ) -> BacktestResult:
        weights = target_weights.reindex_like(price_frame).fillna(0.0)
        constrained_rows = []
        for ts in weights.index:
            constrained = self.risk_manager.apply_weights(
                weights.loc[ts],
                dollar_volume_row=None if dollar_volume is None else dollar_volume.loc[ts],
                funding_rate_row=None if funding_rate is None else funding_rate.loc[ts],
            )
            constrained_rows.append(constrained.rename(ts))
        constrained_weights = pd.DataFrame(constrained_rows).reindex_like(weights).fillna(0.0)

        executed_weights = constrained_weights.shift(1).fillna(0.0)
        asset_returns = price_frame.pct_change().fillna(0.0)
        previous_weights = constrained_weights.shift(1).fillna(0.0)
        turnover = (constrained_weights - previous_weights).abs().sum(axis=1)
        cost_rate = (self.assumptions.fee_bps + self.assumptions.slippage_bps) / 10_000.0
        trading_costs = turnover * cost_rate

        funding_costs = pd.Series(0.0, index=price_frame.index, name="funding_costs")
        if funding_rate is not None:
            aligned = funding_rate.reindex_like(price_frame).fillna(0.0)
            funding_costs = (executed_weights * aligned).sum(axis=1) * -1.0
            funding_costs.name = "funding_costs"

        gross_returns = (executed_weights * asset_returns).sum(axis=1)
        period_returns = gross_returns - trading_costs - funding_costs
        equity_curve = (1.0 + period_returns).cumprod()
        equity_curve.name = "equity"

        return BacktestResult(
            equity_curve=equity_curve,
            period_returns=period_returns.rename("returns"),
            weights=constrained_weights,
            turnover=turnover.rename("turnover"),
            trading_costs=trading_costs.rename("trading_costs"),
            funding_costs=funding_costs,
            metrics=_result_metrics(period_returns, equity_curve, turnover),
        )


@dataclass(slots=True)
class CrossSectionalBacktester:
    assumptions: ExecutionAssumptions = ExecutionAssumptions()
    risk_limits: RiskLimits = RiskLimits()
    long_quantile: float = 0.8
    short_quantile: float = 0.2
    market_neutral: bool = True

    def build_weights(self, factor_frame: pd.DataFrame) -> pd.DataFrame:
        weights = pd.DataFrame(0.0, index=factor_frame.index, columns=factor_frame.columns)
        for ts in factor_frame.index:
            row = factor_frame.loc[ts].dropna()
            if row.empty:
                continue
            long_cutoff = row.quantile(self.long_quantile)
            short_cutoff = row.quantile(self.short_quantile)
            longs = row[row >= long_cutoff].index.tolist()
            shorts = row[row <= short_cutoff].index.tolist()

            if longs:
                weights.loc[ts, longs] = 1.0 / len(longs)
            if shorts:
                short_weight = -1.0 / len(shorts)
                weights.loc[ts, shorts] = short_weight

            if not self.market_neutral and longs:
                weights.loc[ts, shorts] = 0.0
                weights.loc[ts, longs] = 1.0 / len(longs)
        return weights

    def run(
        self,
        *,
        factor_frame: pd.DataFrame,
        price_frame: pd.DataFrame,
        dollar_volume: pd.DataFrame | None = None,
        funding_rate: pd.DataFrame | None = None,
    ) -> BacktestResult:
        weights = self.build_weights(factor_frame)
        backtester = PortfolioBacktester(assumptions=self.assumptions, risk_limits=self.risk_limits)
        return backtester.run(
            target_weights=weights,
            price_frame=price_frame,
            dollar_volume=dollar_volume,
            funding_rate=funding_rate,
        )


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
