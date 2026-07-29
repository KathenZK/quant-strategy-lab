#!/usr/bin/env python
"""BIN-15M-TSM one-shot locked OOS reveal (contract §9). RUN ONCE.

Frozen interpretation, declared before any OOS number is computed:

- State machine (amended canonical EMA336/1536, th 1.0/0.25, N=4) runs over
  the full history 2020-01-01 .. 2026-06-30 so OOS starts from the machine's
  true carried-over state. Scoring window: 2026-01-01 <= ts < 2026-07-01 UTC.
- Portfolio accounting identical to the P2 baseline (two-layer vol target,
  daily-frozen sigma/scale, close-to-close 15m approximation, costs
  0.0014/fill on turnover, funding signed at settlement bars). OOS equity
  restarts at 1.0 on the first OOS bar; MaxDD measured inside OOS only.
- "Closed segments >= 200": trading-pool segments whose exit falls inside the
  OOS window, including segments opened before OOS and segments force-closed
  at the archive end (window_end).
- "PF >= 1.2": profit factor over those closed segments' per-unit-notional
  net returns (P1 measurement convention, costs + funding included). The
  daily-portfolio-return PF is reported for information but is not the gate.
- Gates: closed segments >= 200; portfolio OOS net > 0; segment PF >= 1.2;
  portfolio OOS MaxDD <= 20%; net still > 0 under 1.5x trading costs.
  Any failure -> HARD-GATE-FAILED, family archives, no retry on this window.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import run_p1_segment_baseline as p1  # noqa: E402
import emax_common as ec  # noqa: E402

ARTIFACT_DIR = p1.ARTIFACT_DIR
RUN_TAG = "2026-07-28"

CORE = "ema336_1536"
TH_IN, TH_OUT, CONFIRM = 1.0, 0.25, 4
COST_PER_FILL = p1.COST_PER_FILL

OOS_START = pd.Timestamp("2026-01-01", tz="UTC")
OOS_END = pd.Timestamp("2026-07-01", tz="UTC")

VOL_HALFLIFE_DAYS = 20
TARGET_VOL = 0.20
MAX_LEVERAGE = 2.0
PER_SYMBOL_CAP = 0.10
MIN_VOL_OBS = 10
ANNUALIZER = float(np.sqrt(365.0))

GATE_MIN_SEGMENTS = 200
GATE_MIN_PF = 1.2
GATE_MAX_DD = 0.20


def main() -> None:
    t0 = time.time()
    marker = ARTIFACT_DIR / "LOCKED_OOS_REVEALED.json"
    if marker.exists():
        raise SystemExit(f"locked OOS already revealed: {marker} — no reruns allowed")

    bar_index = pd.date_range(
        pd.Timestamp("2020-01-01", tz="UTC"), OOS_END, freq="15min", inclusive="left"
    )
    bar_ts = bar_index.to_numpy(dtype="datetime64[ns]")
    n_bars = len(bar_index)
    day_keys = bar_index.floor("D")
    unique_days = day_keys.unique()
    day_pos = pd.Series(np.arange(len(unique_days)), index=unique_days)
    bar_day_idx = day_pos.reindex(day_keys).to_numpy()

    daily = ec.build_daily_stats()
    universe = ec.build_universe(daily)
    elig = universe.eligibility
    dev_days = elig.groupby("sym_key")[["eligible", "in_trading_pool"]].sum()
    symbols = sorted(dev_days.loc[dev_days["in_trading_pool"] > 0].index)

    funding = ec.load_funding()
    funding_by_sym = {sym: grp for sym, grp in funding.groupby("sym_key")}
    elig_by_sym = {
        sym: grp.set_index(pd.DatetimeIndex(grp["day"]).tz_localize("UTC"))
        for sym, grp in elig.groupby("sym_key")
        if sym in set(symbols)
    }

    n_syms = len(symbols)
    S = np.zeros((n_bars, n_syms), dtype=np.int8)
    R = np.zeros((n_bars, n_syms), dtype=np.float32)
    F = np.zeros((n_bars, n_syms), dtype=np.float32)
    sigma_daily = np.full((len(unique_days), n_syms), np.nan, dtype=np.float32)
    segment_frames: list[pd.DataFrame] = []

    fast, slow = p1.CORES[CORE]
    for j, sym in enumerate(symbols):
        bars = p1.load_bars(sym)
        bars = bars.loc[bars["ts"] < OOS_END].reset_index(drop=True)
        n = len(bars)
        if n <= p1.ATR_LEN + 1:
            continue
        ts = bars["ts"].to_numpy(dtype="datetime64[ns]")
        close = bars["close"]
        high, low = bars["high"], bars["low"]
        prev_close = close.shift(1)
        true_range = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
        ).max(axis=1)
        atr = true_range.rolling(p1.ATR_LEN, min_periods=p1.ATR_LEN).mean().to_numpy()
        ema_fast = close.ewm(span=fast, adjust=False, min_periods=fast).mean()
        ema_slow = close.ewm(span=slow, adjust=False, min_periods=slow).mean()
        with np.errstate(invalid="ignore", divide="ignore"):
            spread = (ema_fast - ema_slow).to_numpy() / atr
        spread[~np.isfinite(spread)] = np.nan
        finite = np.isfinite(spread)

        bar_days_local = pd.DatetimeIndex(bars["ts"]).floor("D")
        gate = (
            elig_by_sym[sym]["in_trading_pool"]
            .reindex(bar_days_local)
            .fillna(False)
            .to_numpy()
            .astype(bool)
        )
        raw_segments = p1.simulate(
            n,
            gate,
            np.flatnonzero(gate),
            np.flatnonzero(~gate),
            np.flatnonzero(p1.runlen(finite & (spread >= TH_IN)) >= CONFIRM),
            np.flatnonzero(p1.runlen(finite & (spread <= -TH_IN)) >= CONFIRM),
            np.flatnonzero(p1.runlen(finite & (spread <= TH_OUT)) >= CONFIRM),
            np.flatnonzero(p1.runlen(finite & (spread >= -TH_OUT)) >= CONFIRM),
            CONFIRM,
        )

        fund_ts, fund_cum = (
            ec.prepare_funding_lookup(funding_by_sym[sym])
            if sym in funding_by_sym
            else (np.array([], dtype="datetime64[ns]"), np.array([0.0]))
        )
        frame = p1.segment_frame(
            sym, "oos_reveal", "trading", raw_segments, ts, bars["open"].to_numpy(float), atr, fund_ts, fund_cum
        )
        if frame is not None:
            segment_frames.append(frame)

        gpos = np.searchsorted(bar_ts, ts)
        ret = close.pct_change().to_numpy(dtype=np.float32)
        ret[~np.isfinite(ret)] = 0.0
        R[gpos, j] = ret
        for side, e, x, _reason in raw_segments:
            S[gpos[e:x], j] = side
        frows = funding_by_sym.get(sym)
        if frows is not None:
            f_ts = frows["ts"].to_numpy(dtype="datetime64[ns]")
            mask = (f_ts >= bar_ts[0]) & (f_ts < bar_ts[-1])
            fp = np.searchsorted(bar_ts, f_ts[mask])
            np.add.at(F[:, j], fp, frows["funding_rate"].to_numpy()[mask].astype(np.float32))
        day_close = close.groupby(bar_days_local).last()
        vol = (
            day_close.pct_change()
            .ewm(halflife=VOL_HALFLIFE_DAYS, min_periods=MIN_VOL_OBS)
            .std()
            .shift(1)
            * ANNUALIZER
        )
        sigma_daily[:, j] = vol.reindex(pd.DatetimeIndex(unique_days)).to_numpy(np.float32)
        if (j + 1) % 100 == 0:
            print(f"[{j + 1}/{n_syms}] elapsed={time.time() - t0:.0f}s", flush=True)

    sigma_bar = sigma_daily[bar_day_idx, :]
    with np.errstate(invalid="ignore", divide="ignore"):
        raw = np.where(
            (S != 0) & np.isfinite(sigma_bar) & (sigma_bar > 0), S / sigma_bar, 0.0
        ).astype(np.float32)
    rowsum = np.abs(raw).sum(axis=1)
    rowsum[rowsum == 0] = 1.0
    w_unscaled = np.clip(raw / rowsum[:, None], -PER_SYMBOL_CAP, PER_SYMBOL_CAP)

    daily_gross_unscaled = pd.Series((w_unscaled * R).sum(axis=1), index=bar_index).groupby(day_keys).sum()
    sigma_p = (
        daily_gross_unscaled.ewm(halflife=VOL_HALFLIFE_DAYS, min_periods=MIN_VOL_OBS)
        .std()
        .shift(1)
        * ANNUALIZER
    )
    scale_day = np.minimum(TARGET_VOL / sigma_p, MAX_LEVERAGE).fillna(1.0)
    scale_bar = scale_day.reindex(pd.DatetimeIndex(unique_days)).to_numpy()[bar_day_idx].astype(np.float32)
    W = w_unscaled * scale_bar[:, None]

    gross_bar = (W * R).sum(axis=1)
    funding_bar = (W * F).sum(axis=1)
    turnover_bar = np.abs(np.diff(W, axis=0, prepend=np.zeros((1, n_syms), np.float32))).sum(axis=1)

    oos_mask = np.asarray(bar_index >= OOS_START)

    def oos_account(cost_multiplier: float) -> dict:
        net_bar = gross_bar - funding_bar - turnover_bar * COST_PER_FILL * cost_multiplier
        net_oos = net_bar[oos_mask]
        equity = np.cumprod(1.0 + net_oos)
        peak = np.maximum.accumulate(equity)
        daily_net = pd.Series(net_oos, index=bar_index[oos_mask]).groupby(
            day_keys[oos_mask]
        ).apply(lambda g: float(np.prod(1.0 + g.to_numpy()) - 1.0))
        pos = daily_net[daily_net > 0].sum()
        neg = -daily_net[daily_net < 0].sum()
        return {
            "net_return": float(equity[-1] - 1.0),
            "max_dd": float((equity / peak - 1.0).min()),
            "daily_return_pf": float(pos / neg) if neg > 0 else None,
            "sharpe_daily_ann": float(daily_net.mean() / daily_net.std() * ANNUALIZER)
            if daily_net.std() > 0
            else None,
            "monthly_net": {
                str(k.date()): float(v)
                for k, v in daily_net.groupby(daily_net.index.to_period("M").to_timestamp()).apply(
                    lambda g: np.prod(1.0 + g.to_numpy()) - 1.0
                ).items()
            },
            "equity": pd.Series(equity, index=bar_index[oos_mask]),
        }

    base = oos_account(1.0)
    stress = oos_account(1.5)

    segments = pd.concat(segment_frames, ignore_index=True)
    closed_oos = segments.loc[
        (segments["exit_ts"] >= OOS_START.tz_localize(None).to_datetime64())
        & (segments["exit_ts"] < OOS_END.tz_localize(None).to_datetime64())
    ].copy()
    seg_pos = closed_oos.loc[closed_oos["net_pct"] > 0, "net_pct"].sum()
    seg_neg = -closed_oos.loc[closed_oos["net_pct"] < 0, "net_pct"].sum()
    segment_pf = float(seg_pos / seg_neg) if seg_neg > 0 else float("inf")

    gates = {
        "closed_segments": {"value": int(len(closed_oos)), "min": GATE_MIN_SEGMENTS,
                            "pass": bool(len(closed_oos) >= GATE_MIN_SEGMENTS)},
        "net_positive": {"value": base["net_return"], "pass": bool(base["net_return"] > 0)},
        "segment_pf": {"value": segment_pf, "min": GATE_MIN_PF,
                       "pass": bool(segment_pf >= GATE_MIN_PF)},
        "max_dd": {"value": base["max_dd"], "limit": -GATE_MAX_DD,
                   "pass": bool(base["max_dd"] >= -GATE_MAX_DD)},
        "stress_net_positive": {"value": stress["net_return"],
                                "pass": bool(stress["net_return"] > 0)},
    }
    verdict = "PASS" if all(g["pass"] for g in gates.values()) else "HARD-GATE-FAILED"

    report = {
        "family": "BIN-15M-TSM",
        "phase": "locked OOS one-shot reveal",
        "combo": f"{CORE}_in{TH_IN:g}_out{TH_OUT:g}_n{CONFIRM} (amended canonical)",
        "run_utc": pd.Timestamp.now("UTC").isoformat(),
        "oos_window": [str(OOS_START), str(OOS_END)],
        "verdict": verdict,
        "gates": gates,
        "base": {k: v for k, v in base.items() if k != "equity"},
        "stress_1_5x": {k: v for k, v in stress.items() if k != "equity"},
        "closed_oos_segments": {
            "count": int(len(closed_oos)),
            "net_atr_mean": float(np.nanmean(closed_oos["net_atr"])) if len(closed_oos) else None,
            "net_pct_mean": float(closed_oos["net_pct"].mean()) if len(closed_oos) else None,
            "win_rate": float((closed_oos["net_pct"] > 0).mean()) if len(closed_oos) else None,
            "long_net_atr_mean": float(np.nanmean(closed_oos.loc[closed_oos["side"] == 1, "net_atr"])) if len(closed_oos) else None,
            "short_net_atr_mean": float(np.nanmean(closed_oos.loc[closed_oos["side"] == -1, "net_atr"])) if len(closed_oos) else None,
            "reasons": closed_oos["reason"].value_counts().to_dict() if len(closed_oos) else {},
        },
        "elapsed_seconds": round(time.time() - t0, 1),
    }

    report_path = ARTIFACT_DIR / f"bin_15m_tsm_locked_oos_reveal_{RUN_TAG}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    closed_oos.to_parquet(ARTIFACT_DIR / f"bin_15m_tsm_locked_oos_segments_{RUN_TAG}.parquet", index=False)
    base["equity"].rename("equity").to_frame().to_parquet(
        ARTIFACT_DIR / f"bin_15m_tsm_locked_oos_equity_{RUN_TAG}.parquet"
    )
    marker.write_text(
        json.dumps({"revealed_at": pd.Timestamp.now("UTC").isoformat(), "verdict": verdict}),
        encoding="utf-8",
    )

    print(json.dumps({"verdict": verdict, "gates": gates}, indent=2, default=float))
    print(f"report -> {report_path}")


if __name__ == "__main__":
    main()
