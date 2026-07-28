"""Relabel the frozen dev events with an arbitrary TP/SL bracket (diagnostic).

Post-archive Q&A tool: answers "what if the bracket were X/Y" on the
development window only. Reads events_dev.parquet (signal_idx per event) and
the existing symbol cache; never touches the locked/revealed OOS window.
Same conservative fill rules and 96-bar horizon as the frozen contract.

Usage: relabel_custom_bracket.py --tp 5 --sl 7
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

import emax_common as ec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tp", type=float, required=True)
    parser.add_argument("--sl", type=float, required=True)
    return parser.parse_args()


def relabel_symbol(
    sym_key: str,
    events: pd.DataFrame,
    funding_lookup: dict[str, tuple[np.ndarray, np.ndarray]],
    k_tp: float,
    k_sl: float,
) -> pd.DataFrame:
    frame = ec.load_symbol_frame(sym_key)
    ts_ns = (
        frame["ts"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy(dtype="datetime64[ns]")
    )
    open_ = frame["open"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)

    out = []
    for side, group in events.groupby("side", sort=False):
        entry_idx = group["signal_idx"].to_numpy(dtype=np.int64) + 1
        entry_price = group["entry_price"].to_numpy(dtype=float)
        atr = group["atr"].to_numpy(dtype=float)
        # sanity: cached frames must match the frozen extraction
        if not np.allclose(open_[entry_idx], entry_price):
            raise RuntimeError(f"entry price mismatch for {sym_key}; cache changed?")
        outcome = ec.label_bracket(
            open_, high, low, entry_idx, int(side), entry_price, atr, k_tp, k_sl
        )
        fund_ts, fund_cum = funding_lookup.get(
            sym_key, (np.array([], dtype="datetime64[ns]"), np.array([0.0]))
        )
        entry_ns = ts_ns[entry_idx]
        exit_ns = ts_ns[outcome.exit_index]
        funding = ec.funding_cost(fund_ts, fund_cum, entry_ns, exit_ns, int(side))
        net_frac = outcome.gross_ret - ec.ROUND_TRIP_COST - funding
        atr_frac = group["atr_frac"].to_numpy(dtype=float)
        out.append(
            pd.DataFrame(
                {
                    "sym_key": sym_key,
                    "side": int(side),
                    "entry_ts": group["entry_ts"].to_numpy(),
                    "in_trading_pool": group["in_trading_pool"].to_numpy(),
                    "label": outcome.label,
                    "holding_bars": outcome.holding_bars,
                    "gross_atr": outcome.gross_ret / atr_frac,
                    "net_atr": net_frac / atr_frac,
                }
            )
        )
    return pd.concat(out, ignore_index=True)


def summarize(frame: pd.DataFrame) -> dict:
    return {
        "events": int(len(frame)),
        "sl_first": round(float((frame["label"] == 0).mean()), 4),
        "tp_first": round(float((frame["label"] == 1).mean()), 4),
        "timeout": round(float((frame["label"] == 2).mean()), 4),
        "gross_mean_atr": round(float(frame["gross_atr"].mean()), 4),
        "net_mean_atr": round(float(frame["net_atr"].mean()), 4),
        "share_net_positive": round(float((frame["net_atr"] > 0).mean()), 4),
        "median_holding_bars": int(frame["holding_bars"].median()),
    }


def main() -> None:
    args = parse_args()
    events = pd.read_parquet(ec.ARTIFACT_DIR / "events_dev.parquet")
    funding = ec.load_funding()
    funding_lookup = {
        key: ec.prepare_funding_lookup(group)
        for key, group in funding.groupby("sym_key", sort=False)
    }

    frames = []
    started = time.monotonic()
    groups = dict(tuple(events.groupby("sym_key", sort=False)))
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(relabel_symbol, key, group, funding_lookup, args.tp, args.sl): key
            for key, group in groups.items()
        }
        done = 0
        for future in as_completed(futures):
            frames.append(future.result())
            done += 1
            if done % 100 == 0 or done == len(futures):
                print(f"relabel {done}/{len(futures)} ({time.monotonic() - started:.0f}s)", flush=True)
    labeled = pd.concat(frames, ignore_index=True)

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "bracket": {"tp_atr": args.tp, "sl_atr": args.sl},
        "window": "development only (2020-01..2025-12); locked OOS untouched",
        "horizon_bars": ec.HORIZON_BARS,
        "cost_model": "fee 0.001 + slip 4bps per fill + as-of funding",
        "all": summarize(labeled),
        "long": summarize(labeled.loc[labeled["side"] == 1]),
        "short": summarize(labeled.loc[labeled["side"] == -1]),
        "trading_pool": summarize(labeled.loc[labeled["in_trading_pool"]]),
    }
    tag = f"tp{args.tp:g}_sl{args.sl:g}".replace(".", "p")
    output = ec.ARTIFACT_DIR / f"custom_bracket_{tag}.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"report -> {output}")


if __name__ == "__main__":
    main()
