from pathlib import Path

from signal_lab.comparison import StrategyComparisonRunner, load_strategy_comparison
from signal_lab.data import DataLakeLayout
from signal_lab.scenarios import seed_trend_mvp_data


def _write_app_config(tmp_path: Path) -> Path:
    app_config = tmp_path / "app.yaml"
    app_config.write_text(
        f"""
project:
  name: comparison-test
  timezone: UTC

storage:
  root_dir: {tmp_path / 'data'}
  raw_dir: {tmp_path / 'data' / 'raw'}
  normalized_dir: {tmp_path / 'data' / 'normalized'}
  features_dir: {tmp_path / 'data' / 'features'}
  reports_dir: {tmp_path / 'reports'}
""".strip(),
        encoding="utf-8",
    )
    return app_config


def _write_workflow(path: Path, name: str, signal_type: str, strategy_options: str) -> Path:
    path.write_text(
        f"""
strategy:
  name: {name}
  signal_type: {signal_type}
  exchange: binance
  market_type: perp
  symbols: [BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT]
  strategy_options:
{strategy_options}
refresh:
  enabled: false
workflow:
  run_factor_report: false
  run_backtest: true
  run_paper_trade: false
""".strip(),
        encoding="utf-8",
    )
    return path


def test_strategy_comparison_runner_generates_report(tmp_path: Path) -> None:
    layout = DataLakeLayout(
        root_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        normalized_dir=tmp_path / "data" / "normalized",
        features_dir=tmp_path / "data" / "features",
        reports_dir=tmp_path / "reports",
    )
    seed_trend_mvp_data(layout)

    app_config = _write_app_config(tmp_path)
    trend_workflow = _write_workflow(
        tmp_path / "trend.yaml",
        "trend_cmp",
        "trend_confirmation",
        "    max_long_positions: 2\n    max_short_positions: 2",
    )
    crowding_workflow = _write_workflow(
        tmp_path / "crowding.yaml",
        "crowding_cmp",
        "crowding_reversal",
        "    max_long_positions: 2\n    max_short_positions: 2",
    )
    comparison_config = tmp_path / "comparison.yaml"
    comparison_config.write_text(
        f"""
comparison:
  name: test_comparison
  workflow_configs:
    - {trend_workflow.name}
    - {crowding_workflow.name}
""".strip(),
        encoding="utf-8",
    )

    comparison = load_strategy_comparison(comparison_config)
    artifacts = StrategyComparisonRunner(workspace_root=tmp_path, app_config_path=app_config).compare(comparison)

    assert Path(artifacts.report_path).exists()
    assert Path(artifacts.manifest_path).exists()
    content = Path(artifacts.report_path).read_text(encoding="utf-8")
    assert "trend_cmp" in content
    assert "crowding_cmp" in content
