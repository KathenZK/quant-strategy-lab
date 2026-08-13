"""XA-1D-EWMAC-UT P2: portfolio-level aggregation of the frozen P1 signals.

Executes the pre-registered contract in
specs/xa-1d-ewmac-ut-portfolio-contract-2026-08-06.md:

  subsystem  P1 EWMAC forecast + per-asset 20% vol sizing, unchanged
  pool       all 9 P1 assets, zero exclusion, point-in-time activation
  allocation equal risk split 1/N_t across active assets
  overlay    portfolio vol target 20% (EWMA hl=20 on raw-weight returns,
             T-1 info), gross leverage cap 3.0
  buffer     trade only when |target - held| >= 0.10 * full-forecast size
  calendar   union UTC calendar; ETFs book returns on their sessions only;
             ledger ends 2026-08-02 (crypto lake end)
  ledgers    stressed (gate): crypto fee 0.001 + slip 4bps/side + funding,
             tradfi 10bps/side.  diagnostic: tradfi zero cost.
  gates      G1 main-window (>=4 active assets) net>0 & Sharpe>=0.7
             G2 main MDD < 25%
             G3 crypto-era Sharpe>=0.6 & MDD < 25%
             G4 main annual one-way turnover <= 15x
             G5 crypto-era leave-one-out (9 runs) all net > 0

Data identity is the P1 batch: crypto from the audited 15m lake, tradfi
from the archived Yahoo raw JSONs (sha256 pinned in yahoo_raw manifest).

--contract p3 switches to the P3 contract
(specs/xa-1d-ewmac-ut-p3-breadth-scale-contract-2026-08-06.md): pool
extended to 18 assets (adds TLT/IEF/USO/UNG/DBC/DBA/UUP/FXE/EEM, 8 macro
clusters) and a 10% deadband on the applied portfolio scale. Signals,
sizing, buffers, ledgers and gates are unchanged from P2.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[3]
FAMILY_DIR = SCRIPT_DIR.parent
ARTIFACT_DIR = FAMILY_DIR / "artifacts"

BASE_PATH = SCRIPT_DIR / "run_ewmac_universal_trend.py"
YAHOO_RUN_DATE = "2026-08-05"  # reuse the archived P1 raw files
LEDGER_END = pd.Timestamp("2026-08-02")

TARGET_VOL = 0.20
VOL_HALFLIFE = 20
GROSS_CAP = 3.0
BUFFER_FRACTION = 0.10
MIN_ACTIVE_MAIN = 4
FFILL_LIMIT = 5
ANN_DAYS_UNION = 365
TRADFI_STRESS_PER_SIDE = 0.0010

# --- P3 additions (specs/xa-1d-ewmac-ut-p3-breadth-scale-contract-2026-08-06.md)
P3_EXTRA_TRADFI = {
    "TLT": "iShares 20+ Year Treasury Bond",
    "IEF": "iShares 7-10 Year Treasury Bond",
    "USO": "United States Oil Fund (WTI)",
    "UNG": "United States Natural Gas Fund",
    "DBC": "Invesco DB Commodity Index",
    "DBA": "Invesco DB Agriculture",
    "UUP": "Invesco DB US Dollar Bullish",
    "FXE": "Invesco CurrencyShares Euro",
    "EEM": "iShares MSCI Emerging Markets",
}
P3_YAHOO_RUN_DATE = "2026-08-06"
P3_SCALE_DEADBAND = 0.10

CONTRACTS = {
    "p2": {
        "spec": "specs/xa-1d-ewmac-ut-portfolio-contract-2026-08-06.md",
        "prefix": "xa_1d_ewmac_pf",
        "scale_deadband": None,
        "target_vol": 0.20,
        "buffer_fraction": 0.10,
        "pairs": None,
        "g1_sharpe": 0.7,
        "extra_tradfi": False,
    },
    "p3": {
        "spec": "specs/xa-1d-ewmac-ut-p3-breadth-scale-contract-2026-08-06.md",
        "prefix": "xa_1d_ewmac_pf3",
        "scale_deadband": P3_SCALE_DEADBAND,
        "target_vol": 0.20,
        "buffer_fraction": 0.10,
        "pairs": None,
        "g1_sharpe": 0.7,
        "extra_tradfi": True,
    },
    # P4 gate-recalibration contract
    # (specs/xa-1d-ewmac-ut-p4-gate-recalibration-contract-2026-08-06.md)
    "p4": {
        "spec": "specs/xa-1d-ewmac-ut-p4-gate-recalibration-contract-2026-08-06.md",
        "prefix": "xa_1d_ewmac_pf4",
        "scale_deadband": P3_SCALE_DEADBAND,
        "target_vol": 0.12,
        "buffer_fraction": 0.20,
        "pairs": None,
        "g1_sharpe": 0.6,
        "extra_tradfi": True,
    },
    # P4 E2 fallback: only to be run/cited if E1 fails exactly the G4
    # turnover gate (contract section 4)
    "p4e2": {
        "spec": "specs/xa-1d-ewmac-ut-p4-gate-recalibration-contract-2026-08-06.md",
        "prefix": "xa_1d_ewmac_pf4e2",
        "scale_deadband": P3_SCALE_DEADBAND,
        "target_vol": 0.12,
        "buffer_fraction": 0.20,
        "pairs": ((16, 64), (32, 128), (64, 256)),
        "g1_sharpe": 0.6,
        "extra_tradfi": True,
    },
}

CLUSTERS = {
    "BTC": "crypto", "ETH": "crypto", "HYPE": "crypto",
    "QQQ": "equity_us", "SPY": "equity_us", "SOXX": "equity_us",
    "EEM": "equity_intl",
    "GLD": "metals", "SLV": "metals",
    "SOYB": "agriculture", "DBA": "agriculture",
    "USO": "energy", "UNG": "energy",
    "DBC": "commodity_broad",
    "TLT": "rates", "IEF": "rates",
    "UUP": "fx", "FXE": "fx",
}

RECENT_SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 91, "6m": 182, "1y": 365}


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location("ewmac_base", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-date", default="2026-08-06")
    parser.add_argument("--contract", choices=sorted(CONTRACTS), default="p2")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


# --- panel construction -------------------------------------------------------


def subset_forecast(
    close: pd.Series, pairs: tuple[tuple[int, int], ...], base: Any
) -> pd.Series:
    """P1 combined_forecast semantics restricted to a pre-registered pair subset."""
    price_vol = close.diff().ewm(
        halflife=base.VOL_HALFLIFE, min_periods=base.VOL_HALFLIFE
    ).std()
    cols = []
    for fast, slow in pairs:
        raw = (
            close.ewm(span=fast, min_periods=fast).mean()
            - close.ewm(span=slow, min_periods=slow).mean()
        ) / price_vol
        cols.append(
            (raw * base.SCALARS[(fast, slow)]).clip(-base.FORECAST_CAP, base.FORECAST_CAP)
        )
    stacked = pd.concat(cols, axis=1, sort=True)
    available = stacked.notna().sum(axis=1)
    return (
        stacked.mean(axis=1)
        .where(available >= base.MIN_PAIRS)
        .clip(-base.FORECAST_CAP, base.FORECAST_CAP)
    )


def build_panel(
    base: Any,
    tradfi_assets: dict[str, str],
    yahoo_dates: dict[str, str],
    pairs: tuple[tuple[int, int], ...] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Per-asset native series plus tradfi data-quality dicts and raw manifest."""
    forecast_fn = (
        base.combined_forecast
        if pairs is None
        else lambda close: subset_forecast(close, pairs, base)
    )
    panel: dict[str, dict[str, Any]] = {}
    tradfi_quality: dict[str, Any] = {}
    yahoo_manifest: dict[str, Any] = {}

    books, _ = base.load_crypto_daily()
    funding = base.load_crypto_funding()
    for sym in base.CRYPTO_ASSETS:
        close = books[sym]["close"]
        ret = close.pct_change()
        sigma = ret.ewm(halflife=VOL_HALFLIFE, min_periods=VOL_HALFLIFE).std() * math.sqrt(
            base.CRYPTO_ANN_DAYS
        )
        panel[sym] = {
            "class": "crypto",
            "ret": ret,
            "forecast": forecast_fn(close),
            "sigma_ann": sigma,
            "funding": funding[sym] if sym in funding.columns else None,
            "cost_per_side": base.CRYPTO_COST_PER_SIDE,
        }

    for sym in tradfi_assets:
        run_date = yahoo_dates[sym]
        content, url = base.fetch_yahoo(sym, run_date, refresh=False)
        frame, quality = base.parse_yahoo(content, sym)
        if quality["rows"] < 250 or quality["duplicate_days_dropped"] > 0:
            raise RuntimeError(f"data-quality blocker for {sym}: {quality}")
        tradfi_quality[sym] = quality
        yahoo_manifest[sym] = {
            "url": url,
            "run_date": run_date,
            "raw_sha256": quality["raw_sha256"],
        }
        close = frame["close"]
        ret = close.pct_change()
        sigma = ret.ewm(halflife=VOL_HALFLIFE, min_periods=VOL_HALFLIFE).std() * math.sqrt(
            base.TRADFI_ANN_DAYS
        )
        panel[sym] = {
            "class": "tradfi_etf",
            "ret": ret,
            "forecast": forecast_fn(close),
            "sigma_ann": sigma,
            "funding": None,
            "cost_per_side": None,  # set per ledger
        }
    return panel, tradfi_quality, yahoo_manifest


def union_frames(panel: dict[str, dict[str, Any]]) -> dict[str, pd.DataFrame]:
    start = min(entry["ret"].index[0] for entry in panel.values())
    idx = pd.date_range(start, LEDGER_END, freq="D")
    forecast = pd.DataFrame(index=idx)
    sigma = pd.DataFrame(index=idx)
    ret = pd.DataFrame(index=idx)
    fund = pd.DataFrame(0.0, index=idx, columns=list(panel))
    for sym, entry in panel.items():
        forecast[sym] = entry["forecast"].reindex(idx).ffill(limit=FFILL_LIMIT)
        sigma[sym] = entry["sigma_ann"].reindex(idx).ffill(limit=FFILL_LIMIT)
        ret[sym] = entry["ret"].reindex(idx).fillna(0.0)
        if entry["funding"] is not None:
            fund[sym] = entry["funding"].reindex(idx).fillna(0.0)
    return {"forecast": forecast, "sigma": sigma, "ret": ret, "funding": fund}


# --- portfolio engine ---------------------------------------------------------


def portfolio_targets(
    frames: dict[str, pd.DataFrame],
    assets: list[str],
    *,
    scale_deadband: float | None = None,
    target_vol: float = TARGET_VOL,
    buffer_fraction: float = BUFFER_FRACTION,
) -> dict[str, Any]:
    """Raw equal-risk weights, portfolio scale and final targets (all T-1 info)."""
    fc = frames["forecast"][assets].shift(1)
    sig = frames["sigma"][assets].shift(1)
    ret = frames["ret"][assets]

    subsystem = (fc / 10.0) * (target_vol / sig)
    active = subsystem.notna()
    n_active = active.sum(axis=1)
    raw = subsystem.div(n_active.where(n_active > 0), axis=0).fillna(0.0)

    rp_unscaled = (raw * ret).sum(axis=1)
    sigma_p = (
        rp_unscaled.ewm(halflife=VOL_HALFLIFE, min_periods=VOL_HALFLIFE).std().shift(1)
        * math.sqrt(ANN_DAYS_UNION)
    )
    theo = (target_vol / sigma_p).where(sigma_p > 0)
    if scale_deadband is None:
        scale = theo
    else:
        # P3: hold the applied scale until the theoretical value drifts by
        # more than the deadband, then snap to it (path-dependent)
        vals = theo.to_numpy()
        out = np.full(len(vals), np.nan)
        cur = math.nan
        for i, v in enumerate(vals):
            if math.isfinite(v):
                if not math.isfinite(cur) or abs(v / cur - 1.0) > scale_deadband:
                    cur = v
                out[i] = cur
        scale = pd.Series(out, index=theo.index)
    gross_raw = raw.abs().sum(axis=1)
    over = gross_raw * scale > GROSS_CAP
    # hard risk cap clips the applied scale day-by-day without resetting
    # the deadband anchor (contract section 3)
    scale = scale.where(~over, GROSS_CAP / gross_raw)
    scale = scale.fillna(0.0)

    targets = raw.mul(scale, axis=0)
    full_size = (target_vol / sig).div(n_active.where(n_active > 0), axis=0).mul(
        scale, axis=0
    )
    buffers = (buffer_fraction * full_size).fillna(0.0)
    return {
        "targets": targets,
        "buffers": buffers,
        "active": active,
        "n_active": n_active,
        "scale": scale,
    }


def run_ledger(
    frames: dict[str, pd.DataFrame],
    assets: list[str],
    classes: dict[str, str],
    *,
    tradfi_cost_per_side: float,
    crypto_cost_per_side: float,
    start: pd.Timestamp | None = None,
    scale_deadband: float | None = None,
    target_vol: float = TARGET_VOL,
    buffer_fraction: float = BUFFER_FRACTION,
) -> pd.DataFrame:
    built = portfolio_targets(
        frames,
        assets,
        scale_deadband=scale_deadband,
        target_vol=target_vol,
        buffer_fraction=buffer_fraction,
    )
    targets, buffers, active = built["targets"], built["buffers"], built["active"]
    ret = frames["ret"][assets]
    funding = frames["funding"][assets]

    idx = targets.index if start is None else targets.index[targets.index >= start]
    cost_per_side = {
        sym: crypto_cost_per_side if classes[sym] == "crypto" else tradfi_cost_per_side
        for sym in assets
    }

    held = {sym: 0.0 for sym in assets}
    rows = []
    t_np = {k: v.to_numpy() for k, v in targets.items()}
    b_np = {k: v.to_numpy() for k, v in buffers.items()}
    a_np = {k: v.to_numpy() for k, v in active.items()}
    r_np = {k: v.to_numpy() for k, v in ret.items()}
    f_np = {k: v.to_numpy() for k, v in funding.items()}
    pos = {d: i for i, d in enumerate(targets.index)}
    scale_np = built["scale"].to_numpy()
    n_np = built["n_active"].to_numpy()

    for day in idx:
        i = pos[day]
        day_cost = 0.0
        day_price = 0.0
        day_funding = 0.0
        day_turnover = 0.0
        # pass 1: rebalance at the day's open (buffer + forced closes)
        for sym in assets:
            if not a_np[sym][i]:
                if held[sym] != 0.0:  # forced close on deactivation
                    day_turnover += abs(held[sym])
                    day_cost += abs(held[sym]) * cost_per_side[sym]
                    held[sym] = 0.0
                continue
            target = t_np[sym][i]
            if abs(target - held[sym]) >= b_np[sym][i]:
                traded = abs(target - held[sym])
                day_turnover += traded
                day_cost += traded * cost_per_side[sym]
                held[sym] = float(target)
        gross = sum(abs(v) for v in held.values())
        if gross > GROSS_CAP:
            # stale buffered positions can drift past the cap; enforce it
            # with a proportional scale-down, counted as real trades
            shrink = GROSS_CAP / gross
            for sym in assets:
                if held[sym] != 0.0:
                    delta = abs(held[sym]) * (1.0 - shrink)
                    day_turnover += delta
                    day_cost += delta * cost_per_side[sym]
                    held[sym] *= shrink
            gross = GROSS_CAP
        # pass 2: mark the day's PnL on post-rebalance positions
        contrib = {}
        for sym in assets:
            pnl_price = held[sym] * r_np[sym][i]
            pnl_funding = -held[sym] * f_np[sym][i]
            day_price += pnl_price
            day_funding += pnl_funding
            contrib[sym] = pnl_price + pnl_funding
        rows.append(
            {
                "day": day,
                "net": day_price - day_cost + day_funding,
                "price_pnl": day_price,
                "cost": -day_cost,
                "funding_pnl": day_funding,
                "turnover": day_turnover,
                "gross": gross,
                "n_active": n_np[i],
                "scale": scale_np[i],
                **{f"pnl_{sym}": contrib[sym] for sym in assets},
            }
        )
    return pd.DataFrame(rows).set_index("day")


# --- metrics ------------------------------------------------------------------


def drawdown_min(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1.0).min())


def window_metrics(path: pd.DataFrame, assets: list[str]) -> dict[str, Any]:
    net = path["net"]
    equity = (1.0 + net).cumprod()
    n_years = max((net.index[-1] - net.index[0]).days / 365.25, 1e-9)
    vol = float(net.std() * math.sqrt(ANN_DAYS_UNION))
    sharpe = (
        float(net.mean() / net.std() * math.sqrt(ANN_DAYS_UNION)) if net.std() > 0 else math.nan
    )
    total = float(equity.iloc[-1] - 1.0)
    yearly = equity.groupby(equity.index.year).last()
    yearly_prev = yearly.shift(1)
    yearly_prev.iloc[0] = 1.0
    contrib = {
        sym: round(float(path[f"pnl_{sym}"].sum()), 4)
        for sym in assets
        if f"pnl_{sym}" in path.columns
    }
    return {
        "window": [str(net.index[0].date()), str(net.index[-1].date())],
        "years": round(n_years, 2),
        "total_net_return": round(total, 4),
        "cagr": round(float((1.0 + total) ** (1.0 / n_years) - 1.0), 4),
        "realized_ann_vol": round(vol, 4),
        "sharpe_net": round(sharpe, 3),
        "max_drawdown": round(drawdown_min(equity), 4),
        "yearly_net": {
            str(y): round(float(v / p - 1.0), 4)
            for (y, v), p in zip(yearly.items(), yearly_prev)
        },
        "ann_one_way_turnover": round(float(path["turnover"].sum() / n_years), 2),
        "cost_drag_per_year": round(float(-path["cost"].sum() / n_years), 4),
        "funding_drag_per_year": round(float(-path["funding_pnl"].sum() / n_years), 4),
        "avg_gross_leverage": round(float(path["gross"].mean()), 3),
        "max_gross_leverage": round(float(path["gross"].max()), 3),
        "avg_scale": round(float(path["scale"].mean()), 3),
        "pnl_contribution_return_units": dict(
            sorted(contrib.items(), key=lambda kv: kv[1], reverse=True)
        ),
    }


def recent_rows(path: pd.DataFrame, variant: str) -> list[dict[str, Any]]:
    equity = (1.0 + path["net"]).cumprod()
    end = equity.index[-1]
    rows = []
    for label, days in RECENT_SLICES.items():
        base_curve = equity.loc[: end - pd.Timedelta(days=days)]
        if base_curve.empty:
            continue
        rows.append(
            {
                "variant": variant,
                "slice": label,
                "net_return": round(float(equity.iloc[-1] / base_curve.iloc[-1] - 1.0), 4),
            }
        )
    return rows


def subsystem_correlation(path: pd.DataFrame, assets: list[str]) -> float:
    cols = [f"pnl_{sym}" for sym in assets if f"pnl_{sym}" in path.columns]
    frame = path[cols]
    frame = frame.loc[:, frame.std() > 0]
    corr = frame.corr()
    n = corr.shape[0]
    if n < 2:
        return math.nan
    off_diag = (corr.to_numpy().sum() - n) / (n * (n - 1))
    return round(float(off_diag), 3)


# --- self test ----------------------------------------------------------------


def self_test() -> None:
    rng = np.random.default_rng(11)
    idx = pd.date_range("2020-01-01", periods=1200, freq="D")
    make = lambda drift, vol, seed: pd.Series(  # noqa: E731
        100.0
        * np.exp(
            np.cumsum(np.full(len(idx), drift) + np.random.default_rng(seed).normal(0, vol, len(idx)))
        ),
        index=idx,
    )
    closes = {"A": make(0.001, 0.01, 1), "B": make(-0.001, 0.01, 2), "C": make(0.0, 0.01, 3)}
    frames_forecast = pd.DataFrame(index=idx)
    frames_sigma = pd.DataFrame(index=idx)
    frames_ret = pd.DataFrame(index=idx)
    base = load_base()
    for sym, close in closes.items():
        ret = close.pct_change()
        frames_forecast[sym] = base.combined_forecast(close)
        frames_sigma[sym] = ret.ewm(halflife=20, min_periods=20).std() * math.sqrt(365)
        frames_ret[sym] = ret.fillna(0.0)
    frames = {
        "forecast": frames_forecast,
        "sigma": frames_sigma,
        "ret": frames_ret,
        "funding": pd.DataFrame(0.0, index=idx, columns=list(closes)),
    }
    global LEDGER_END
    old_end = LEDGER_END
    LEDGER_END = idx[-1]
    try:
        path = run_ledger(
            frames,
            list(closes),
            {s: "crypto" for s in closes},
            tradfi_cost_per_side=0.001,
            crypto_cost_per_side=0.0014,
        )
        path_db = run_ledger(
            frames,
            list(closes),
            {s: "crypto" for s in closes},
            tradfi_cost_per_side=0.001,
            crypto_cost_per_side=0.0014,
            scale_deadband=0.10,
        )
        path_p4 = run_ledger(
            frames,
            list(closes),
            {s: "crypto" for s in closes},
            tradfi_cost_per_side=0.001,
            crypto_cost_per_side=0.0014,
            scale_deadband=0.10,
            target_vol=0.12,
            buffer_fraction=0.20,
        )
    finally:
        LEDGER_END = old_end
    assert (path["gross"] <= GROSS_CAP + 1e-9).all(), "gross cap violated"
    total = float((1.0 + path["net"]).prod())
    assert total > 1.0, f"two clean trends must beat noise, got {total}"
    assert path["turnover"].sum() / 3.3 < 40, "buffer must bound turnover"
    m = window_metrics(path, list(closes))
    assert abs(m["realized_ann_vol"] - TARGET_VOL) < 0.10, "vol target far off"
    # deadband checks: cap still enforced, scale changes rarer, turnover not higher
    assert (path_db["gross"] <= GROSS_CAP + 1e-9).all(), "gross cap violated (deadband)"
    changes_daily = int((path["scale"].diff().abs() > 1e-12).sum())
    changes_db = int((path_db["scale"].diff().abs() > 1e-12).sum())
    assert changes_db < changes_daily / 2, (
        f"deadband must cut scale updates: {changes_db} vs {changes_daily}"
    )
    assert path_db["turnover"].sum() <= path["turnover"].sum() + 1e-9, (
        "deadband must not raise turnover"
    )
    # P4 construction: realized vol tracks 12%, turnover strictly below P3-style run
    m_p4 = window_metrics(path_p4, list(closes))
    assert abs(m_p4["realized_ann_vol"] - 0.12) < 0.06, (
        f"12% vol target far off: {m_p4['realized_ann_vol']}"
    )
    assert path_p4["turnover"].sum() < path_db["turnover"].sum(), (
        "lower vol + wider buffer must cut turnover"
    )
    print("self-test passed")


# --- main ---------------------------------------------------------------------


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return

    base = load_base()
    run_date = args.run_date
    cfg = CONTRACTS[args.contract]
    prefix = cfg["prefix"]
    deadband = cfg["scale_deadband"]
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    target_vol = cfg["target_vol"]
    buffer_fraction = cfg["buffer_fraction"]
    tradfi_assets = dict(base.TRADFI_ASSETS)
    yahoo_dates = {sym: YAHOO_RUN_DATE for sym in base.TRADFI_ASSETS}
    if cfg["extra_tradfi"]:
        tradfi_assets.update(P3_EXTRA_TRADFI)
        yahoo_dates.update({sym: P3_YAHOO_RUN_DATE for sym in P3_EXTRA_TRADFI})

    panel, tradfi_quality, yahoo_manifest = build_panel(
        base, tradfi_assets, yahoo_dates, pairs=cfg["pairs"]
    )
    assets = list(panel)
    classes = {sym: entry["class"] for sym, entry in panel.items()}
    frames = union_frames(panel)

    built = portfolio_targets(
        frames,
        assets,
        scale_deadband=deadband,
        target_vol=target_vol,
        buffer_fraction=buffer_fraction,
    )
    n_active = built["n_active"]
    main_start = n_active[n_active >= MIN_ACTIVE_MAIN].index[0]
    btc_active = built["active"]["BTC"]
    crypto_start = btc_active[btc_active].index[0]
    scale_main = built["scale"].loc[main_start:]
    scale_updates_per_year = float(
        (scale_main.diff().abs() > 1e-12).sum()
        / max((scale_main.index[-1] - scale_main.index[0]).days / 365.25, 1e-9)
    )

    ledgers = {
        "stressed": TRADFI_STRESS_PER_SIDE,
        "diagnostic_zero_tradfi": 0.0,
    }
    summary: dict[str, Any] = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": cfg["spec"],
        "base_engine_sha256": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest(),
        "pool": assets,
        "params": {
            "target_vol": target_vol,
            "vol_halflife": VOL_HALFLIFE,
            "gross_cap": GROSS_CAP,
            "buffer_fraction": buffer_fraction,
            "ewmac_pairs": list(cfg["pairs"]) if cfg["pairs"] else "all_four",
            "scale_deadband": deadband,
            "min_active_main": MIN_ACTIVE_MAIN,
            "ffill_limit_days": FFILL_LIMIT,
            "ledger_end": str(LEDGER_END.date()),
            "crypto_cost_per_side": base.CRYPTO_COST_PER_SIDE,
            "tradfi_stress_per_side": TRADFI_STRESS_PER_SIDE,
        },
        "windows": {
            "main_start": str(main_start.date()),
            "crypto_era_start": str(crypto_start.date()),
        },
        "scale_applied_changes_per_year_main": round(scale_updates_per_year, 1),
        "data_quality_tradfi": tradfi_quality,
        "yahoo_manifest": yahoo_manifest,
        "ledgers": {},
    }

    recent: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    equity_curves: dict[str, pd.Series] = {}
    stressed_main: dict[str, Any] = {}
    stressed_crypto: dict[str, Any] = {}

    for name, tradfi_cost in ledgers.items():
        path = run_ledger(
            frames,
            assets,
            classes,
            tradfi_cost_per_side=tradfi_cost,
            crypto_cost_per_side=base.CRYPTO_COST_PER_SIDE,
            start=main_start,
            scale_deadband=deadband,
            target_vol=target_vol,
            buffer_fraction=buffer_fraction,
        )
        m_main = window_metrics(path, assets)
        m_crypto = window_metrics(path.loc[path.index >= crypto_start], assets)
        m_crypto["avg_pairwise_subsystem_corr"] = subsystem_correlation(
            path.loc[path.index >= crypto_start], assets
        )
        summary["ledgers"][name] = {"main_window": m_main, "crypto_era": m_crypto}
        recent.extend(recent_rows(path, name))
        yearly_rows.extend(
            {"variant": name, "year": y, "net_return": v}
            for y, v in m_main["yearly_net"].items()
        )
        equity_curves[name] = (1.0 + path["net"]).cumprod()
        if name == "stressed":
            stressed_main, stressed_crypto = m_main, m_crypto
            stressed_path = path

    # benchmarks (gross price, same windows)
    for bench, start in (("SPY", main_start), ("BTC", crypto_start)):
        r = frames["ret"][bench].loc[start:LEDGER_END]
        curve = (1.0 + r).cumprod()
        summary.setdefault("benchmarks", {})[f"{bench}_hold_from_{start.date()}"] = {
            "total_return": round(float(curve.iloc[-1] - 1.0), 4),
            "max_drawdown": round(drawdown_min(curve), 4),
        }

    # leave-one-out on crypto era, stressed ledger
    loo_rows = []
    for excluded in assets:
        rest = [s for s in assets if s != excluded]
        sub_path = run_ledger(
            frames,
            rest,
            classes,
            tradfi_cost_per_side=TRADFI_STRESS_PER_SIDE,
            crypto_cost_per_side=base.CRYPTO_COST_PER_SIDE,
            start=crypto_start,
            scale_deadband=deadband,
            target_vol=target_vol,
            buffer_fraction=buffer_fraction,
        )
        m = window_metrics(sub_path, rest)
        loo_rows.append(
            {
                "excluded": excluded,
                "total_net_return": m["total_net_return"],
                "sharpe_net": m["sharpe_net"],
                "max_drawdown": m["max_drawdown"],
            }
        )
    summary["leave_one_out_crypto_era_stressed"] = loo_rows

    g1 = cfg["g1_sharpe"]
    g1_key = f"G1_main_net_pos_and_sharpe_ge_{str(g1).replace('.', 'p')}"
    gates = {
        g1_key: stressed_main["total_net_return"] > 0
        and stressed_main["sharpe_net"] >= g1,
        "G2_main_mdd_lt_25pct": stressed_main["max_drawdown"] > -0.25,
        "G3_crypto_sharpe_ge_0p6_mdd_lt_25pct": stressed_crypto["sharpe_net"] >= 0.6
        and stressed_crypto["max_drawdown"] > -0.25,
        "G4_main_turnover_le_15x": stressed_main["ann_one_way_turnover"] <= 15.0,
        "G5_loo_all_positive": all(r["total_net_return"] > 0 for r in loo_rows),
    }
    gates["all_pass"] = all(gates.values())
    summary["gates"] = gates

    # portfolio-value diagnostic vs SPY (report obligation, not a gate):
    # union-calendar approximation, SPY daily returns are 0 on non-sessions
    strat_net = stressed_path["net"]
    spy_ret = frames["ret"]["SPY"].loc[strat_net.index]

    def _combo_stats(r: pd.Series) -> dict[str, float]:
        eq = (1.0 + r).cumprod()
        yrs = max((r.index[-1] - r.index[0]).days / 365.25, 1e-9)
        return {
            "cagr": round(float(eq.iloc[-1] ** (1.0 / yrs) - 1.0), 4),
            "sharpe": round(float(r.mean() / r.std() * math.sqrt(ANN_DAYS_UNION)), 3),
            "max_drawdown": round(drawdown_min(eq), 4),
        }

    summary["spy_combo_diagnostic_main_stressed"] = {
        "corr_daily_vs_spy": round(float(strat_net.corr(spy_ret)), 3),
        "spy_only": _combo_stats(spy_ret),
        "combo_50_strategy_50_spy_daily_rebalance": _combo_stats(
            0.5 * strat_net + 0.5 * spy_ret
        ),
    }

    # turnover decomposition (P4 report obligation, diagnostic only): start
    # from the P3 construction and change one lever at a time
    if args.contract == "p4":
        decomp = {}
        for label, tv, bf in (
            ("p3_construction_20pct_buffer0p10", 0.20, 0.10),
            ("only_vol_target_12pct", 0.12, 0.10),
            ("only_buffer_0p20", 0.20, 0.20),
            ("p4_both", 0.12, 0.20),
        ):
            d_path = run_ledger(
                frames,
                assets,
                classes,
                tradfi_cost_per_side=TRADFI_STRESS_PER_SIDE,
                crypto_cost_per_side=base.CRYPTO_COST_PER_SIDE,
                start=main_start,
                scale_deadband=deadband,
                target_vol=tv,
                buffer_fraction=bf,
            )
            yrs = max((d_path.index[-1] - d_path.index[0]).days / 365.25, 1e-9)
            decomp[label] = round(float(d_path["turnover"].sum() / yrs), 2)
        summary["turnover_decomposition_ann_one_way"] = decomp

    # artifacts
    pd.DataFrame(yearly_rows).to_csv(
        ARTIFACT_DIR / f"{prefix}_yearly_{run_date}.csv", index=False
    )
    pd.DataFrame(recent).to_csv(
        ARTIFACT_DIR / f"{prefix}_recent_{run_date}.csv", index=False
    )
    pd.DataFrame(loo_rows).to_csv(
        ARTIFACT_DIR / f"{prefix}_loo_{run_date}.csv", index=False
    )
    # cluster-by-year PnL contribution (stressed ledger, additive return units)
    contrib_daily = pd.DataFrame(
        {sym: stressed_path[f"pnl_{sym}"] for sym in assets}
    )
    cluster_daily = contrib_daily.T.groupby(
        contrib_daily.columns.map(CLUSTERS)
    ).sum().T
    cluster_yearly = cluster_daily.groupby(cluster_daily.index.year).sum().round(4)
    cluster_yearly.to_csv(ARTIFACT_DIR / f"{prefix}_cluster_yearly_{run_date}.csv")
    metric_rows = []
    for name, entry in summary["ledgers"].items():
        for window, m in entry.items():
            metric_rows.append(
                {
                    "variant": name,
                    "window": window,
                    **{k: v for k, v in m.items() if not isinstance(v, dict)},
                }
            )
    pd.DataFrame(metric_rows).to_csv(
        ARTIFACT_DIR / f"{prefix}_metrics_{run_date}.csv", index=False
    )
    curves = pd.DataFrame(equity_curves)
    curves.reset_index(names="day").to_parquet(
        ARTIFACT_DIR / f"{prefix}_equity_{run_date}.parquet", index=False
    )
    if cfg["extra_tradfi"]:
        new_manifest = {
            sym: yahoo_manifest[sym] for sym in P3_EXTRA_TRADFI if sym in yahoo_manifest
        }
        (base.YAHOO_RAW_DIR / f"manifest_{P3_YAHOO_RUN_DATE}.json").write_text(
            json.dumps(new_manifest, indent=2), encoding="utf-8"
        )

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(
        3, 1, figsize=(12, 10), sharex=True, gridspec_kw={"height_ratios": [3, 1, 1]}
    )
    stressed_eq = equity_curves["stressed"]
    diag_eq = equity_curves["diagnostic_zero_tradfi"]
    spy = (1.0 + frames["ret"]["SPY"].loc[main_start:LEDGER_END]).cumprod()
    axes[0].plot(stressed_eq.index, stressed_eq, lw=1.4, label="portfolio (stressed costs)")
    axes[0].plot(diag_eq.index, diag_eq, lw=0.9, alpha=0.7, label="portfolio (0-cost tradfi)")
    axes[0].plot(spy.index, spy, lw=0.8, alpha=0.6, label="SPY buy&hold")
    axes[0].axvline(crypto_start, color="gray", ls="--", lw=0.8, alpha=0.7)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity (log)")
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    dd = stressed_eq / stressed_eq.cummax() - 1.0
    axes[1].plot(dd.index, dd, lw=0.9, color="tab:red")
    axes[1].set_ylabel("drawdown")
    axes[1].grid(alpha=0.3)
    axes[2].plot(stressed_path.index, stressed_path["gross"], lw=0.7)
    axes[2].set_ylabel("gross lev")
    axes[2].grid(alpha=0.3)
    fig.suptitle(
        f"XA-1D-EWMAC-UT {args.contract.upper()}: {len(assets)}-asset equal-risk "
        "portfolio, 20% vol target "
        f"(main window from {main_start.date()}, dashed = crypto era)"
    )
    fig.tight_layout()
    fig.savefig(ARTIFACT_DIR / f"{prefix}_equity_{run_date}.png", dpi=150)

    out = ARTIFACT_DIR / f"{prefix}_summary_{run_date}.json"
    out.write_text(
        json.dumps(base.clean_json(summary), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(base.clean_json(summary["gates"]), indent=2))
    for name in ledgers:
        m = summary["ledgers"][name]["main_window"]
        c = summary["ledgers"][name]["crypto_era"]
        print(
            f"{name:22s} main: total={m['total_net_return']:+.2%} sharpe={m['sharpe_net']:.2f} "
            f"mdd={m['max_drawdown']:.2%} to={m['ann_one_way_turnover']:.1f}x | "
            f"crypto-era: total={c['total_net_return']:+.2%} sharpe={c['sharpe_net']:.2f} "
            f"mdd={c['max_drawdown']:.2%}"
        )
    print("report ->", out)


if __name__ == "__main__":
    main()
