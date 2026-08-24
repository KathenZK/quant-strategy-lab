from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
PARENT_PATH = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "audit_hype_1d_v2_3x_leverage.py"
)
PARENT_SHA256 = (
    "ebde0e381654af1bdbe092b76e9f3d1ebd68f98b995ff3c0243850e6690ed22a"
)
V3_1X_EQUITY_MULTIPLE = 4.508464159893385


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(
            f"expected one parent adapter target, got {source.count(old)}: {old}"
        )
    return source.replace(old, new)


def transformed_parent() -> str:
    actual = hashlib.sha256(PARENT_PATH.read_bytes()).hexdigest()
    if actual != PARENT_SHA256:
        raise RuntimeError(
            f"V2 leverage parent drift: expected {PARENT_SHA256}, got {actual}"
        )
    source = PARENT_PATH.read_text(encoding="utf-8")
    source = source.replace("V2", "V3").replace("v2", "v3")
    source = replace_once(
        source,
        "V3_1X_EQUITY_MULTIPLE = 4.225904698992523",
        f"V3_1X_EQUITY_MULTIPLE = {V3_1X_EQUITY_MULTIPLE!r}",
    )
    source = replace_once(
        source,
        'short_config = engine.Config(**selected["short_config"])',
        (
            'short_config = engine.Config(**{**selected["short_config"], '
            '"exit_buffer_atr": 0.75})'
        ),
    )
    source = replace_once(
        source,
        "hype-1d-ma7-abt-v3-3x-leverage-contract-2026-08-06.md",
        "hype-1d-ma7-abt-v3-3x-leverage-contract-2026-08-07.md",
    )
    source = replace_once(
        source,
        '"pins": {\n            "formation_path":',
        (
            '"pins": {\n'
            '            "adapter_parent_path": '
            '"research/hype/1d-ma7-asymmetric-body-trend/scripts/'
            'audit_hype_1d_v2_3x_leverage.py",\n'
            f'            "adapter_parent_sha256": "{PARENT_SHA256}",\n'
            '            "formation_path":'
        ),
    )
    return source


def main() -> None:
    namespace: dict[str, Any] = {
        "__name__": "hype_v3_3x_transformed_parent",
        "__file__": str(Path(__file__).resolve()),
    }
    source = transformed_parent()
    exec(compile(source, str(PARENT_PATH), "exec"), namespace)
    namespace["main"]()


if __name__ == "__main__":
    main()
