"""V1 pending audits: long first-day protection, phase grid, start-point grid.

Closes the two audit gaps recorded in the family core ledger without
changing V1 identity:

1. long first-day protection: V1 longs carry no hard stop on the first
   holding day. Quantify the historical first-day intraday MAE of every
   long trade (hourly lows vs entry fill) and how often hypothetical
   first-day stops at k*ATR7 would have been touched. Diagnostic only.
2. phase audit: rebuild the daily book at all 24 hourly day-boundary
   offsets and replay the frozen V1 pair on each.
3. start-point audit: replay from each of the first 60 daily start
   indices on the phase-0 book.

Uses the frozen configs from the registered search summary and the same
engine as the observation harness. Anchor-grade determinism is inherited
from the observation harness run of the same date.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BASE_SCRIPT = FAMILY_DIR / "scripts/research_hype_1d_ma7_asymmetric_body_trend.py"
SEARCH_SCRIPT = FAMILY_DIR / "scripts/search_hype_1d_ma7_separated_trend.py"
FROZEN_SUMMARY = ARTIFACT_DIR / "hype_1d_ma7_separated_summary_2026-08-04.json"

STOP_GRID = (1.0, 1.5, 2.0, 3.0)
START_POINTS = 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    return parser.parse_args()


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    args = parse_args()
    base = load_module(BASE_SCRIPT, "abt_base_audit")
    search = load_module(SEARCH_SCRIPT, "abt_search_audit")
    parent = base.load_parent()
    engine = parent.load_engine()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    payload = json.loads(FROZEN_SUMMARY.read_text(encoding="utf-8"))
    candidate = payload["historically_profitable_all_checks"][0]
    long_config = search.Config(**candidate["long_config"])
    short_config = search.Config(**candidate["short_config"])

    hourly, hourly_quality = engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = engine.load_and_audit_funding(ROOT)
    hourly["ts"] = pd.to_datetime(hourly["ts"], utc=True)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)

    def build(phase: int) -> tuple[Any, Any]:
        book = base.build_book(
            parent, hourly, hourly_quality, funding, funding_quality,
            phase_hours=phase,
        )
        return book, search.build_features(book, hourly, funding)

    def replay(book: Any, features: Any, *, start: int = 0, retain: bool = False) -> Any:
        return search.backtest(
            book,
            features,
            long_config=long_config,
            short_config=short_config,
            start_index=start,
            terminal_index=book.count,
            retain=retain,
        )

    # --- 1. long first-day protection audit (phase 0) -------------------------
    book0, feats0 = build(0)
    full = replay(book0, feats0, retain=True)
    day_index = {pd.Timestamp(ts): i for i, ts in enumerate(book0.ts)}
    first_day_rows = []
    for trade in full.trades:
        if trade["side"] != "long":
            continue
        entry_ts = pd.Timestamp(trade["entry_ts"])
        idx = day_index[entry_ts.floor("1D")]
        entry_price = float(trade["entry_price"])
        atr = float(feats0.atr7[idx - 1])
        day_low = float(np.nanmin(feats0.hourly_low[idx]))
        day_close = float(book0.close[idx])
        mae_pct = (day_low / entry_price - 1.0) * 100.0
        row = {
            "entry_ts": entry_ts.isoformat(),
            "entry_price": entry_price,
            "signal_day_atr7": atr,
            "first_day_low": day_low,
            "first_day_close": day_close,
            "first_day_mae_pct": mae_pct,
            "first_day_mae_atr": (entry_price - day_low) / atr if atr > 0 else math.nan,
            "first_day_close_pct": (day_close / entry_price - 1.0) * 100.0,
            "trade_net_return_pct": float(trade["net_return"]) * 100.0,
        }
        for k in STOP_GRID:
            row[f"stop_{k}atr_touched"] = day_low <= entry_price - k * atr
        first_day_rows.append(row)
    first_day = pd.DataFrame(first_day_rows)

    # --- 2. phase audit --------------------------------------------------------
    phase_rows = []
    for phase in range(24):
        try:
            book_p, feats_p = build(phase)
            res = replay(book_p, feats_p)
            m = res.metrics
            phase_rows.append(
                {
                    "phase_hours": phase,
                    "days": book_p.count,
                    "equity_multiple": m["equity_multiple"],
                    "net_return_pct": m["net_return_pct"],
                    "max_drawdown_pct": m["max_drawdown_pct"],
                    "closed_trades": m["closed_trades"],
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 - record and continue
            phase_rows.append(
                {
                    "phase_hours": phase,
                    "days": None,
                    "equity_multiple": None,
                    "net_return_pct": None,
                    "max_drawdown_pct": None,
                    "closed_trades": None,
                    "error": str(exc)[:200],
                }
            )
    phases = pd.DataFrame(phase_rows)

    # --- 3. start-point audit (phase 0) ----------------------------------------
    start_rows = []
    for start in range(START_POINTS):
        res = replay(book0, feats0, start=start)
        m = res.metrics
        start_rows.append(
            {
                "start_index": start,
                "start_ts": pd.Timestamp(book0.ts[start]).isoformat(),
                "net_return_pct": m["net_return_pct"],
                "max_drawdown_pct": m["max_drawdown_pct"],
                "closed_trades": m["closed_trades"],
            }
        )
    starts = pd.DataFrame(start_rows)

    valid = phases.dropna(subset=["net_return_pct"])
    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "data_last_day": pd.Timestamp(book0.ts[-1]).isoformat(),
        "long_first_day": {
            "long_trades": int(len(first_day)),
            "worst_mae_pct": float(first_day["first_day_mae_pct"].min()) if len(first_day) else None,
            "median_mae_pct": float(first_day["first_day_mae_pct"].median()) if len(first_day) else None,
            "worst_mae_atr": float(first_day["first_day_mae_atr"].max()) if len(first_day) else None,
            "hypothetical_stop_touches": {
                f"{k}xATR7": int(first_day[f"stop_{k}atr_touched"].sum())
                for k in STOP_GRID
            }
            if len(first_day)
            else {},
        },
        "phase_grid": {
            "phases_ok": int(len(valid)),
            "net_return_pct_min": float(valid["net_return_pct"].min()),
            "net_return_pct_median": float(valid["net_return_pct"].median()),
            "net_return_pct_max": float(valid["net_return_pct"].max()),
            "negative_phases": int((valid["net_return_pct"] < 0).sum()),
            "worst_mdd_pct": float(valid["max_drawdown_pct"].min()),
        },
        "start_points": {
            "count": int(len(starts)),
            "net_return_pct_min": float(starts["net_return_pct"].min()),
            "net_return_pct_median": float(starts["net_return_pct"].median()),
            "net_return_pct_max": float(starts["net_return_pct"].max()),
            "negative_starts": int((starts["net_return_pct"] < 0).sum()),
        },
    }

    prefix = f"hype_1d_v1_protection_phase_audit_{args.run_date}"
    first_day.to_csv(ARTIFACT_DIR / f"{prefix}_first_day.csv", index=False)
    phases.to_csv(ARTIFACT_DIR / f"{prefix}_phases.csv", index=False)
    starts.to_csv(ARTIFACT_DIR / f"{prefix}_starts.csv", index=False)
    out = ARTIFACT_DIR / f"{prefix}_summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("report ->", out)


if __name__ == "__main__":
    main()
