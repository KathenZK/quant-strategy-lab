from pathlib import Path
import json

from strategy_lab.comparison import StrategyComparisonRunner, load_strategy_comparison
from strategy_lab.data import DataLakeLayout, DuckDBWarehouse
from strategy_lab.experiments import ExperimentRunner, RunRegistry, load_experiment_config
from strategy_lab.factors import default_registry
from strategy_lab.features import FeatureBuilder, FeatureStore
from strategy_lab.fs import append_text_locked
from strategy_lab.orchestration import StrategyRunner, load_strategy_workflow
from strategy_lab.scenarios import seed_trend_mvp_data


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


def _write_history_manifest(reports_dir: Path) -> Path:
    run_dir = reports_dir / "runs" / "history_probe" / "run-1"
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    prices = (artifacts_dir / "prices.parquet")
    equity = (artifacts_dir / "equity_curve.parquet")
    trades = (artifacts_dir / "trades.parquet")
    metrics = (artifacts_dir / "metrics.json")

    import pandas as pd

    pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC"),
            "BTC/USDT": [100.0, 101.0, 102.0],
        }
    ).to_parquet(prices, index=False)
    pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC"),
            "equity": [1.0, 1.01, 1.03],
        }
    ).to_parquet(equity, index=False)
    pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=2, freq="D", tz="UTC"),
            "symbol": ["BTC/USDT", "BTC/USDT"],
            "side": ["buy", "sell"],
            "previous_weight": [0.0, 0.5],
            "target_weight": [0.5, 0.0],
            "delta_weight": [0.5, -0.5],
            "price": [100.0, 102.0],
            "signal": [1.0, -1.0],
            "reason": ["increase_long", "reduce_long"],
        }
    ).to_parquet(trades, index=False)
    metrics.write_text(
        json.dumps(
            {
                "backtest_metrics": {
                    "sharpe": 1.2,
                    "cumulative_return": 0.03,
                },
                "backtest_attribution": {
                    "gross_return_sum": 0.05,
                },
            }
        ),
        encoding="utf-8",
    )
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "generated_at": "2026-01-01T00:00:00+00:00",
                "strategy_type": "factor",
                "signal_version": "v1",
                "structured_artifacts": {
                    "prices": str(prices),
                    "equity_curve": str(equity),
                    "trades": str(trades),
                    "metrics": str(metrics),
                },
                "backtest_metrics": {"sharpe": 1.2, "cumulative_return": 0.03},
                "backtest_attribution": {"gross_return_sum": 0.05},
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


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

    registry = RunRegistry(layout.reports_dir, db_path=layout.run_registry_db_path)
    records = registry.load()
    kinds = {item["kind"] for item in records}

    assert {"workflow_run", "experiment_run", "comparison_run"} <= kinds
    assert any(item["kind"] == "workflow_run" and item["name"] == "trend_registry" for item in records)

    experiment_records = [item for item in records if item["kind"] == "experiment_run" and item["name"] == "registry_experiment"]
    assert len(experiment_records) == 1
    assert len(experiment_records[0]["child_manifest_paths"]) == 2
    assert experiment_records[0]["child_run_count"] == 2

    comparison_records = [item for item in records if item["kind"] == "comparison_run" and item["name"] == "registry_comparison"]
    assert len(comparison_records) == 1
    assert len(comparison_records[0]["child_manifest_paths"]) == 2
    assert comparison_records[0]["child_run_count"] == 2
    assert registry.sqlite_path.exists()

    workflow_record = next(item for item in records if item["kind"] == "workflow_run" and item["name"] == "trend_registry")
    assert registry.load_run(workflow_record["manifest_path"]) is not None
    assert registry.load_series(workflow_record["manifest_path"], "equity_curve", limit=5)
    assert registry.load_trades(workflow_record["manifest_path"], limit=5)


def test_run_registry_backfill_from_jsonl_is_idempotent(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    manifest_path = _write_history_manifest(reports_dir)
    registry = RunRegistry(reports_dir)
    entry_payload = {
        "kind": "workflow_run",
        "name": "history_probe",
        "run_id": "run-1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "manifest_path": str(manifest_path),
        "strategy_name": "history_probe",
        "signal_name": "ret_1",
        "strategy_type": "factor",
        "backtest_metrics": {"sharpe": 1.2, "cumulative_return": 0.03},
        "backtest_attribution": {"gross_return_sum": 0.05},
        "structured_artifact_paths": json.loads(manifest_path.read_text(encoding="utf-8"))["structured_artifacts"],
    }
    append_text_locked(registry.path, json.dumps(entry_payload) + "\n", encoding="utf-8")

    first = registry.backfill_from_jsonl()
    second = registry.backfill_from_jsonl()

    assert first["processed"] == 1
    assert first["failed"] == 0
    assert second["processed"] == 1
    assert second["failed"] == 0

    records = registry.load(kind="workflow_run")
    assert len(records) == 1
    assert records[0]["manifest_path"] == str(manifest_path)
    assert registry.load_series(str(manifest_path), "equity_curve", limit=10)
    assert registry.load_trades(str(manifest_path), limit=10)
