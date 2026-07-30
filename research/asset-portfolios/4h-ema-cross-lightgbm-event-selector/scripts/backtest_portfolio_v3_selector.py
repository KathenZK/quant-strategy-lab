"""V3 lean-selector portfolio backtest for BIN-4H-EMAX.

Implements the frozen contract in
specs/bin-4h-emax-v3-lean-selector-portfolio-contract-2026-07-30.md.

Variants (pre-registered, no threshold search):
  B0  control: all in-pool two-sided events in the window, unfiltered
  S1  absolute threshold: score_local_trend > 0
  S2  primary: score > trailing-365d (exclusive) 90th percentile of all
      scored events; requires >= 200 trailing scored events, else no trade

Scores are the year-wise expanding-window OOF scores produced by
research_local_trend_selector.py, so every 2022-2025 event is scored by a
model that only saw prior years. Portfolio machinery (sizing, capacity,
leverage, release timing, summary) is reused verbatim from the P2 control-A
script; costs live inside b4_2_net_frac.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest_portfolio_control_a as ca  # noqa: E402
import run_baseline as rb  # noqa: E402

OUT_DIR = rb.ARTIFACT_DIR / "v3_portfolio"
WINDOW_START = pd.Timestamp("2022-01-01", tz="UTC")
TRAIL = pd.Timedelta(days=365)
TRAIL_MIN_EVENTS = 200
TRAIL_QUANTILE = 0.90


def load_scored_pool() -> pd.DataFrame:
    events = pd.read_parquet(rb.ARTIFACT_DIR / "events_dev_4h.parquet")
    events["entry_ts"] = pd.to_datetime(events["entry_ts"], utc=True)
    events["b4_2_exit_ts"] = pd.to_datetime(events["b4_2_exit_ts"], utc=True)
    pool = events.loc[events["in_trading_pool"]].copy()

    scores = pd.read_parquet(
        rb.ARTIFACT_DIR / "local_trend_selector/oof_scores_local_trend.parquet"
    )[["sym_key", "entry_ts", "side", "score_local_trend"]]
    scores["entry_ts"] = pd.to_datetime(scores["entry_ts"], utc=True)
    merged = pool.merge(scores, on=["sym_key", "entry_ts", "side"], how="left", validate="1:1")

    window = merged.loc[merged["entry_ts"] >= WINDOW_START].copy()
    n_missing = int(window["score_local_trend"].isna().sum())
    if n_missing:
        raise RuntimeError(f"{n_missing} window events missing OOF scores")
    return window.sort_values(["entry_ts", "sym_key"]).reset_index(drop=True)


def trailing_quantile_mask(events: pd.DataFrame) -> pd.Series:
    """Causal S2 selection: score > q90 of trailing-365d scores (exclusive)."""
    ts = events["entry_ts"].astype("int64").to_numpy()
    scores = events["score_local_trend"].to_numpy()
    lo = np.searchsorted(ts, ts - TRAIL.value, side="left")
    hi = np.searchsorted(ts, ts, side="left")  # excludes same-timestamp events
    selected = np.zeros(len(events), dtype=bool)
    for i in range(len(events)):
        window = scores[lo[i]:hi[i]]
        if len(window) < TRAIL_MIN_EVENTS:
            continue
        selected[i] = scores[i] > np.quantile(window, TRAIL_QUANTILE)
    return pd.Series(selected, index=events.index)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    events = load_scored_pool()
    dev_end = events["entry_ts"].max()
    s2_mask = trailing_quantile_mask(events)

    variants = {
        "B0_unfiltered": events,
        "S1_score_gt0": events.loc[events["score_local_trend"] > 0].reset_index(drop=True),
        "S2_trailing_q90": events.loc[s2_mask].reset_index(drop=True),
    }
    results = {name: ca.simulate(evs, None) for name, evs in variants.items()}
    summaries = {name: ca.summarize(name, res, dev_end) for name, res in results.items()}

    for name, evs in variants.items():
        trades = results[name]["trades"]
        merged = trades.merge(
            events[["sym_key", "entry_ts", "side"]], on=["sym_key", "entry_ts"], how="left"
        )
        by_side = merged.groupby("side")["pnl"].agg(["count", "sum"])
        summaries[name]["events_selected"] = int(len(evs))
        summaries[name]["side_breakdown"] = {
            {1: "long", -1: "short"}[int(side)]: {
                "trades": int(row["count"]),
                "pnl": round(float(row["sum"]), 2),
            }
            for side, row in by_side.iterrows()
        }

    s2 = summaries["S2_trailing_q90"]
    b0 = summaries["B0_unfiltered"]
    ret_over_dd = lambda s: s["total_return"] / abs(s["max_drawdown"]) if s["max_drawdown"] else np.nan
    yearly_pos = sum(1 for v in s2["yearly_returns"].values() if v > 0)
    total_pnl = s2["final_equity"] - ca.INITIAL_EQUITY
    max_year_share = None
    if total_pnl > 0:
        trades = results["S2_trailing_q90"]["trades"]
        pnl_by_year = trades.set_index("exit_ts")["pnl"].groupby(lambda t: t.year).sum()
        max_year_share = round(float(pnl_by_year.max()) / total_pnl, 4)
    gates = {
        "G1_maxdd_lt_40pct": bool(s2["max_drawdown"] > -0.40),
        "G2_yearly_robust": bool(
            yearly_pos >= 3 and (max_year_share is None or max_year_share <= 0.60)
        ),
        "G3_total_return_positive": bool(s2["total_return"] > 0),
        "G4_adds_value_vs_b0": bool(
            s2["max_drawdown"] > b0["max_drawdown"]
            and ret_over_dd(s2) > ret_over_dd(b0)
        ),
    }
    gates["ALL_PASS"] = all(gates.values())

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-4h-emax-v3-lean-selector-portfolio-contract-2026-07-30.md",
        "market": "Binance USD-M USDT perp, 4h (derived from audited 1h), point-in-time top-120 pool",
        "window_utc": [str(events["entry_ts"].min()), str(dev_end)],
        "cost_model": "fee 0.001 + slip 4bps per side + as-of funding (inside net_frac)",
        "bracket": ca.BRACKET,
        "sizing": {
            "initial_equity": ca.INITIAL_EQUITY,
            "risk_per_trade": ca.RISK_PER_TRADE,
            "max_notional_frac": ca.MAX_NOTIONAL_FRAC,
            "max_positions": ca.MAX_POSITIONS,
            "max_gross_leverage": ca.MAX_GROSS_LEVERAGE,
        },
        "s2_rule": {
            "trailing_days": 365,
            "quantile": TRAIL_QUANTILE,
            "min_trailing_events": TRAIL_MIN_EVENTS,
        },
        "pool_events_window": int(len(events)),
        "kill_gates_s2": gates,
        "ret_over_dd": {name: round(ret_over_dd(s), 3) for name, s in summaries.items()},
        "variants": summaries,
    }

    curves = pd.DataFrame(
        {name: res["curve"] for name, res in results.items()}
    ).reset_index(names="ts")
    curves.to_parquet(OUT_DIR / "v3_portfolio_equity.parquet", index=False)
    for name, res in results.items():
        res["trades"].to_parquet(OUT_DIR / f"v3_portfolio_trades_{name}.parquet", index=False)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1]})
    for name, res in results.items():
        axes[0].plot(res["curve"].index, res["curve"].to_numpy(), label=name, linewidth=1.2)
        dd = res["curve"] / res["curve"].cummax() - 1.0
        axes[1].plot(dd.index, dd.to_numpy(), label=name, linewidth=1.0)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity (USDT, log)")
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    axes[1].set_ylabel("drawdown")
    axes[1].grid(alpha=0.3)
    fig.suptitle("BIN-4H-EMAX V3 lean-selector portfolio (2022-2025, b4_2, two-sided)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "v3_portfolio_equity.png", dpi=150)

    out = OUT_DIR / "v3_portfolio_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for name, s in summaries.items():
        compact = {k: s[k] for k in (
            "events_selected", "final_equity", "total_return", "cagr", "max_drawdown",
            "trades", "yearly_returns", "side_breakdown", "avg_concurrency", "max_concurrency",
        )}
        print(name, json.dumps(compact, ensure_ascii=False))
    print("kill_gates_s2:", json.dumps(gates, ensure_ascii=False))
    print(f"report -> {out}")


if __name__ == "__main__":
    main()
