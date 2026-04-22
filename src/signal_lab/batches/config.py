from __future__ import annotations

from pathlib import Path

import yaml

from signal_lab.batches.models import WorkflowBatchConfig


def load_workflow_batch_config(
    path: str | Path,
    *,
    sections: tuple[str, ...] = ("batch",),
) -> WorkflowBatchConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"batch config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    batch_payload = None
    matched_section = None
    for section in sections:
        candidate = payload.get(section)
        if candidate is not None:
            batch_payload = candidate
            matched_section = section
            break

    if batch_payload is None:
        expected = ", ".join(sections)
        raise KeyError(f"expected one of batch config sections: {expected}")

    workflow_configs = []
    for item in batch_payload.get("workflow_configs", []):
        candidate = Path(item)
        if not candidate.is_absolute():
            candidate = (config_path.parent / candidate).resolve()
        workflow_configs.append(str(candidate))

    try:
        name = batch_payload["name"]
    except KeyError as exc:
        raise KeyError(f"missing required key 'name' in {matched_section} config") from exc

    return WorkflowBatchConfig(
        name=name,
        workflow_configs=workflow_configs,
        description=batch_payload.get("description"),
    )
