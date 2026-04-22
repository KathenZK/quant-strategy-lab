from pathlib import Path

from signal_lab.data import DataLakeLayout
from signal_lab.experiments import ExperimentRunner, load_experiment_config
from signal_lab.scenarios import seed_trend_mvp_data


def _write_app_config(tmp_path: Path) -> Path:
    app_config = tmp_path / "app.yaml"
    app_config.write_text(
        f"""
project:
  name: experiment-test
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


def test_experiment_runner_generates_report_and_manifest(tmp_path: Path) -> None:
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
        "trend_exp",
        "trend_confirmation",
        "    max_long_positions: 2\n    max_short_positions: 2",
    )
    crowding_workflow = _write_workflow(
        tmp_path / "crowding.yaml",
        "crowding_exp",
        "crowding_reversal",
        "    max_long_positions: 2\n    max_short_positions: 2",
    )
    experiment_config = tmp_path / "experiment.yaml"
    experiment_config.write_text(
        f"""
experiment:
  name: test_experiment
  workflow_configs:
    - {trend_workflow.name}
    - {crowding_workflow.name}
""".strip(),
        encoding="utf-8",
    )

    experiment = load_experiment_config(experiment_config)
    artifacts = ExperimentRunner(workspace_root=tmp_path, app_config_path=app_config).run(experiment)

    assert Path(artifacts.report_path).exists()
    assert Path(artifacts.manifest_path).exists()
    report = Path(artifacts.report_path).read_text(encoding="utf-8")
    manifest = Path(artifacts.manifest_path).read_text(encoding="utf-8")
    assert "trend_exp" in report
    assert "crowding_exp" in report
    assert "test_experiment" in manifest
    assert len(artifacts.entries) == 2
    assert artifacts.entries[0].backtest_attribution


def test_experiment_loader_supports_shared_batch_config(tmp_path: Path) -> None:
    trend_workflow = _write_workflow(
        tmp_path / "trend-batch.yaml",
        "trend_exp_batch",
        "trend_confirmation",
        "    max_long_positions: 2\n    max_short_positions: 2",
    )
    crowding_workflow = _write_workflow(
        tmp_path / "crowding-batch.yaml",
        "crowding_exp_batch",
        "crowding_reversal",
        "    max_long_positions: 2\n    max_short_positions: 2",
    )
    config_path = tmp_path / "experiment-shared-batch.yaml"
    config_path.write_text(
        f"""
batch:
  name: experiment_via_batch
  workflow_configs:
    - {trend_workflow.name}
    - {crowding_workflow.name}
""".strip(),
        encoding="utf-8",
    )

    config = load_experiment_config(config_path)

    assert config.name == "experiment_via_batch"
    assert len(config.workflow_configs) == 2
