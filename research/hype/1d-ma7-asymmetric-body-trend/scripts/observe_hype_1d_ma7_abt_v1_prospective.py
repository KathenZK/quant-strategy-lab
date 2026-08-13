"""V1 prospective observation harness (protocol 2026-08-06).

Runs the frozen V1 pair (group 041) as a deterministic full replay on the
extended lake, after an anchor re-computation check that truncates the
hourly/funding data back to the frozen lake end (2026-07-30 04:00 UTC) and
must reproduce the registered full-window numbers exactly. Only the
observation window (>= 2026-07-30 00:00 UTC) is reported as new evidence.

See specs/hype-1d-ma7-abt-v1-prospective-observation-protocol-2026-08-06.md.
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

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BASE_SCRIPT = FAMILY_DIR / "scripts/research_hype_1d_ma7_asymmetric_body_trend.py"
SEARCH_SCRIPT = FAMILY_DIR / "scripts/search_hype_1d_ma7_separated_trend.py"
FROZEN_SUMMARY = ARTIFACT_DIR / "hype_1d_ma7_separated_summary_2026-08-04.json"

ANCHOR_CUTOFF = pd.Timestamp("2026-07-30T04:00:00Z")
OBS_START = pd.Timestamp("2026-07-30T00:00:00Z")


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


def frozen_identity() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    payload = json.loads(FROZEN_SUMMARY.read_text(encoding="utf-8"))
    candidate = payload["historically_profitable_all_checks"][0]
    if candidate["label"] != "post_reveal_combined_observation_041":
        raise RuntimeError(f"unexpected frozen candidate: {candidate['label']}")
    return (
        candidate["long_config"],
        candidate["short_config"],
        candidate["windows"]["full"]["base"],
    )


def run_replay(
    base: Any,
    search: Any,
    parent: Any,
    hourly: pd.DataFrame,
    hourly_quality: dict[str, Any],
    funding: pd.DataFrame,
    funding_quality: dict[str, Any],
    long_config: Any,
    short_config: Any,
    *,
    slippage: float,
    retain: bool,
) -> tuple[Any, Any]:
    book = base.build_book(
        parent, hourly, hourly_quality, funding, funding_quality, phase_hours=0
    )
    features = search.build_features(book, hourly, funding)
    result = search.backtest(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=0,
        terminal_index=book.count,
        slippage=slippage,
        retain=retain,
    )
    return book, result


def main() -> None:
    args = parse_args()
    base = load_module(BASE_SCRIPT, "abt_base_obs")
    search = load_module(SEARCH_SCRIPT, "abt_search_obs")
    parent = base.load_parent()
    engine = parent.load_engine()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    long_dict, short_dict, frozen_full = frozen_identity()
    long_config = search.Config(**long_dict)
    short_config = search.Config(**short_dict)

    hourly, hourly_quality = engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = engine.load_and_audit_funding(ROOT)
    hourly["ts"] = pd.to_datetime(hourly["ts"], utc=True)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)

    # --- anchor re-computation check (protocol section 2) ---
    hourly_anchor = hourly.loc[hourly["ts"] <= ANCHOR_CUTOFF].copy()
    funding_anchor = funding.loc[funding["ts"] <= ANCHOR_CUTOFF].copy()
    _, anchor_result = run_replay(
        base, search, parent,
        hourly_anchor, hourly_quality, funding_anchor, funding_quality,
        long_config, short_config,
        slippage=search.BASE_SLIPPAGE, retain=False,
    )
    anchor = anchor_result.metrics
    checks = {
        "equity_multiple": (anchor["equity_multiple"], frozen_full["equity_multiple"]),
        "max_drawdown_pct": (anchor["max_drawdown_pct"], frozen_full["max_drawdown_pct"]),
        "closed_trades": (anchor["closed_trades"], frozen_full["closed_trades"]),
    }
    for name, (got, expected) in checks.items():
        if not math.isclose(float(got), float(expected), rel_tol=1e-9, abs_tol=1e-9):
            raise RuntimeError(
                f"anchor check failed on {name}: replay {got} vs frozen {expected}"
            )

    # --- extended replay (observation) ---
    book, result = run_replay(
        base, search, parent,
        hourly, hourly_quality, funding, funding_quality,
        long_config, short_config,
        slippage=search.BASE_SLIPPAGE, retain=True,
    )
    _, stress_result = run_replay(
        base, search, parent,
        hourly, hourly_quality, funding, funding_quality,
        long_config, short_config,
        slippage=search.STRESS_SLIPPAGE, retain=True,
    )

    def window_slice(res: Any) -> tuple[pd.DataFrame, float, float]:
        path = pd.DataFrame(res.path)
        path["ts"] = pd.to_datetime(path["ts"], utc=True)
        window = path.loc[path["ts"] >= OBS_START].copy()
        if window.empty:
            raise RuntimeError("no observation-window path rows")
        # equity marked exactly at the window-start open: pre-window price
        # moves (e.g. the 07-29 -> 07-30 overnight mark) stay outside
        base_equity = float(window["pre_action_equity"].iloc[0])
        end_equity = float(window["post_action_equity"].iloc[-1])
        return window, base_equity, end_equity

    window, base_equity, end_equity = window_slice(result)
    window_stress, stress_base, stress_end = window_slice(stress_result)

    trades = pd.DataFrame(result.trades)
    if not trades.empty:
        trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
        trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
        window_trades = trades.loc[trades["exit_ts"] >= OBS_START].copy()
    else:
        window_trades = trades

    funding_events_in_window = int(
        ((funding["ts"] >= OBS_START) & (funding["ts"] <= book.terminal_ts)).sum()
    )
    obs_days = pd.DatetimeIndex(book.ts)
    obs_days = obs_days[obs_days >= OBS_START]
    open_at_start = float(book.open[list(book.ts).index(obs_days[0])])
    hold_gross = float(book.quality["terminal_open"]) / open_at_start - 1.0

    actions = window.loc[~window["action"].isin(["hold", "terminal"])]
    position_at_start = int(window["position"].iloc[0]) if len(window) else 0

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "protocol": "specs/hype-1d-ma7-abt-v1-prospective-observation-protocol-2026-08-06.md",
        "observation_number": 1,
        "anchor_check": {
            "cutoff": ANCHOR_CUTOFF.isoformat(),
            "passed": True,
            **{k: {"replay": v[0], "frozen": v[1]} for k, v in checks.items()},
        },
        "window": {
            "start": OBS_START.isoformat(),
            "end_terminal_open": book.terminal_ts.isoformat(),
            "complete_days": int(len(obs_days)),
        },
        "base_4bps": {
            "net_return_pct": (end_equity / base_equity - 1.0) * 100.0,
            "equity_at_window_start_open": base_equity,
            "equity_at_terminal": end_equity,
        },
        "stress_8bps": {
            "net_return_pct": (stress_end / stress_base - 1.0) * 100.0,
        },
        "position_at_window_start": position_at_start,
        "actions_in_window": actions[["ts", "action", "position"]].astype(str).to_dict("records"),
        "closed_trades_in_window": int(len(window_trades)),
        "funding_events_in_window": funding_events_in_window,
        "buy_hold_gross_return_pct": hold_gross * 100.0,
        "cumulative_since_protocol": {
            "days": int(len(obs_days)),
            "closed_trades": int(len(window_trades)),
            "net_return_pct": (end_equity / base_equity - 1.0) * 100.0,
        },
        "full_replay_reference": {
            "base": result.metrics,
            "stress_8bps": stress_result.metrics,
        },
    }

    prefix = f"hype_1d_v1_prospective_obs_{args.run_date}"
    window.to_csv(ARTIFACT_DIR / f"{prefix}_path.csv", index=False)
    window_trades.to_csv(ARTIFACT_DIR / f"{prefix}_trades.csv", index=False)
    out = ARTIFACT_DIR / f"{prefix}_summary.json"
    out.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print("anchor check passed (replay == frozen V1 numbers)")
    print(
        f"observation window {OBS_START.date()} -> {book.terminal_ts.date()} "
        f"({len(obs_days)} complete days): net {summary['base_4bps']['net_return_pct']:+.2f}% "
        f"(stress {summary['stress_8bps']['net_return_pct']:+.2f}%), "
        f"trades closed {len(window_trades)}, position at start {position_at_start}, "
        f"buy&hold gross {hold_gross * 100.0:+.2f}%"
    )
    print("report ->", out)


if __name__ == "__main__":
    main()
