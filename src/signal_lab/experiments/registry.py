from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json

from signal_lab.fs import append_text_locked
from signal_lab.experiments.sqlite_store import RunSqliteStore


@dataclass(frozen=True, slots=True)
class RunRegistryEntry:
    kind: str
    name: str
    run_id: str
    generated_at: str
    manifest_path: str
    app_config_path: str | None = None
    primary_report_path: str | None = None
    factor_report_path: str | None = None
    backtest_report_path: str | None = None
    paper_report_path: str | None = None
    strategy_name: str | None = None
    signal_name: str | None = None
    strategy_type: str | None = None
    variant_id: str | None = None
    config_hash: str | None = None
    git_sha: str | None = None
    data_snapshot_id: str | None = None
    backtest_metrics: dict[str, float] = field(default_factory=dict)
    backtest_attribution: dict[str, float | str | None] = field(default_factory=dict)
    paper_summary: dict[str, float] = field(default_factory=dict)
    structured_artifact_paths: dict[str, str] = field(default_factory=dict)
    child_manifest_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RunRegistryEntry":
        return cls(
            kind=str(payload["kind"]),
            name=str(payload["name"]),
            run_id=str(payload["run_id"]),
            generated_at=str(payload["generated_at"]),
            manifest_path=str(payload["manifest_path"]),
            app_config_path=payload.get("app_config_path"),
            primary_report_path=payload.get("primary_report_path"),
            factor_report_path=payload.get("factor_report_path"),
            backtest_report_path=payload.get("backtest_report_path"),
            paper_report_path=payload.get("paper_report_path"),
            strategy_name=payload.get("strategy_name"),
            signal_name=payload.get("signal_name"),
            strategy_type=payload.get("strategy_type") or payload.get("signal_type"),
            variant_id=payload.get("variant_id"),
            config_hash=payload.get("config_hash"),
            git_sha=payload.get("git_sha"),
            data_snapshot_id=payload.get("data_snapshot_id"),
            backtest_metrics=dict(payload.get("backtest_metrics", {})),
            backtest_attribution=dict(payload.get("backtest_attribution", {})),
            paper_summary=dict(payload.get("paper_summary", {})),
            structured_artifact_paths=dict(payload.get("structured_artifact_paths", {})),
            child_manifest_paths=list(payload.get("child_manifest_paths", [])),
        )


class RunRegistry:
    def __init__(self, reports_dir: Path, *, db_path: Path | None = None) -> None:
        self.reports_dir = reports_dir
        self.sqlite_store = RunSqliteStore(db_path or (reports_dir / "_registry" / "runs.sqlite"))

    @property
    def path(self) -> Path:
        return self.reports_dir / "_registry" / "runs.jsonl"

    @property
    def sqlite_path(self) -> Path:
        return self.sqlite_store.db_path

    def append(self, entry: RunRegistryEntry, *, manifest_payload: dict[str, Any] | None = None) -> Path:
        jsonl_path = append_text_locked(
            self.path,
            json.dumps(entry.to_dict(), sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        self.sqlite_store.upsert_run(entry, manifest_payload=manifest_payload)
        return jsonl_path

    def _load_jsonl_rows(self, kind: str | None = None) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []

        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if kind is not None and payload.get("kind") != kind:
                continue
            rows.append(payload)
        return rows

    def load(
        self,
        kind: str | None = None,
        *,
        search: str | None = None,
        strategy_type: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort_by: str = "generated_at",
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        if self.sqlite_store.load_count() > 0:
            return self.sqlite_store.load_runs(
                kind=kind,
                search=search,
                strategy_type=strategy_type,
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_order=sort_order,
            )

        rows = self._load_jsonl_rows(kind=kind)
        if search:
            pattern = search.lower()
            rows = [
                row
                for row in rows
                if pattern in " ".join(
                    str(row.get(key, "")).lower()
                    for key in ("name", "strategy_name", "signal_name", "strategy_type", "variant_id")
                )
            ]
        if strategy_type:
            rows = [row for row in rows if (row.get("strategy_type") or row.get("signal_type")) == strategy_type]

        reverse = sort_order.lower() != "asc"

        def sort_value(row: dict[str, Any]):
            metrics = row.get("backtest_metrics") or {}
            if sort_by in metrics:
                return metrics.get(sort_by) or float("-inf")
            if sort_by == "final_equity":
                return (row.get("paper_summary") or {}).get("final_equity") or float("-inf")
            return row.get(sort_by) or ""

        rows.sort(key=sort_value, reverse=reverse)
        if offset:
            rows = rows[offset:]
        if limit is not None:
            rows = rows[:limit]
        for row in rows:
            row["child_run_count"] = len(row.get("child_manifest_paths", []))
        return rows

    def load_run(self, manifest_path: str) -> dict[str, Any] | None:
        if self.sqlite_store.load_count() > 0:
            return self.sqlite_store.load_run(manifest_path)
        for row in self._load_jsonl_rows():
            if row.get("manifest_path") == manifest_path:
                row["child_run_count"] = len(row.get("child_manifest_paths", []))
                return row
        return None

    def load_manifest(self, manifest_path: str) -> dict[str, Any] | None:
        return self.sqlite_store.load_manifest(manifest_path)

    def load_series(self, manifest_path: str, series_name: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        return self.sqlite_store.load_series(manifest_path, series_name, limit=limit)

    def load_trades(self, manifest_path: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        return self.sqlite_store.load_trades(manifest_path, limit=limit)

    def load_children(self, parent_manifest_path: str) -> list[dict[str, Any]]:
        return self.sqlite_store.load_children(parent_manifest_path)

    def backfill_from_jsonl(self) -> dict[str, Any]:
        summary = {
            "jsonl_path": str(self.path),
            "sqlite_path": str(self.sqlite_path),
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "failed_manifests": [],
        }
        for row in self._load_jsonl_rows():
            summary["processed"] += 1
            entry = RunRegistryEntry.from_dict(row)
            manifest_payload = None
            manifest_path = Path(entry.manifest_path)
            if manifest_path.exists():
                try:
                    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    manifest_payload = None
            try:
                self.sqlite_store.upsert_run(entry, manifest_payload=manifest_payload)
            except Exception:
                summary["failed"] += 1
                summary["failed_manifests"].append(entry.manifest_path)
            else:
                summary["succeeded"] += 1
        return summary
