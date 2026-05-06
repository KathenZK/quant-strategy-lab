import pandas as pd

from strategy_lab.journal.research import FactorResearchLab, factor_correlation_matrix


def _price_and_factor_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    index = pd.date_range("2024-01-01", periods=8, freq="D", tz="UTC")
    price_frame = pd.DataFrame(
        {
            "BTC/USDT": [100, 102, 104, 106, 108, 110, 112, 114],
            "ETH/USDT": [50, 50.5, 51, 52, 53, 53.5, 54, 55],
            "SOL/USDT": [20, 19.5, 20.5, 21, 22, 22.5, 23, 24],
        },
        index=index,
    )
    factor_frame = price_frame.pct_change().fillna(0.0)
    return price_frame, factor_frame


def test_factor_research_lab_returns_decay_and_walk_forward() -> None:
    price_frame, factor_frame = _price_and_factor_frames()
    diagnostics = FactorResearchLab(quantiles=3, horizons=(1, 2, 3), walk_forward_window=4, walk_forward_step=2).evaluate(
        factor_frame,
        price_frame,
    )
    assert not diagnostics.decay.empty
    assert "h1" in diagnostics.decay.index
    assert not diagnostics.walk_forward.empty


def test_factor_correlation_matrix_compares_factor_panels() -> None:
    _, factor_frame = _price_and_factor_frames()
    matrix = factor_correlation_matrix({"momentum": factor_frame, "reversion": -factor_frame})
    assert list(matrix.columns) == ["momentum", "reversion"]
    assert matrix.loc["momentum", "reversion"] < 0
