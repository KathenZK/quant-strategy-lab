from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json

from signal_lab.fs import append_text_locked


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
    signal_type: str | None = None
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


class RunRegistry:
    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir

    @property
    def path(self) -> Path:
        return self.reports_dir / "_registry" / "runs.jsonl"

    def append(self, entry: RunRegistryEntry) -> Path:
        return append_text_locked(
            self.path,
            json.dumps(entry.to_dict(), sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )

    def load(self, kind: str | None = None) -> list[dict]:
        if not self.path.exists():
            return []

        rows: list[dict] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if kind is not None and payload.get("kind") != kind:
                continue
            rows.append(payload)
        return rows
