from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import mmtf_engine as engine
import mmtf_v2
import research_hype_15m_mmtf_v2_clean_tune as tune


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-multi-mechanism-trend-following"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
TUNE_PATH = ARTIFACT_DIR / "hype_15m_mmtf_v2_clean_tune_2026-07-22.json"
M1_ROOT = ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1m"


def _verify_freeze(summary: dict[str, Any]) -> None:
    scripts = Path(__file__).parent
    current = {
        "engine": hashlib.sha256((scripts / "mmtf_engine.py").read_bytes()).hexdigest(),
        "clean_adapter": hashlib.sha256((scripts / "mmtf_v2.py").read_bytes()).hexdigest(),
        "tune_script": hashlib.sha256(
            (scripts / "research_hype_15m_mmtf_v2_clean_tune.py").read_bytes()
        ).hexdigest(),
    }
    if current != summary["code_hashes"]:
        raise RuntimeError(f"frozen code hash mismatch: {current} != {summary['code_hashes']}")


def _bootstrap(trade_returns: np.ndarray, *, draws: int = 20_000, seed: int = 2026072203) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    ending = np.empty(draws, dtype="float64")
    max_dd = np.empty(draws, dtype="float64")
    win_rate = np.empty(draws, dtype="float64")
    for index in range(draws):
        sample = rng.choice(trade_returns, size=len(trade_returns), replace=True)
        path = np.cumprod(1.0 + sample)
        peaks = np.maximum.accumulate(np.r_[1.0, path])
        equity = np.r_[1.0, path]
        ending[index] = path[-1]
        max_dd[index] = float((1.0 - equity / peaks).max())
        win_rate[index] = float((sample > 0.0).mean())
    quantiles = (0.05, 0.10, 0.50, 0.90, 0.95)
    return {
        "draws": draws,
        "trade_count_per_draw": int(len(trade_returns)),
        "ending_equity_quantiles": {str(q): float(np.quantile(ending, q)) for q in quantiles},
        "max_drawdown_quantiles": {str(q): float(np.quantile(max_dd, q)) for q in quantiles},
        "win_rate_quantiles": {str(q): float(np.quantile(win_rate, q)) for q in quantiles},
        "probability_ending_equity_gt_1": float((ending > 1.0).mean()),
        "probability_max_drawdown_lt_20pct": float((max_dd < 0.20).mean()),
    }


def _neighbor(values: tuple[Any, ...], value: Any) -> list[Any]:
    index = values.index(value)
    output: list[Any] = []
    if index > 0:
        output.append(values[index - 1])
    if index + 1 < len(values):
        output.append(values[index + 1])
    return output


def _neighborhood(clean: mmtf_v2.CleanConfig) -> list[tuple[str, mmtf_v2.CleanConfig]]:
    value_map: dict[str, tuple[Any, ...]] = {
        "ema_fast": tune.FAST_VALUES,
        "ema_slow": tune.SLOW_VALUES,
        "atr_window": tune.ATR_VALUES,
        "adx_min": tune.ADX_VALUES,
        "rvol_min": tune.RVOL_VALUES,
        "keltner_atr": tune.KELTNER_VALUES,
        "sl_atr": tune.SL_VALUES,
        "tp_atr": tune.TP_VALUES,
        "max_hold_bars": tune.MAX_HOLD_VALUES,
        "leverage": tune.LEVERAGE_VALUES,
        "trend_exit_window": tune.TREND_EXIT_VALUES,
    }
    variants: list[tuple[str, mmtf_v2.CleanConfig]] = [("baseline", clean)]
    for field, values in value_map.items():
        current = getattr(clean, field)
        for value in _neighbor(values, current):
            candidate = replace(clean, **{field: value})
            try:
                candidate.validate()
            except ValueError:
                continue
            variants.append((f"{field}={value}", candidate))
    return variants


def _load_1m() -> tuple[pd.DataFrame, dict[str, Any]]:
    paths = sorted(M1_ROOT.glob("date=*/symbol=hype_usdt_usdt.parquet"))
    if not paths:
        raise RuntimeError("1m HYPE data missing for phase audit")
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)
    expected = pd.date_range(frame.ts.iloc[0], frame.ts.iloc[-1], freq="1min")
    quality = {
        "rows": int(len(frame)),
        "first_ts": frame.ts.iloc[0].isoformat(),
        "last_ts": frame.ts.iloc[-1].isoformat(),
        "missing": int(len(expected.difference(pd.DatetimeIndex(frame.ts)))),
        "duplicates": int(frame.ts.duplicated().sum()),
        "unclosed": int((~frame.is_closed.astype(bool)).sum()),
        "critical_null_rows": int(
            frame[["ts", "open", "high", "low", "close", "volume"]].isna().any(axis=1).sum()
        ),
    }
    if sum(value for key, value in quality.items() if key in {"missing", "duplicates", "unclosed", "critical_null_rows"}):
        raise RuntimeError(f"1m phase data blocker: {quality}")
    return frame, quality


def _aggregate_phase(frame: pd.DataFrame, *, offset_minutes: int, end: pd.Timestamp) -> pd.DataFrame:
    source = frame.loc[frame.ts < end].set_index("ts")
    offset = pd.Timedelta(minutes=offset_minutes)
    grouped = source.resample("15min", origin="epoch", offset=offset, label="left", closed="left")
    result = grouped.agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum"), count=("open", "count"),
    )
    result = result.loc[result["count"] == 15].drop(columns="count").reset_index()
    result = result.loc[result.ts + pd.Timedelta(minutes=15) <= end].reset_index(drop=True)
    return result


def _book_from_15m(frame: pd.DataFrame, funding: pd.DataFrame, selection_end: pd.Timestamp) -> engine.FeatureBook:
    ts = pd.DatetimeIndex(frame.ts)
    open_values = frame.open.to_numpy("float64")
    high = frame.high.to_numpy("float64")
    low = frame.low.to_numpy("float64")
    close = frame.close.to_numpy("float64")
    volume = frame.volume.to_numpy("float64")
    atr = {window: engine._atr(high, low, close, window) for window in engine.ATR_WINDOWS}
    ema = {span: engine._ema(close, span) for span in engine.EMA_SPANS}
    all_windows = sorted(set(engine.ENTRY_WINDOWS + engine.EXIT_WINDOWS))
    prior_high = {window: engine._prior_roll(high, window, "max") for window in all_windows}
    prior_low = {window: engine._prior_roll(low, window, "min") for window in all_windows}
    momentum: dict[tuple[int, int], np.ndarray] = {}
    for window in all_windows:
        delta = close - np.r_[np.full(window, np.nan), close[:-window]]
        for atr_window, values in atr.items():
            momentum[(window, atr_window)] = delta / values
    prior_close = np.r_[np.nan, close[:-1]]
    tr = np.maximum(high - low, np.maximum(abs(high - prior_close), abs(low - prior_close)))
    rvol = volume / pd.Series(volume).shift(1).rolling(96, min_periods=96).median().to_numpy("float64")
    return engine.FeatureBook(
        ts=ts,
        terminal_ts=pd.Timestamp(ts[-1]) + pd.Timedelta(minutes=15),
        open=open_values,
        high=high,
        low=low,
        close=close,
        volume=volume,
        atr=atr,
        adx=engine._adx(high, low, close),
        ema=ema,
        prior_high=prior_high,
        prior_low=prior_low,
        momentum_atr=momentum,
        rvol=rvol,
        tr_over_atr={window: tr / values for window, values in atr.items()},
        funding_by_bar=engine._funding_by_bar(ts, funding),
        source_start=pd.Timestamp(ts[0]),
        selection_end=selection_end,
    )


def _phase_audit(clean: mmtf_v2.CleanConfig, selection_end: pd.Timestamp) -> dict[str, Any]:
    m1, quality = _load_1m()
    funding = pd.read_parquet(engine.FUNDING_PATH)
    funding["ts"] = pd.to_datetime(funding.ts, utc=True)
    funding = funding.loc[funding.ts < selection_end]
    config = mmtf_v2.to_engine_config(clean)
    phases: dict[str, Any] = {}
    phase_frames: dict[int, pd.DataFrame] = {}
    for offset in (0, 5, 10):
        frame_15m = _aggregate_phase(m1, offset_minutes=offset, end=selection_end)
        phase_frames[offset] = frame_15m
        book = _book_from_15m(frame_15m, funding, selection_end)
        metrics = engine.run_backtest(book, config).metrics
        phases[str(offset)] = {
            "rows": int(len(frame_15m)),
            "first_ts": frame_15m.ts.iloc[0].isoformat(),
            "last_ts": frame_15m.ts.iloc[-1].isoformat(),
            "metrics": metrics,
        }
    native = engine.build_book(include_locked_oos=False)
    phase0 = phase_frames[0].set_index("ts")
    common = phase0.index.intersection(native.ts)
    native_map = pd.DataFrame(
        {"open": native.open, "high": native.high, "low": native.low, "close": native.close},
        index=native.ts,
    ).loc[common]
    phase_map = phase0.loc[common, ["open", "high", "low", "close"]]
    parity_mismatch = int(
        (~np.isclose(native_map.to_numpy(), phase_map.to_numpy(), rtol=0.0, atol=1e-12)).sum()
    )
    base_return = phases["0"]["metrics"]["total_return"]
    base_dd = phases["0"]["metrics"]["max_drawdown"]
    shifted_returns = np.asarray(
        [phases[str(offset)]["metrics"]["total_return"] for offset in (5, 10)]
    )
    shifted_dds = np.asarray(
        [phases[str(offset)]["metrics"]["max_drawdown"] for offset in (5, 10)]
    )
    all_returns = np.asarray(
        [phases[str(offset)]["metrics"]["total_return"] for offset in (0, 5, 10)]
    )
    return_cv = float(all_returns.std() / abs(all_returns.mean())) if all_returns.mean() else float("inf")
    shifted_return_median = float(np.median(shifted_returns))
    shifted_dd_median = float(np.median(shifted_dds))
    return {
        "source_quality": quality,
        "phase_native_aggregation_mismatch_cells": parity_mismatch,
        "phases": phases,
        "shifted_return_median": shifted_return_median,
        "shifted_to_native_return_ratio": shifted_return_median / base_return if base_return else 0.0,
        "shifted_to_native_mdd_ratio": shifted_dd_median / base_dd if base_dd else float("inf"),
        "cross_phase_return_cv": return_cv,
        "default_phase_gate_pass": bool(
            parity_mismatch == 0
            and shifted_return_median > 0.0
            and shifted_return_median >= 0.40 * base_return
            and shifted_dd_median <= 2.0 * base_dd
            and return_cv < 0.75
        ),
    }


def _extreme_windows(book: engine.FeatureBook, config: engine.Config) -> list[dict[str, Any]]:
    atr_pct = pd.Series(book.atr[config.atr_window] / book.close, index=book.ts)
    rolling = atr_pct.rolling(96 * 30, min_periods=96 * 20).mean().dropna().sort_values(ascending=False)
    selected: list[pd.Timestamp] = []
    for timestamp in rolling.index:
        start = pd.Timestamp(timestamp) - pd.Timedelta(days=30)
        if all(abs(start - existing) >= pd.Timedelta(days=30) for existing in selected):
            selected.append(start)
        if len(selected) == 2:
            break
    output: list[dict[str, Any]] = []
    for start in sorted(selected):
        end = min(start + pd.Timedelta(days=30), book.terminal_ts)
        metrics = engine.run_backtest(book, config, start_ts=start, end_ts=end).metrics
        output.append({"start": start.isoformat(), "end": end.isoformat(), "metrics": metrics})
    return output


def main() -> None:
    tune_summary = json.loads(TUNE_PATH.read_text(encoding="utf-8"))
    _verify_freeze(tune_summary)
    clean = mmtf_v2.clean_from_dict(tune_summary["v3_tuned_freeze"]["config"])
    config = mmtf_v2.to_engine_config(clean)
    book = engine.build_book(include_locked_oos=False)
    base = engine.run_backtest(book, config, detailed=True)
    validation_start = book.terminal_ts - pd.Timedelta(days=90)

    stress: dict[str, Any] = {}
    for name, delay, slippage in (
        ("base_k1_4bps", 1, engine.BASE_SLIPPAGE),
        ("delay_k2_4bps", 2, engine.BASE_SLIPPAGE),
        ("base_k1_8bps", 1, engine.STRESS_SLIPPAGE),
        ("delay_k2_8bps", 2, engine.STRESS_SLIPPAGE),
    ):
        full = engine.run_backtest(
            book, config, entry_delay_bars=delay, slippage_per_fill=slippage
        )
        validation = engine.run_backtest(
            book,
            config,
            start_ts=validation_start,
            entry_delay_bars=delay,
            slippage_per_fill=slippage,
        )
        stress[name] = {"prefit": full.metrics, "validation": validation.metrics}

    neighborhood_rows: list[dict[str, Any]] = []
    for label, variant in _neighborhood(clean):
        result = engine.run_backtest(book, mmtf_v2.to_engine_config(variant))
        validation = engine.run_backtest(
            book, mmtf_v2.to_engine_config(variant), start_ts=validation_start
        )
        neighborhood_rows.append(
            {
                "variant": label,
                **asdict(variant),
                **{f"prefit_{key}": result.metrics[key] for key in ("annual_factor", "max_drawdown", "win_rate", "trades", "profit_factor")},
                **{f"validation_{key}": validation.metrics[key] for key in ("annual_factor", "max_drawdown", "win_rate", "trades", "profit_factor")},
            }
        )
    neighborhood = pd.DataFrame(neighborhood_rows)
    neighborhood["hard_shape_pass"] = (
        (neighborhood.prefit_max_drawdown < 0.20)
        & (neighborhood.prefit_win_rate >= 0.80)
        & (neighborhood.prefit_trades >= 100)
        & (neighborhood.validation_max_drawdown < 0.20)
        & (neighborhood.validation_win_rate >= 0.80)
        & (neighborhood.validation_trades >= 20)
    )
    neighborhood.to_csv(
        ARTIFACT_DIR / "hype_15m_mmtf_v3_parameter_neighborhood_2026-07-22.csv",
        index=False,
    )

    trades = np.asarray([trade["net_return"] for trade in base.trades], dtype="float64")
    leverage_ladder = {
        f"{leverage:g}x": engine.run_backtest(
            book,
            mmtf_v2.to_engine_config(replace(clean, leverage=leverage)),
        ).metrics
        for leverage in (1.0, 2.0, 3.0)
    }
    funding_stress = {
        f"{multiple:g}x_actual": engine.run_backtest(
            replace(book, funding_by_bar=book.funding_by_bar * multiple),
            config,
        ).metrics
        for multiple in (0.0, 1.0, 2.0)
    }
    summary = {
        "family": "HYPE-15M-Multi-Mechanism-Trend-Following",
        "version": "HYPE-15M-Multi-Mechanism-Trend-Following-V3",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "locked_oos_accessed": False,
        "freeze_verified": True,
        "config": asdict(clean),
        "base_prefit": base.metrics,
        "stress": stress,
        "leverage_ladder": leverage_ladder,
        "funding_stress": funding_stress,
        "monte_carlo_trade_bootstrap": _bootstrap(trades),
        "parameter_neighborhood": {
            "variants": int(len(neighborhood)),
            "hard_shape_pass": int(neighborhood.hard_shape_pass.sum()),
            "csv": "research/hype/15m-multi-mechanism-trend-following/artifacts/hype_15m_mmtf_v3_parameter_neighborhood_2026-07-22.csv",
        },
        "extreme_30d_windows": _extreme_windows(book, config),
        "phase_audit": _phase_audit(clean, book.terminal_ts),
        "state_machine_static_audit": {
            "overlapping_trade_pairs": int(
                sum(
                    pd.Timestamp(left["exit_ts"]) > pd.Timestamp(right["entry_ts"])
                    for left, right in zip(base.trades, base.trades[1:], strict=False)
                )
            ),
            "max_leverage": float(max(trade["leverage"] for trade in base.trades)),
            "all_entries_k1_or_later": bool(
                all(pd.Timestamp(trade["entry_ts"]) > pd.Timestamp(trade["signal_ts"]) for trade in base.trades)
            ),
            "protective_exit_reasons": sorted(set(trade["exit_reason"] for trade in base.trades)),
            "runner_present": False,
            "restart_recovery_proven": False,
            "reject_order_recovery_proven": False,
            "missing_bar_fail_closed_proven": False,
            "kill_switch_proven": False,
        },
    }
    (ARTIFACT_DIR / "hype_15m_mmtf_v3_prefit_robustness_2026-07-22.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
