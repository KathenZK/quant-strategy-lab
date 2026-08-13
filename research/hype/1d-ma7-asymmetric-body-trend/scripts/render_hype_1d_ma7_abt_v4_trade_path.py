from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PARENT_PATH = (
    FAMILY_DIR
    / "scripts/render_hype_1d_ma7_abt_v3_ma_only_reversal_trade_path.py"
)
PARENT_SHA256 = (
    "975e81ddb51c4521f510f153448796cded29e2d8ede1cc6bdb8c6f4a7b533d39"
)
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v4_trade_path_2026-08-07.html"


def main() -> None:
    spec = importlib.util.spec_from_file_location(
        "hype_v4_chart_parent",
        PARENT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {PARENT_PATH}")
    actual = hashlib.sha256(PARENT_PATH.read_bytes()).hexdigest()
    if actual != PARENT_SHA256:
        raise RuntimeError(
            f"{PARENT_PATH.name} drift: expected {PARENT_SHA256}, got {actual}"
        )
    parent = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = parent
    spec.loader.exec_module(parent)
    audit = parent.load_pinned(
        parent.AUDIT_PATH,
        parent.AUDIT_SHA256,
        "hype_v4_chart_audit",
    )
    renderer = parent.load_pinned(
        parent.V2_RENDERER_PATH,
        parent.V2_RENDERER_SHA256,
        "hype_v4_chart_renderer",
    )
    template = renderer.load_pinned(
        renderer.TEMPLATE_PATH,
        renderer.TEMPLATE_SHA256,
        "hype_v4_chart_template",
    )
    payload = parent.build_payload(audit, renderer)
    payload["title"] = "HYPE 日线 MA7 非对称趋势 V4：完整交易路径"
    payload["subtitle"] = (
        "V4 registered 1x · trailing平多后仅在拟反手真实1h open低于"
        "上一完整日MA7时做空 · 2次拒绝 · 5次反手"
    )
    html = template.HTML_TEMPLATE.replace(
        "<title>HYPE MA7 完整交易路径</title>",
        "<title>HYPE MA7 V4 完整交易路径</title>",
    ).replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    parent.validate(payload, html)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH.relative_to(ROOT)),
                "candles": len(payload["candles"]),
                "trades": len(payload["trades"]),
                "forced_reversal_trades": sum(
                    trade["entrySource"] == "forced_trailing_stop_reversal"
                    for trade in payload["trades"]
                ),
                "all_trades_connected": True,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
