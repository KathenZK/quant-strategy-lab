from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import audit_binance_as6s_clean_rsi_hf_robustness as clean
from as6s_engine import (
    FEE_PER_FILL,
    REUSED_END,
    STARTS,
    StrategyConfig,
    adverse_fill,
    build_signal,
    funding_arrays,
    funding_return,
    load_funding,
    load_symbol_frame,
)
from combine_hybrid_asset_specific_account import UnifiedTrade
import combine_binance_as6s_v6_microtuned_account as account
import research_binance_as6s_v5_legacy_exact_full_ablation as legacy_full


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
)
SOURCE = FAMILY_DIR / "artifacts/binance_as6s_v6_microtuned_account_2026-07-15.json"
MARK_ROOT = (
    ROOT
    / "data/normalized/mark_price_klines/exchange=binance/market_type=perp/timeframe=15m"
)
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_mark_price_account_2026-07-15.json"
TRADES_OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v6_mark_price_account_trades_2026-07-15.csv"
REPORT = FAMILY_DIR / "diagnostics/binance-as6s-v6-mark-price-account-2026-07-15.md"
SLUGS = {
    "BTCUSDT": "btc_usdt_usdt",
    "ETHUSDT": "eth_usdt_usdt",
    "SOLUSDT": "sol_usdt_usdt",
    "BNBUSDT": "bnb_usdt_usdt",
    "TRXUSDT": "trx_usdt_usdt",
    "HYPEUSDT": "hype_usdt_usdt",
}


def load_mark(symbol: str) -> pd.DataFrame:
    paths = sorted(MARK_ROOT.glob(f"date=*/symbol={SLUGS[symbol]}.parquet"))
    if not paths:
        raise RuntimeError(f"missing mark-price partitions for {symbol}")
    frame = pd.concat(
        [
            pd.read_parquet(
                path, columns=["ts", "open", "high", "low", "close"]
            )
            for path in paths
        ],
        ignore_index=True,
    )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = (
        frame.loc[frame["ts"] < REUSED_END]
        .drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    if frame["ts"].max() >= REUSED_END:
        raise RuntimeError(f"{symbol} mark-price crossed cutoff")
    return frame


def aligned_mark(frame: pd.DataFrame, mark: pd.DataFrame, symbol: str) -> pd.DataFrame:
    aligned = frame[["ts"]].merge(mark, on="ts", how="left")
    if aligned[["open", "high", "low", "close"]].isna().any().any():
        missing = aligned.loc[aligned["open"].isna(), "ts"].head().tolist()
        raise RuntimeError(f"{symbol} mark alignment missing: {missing}")
    return aligned


def mapped_intrabar_fill(
    trigger_price: float,
    *,
    trade_open: float,
    trade_low: float,
    trade_high: float,
    mark_open: float,
) -> float:
    ratio = trade_open / mark_open if mark_open > 0.0 else 1.0
    return float(np.clip(trigger_price * ratio, trade_low, trade_high))


def mark_hit(
    side: int,
    *,
    mark_open: float,
    mark_high: float,
    mark_low: float,
    stop: float,
    target: float | None,
    trail: float | None,
) -> tuple[str | None, float | None, bool]:
    if side > 0:
        if mark_open <= stop:
            return "mark_gap_stop", stop, True
        if trail is not None and mark_open <= trail:
            return "mark_gap_trail", trail, True
        if target is not None and mark_open >= target:
            return "mark_gap_target", target, True
        stop_hit = mark_low <= stop
        trail_hit = trail is not None and mark_low <= trail
        target_hit = target is not None and mark_high >= target
    else:
        if mark_open >= stop:
            return "mark_gap_stop", stop, True
        if trail is not None and mark_open >= trail:
            return "mark_gap_trail", trail, True
        if target is not None and mark_open <= target:
            return "mark_gap_target", target, True
        stop_hit = mark_high >= stop
        trail_hit = trail is not None and mark_high >= trail
        target_hit = target is not None and mark_low <= target
    if stop_hit:
        return "mark_stop", stop, False
    if trail_hit:
        return "mark_trail", trail, False
    if target_hit:
        return "mark_target", target, False
    return None, None, False


def frontier_universe(
    sleeve: str,
    audit: dict[str, Any],
    config_dict: dict[str, Any],
    frame: pd.DataFrame,
    mark: pd.DataFrame,
    funding: pd.DataFrame,
) -> dict[str, list[UnifiedTrade]]:
    config = StrategyConfig.from_dict(config_dict)
    mark_frame = aligned_mark(frame, mark, config.symbol)
    sides, scores = build_signal(frame, config)
    times, prefix = funding_arrays(funding)
    trade_open = frame["open"].to_numpy(dtype=float)
    trade_high = frame["high"].to_numpy(dtype=float)
    trade_low = frame["low"].to_numpy(dtype=float)
    trade_close = frame["close"].to_numpy(dtype=float)
    mark_open = mark_frame["open"].to_numpy(dtype=float)
    mark_high = mark_frame["high"].to_numpy(dtype=float)
    mark_low = mark_frame["low"].to_numpy(dtype=float)
    atr = frame["atr14"].to_numpy(dtype=float)
    slow = (
        frame[f"ema_{config.ema_slow}"].to_numpy(dtype=float)
        if config.ema_slow
        else np.full(len(frame), np.nan)
    )
    timestamps = frame["ts"].tolist()
    quality = float(audit["quality"])
    exposure = float(audit["exposure"])
    output: dict[str, list[UnifiedTrade]] = {}
    for scenario, (slippage, delay) in account.SCENARIOS.items():
        rows: list[UnifiedTrade] = []
        for signal_i in np.flatnonzero(sides):
            entry_i = int(signal_i + delay)
            if (
                entry_i >= len(frame)
                or timestamps[entry_i] >= REUSED_END
                or not np.isfinite(atr[signal_i])
            ):
                continue
            side = int(sides[signal_i])
            entry_fill = adverse_fill(
                trade_open[entry_i], side, entry=True, slippage=slippage
            )
            stop = entry_fill - side * config.sl_atr * atr[signal_i]
            target = (
                entry_fill + side * config.tp_atr * atr[signal_i]
                if config.tp_atr > 0.0
                else None
            )
            timeout_i = min(entry_i + config.max_hold_bars, len(frame) - 1)
            exit_i = timeout_i
            raw_exit = trade_open[timeout_i]
            reason = "time_open"
            high_water = entry_fill
            low_water = entry_fill
            trail: float | None = None
            for index in range(entry_i, timeout_i):
                hit_reason, trigger, gap = mark_hit(
                    side,
                    mark_open=mark_open[index],
                    mark_high=mark_high[index],
                    mark_low=mark_low[index],
                    stop=stop,
                    target=target,
                    trail=trail,
                )
                if hit_reason is not None and trigger is not None:
                    exit_i = index
                    raw_exit = (
                        trade_open[index]
                        if gap
                        else mapped_intrabar_fill(
                            trigger,
                            trade_open=trade_open[index],
                            trade_low=trade_low[index],
                            trade_high=trade_high[index],
                            mark_open=mark_open[index],
                        )
                    )
                    reason = hit_reason
                    break
                if config.mechanism == "trend_state" and index > entry_i:
                    if (
                        side > 0 and trade_close[index - 1] < slow[index - 1]
                    ) or (
                        side < 0 and trade_close[index - 1] > slow[index - 1]
                    ):
                        exit_i, raw_exit, reason = (
                            index,
                            trade_open[index],
                            "trend_break_open",
                        )
                        break
                high_water = max(high_water, trade_high[index])
                low_water = min(low_water, trade_low[index])
                if (
                    config.mechanism == "trend_state"
                    and config.trail_activate_atr > 0.0
                ):
                    mfe = (
                        side
                        * (
                            (high_water if side > 0 else low_water) - entry_fill
                        )
                        / atr[signal_i]
                    )
                    if mfe >= config.trail_activate_atr:
                        candidate = (
                            high_water - config.trail_atr * atr[signal_i]
                            if side > 0
                            else low_water + config.trail_atr * atr[signal_i]
                        )
                        trail = (
                            candidate
                            if trail is None
                            else max(trail, candidate)
                            if side > 0
                            else min(trail, candidate)
                        )
            if timestamps[exit_i] >= REUSED_END:
                continue
            exit_fill = adverse_fill(
                raw_exit, side, entry=False, slippage=slippage
            )
            price_ret = side * (exit_fill / entry_fill - 1.0)
            funding_ret = funding_return(
                side, timestamps[entry_i], timestamps[exit_i], times, prefix
            )
            fee_ret = -2.0 * FEE_PER_FILL
            if side > 0:
                mae = float(
                    np.nanmin(
                        trade_low[entry_i : exit_i + 1] / entry_fill - 1.0
                    )
                )
            else:
                mae = float(
                    np.nanmin(
                        1.0 - trade_high[entry_i : exit_i + 1] / entry_fill
                    )
                )
            net = float(price_ret + funding_ret + fee_ret)
            rows.append(
                UnifiedTrade(
                    sleeve=sleeve,
                    symbol=config.symbol,
                    mechanism=config.mechanism,
                    source_timeframe="15m",
                    side=side,
                    entry_ts=timestamps[entry_i],
                    exit_ts=timestamps[exit_i],
                    entry_price=entry_fill,
                    net_return_1x=net,
                    mae_return_1x=min(mae + fee_ret, net),
                    raw_strength=float(scores[signal_i]),
                    strength=float(
                        0.75 * quality
                        + 0.25 * np.clip(scores[signal_i], 0.0, 1.0)
                    ),
                    exposure=exposure,
                    exit_reason=reason,
                )
            )
        output[scenario] = rows
    return output


def prepare_clean_mark_context(
    frame: pd.DataFrame,
    mark: pd.DataFrame,
    funding: pd.DataFrame,
    symbol: str,
) -> dict[str, Any]:
    raw = frame[["ts", "open", "high", "low", "close", "volume"]]
    features = clean.evolution.add_rsi_features(clean.evolution.add_features(raw, []))
    mark_frame = aligned_mark(frame, mark, symbol)
    times, prefix = funding_arrays(funding)
    return {
        "features": features,
        "market": clean.mii.build_market_arrays(features),
        "mark_open": mark_frame["open"].to_numpy(dtype=float),
        "mark_high": mark_frame["high"].to_numpy(dtype=float),
        "mark_low": mark_frame["low"].to_numpy(dtype=float),
        "funding_times": times,
        "funding_prefix": prefix,
    }


def clean_universe(
    sleeve: str,
    audit: dict[str, Any],
    config_dict: dict[str, Any],
    frame: pd.DataFrame,
    mark: pd.DataFrame,
    funding: pd.DataFrame,
    *,
    prepared_context: dict[str, Any] | None = None,
) -> dict[str, list[UnifiedTrade]]:
    config = clean.Config(**config_dict)
    context = prepared_context or prepare_clean_mark_context(
        frame, mark, funding, audit["symbol"]
    )
    features = context["features"]
    market = context["market"]
    state = clean.mii.signal_state(features, config.signal)
    filter_spec = replace(config.filter, max_atr_pct96=99.0)
    mark_open = context["mark_open"]
    mark_high = context["mark_high"]
    mark_low = context["mark_low"]
    times = context["funding_times"]
    prefix = context["funding_prefix"]
    quality = float(audit["quality"])
    exposure = float(audit["exposure"])
    output: dict[str, list[UnifiedTrade]] = {}
    for scenario, (slippage, delay) in account.SCENARIOS.items():
        rows: list[UnifiedTrade] = []
        for signal_i, direction_value in zip(
            state.signal_i, state.directions, strict=False
        ):
            entry_i = int(signal_i + delay)
            if entry_i >= len(frame) - 1:
                continue
            forced_i = min(entry_i + config.exit.max_hold_bars, len(frame) - 1)
            if forced_i <= entry_i:
                continue
            side = int(direction_value)
            entry_fill = adverse_fill(
                float(market.open[entry_i]), side, entry=True, slippage=slippage
            )
            stop = entry_fill * (1.0 - side * config.exit.stop_pct)
            target = entry_fill * (1.0 + side * config.exit.take_profit_pct)
            exit_i = forced_i
            raw_exit = float(market.open[forced_i])
            reason = "max_hold"
            min_path = 0.0
            max_path = 0.0
            for index in range(entry_i, forced_i):
                high = float(market.high[index])
                low = float(market.low[index])
                if side > 0:
                    min_path = min(min_path, low / entry_fill - 1.0)
                    max_path = max(max_path, high / entry_fill - 1.0)
                else:
                    min_path = min(min_path, 1.0 - high / entry_fill)
                    max_path = max(max_path, 1.0 - low / entry_fill)
                hit_reason, trigger, gap = mark_hit(
                    side,
                    mark_open=mark_open[index],
                    mark_high=mark_high[index],
                    mark_low=mark_low[index],
                    stop=stop,
                    target=target,
                    trail=None,
                )
                if hit_reason is None or trigger is None:
                    continue
                exit_i = index
                raw_exit = (
                    float(market.open[index])
                    if gap
                    else mapped_intrabar_fill(
                        trigger,
                        trade_open=float(market.open[index]),
                        trade_low=float(market.low[index]),
                        trade_high=float(market.high[index]),
                        mark_open=mark_open[index],
                    )
                )
                reason = hit_reason
                break
            exit_fill = adverse_fill(
                raw_exit, side, entry=False, slippage=slippage
            )
            entry_ts = pd.Timestamp(market.ts[entry_i])
            exit_ts = pd.Timestamp(market.ts[exit_i])
            price_ret = side * (exit_fill / entry_fill - 1.0)
            funding_ret = funding_return(
                side, entry_ts, exit_ts, times, prefix
            )
            fee_ret = -FEE_PER_FILL * (1.0 + exit_fill / entry_fill)
            net = float(price_ret + funding_ret + fee_ret)
            event = clean.mii.EventTrade(
                signal_i=int(signal_i),
                entry_i=entry_i,
                exit_i=exit_i,
                direction=side,
                entry_ts=entry_ts,
                exit_ts=exit_ts,
                entry_price=entry_fill,
                exit_price=exit_fill,
                raw_return=net,
                min_path_return=min(min_path - 2.0 * FEE_PER_FILL, net),
                max_path_return=max_path,
                bars_held=max(exit_i - entry_i, 0),
                exit_reason=reason,
                signal_name=state.spec.name,
                signal_kind=state.spec.kind,
                adx14=clean.mii.finite(market.adx14[int(signal_i)], default=0.0),
                rvol96=clean.mii.finite(
                    market.rvol96[int(signal_i)], default=0.0
                ),
                h1_dir_spread=(
                    clean.mii.finite(
                        market.h1_spread[int(signal_i)], default=0.0
                    )
                    * side
                ),
                h4_dir_spread=(
                    clean.mii.finite(
                        market.h4_spread[int(signal_i)], default=0.0
                    )
                    * side
                ),
                dir_ret16=(
                    clean.mii.finite(market.ret16[int(signal_i)], default=0.0)
                    * side
                ),
                dir_ret48=(
                    clean.mii.finite(market.ret48[int(signal_i)], default=0.0)
                    * side
                ),
                dir_ret96=(
                    clean.mii.finite(market.ret96[int(signal_i)], default=0.0)
                    * side
                ),
                dir_macd=(
                    clean.mii.finite(
                        market.macd_hist[int(signal_i)], default=0.0
                    )
                    * side
                ),
                dir_rsi14=(
                    clean.mii.finite(
                        market.rsi14[int(signal_i)], default=50.0
                    )
                    if side > 0
                    else 100.0
                    - clean.mii.finite(
                        market.rsi14[int(signal_i)], default=50.0
                    )
                ),
                atr_pct96=clean.mii.finite(
                    market.atr_pct96[int(signal_i)], default=0.0
                ),
                atr_ratio96_672=clean.mii.finite(
                    market.atr_ratio96_672[int(signal_i)], default=99.0
                ),
                previous_signal_age=clean.mii.finite(
                    state.previous_signal_age[int(signal_i)], default=0.0
                ),
                churn192=clean.mii.finite(
                    state.churn192[int(signal_i)], default=999.0
                ),
            )
            if (
                clean.mii.passes_filter(event, filter_spec)
                and STARTS[audit["symbol"]] <= entry_ts < REUSED_END
                and exit_ts < REUSED_END
            ):
                rows.append(
                    UnifiedTrade(
                        sleeve=sleeve,
                        symbol=audit["symbol"],
                        mechanism="clean_rsi_reversal",
                        source_timeframe="15m",
                        side=side,
                        entry_ts=entry_ts,
                        exit_ts=exit_ts,
                        entry_price=entry_fill,
                        net_return_1x=net,
                        mae_return_1x=event.min_path_return,
                        raw_strength=0.0,
                        strength=0.75 * quality,
                        exposure=exposure,
                        exit_reason=reason,
                    )
                )
        output[scenario] = rows
    return output


def legacy_universe(
    sleeve: str,
    audit: dict[str, Any],
    config_dict: dict[str, Any],
    engine: Any,
    baseline_config: Any,
    h1: pd.DataFrame,
    trade15: pd.DataFrame,
    mark15: pd.DataFrame,
    funding_prefixes: tuple[np.ndarray, np.ndarray],
) -> dict[str, list[UnifiedTrade]]:
    config = type(baseline_config)(**config_dict)
    signal = engine.build_signal(h1, config)
    h1_atr = h1["atr14"].to_numpy(dtype=float)
    h1_ts = h1["ts"].tolist()
    trade15 = trade15.set_index("ts", drop=False)
    mark15 = mark15.set_index("ts", drop=False)
    quality = float(audit["quality"])
    exposure = float(audit["exposure"])
    output: dict[str, list[UnifiedTrade]] = {}
    funding_times, funding_cumulative = funding_prefixes
    for scenario, (slippage, delay) in account.SCENARIOS.items():
        rows: list[UnifiedTrade] = []
        for signal_i in np.flatnonzero(signal):
            entry_h1_i = int(signal_i + delay)
            if entry_h1_i >= len(h1):
                continue
            side = int(signal[signal_i])
            signal_atr = float(h1_atr[signal_i])
            if side == 0 or not np.isfinite(signal_atr) or signal_atr <= 0.0:
                continue
            entry_ts = pd.Timestamp(h1_ts[entry_h1_i])
            if entry_ts not in trade15.index or entry_ts >= REUSED_END:
                continue
            timeout_h1_i = min(
                len(h1) - 1, entry_h1_i + config.max_hold_bars
            )
            timeout_ts = pd.Timestamp(h1_ts[timeout_h1_i])
            entry_raw = float(trade15.at[entry_ts, "open"])
            entry_fill = adverse_fill(
                entry_raw, side, entry=True, slippage=slippage
            )
            stop = entry_fill - side * config.sl_atr * signal_atr
            target = (
                entry_fill + side * config.tp_atr * signal_atr
                if config.exit_kind == "fixed"
                else None
            )
            trail: float | None = None
            best_price = entry_fill
            exit_ts = timeout_ts
            raw_exit = float(trade15.at[timeout_ts, "open"])
            reason = "timeout_open"
            exited = False
            for h1_i in range(entry_h1_i, timeout_h1_i):
                hour_ts = pd.Timestamp(h1_ts[h1_i])
                sub_end = hour_ts + pd.Timedelta(hours=1)
                trade_hour = trade15.loc[
                    (trade15["ts"] >= hour_ts) & (trade15["ts"] < sub_end)
                ]
                mark_hour = mark15.loc[
                    (mark15["ts"] >= hour_ts) & (mark15["ts"] < sub_end)
                ]
                if len(trade_hour) != 4 or len(mark_hour) != 4:
                    raise RuntimeError(
                        f"{audit['symbol']} incomplete 15m protection hour {hour_ts}"
                    )
                for trade_bar, mark_bar in zip(
                    trade_hour.itertuples(index=False),
                    mark_hour.itertuples(index=False),
                    strict=True,
                ):
                    hit_reason, trigger, gap = mark_hit(
                        side,
                        mark_open=float(mark_bar.open),
                        mark_high=float(mark_bar.high),
                        mark_low=float(mark_bar.low),
                        stop=stop,
                        target=target,
                        trail=trail,
                    )
                    if hit_reason is None or trigger is None:
                        continue
                    exit_ts = pd.Timestamp(trade_bar.ts)
                    raw_exit = (
                        float(trade_bar.open)
                        if gap
                        else mapped_intrabar_fill(
                            trigger,
                            trade_open=float(trade_bar.open),
                            trade_low=float(trade_bar.low),
                            trade_high=float(trade_bar.high),
                            mark_open=float(mark_bar.open),
                        )
                    )
                    reason = hit_reason
                    exited = True
                    break
                if exited:
                    break
                if config.exit_kind == "trailing":
                    if side > 0:
                        best_price = max(best_price, float(trade_hour["high"].max()))
                        if (
                            best_price - entry_fill
                            >= config.trail_activation_atr * signal_atr
                        ):
                            candidate = best_price - config.trail_atr * signal_atr
                            trail = (
                                candidate if trail is None else max(trail, candidate)
                            )
                    else:
                        best_price = min(best_price, float(trade_hour["low"].min()))
                        if (
                            entry_fill - best_price
                            >= config.trail_activation_atr * signal_atr
                        ):
                            candidate = best_price + config.trail_atr * signal_atr
                            trail = (
                                candidate if trail is None else min(trail, candidate)
                            )
            if exit_ts >= REUSED_END:
                continue
            exit_fill = adverse_fill(
                raw_exit, side, entry=False, slippage=slippage
            )
            price_ret = side * (exit_fill / entry_fill - 1.0)
            funding_ret = engine.trade_funding(
                int(entry_ts.value),
                int(exit_ts.value),
                side,
                funding_times,
                funding_cumulative,
            )
            fee_ret = engine.FEE_PER_FILL * (1.0 + exit_fill / entry_fill)
            net = float(price_ret - fee_ret + funding_ret)
            path = trade15.loc[
                (trade15["ts"] >= entry_ts) & (trade15["ts"] <= exit_ts)
            ]
            if side > 0:
                mae = float(path["low"].min() / entry_fill - 1.0)
            else:
                mae = float(1.0 - path["high"].max() / entry_fill)
            mae -= 2.0 * engine.FEE_PER_FILL
            rows.append(
                UnifiedTrade(
                    sleeve=sleeve,
                    symbol=audit["symbol"],
                    mechanism=audit["mechanism"],
                    source_timeframe="1h",
                    side=side,
                    entry_ts=entry_ts,
                    exit_ts=exit_ts,
                    entry_price=entry_fill,
                    net_return_1x=net,
                    mae_return_1x=min(mae, net),
                    raw_strength=0.0,
                    cooldown_hours=int(config.cooldown_bars),
                    strength=0.75 * quality,
                    exposure=exposure,
                    exit_reason=reason,
                )
            )
        output[scenario] = rows
    return output


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    frames = {
        symbol: load_symbol_frame(symbol, end=REUSED_END) for symbol in STARTS
    }
    funding = {symbol: load_funding(symbol, end=REUSED_END) for symbol in STARTS}
    marks = {symbol: load_mark(symbol) for symbol in STARTS}
    contexts, captured, featured, prefixes = legacy_full.prepare()
    results: dict[str, Any] = {}
    routed_by_mode: dict[str, dict[str, list[UnifiedTrade]]] = {}
    raw_counts: dict[str, Any] = {}
    for mode, mode_source in source["results"].items():
        options: dict[str, list[dict[str, Any]]] = {}
        active_sleeves: list[str] = []
        raw_counts[mode] = {}
        for sleeve, selection in mode_source["selection"].items():
            if selection["option"] == "dropped":
                continue
            audit = manifest["sleeve_configs"][sleeve]
            config = selection["config"]
            symbol = audit["symbol"]
            if audit["source"] == "prefit_frontier_asset_first":
                universe = frontier_universe(
                    sleeve,
                    audit,
                    config,
                    frames[symbol],
                    marks[symbol],
                    funding[symbol],
                )
            elif audit["source"] == "asset_specific_clean_rsi_hf":
                universe = clean_universe(
                    sleeve,
                    audit,
                    config,
                    frames[symbol],
                    marks[symbol],
                    funding[symbol],
                )
            elif audit["source"] == "legacy_asset_specific_1h":
                asset = symbol.removesuffix("USDT")
                baseline = next(
                    cfg
                    for name, cfg in captured.items()
                    if name.startswith(asset) and cfg.style == audit["mechanism"]
                )
                universe = legacy_universe(
                    sleeve,
                    audit,
                    config,
                    contexts[asset]["engine"],
                    baseline,
                    featured[asset],
                    frames[symbol],
                    marks[symbol],
                    prefixes[asset],
                )
            else:
                raise RuntimeError(f"unknown source {audit['source']}")
            active_sleeves.append(sleeve)
            options[sleeve] = [
                {"option_id": selection["option"], "config": config, "universe": universe}
            ]
            raw_counts[mode][sleeve] = {
                scenario: len(rows) for scenario, rows in universe.items()
            }
        sleeves = tuple(active_sleeves)
        chosen = tuple(0 for _ in sleeves)
        routed = account.route_scenarios(
            chosen,
            sleeves,
            options,
            mode=mode,
            frames=frames,
            funding=funding,
        )
        source_scale = float(mode_source["result"]["scale"])
        source_scale_result = account.scale_result(routed, source_scale)
        scale_rows = [
            account.scale_result(routed, scale) for scale in account.SCALES
        ]
        passing = [row for row in scale_rows if row["hard_pass"]]
        buffered = [
            row
            for row in passing
            if min(
                row["scenarios"][scenario][window]["max_dd"]
                for scenario in account.SCENARIOS
                for window in ("full", "current_3m")
            )
            > account.ROBUST_DD_BUFFER
        ]
        best = max(buffered or passing or scale_rows, key=lambda row: row["score"])
        results[mode] = {
            "active_sleeves": sleeves,
            "source_trade_ohlc_scale": source_scale,
            "source_scale_result": source_scale_result,
            "best_mark_price_scale_result": best,
            "scale_grid": scale_rows,
        }
        routed_by_mode[mode] = routed

    trade_rows: list[dict[str, Any]] = []
    for mode, routed in routed_by_mode.items():
        scale = results[mode]["best_mark_price_scale_result"]["scale"]
        for trade in routed["base"]:
            trade_rows.append({"mode": mode, "scale": scale, **asdict(trade)})
    pd.DataFrame(trade_rows).to_csv(TRADES_OUTPUT, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "v6_mark_price_full_account_replay_not_registered",
        "research_cutoff_exclusive": REUSED_END.isoformat(),
        "future_oos_read": False,
        "frozen_v5_modified": False,
        "execution_model": {
            "signals_and_entries": "trade OHLC; next due open; adverse slippage",
            "protective_trigger": "Binance 15m mark-price OHLC",
            "gap_fill": "same 15m trade open plus adverse slippage",
            "intrabar_fill": (
                "trigger price mapped by same-bar trade-open/mark-open basis, "
                "clipped to trade high-low, then adverse slippage"
            ),
            "trailing_update": "closed strategy bar only; active on next bar",
            "same_bar_collision": "stop first",
            "account_state": "rerouted from changed actual exit timestamps",
        },
        "raw_opportunity_counts": raw_counts,
        "results": results,
        "trades_csv": str(TRADES_OUTPUT.relative_to(ROOT)),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# BIN-15M-AS6S V6 mark-price完整账户重放（2026-07-15）",
        "",
        "信号和入场使用trade OHLC；保护单由15m mark OHLC触发，退出按trade价格代理成交并重新运行联合账户仲裁。未来OOS未读取。",
        "",
        "| 路线 | 原scale | 原scale hard pass | mark最佳scale | mark hard pass | full年化倍数 | full胜率 | full回撤 | 当前3m收益 | 当前3m胜率 | 当前频率 |",
        "|---|---:|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for mode, row in results.items():
        source_result = row["source_scale_result"]
        best = row["best_mark_price_scale_result"]
        base = best["scenarios"]["base"]
        lines.append(
            f"| `{mode}` | {row['source_trade_ohlc_scale']:.2f} | "
            f"`{source_result['hard_pass']}` | {best['scale']:.2f} | "
            f"`{best['hard_pass']}` | {base['full']['annual_multiple']:.3f}x | "
            f"{base['full']['win_rate']:.2%} | {base['full']['max_dd']:.2%} | "
            f"{base['current_3m']['total_return']:+.2%} | "
            f"{base['current_3m']['win_rate']:.2%} | "
            f"{base['current_3m']['trades_per_day']:.3f}/日 |"
        )
    lines.extend(
        [
            "",
            "这是15m OHLC可支持的完整离线mark重放；真实触发后的逐笔成交价仍需testnet/dry-run核对，但退出时序与后续账户占用已重新计算。",
            "",
            f"结构化结果：[`{OUTPUT.name}`](../artifacts/{OUTPUT.name})；交易路径：[`{TRADES_OUTPUT.name}`](../artifacts/{TRADES_OUTPUT.name})。",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "report": str(REPORT.relative_to(ROOT)),
                "results": {
                    mode: {
                        "source_scale_hard_pass": row["source_scale_result"][
                            "hard_pass"
                        ],
                        "best_scale": row["best_mark_price_scale_result"]["scale"],
                        "best_hard_pass": row["best_mark_price_scale_result"][
                            "hard_pass"
                        ],
                        "best_score": row["best_mark_price_scale_result"]["score"],
                    }
                    for mode, row in results.items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
