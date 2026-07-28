"""Extract EMA21/96 cross events with 3-bracket labels for BIN-15M-EMAX-LGBM.

One row per training-pool-eligible event, with first-touch labels, funding, and
net returns for every pre-registered bracket candidate. Development window only
by default; the locked OOS (2026-01..2026-06) requires EMAX_OOS_REVEAL=1 and
--include-locked-oos (reveal script only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

import emax_common as ec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="*", help="Optional sym_key subset (e.g. BTC ETH).")
    parser.add_argument("--output", type=Path, default=ec.ARTIFACT_DIR / "events_dev.parquet")
    parser.add_argument("--rebuild-cache", action="store_true")
    parser.add_argument("--include-locked-oos", action="store_true")
    parser.add_argument(
        "--min-entry-ts",
        default=None,
        help="Optional lower bound on entry_ts (e.g. 2025-11-01 for the OOS reveal).",
    )
    parser.add_argument("--workers", type=int, default=6)
    return parser.parse_args()


def to_ns(values: pd.Series) -> np.ndarray:
    return values.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy(dtype="datetime64[ns]")


def extract_symbol(
    sym_key: str,
    eligibility: pd.DataFrame,
    funding_lookup: dict[str, tuple[np.ndarray, np.ndarray]],
    *,
    entry_cutoff: pd.Timestamp,
    entry_floor: pd.Timestamp,
) -> pd.DataFrame | None:
    frame = ec.load_symbol_frame(sym_key)
    if len(frame) < ec.WARMUP_BARS + ec.HORIZON_BARS + 2:
        return None
    frame = ec.compute_indicators(frame)
    golden, death = ec.detect_cross_indices(frame)

    ts = frame["ts"]
    ts_ns = to_ns(ts)
    open_ = frame["open"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    atr_all = frame["atr"].to_numpy(dtype=float)

    elig = eligibility.loc[eligibility["sym_key"] == sym_key]
    elig_map = elig.set_index("day")[["eligible", "in_trading_pool", "adv_30d"]]

    outputs = []
    for side, signal_idx in ((1, golden), (-1, death)):
        signal_idx = signal_idx[signal_idx >= ec.WARMUP_BARS]
        entry_idx = signal_idx + 1
        keep = entry_idx + ec.HORIZON_BARS <= len(frame) - 1
        signal_idx, entry_idx = signal_idx[keep], entry_idx[keep]
        if len(signal_idx) == 0:
            continue
        entry_ts = ts.iloc[entry_idx]
        in_window = (entry_ts >= entry_floor) & (entry_ts <= entry_cutoff)
        signal_idx, entry_idx = signal_idx[in_window.to_numpy()], entry_idx[in_window.to_numpy()]
        if len(signal_idx) == 0:
            continue

        atr = atr_all[signal_idx]
        entry_price = open_[entry_idx]
        valid = (atr > 0) & (entry_price > 0) & np.isfinite(atr)
        signal_idx, entry_idx = signal_idx[valid], entry_idx[valid]
        atr, entry_price = atr[valid], entry_price[valid]
        if len(signal_idx) == 0:
            continue

        entry_days = ts.iloc[entry_idx].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)
        joined = elig_map.reindex(entry_days.to_numpy())
        eligible = joined["eligible"].fillna(False).to_numpy(dtype=bool)
        if not eligible.any():
            continue
        pool = joined["in_trading_pool"].fillna(False).to_numpy(dtype=bool)[eligible]
        adv = joined["adv_30d"].to_numpy(dtype=float)[eligible]
        signal_idx, entry_idx = signal_idx[eligible], entry_idx[eligible]
        atr, entry_price = atr[eligible], entry_price[eligible]

        atr_frac = atr / entry_price
        row = {
            "sym_key": sym_key,
            "side": side,
            "signal_idx": signal_idx,
            "signal_ts": ts.iloc[signal_idx].to_numpy(),
            "entry_ts": ts.iloc[entry_idx].to_numpy(),
            "entry_price": entry_price,
            "atr": atr,
            "atr_frac": atr_frac,
            "cost_atr": ec.ROUND_TRIP_COST / atr_frac,
            "in_trading_pool": pool,
            "adv_30d": adv,
        }
        entry_ns = ts_ns[entry_idx]
        fund_ts, fund_cum = funding_lookup.get(sym_key, (np.array([], dtype="datetime64[ns]"), np.array([0.0])))
        for name, (k_tp, k_sl) in ec.BRACKETS.items():
            outcome = ec.label_bracket(
                open_, high, low, entry_idx, side, entry_price, atr, k_tp, k_sl
            )
            exit_ns = ts_ns[outcome.exit_index]
            funding = ec.funding_cost(fund_ts, fund_cum, entry_ns, exit_ns, side)
            net_frac = outcome.gross_ret - ec.ROUND_TRIP_COST - funding
            row[f"{name}_label"] = outcome.label
            row[f"{name}_exit_ts"] = ts.iloc[outcome.exit_index].to_numpy()
            row[f"{name}_holding_bars"] = outcome.holding_bars
            row[f"{name}_gross_frac"] = outcome.gross_ret
            row[f"{name}_funding_frac"] = funding
            row[f"{name}_net_frac"] = net_frac
            row[f"{name}_net_atr"] = net_frac / atr_frac
            row[f"{name}_gross_atr"] = outcome.gross_ret / atr_frac
        outputs.append(pd.DataFrame(row))
    if not outputs:
        return None
    return pd.concat(outputs, ignore_index=True)


def main() -> None:
    args = parse_args()
    entry_cutoff = ec.DEV_ENTRY_CUTOFF
    if args.include_locked_oos:
        if os.environ.get("EMAX_OOS_REVEAL") != "1":
            raise RuntimeError(
                "locked OOS extraction requires EMAX_OOS_REVEAL=1; "
                "development scripts must not read the locked window"
            )
        entry_cutoff = ec.LOCKED_OOS_END
    entry_floor = (
        pd.Timestamp(args.min_entry_ts, tz="UTC") if args.min_entry_ts else ec.DEV_START
    )

    print("building symbol partition cache (one-off)...", flush=True)
    ec.ensure_symbol_partition_cache(rebuild=args.rebuild_cache)
    daily = ec.build_daily_stats(rebuild=args.rebuild_cache)
    universe = ec.build_universe(daily)
    print(
        f"universe: {daily['sym_key'].nunique()} symbols, "
        f"{int(universe.eligibility['eligible'].sum())} eligible symbol-days",
        flush=True,
    )

    funding = ec.load_funding()
    funding_lookup = {
        key: ec.prepare_funding_lookup(group)
        for key, group in funding.groupby("sym_key", sort=False)
    }

    symbols = args.symbols or ec.list_cached_symbols()
    frames: list[pd.DataFrame] = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                extract_symbol,
                sym_key,
                universe.eligibility,
                funding_lookup,
                entry_cutoff=entry_cutoff,
                entry_floor=entry_floor,
            ): sym_key
            for sym_key in symbols
        }
        done = 0
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                frames.append(result)
            done += 1
            if done % 100 == 0 or done == len(futures):
                print(f"extract {done}/{len(futures)} ({time.monotonic() - started:.0f}s)", flush=True)

    events = pd.concat(frames, ignore_index=True).sort_values(["entry_ts", "sym_key"])
    events = events.reset_index(drop=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    events.to_parquet(args.output, index=False, compression="zstd")
    sha = hashlib.sha256(args.output.read_bytes()).hexdigest()

    manifest = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-15m-emax-lgbm-research-contract-2026-07-23.md",
        "window": {
            "entry_floor": str(entry_floor),
            "entry_cutoff": str(entry_cutoff),
            "locked_oos_included": bool(args.include_locked_oos),
        },
        "signal": {"ema_fast": ec.EMA_FAST, "ema_slow": ec.EMA_SLOW, "atr_len": ec.ATR_LEN},
        "brackets": ec.BRACKETS,
        "costs": {
            "fee_per_fill": ec.FEE_PER_FILL,
            "slip_per_fill": ec.SLIP_PER_FILL,
            "round_trip": ec.ROUND_TRIP_COST,
            "funding": "as-of actual per event",
        },
        "universe": {
            "min_listing_days": ec.MIN_LISTING_DAYS,
            "min_adv_usdt": ec.MIN_ADV_USDT,
            "min_coverage": ec.MIN_COVERAGE,
            "delist_guard_days": ec.DELIST_GUARD_DAYS,
            "trading_pool_size": ec.TRADING_POOL_SIZE,
        },
        "rows": len(events),
        "long_events": int((events["side"] == 1).sum()),
        "short_events": int((events["side"] == -1).sum()),
        "symbols": int(events["sym_key"].nunique()),
        "trading_pool_rows": int(events["in_trading_pool"].sum()),
        "output": str(args.output.relative_to(ec.ROOT)),
        "output_sha256": sha,
    }
    manifest_path = args.output.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps({k: manifest[k] for k in ["rows", "long_events", "short_events", "symbols", "trading_pool_rows"]}, indent=2))
    print(f"events -> {args.output}")


if __name__ == "__main__":
    main()
