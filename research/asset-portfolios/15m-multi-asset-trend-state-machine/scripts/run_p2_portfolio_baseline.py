#!/usr/bin/env python
"""BIN-15M-TSM P2 portfolio baseline.

Implements contract §8 (amended canonical core EMA336/1536, th 1.0/0.25, N=4):

- Per-symbol trading-pool state series from the P1 state machine (states
  already force-close on pool exit / dev window end).
- Two-layer vol targeting reused from the BIN-1D-TSMOM-VT contract:
  per symbol w_i = state_i / sigma_i (EWMA daily-return vol, half-life 20d,
  annualized, T-1 shifted), normalized to sum(|w|)=1 over active states,
  per-symbol cap |w| <= 0.10 (truncate, no redistribution); portfolio layer
  scales by min(20% / sigma_p, 2.0) where sigma_p is the EWMA (half-life 20d)
  vol of the *unscaled* portfolio's daily gross returns, shifted one day
  (scale = 1.0 until 10 daily observations exist).
- Weights re-derived every closed 15m bar (daily-frozen sigma and scale;
  state flips take effect immediately). Bar accounting uses close-to-close
  15m returns as the declared approximation of next-open execution.
- Costs: turnover * (0.001 + 4 bps) per fill on traded notional; funding
  charged as w[t] * funding_rate at the bar whose open equals the settlement
  timestamp (long pays positive). Stress: 1.5x trading costs.
- Dev window only (ts < 2026-01-01 UTC); locked OOS untouched.

Kill gates (frozen): net > 0; 1.5x-cost net > 0; MaxDD <= 40%; mean annual
trading-cost drag <= 30% notional. BTC buy-and-hold comparison reported.
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
import emax_common as ec  # noqa: E402  (path injected by p1 import)

ARTIFACT_DIR = p1.ARTIFACT_DIR
RUN_TAG = "2026-07-28"

CORE = "ema336_1536"
TH_IN, TH_OUT, CONFIRM = 1.0, 0.25, 4

COST_PER_FILL = p1.COST_PER_FILL
DEV_END = p1.DEV_END

VOL_HALFLIFE_DAYS = 20
TARGET_VOL = 0.20
MAX_LEVERAGE = 2.0
PER_SYMBOL_CAP = 0.10
MIN_VOL_OBS = 10
ANNUALIZER = float(np.sqrt(365.0))

GATE_MAX_DD = 0.40
GATE_MAX_ANNUAL_COST_DRAG = 0.30


def yearly_compound(returns: pd.Series) -> dict[int, float]:
    out = {}
    for year, group in returns.groupby(returns.index.year):
        out[int(year)] = float(np.prod(1.0 + group.to_numpy()) - 1.0)
    return out


def main() -> None:
    t0 = time.time()
    bar_index = pd.date_range(
        pd.Timestamp("2020-01-01", tz="UTC"), DEV_END, freq="15min", inclusive="left"
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
    elig = elig.loc[elig["day"] < DEV_END.tz_localize(None)]
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

    fast, slow = p1.CORES[CORE]
    for j, sym in enumerate(symbols):
        bars = p1.load_bars(sym)
        bars = bars.loc[bars["ts"] < DEV_END].reset_index(drop=True)
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
        pos = {
            "enter_long": np.flatnonzero(p1.runlen(finite & (spread >= TH_IN)) >= CONFIRM),
            "enter_short": np.flatnonzero(p1.runlen(finite & (spread <= -TH_IN)) >= CONFIRM),
            "exit_long": np.flatnonzero(p1.runlen(finite & (spread <= TH_OUT)) >= CONFIRM),
            "exit_short": np.flatnonzero(p1.runlen(finite & (spread >= -TH_OUT)) >= CONFIRM),
        }
        raw_segments = p1.simulate(
            n,
            gate,
            np.flatnonzero(gate),
            np.flatnonzero(~gate),
            pos["enter_long"],
            pos["enter_short"],
            pos["exit_long"],
            pos["exit_short"],
            CONFIRM,
        )

        gpos = np.searchsorted(bar_ts, ts)  # local bar -> global bar
        # 15m close-to-close returns land on the later bar
        ret = close.pct_change().to_numpy(dtype=np.float32)
        ret[~np.isfinite(ret)] = 0.0
        R[gpos, j] = ret
        # exposure bars: entry_bar .. exit_bar-1 (position from entry open to exit open)
        for side, e, x, _reason in raw_segments:
            S[gpos[e:x], j] = side
        # funding events mapped to the bar whose open equals the settlement ts
        frows = funding_by_sym.get(sym)
        if frows is not None:
            f_ts = frows["ts"].to_numpy(dtype="datetime64[ns]")
            mask = (f_ts >= bar_ts[0]) & (f_ts < bar_ts[-1])
            fp = np.searchsorted(bar_ts, f_ts[mask])
            np.add.at(F[:, j], fp, frows["funding_rate"].to_numpy()[mask].astype(np.float32))
        # daily sigma from daily closes (T-1 shifted, EWMA half-life 20d, annualized)
        day_close = close.groupby(bar_days_local).last()
        day_ret = day_close.pct_change()
        vol = (
            day_ret.ewm(halflife=VOL_HALFLIFE_DAYS, min_periods=MIN_VOL_OBS)
            .std()
            .shift(1)
            * ANNUALIZER
        )
        vol = vol.reindex(pd.DatetimeIndex(unique_days))
        sigma_daily[:, j] = vol.to_numpy(dtype=np.float32)
        if (j + 1) % 50 == 0:
            print(f"[{j + 1}/{n_syms}] {sym} elapsed={time.time() - t0:.0f}s", flush=True)

    print(f"state matrices built in {time.time() - t0:.0f}s", flush=True)

    sigma_bar = sigma_daily[bar_day_idx, :]
    with np.errstate(invalid="ignore", divide="ignore"):
        raw = np.where(
            (S != 0) & np.isfinite(sigma_bar) & (sigma_bar > 0),
            S / sigma_bar,
            0.0,
        ).astype(np.float32)
    rowsum = np.abs(raw).sum(axis=1)
    rowsum[rowsum == 0] = 1.0
    w_unscaled = np.clip(raw / rowsum[:, None], -PER_SYMBOL_CAP, PER_SYMBOL_CAP)

    # portfolio layer: EWMA vol of the unscaled portfolio's daily gross returns
    gross_unscaled_bar = (w_unscaled * R).sum(axis=1)
    daily_gross_unscaled = pd.Series(gross_unscaled_bar, index=bar_index).groupby(
        day_keys
    ).sum()
    sigma_p = (
        daily_gross_unscaled.ewm(halflife=VOL_HALFLIFE_DAYS, min_periods=MIN_VOL_OBS)
        .std()
        .shift(1)
        * ANNUALIZER
    )
    scale_day = np.minimum(TARGET_VOL / sigma_p, MAX_LEVERAGE).fillna(1.0)
    scale_bar = scale_day.reindex(pd.DatetimeIndex(unique_days)).to_numpy()[
        bar_day_idx
    ].astype(np.float32)

    W = w_unscaled * scale_bar[:, None]

    gross_bar = (W * R).sum(axis=1)
    funding_bar = (W * F).sum(axis=1)  # long pays positive funding
    turnover_bar = np.abs(np.diff(W, axis=0, prepend=np.zeros((1, n_syms), np.float32))).sum(axis=1)
    leverage_bar = np.abs(W).sum(axis=1)

    def account(cost_multiplier: float) -> dict:
        cost_bar = turnover_bar * COST_PER_FILL * cost_multiplier
        net_bar = gross_bar - funding_bar - cost_bar
        equity = np.cumprod(1.0 + net_bar)
        peak = np.maximum.accumulate(equity)
        max_dd = float((equity / peak - 1.0).min())
        net_daily = pd.Series(net_bar, index=bar_index).groupby(day_keys).apply(
            lambda g: float(np.prod(1.0 + g.to_numpy()) - 1.0)
        )
        sharpe = (
            float(net_daily.mean() / net_daily.std() * ANNUALIZER)
            if net_daily.std() > 0
            else None
        )
        realized_vol = float(net_daily.std() * ANNUALIZER)
        years = (bar_index[-1] - bar_index[0]).days / 365.0
        return {
            "net_return": float(equity[-1] - 1.0),
            "max_dd": max_dd,
            "sharpe_daily_ann": sharpe,
            "realized_vol_ann": realized_vol,
            "yearly_net": yearly_compound(net_daily),
            "annual_cost_drag": float(cost_bar.sum() / years),
            "annual_funding_drag": float(funding_bar.sum() / years),
            "annual_turnover": float(turnover_bar.sum() / years),
            "equity_series": pd.Series(equity, index=bar_index),
            "net_daily": net_daily,
        }

    base = account(1.0)
    stress = account(1.5)

    # attribution and leverage
    long_gross = float((np.where(W > 0, W, 0) * R).sum())
    short_gross = float((np.where(W < 0, W, 0) * R).sum())
    lev_stats = {
        "mean": float(leverage_bar.mean()),
        "p99": float(np.quantile(leverage_bar, 0.99)),
        "max": float(leverage_bar.max()),
    }

    # BTC buy-and-hold comparison, same window, single round trip cost
    btc = p1.load_bars("BTC")
    btc = btc.loc[btc["ts"] < DEV_END]
    btc_bh = float(
        btc["close"].iloc[-1] / btc["close"].iloc[0] - 1.0 - 2 * COST_PER_FILL
    )
    btc_daily = (
        btc.set_index("ts")["close"].groupby(btc.set_index("ts").index.floor("D")).last().pct_change().dropna()
    )
    btc_dd = float(
        (
            (1 + btc_daily).cumprod() / (1 + btc_daily).cumprod().cummax() - 1
        ).min()
    )

    # recent slices, audit only, anchored to dev end
    recent = {}
    for name, delta in p1.RECENT_SLICES.items():
        sub = base["net_daily"].loc[base["net_daily"].index >= bar_index[-1] - delta]
        recent[name] = float(np.prod(1.0 + sub.to_numpy()) - 1.0)

    gates = {
        "net_positive": base["net_return"] > 0,
        "stress_net_positive": stress["net_return"] > 0,
        "max_dd_leq_40pct": base["max_dd"] >= -GATE_MAX_DD,
        "annual_cost_drag_leq_30pct": base["annual_cost_drag"] <= GATE_MAX_ANNUAL_COST_DRAG,
    }
    gates["pass"] = all(gates.values())

    report = {
        "family": "BIN-15M-TSM",
        "phase": "P2 portfolio baseline",
        "combo": f"{CORE}_in{TH_IN:g}_out{TH_OUT:g}_n{CONFIRM} (amended canonical)",
        "run_utc": pd.Timestamp.now("UTC").isoformat(),
        "dev_window": [str(bar_index[0]), str(bar_index[-1])],
        "symbols": n_syms,
        "base": {k: v for k, v in base.items() if k not in ("equity_series", "net_daily")},
        "stress_1_5x": {
            k: v
            for k, v in stress.items()
            if k in ("net_return", "max_dd", "sharpe_daily_ann", "yearly_net")
        },
        "attribution": {
            "long_gross_sum": long_gross,
            "short_gross_sum": short_gross,
            "funding_sum": float(funding_bar.sum()),
            "cost_sum": float((turnover_bar * COST_PER_FILL).sum()),
        },
        "leverage": lev_stats,
        "vol_target": {
            "target": TARGET_VOL,
            "realized": base["realized_vol_ann"],
            "scale_mean": float(np.nanmean(scale_day.to_numpy())),
        },
        "btc_buy_hold": {"net_return": btc_bh, "max_dd_daily": btc_dd},
        "recent_slices_audit_only": recent,
        "gates": gates,
        "elapsed_seconds": round(time.time() - t0, 1),
    }

    report_path = ARTIFACT_DIR / f"bin_15m_tsm_p2_portfolio_baseline_{RUN_TAG}.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=float),
        encoding="utf-8",
    )
    pd.DataFrame(
        {
            "equity": base["equity_series"].groupby(day_keys).last(),
            "net_daily": base["net_daily"],
        }
    ).to_parquet(ARTIFACT_DIR / f"bin_15m_tsm_p2_daily_equity_{RUN_TAG}.parquet")

    print(json.dumps({k: report[k] for k in ("base", "gates")}, indent=2, default=str))
    print(f"report -> {report_path}")
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
