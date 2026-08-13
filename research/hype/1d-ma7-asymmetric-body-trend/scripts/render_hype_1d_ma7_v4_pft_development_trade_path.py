"""Render the locked D-only A001_T failed-candidate trade path."""

from __future__ import annotations

from datetime import UTC, datetime
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
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
PARENT_PATH = SCRIPT_DIR / "render_hype_1d_ma7_abt_v3_ma_only_reversal_trade_path.py"
MANIFEST_PATH = ARTIFACT_DIR / "hype_1d_ma7_v4_pft_repair_2026-08-09_manifest.json"
TRIALS_PATH = ARTIFACT_DIR / "hype_1d_ma7_v4_pft_repair_2026-08-09_development_trials.json"
DEVELOPMENT_PATH = ARTIFACT_DIR / "hype_1d_ma7_v4_pft_repair_2026-08-09_development.json"
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_v4_pft_repair_2026-08-09_development_failed_A001_T_trade_path.html"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_locked(path: Path) -> None:
    sidecar = path.with_suffix(".sha256")
    fields = sidecar.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[0] != sha256(path) or fields[1] != path.name:
        raise RuntimeError(f"invalid locked artifact: {path.name}")


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_payload() -> dict[str, Any]:
    for path in (MANIFEST_PATH, TRIALS_PATH, DEVELOPMENT_PATH):
        verify_locked(path)
    development = json.loads(DEVELOPMENT_PATH.read_text(encoding="utf-8"))
    if development["status"] != "FAIL" or development["champion_arm_id"] is not None:
        raise RuntimeError("renderer is only valid for the locked failed D outcome")
    trials = json.loads(TRIALS_PATH.read_text(encoding="utf-8"))["trials"]
    by_id = {trial["arm_id"]: trial for trial in trials}
    candidate = by_id["A001_T"]["base_full"]
    control = by_id["A000_V4"]["base_full"]
    adapter = load_module(ADAPTER_PATH, "hype_v4_pft_renderer_adapter")
    context = adapter.load_context()
    parent = load_module(PARENT_PATH, "hype_v4_pft_renderer_parent")
    renderer = parent.load_pinned(
        parent.V2_RENDERER_PATH,
        parent.V2_RENDERER_SHA256,
        "hype_v4_pft_renderer_kernel",
    )
    candles = [
        {
            "t": renderer.timestamp_ms(ts),
            "o": float(context.book.open[index]),
            "h": float(context.book.high[index]),
            "l": float(context.book.low[index]),
            "c": float(context.book.close[index]),
            "ma": renderer.finite_or_none(context.features.ma7[index]),
        }
        for index, ts in enumerate(context.book.ts[:259])
    ]
    trades = []
    previous: dict[str, Any] | None = None
    for index, trade in enumerate(candidate["trades"], 1):
        forced = bool(
            previous
            and previous["side"] == "long"
            and previous["exit_ts"] == trade["entry_ts"]
            and trade["side"] == "short"
        )
        entry_source = (
            "forced_trailing_stop_reversal" if forced else "natural_reclaim"
        )
        trades.append(
            {
                "id": f"A001-{index:02d}",
                "side": str(trade["side"]),
                "entryT": renderer.timestamp_ms(trade["entry_ts"]),
                "exitT": renderer.timestamp_ms(trade["exit_ts"]),
                "entryTs": str(trade["entry_ts"]),
                "exitTs": str(trade["exit_ts"]),
                "entry": float(trade["entry_price"]),
                "exit": float(trade["exit_price"]),
                "bars": int(trade["bars_held"]),
                "reason": str(trade["exit_reason"]),
                "returnPct": float(trade["net_return"]) * 100.0,
                "netPnl": float(trade["net_pnl"]),
                "entrySource": entry_source,
            }
        )
        previous = trade
    equity = [
        {
            "t": renderer.timestamp_ms(row["ts"]),
            "v": float(row["close_equity"]),
            "position": int(row["position"]),
            "action": str(row["action"]),
        }
        for row in candidate["path"]
    ]
    metrics = candidate["metrics"]
    v4 = control["metrics"]
    return {
        "title": "HYPE 1D MA7 V4-PFT：A001_T 开发集失败路径",
        "subtitle": (
            "D-only · hard-gate FAIL · RSI6<25×2 short take-profit · "
            f"A001 +{metrics['net_return_pct']:.2f}% / {metrics['max_drawdown_pct']:.2f}% MDD · "
            f"exact V4 +{v4['net_return_pct']:.2f}% / {v4['max_drawdown_pct']:.2f}% MDD · "
            "V/H 未揭示"
        ),
        "generatedAt": datetime.now(UTC).isoformat(),
        "candles": candles,
        "trades": trades,
        "equity": equity,
        "metrics": {
            "returnPct": metrics["net_return_pct"],
            "mddPct": metrics["max_drawdown_pct"],
            "sharpe": None,
            "profitFactor": metrics["profit_factor"],
            "trades": metrics["closed_trades"],
            "longTrades": metrics["long_trades"],
            "shortTrades": metrics["short_trades"],
        },
    }


def main() -> None:
    payload = build_payload()
    parent = sys.modules["hype_v4_pft_renderer_parent"]
    renderer = sys.modules["hype_v4_pft_renderer_kernel"]
    template = parent.load_pinned(
        renderer.TEMPLATE_PATH,
        renderer.TEMPLATE_SHA256,
        "hype_v4_pft_renderer_template",
    )
    html = template.HTML_TEMPLATE.replace(
        "<title>HYPE MA7 完整交易路径</title>",
        "<title>HYPE V4-PFT A001_T D-only失败路径</title>",
    ).replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    if "__PAYLOAD__" in html or "ctx.lineTo(x2, y2)" not in html:
        raise RuntimeError("trade-path HTML validation failed")
    if len(payload["trades"]) != payload["metrics"]["trades"]:
        raise RuntimeError("trade count mismatch")
    if OUTPUT_PATH.exists() or OUTPUT_PATH.with_suffix(".sha256").exists():
        raise RuntimeError("refusing to overwrite locked diagnostic HTML")
    encoded = html.encode()
    digest = hashlib.sha256(encoded).hexdigest()
    with OUTPUT_PATH.open("xb") as handle:
        handle.write(encoded)
    with OUTPUT_PATH.with_suffix(".sha256").open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {OUTPUT_PATH.name}\n")
    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH.relative_to(ROOT)),
                "sha256": digest,
                "candles": len(payload["candles"]),
                "trades": len(payload["trades"]),
                "all_trades_connected": True,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
