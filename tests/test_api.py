from pathlib import Path
import json

from fastapi import HTTPException
import pandas as pd
import pytest

from signal_lab.api import _jsonable_frame, _load_manifest


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

    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "generated_at": "2026-01-01T00:00:00+00:00",
                "structured_artifacts": {
                    "prices": str(prices_path),
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
