from pathlib import Path

from signal_lab.comparison import StrategyComparisonRunner, load_strategy_comparison
from signal_lab.data import DataLakeLayout, DuckDBWarehouse
from signal_lab.experiments import ExperimentRunner, RunRegistry, load_experiment_config
from signal_lab.factors import default_registry
from signal_lab.features import FeatureBuilder, FeatureStore
from signal_lab.orchestration import StrategyRunner, load_strategy_workflow
from signal_lab.scenarios import seed_trend_mvp_data


def _write_app_config(tmp_path: Path) -> Path:
    app_config = tmp_path / "app.yaml"
    app_config.write_text(
        f"""
project:
  name: registry-test
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


def _write_workflow(path: Path, name: str, strategy_type: str, strategy_params: str) -> Path:
    path.write_text(
        f"""
strategy:
  name: {name}
  strategy_type: {strategy_type}
  exchange: binance
  market_type: perp
  symbols: [BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT]
  strategy_params:
{strategy_params}
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


def test_run_registry_indexes_workflow_experiment_and_comparison_runs(tmp_path: Path) -> None:
    layout = DataLakeLayout(
        root_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        normalized_dir=tmp_path / "data" / "normalized",
        features_dir=tmp_path / "data" / "features",
        reports_dir=tmp_path / "reports",
    )
    seed_trend_mvp_data(layout)

    app_config = _write_app_config(tmp_path)
    workflow_for_direct_run = _write_workflow(
        tmp_path / "trend-registry.yaml",
        "trend_registry",
        "trend_confirmation",
        "    max_long_positions: 2\n    max_short_positions: 2",
    )
    trend_workflow = _write_workflow(
        tmp_path / "trend-exp.yaml",
        "trend_exp_registry",
        "trend_confirmation",
        "    max_long_positions: 2\n    max_short_positions: 2",
    )
    crowding_workflow = _write_workflow(
        tmp_path / "crowding-exp.yaml",
        "crowding_exp_registry",
        "crowding_reversal",
        "    max_long_positions: 2\n    max_short_positions: 2",
    )

    builder = FeatureBuilder(
        warehouse=DuckDBWarehouse(layout),
        store=FeatureStore(layout),
        registry=default_registry(),
    )
    direct_workflow = load_strategy_workflow(workflow_for_direct_run)
    StrategyRunner(layout=layout, builder=builder).run(direct_workflow)

    experiment_config = tmp_path / "experiment.yaml"
    experiment_config.write_text(
        f"""
experiment:
  name: registry_experiment
  workflow_configs:
    - {trend_workflow.name}
    - {crowding_workflow.name}
""".strip(),
        encoding="utf-8",
    )
    ExperimentRunner(workspace_root=tmp_path, app_config_path=app_config).run(
        load_experiment_config(experiment_config)
    )

    comparison_config = tmp_path / "comparison.yaml"
    comparison_config.write_text(
        f"""
comparison:
  name: registry_comparison
  workflow_configs:
    - {trend_workflow.name}
    - {crowding_workflow.name}
""".strip(),
        encoding="utf-8",
    )
    StrategyComparisonRunner(workspace_root=tmp_path, app_config_path=app_config).compare(
        load_strategy_comparison(comparison_config)
    )

    registry = RunRegistry(layout.reports_dir)
    records = registry.load()
    kinds = {item["kind"] for item in records}

    assert {"workflow_run", "experiment_run", "comparison_run"} <= kinds
    assert any(item["kind"] == "workflow_run" and item["name"] == "trend_registry" for item in records)

    experiment_records = [item for item in records if item["kind"] == "experiment_run" and item["name"] == "registry_experiment"]
    assert len(experiment_records) == 1
    assert len(experiment_records[0]["child_manifest_paths"]) == 2

    comparison_records = [item for item in records if item["kind"] == "comparison_run" and item["name"] == "registry_comparison"]
    assert len(comparison_records) == 1
    assert len(comparison_records[0]["child_manifest_paths"]) == 2
