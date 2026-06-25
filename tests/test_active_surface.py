from pathlib import Path


def test_strategy_platform_is_archived() -> None:
    package_dir = Path("src/strategy_lab")

    assert not (package_dir / "strategies").exists()
    assert not (package_dir / "workflow").exists()
    assert not (package_dir / "journal").exists()
    assert Path(
        "archive/code/platform/src/strategy_lab/strategies/candle_count_short/strategy.py"
    ).exists()
    assert Path(
        "archive/code/platform/src/strategy_lab/strategies/candle_count_short/intrabar_backtest.py"
    ).exists()
    assert Path(
        "archive/code/platform/src/strategy_lab/strategies/hype_ema_crossover_trend/strategy.py"
    ).exists()
    assert not Path("archive/code/platform/src/strategy_lab/workflow").exists()
    assert not Path("archive/code/platform/src/strategy_lab/journal").exists()
