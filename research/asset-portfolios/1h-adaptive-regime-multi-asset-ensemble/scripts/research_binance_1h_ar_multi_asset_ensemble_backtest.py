"""Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble first combination backtest.

Combines the latest registered version of six 1h adaptive-regime families
into one equal-weight (1/6 per sleeve) multi-asset portfolio:

- TRX-1H-Adaptive-Regime-V3
- SOL-1H-Adaptive-Regime-V2
- HYPE-1H-Adaptive-Regime-V4
- ETH-1H-Adaptive-Regime-V3
- BTC-1H-Adaptive-Regime-V4
- BNB-1H-Adaptive-Regime-V3

Each sleeve reuses its family frozen trade path (fee 0.001/fill, slippage
4 bps/fill, actual Binance funding). Every sleeve is verified against its
core-ledger current-full metrics before combination. Portfolio equity is
built on an hourly grid with intra-trade mark-to-market from bar closes
(fees/funding trued up at each trade exit via the frozen equity_ret).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DATE_TAG = "2026-07-07"
SUMMARY_JSON = ARTIFACT_DIR / f"binance_1h_ar_mae_first_backtest_{DATE_TAG}.json"
EQUITY_CSV = ARTIFACT_DIR / f"binance_1h_ar_mae_equity_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"binance_1h_ar_mae_trades_{DATE_TAG}.csv"

SCRIPT_DIRS = {
    "trx": ROOT / "research/trx/1h-adaptive-regime/scripts",
    "sol": ROOT / "research/sol/1h-adaptive-regime/scripts",
    "hype": ROOT / "research/hype/1h-adaptive-regime/scripts",
    "eth": ROOT / "research/eth/1h-adaptive-regime/scripts",
    "btc": ROOT / "research/btc/1h-adaptive-regime/scripts",
    "bnb": ROOT / "research/bnb/1h-adaptive-regime/scripts",
}

# Ledger current-full expectations: (annual_multiple, max_dd, win_rate, trades)
LEDGER_EXPECTED = {
    "TRX": (5.686, -0.1717, 0.9247, 93),
    "SOL": (2.07, -0.1741, 0.9391, 115),
    "HYPE": (22.8128, -0.1911, 0.8108, 74),
    "ETH": (3.3084, -0.1570, 0.9565, 46),
    "BTC": (5.27, -0.1747, 0.8649, 74),
    "BNB": (2.94, -0.1824, 0.8833, 120),
}

SLICES = (
    ("last_1d", pd.Timedelta(days=1)),
    ("last_7d", pd.Timedelta(days=7)),
    ("last_1m", pd.DateOffset(months=1)),
    ("last_3m", pd.DateOffset(months=3)),
    ("last_6m", pd.DateOffset(months=6)),
    ("last_1y", pd.DateOffset(years=1)),
)


def load_module(path: Path, name: str) -> Any:
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


# ---------------------------------------------------------------------------
# Sleeve loaders. Each returns a dict with keys:
#   asset, version, engine, frame, trades (merged, frozen path),
#   start (family scoring start), end (family full end), quality
# ---------------------------------------------------------------------------


def load_trx() -> dict[str, Any]:
    scripts = SCRIPT_DIRS["trx"]
    v3c = load_module(scripts / "trx_1h_ar_v3_clean.py", "trx_1h_ar_v3_clean")
    v3 = sys.modules["trx_1h_ar_v3"]
    v1 = sys.modules["trx_1h_ar_v1"]
    engine, frame, funding, quality = v3.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    trades, _macd, _stoch, _prio = v3c.simulate_clean(
        engine, frame, funding_times, funding_cumulative
    )
    return {
        "asset": "TRX",
        "version": "TRX-1H-Adaptive-Regime-V3",
        "engine": engine,
        "frame": frame,
        "trades": trades,
        "start": v1.TRAIN_START,
        "end": v1.FULL_END,
        "quality": quality,
    }


def load_sol() -> dict[str, Any]:
    scripts = SCRIPT_DIRS["sol"]
    v1 = load_module(scripts / "sol_1h_ar_v1.py", "sol_1h_ar_v1")
    hw = load_module(
        scripts / "research_sol_1h_ar_high_win_target_search.py",
        "research_sol_1h_ar_high_win_target_search",
    )
    engine, frame, funding, quality = v1.load_context()
    hw.apply_high_win_overrides(engine)
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    donchian = {
        "name": "SOL_1H_AR_HW_R132002",
        "style": "donchian_break",
        "side_mode": "both",
        "ema_fast": 144,
        "ema_slow": 233,
        "ema_htf": 377,
        "indicator_window": 24,
        "threshold_low": 25.0,
        "threshold_high": 75.0,
        "band_k": 1.5,
        "pullback_atr": 0.25,
        "roc_window": 24,
        "roc_threshold_bps": 50.0,
        "macd_fast": 34,
        "macd_slow": 89,
        "macd_signal": 13,
        "min_adx": 36.0,
        "max_adx": 100.0,
        "min_rvol": 1.0,
        "min_atr_bps": 100.0,
        "max_atr_bps": 10_000.0,
        "min_dir_roc_bps": 100.0,
        "max_dist_ema_bps": 750.0,
        "htf_mode": "none",
        "require_macd_turn": True,
        "require_body_dir": False,
        "max_aligned_funding_bps": 2.0,
        "exit_kind": "fixed",
        "tp_atr": 0.75,
        "sl_atr": 4.0,
        "trail_activation_atr": 0.75,
        "trail_atr": 0.5,
        "max_hold_bars": 120,
        "cooldown_bars": 0,
        "entry_delay_bars": 1,
        "sizing_kind": "fixed",
        "fixed_leverage": 3.0,
        "risk_fraction": 0.01,
        "max_leverage": 2.5,
    }
    vwap = {
        "name": "SOL_1H_AR_HW_R243705",
        "style": "vwap_revert",
        "side_mode": "short",
        "ema_fast": 34,
        "ema_slow": 55,
        "ema_htf": 89,
        "indicator_window": 48,
        "threshold_low": 30.0,
        "threshold_high": 70.0,
        "band_k": 1.25,
        "pullback_atr": 0.25,
        "roc_window": 72,
        "roc_threshold_bps": 50.0,
        "macd_fast": 8,
        "macd_slow": 21,
        "macd_signal": 5,
        "min_adx": 0.0,
        "max_adx": 100.0,
        "min_rvol": 0.0,
        "min_atr_bps": 125.0,
        "max_atr_bps": 10_000.0,
        "min_dir_roc_bps": -10_000.0,
        "max_dist_ema_bps": 1000.0,
        "htf_mode": "h12",
        "require_macd_turn": False,
        "require_body_dir": True,
        "max_aligned_funding_bps": 1.0,
        "exit_kind": "fixed",
        "tp_atr": 0.75,
        "sl_atr": 3.0,
        "trail_activation_atr": 1.0,
        "trail_atr": 1.25,
        "max_hold_bars": 18,
        "cooldown_bars": 3,
        "entry_delay_bars": 1,
        "sizing_kind": "fixed",
        "fixed_leverage": 1.5,
        "risk_fraction": 0.01,
        "max_leverage": 1.5,
    }
    legs = []
    for cfg_dict in (donchian, vwap):
        cfg = engine.StrategyConfig(**cfg_dict)
        trades = engine.simulate_trades(
            frame,
            engine.build_signal(frame, cfg),
            cfg,
            funding_times,
            funding_cumulative,
        )
        train = engine.metrics(trades, v1.TRAIN_START, v1.TRAIN_END)
        validation = engine.metrics(trades, v1.TRAIN_END, v1.PREFIT_END)
        prefit = engine.metrics(trades, v1.TRAIN_START, v1.PREFIT_END)
        legs.append((trades, engine.prefit_score(train, validation, prefit)))
    merged = engine.merge_trade_sets(legs[0][0], legs[1][0], legs[0][1], legs[1][1])
    return {
        "asset": "SOL",
        "version": "SOL-1H-Adaptive-Regime-V2",
        "engine": engine,
        "frame": frame,
        "trades": merged,
        "start": v1.TRAIN_START,
        "end": v1.FULL_END,
        "quality": quality,
    }


def load_hype() -> dict[str, Any]:
    scripts = SCRIPT_DIRS["hype"]
    pt = load_module(
        scripts / "research_hype_1h_ar_v3_prune_and_tune.py",
        "research_hype_1h_ar_v3_prune_and_tune",
    )
    base = sys.modules["research_hype_1h_adaptive_regime_search"]
    boundary = sys.modules["audit_hype_1h_adaptive_regime_boundary"]
    v2 = sys.modules["research_hype_1h_ar_v2_clean_tune"]
    v3ab = sys.modules["research_hype_1h_ar_v3_full_ablation"]

    frame, funding, quality = base.load_data()
    frame = base.add_features(frame, funding)
    frame = v3ab.ensure_extra_macd_features(frame)
    funding_times, funding_cumulative = base.funding_prefix(funding)

    di_v4 = pt.DIPrunedConfig(
        min_adx=10.0,
        min_rvol=2.0,
        max_atr_bps=250.0,
        htf_mode="h12",
        require_body_dir=False,
        tp_atr=1.5,
        sl_atr=4.5,
        max_hold_bars=18,
        fixed_leverage=3.0,
    )
    stoch_v4 = pt.StochPrunedConfig(
        indicator_window=21,
        threshold_low=25.0,
        threshold_high=55.0,
        min_adx=0.0,
        min_rvol=1.0,
        min_atr_bps=200.0,
        max_atr_bps=500.0,
        macd_fast=8,
        macd_slow=55,
        macd_signal=5,
        require_macd_turn=True,
        trail_activation_atr=1.0,
        trail_atr=1.0,
        max_hold_bars=8,
        cooldown_bars=36,
        fixed_leverage=2.0,
    )
    di_cfg = v2.di_to_base(pt.di_pruned_to_clean(di_v4), "HYPE_1H_AR_V4_DI")
    stoch_cfg = v2.stoch_to_base(pt.stoch_pruned_to_clean(stoch_v4), "HYPE_1H_AR_V4_STOCH")
    di_trades = boundary.component_trades(frame, funding_times, funding_cumulative, di_cfg)
    stoch_trades = boundary.component_trades(
        frame, funding_times, funding_cumulative, stoch_cfg
    )
    # HYPE ensemble contract: DI-cross has priority on same-bar conflicts.
    merged = base.merge_trade_sets(di_trades, stoch_trades, 1.0, 0.0)
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    return {
        "asset": "HYPE",
        "version": "HYPE-1H-Adaptive-Regime-V4",
        "engine": base,
        "frame": frame,
        "trades": merged,
        "start": pt.TRAIN_START,
        "end": full_end,
        "quality": quality,
    }


def load_eth() -> dict[str, Any]:
    scripts = SCRIPT_DIRS["eth"]
    v21c = load_module(scripts / "eth_1h_ar_v2_1_clean.py", "eth_1h_ar_v2_1_clean")
    v1 = sys.modules["eth_1h_ar_v1"]
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    # ETH-1H-Adaptive-Regime-V3 frozen clean parameters
    # (specs/eth-1h-ar-v3-clean-tuned-spec-2026-07-07.md)
    bb_v3 = v21c.BBBreakV21CleanConfig(
        indicator_window=72,
        band_k=2.5,
        roc_window=24,
        min_adx=16.0,
        min_rvol=3.5,
        min_atr_bps=75.0,
        min_dir_roc_bps=200.0,
        max_dist_ema_bps=750.0,
        tp_atr=3.0,
        sl_atr=5.0,
        max_hold_bars=72,
        fixed_leverage=1.5,
    )
    rsi_v3 = v21c.RSIV21CleanConfig()  # V3 RSI leg equals V2.1 frozen values
    trades, _bb, _rsi, _prio = v21c.simulate_clean(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        bb_break=bb_v3,
        rsi=rsi_v3,
    )
    return {
        "asset": "ETH",
        "version": "ETH-1H-Adaptive-Regime-V3",
        "engine": engine,
        "frame": frame,
        "trades": trades,
        "start": v1.TRAIN_START,
        "end": v1.FULL_END,
        "quality": quality,
    }


def load_btc() -> dict[str, Any]:
    scripts = SCRIPT_DIRS["btc"]
    v4 = load_module(scripts / "btc_1h_ar_v4.py", "btc_1h_ar_v4")
    v1 = sys.modules["btc_1h_ar_v1"]
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    trades, _keltner, _cci, _prio = v4.simulate_v4(
        engine, frame, funding_times, funding_cumulative
    )
    return {
        "asset": "BTC",
        "version": "BTC-1H-Adaptive-Regime-V4",
        "engine": engine,
        "frame": frame,
        "trades": trades,
        "start": v1.TRAIN_START,
        "end": v1.FULL_END,
        "quality": quality,
    }


def load_bnb() -> dict[str, Any]:
    scripts = SCRIPT_DIRS["bnb"]
    v2 = load_module(scripts / "bnb_1h_ar_v2.py", "bnb_1h_ar_v2")
    ctx = v2.load_context()
    engine = ctx["engine"]
    frame = ctx["frame"]
    tune_json = (
        ROOT
        / "research/bnb/1h-adaptive-regime/artifacts"
        / "bnb_1h_ar_v2_micro_tune_2026-07-07.json"
    )
    preferred = json.loads(tune_json.read_text(encoding="utf-8"))["preferred"]
    configs = tuple(engine.StrategyConfig(**cfg) for cfg in preferred["configs"])
    priorities = tuple(float(x) for x in preferred["priorities"])
    trades = v2.simulate_strategy(
        engine,
        frame,
        ctx["funding_times"],
        ctx["funding_cumulative"],
        configs,
        priorities,
    )
    return {
        "asset": "BNB",
        "version": "BNB-1H-Adaptive-Regime-V3",
        "engine": engine,
        "frame": frame,
        "trades": trades,
        "start": ctx["split"]["train_start"],
        "end": ctx["split"]["full_end"],
        "quality": ctx["quality"],
    }


# ---------------------------------------------------------------------------
# Verification and portfolio construction
# ---------------------------------------------------------------------------


def verify_sleeve(sleeve: dict[str, Any]) -> dict[str, Any]:
    engine = sleeve["engine"]
    metric = engine.metrics(sleeve["trades"], sleeve["start"], sleeve["end"])
    expected = LEDGER_EXPECTED[sleeve["asset"]]
    checks = {
        "annual_multiple": (metric["annual_multiple"], expected[0]),
        "max_dd": (metric["max_dd"], expected[1]),
        "win_rate": (metric["win_rate"], expected[2]),
        "trades": (metric["trades"], expected[3]),
    }
    for key, (actual, target) in checks.items():
        tolerance = 0.006 * max(abs(target), 1.0) if key != "trades" else 0.5
        if abs(float(actual) - float(target)) > tolerance:
            raise RuntimeError(
                f"{sleeve['asset']} sleeve drifted from ledger at {key}: "
                f"{actual} != {target}"
            )
    return metric


def sleeve_equity_series(
    sleeve: dict[str, Any], start: pd.Timestamp, end: pd.Timestamp
) -> pd.Series:
    """Hourly sleeve equity (1.0 start) with intra-trade close-based M2M."""
    frame = sleeve["frame"]
    close = frame["close"].to_numpy(dtype="float64")
    close_time = (frame["ts"] + pd.Timedelta(hours=1)).to_numpy()
    n = len(frame)
    values = np.ones(n, dtype="float64")
    cursor = 0
    equity = 1.0
    trades = [
        trade
        for trade in sleeve["trades"]
        if start <= trade.entry_ts and trade.entry_ts < end
    ]
    trades.sort(key=lambda trade: trade.entry_i)
    for trade in trades:
        entry_i = int(trade.entry_i)
        exit_i = int(trade.exit_i)
        values[cursor:entry_i] = equity
        if exit_i > entry_i:
            marks = close[entry_i:exit_i] / float(trade.entry_price) - 1.0
            values[entry_i:exit_i] = equity * (
                1.0 + float(trade.exposure) * float(trade.side) * marks
            )
        equity *= 1.0 + float(trade.equity_ret)
        values[exit_i] = equity
        cursor = exit_i + 1
    values[cursor:] = equity
    series = pd.Series(values, index=pd.DatetimeIndex(close_time, tz="UTC"))
    timeline = pd.date_range(start, end, freq="1h", tz="UTC")
    series = series.reindex(timeline, method="ffill").fillna(1.0)
    return series


def sleeve_exposure_series(
    sleeve: dict[str, Any], start: pd.Timestamp, end: pd.Timestamp
) -> pd.Series:
    frame = sleeve["frame"]
    close_time = (frame["ts"] + pd.Timedelta(hours=1)).to_numpy()
    values = np.zeros(len(frame), dtype="float64")
    for trade in sleeve["trades"]:
        if start <= trade.entry_ts and trade.entry_ts < end:
            values[int(trade.entry_i) : int(trade.exit_i) + 1] = float(trade.exposure)
    series = pd.Series(values, index=pd.DatetimeIndex(close_time, tz="UTC"))
    timeline = pd.date_range(start, end, freq="1h", tz="UTC")
    return series.reindex(timeline).fillna(0.0)


def curve_metrics(curve: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, float]:
    window = curve.loc[(curve.index >= start) & (curve.index <= end)]
    if len(window) < 2:
        return {
            "days": 0.0,
            "final_equity": 1.0,
            "total_return": 0.0,
            "annual_multiple": 1.0,
            "max_dd": 0.0,
        }
    rebased = window / window.iloc[0]
    days = max((window.index[-1] - window.index[0]).total_seconds() / 86_400.0, 1.0)
    final = float(rebased.iloc[-1])
    max_dd = float((rebased / rebased.cummax() - 1.0).min())
    annual = final ** (365.25 / days) if final > 0 else 0.0
    return {
        "days": float(days),
        "final_equity": final,
        "total_return": final - 1.0,
        "annual_multiple": float(annual),
        "annual_return": float(annual - 1.0),
        "max_dd": max_dd,
    }


def trade_stats(
    sleeves: list[dict[str, Any]], start: pd.Timestamp, end: pd.Timestamp
) -> dict[str, float]:
    returns: list[float] = []
    for sleeve in sleeves:
        for trade in sleeve["trades"]:
            if start <= trade.entry_ts < end:
                returns.append(float(trade.equity_ret))
    if not returns:
        return {"trades": 0.0, "win_rate": 0.0, "profit_factor": 0.0}
    positives = [value for value in returns if value > 0]
    negatives = [abs(value) for value in returns if value < 0]
    return {
        "trades": float(len(returns)),
        "win_rate": float(len(positives) / len(returns)),
        "profit_factor": (
            float(sum(positives) / sum(negatives)) if negatives else float("inf")
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    loaders = (load_trx, load_sol, load_hype, load_eth, load_btc, load_bnb)
    sleeves: list[dict[str, Any]] = []
    verification: dict[str, Any] = {}
    for loader in loaders:
        sleeve = loader()
        metric = verify_sleeve(sleeve)
        verification[sleeve["asset"]] = {
            "version": sleeve["version"],
            "ledger_expected": LEDGER_EXPECTED[sleeve["asset"]],
            "reproduced_current_full": metric,
        }
        # Respect each family's own scoring boundary (e.g. HYPE warmup trades
        # before its TRAIN_START are not part of the frozen version identity).
        sleeve["trades"] = [
            trade
            for trade in sleeve["trades"]
            if sleeve["start"] <= trade.entry_ts < sleeve["end"]
        ]
        sleeves.append(sleeve)
        print(
            f"verified {sleeve['asset']} {sleeve['version']}: "
            f"annual={metric['annual_multiple']:.4f}x dd={metric['max_dd']:.2%} "
            f"win={metric['win_rate']:.2%} trades={int(metric['trades'])}",
            flush=True,
        )

    # Portfolio window: common start across the five majors; HYPE joins later
    # (its sleeve holds cash before its scoring start). End = earliest sleeve end.
    start = max(s["start"] for s in sleeves if s["asset"] != "HYPE")
    hype_start = next(s["start"] for s in sleeves if s["asset"] == "HYPE")
    end = min(s["end"] for s in sleeves)

    curves = {
        sleeve["asset"]: sleeve_equity_series(sleeve, start, end) for sleeve in sleeves
    }
    frame = pd.DataFrame(curves)
    returns = frame.pct_change().fillna(0.0)

    # Primary: hourly-rebalanced equal weight (1/6 per sleeve, cash when idle).
    rebalanced = (1.0 + returns.mean(axis=1)).cumprod()
    rebalanced.iloc[0] = 1.0
    # Secondary: no-rebalance, each sleeve compounds its own 1/6.
    static = frame.mean(axis=1)

    windows: list[tuple[str, pd.Timestamp]] = [
        ("full", start),
        ("all_six_active", hype_start),
        ("reused_holdout", pd.Timestamp("2026-04-03T00:00:00Z")),
    ]
    for name, delta in SLICES:
        windows.append((name, max(start, end - delta)))

    results: dict[str, Any] = {}
    for name, window_start in windows:
        results[name] = {
            "start": window_start,
            "end": end,
            "rebalanced": curve_metrics(rebalanced, window_start, end),
            "static": curve_metrics(static, window_start, end),
            "trade_stats": trade_stats(sleeves, window_start, end),
        }

    per_sleeve: dict[str, Any] = {}
    for sleeve in sleeves:
        asset = sleeve["asset"]
        engine = sleeve["engine"]
        per_sleeve[asset] = {
            "version": sleeve["version"],
            "portfolio_window": engine.metrics(sleeve["trades"], start, end),
            "curve_in_portfolio": curve_metrics(curves[asset], start, end),
        }

    daily_returns = frame.resample("1D").last().pct_change().dropna(how="all")
    correlation = daily_returns.loc[daily_returns.index >= hype_start].corr()

    exposure = pd.DataFrame(
        {s["asset"]: sleeve_exposure_series(s, start, end) for s in sleeves}
    )
    portfolio_gross = exposure.sum(axis=1) / 6.0
    exposure_stats = {
        "portfolio_gross_avg": float(portfolio_gross.mean()),
        "portfolio_gross_max": float(portfolio_gross.max()),
        "hours_any_position_pct": float((portfolio_gross > 0).mean()),
        "hours_ge_3_sleeves_pct": float(((exposure > 0).sum(axis=1) >= 3).mean()),
    }

    trades_rows = []
    for sleeve in sleeves:
        for trade in sleeve["trades"]:
            if start <= trade.entry_ts < end:
                trades_rows.append(
                    {
                        "asset": sleeve["asset"],
                        "version": sleeve["version"],
                        "style": trade.style,
                        "entry_ts": trade.entry_ts,
                        "exit_ts": trade.exit_ts,
                        "side": trade.side,
                        "exposure": trade.exposure,
                        "equity_ret_sleeve": trade.equity_ret,
                        "equity_ret_portfolio_weighted": trade.equity_ret / 6.0,
                        "exit_reason": trade.exit_reason,
                    }
                )
    trades_frame = pd.DataFrame(trades_rows).sort_values("entry_ts")
    trades_frame.to_csv(TRADES_CSV, index=False)

    equity_out = frame.copy()
    equity_out["portfolio_rebalanced"] = rebalanced
    equity_out["portfolio_static"] = static
    equity_out.to_csv(EQUITY_CSV, index_label="ts")

    payload = {
        "family": "Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble",
        "status": "first_combination_diagnostic_not_promoted_not_live_ready",
        "date": DATE_TAG,
        "structure": "six equal-weight sub-account sleeves, 1/6 equity each",
        "portfolio_start": start,
        "hype_sleeve_start": hype_start,
        "portfolio_end": end,
        "costs": {
            "fee_per_fill": 0.001,
            "slippage_per_fill": 0.0004,
            "funding": "actual_binance_history_per_trade_per_sleeve",
        },
        "sleeve_verification": verification,
        "portfolio_windows": results,
        "per_sleeve_in_portfolio_window": per_sleeve,
        "daily_return_correlation_all_six_window": correlation.to_dict(),
        "exposure_stats": exposure_stats,
        "data_quality": {s["asset"]: s["quality"] for s in sleeves},
        "notes": [
            "Slice selection: none. All windows are post-freeze audit only; no "
            "parameter was chosen using these results.",
            "Intra-trade marks use bar closes with the sleeve's frozen entry "
            "price and exposure; fees/slippage/funding are trued up at each "
            "exit via the frozen per-trade equity_ret.",
            "Portfolio end is the earliest sleeve data end (HYPE), so the last "
            "hours of the other five sleeves are cropped.",
        ],
    }
    SUMMARY_JSON.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    brief = {
        name: {
            "rebalanced_annual": results[name]["rebalanced"]["annual_multiple"],
            "rebalanced_return": results[name]["rebalanced"]["total_return"],
            "rebalanced_max_dd": results[name]["rebalanced"]["max_dd"],
            "static_annual": results[name]["static"]["annual_multiple"],
            "static_max_dd": results[name]["static"]["max_dd"],
            "trades": results[name]["trade_stats"]["trades"],
            "win_rate": results[name]["trade_stats"]["win_rate"],
        }
        for name, _ in windows
    }
    print(json.dumps(json_safe(brief), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
