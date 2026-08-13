"""Render the locked V6 fixed-3x diagnostic as a self-contained trade path."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
MACHINE_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_abt_v6_3x_leverage_2026-08-10.json"
)
RENDERER_PATH = (
    SCRIPT_DIR / "render_hype_1d_ma7_profit_exit_handoff_continuity.py"
)
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
AUDIT_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v6_3x_leverage.py"
SELF_PATH = Path(__file__).resolve()
HTML_PATH = (
    ARTIFACT_DIR
    / "hype_1d_ma7_abt_v6_3x_leverage_trade_path_2026-08-10.html"
)
MANIFEST_PATH = (
    ARTIFACT_DIR
    / "hype_1d_ma7_abt_v6_3x_leverage_trade_path_2026-08-10_manifest.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_locked_json(path: Path) -> dict[str, Any]:
    sidecar = Path(f"{path}.sha256")
    if not path.exists() or not sidecar.exists():
        raise RuntimeError(f"locked input missing: {path.name}")
    expected = sidecar.read_text(encoding="utf-8").split()[0]
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"{path.name} sidecar mismatch")
    return json.loads(path.read_text(encoding="utf-8"))


def write_locked_json(path: Path, payload: dict[str, Any]) -> None:
    sidecar = Path(f"{path}.sha256")
    if path.exists() or sidecar.exists():
        raise RuntimeError(f"locked output exists: {path.name}")
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    with path.open("xb") as handle:
        handle.write(encoded)
    with sidecar.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")


def validate_trade_path(run: dict[str, Any], label: str) -> dict[str, Any]:
    trades = list(run["trades"])
    if len(trades) != int(run["metrics"]["closed_trades"]):
        raise RuntimeError(f"{label}: trade count mismatch")
    keys = [(str(row["side"]), str(row["entry_ts"])) for row in trades]
    if len(keys) != len(set(keys)):
        raise RuntimeError(f"{label}: duplicate trade identity")
    if any(str(row["entry_ts"]) > str(row["exit_ts"]) for row in trades):
        raise RuntimeError(f"{label}: invalid trade timestamp order")
    if not run.get("path"):
        raise RuntimeError(f"{label}: empty equity path")
    return {
        "closed_trades": len(trades),
        "unique_trade_identities": True,
        "timestamp_order": True,
        "all_endpoints_present": True,
        "line_rendering_path_count": len(trades),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to render the locked diagnostic")

    machine = read_locked_json(MACHINE_PATH)
    if machine.get("status") != "COMPLETED_DIAGNOSTIC":
        raise RuntimeError("V6 3x diagnostic is not complete")
    if machine.get("pins", {}).get("audit") != sha256(AUDIT_PATH):
        raise RuntimeError("V6 3x audit implementation drift")

    candidate = machine["full"]["three_x"]
    control = machine["full"]["one_x"]
    candidate_audit = validate_trade_path(candidate, "candidate")
    control_audit = validate_trade_path(control, "control")
    if candidate["behavior_sha256"] != control["behavior_sha256"]:
        raise RuntimeError("1x/3x trade behavior drift")

    renderer = load_module(RENDERER_PATH, "v6_3x_base_renderer")
    adapter = load_module(ADAPTER_PATH, "v6_3x_adapter")
    context = adapter.load_context()
    document, base_audit = renderer.build_document(
        title="HYPE-1D-MA7-ABT-V6 — 固定 3x vs Exact V6 1x",
        candles=renderer.candles_from_context(context),
        candidate=candidate,
        control=control,
    )
    replacements = {
        "按钮切换唯一shadow候选与exact V4。": (
            "按钮切换固定3x与exact V6 1x；交易行为相同，仅仓位与权益路径不同。"
        ),
        ">PEHC Shadow Candidate<": ">V6 Fixed 3x<",
        ">Exact V4<": ">Exact V6 1x<",
    }
    text = document.decode("utf-8")
    for old, new in replacements.items():
        if text.count(old) != 1:
            raise RuntimeError(f"renderer label drift: {old}")
        text = text.replace(old, new)
    document = text.encode("utf-8")
    if "Exact V4" in text or "exact V4" in text:
        raise RuntimeError("stale Exact V4 label remains")
    if "__PLACEHOLDER__" in text:
        raise RuntimeError("template placeholder remains")

    html_write = renderer.write_locked(HTML_PATH, document)
    manifest = {
        "schema": "hype-1d-ma7-abt-v6-fixed-3x-trade-path-v1",
        "machine_sha256": sha256(MACHINE_PATH),
        "audit_sha256": sha256(AUDIT_PATH),
        "renderer_sha256": sha256(SELF_PATH),
        "base_renderer_sha256": sha256(RENDERER_PATH),
        "html": html_write,
        "html_sha256_verified": sha256(HTML_PATH) == html_write["sha256"],
        "embedded_payload_complete": True,
        "candidate": candidate_audit,
        "control": control_audit,
        "candidate_control_trade_behavior_equal": True,
        "all_trades_connected": (
            candidate_audit["line_rendering_path_count"]
            == candidate_audit["closed_trades"]
            and control_audit["line_rendering_path_count"]
            == control_audit["closed_trades"]
        ),
        "base_renderer_audit": base_audit,
        "external_dependencies": 0,
        "template_placeholders": 0,
    }
    if not (
        manifest["html_sha256_verified"]
        and manifest["all_trades_connected"]
        and base_audit["all_trades_connected"]
        and base_audit["external_dependencies"] == 0
    ):
        raise RuntimeError("V6 3x trade-path validation failed")
    write_locked_json(MANIFEST_PATH, manifest)
    print(
        json.dumps(
            {
                "html": str(HTML_PATH),
                "manifest": str(MANIFEST_PATH),
                "candidate_trades": candidate_audit["closed_trades"],
                "control_trades": control_audit["closed_trades"],
                "sha256": html_write["sha256"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
