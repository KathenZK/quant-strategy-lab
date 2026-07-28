"""P2 portfolio backtest, control group A (no model) for BIN-4H-EMAX.

Implements the pre-registered contract in
specs/bin-4h-emax-portfolio-contract-2026-07-24.md. Two variants:

  A1  ungated: every trading-pool death-cross short (bracket b4_2)
  A2  regime-gated: new entries only when BTC's previous completed UTC daily
      close is below its daily EMA96 (single pre-registered gate, no search)

Event-driven simulation on the corrected dev events (majors included).
Costs (fee 0.001 + slip 4bps per side + as-of funding) are already inside
``b4_2_net_frac``. Equity is realized-at-exit; capital is freed at the END of
the exit bar (exit_ts + 4h), a conservative, documented convention.
"""

from __future__ import annotations

import heapq
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_baseline as rb  # noqa: E402  (family baseline module: paths + cache)

FAMILY_DIR = ROOT / "research/asset-portfolios/4h-ema-cross-lightgbm-event-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"

BRACKET = "b4_2"
K_SL = 2.0
INITIAL_EQUITY = 100_000.0
RISK_PER_TRADE = 0.005
MAX_NOTIONAL_FRAC = 0.10
MAX_POSITIONS = 20
MAX_GROSS_LEVERAGE = 2.0
BAR = pd.Timedelta(hours=4)


def load_short_pool_events() -> pd.DataFrame:
    events = pd.read_parquet(ARTIFACT_DIR / "events_dev_4h.parquet")
    events["entry_ts"] = pd.to_datetime(events["entry_ts"], utc=True)
    events[f"{BRACKET}_exit_ts"] = pd.to_datetime(events[f"{BRACKET}_exit_ts"], utc=True)
    pool = events.loc[(events["in_trading_pool"]) & (events["side"] == -1)].copy()
    return pool.sort_values(["entry_ts", "sym_key"]).reset_index(drop=True)


def btc_gate_days() -> set[pd.Timestamp]:
    """UTC days D such that day (D-1)'s BTC close < its daily EMA96 (known at D 00:00)."""
    btc = rb.load_symbol_frame("BTC")
    daily = btc.set_index("ts")["close"].resample("1D").last().dropna()
    ema96 = daily.ewm(span=96, adjust=False).mean()
    below = daily < ema96
    return {day + pd.Timedelta(days=1) for day, flag in below.items() if flag}


def simulate(events: pd.DataFrame, gate_days: set[pd.Timestamp] | None) -> dict:
    equity = INITIAL_EQUITY
    open_symbols: set[str] = set()
    gross_notional = 0.0
    # heap items: (release_ts, sym_key, notional, pnl, exit_ts)
    exit_heap: list[tuple[pd.Timestamp, str, float, float, pd.Timestamp]] = []
    bookings: list[tuple[pd.Timestamp, float]] = []  # (release_ts, pnl)
    trades: list[dict] = []
    skips = {"gate": 0, "symbol_open": 0, "capacity": 0, "leverage": 0}
    concurrency_samples: list[int] = []

    for row in events.itertuples(index=False):
        entry_ts = row.entry_ts
        while exit_heap and exit_heap[0][0] <= entry_ts:
            _, sym, notional, pnl, _ = heapq.heappop(exit_heap)
            open_symbols.discard(sym)
            gross_notional -= notional
            equity += pnl
        concurrency_samples.append(len(open_symbols))

        if gate_days is not None and entry_ts.normalize() not in gate_days:
            skips["gate"] += 1
            continue
        if row.sym_key in open_symbols:
            skips["symbol_open"] += 1
            continue
        if len(open_symbols) >= MAX_POSITIONS:
            skips["capacity"] += 1
            continue
        notional = min(
            equity * RISK_PER_TRADE / (K_SL * row.atr_frac),
            equity * MAX_NOTIONAL_FRAC,
        )
        if gross_notional + notional > MAX_GROSS_LEVERAGE * equity:
            skips["leverage"] += 1
            continue

        net_frac = getattr(row, f"{BRACKET}_net_frac")
        exit_ts = getattr(row, f"{BRACKET}_exit_ts")
        release_ts = exit_ts + BAR
        pnl = notional * net_frac
        open_symbols.add(row.sym_key)
        gross_notional += notional
        heapq.heappush(exit_heap, (release_ts, row.sym_key, notional, pnl, exit_ts))
        bookings.append((release_ts, pnl))
        trades.append(
            {
                "entry_ts": entry_ts,
                "exit_ts": exit_ts,
                "sym_key": row.sym_key,
                "notional": notional,
                "pnl": pnl,
                "net_atr": getattr(row, f"{BRACKET}_net_atr"),
            }
        )

    while exit_heap:
        _, sym, notional, pnl, _ = heapq.heappop(exit_heap)
        equity += pnl

    booked = pd.DataFrame(bookings, columns=["ts", "pnl"]).sort_values("ts")
    curve_index = pd.date_range(
        events["entry_ts"].min().floor("D"),
        booked["ts"].max().ceil("D"),
        freq="4h",
        tz="UTC",
    )
    pnl_by_bar = booked.set_index("ts")["pnl"].groupby(level=0).sum()
    curve = pnl_by_bar.reindex(curve_index, fill_value=0.0).cumsum() + INITIAL_EQUITY
    return {
        "final_equity": equity,
        "curve": curve,
        "trades": pd.DataFrame(trades),
        "skips": skips,
        "avg_concurrency": float(np.mean(concurrency_samples)),
        "max_concurrency": int(np.max(concurrency_samples)),
    }


def drawdown_stats(curve: pd.Series) -> dict:
    running_max = curve.cummax()
    dd = curve / running_max - 1.0
    trough_ts = dd.idxmin()
    return {
        "max_drawdown": round(float(dd.min()), 4),
        "max_drawdown_trough_ts": str(trough_ts),
    }


def periodic_returns(curve: pd.Series, freq: str) -> pd.Series:
    period_end = curve.resample(freq).last()
    period_start = period_end.shift(1)
    period_start.iloc[0] = INITIAL_EQUITY
    return period_end / period_start - 1.0


def summarize(name: str, result: dict, dev_end: pd.Timestamp) -> dict:
    curve = result["curve"]
    trades = result["trades"]
    years_span = (curve.index[-1] - curve.index[0]).days / 365.25
    total_return = result["final_equity"] / INITIAL_EQUITY - 1.0
    monthly = periodic_returns(curve, "ME")
    yearly = periodic_returns(curve, "YE")
    pnl_by_year = trades.set_index("exit_ts")["pnl"].groupby(lambda ts: ts.year).sum()
    total_pnl = float(trades["pnl"].sum())
    worst_months = monthly.nsmallest(5)
    squeeze_months = {
        month: round(float(monthly.get(pd.Timestamp(month, tz="UTC") + pd.offsets.MonthEnd(0), np.nan)), 4)
        for month in ("2021-01-31", "2021-02-28", "2021-08-31", "2021-10-31", "2022-06-30")
    }
    slices = {"1d": 1, "7d": 7, "1m": 30, "3m": 91, "6m": 182, "1y": 365}
    recent = {}
    for label, days in slices.items():
        window = trades.loc[trades["exit_ts"] >= dev_end - pd.Timedelta(days=days)]
        recent[label] = {
            "trades": int(len(window)),
            "pnl": round(float(window["pnl"].sum()), 2),
        }
    return {
        "variant": name,
        "final_equity": round(result["final_equity"], 2),
        "total_return": round(total_return, 4),
        "cagr": round((1 + total_return) ** (1 / years_span) - 1, 4),
        **drawdown_stats(curve),
        "trades": int(len(trades)),
        "share_trades_positive": round(float((trades["pnl"] > 0).mean()), 4),
        "skips": result["skips"],
        "avg_concurrency": round(result["avg_concurrency"], 2),
        "max_concurrency": result["max_concurrency"],
        "yearly_returns": {str(ts.year): round(float(v), 4) for ts, v in yearly.items()},
        "pnl_share_2022": round(float(pnl_by_year.get(2022, 0.0)) / total_pnl, 4)
        if total_pnl > 0
        else None,
        "worst_5_months": {str(ts.date()): round(float(v), 4) for ts, v in worst_months.items()},
        "stress_months": squeeze_months,
        "monthly_returns": {str(ts.date()): round(float(v), 4) for ts, v in monthly.items()},
        "recent_slices_audit_only": recent,
    }


def main() -> None:
    events = load_short_pool_events()
    dev_end = events["entry_ts"].max()
    gate_days = btc_gate_days()

    results = {
        "A1_ungated": simulate(events, None),
        "A2_btc_ema96_gated": simulate(events, gate_days),
    }

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-4h-emax-portfolio-contract-2026-07-24.md",
        "market": "Binance USD-M USDT perp, 4h (derived from audited 1h), point-in-time top-120 pool",
        "window_utc": [str(events["entry_ts"].min()), str(dev_end)],
        "cost_model": "fee 0.001 + slip 4bps per side + as-of funding (inside net_frac)",
        "bracket": BRACKET,
        "sizing": {
            "initial_equity": INITIAL_EQUITY,
            "risk_per_trade": RISK_PER_TRADE,
            "max_notional_frac": MAX_NOTIONAL_FRAC,
            "max_positions": MAX_POSITIONS,
            "max_gross_leverage": MAX_GROSS_LEVERAGE,
        },
        "pool_short_events": int(len(events)),
        "gate_days": len(gate_days),
        "variants": {name: summarize(name, result, dev_end) for name, result in results.items()},
    }

    curves = pd.DataFrame(
        {name: result["curve"] for name, result in results.items()}
    ).reset_index(names="ts")
    curves.to_parquet(ARTIFACT_DIR / "portfolio_control_a_equity.parquet", index=False)
    for name, result in results.items():
        result["trades"].to_parquet(
            ARTIFACT_DIR / f"portfolio_control_a_trades_{name}.parquet", index=False
        )

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1]})
    for name, result in results.items():
        axes[0].plot(result["curve"].index, result["curve"].to_numpy(), label=name, linewidth=1.2)
        dd = result["curve"] / result["curve"].cummax() - 1.0
        axes[1].plot(dd.index, dd.to_numpy(), label=name, linewidth=1.0)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity (USDT, log)")
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    axes[1].set_ylabel("drawdown")
    axes[1].grid(alpha=0.3)
    fig.suptitle("BIN-4H-EMAX control-A short-only portfolio (dev 2020-2025, b4_2)")
    fig.tight_layout()
    fig.savefig(ARTIFACT_DIR / "portfolio_control_a_equity.png", dpi=150)

    output = ARTIFACT_DIR / "portfolio_control_a_report.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for name, summary in report["variants"].items():
        compact = {k: summary[k] for k in (
            "final_equity", "total_return", "cagr", "max_drawdown", "trades",
            "yearly_returns", "pnl_share_2022", "skips", "avg_concurrency", "max_concurrency",
        )}
        print(name, json.dumps(compact, ensure_ascii=False))
    print(f"report -> {output}")


if __name__ == "__main__":
    main()
