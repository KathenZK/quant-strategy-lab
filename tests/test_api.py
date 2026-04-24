from pathlib import Path
import json

from fastapi import HTTPException
import pandas as pd
import pytest

from signal_lab.api import _jsonable_frame, _load_manifest, create_app
from signal_lab.experiments import RunRegistry, RunRegistryEntry


def _write_run_manifest(reports_dir: Path, *, row_count: int) -> Path:
    run_dir = reports_dir / "runs" / "api_probe" / "run-1"
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
                "run_id": "run-1",
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
