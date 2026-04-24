from __future__ import annotations

from pathlib import Path
import json
import os

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

from signal_lab.config import load_settings
from signal_lab.data import DataLakeLayout
from signal_lab.experiments import RunRegistry


def _layout(config_path: str | Path | None = None) -> DataLakeLayout:
    return DataLakeLayout.from_settings(load_settings(config_path))


def _resolve_reports_path(
    reports_dir: Path,
    value: str | Path | None,
    *,
    strict: bool = True,
) -> Path | None:
    if not value:
        return None
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (reports_dir / candidate).resolve()
    reports_root = reports_dir.resolve()
    try:
        resolved.relative_to(reports_root)
    except ValueError:
        if strict:
            raise HTTPException(status_code=400, detail=f"path escapes reports dir: {value}")
        return None
    return resolved


def _jsonable_frame(
    reports_dir: Path,
    path: str | None,
    *,
    row_limit: int,
    strict: bool = True,
) -> list[dict[str, object]]:
    artifact_path = _resolve_reports_path(reports_dir, path, strict=strict)
    if artifact_path is None:
        return []
    if not artifact_path.exists():
        return []
    frame = pd.read_parquet(artifact_path)
    if row_limit > 0 and len(frame) > row_limit:
        frame = frame.tail(row_limit).reset_index(drop=True)
    for column in frame.columns:
        if pd.api.types.is_datetime64_any_dtype(frame[column]):
            frame[column] = pd.to_datetime(frame[column], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def _read_json(reports_dir: Path, path: str | None, *, strict: bool = True) -> dict:
    target = _resolve_reports_path(reports_dir, path, strict=strict)
    if target is None:
        return {}
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def _load_manifest(reports_dir: Path, manifest_path: str, *, strict: bool = True) -> dict:
    target = _resolve_reports_path(reports_dir, manifest_path, strict=strict)
    if target is None:
        raise HTTPException(status_code=400, detail=f"path escapes reports dir: {manifest_path}")
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"manifest not found: {manifest_path}")
    return json.loads(target.read_text(encoding="utf-8"))


def _enrich_run(reports_dir: Path, row: dict) -> dict:
    manifest = {}
    if not row.get("config_hash") or not row.get("git_sha") or not row.get("data_snapshot_id") or not row.get("structured_artifact_paths"):
        manifest = _read_json(reports_dir, row.get("manifest_path"), strict=False)
    metadata = manifest.get("metadata", {})
    strategy_type = (
        row.get("strategy_type")
        or manifest.get("strategy_type")
        or row.get("signal_type")
        or manifest.get("signal_type")
    )
    return {
        **row,
        "variant_id": row.get("variant_id") or metadata.get("variant_id"),
        "config_hash": row.get("config_hash") or manifest.get("config_hash"),
        "git_sha": row.get("git_sha") or manifest.get("git_sha"),
        "data_snapshot_id": row.get("data_snapshot_id") or manifest.get("data_snapshot_id"),
        "strategy_type": strategy_type,
        "structured_artifact_paths": row.get("structured_artifact_paths") or manifest.get("structured_artifacts", {}),
        "generated_at": row.get("generated_at") or manifest.get("generated_at"),
    }


def create_app(config_path: str | Path | None = None) -> FastAPI:
    resolved_config = config_path or os.environ.get("SIGNAL_LAB_CONFIG")
    layout = _layout(resolved_config)
    registry = RunRegistry(layout.reports_dir, db_path=layout.run_registry_db_path)
    app = FastAPI(title="Quant Strategy Lab API", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "reports_dir": str(layout.reports_dir)}

    @app.get("/api/runs")
    def runs(
        kind: str | None = Query(None),
        search: str | None = Query(None),
        strategy_type: str | None = Query(None),
        sort_by: str = Query("generated_at"),
        sort_order: str = Query("desc"),
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ) -> dict[str, list[dict]]:
        rows = [
            _enrich_run(layout.reports_dir, row)
            for row in registry.load(
                kind=kind,
                search=search,
                strategy_type=strategy_type,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
                offset=offset,
            )
        ]
        return {"runs": rows}

    @app.get("/api/run-detail")
    def run_detail(
        manifest_path: str = Query(...),
        limit: int = Query(1000, ge=1, le=5000),
    ) -> dict:
        run_row = registry.load_run(manifest_path)
        manifest = registry.load_manifest(manifest_path) or _load_manifest(layout.reports_dir, manifest_path)
        artifacts = manifest.get("structured_artifacts", {})
        metrics = None
        if run_row and (run_row.get("backtest_metrics") or run_row.get("backtest_attribution")):
            metrics = {
                "backtest_metrics": run_row.get("backtest_metrics", {}),
                "backtest_attribution": run_row.get("backtest_attribution", {}),
            }
        equity_curve = registry.load_series(manifest_path, "equity_curve", limit=limit)
        period_returns = registry.load_series(manifest_path, "period_returns", limit=limit)
        trades = registry.load_trades(manifest_path, limit=limit)
        return {
            "run": _enrich_run(layout.reports_dir, run_row) if run_row else None,
            "manifest": manifest,
            "artifacts": {
                "prices": _jsonable_frame(layout.reports_dir, artifacts.get("prices"), row_limit=limit),
                "signals": _jsonable_frame(layout.reports_dir, artifacts.get("signals"), row_limit=limit),
                "weights": _jsonable_frame(layout.reports_dir, artifacts.get("weights"), row_limit=limit),
                "trades": trades or _jsonable_frame(layout.reports_dir, artifacts.get("trades"), row_limit=limit),
                "equity_curve": equity_curve or _jsonable_frame(layout.reports_dir, artifacts.get("equity_curve"), row_limit=limit),
                "period_returns": period_returns or _jsonable_frame(layout.reports_dir, artifacts.get("period_returns"), row_limit=limit),
            },
            "metrics": metrics or _read_json(layout.reports_dir, artifacts.get("metrics")),
            "row_limit": limit,
        }

    @app.get("/api/experiment-detail")
    def experiment_detail(manifest_path: str = Query(...)) -> dict:
        return {"manifest": registry.load_manifest(manifest_path) or _load_manifest(layout.reports_dir, manifest_path)}

    return app


app = create_app()
