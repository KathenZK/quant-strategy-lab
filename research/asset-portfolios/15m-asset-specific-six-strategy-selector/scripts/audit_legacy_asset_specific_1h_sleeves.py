from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

from as6s_engine import PREFIT_END, REUSED_END, SYMBOLS, load_funding, load_symbol_frame


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
LEGACY_DIR = ROOT / "research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble"
OUTPUT = FAMILY_DIR / "artifacts/binance_legacy_asset_specific_1h_sleeves_2026-07-14.json"
TRADES_OUTPUT = FAMILY_DIR / "artifacts/binance_legacy_asset_specific_1h_sleeves_trades_2026-07-14.csv"
WARMUP = pd.Timedelta(days=45)


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def aggregate_h1(symbol: str) -> pd.DataFrame:
    frame = load_symbol_frame(symbol, end=REUSED_END)
    indexed = frame.set_index("ts")
    h1 = indexed.resample("1h", label="left", closed="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        quote_volume=("quote_volume", "sum"),
        trade_count=("trade_count", "sum"),
        source_bars=("close", "count"),
    )
    h1 = h1.loc[h1["source_bars"] == 4].drop(columns="source_bars").reset_index()
    h1["vwap"] = h1["quote_volume"] / h1["volume"].replace(0.0, np.nan)
    h1["is_closed"] = True
    h1["source"] = "derived_from_audited_binance_15m_lake"
    expected = pd.date_range(h1["ts"].iloc[0], h1["ts"].iloc[-1], freq="1h")
    missing = expected.difference(pd.DatetimeIndex(h1["ts"]))
    if len(missing) or h1.duplicated("ts").any() or h1.isna().any().any():
        raise RuntimeError(f"{symbol} derived 1h quality blocker")
    return h1


def cap_trade(trade: Any, cap: float = 3.0) -> Any:
    exposure = min(cap, float(trade.exposure))
    return replace(
        trade,
        exposure=exposure,
        equity_ret=exposure * float(trade.net_ret_1x),
        equity_mae=exposure * float(trade.mae_1x),
    )


def simulate_stateless(
    engine: Any,
    frame: pd.DataFrame,
    cfg: Any,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
) -> list[Any]:
    signal = engine.build_signal(frame, cfg)
    ts_ns = frame["ts"].astype("datetime64[ns, UTC]").astype("int64").to_numpy()
    open_ = frame["open"].to_numpy(dtype=np.float64)
    high = frame["high"].to_numpy(dtype=np.float64)
    low = frame["low"].to_numpy(dtype=np.float64)
    atr = frame["atr14"].to_numpy(dtype=np.float64)
    trades: list[Any] = []
    for signal_i in np.flatnonzero(signal):
        side = int(signal[signal_i])
        entry_i = int(signal_i + cfg.entry_delay_bars)
        if side == 0 or entry_i >= len(frame):
            continue
        signal_atr = float(atr[signal_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0.0:
            continue
        raw_entry = float(open_[entry_i])
        entry_price = raw_entry * (1.0 + side * engine.SLIPPAGE_PER_FILL)
        initial_stop = entry_price - side * cfg.sl_atr * signal_atr
        target = (
            entry_price + side * cfg.tp_atr * signal_atr
            if cfg.exit_kind == "fixed"
            else None
        )
        stop_price = initial_stop
        best_price = entry_price
        timeout_i = min(len(frame) - 1, entry_i + cfg.max_hold_bars)
        exit_i = timeout_i
        raw_exit = float(open_[timeout_i])
        reason = "timeout_open"
        for bar_i in range(entry_i, timeout_i + 1):
            bar_open = float(open_[bar_i])
            if bar_i == timeout_i:
                exit_i, raw_exit, reason = bar_i, bar_open, "timeout_open"
                break
            if engine.crossed_stop(bar_open, stop_price, side):
                exit_i, raw_exit, reason = bar_i, bar_open, "stop_gap_open"
                break
            if target is not None and engine.crossed_target(bar_open, target, side):
                exit_i, raw_exit, reason = bar_i, float(target), "target_gap_or_open"
                break
            stop_hit = engine.touched_stop(float(high[bar_i]), float(low[bar_i]), stop_price, side)
            target_hit = target is not None and engine.touched_target(
                float(high[bar_i]), float(low[bar_i]), float(target), side
            )
            if stop_hit and target_hit:
                exit_i, raw_exit, reason = bar_i, stop_price, "both_hit_stop_first"
                break
            if stop_hit:
                exit_i, raw_exit, reason = bar_i, stop_price, "stop_market"
                break
            if target_hit:
                exit_i, raw_exit, reason = bar_i, float(target), "take_profit"
                break
            if cfg.exit_kind == "trailing":
                if side > 0:
                    best_price = max(best_price, float(high[bar_i]))
                    if best_price - entry_price >= cfg.trail_activation_atr * signal_atr:
                        stop_price = max(stop_price, best_price - cfg.trail_atr * signal_atr)
                else:
                    best_price = min(best_price, float(low[bar_i]))
                    if entry_price - best_price >= cfg.trail_activation_atr * signal_atr:
                        stop_price = min(stop_price, best_price + cfg.trail_atr * signal_atr)
        exit_price = raw_exit * (1.0 - side * engine.SLIPPAGE_PER_FILL)
        price_ret = side * (exit_price / entry_price - 1.0)
        fee_ret = engine.FEE_PER_FILL * (1.0 + exit_price / entry_price)
        funding_ret = engine.trade_funding(
            int(ts_ns[entry_i]), int(ts_ns[exit_i]), side,
            funding_times, funding_cumulative,
        )
        net_ret_1x = price_ret - fee_ret + funding_ret
        if side > 0:
            mae = float(np.nanmin(low[entry_i : exit_i + 1] / entry_price - 1.0))
            mfe = float(np.nanmax(high[entry_i : exit_i + 1] / entry_price - 1.0))
        else:
            mae = float(np.nanmin(1.0 - high[entry_i : exit_i + 1] / entry_price))
            mfe = float(np.nanmax(1.0 - low[entry_i : exit_i + 1] / entry_price))
        mae -= 2.0 * engine.FEE_PER_FILL
        stop_distance_pct = cfg.sl_atr * signal_atr / entry_price
        exposure = engine.exposure_for_trade(cfg, stop_distance_pct)
        trades.append(
            engine.Trade(
                config=cfg.name, style=cfg.style, signal_i=int(signal_i),
                entry_i=entry_i, exit_i=exit_i,
                signal_ts=pd.Timestamp(ts_ns[signal_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                side=side, entry_price=entry_price, exit_price=exit_price,
                exit_reason=reason, bars_held=int(exit_i - entry_i),
                exposure=float(exposure), net_ret_1x=float(net_ret_1x),
                equity_ret=float(exposure * net_ret_1x), mae_1x=float(mae),
                equity_mae=float(exposure * mae), mfe_1x=float(mfe),
                funding_ret_1x=float(funding_ret),
                signal_atr_bps=float(signal_atr / frame["close"].iloc[signal_i] * 10_000.0),
            )
        )
    return trades


def select_component_path(trades: list[Any], cooldown_bars: int) -> list[Any]:
    selected: list[Any] = []
    blocked_until = -1
    for trade in sorted(trades, key=lambda value: (value.entry_i, value.exit_i)):
        if trade.entry_i <= blocked_until:
            continue
        selected.append(trade)
        blocked_until = trade.exit_i + cooldown_bars
    return selected


def strict_metrics(trades: list[Any], start: pd.Timestamp, end: pd.Timestamp) -> dict[str, float]:
    chosen = sorted(
        (trade for trade in trades if start <= trade.entry_ts and trade.exit_ts < end),
        key=lambda trade: trade.exit_ts,
    )
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    returns: list[float] = []
    for trade in chosen:
        trough = equity * max(0.001, 1.0 + float(trade.equity_mae))
        max_dd = min(max_dd, trough / peak - 1.0)
        value = float(trade.equity_ret)
        equity *= max(0.001, 1.0 + value)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
        returns.append(value)
    positives = [value for value in returns if value > 0.0]
    negatives = [value for value in returns if value < 0.0]
    years = max((end - start).total_seconds() / (365.25 * 86400.0), 1 / 365.25)
    return {
        "trades": float(len(chosen)),
        "wins": float(len(positives)),
        "win_rate": len(positives) / len(chosen) if chosen else 0.0,
        "total_return": equity - 1.0,
        "annual_multiple": equity ** (1.0 / years) if equity > 0.0 else 0.0,
        "max_dd": max_dd,
        "profit_factor": sum(positives) / abs(sum(negatives)) if negatives else math.inf,
        "long_trades": float(sum(trade.side > 0 for trade in chosen)),
        "short_trades": float(sum(trade.side < 0 for trade in chosen)),
    }


def sol_configs(engine: Any, delay: int) -> tuple[Any, Any]:
    common = {
        "threshold_low": 25.0, "threshold_high": 75.0, "pullback_atr": 0.25,
        "roc_threshold_bps": 50.0, "require_macd_turn": False,
        "max_atr_bps": 10_000.0, "risk_fraction": 0.01,
    }
    donchian = engine.StrategyConfig(
        name="SOL_1H_AR_HW_R132002", style="donchian_break", side_mode="both",
        ema_fast=144, ema_slow=233, ema_htf=377, indicator_window=24,
        band_k=1.5, roc_window=24, macd_fast=34, macd_slow=89, macd_signal=13,
        min_adx=36.0, max_adx=100.0, min_rvol=1.0, min_atr_bps=100.0,
        min_dir_roc_bps=100.0, max_dist_ema_bps=750.0, htf_mode="none",
        require_body_dir=False, max_aligned_funding_bps=2.0, exit_kind="fixed",
        tp_atr=0.75, sl_atr=4.0, trail_activation_atr=0.75, trail_atr=0.5,
        max_hold_bars=120, cooldown_bars=0, entry_delay_bars=delay,
        sizing_kind="fixed", fixed_leverage=3.0, max_leverage=2.5, **common,
    )
    vwap = engine.StrategyConfig(
        name="SOL_1H_AR_HW_R243705", style="vwap_revert", side_mode="short",
        ema_fast=34, ema_slow=55, ema_htf=89, indicator_window=48,
        threshold_low=30.0, threshold_high=70.0, band_k=1.25, pullback_atr=0.25,
        roc_window=72, roc_threshold_bps=50.0, macd_fast=8, macd_slow=21,
        macd_signal=5, min_adx=0.0, max_adx=100.0, min_rvol=0.0,
        min_atr_bps=125.0, max_atr_bps=10_000.0, min_dir_roc_bps=-10_000.0,
        max_dist_ema_bps=1000.0, htf_mode="h12", require_macd_turn=False,
        require_body_dir=True, max_aligned_funding_bps=1.0, exit_kind="fixed",
        tp_atr=0.75, sl_atr=3.0, trail_activation_atr=1.0, trail_atr=1.25,
        max_hold_bars=18, cooldown_bars=3, entry_delay_bars=delay,
        sizing_kind="fixed", fixed_leverage=1.5, risk_fraction=0.01,
        max_leverage=1.5,
    )
    return donchian, vwap


def prepare_legacy() -> tuple[Any, dict[str, dict[str, Any]]]:
    first = load_module(
        LEGACY_DIR / "scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py",
        "as6s_legacy_first",
    )
    contexts: dict[str, dict[str, Any]] = {}
    for asset, loader in (
        ("TRX", first.load_trx), ("SOL", first.load_sol), ("HYPE", first.load_hype),
        ("ETH", first.load_eth), ("BTC", first.load_btc), ("BNB", first.load_bnb),
    ):
        contexts[asset] = loader()
    first.load_module(
        ROOT / "research/eth/1h-adaptive-regime/scripts/eth_1h_ar_v4.py",
        "eth_1h_ar_v4",
    )
    return first, contexts


def simulate_components(
    first: Any,
    contexts: dict[str, dict[str, Any]],
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
    *,
    slippage: float,
    delay: int,
) -> tuple[dict[str, list[Any]], dict[str, int]]:
    output: dict[str, list[Any]] = {}
    cooldowns: dict[str, int] = {}
    featured: dict[str, pd.DataFrame] = {}
    prefixes: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for symbol in SYMBOLS:
        asset = symbol.removesuffix("USDT")
        engine = contexts[asset]["engine"]
        engine.SLIPPAGE_PER_FILL = slippage
        featured[asset] = engine.add_features(frames[symbol], funding[symbol])
        prefixes[asset] = engine.funding_prefix(funding[symbol])
    featured["HYPE"] = sys.modules[
        "research_hype_1h_ar_v3_full_ablation"
    ].ensure_extra_macd_features(featured["HYPE"])

    engine = contexts["TRX"]["engine"]
    trx_clean = sys.modules["trx_1h_ar_v3_clean"]
    macd = replace(trx_clean.MACDV3CleanConfig(), entry_delay_bars=delay)
    stoch = replace(trx_clean.StochV3CleanConfig(), entry_delay_bars=max(delay, 2))
    trx_v3 = sys.modules["trx_1h_ar_v3"]
    trx_v2 = trx_v3.v2
    macd_cfg = trx_v2.macd_to_base(engine, trx_v3.macd_to_v2(trx_clean.macd_to_v3(macd)))
    stoch_cfg = trx_v2.stoch_to_base(engine, trx_v3.stoch_to_v2(trx_clean.stoch_to_v3(stoch)))
    macd_trades = simulate_stateless(engine, featured["TRX"], macd_cfg, *prefixes["TRX"])
    stoch_trades = simulate_stateless(engine, featured["TRX"], stoch_cfg, *prefixes["TRX"])
    output["TRX:macd_flip"] = [cap_trade(t) for t in macd_trades]
    output["TRX:stoch_reversal"] = [cap_trade(t) for t in stoch_trades]
    cooldowns["TRX:macd_flip"] = macd_cfg.cooldown_bars
    cooldowns["TRX:stoch_reversal"] = stoch_cfg.cooldown_bars

    engine = contexts["SOL"]["engine"]
    for cfg in sol_configs(engine, delay):
        trades = simulate_stateless(engine, featured["SOL"], cfg, *prefixes["SOL"])
        output[f"SOL:{cfg.style}"] = [cap_trade(t) for t in trades]
        cooldowns[f"SOL:{cfg.style}"] = cfg.cooldown_bars

    engine = contexts["HYPE"]["engine"]
    pt = sys.modules["research_hype_1h_ar_v3_prune_and_tune"]
    v2 = sys.modules["research_hype_1h_ar_v2_clean_tune"]
    di_clean = pt.DIPrunedConfig(
        min_adx=10.0, min_rvol=2.0, max_atr_bps=250.0, htf_mode="h12",
        require_body_dir=False, tp_atr=1.5, sl_atr=4.5, max_hold_bars=18,
        fixed_leverage=3.0,
    )
    stoch_clean = pt.StochPrunedConfig(
        indicator_window=21, threshold_low=25.0, threshold_high=55.0,
        min_adx=0.0, min_rvol=1.0, min_atr_bps=200.0, max_atr_bps=500.0,
        macd_fast=8, macd_slow=55, macd_signal=5, require_macd_turn=True,
        trail_activation_atr=1.0, trail_atr=1.0, max_hold_bars=8,
        cooldown_bars=36, fixed_leverage=2.0,
    )
    di_cfg = replace(
        v2.di_to_base(pt.di_pruned_to_clean(di_clean), "HYPE_1H_AR_V4_DI"),
        entry_delay_bars=delay,
    )
    stoch_cfg = replace(
        v2.stoch_to_base(pt.stoch_pruned_to_clean(stoch_clean), "HYPE_1H_AR_V4_STOCH"),
        entry_delay_bars=delay,
    )
    output["HYPE:di_cross"] = [cap_trade(t) for t in simulate_stateless(
        engine, featured["HYPE"], di_cfg, *prefixes["HYPE"]
    )]
    output["HYPE:stoch_reversal"] = [cap_trade(t) for t in simulate_stateless(
        engine, featured["HYPE"], stoch_cfg, *prefixes["HYPE"]
    )]
    cooldowns["HYPE:di_cross"] = di_cfg.cooldown_bars
    cooldowns["HYPE:stoch_reversal"] = stoch_cfg.cooldown_bars

    engine = contexts["ETH"]["engine"]
    eth_v4 = sys.modules["eth_1h_ar_v4"]
    clean21 = sys.modules["eth_1h_ar_v2_1_clean"]
    bb_cfg = clean21.v1_clean.bb_break_to_base(
        engine, clean21.bb_to_v1_clean(eth_v4.V4_BB_BREAK)
    )
    rsi_cfg = clean21.v1_clean.rsi_to_base(
        engine, clean21.rsi_to_v1_clean(eth_v4.V4_RSI)
    )
    bb_cfg = replace(bb_cfg, entry_delay_bars=delay)
    rsi_cfg = replace(rsi_cfg, entry_delay_bars=delay)
    bb_trades = simulate_stateless(engine, featured["ETH"], bb_cfg, *prefixes["ETH"])
    rsi_trades = simulate_stateless(engine, featured["ETH"], rsi_cfg, *prefixes["ETH"])
    output["ETH:bb_break"] = [cap_trade(t) for t in bb_trades]
    output["ETH:rsi_reversal"] = [cap_trade(t) for t in rsi_trades]
    cooldowns["ETH:bb_break"] = bb_cfg.cooldown_bars
    cooldowns["ETH:rsi_reversal"] = rsi_cfg.cooldown_bars

    engine = contexts["BTC"]["engine"]
    btc_v4 = sys.modules["btc_1h_ar_v4"]
    keltner, cci = btc_v4.v4_configs(engine)
    keltner = replace(keltner, entry_delay_bars=delay)
    cci = replace(cci, entry_delay_bars=delay)
    keltner_trades = simulate_stateless(engine, featured["BTC"], keltner, *prefixes["BTC"])
    cci_trades = simulate_stateless(engine, featured["BTC"], cci, *prefixes["BTC"])
    output["BTC:keltner_break"] = [cap_trade(t) for t in keltner_trades]
    output["BTC:cci_reversal"] = [cap_trade(t) for t in cci_trades]
    cooldowns["BTC:keltner_break"] = keltner.cooldown_bars
    cooldowns["BTC:cci_reversal"] = cci.cooldown_bars

    engine = contexts["BNB"]["engine"]
    tune_json = ROOT / "research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v2_micro_tune_2026-07-07.json"
    preferred = json.loads(tune_json.read_text(encoding="utf-8"))["preferred"]
    for raw in preferred["configs"]:
        cfg = replace(engine.StrategyConfig(**raw), entry_delay_bars=delay)
        trades = simulate_stateless(engine, featured["BNB"], cfg, *prefixes["BNB"])
        output[f"BNB:{cfg.style}"] = [cap_trade(t) for t in trades]
        cooldowns[f"BNB:{cfg.style}"] = cfg.cooldown_bars
    return output, cooldowns


def main() -> None:
    first, contexts = prepare_legacy()
    raw_frames = {symbol: aggregate_h1(symbol) for symbol in SYMBOLS}
    funding = {symbol: load_funding(symbol, end=REUSED_END) for symbol in SYMBOLS}
    starts = {
        symbol.removesuffix("USDT"): raw_frames[symbol]["ts"].iloc[0] + WARMUP
        for symbol in SYMBOLS
    }
    scenario_runs = {
        name: simulate_components(
            first, contexts, raw_frames, funding, slippage=slippage, delay=delay
        )
        for name, slippage, delay in (
            ("base", 0.0004, 1), ("stress_8bps", 0.0008, 1), ("k_plus_2", 0.0004, 2)
        )
    }
    scenarios = {name: result[0] for name, result in scenario_runs.items()}
    cooldowns = scenario_runs["base"][1]
    if any(result[1] != cooldowns for result in scenario_runs.values()):
        raise RuntimeError("scenario cooldown metadata drift")
    results: dict[str, Any] = {}
    for key, trades in scenarios["base"].items():
        asset = key.split(":", 1)[0]
        results[key] = {}
        for scenario, scenario_rows in scenarios.items():
            rows = select_component_path(scenario_rows[key], cooldowns[key])
            results[key][scenario] = {
                "prefit": strict_metrics(rows, starts[asset], PREFIT_END),
                "reused": strict_metrics(rows, PREFIT_END, REUSED_END),
                "through_reused": strict_metrics(rows, starts[asset], REUSED_END),
            }

    trade_rows: list[dict[str, Any]] = []
    for scenario, scenario_components in scenarios.items():
        for key, trades in scenario_components.items():
            asset, style = key.split(":", 1)
            for trade in trades:
                trade_rows.append(
                    {
                        "scenario": scenario, "asset": asset, "style": style,
                        "entry_ts": trade.entry_ts, "exit_ts": trade.exit_ts,
                        "side": trade.side, "exposure": trade.exposure,
                        "net_ret_1x": trade.net_ret_1x,
                        "mae_1x": trade.mae_1x, "equity_ret": trade.equity_ret,
                        "equity_mae": trade.equity_mae,
                        "entry_price": trade.entry_price,
                        "cooldown_bars": cooldowns[key],
                        "exit_reason": trade.exit_reason,
                    }
                )
    pd.DataFrame(trade_rows).sort_values("entry_ts").to_csv(TRADES_OUTPUT, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-15M-Asset-Specific-Six-Strategy-Selector",
        "stage": "legacy_asset_specific_1h_mechanism_revalidation_on_current_lake",
        "source_family": "Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble",
        "role": "mechanism prior revalidation; reused window is diagnostic, not final OOS",
        "exposure_cap": 3.0,
        "windows": {
            "prefit_end": PREFIT_END.isoformat(),
            "reused_end": REUSED_END.isoformat(),
            "asset_starts": {key: value.isoformat() for key, value in starts.items()},
        },
        "data": {
            symbol: {
                "rows_1h": len(frame), "first_ts": frame["ts"].iloc[0],
                "last_ts": frame["ts"].iloc[-1], "source": frame["source"].iloc[0],
            }
            for symbol, frame in raw_frames.items()
        },
        "results": results,
        "component_cooldown_bars": cooldowns,
        "trades_csv": str(TRADES_OUTPUT.relative_to(ROOT)),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps({"output": str(OUTPUT), "components": len(results)}, indent=2))


if __name__ == "__main__":
    main()
