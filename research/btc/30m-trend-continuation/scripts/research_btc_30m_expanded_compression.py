from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/30m-trend-continuation"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
HELPER_PATH = FAMILY_DIR / "scripts/research_btc_30m_trend_continuation.py"
HELPER_SHA256 = "c8dbe4fd8ca3d3b8c030c5cf87133b6bda1204dbad06cddf3966c249128cb5f7"
DATE = "2026-07-21"
SUMMARY_PATH = ARTIFACT_DIR / f"btc_30m_expanded_compression_summary_{DATE}.json"
CANDIDATES_PATH = (
    ARTIFACT_DIR / f"btc_30m_expanded_compression_candidates_{DATE}.csv"
)
TRADES_PATH = (
    ARTIFACT_DIR / f"btc_30m_expanded_compression_selected_trades_{DATE}.csv"
)
WINDOWS_PATH = (
    ARTIFACT_DIR / f"btc_30m_expanded_compression_rolling_{DATE}.csv"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_helper() -> Any:
    actual = sha256_bytes(HELPER_PATH.read_bytes())
    if actual != HELPER_SHA256:
        raise RuntimeError(
            "BTC 30m helper SHA mismatch: "
            f"expected {HELPER_SHA256}, got {actual}"
        )
    module_name = "btc_30m_expanded_compression_helper"
    spec = importlib.util.spec_from_file_location(module_name, HELPER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load helper: {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def configure_expanded(base: Any) -> None:
    base.DATE = DATE
    base.SUMMARY_PATH = SUMMARY_PATH
    base.CANDIDATES_PATH = CANDIDATES_PATH
    base.TRADES_PATH = TRADES_PATH
    base.WINDOWS_PATH = WINDOWS_PATH
    base.COMPRESSION_QUANTILES = (0.35, 0.50, 0.65, 0.80)
    base.COMPRESSION_LOOKBACKS = (8, 16, 32)
    base.BREAKOUT_WINDOWS = (12, 24)
    base.EMA_PAIRS = ((24, 96),)
    base.SLOPE_LAGS = (4,)
    base.ATR_CAPS = (0.005, 0.0075, 0.010, 0.015, 0.050)
    base.EXIT_PROFILES = tuple(
        (stop_atr, hold_bars)
        for stop_atr in (3.0, 4.0, 5.0)
        for hold_bars in (24, 48, 96, 192)
    )


def main() -> None:
    helper = load_helper()
    base = helper.load_source()
    helper.configure(base)
    configure_expanded(base)
    base.main()
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    _, funding, _ = base.load_data()
    phase = helper.phase_audit(base, summary, funding)
    summary = helper.correct_summary(base, summary, phase)
    summary["research_identity"] = "BTC-30M-EXPANDED-COMPRESSION-2026-07-21"
    summary["selection_disclosure"] = (
        "The expanded compression parameters were selected using train, validation, "
        "reused diagnostic, and recent 1y filters. This is full-history research "
        "selection and supplies no untouched OOS evidence."
    )
    summary["provenance"].update(
        {
            "formula_version": "btc-30m-expanded-compression-v1",
            "code_path": str(Path(__file__).resolve().relative_to(ROOT)),
            "code_sha256": sha256_bytes(Path(__file__).read_bytes()),
            "helper_path": str(HELPER_PATH.relative_to(ROOT)),
            "helper_sha256": HELPER_SHA256,
            "generation_time_utc": datetime.now(timezone.utc).isoformat(),
        }
    )
    base.atomic_write_json(SUMMARY_PATH, summary)
    print(
        json.dumps(
            {
                "research_candidate": summary["research_candidate"],
                "research_role": summary["research_role"],
                "universe": summary["universe"],
                "selected": summary["selected"],
                "reused_diagnostic": summary["reused_diagnostic"],
                "reused_diagnostic_2x_cost": summary["reused_diagnostic_2x_cost"],
                "recent_slices": summary["recent_slices"],
                "phase_alignment_audit": summary["phase_alignment_audit"],
                "year_metrics": summary["year_metrics"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
