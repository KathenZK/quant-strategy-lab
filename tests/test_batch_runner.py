from pathlib import Path

import strategy_lab.batches.runner as batch_runner_module

from strategy_lab.batches import WorkflowBatchRunner
from strategy_lab.data import DataLakeLayout
from strategy_lab.orchestration import StrategyRunner
from market_data_fixtures import seed_real_binance_perp_ohlcv_sample


def _write_app_config(tmp_path: Path) -> Path:
    app_config = tmp_path / "app.yaml"
    app_config.write_text(
        f"""
project:
  name: batch-runner-test
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
  enabled: true
workflow:
  run_factor_report: false
  run_backtest: true
  run_paper_trade: false
""".strip(),
        encoding="utf-8",
    )
    return path


def test_workflow_batch_runner_uses_shared_refresh_once(tmp_path: Path, monkeypatch) -> None:
    layout = DataLakeLayout(
        root_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        normalized_dir=tmp_path / "data" / "normalized",
        features_dir=tmp_path / "data" / "features",
        reports_dir=tmp_path / "reports",
    )
    seed_real_binance_perp_ohlcv_sample(layout)

    app_config = _write_app_config(tmp_path)
    trend_workflow = _write_workflow(tmp_path / "trend.yaml", "trend_batch_runner", "ret_1")
    crowding_workflow = _write_workflow(tmp_path / "crowding.yaml", "crowding_batch_runner", "ret_4")

    batch_runner = WorkflowBatchRunner(workspace_root=tmp_path, app_config_path=app_config)
    runner = batch_runner.create_strategy_runner()
    workflows = batch_runner.load_workflows([str(trend_workflow), str(crowding_workflow)])

    refresh_flags: list[bool] = []

    def fake_refresh(self, config):
        refresh_flags.append(config.refresh.enabled)
        return {}

    monkeypatch.setattr(StrategyRunner, "refresh_data", fake_refresh)
    entries = batch_runner.collect_entries_from_workflows(
        workflows,
        runner=runner,
        shared_refresh=True,
    )

    assert len(entries) == 2
    assert refresh_flags.count(True) == 1
    assert refresh_flags.count(False) == 2
    assert all(entry.backtest_metrics for entry in entries)


def test_workflow_batch_runner_falls_back_to_serial_when_refresh_is_enabled(tmp_path: Path, monkeypatch) -> None:
    layout = DataLakeLayout(
        root_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        normalized_dir=tmp_path / "data" / "normalized",
        features_dir=tmp_path / "data" / "features",
        reports_dir=tmp_path / "reports",
    )
    seed_real_binance_perp_ohlcv_sample(layout)

    app_config = _write_app_config(tmp_path)
    trend_workflow = _write_workflow(tmp_path / "trend-parallel.yaml", "trend_parallel_guard", "ret_1")
    crowding_workflow = _write_workflow(tmp_path / "crowding-parallel.yaml", "crowding_parallel_guard", "ret_4")

    batch_runner = WorkflowBatchRunner(workspace_root=tmp_path, app_config_path=app_config)
    runner = batch_runner.create_strategy_runner()
    workflows = batch_runner.load_workflows([str(trend_workflow), str(crowding_workflow)])

    def fail_parallel(*args, **kwargs):
        raise AssertionError("parallel worker path should not run when refresh is enabled")

    def fake_refresh(self, config):
        return {}

    monkeypatch.setattr(batch_runner_module, "_run_workflow_entry", fail_parallel)
    monkeypatch.setattr(StrategyRunner, "refresh_data", fake_refresh)
    entries = batch_runner.collect_entries_from_workflows(
        workflows,
        runner=runner,
        max_workers=2,
    )

    assert len(entries) == 2
    assert all(entry.backtest_metrics for entry in entries)
