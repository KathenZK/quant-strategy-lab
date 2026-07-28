"""P0 demo backtest for BIN-1D-TSMOM-VT.

Implements the pre-registered contract in
specs/bin-1d-tsmom-vt-demo-contract-2026-07-27.md:

  signal   classic TSMOM sign ensemble over 30/91/182/365-day lookbacks
  sizing   inverse-vol asset weights (EWMA hl=20), Sum|w|=1, cap 0.10,
           portfolio-level vol targeting at 20% ann. with 2.0x gross cap
  universe point-in-time monthly top-30 crypto perps by 30d ADV (>= $10M,
           >= 91 trading days history), stables/fiat/non-crypto excluded
  costs    fee 0.001 + slip 4bps per side on turnover; daily as-of funding
  window   eval 2021-01-01..2025-12-31 UTC (2020 warmup only; 2026H1 excluded)

Data: audited 1h Vision archives resampled to 1d (emax_1d_derived cache,
provenance recorded by the BIN-1D-EMAX baseline). No parameter was tuned on
results; every constant below is frozen in the contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(
    0, str(ROOT / "research/asset-portfolios/15m-ema-cross-lightgbm-event-selector/scripts")
)
import emax_common as ec  # noqa: E402  (frozen 15m engine, pure functions reused)

FAMILY_DIR = ROOT / "research/asset-portfolios/1d-multi-asset-tsmom-vol-target"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CACHE = ROOT / "data/cache/emax_1d_derived/klines_by_symbol"

LOOKBACKS = (30, 91, 182, 365)
MIN_LOOKBACKS = 2
VOL_HALFLIFE = 20
ANNUALIZER = np.sqrt(365.0)
TARGET_VOL = 0.20
MAX_LEVERAGE = 2.0
WEIGHT_CAP = 0.10
TOP_N = 30
MIN_ADV_USDT = 1e7
MIN_HISTORY_DAYS = 91
FEE_SLIP_PER_SIDE = 0.001 + 0.0004
WARMUP_UNIVERSE_START = pd.Timestamp("2020-07-01")
EVAL_START = pd.Timestamp("2021-01-01")
EVAL_END = pd.Timestamp("2025-12-31")
INITIAL_EQUITY = 100_000.0


def load_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    con = ec.connect()
    panel = con.execute(
        f"""
        SELECT sym_key, CAST(ts AS DATE) AS day, close, quote_volume
        FROM read_parquet('{CACHE}/**/*.parquet', hive_partitioning=true)
        ORDER BY sym_key, day
        """
    ).fetch_df()
    panel = panel.loc[~panel["sym_key"].isin(ec.excluded_bases())]
    panel["day"] = pd.to_datetime(panel["day"])
    panel = panel.loc[panel["day"] <= EVAL_END]
    close = panel.pivot(index="day", columns="sym_key", values="close")
    qv = panel.pivot(index="day", columns="sym_key", values="quote_volume")
    full_index = pd.date_range(close.index.min(), EVAL_END, freq="D")
    return close.reindex(full_index), qv.reindex(full_index)


def build_universe(close: pd.DataFrame, qv: pd.DataFrame) -> pd.DataFrame:
    adv30 = qv.rolling(30, min_periods=30).mean()
    history = close.notna().cumsum()
    universe = pd.DataFrame(False, index=close.index, columns=close.columns)
    for month_start in pd.date_range(WARMUP_UNIVERSE_START, EVAL_END, freq="MS"):
        asof = month_start - pd.Timedelta(days=1)
        adv_asof = adv30.loc[:asof].iloc[-1]
        hist_asof = history.loc[:asof].iloc[-1]
        eligible = adv_asof[(hist_asof >= MIN_HISTORY_DAYS) & (adv_asof >= MIN_ADV_USDT)]
        members = eligible.nlargest(TOP_N).index
        month_end = min(month_start + pd.offsets.MonthEnd(0), close.index[-1])
        universe.loc[month_start:month_end, members] = True
    return universe


def build_signal(close: pd.DataFrame) -> pd.DataFrame:
    c1 = close.shift(1)  # decisions for day T use closes through T-1
    signs = [np.sign(c1 / close.shift(1 + k) - 1.0) for k in LOOKBACKS]
    available = sum(s.notna().astype(int) for s in signs)
    total = sum(s.fillna(0.0) for s in signs)
    return total / available.where(available >= MIN_LOOKBACKS)


def build_weights(
    close: pd.DataFrame, universe: pd.DataFrame
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    ret = close.pct_change()
    sigma = ret.ewm(halflife=VOL_HALFLIFE, min_periods=VOL_HALFLIFE).std().shift(1) * ANNUALIZER
    signal = build_signal(close)

    raw = (signal / sigma).where(universe & signal.notna() & (sigma > 0.01) & close.shift(1).notna())
    gross = raw.abs().sum(axis=1)
    w = raw.div(gross.where(gross > 0), axis=0).fillna(0.0)
    w = w.clip(-WEIGHT_CAP, WEIGHT_CAP)

    ret_fill = ret.fillna(0.0)
    rp_unscaled = (w * ret_fill).sum(axis=1)
    sigma_p = (
        rp_unscaled.ewm(halflife=VOL_HALFLIFE, min_periods=VOL_HALFLIFE).std().shift(1) * ANNUALIZER
    )
    scale = (TARGET_VOL / sigma_p).clip(upper=MAX_LEVERAGE).fillna(0.0)
    return w.mul(scale, axis=0), scale, ret_fill


def load_daily_funding(index: pd.DatetimeIndex, columns: pd.Index) -> pd.DataFrame:
    funding = ec.load_funding()
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding["day"] = funding["ts"].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)
    daily = funding.groupby(["day", "sym_key"])["funding_rate"].sum().unstack()
    return daily.reindex(index=index, columns=columns)


def drawdown(curve: pd.Series) -> pd.Series:
    return curve / curve.cummax() - 1.0


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    close, qv = load_panel()
    universe = build_universe(close, qv)
    weights, scale, ret_fill = build_weights(close, universe)

    fr = load_daily_funding(close.index, close.columns)
    held = weights.abs() > 0
    funding_coverage = float((held & fr.notna()).to_numpy().sum() / max(held.to_numpy().sum(), 1))
    funding_pnl = -(weights * fr.fillna(0.0)).sum(axis=1)  # long pays positive funding

    turnover = (weights - weights.shift(1).fillna(0.0)).abs().sum(axis=1)
    cost = turnover * FEE_SLIP_PER_SIDE
    price_pnl = (weights * ret_fill).sum(axis=1)
    net = price_pnl - cost + funding_pnl

    mask = (net.index >= EVAL_START) & (net.index <= EVAL_END)
    net_eval = net[mask]
    equity = (1.0 + net_eval).cumprod() * INITIAL_EQUITY
    dd = drawdown(equity)

    years = net_eval.index.year
    yearly_net = equity.resample("YE").last() / equity.resample("YE").last().shift(1).fillna(
        INITIAL_EQUITY
    ) - 1.0
    pnl_daily = equity.diff().fillna(equity.iloc[0] - INITIAL_EQUITY)
    pnl_by_year = pnl_daily.groupby(pnl_daily.index.year).sum()
    total_pnl = float(pnl_daily.sum())

    long_ret = (weights.clip(lower=0.0) * ret_fill).sum(axis=1)[mask]
    short_ret = (weights.clip(upper=0.0) * ret_fill).sum(axis=1)[mask]
    gross_lev = weights.abs().sum(axis=1)[mask]

    ann_vol = float(net_eval.std() * ANNUALIZER)
    sharpe = float(net_eval.mean() / net_eval.std() * ANNUALIZER) if net_eval.std() > 0 else np.nan
    total_return = float(equity.iloc[-1] / INITIAL_EQUITY - 1.0)
    n_years = (net_eval.index[-1] - net_eval.index[0]).days / 365.25
    cagr = (1.0 + total_return) ** (1.0 / n_years) - 1.0

    btc_ret = close["BTC"].pct_change()[mask].fillna(0.0)
    btc_curve = (1.0 + btc_ret).cumprod() * INITIAL_EQUITY

    contrib = (weights * ret_fill)[mask].sum().sort_values()
    hype_days = universe["HYPE"][mask].sum() if "HYPE" in universe.columns else 0
    hype_first = (
        str(universe.index[universe["HYPE"]].min().date())
        if "HYPE" in universe.columns and universe["HYPE"].any()
        else None
    )

    slices = {"1d": 1, "7d": 7, "1m": 30, "3m": 91, "6m": 182, "1y": 365}
    recent = {
        label: round(float(equity.iloc[-1] / equity.loc[: EVAL_END - pd.Timedelta(days=d)].iloc[-1] - 1.0), 4)
        for label, d in slices.items()
    }

    max_year_share = (
        round(float(pnl_by_year.max()) / total_pnl, 4) if total_pnl > 0 else None
    )
    evaluation = {
        "1_total_positive_and_3of5_years": bool(
            total_return > 0 and int((yearly_net > 0).sum()) >= 3
        ),
        "2_max_year_pnl_share_lt_0p7": bool(max_year_share is not None and max_year_share < 0.7),
        "3_realized_vol_in_10_30": bool(0.10 <= ann_vol <= 0.30),
        "4_max_dd_lt_40pct": bool(dd.min() > -0.40),
    }

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-1d-tsmom-vt-demo-contract-2026-07-27.md",
        "market": "Binance USD-M USDT crypto perp, 1d (derived from audited 1h), "
        "point-in-time monthly top-30 by ADV30",
        "window_utc": [str(EVAL_START.date()), str(EVAL_END.date())],
        "cost_model": "fee 0.001 + slip 4bps per side on turnover + daily as-of funding",
        "params": {
            "lookbacks_days": list(LOOKBACKS),
            "min_lookbacks": MIN_LOOKBACKS,
            "vol_halflife_days": VOL_HALFLIFE,
            "target_vol": TARGET_VOL,
            "max_gross_leverage": MAX_LEVERAGE,
            "weight_cap": WEIGHT_CAP,
            "top_n": TOP_N,
            "min_adv_usdt": MIN_ADV_USDT,
        },
        "results": {
            "final_equity": round(float(equity.iloc[-1]), 2),
            "total_return": round(total_return, 4),
            "cagr": round(float(cagr), 4),
            "sharpe_net": round(sharpe, 3),
            "realized_ann_vol": round(ann_vol, 4),
            "max_drawdown": round(float(dd.min()), 4),
            "max_dd_trough": str(dd.idxmin().date()),
            "yearly_returns": {str(ts.year): round(float(v), 4) for ts, v in yearly_net.items()},
            "max_year_pnl_share": max_year_share,
            "avg_gross_leverage": round(float(gross_lev.mean()), 3),
            "max_gross_leverage": round(float(gross_lev.max()), 3),
            "ann_one_way_turnover": round(float(turnover[mask].mean() * 365), 1),
        },
        "attribution_return_units": {
            "price_pnl": round(float(price_pnl[mask].sum()), 4),
            "trading_cost": round(float(-cost[mask].sum()), 4),
            "funding_pnl": round(float(funding_pnl[mask].sum()), 4),
            "long_sleeve_by_year": {
                str(y): round(float(v), 4) for y, v in long_ret.groupby(years).sum().items()
            },
            "short_sleeve_by_year": {
                str(y): round(float(v), 4) for y, v in short_ret.groupby(years).sum().items()
            },
        },
        "funding_coverage_weighted_days": round(funding_coverage, 4),
        "btc_buy_hold": {
            "total_return": round(float(btc_curve.iloc[-1] / INITIAL_EQUITY - 1.0), 4),
            "max_drawdown": round(float(drawdown(btc_curve).min()), 4),
            "realized_ann_vol": round(float(btc_ret.std() * ANNUALIZER), 4),
        },
        "hype": {"days_in_universe_eval": int(hype_days), "first_universe_day": hype_first},
        "top_contributors_return_units": {
            k: round(float(v), 4) for k, v in contrib.tail(10)[::-1].items()
        },
        "bottom_contributors_return_units": {
            k: round(float(v), 4) for k, v in contrib.head(10).items()
        },
        "recent_slices_audit_only": recent,
        "pre_registered_evaluation": evaluation,
    }

    curves = pd.DataFrame(
        {"ts": equity.index, "tsmom_vt": equity.to_numpy(), "btc_hold": btc_curve.to_numpy()}
    )
    curves.to_parquet(ARTIFACT_DIR / "tsmom_vt_demo_equity.parquet", index=False)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(
        3, 1, figsize=(11, 10), sharex=True, gridspec_kw={"height_ratios": [3, 1, 1]}
    )
    axes[0].plot(equity.index, equity.to_numpy(), label="TSMOM + vol target (net)", lw=1.4)
    axes[0].plot(btc_curve.index, btc_curve.to_numpy(), label="BTC buy & hold", lw=1.0, alpha=0.7)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity (USDT, log)")
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    axes[1].plot(dd.index, dd.to_numpy(), lw=1.0, color="tab:red", label="strategy DD")
    axes[1].plot(
        btc_curve.index, drawdown(btc_curve).to_numpy(), lw=0.8, alpha=0.5, label="BTC DD"
    )
    axes[1].set_ylabel("drawdown")
    axes[1].legend()
    axes[1].grid(alpha=0.3)
    axes[2].plot(gross_lev.index, gross_lev.to_numpy(), lw=0.8, label="gross leverage")
    axes[2].set_ylabel("gross lev")
    axes[2].grid(alpha=0.3)
    axes[2].legend()
    fig.suptitle("BIN-1D-TSMOM-VT demo: multi-asset TSMOM + 20% vol target (2021-2025, net)")
    fig.tight_layout()
    fig.savefig(ARTIFACT_DIR / "tsmom_vt_demo_equity.png", dpi=150)

    out = ARTIFACT_DIR / "tsmom_vt_demo_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["results"], ensure_ascii=False))
    print("attribution:", json.dumps(report["attribution_return_units"], ensure_ascii=False))
    print("evaluation:", json.dumps(report["pre_registered_evaluation"], ensure_ascii=False))
    print("funding coverage:", funding_coverage, "| report ->", out)


if __name__ == "__main__":
    main()
