import pandas as pd

from strategy_lab.workflow import build_strategy_scan_result


def test_strategy_scanner_classifies_latest_weight_changes() -> None:
    index = pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC")
    signal = pd.DataFrame(
        {
            "BTC/USDT": [1.0, 1.2],
            "ETH/USDT": [0.8, 0.0],
            "SOL/USDT": [0.0, 1.1],
            "DOGE/USDT": [0.0, 0.9],
        },
        index=index,
    )
    weights = pd.DataFrame(
        {
            "BTC/USDT": [0.1, 0.1],
            "ETH/USDT": [0.1, 0.0],
            "SOL/USDT": [0.0, 0.1],
            "DOGE/USDT": [0.0, 0.0],
        },
        index=index,
    )
    prices = pd.DataFrame(
        {
            "BTC/USDT": [100.0, 101.0],
            "ETH/USDT": [50.0, 49.0],
            "SOL/USDT": [20.0, 21.0],
            "DOGE/USDT": [0.1, 0.11],
        },
        index=index,
    )

    scan = build_strategy_scan_result(
        signal_frame=signal,
        target_weights=weights,
        price_frame=prices,
        top_n=5,
    )

    assert [item.symbol for item in scan.by_action("sell")] == ["ETH/USDT"]
    assert [item.symbol for item in scan.by_action("buy")] == ["SOL/USDT"]
    assert [item.symbol for item in scan.by_action("hold")] == ["BTC/USDT"]
    assert [item.symbol for item in scan.watchlist] == ["DOGE/USDT"]
    assert scan.by_action("buy")[0].price == 21.0
