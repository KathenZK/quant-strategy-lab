import pandas as pd

from strategy_lab.cli import _with_cli_local_universe
from strategy_lab.data import MarketType
from strategy_lab.workflow import StrategyWorkflowConfig, StrategyWorkflowSpec, WorkflowService


class FakeWarehouse:
    def load_dataset(self, **kwargs):
        assert kwargs["timeframe"] == "1h"
        index = pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC")
        return pd.DataFrame(
            {
                "ts": list(index) * 3,
                "symbol": ["BTC/USDT"] * 5 + ["ACH/USDT"] * 5 + ["THIN/USDT"] * 5,
                "close": [100.0] * 5 + [1.0] * 5 + [1.0] * 5,
                "volume": [20_000.0] * 5 + [2_000_000.0] * 5 + [10.0] * 5,
            }
        )


class FakeBuilder:
    warehouse = FakeWarehouse()


def test_cli_local_universe_options_resolve_in_workflow_service() -> None:
    workflow = StrategyWorkflowConfig(
        strategy=StrategyWorkflowSpec(
            name="spot_cta_test",
            exchange="binance",
            market_type=MarketType.SPOT,
            symbols=["ETH/USDT"],
            benchmark_symbol="BTC/USDT",
            strategy_type="spot_cta_trend",
        ),
    )

    configured = _with_cli_local_universe(
        workflow,
        min_avg_dollar_volume=1_000.0,
        min_history_bars=5,
        max_symbols=1,
    )
    updated = WorkflowService(FakeBuilder()).with_resolved_symbols(configured)

    assert updated.strategy.symbols == ["BTC/USDT", "ACH/USDT"]
    assert workflow.strategy.symbols == ["ETH/USDT"]
