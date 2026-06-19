from pathlib import Path

import pandas as pd

from strategy_lab.strategies import create_strategy, list_strategies


def test_legacy_strategies_are_directory_packages_not_flat_modules() -> None:
    strategies_dir = Path(__file__).resolve().parents[1] / "src" / "strategy_lab" / "strategies"
    allowed_top_level = {"__init__.py", "base.py", "common.py", "factory.py", "registry.py"}
    flat_modules = {path.name for path in strategies_dir.glob("*.py")} - allowed_top_level

    assert flat_modules == set()


def test_strategy_lab_top_level_is_minimal_after_refactor() -> None:
    package_dir = Path(__file__).resolve().parents[1] / "src" / "strategy_lab"
    allowed_dirs = {"data", "journal", "strategies", "workflow"}
    top_level_dirs = {path.name for path in package_dir.iterdir() if path.is_dir() and path.name != "__pycache__"}

    assert top_level_dirs == allowed_dirs


def test_each_strategy_package_only_holds_strategy_intent() -> None:
    strategies_dir = Path(__file__).resolve().parents[1] / "src" / "strategy_lab" / "strategies"
    infrastructure_dirs = {"__pycache__"}
    strategy_dirs = [
        path
        for path in strategies_dir.iterdir()
        if path.is_dir() and path.name not in infrastructure_dirs and not path.name.startswith(".")
    ]

    assert strategy_dirs
    forbidden = {"backtest.py", "paper.py", "factors.py", "portfolio_base.py", "portfolio_common.py", "signal_common.py"}
    for strategy_dir in strategy_dirs:
        present = {path.name for path in strategy_dir.iterdir() if path.is_file()}
        assert "strategy.py" in present, f"{strategy_dir.name} missing strategy.py"
        leaked = present & forbidden
        assert not leaked, f"{strategy_dir.name} still ships shared infra: {sorted(leaked)}"


def test_shared_execution_lives_under_data_layer() -> None:
    package_dir = Path(__file__).resolve().parents[1] / "src" / "strategy_lab"

    assert (package_dir / "data" / "execution" / "backtest.py").exists()
    assert (package_dir / "data" / "execution" / "paper.py").exists()
    assert not (package_dir / "journal" / "engine").exists()
    assert not (package_dir / "workflow.py").exists()


def test_strategy_registry_discovers_isolated_spot_cta_strategies() -> None:
    strategy_types = set(list_strategies())

    assert {"donchian_hold_72h", "spot_trend"} <= strategy_types
    assert "spot_cta_pump" not in strategy_types


def test_donchian_hold_72h_builds_fixed_hold_weights_without_shared_allocator() -> None:
    strategy = create_strategy(
        "donchian_hold_72h",
        {"breakout_factor": "donchian_breakout_20", "hold_bars": 2, "max_positions": 1, "long_allocation": 1.0},
    )
    index = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    breakout = pd.DataFrame(
        {
            "AAA/USDT": [1.0, 0.0, 0.0, 0.0],
            "BBB/USDT": [0.0, 1.0, 0.0, 0.0],
        },
        index=index,
    )

    signal = strategy.build_signal_frame({"donchian_breakout_20": breakout})
    weights = strategy.build_weights(signal)

    assert list(weights["AAA/USDT"]) == [1.0, 1.0, 0.0, 0.0]
    assert list(weights["BBB/USDT"]) == [0.0, 0.0, 0.0, 0.0]
