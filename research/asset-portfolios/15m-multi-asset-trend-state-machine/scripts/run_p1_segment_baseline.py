#!/usr/bin/env python
"""BIN-15M-TSM P1 segment-level naked baseline.

Implements the frozen research contract
(specs/bin-15m-tsm-research-contract-2026-07-28.md):

- Three-state trend machine per symbol on closed 15m bars:
  spread_atr = (EMA_fast - EMA_slow) / ATR672.
  Enter LONG after `confirm` consecutive closed bars with spread_atr >= +th_in;
  exit to FLAT after `confirm` consecutive bars with spread_atr <= +th_out.
  SHORT symmetric. No direct flip: reverse confirmation counting restarts
  after the FLAT transition (implemented as run-start >= flat_since).
- Execution: state confirmed at bar t close -> position change at bar t+1 open.
  Entry additionally requires pool membership on both the confirm bar and the
  execution bar; leaving the pool force-closes at the first bar of the first
  non-member day (reason=pool_exit). Dev-window end closes remaining segments
  at the last dev bar open (reason=window_end).
- Costs: 0.001 fee + 4 bps adverse slippage per fill (0.0028 round trip);
  funding signed as-of over (entry_ts, exit_ts]; ATR-unit normalization uses
  ATR672 at the entry confirm bar divided by the entry fill price.
- Dev window only: bars with ts < 2026-01-01 UTC. The locked OOS window is
  never read.

Data loading, point-in-time universe, and funding reuse the frozen loaders of
BIN-15M-EMAX-LGBM (`emax_common.py`), read-only.

Canonical combo runs on both the training pool and the trading pool with full
per-segment output; the pre-registered 54-combo sensitivity set runs on the
trading pool with aggregate stats only.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
EMAX_SCRIPTS = (
    ROOT / "research/asset-portfolios/15m-ema-cross-lightgbm-event-selector/scripts"
)
sys.path.insert(0, str(EMAX_SCRIPTS))
import emax_common as ec  # noqa: E402  (frozen shared loaders, read-only)

FAMILY_DIR = ROOT / "research/asset-portfolios/15m-multi-asset-trend-state-machine"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"

RUN_DATE = "2026-07-28"

# --- frozen contract constants ---------------------------------------------
DEV_END = pd.Timestamp("2026-01-01", tz="UTC")
COST_PER_FILL = 0.001 + 0.0004
ROUND_TRIP_COST = 2.0 * COST_PER_FILL
ATR_LEN = 672

CORES = {"ema96_384": (96, 384), "ema336_1536": (336, 1536)}
TH_INS = [0.75, 1.0, 1.5]
TH_OUTS = [0.0, 0.25, 0.5]
CONFIRMS = [1, 4, 8]
CANONICAL = ("ema96_384", 1.0, 0.25, 4)

# P1 gates (frozen)
GATE_MIN_MEDIAN_HOLD_BARS = 96
GATE_MAX_ROUND_TRIPS_PER_POOL_YEAR = 60.0
GATE_ONE_SIDE_MIN_ATR = 0.10

RECENT_SLICES = {
    "1d": pd.Timedelta(days=1),
    "7d": pd.Timedelta(days=7),
    "1m": pd.Timedelta(days=30),
    "3m": pd.Timedelta(days=91),
    "6m": pd.Timedelta(days=182),
    "1y": pd.Timedelta(days=365),
}


def load_bars(sym_key: str) -> pd.DataFrame:
    """Load per-symbol bars; duckdb hive partitions URL-encode non-ASCII keys."""
    from urllib.parse import quote

    if (ec.symbol_cache_dir() / f"sym_key={sym_key}").is_dir():
        return ec.load_symbol_frame(sym_key)
    return ec.load_symbol_frame(quote(sym_key, safe=""))


def runlen(cond: np.ndarray) -> np.ndarray:
    """Length of the consecutive True run ending at each index (0 where False)."""
    n = len(cond)
    idx = np.arange(n)
    last_false = np.maximum.accumulate(np.where(~cond, idx, -1))
    return idx - last_false


def simulate(
    n: int,
    gate: np.ndarray,
    gate_true_pos: np.ndarray,
    gate_false_pos: np.ndarray,
    pos_enter_long: np.ndarray,
    pos_enter_short: np.ndarray,
    pos_exit_long: np.ndarray,
    pos_exit_short: np.ndarray,
    confirm: int,
) -> list[tuple[int, int, int, str]]:
    """Sequential state machine scan. Returns (side, entry_bar, exit_bar, reason)."""
    segments: list[tuple[int, int, int, str]] = []
    flat_since = 0
    while True:
        p = flat_since + confirm - 1
        # --- find entry confirm bar t with membership on confirm bar ---
        while True:
            i_long = np.searchsorted(pos_enter_long, p)
            i_short = np.searchsorted(pos_enter_short, p)
            cand_long = pos_enter_long[i_long] if i_long < len(pos_enter_long) else n
            cand_short = (
                pos_enter_short[i_short] if i_short < len(pos_enter_short) else n
            )
            t = min(cand_long, cand_short)
            if t >= n:
                return segments
            if cand_long == cand_short:  # impossible for th_in > 0; skip defensively
                p = t + 1
                continue
            side = 1 if cand_long < cand_short else -1
            if gate[t]:
                break
            j = np.searchsorted(gate_true_pos, t)
            if j >= len(gate_true_pos):
                return segments
            p = max(gate_true_pos[j], p + 1)
        entry_bar = t + 1
        if entry_bar >= n:
            return segments
        if not gate[entry_bar]:  # membership lapsed on the execution bar
            flat_since = entry_bar
            continue
        # --- find exit ---
        pos_exit = pos_exit_long if side == 1 else pos_exit_short
        k = np.searchsorted(pos_exit, entry_bar)
        state_exec = pos_exit[k] + 1 if k < len(pos_exit) else n
        g = np.searchsorted(gate_false_pos, entry_bar)
        pool_exec = gate_false_pos[g] if g < len(gate_false_pos) else n
        exit_bar = min(state_exec, pool_exec, n - 1)
        if exit_bar == state_exec and state_exec <= pool_exec:
            reason = "state_exit"
        elif exit_bar == pool_exec and pool_exec < state_exec:
            reason = "pool_exit"
        else:
            reason = "window_end"
        segments.append((side, entry_bar, exit_bar, reason))
        flat_since = exit_bar
        if exit_bar >= n - 1:
            return segments


def segment_frame(
    sym_key: str,
    combo_id: str,
    pool_name: str,
    raw_segments: list[tuple[int, int, int, str]],
    ts: np.ndarray,
    open_: np.ndarray,
    atr: np.ndarray,
    fund_ts: np.ndarray,
    fund_cum: np.ndarray,
) -> pd.DataFrame | None:
    if not raw_segments:
        return None
    side = np.array([s[0] for s in raw_segments], dtype=np.int8)
    e = np.array([s[1] for s in raw_segments], dtype=np.int64)
    x = np.array([s[2] for s in raw_segments], dtype=np.int64)
    reason = np.array([s[3] for s in raw_segments])
    entry_px = open_[e]
    exit_px = open_[x]
    gross = side * (exit_px / entry_px - 1.0)
    if len(fund_ts):
        lo = np.searchsorted(fund_ts, ts[e], side="right")
        hi = np.searchsorted(fund_ts, ts[x], side="right")
        funding = side * (fund_cum[hi] - fund_cum[lo])
    else:
        funding = np.zeros(len(e))
    net_pct = gross - ROUND_TRIP_COST - funding
    atr_pct = atr[e - 1] / entry_px
    valid = np.isfinite(atr_pct) & (atr_pct > 0)
    net_atr = np.where(valid, net_pct / atr_pct, np.nan)
    return pd.DataFrame(
        {
            "sym_key": sym_key,
            "combo": combo_id,
            "pool": pool_name,
            "side": side,
            "entry_ts": ts[e],
            "exit_ts": ts[x],
            "holding_bars": x - e,
            "reason": reason,
            "entry_px": entry_px,
            "exit_px": exit_px,
            "gross_pct": gross,
            "funding_pct": funding,
            "net_pct": net_pct,
            "entry_atr_pct": atr_pct,
            "net_atr": net_atr,
        }
    )


def aggregate(frame: pd.DataFrame, pool_years: float) -> dict:
    if frame is None or frame.empty:
        return {"segments": 0}
    net = frame["net_atr"].to_numpy()
    yearly = (
        frame.assign(year=frame["entry_ts"].dt.year)
        .groupby("year")["net_atr"]
        .agg(["count", "mean"])
    )
    out = {
        "segments": int(len(frame)),
        "symbols": int(frame["sym_key"].nunique()),
        "net_atr_mean": float(np.nanmean(net)),
        "net_atr_median": float(np.nanmedian(net)),
        "net_pct_mean": float(frame["net_pct"].mean()),
        "win_rate": float((frame["net_pct"] > 0).mean()),
        "hold_bars_median": float(frame["holding_bars"].median()),
        "hold_bars_p10": float(frame["holding_bars"].quantile(0.10)),
        "hold_bars_p90": float(frame["holding_bars"].quantile(0.90)),
        "round_trips_per_pool_year": (
            float(len(frame) / pool_years) if pool_years > 0 else None
        ),
        "reasons": frame["reason"].value_counts().to_dict(),
        "yearly": {
            int(y): {"count": int(r["count"]), "net_atr_mean": float(r["mean"])}
            for y, r in yearly.iterrows()
        },
        "sides": {},
    }
    for side_name, side_val in (("long", 1), ("short", -1)):
        sub = frame.loc[frame["side"] == side_val]
        if sub.empty:
            out["sides"][side_name] = {"segments": 0}
            continue
        side_yearly = (
            sub.assign(year=sub["entry_ts"].dt.year).groupby("year")["net_atr"].mean()
        )
        out["sides"][side_name] = {
            "segments": int(len(sub)),
            "net_atr_mean": float(np.nanmean(sub["net_atr"])),
            "net_pct_mean": float(sub["net_pct"].mean()),
            "win_rate": float((sub["net_pct"] > 0).mean()),
            "hold_bars_median": float(sub["holding_bars"].median()),
            "years_positive": int((side_yearly > 0).sum()),
            "years_total": int(len(side_yearly)),
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="smoke: cap symbol count")
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--out-tag", default=RUN_DATE)
    parser.add_argument(
        "--detail-combo",
        default=None,
        help=(
            "core,th_in,th_out,confirm — produce the detailed report for this "
            "pre-registered sensitivity combo instead of the frozen canonical. "
            "Diagnostic view only; does not change the contract canonical."
        ),
    )
    args = parser.parse_args()

    detail_combo = CANONICAL
    if args.detail_combo:
        core, th_in, th_out, confirm = args.detail_combo.split(",")
        detail_combo = (core, float(th_in), float(th_out), int(confirm))
        assert core in CORES and float(th_in) in TH_INS
        assert float(th_out) in TH_OUTS and int(confirm) in CONFIRMS

    t0 = time.time()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    daily = ec.build_daily_stats()
    universe = ec.build_universe(daily)
    elig = universe.eligibility
    elig = elig.loc[elig["day"] < DEV_END.tz_localize(None)]

    dev_days = elig.groupby("sym_key")[["eligible", "in_trading_pool"]].sum()
    candidates = sorted(dev_days.loc[dev_days["eligible"] > 0].index)
    if args.symbols:
        candidates = [s for s in candidates if s in set(args.symbols)]
    if args.limit:
        candidates = candidates[: args.limit]

    pool_years = {
        "training": float(dev_days.loc[candidates, "eligible"].sum() / 365.0),
        "trading": float(dev_days.loc[candidates, "in_trading_pool"].sum() / 365.0),
    }

    funding = ec.load_funding()
    funding_by_sym = {
        sym: ec.prepare_funding_lookup(group)
        for sym, group in funding.groupby("sym_key")
    }

    combos = [
        (core, th_in, th_out, confirm)
        for core in CORES
        for th_in in TH_INS
        for th_out in TH_OUTS
        for confirm in CONFIRMS
    ]

    def combo_id(core: str, th_in: float, th_out: float, confirm: int) -> str:
        return f"{core}_in{th_in:g}_out{th_out:g}_n{confirm}"

    canonical_id = combo_id(*detail_combo)
    canonical_frames: list[pd.DataFrame] = []
    sensitivity_frames: dict[str, list[pd.DataFrame]] = {
        combo_id(*c): [] for c in combos
    }

    elig_by_sym = {
        sym: group.set_index(pd.DatetimeIndex(group["day"]).tz_localize("UTC"))
        for sym, group in elig.groupby("sym_key")
        if sym in set(candidates)
    }

    processed = 0
    skipped_short = 0
    for sym in candidates:
        bars = load_bars(sym)
        bars = bars.loc[bars["ts"] < DEV_END].reset_index(drop=True)
        n = len(bars)
        if n <= ATR_LEN + 1:
            skipped_short += 1
            continue
        ts = bars["ts"].to_numpy(dtype="datetime64[ns]")
        open_ = bars["open"].to_numpy(dtype=float)
        close = bars["close"]
        high = bars["high"]
        low = bars["low"]
        prev_close = close.shift(1)
        true_range = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
        ).max(axis=1)
        atr = true_range.rolling(ATR_LEN, min_periods=ATR_LEN).mean().to_numpy()

        spreads: dict[str, np.ndarray] = {}
        for core, (fast, slow) in CORES.items():
            ema_fast = close.ewm(span=fast, adjust=False, min_periods=fast).mean()
            ema_slow = close.ewm(span=slow, adjust=False, min_periods=slow).mean()
            with np.errstate(invalid="ignore", divide="ignore"):
                spread = (ema_fast - ema_slow).to_numpy() / atr
            spread[~np.isfinite(spread)] = np.nan
            spreads[core] = spread

        # membership gates per bar (day-level, point-in-time)
        sym_elig = elig_by_sym.get(sym)
        bar_days = pd.DatetimeIndex(bars["ts"]).floor("D")
        gates: dict[str, np.ndarray] = {}
        for pool_name, column in (("training", "eligible"), ("trading", "in_trading_pool")):
            member = sym_elig[column].reindex(bar_days).fillna(False).to_numpy()
            gates[pool_name] = member.astype(bool)

        # run lengths per (core, threshold, side-condition)
        runlens: dict[tuple[str, str, float], np.ndarray] = {}
        for core, spread in spreads.items():
            finite = np.isfinite(spread)
            for th in TH_INS:
                runlens[(core, "enter_long", th)] = runlen(finite & (spread >= th))
                runlens[(core, "enter_short", th)] = runlen(finite & (spread <= -th))
            for th in TH_OUTS:
                runlens[(core, "exit_long", th)] = runlen(finite & (spread <= th))
                runlens[(core, "exit_short", th)] = runlen(finite & (spread >= -th))

        fund_ts, fund_cum = funding_by_sym.get(sym, (np.array([], dtype="datetime64[ns]"), np.array([0.0])))

        gate_pos = {
            pool_name: (np.flatnonzero(gate), np.flatnonzero(~gate))
            for pool_name, gate in gates.items()
        }

        for core, th_in, th_out, confirm in combos:
            cid = combo_id(core, th_in, th_out, confirm)
            pos = {
                key: np.flatnonzero(runlens[(core, key, th)] >= confirm)
                for key, th in (
                    ("enter_long", th_in),
                    ("enter_short", th_in),
                    ("exit_long", th_out),
                    ("exit_short", th_out),
                )
            }
            pools = ("trading", "training") if cid == canonical_id else ("trading",)
            for pool_name in pools:
                gate = gates[pool_name]
                gate_true, gate_false = gate_pos[pool_name]
                raw = simulate(
                    n,
                    gate,
                    gate_true,
                    gate_false,
                    pos["enter_long"],
                    pos["enter_short"],
                    pos["exit_long"],
                    pos["exit_short"],
                    confirm,
                )
                frame = segment_frame(
                    sym, cid, pool_name, raw, ts, open_, atr, fund_ts, fund_cum
                )
                if frame is None:
                    continue
                if cid == canonical_id:
                    canonical_frames.append(frame)
                if pool_name == "trading":
                    sensitivity_frames[cid].append(frame)
        processed += 1
        if processed % 50 == 0:
            print(
                f"[{processed}/{len(candidates)}] {sym} elapsed={time.time() - t0:.0f}s",
                flush=True,
            )

    canonical = (
        pd.concat(canonical_frames, ignore_index=True)
        if canonical_frames
        else pd.DataFrame()
    )
    canonical_trading = canonical.loc[canonical["pool"] == "trading"]
    canonical_training = canonical.loc[canonical["pool"] == "training"]

    # per-symbol round-trip distribution (trading pool, canonical)
    sym_pool_years = (
        dev_days.loc[candidates, "in_trading_pool"].astype(float) / 365.0
    )
    seg_counts = canonical_trading.groupby("sym_key").size()
    per_sym_rt = (
        (seg_counts / sym_pool_years.reindex(seg_counts.index))
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )

    # recent slices, audit only, anchored to dev end
    anchor = canonical_trading["entry_ts"].max() if not canonical_trading.empty else None
    recent = {}
    if anchor is not None:
        for name, delta in RECENT_SLICES.items():
            sub = canonical_trading.loc[canonical_trading["entry_ts"] >= anchor - delta]
            recent[name] = {
                "segments": int(len(sub)),
                "net_atr_mean": float(np.nanmean(sub["net_atr"])) if len(sub) else None,
            }

    trading_stats = aggregate(canonical_trading, pool_years["trading"])
    training_stats = aggregate(canonical_training, pool_years["training"])

    # --- frozen P1 gates on the canonical trading pool ---
    identity_gate = {
        "median_hold_bars": trading_stats.get("hold_bars_median"),
        "median_hold_requirement": GATE_MIN_MEDIAN_HOLD_BARS,
        "round_trips_per_pool_year": trading_stats.get("round_trips_per_pool_year"),
        "round_trips_requirement": GATE_MAX_ROUND_TRIPS_PER_POOL_YEAR,
        "per_symbol_round_trips_p90": (
            float(per_sym_rt.quantile(0.9)) if len(per_sym_rt) else None
        ),
    }
    identity_gate["pass"] = bool(
        trading_stats.get("hold_bars_median", 0) >= GATE_MIN_MEDIAN_HOLD_BARS
        and (trading_stats.get("round_trips_per_pool_year") or np.inf)
        <= GATE_MAX_ROUND_TRIPS_PER_POOL_YEAR
    )

    overall_pos = trading_stats.get("net_atr_mean", 0.0) > 0
    sides = trading_stats.get("sides", {})
    side_branch = {}
    for side_name in ("long", "short"):
        side = sides.get(side_name, {})
        side_branch[side_name] = bool(
            side.get("segments", 0) > 0
            and side.get("net_atr_mean", -np.inf) >= GATE_ONE_SIDE_MIN_ATR
            and side.get("years_positive", 0) * 2 > side.get("years_total", 0)
        )
    expectancy_gate = {
        "overall_net_atr_mean": trading_stats.get("net_atr_mean"),
        "overall_positive": bool(overall_pos),
        "one_side_branch": side_branch,
        "pass": bool(overall_pos or any(side_branch.values())),
    }

    sensitivity_rows = []
    for core, th_in, th_out, confirm in combos:
        cid = combo_id(core, th_in, th_out, confirm)
        frames = sensitivity_frames[cid]
        merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        stats = aggregate(merged, pool_years["trading"])
        sensitivity_rows.append(
            {
                "combo": cid,
                "core": core,
                "th_in": th_in,
                "th_out": th_out,
                "confirm": confirm,
                "segments": stats.get("segments", 0),
                "net_atr_mean": stats.get("net_atr_mean"),
                "net_atr_mean_long": stats.get("sides", {}).get("long", {}).get("net_atr_mean"),
                "net_atr_mean_short": stats.get("sides", {}).get("short", {}).get("net_atr_mean"),
                "win_rate": stats.get("win_rate"),
                "hold_bars_median": stats.get("hold_bars_median"),
                "round_trips_per_pool_year": stats.get("round_trips_per_pool_year"),
            }
        )
    sensitivity = pd.DataFrame(sensitivity_rows)

    worst = (
        canonical_trading.nsmallest(10, "net_pct")[
            ["sym_key", "side", "entry_ts", "exit_ts", "holding_bars", "net_pct", "net_atr", "reason"]
        ].to_dict(orient="records")
        if not canonical_trading.empty
        else []
    )
    for row in worst:
        row["entry_ts"] = str(row["entry_ts"])
        row["exit_ts"] = str(row["exit_ts"])

    report = {
        "family": "BIN-15M-TSM",
        "phase": "P1 segment baseline",
        "run_utc": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-15m-tsm-research-contract-2026-07-28.md",
        "dev_window": ["2020-01-01", "2026-01-01"],
        "cost_model": {
            "fee_per_fill": 0.001,
            "slippage_per_fill": 0.0004,
            "round_trip": ROUND_TRIP_COST,
            "funding": "as-of, signed",
        },
        "canonical": {
            "combo": canonical_id,
            "trading_pool": trading_stats,
            "training_pool": training_stats,
            "recent_slices_audit_only": recent,
            "worst_10_trading_segments": worst,
        },
        "gates": {"identity": identity_gate, "expectancy": expectancy_gate},
        "universe": {
            "symbols_processed": processed,
            "symbols_skipped_short_history": skipped_short,
            "trading_pool_symbol_years": pool_years["trading"],
            "training_pool_symbol_years": pool_years["training"],
        },
        "elapsed_seconds": round(time.time() - t0, 1),
    }

    tag = args.out_tag
    report_path = ARTIFACT_DIR / f"bin_15m_tsm_p1_segment_baseline_{tag}.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    canonical.to_parquet(
        ARTIFACT_DIR / f"bin_15m_tsm_p1_canonical_segments_{tag}.parquet", index=False
    )
    sensitivity.to_csv(
        ARTIFACT_DIR / f"bin_15m_tsm_p1_sensitivity_{tag}.csv", index=False
    )

    print(json.dumps(report["gates"], indent=2, ensure_ascii=False))
    print(f"report -> {report_path}")
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
