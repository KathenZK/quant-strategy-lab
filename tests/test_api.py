from pathlib import Path
import json

from fastapi import HTTPException
import pandas as pd
import pytest

from strategy_lab.api import _jsonable_frame, _load_manifest, create_app
from strategy_lab.config import load_settings
from strategy_lab.data import DataLakeLayout
from strategy_lab.experiments import RunRegistry, RunRegistryEntry
from strategy_lab.scenarios import seed_trend_mvp_data


def _write_run_manifest(
    reports_dir: Path,
    *,
    row_count: int,
    strategy_name: str = "api_probe",
    run_id: str = "run-1",
) -> Path:
    run_dir = reports_dir / "runs" / strategy_name / run_id
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    prices = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=row_count, freq="D", tz="UTC"),
            "BTC/USDT:USDT": list(range(row_count)),
        }
    )
    prices_path = artifacts_dir / "prices.parquet"
    prices.to_parquet(prices_path, index=False)

    metrics_path = artifacts_dir / "metrics.json"
    metrics_path.write_text(json.dumps({"backtest_metrics": {"sharpe": 1.23}}), encoding="utf-8")

    equity_curve = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=min(row_count, 5), freq="D", tz="UTC"),
            "equity": [1.0, 1.02, 1.01, 1.04, 1.05][: min(row_count, 5)],
        }
    )
    equity_path = artifacts_dir / "equity_curve.parquet"
    equity_curve.to_parquet(equity_path, index=False)

    trades = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=2, freq="D", tz="UTC"),
            "symbol": ["BTC/USDT:USDT", "BTC/USDT:USDT"],
            "side": ["buy", "sell"],
            "previous_weight": [0.0, 0.5],
            "target_weight": [0.5, 0.0],
            "delta_weight": [0.5, -0.5],
            "price": [100.0, 101.0],
            "signal": [1.0, -1.0],
            "reason": ["increase_long", "reduce_long"],
        }
    )
    trades_path = artifacts_dir / "trades.parquet"
    trades.to_parquet(trades_path, index=False)

    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "generated_at": "2026-01-01T00:00:00+00:00",
                "strategy_type": "factor",
                "signal_version": "v1",
                "backtest_metrics": {"sharpe": 1.23},
                "structured_artifacts": {
                    "prices": str(prices_path),
                    "equity_curve": str(equity_path),
                    "trades": str(trades_path),
                    "metrics": str(metrics_path),
                },
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_run_detail_rejects_manifest_path_outside_reports_dir(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    outside_manifest = tmp_path / "outside.json"
    outside_manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(HTTPException) as exc_info:
        _load_manifest(reports_dir, str(outside_manifest))

    assert getattr(exc_info.value, "status_code", None) == 400
    assert "reports dir" in str(getattr(exc_info.value, "detail", ""))


def test_run_detail_limits_structured_artifact_rows(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    manifest_path = _write_run_manifest(reports_dir, row_count=1200)

    manifest = _load_manifest(reports_dir, str(manifest_path))
    prices = _jsonable_frame(
        reports_dir,
        manifest["structured_artifacts"]["prices"],
        row_limit=100,
    )

    assert len(prices) == 100
    assert prices[0]["BTC/USDT:USDT"] == 1100


def _write_app_config(tmp_path: Path, reports_dir: Path) -> Path:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""
project:
  name: api-test
  timezone: UTC

storage:
  root_dir: {tmp_path / 'data'}
  raw_dir: {tmp_path / 'data' / 'raw'}
  normalized_dir: {tmp_path / 'data' / 'normalized'}
  features_dir: {tmp_path / 'data' / 'features'}
  reports_dir: {reports_dir}
""".strip(),
        encoding="utf-8",
    )
    return config_path


def _endpoint(app, path: str):
    for route in app.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise AssertionError(f"route not found: {path}")


def test_api_prefers_sqlite_for_runs_and_detail(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    manifest_path = _write_run_manifest(reports_dir, row_count=12)
    app_config = _write_app_config(tmp_path, reports_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    registry = RunRegistry(reports_dir)
    registry.append(
        RunRegistryEntry(
            kind="workflow_run",
            name="api_probe",
            run_id="run-1",
            generated_at="2026-01-01T00:00:00+00:00",
            manifest_path=str(manifest_path),
            strategy_name="api_probe",
            signal_name="ret_1",
            strategy_type="factor",
            backtest_metrics={"sharpe": 1.23},
            backtest_attribution={"gross_return_sum": 0.11},
            paper_summary={"final_equity": 105000.0, "fill_count": 2},
            structured_artifact_paths=dict(manifest["structured_artifacts"]),
        ),
        manifest_payload=manifest,
    )

    Path(manifest["structured_artifacts"]["equity_curve"]).unlink()
    Path(manifest["structured_artifacts"]["trades"]).unlink()

    app = create_app(app_config)
    runs = _endpoint(app, "/api/runs")(
        kind=None,
        search="api_probe",
        strategy_type="factor",
        sort_by="generated_at",
        sort_order="desc",
        limit=200,
        offset=0,
    )["runs"]
    assert len(runs) == 1
    assert runs[0]["strategy_type"] == "factor"

    payload = _endpoint(app, "/api/run-detail")(manifest_path=str(manifest_path), limit=10)
    assert payload["metrics"]["backtest_metrics"]["sharpe"] == 1.23
    assert payload["artifacts"]["equity_curve"]
    assert payload["artifacts"]["trades"]


def test_api_returns_experiment_and_comparison_details(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    child_one_manifest = _write_run_manifest(reports_dir, row_count=6, strategy_name="child_one", run_id="run-a")
    child_two_manifest = _write_run_manifest(reports_dir, row_count=6, strategy_name="child_two", run_id="run-b")
    app_config = _write_app_config(tmp_path, reports_dir)

    child_one = json.loads(child_one_manifest.read_text(encoding="utf-8"))
    child_two = json.loads(child_two_manifest.read_text(encoding="utf-8"))
    registry = RunRegistry(reports_dir)
    registry.append(
        RunRegistryEntry(
            kind="workflow_run",
            name="child_one",
            run_id="run-a",
            generated_at="2026-01-01T00:00:00+00:00",
            manifest_path=str(child_one_manifest),
            strategy_name="child_one",
            signal_name="ret_1",
            strategy_type="factor",
            backtest_metrics={"sharpe": 1.5, "cumulative_return": 0.12},
            structured_artifact_paths=dict(child_one["structured_artifacts"]),
        ),
        manifest_payload=child_one,
    )
    registry.append(
        RunRegistryEntry(
            kind="workflow_run",
            name="child_two",
            run_id="run-b",
            generated_at="2026-01-02T00:00:00+00:00",
            manifest_path=str(child_two_manifest),
            strategy_name="child_two",
            signal_name="ret_4",
            strategy_type="factor",
            backtest_metrics={"sharpe": 0.9, "cumulative_return": 0.04},
            structured_artifact_paths=dict(child_two["structured_artifacts"]),
        ),
        manifest_payload=child_two,
    )

    experiment_manifest_path = reports_dir / "experiments" / "exp_demo" / "run-exp" / "experiment_manifest.json"
    experiment_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    experiment_manifest = {
        "run_id": "run-exp",
        "generated_at": "2026-01-03T00:00:00+00:00",
        "experiment": {
            "name": "exp_demo",
            "description": "experiment detail probe",
            "objective": {"metric": "sharpe", "direction": "max"},
        },
        "entries": [
            {
                "strategy_name": "child_one",
                "workflow_name": "child_one",
                "run_id": "run-a",
                "run_manifest_path": str(child_one_manifest),
            },
            {
                "strategy_name": "child_two",
                "workflow_name": "child_two",
                "run_id": "run-b",
                "run_manifest_path": str(child_two_manifest),
            },
        ],
        "winner": {
            "strategy_name": "child_one",
            "workflow_name": "child_one",
            "run_id": "run-a",
            "run_manifest_path": str(child_one_manifest),
        },
    }
    experiment_manifest_path.write_text(json.dumps(experiment_manifest), encoding="utf-8")
    registry.append(
        RunRegistryEntry(
            kind="experiment_run",
            name="exp_demo",
            run_id="run-exp",
            generated_at="2026-01-03T00:00:00+00:00",
            manifest_path=str(experiment_manifest_path),
            child_manifest_paths=[str(child_one_manifest), str(child_two_manifest)],
        ),
        manifest_payload=experiment_manifest,
    )

    comparison_manifest_path = reports_dir / "comparisons" / "cmp_demo" / "run-cmp" / "comparison_manifest.json"
    comparison_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_manifest = {
        "run_id": "run-cmp",
        "generated_at": "2026-01-04T00:00:00+00:00",
        "comparison": {
            "name": "cmp_demo",
            "description": "comparison detail probe",
        },
        "entries": [
            {"strategy_name": "child_one"},
            {"strategy_name": "child_two"},
        ],
    }
    comparison_manifest_path.write_text(json.dumps(comparison_manifest), encoding="utf-8")
    registry.append(
        RunRegistryEntry(
            kind="comparison_run",
            name="cmp_demo",
            run_id="run-cmp",
            generated_at="2026-01-04T00:00:00+00:00",
            manifest_path=str(comparison_manifest_path),
            child_manifest_paths=[str(child_one_manifest), str(child_two_manifest)],
        ),
        manifest_payload=comparison_manifest,
    )

    app = create_app(app_config)
    experiment_detail = _endpoint(app, "/api/experiment-detail")(manifest_path=str(experiment_manifest_path))
    comparison_detail = _endpoint(app, "/api/comparison-detail")(manifest_path=str(comparison_manifest_path))

    assert experiment_detail["run"]["name"] == "exp_demo"
    assert len(experiment_detail["children"]) == 2
    assert experiment_detail["manifest"]["winner"]["run_manifest_path"] == str(child_one_manifest)

    assert comparison_detail["run"]["name"] == "cmp_demo"
    assert len(comparison_detail["children"]) == 2
    assert comparison_detail["manifest"]["comparison"]["description"] == "comparison detail probe"


def test_lab_strategy_templates_are_loaded_from_yaml(tmp_path: Path) -> None:
    app_config = _write_app_config(tmp_path, tmp_path / "reports")
    app = create_app(app_config)

    payload = _endpoint(app, "/api/lab/strategy-templates")()

    assert payload["templates"]
    strategy_types = [template["strategy_type"] for template in payload["templates"]]
    assert len(strategy_types) == len(set(strategy_types))
    assert "crowding_reversal" in strategy_types
    assert "momentum_rotation" in strategy_types
    template = payload["templates"][0]
    assert template["id"].endswith((".yaml", ".yml"))
    assert template["path"].startswith("configs/workflows/strategies/")
    assert "strategy:" in template["workflow_yaml"]
    assert template["workflow"]["strategy"]["name"]


def test_lab_backtest_job_accepts_full_workflow_yaml(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    app_config = _write_app_config(tmp_path, reports_dir)
    app = create_app(app_config)
    seed_trend_mvp_data(DataLakeLayout.from_settings(load_settings(app_config)))
    workflow_yaml = """
strategy:
  name: lab_yaml_probe
  strategy_type: factor
  factor_name: ret_1
  exchange: binance
  market_type: perp
  symbols:
    - BTC/USDT:USDT
refresh:
  enabled: false
  timeframe: 1h
workflow:
  run_factor_report: false
  run_backtest: true
  run_paper_trade: false
""".strip()

    payload = _endpoint(app, "/api/lab/backtests")(
        payload={
            "template_id": "lab_yaml_probe.yaml",
            "workflow_yaml": workflow_yaml,
        }
    )

    job = payload["job"]
    assert job["template_name"] == "lab_yaml_probe"
    assert job["source"] == "binance"
    assert job["timeframe"] == "1h"
    assert job["universe"] == ["BTC/USDT:USDT"]
    assert job["status"] == "completed"
    assert Path(job["manifest_path"]).exists()
    assert Path(job["backtest_report_path"]).exists()
    assert Path(job["workflow_yaml_path"]).read_text(encoding="utf-8") == workflow_yaml

    runs = _endpoint(app, "/api/runs")(
        kind="workflow_run",
        search="lab_yaml_probe",
        strategy_type=None,
        sort_by="generated_at",
        sort_order="desc",
        limit=200,
        offset=0,
    )["runs"]
    assert any(run["run_id"] == job["run_id"] for run in runs)
