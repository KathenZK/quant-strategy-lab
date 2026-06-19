import pandas as pd

from strategy_lab.data.execution import (
    CrossSectionalBacktester,
    ExecutionAssumptions,
    PortfolioBacktester,
    RiskLimits,
)
from strategy_lab.data.execution.backtest import _periods_per_year


def _frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    index = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    price_frame = pd.DataFrame(
        {
            "BTC/USDT": [100.0, 101.0, 103.0, 102.0, 104.0],
            "ETH/USDT": [50.0, 49.0, 50.0, 51.0, 52.0],
        },
        index=index,
    )
    target_weights = pd.DataFrame(
        {
            "BTC/USDT": [0.5, 0.5, 0.5, 0.5, 0.5],
            "ETH/USDT": [-0.5, -0.5, -0.5, -0.5, -0.5],
        },
        index=index,
    )
    dollar_volume = pd.DataFrame({"BTC/USDT": [1_000_000] * 5, "ETH/USDT": [1_000_000] * 5}, index=index)
    funding = pd.DataFrame({"BTC/USDT": [0.0] * 5, "ETH/USDT": [0.001] * 5}, index=index)
    return price_frame, target_weights, dollar_volume, funding


def test_portfolio_backtester_charges_trading_and_funding_costs() -> None:
    price_frame, target_weights, dollar_volume, funding = _frames()
    result = PortfolioBacktester(
        assumptions=ExecutionAssumptions(fee_bps=10.0, slippage_bps=0.0),
        risk_limits=RiskLimits(max_abs_weight=0.6, max_gross_leverage=1.0),
    ).run(
        target_weights=target_weights,
        price_frame=price_frame,
        dollar_volume=dollar_volume,
        funding_rate=funding,
    )
    assert result.trading_costs.iloc[0] > 0
    assert result.funding_costs.iloc[1] != 0
    assert "sharpe" in result.metrics


def test_cross_sectional_backtester_builds_weights_from_factor_panel() -> None:
    price_frame, _, dollar_volume, _ = _frames()
    factor_frame = pd.DataFrame(
        {
            "BTC/USDT": [1.0, 2.0, 3.0, 1.0, 2.0],
            "ETH/USDT": [0.0, -1.0, -2.0, 0.5, -0.5],
        },
        index=price_frame.index,
    )
    result = CrossSectionalBacktester(risk_limits=RiskLimits(max_abs_weight=1.0)).run(
        factor_frame=factor_frame,
        price_frame=price_frame,
        dollar_volume=dollar_volume,
    )
    assert len(result.equity_curve) == len(price_frame)
    assert not result.weights.empty


def test_periods_per_year_uses_crypto_calendar_for_hourly_data() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    assert _periods_per_year(index) == 24 * 365
