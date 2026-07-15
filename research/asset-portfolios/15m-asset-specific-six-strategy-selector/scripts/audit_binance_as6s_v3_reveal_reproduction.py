from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

import reveal_binance_as6s_v3_future_oos as reveal
from as6s_engine import load_funding, load_symbol_frame


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
SOURCE = FAMILY_DIR / "artifacts/binance_as6s_asset_first_v3_candidate_2026-07-14.json"
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v3_reveal_reproduction_2026-07-14.json"

FIELDS = (
    "trades",
    "wins",
    "win_rate",
    "total_return",
    "annual_multiple",
    "max_dd",
    "profit_factor",
    "long_trades",
    "short_trades",
    "preemptions",
    "trades_per_day",
)


def equal(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if math.isinf(float(left)) and math.isinf(float(right)):
            return True
        return math.isclose(float(left), float(right), rel_tol=1e-11, abs_tol=1e-11)
    return left == right


def main() -> None:
    manifest = reveal.load_manifest()
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    reveal.OOS_END = reveal.OOS_START
    frames = {
        symbol: load_symbol_frame(symbol, end=reveal.OOS_END)
        for symbol in reveal.SYMBOLS
    }
    funding = {
        symbol: load_funding(symbol, end=reveal.OOS_END)
        for symbol in reveal.SYMBOLS
    }
    universe = reveal.build_universe(manifest, frames, funding)
    reproduced, _trades = reveal.route_results(manifest, universe, frames, funding)

    comparisons: dict[str, Any] = {}
    failures: list[str] = []
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        comparisons[mode] = {}
        for scenario in reveal.SCENARIOS:
            expected = source["comparisons"][mode]["scenarios"][scenario]["full"]
            actual = reproduced[mode]["scenarios"][scenario]["full"]
            field_results = {
                field: equal(actual[field], expected[field]) for field in FIELDS
            }
            comparisons[mode][scenario] = {
                "pass": all(field_results.values()),
                "fields": field_results,
                "expected": {field: expected[field] for field in FIELDS},
                "actual": {field: actual[field] for field in FIELDS},
            }
            failures.extend(
                f"{mode}:{scenario}:{field}"
                for field, passed in field_results.items()
                if not passed
            )

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "future_reveal_harness_frozen_period_reproduction",
        "result": "PASS" if not failures else "FAIL",
        "source": str(SOURCE.relative_to(ROOT)),
        "reproduction_end_exclusive": reveal.OOS_END.isoformat(),
        "comparisons": comparisons,
        "failures": failures,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    if failures:
        raise RuntimeError(f"future reveal harness reproduction failed: {failures}")
    print(json.dumps({"output": str(OUTPUT), "result": "PASS"}, indent=2))


if __name__ == "__main__":
    main()
