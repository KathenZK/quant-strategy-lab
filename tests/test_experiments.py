from pathlib import Path
import json

from strategy_lab.batches.models import WorkflowBatchEntry
from strategy_lab.data import DataLakeLayout
from strategy_lab.experiments import ExperimentRunner, load_experiment_config
from strategy_lab.experiments.runner import _pick_winner
from strategy_lab.reporting.experiments import render_experiment_report
from market_data_fixtures import seed_real_binance_perp_ohlcv_sample


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


def _write_workflow(path: Path, name: str, factor_name: str) -> Path:
    path.write_text(
        f"""
strategy:
  name: {name}
  strategy_type: factor
  factor_name: {factor_name}
  exchange: binance
  market_type: perp
  symbols: [BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT]
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


def _write_factor_workflow(path: Path, name: str, factor: str) -> Path:
    path.write_text(
        f"""
strategy:
  name: {name}
  strategy_type: factor
  factor_name: {factor}
  exchange: binance
  market_type: perp
  symbols: [BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT]
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
    seed_real_binance_perp_ohlcv_sample(layout)

    app_config = _write_app_config(tmp_path)
    trend_workflow = _write_workflow(
        tmp_path / "trend.yaml",
        "trend_exp",
        "ret_1",
    )
    crowding_workflow = _write_workflow(
        tmp_path / "crowding.yaml",
        "crowding_exp",
        "ret_4",
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
        "ret_1",
    )
    crowding_workflow = _write_workflow(
        tmp_path / "crowding-batch.yaml",
        "crowding_exp_batch",
        "ret_4",
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


def test_experiment_runner_supports_sweep_variants_and_structured_artifacts(tmp_path: Path) -> None:
    layout = DataLakeLayout(
        root_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        normalized_dir=tmp_path / "data" / "normalized",
        features_dir=tmp_path / "data" / "features",
        reports_dir=tmp_path / "reports",
    )
    seed_real_binance_perp_ohlcv_sample(layout)

    app_config = _write_app_config(tmp_path)
    base_workflow = _write_factor_workflow(tmp_path / "factor-base.yaml", "factor_probe", "ret_1")
    experiment_config = tmp_path / "factor-sweep.yaml"
    experiment_config.write_text(
        f"""
experiment:
  name: factor_sweep
  base_workflow: {base_workflow.name}
  max_workers: 2
  objective:
    metric: sharpe
    direction: max
  sweep:
    strategy.factor_name: [ret_1, ret_4]
""".strip(),
        encoding="utf-8",
    )

    experiment = load_experiment_config(experiment_config)
    artifacts = ExperimentRunner(workspace_root=tmp_path, app_config_path=app_config).run(experiment)

    assert len(artifacts.entries) == 2
    assert artifacts.winner is not None
    assert {entry.variant_id for entry in artifacts.entries} == {"factor_ret_1", "factor_ret_4"}
    manifest = json.loads(Path(artifacts.manifest_path).read_text(encoding="utf-8"))
    assert manifest["winner"]
    for entry in artifacts.entries:
        assert entry.structured_artifact_paths["prices"]
        assert entry.structured_artifact_paths["signals"]
        assert entry.structured_artifact_paths["weights"]
        assert entry.structured_artifact_paths["trades"]
        assert Path(entry.structured_artifact_paths["equity_curve"]).exists()


def test_experiment_report_keeps_missing_metrics_at_bottom_for_min_objective() -> None:
    complete = WorkflowBatchEntry(
        workflow_name="has_metric",
        strategy_name="has_metric",
        signal_name="ret_1",
        strategy_type="factor",
        signal_version="v1",
        run_id="run-complete",
        backtest_metrics={"max_drawdown": 0.12},
    )
    missing = WorkflowBatchEntry(
        workflow_name="missing_metric",
        strategy_name="missing_metric",
        signal_name="ret_4",
        strategy_type="factor",
        signal_version="v1",
        run_id="run-missing",
        backtest_metrics={},
    )

    winner = _pick_winner([missing, complete], "max_drawdown", "min")
    report = render_experiment_report(
        "drawdown_min",
        [missing, complete],
        objective_metric="max_drawdown",
        objective_direction="min",
        winner=winner,
    )

    assert winner is complete
    assert report.index("## has_metric") < report.index("## missing_metric")
