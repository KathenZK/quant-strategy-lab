import pandas as pd

from strategy_lab.strategies.donchian_hold_72h.backtest import RiskLimits, RiskManager
from strategy_lab.strategies.donchian_hold_72h.paper import PaperBroker, PaperTradingSession


def test_paper_broker_rebalances_and_marks_equity() -> None:
    broker = PaperBroker(starting_cash=1_000.0, fee_bps=0.0, slippage_bps=0.0)
    ts = pd.Timestamp("2024-01-01T00:00:00Z")
    fills = broker.rebalance_to_weights(ts, pd.Series({"BTC/USDT": 0.5}), pd.Series({"BTC/USDT": 100.0}))
    snapshot = broker.snapshot(ts, pd.Series({"BTC/USDT": 100.0}))
    assert fills
    assert snapshot.equity == 1_000.0
    assert "BTC/USDT" in snapshot.positions


def test_paper_trading_session_runs_full_loop() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D", tz="UTC")
    target_weights = pd.DataFrame({"BTC/USDT": [0.5, 0.5, 0.0, 0.0]}, index=index)
    price_frame = pd.DataFrame({"BTC/USDT": [100.0, 101.0, 102.0, 103.0]}, index=index)
    funding = pd.DataFrame({"BTC/USDT": [0.0, 0.001, 0.0, 0.0]}, index=index)

    session = PaperTradingSession(
        broker=PaperBroker(starting_cash=1_000.0, fee_bps=0.0, slippage_bps=0.0),
        risk_manager=RiskManager(RiskLimits(max_abs_weight=1.0, max_gross_leverage=1.0)),
    )
    result = session.run(target_weights=target_weights, price_frame=price_frame, funding_rate=funding)
    assert len(result.snapshots) == len(index)
    assert len(result.fills) >= 1
    assert not result.equity_curve.empty
