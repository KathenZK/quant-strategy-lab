from pathlib import Path

from strategy_lab.batches import BatchRunMode
from strategy_lab.batches.service import load_batch_for_mode, run_workflow_batch
from strategy_lab.data import DataLakeLayout
from strategy_lab.scenarios import seed_trend_mvp_data


def _write_app_config(tmp_path: Path) -> Path:
    app_config = tmp_path / "app.yaml"
    app_config.write_text(
        f"""
project:
  name: batch-service-test
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


def test_run_workflow_batch_dispatches_experiment_and_comparison(tmp_path: Path) -> None:
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
        "trend_batch_service",
        "trend_confirmation",
        "    max_long_positions: 2\n    max_short_positions: 2",
    )
    crowding_workflow = _write_workflow(
        tmp_path / "crowding.yaml",
        "crowding_batch_service",
        "crowding_reversal",
        "    max_long_positions: 2\n    max_short_positions: 2",
    )
    batch_config_path = tmp_path / "batch.yaml"
    batch_config_path.write_text(
        f"""
batch:
  name: batch_service_demo
  workflow_configs:
    - {trend_workflow.name}
    - {crowding_workflow.name}
""".strip(),
        encoding="utf-8",
    )

    experiment_batch = load_batch_for_mode(batch_config_path, BatchRunMode.EXPERIMENT)
    experiment_artifacts = run_workflow_batch(
        BatchRunMode.EXPERIMENT,
        experiment_batch,
        workspace_root=tmp_path,
        app_config_path=app_config,
    )

    comparison_batch = load_batch_for_mode(batch_config_path, BatchRunMode.COMPARISON)
    comparison_artifacts = run_workflow_batch(
        BatchRunMode.COMPARISON,
        comparison_batch,
        workspace_root=tmp_path,
        app_config_path=app_config,
    )

    assert Path(experiment_artifacts.report_path).exists()
    assert Path(experiment_artifacts.manifest_path).exists()
    assert Path(comparison_artifacts.report_path).exists()
    assert Path(comparison_artifacts.manifest_path).exists()
