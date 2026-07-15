from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
SOURCE_DIR = FAMILY_DIR / "artifacts/per_asset_hf_filter_tune"
OUTPUT_DIR = FAMILY_DIR / "artifacts/per_asset_hf_exit_tune"
MII_SCRIPTS = ROOT / "research/hype/15m-multi-indicator-intraday/scripts"
AS6S_SCRIPTS = FAMILY_DIR / "scripts"
sys.path.insert(0, str(MII_SCRIPTS))
sys.path.insert(0, str(AS6S_SCRIPTS))

import research_hype_15m_mii_search as mii  # noqa: E402
from as6s_engine import REUSED_END, STARTS, load_symbol_frame  # noqa: E402
from research_binance_as6s_per_asset_hf_discovery import (  # noqa: E402
    HISTORICAL_OOS_END,
    PREFIT_END,
)
from research_binance_as6s_per_asset_hf_filter_tune import (  # noqa: E402
    score,
    window_metric,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune full exit grid per asset.")
    parser.add_argument("--symbol", choices=tuple(STARTS), required=True)
    parser.add_argument("--signals", type=int, default=20)
    parser.add_argument("--filters", type=int, default=24)
    parser.add_argument("--top", type=int, default=240)
    return parser.parse_args()


def select_signal_specs(
    rows: list[dict[str, Any]], limit: int
) -> list[mii.SignalSpec]:
    output: list[mii.SignalSpec] = []
    seen: set[str] = set()
    kind_counts: dict[str, int] = {}
    for row in rows:
        spec = mii.SignalSpec(**row["signal"])
        if spec.name in seen or kind_counts.get(spec.kind, 0) >= 5:
            continue
        output.append(spec)
        seen.add(spec.name)
        kind_counts[spec.kind] = kind_counts.get(spec.kind, 0) + 1
        if len(output) >= limit:
            return output
    for row in rows:
        spec = mii.SignalSpec(**row["signal"])
        if spec.name in seen:
            continue
        output.append(spec)
        seen.add(spec.name)
        if len(output) >= limit:
            break
    return output


def select_filter_specs(
    rows: list[dict[str, Any]], limit: int
) -> list[mii.FilterSpec]:
    output: list[mii.FilterSpec] = []
    seen: set[str] = set()
    for row in rows:
        spec = mii.FilterSpec(**row["filter"])
        if spec.name in seen:
            continue
        output.append(spec)
        seen.add(spec.name)
        if len(output) >= limit:
            break
    return output


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_path = SOURCE_DIR / f"{args.symbol.lower()}_hf_filter_tune_2026-07-14.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source_rows = source["ranking"]
    signals = select_signal_specs(source_rows, args.signals)
    filters = select_filter_specs(source_rows, args.filters)
    exits_by_name = {
        spec.name: spec for spec in (*mii.full_exit_specs(), *mii.coarse_exit_specs())
    }
    exits = list(exits_by_name.values())

    raw = load_symbol_frame(args.symbol, end=REUSED_END)[
        ["ts", "open", "high", "low", "close", "volume"]
    ].copy()
    all_signal_specs = mii.signal_specs()
    spans = sorted(
        {value for spec in all_signal_specs for value in (spec.fast, spec.slow) if value}
    )
    features = mii.add_features(raw, spans)
    market = mii.build_market_arrays(features)

    ranking: list[dict[str, Any]] = []
    evaluated = 0
    simulated = 0
    for signal_no, signal_spec in enumerate(signals, start=1):
        state = mii.signal_state(features, signal_spec)
        for exit_spec in exits:
            raw_trades = mii.simulate_trades(market, state, exit_spec)
            simulated += 1
            if len(raw_trades) < 12:
                continue
            for filter_spec in filters:
                evaluated += 1
                picked = mii.selected_trades(raw_trades, filter_spec)
                row = {
                    "signal": asdict(signal_spec),
                    "exit": asdict(exit_spec),
                    "filter": asdict(filter_spec),
                    "filter_name": filter_spec.name,
                    "asset_start": STARTS[args.symbol],
                    "prefit": window_metric(picked, STARTS[args.symbol], PREFIT_END),
                    "historical_oos": window_metric(
                        picked, PREFIT_END, HISTORICAL_OOS_END
                    ),
                    "current_3m": window_metric(
                        picked, HISTORICAL_OOS_END, REUSED_END
                    ),
                    "through_current": window_metric(
                        picked, STARTS[args.symbol], REUSED_END
                    ),
                }
                row["score"] = score(row)
                if row["score"] <= -1e8:
                    continue
                ranking.append(row)
            if len(ranking) > max(args.top * 30, 5000):
                ranking.sort(key=lambda row: row["score"], reverse=True)
                del ranking[max(args.top * 10, 2400) :]
        print(
            f"{args.symbol} signals={signal_no}/{len(signals)} "
            f"simulated={simulated} evaluated={evaluated} kept={len(ranking)}",
            flush=True,
        )

    ranking.sort(key=lambda row: row["score"], reverse=True)
    for row in ranking:
        row["asset_start"] = row["asset_start"].isoformat()
    hard80 = [
        row
        for row in ranking
        if all(
            row[name]["trades"] >= 8
            and row[name]["win_rate"] >= 0.80
            and row[name]["total_return"] > 0.0
            and row[name]["max_dd"] > -0.20
            for name in ("prefit", "historical_oos", "current_3m")
        )
    ]
    output = OUTPUT_DIR / f"{args.symbol.lower()}_hf_exit_tune_2026-07-14.json"
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "full_exit_tune_discovery_only_not_live_ready",
        "symbol": args.symbol,
        "source": str(source_path.relative_to(ROOT)),
        "search_space": {
            "signals": len(signals),
            "filters": len(filters),
            "exits": len(exits),
            "simulated": simulated,
            "evaluated": evaluated,
        },
        "hard80_count_before_robust_replay": len(hard80),
        "disclosure": (
            "Current 3m participates in research ranking. Funding, gap-safe fills, "
            "8bps and K+2 replay remain mandatory before portfolio use."
        ),
        "ranking": ranking[: args.top],
        "hard80": hard80[: args.top],
    }
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "symbol": args.symbol,
                "output": str(output),
                "hard80": len(hard80),
                "best": ranking[0] if ranking else None,
            },
            indent=2,
            default=str,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
