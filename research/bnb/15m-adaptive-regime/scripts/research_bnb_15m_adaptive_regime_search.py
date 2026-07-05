from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import sys
from dataclasses import asdict, dataclass, replace
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/bnb/15m-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
ENGINE_PATH = (
    ROOT
    / "research/hype/1h-adaptive-regime/scripts"
    / "research_hype_1h_adaptive_regime_search.py"
)
ENGINE_SHA256 = "0420ea44854201e17d4bf5b9142fb8335d143e78772656473a1dcf4594a5f04c"
DATA_PATH = ARTIFACT_DIR / "bnb_binance_15m_closed_klines_2y.parquet"
QUALITY_PATH = ARTIFACT_DIR / "bnb_binance_15m_data_quality_2y.json"
FUNDING_PATH = (
    ROOT
    / "data/normalized/funding/exchange=binance/market_type=perp"
    / "symbol=bnb_usdt_usdt/funding.parquet"
)
DATE_TAG = "2026-07-05"
FREEZE_JSON = ARTIFACT_DIR / f"bnb_15m_adaptive_regime_frozen_primary_{DATE_TAG}.json"
SUMMARY_JSON = ARTIFACT_DIR / f"bnb_15m_adaptive_regime_search_{DATE_TAG}.json"
PREFIT_CSV = ARTIFACT_DIR / f"bnb_15m_adaptive_regime_prefit_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"bnb_15m_adaptive_regime_slices_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"bnb_15m_adaptive_regime_primary_trades_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"bnb-15m-adaptive-regime-search-{DATE_TAG}.md"

TARGET_ANNUAL_MULTIPLE = 10.0
TARGET_WIN_RATE = 0.50
TARGET_MAX_DD = -0.20
MIN_PREFIT_TRADES = 70
MIN_VALIDATION_TRADES = 20
MIN_OOS_TRADES = 15
WARMUP_DAYS = 60
OOS_MONTHS = 3

CONTEXT_MODES = (
    "none",
    "trend_stack",
    "impulse",
    "shock_repair",
    "pullback_zone",
    "compression",
)
VOL_MODES = ("all", "low_mid", "mid", "mid_high", "high")
SESSION_MODES = ("all", "asia", "europe", "us", "liquid_hours")


@dataclass(frozen=True, slots=True)
class SearchConfig:
    base: Any
    context_mode: str
    vol_mode: str
    session_mode: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BNB-specific 15m broad search with a structurally locked three-month OOS."
    )
    parser.add_argument("--random-configs", type=int, default=300_000)
    parser.add_argument("--neighbors", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=2026070501)
    parser.add_argument("--prefit-keep", type=int, default=1_500)
    parser.add_argument("--seed-pool", type=int, default=240)
    parser.add_argument("--progress-every", type=int, default=5_000)
    parser.add_argument("--prefit-only", action="store_true")
    parser.add_argument("--no-ensembles", action="store_true")
    return parser.parse_args()


def load_engine() -> Any:
    actual_hash = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if actual_hash != ENGINE_SHA256:
        raise RuntimeError(
            f"Search engine drift: expected {ENGINE_SHA256}, got {actual_hash}"
        )
    spec = importlib.util.spec_from_file_location("bnb_15m_engine", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load engine: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.TARGET_ANNUAL_MULTIPLE = TARGET_ANNUAL_MULTIPLE
    module.TARGET_WIN_RATE = TARGET_WIN_RATE
    module.TARGET_MAX_DD = TARGET_MAX_DD
    module.MIN_PREFIT_TRADES = MIN_PREFIT_TRADES
    module.MIN_VALIDATION_TRADES = MIN_VALIDATION_TRADES
    module.MIN_HOLDOUT_TRADES = MIN_OOS_TRADES
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


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if not DATA_PATH.exists() or not QUALITY_PATH.exists() or not FUNDING_PATH.exists():
        raise FileNotFoundError("Run fetch_bnb_binance_15m.py first")
    frame = pd.read_parquet(DATA_PATH)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    duplicate = int(frame.duplicated("ts").sum())
    frame = frame.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    expected = pd.date_range(frame["ts"].iloc[0], frame["ts"].iloc[-1], freq="15min")
    missing = expected.difference(pd.DatetimeIndex(frame["ts"]))
    quality_meta = json.loads(QUALITY_PATH.read_text(encoding="utf-8"))
    if duplicate or len(missing) or quality_meta["data_quality"]["blocker_count"]:
        raise RuntimeError(
            f"BNBUSDT 15m data-quality blocker: duplicate={duplicate}, missing={len(missing)}"
        )
    funding = pd.read_parquet(FUNDING_PATH)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = funding.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    if funding.empty or funding["funding_rate"].isna().any():
        raise RuntimeError("BNB funding is empty or contains nulls")
    quality = {
        "rows": int(len(frame)),
        "first_ts": frame["ts"].iloc[0].isoformat(),
        "last_ts": frame["ts"].iloc[-1].isoformat(),
        "missing_bars": int(len(missing)),
        "duplicate_bars": duplicate,
        "funding_rows": int(len(funding)),
        "funding_first_ts": funding["ts"].iloc[0].isoformat(),
        "funding_last_ts": funding["ts"].iloc[-1].isoformat(),
        "contract_snapshot": quality_meta["contract_snapshot"],
    }
    return frame, funding, quality


def add_bnb_features(engine: Any, frame: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    result = engine.add_features(frame, funding)
    result["atr_rank_30d"] = result["atr_bps"].rolling(2_880, min_periods=672).rank(pct=True)
    result["hour_utc"] = result["ts"].dt.hour.astype(np.int16)
    return result


def external_filter(frame: pd.DataFrame, signal: np.ndarray, cfg: SearchConfig) -> np.ndarray:
    result = signal.copy()
    idx = np.flatnonzero(result)
    if len(idx) == 0:
        return result
    side = result[idx].astype(float)
    keep = np.ones(len(idx), dtype=bool)
    atr_rank = frame["atr_rank_30d"].to_numpy(float)[idx]
    if cfg.vol_mode == "low_mid":
        keep &= atr_rank <= 0.50
    elif cfg.vol_mode == "mid":
        keep &= (atr_rank >= 0.25) & (atr_rank <= 0.75)
    elif cfg.vol_mode == "mid_high":
        keep &= atr_rank >= 0.50
    elif cfg.vol_mode == "high":
        keep &= atr_rank >= 0.75

    hour = frame["hour_utc"].to_numpy(int)[idx]
    if cfg.session_mode == "asia":
        keep &= hour < 9
    elif cfg.session_mode == "europe":
        keep &= (hour >= 7) & (hour < 16)
    elif cfg.session_mode == "us":
        keep &= (hour >= 13) & (hour < 22)
    elif cfg.session_mode == "liquid_hours":
        keep &= (hour >= 6) & (hour < 22)

    close = frame["close"].to_numpy(float)[idx]
    ema20 = frame["ema21"].to_numpy(float)[idx]
    ema80 = frame["ema89"].to_numpy(float)[idx]
    ema192 = frame["ema233"].to_numpy(float)[idx]
    atr = frame["atr14"].to_numpy(float)[idx]
    rvol = frame["rvol48"].to_numpy(float)[idx]
    body = frame["body_atr"].to_numpy(float)[idx]
    close_pos = frame["close_pos"].to_numpy(float)[idx]
    ret12 = frame["roc12_bps"].to_numpy(float)[idx]
    if cfg.context_mode == "trend_stack":
        aligned = np.where(
            side > 0,
            (ema20 > ema80) & (ema80 > ema192),
            (ema20 < ema80) & (ema80 < ema192),
        )
        keep &= aligned
    elif cfg.context_mode == "impulse":
        keep &= (side * body >= 0.5) & (rvol >= 1.0)
    elif cfg.context_mode == "shock_repair":
        keep &= np.where(
            side > 0,
            (ret12 <= -150) & (close_pos >= 0.60),
            (ret12 >= 150) & (close_pos <= 0.40),
        )
    elif cfg.context_mode == "pullback_zone":
        aligned = np.where(side > 0, ema20 > ema80, ema20 < ema80)
        keep &= aligned & (np.abs(close - ema20) <= 0.75 * atr)
    elif cfg.context_mode == "compression":
        width = frame["bb_width_z48"].to_numpy(float)[idx]
        keep &= width <= 0.0
    result[idx[~keep]] = 0
    return result


def build_signal(engine: Any, frame: pd.DataFrame, cfg: SearchConfig) -> np.ndarray:
    return external_filter(frame, engine.build_signal(frame, cfg.base), cfg)


def style_window(engine: Any, style: str, rng: random.Random) -> int:
    if style in {"bb_revert", "bb_break", "keltner_break", "squeeze_release"}:
        return rng.choice(engine.BAND_WINDOWS)
    if style == "donchian_break":
        return rng.choice(engine.DONCHIAN_WINDOWS)
    if style == "rsi_reversal":
        return rng.choice(engine.RSI_WINDOWS)
    if style == "stoch_reversal":
        return rng.choice(engine.STOCH_WINDOWS)
    if style in {"cci_reversal", "williams_reversal"}:
        return rng.choice(engine.CCI_WINDOWS)
    if style == "vwap_revert":
        return rng.choice(engine.VWAP_WINDOWS)
    return rng.choice(engine.BAND_WINDOWS)


def random_config(engine: Any, rng: random.Random, index: int) -> SearchConfig:
    donor = engine.random_config(rng, index)
    style = rng.choices(
        engine.STYLES,
        weights=(8, 8, 10, 4, 7, 3, 3, 2, 2, 10, 8, 8, 6, 2, 10, 4),
        k=1,
    )[0]
    fast = rng.choice(engine.EMA_VALUES[:-2])
    slow = rng.choice([value for value in engine.EMA_VALUES if value > fast * 1.35])
    min_adx = rng.choice((0.0, 0.0, 12.0, 16.0, 20.0, 24.0, 28.0, 32.0))
    max_adx = rng.choice((100.0, 100.0, 28.0, 36.0, 45.0))
    if max_adx <= min_adx:
        max_adx = 100.0
    min_atr = rng.choice((0.0, 0.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0))
    max_atr = rng.choice((10_000.0, 10_000.0, 50.0, 75.0, 100.0, 150.0, 250.0))
    if max_atr <= min_atr:
        max_atr = 10_000.0
    exit_kind = rng.choices(("fixed", "trailing"), weights=(0.65, 0.35), k=1)[0]
    base = replace(
        donor,
        name=f"BNB_15M_AR_R{index:07d}",
        style=style,
        side_mode=rng.choices(("both", "long", "short"), weights=(0.45, 0.35, 0.20), k=1)[0],
        ema_fast=fast,
        ema_slow=slow,
        ema_htf=rng.choice((55, 89, 144, 233, 377)),
        indicator_window=style_window(engine, style, rng),
        min_adx=min_adx,
        max_adx=max_adx,
        min_rvol=rng.choice((0.0, 0.0, 0.6, 0.8, 1.0, 1.25, 1.5)),
        min_atr_bps=min_atr,
        max_atr_bps=max_atr,
        min_dir_roc_bps=rng.choice((-10_000.0, -300.0, -150.0, -75.0, 0.0, 50.0, 100.0, 200.0)),
        max_dist_ema_bps=rng.choice((10_000.0, 300.0, 500.0, 750.0, 1_000.0, 1_500.0)),
        htf_mode=rng.choices(("none", "h4", "h12", "d1"), weights=(0.35, 0.30, 0.25, 0.10), k=1)[0],
        require_macd_turn=rng.random() < 0.25,
        require_body_dir=rng.random() < 0.25,
        max_aligned_funding_bps=rng.choice((10_000.0, 10_000.0, 0.5, 1.0, 2.0, 4.0)),
        exit_kind=exit_kind,
        tp_atr=rng.choice((2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 16.0)),
        sl_atr=rng.choice((1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0)),
        trail_activation_atr=rng.choice((2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)),
        trail_atr=rng.choice((1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0)),
        max_hold_bars=rng.choice((32, 48, 64, 96, 144, 192, 288, 384)),
        cooldown_bars=rng.choice((0, 0, 8, 16, 24, 48, 96)),
        entry_delay_bars=1,
        sizing_kind=rng.choices(("risk", "fixed"), weights=(0.55, 0.45), k=1)[0],
        fixed_leverage=rng.choice((0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)),
        risk_fraction=rng.choice((0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025, 0.03)),
        max_leverage=rng.choice((1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)),
    )
    return SearchConfig(
        base=base,
        context_mode=rng.choices(CONTEXT_MODES, weights=(45, 15, 10, 10, 15, 5), k=1)[0],
        vol_mode=rng.choices(VOL_MODES, weights=(55, 8, 12, 17, 8), k=1)[0],
        session_mode=rng.choices(SESSION_MODES, weights=(75, 5, 5, 5, 10), k=1)[0],
    )


def config_dict(cfg: SearchConfig) -> dict[str, Any]:
    return {
        "base": asdict(cfg.base),
        "context_mode": cfg.context_mode,
        "vol_mode": cfg.vol_mode,
        "session_mode": cfg.session_mode,
    }


def strict_metrics(
    engine: Any, trades: list[Any], start: pd.Timestamp, end: pd.Timestamp
) -> dict[str, float]:
    selected = [
        trade
        for trade in trades
        if start <= trade.entry_ts < end and trade.exit_ts < end
    ]
    return engine.metrics(selected, start, end)


def candidate_from_trades(
    engine: Any,
    cfg: SearchConfig,
    trades: list[Any],
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    prefit_end: pd.Timestamp,
) -> Any | None:
    train = strict_metrics(engine, trades, train_start, train_end)
    validation = strict_metrics(engine, trades, train_end, prefit_end)
    prefit = strict_metrics(engine, trades, train_start, prefit_end)
    score = engine.prefit_score(train, validation, prefit)
    if score <= -1e8:
        return None
    return engine.Candidate(
        name=cfg.base.name,
        kind="single",
        styles=cfg.base.style,
        config_names=cfg.base.name,
        prefit_score=score,
        prefit_pass=engine.prefit_gate(train, validation, prefit),
        train=train,
        validation=validation,
        prefit=prefit,
    )


def selection_key(candidate: Any) -> tuple[int, float, float, float, float]:
    return (
        int(candidate.prefit_pass),
        candidate.prefit_score,
        min(candidate.train["annual_multiple"], candidate.validation["annual_multiple"]),
        min(candidate.train["max_dd"], candidate.validation["max_dd"]),
        min(candidate.train["win_rate"], candidate.validation["win_rate"]),
    )


def retain(
    rows: list[tuple[Any, SearchConfig, list[Any]]],
    item: tuple[Any, SearchConfig, list[Any]],
    keep: int,
) -> list[tuple[Any, SearchConfig, list[Any]]]:
    rows.append(item)
    if len(rows) > keep * 3:
        rows = sorted(rows, key=lambda row: selection_key(row[0]), reverse=True)[:keep]
    return rows


def mutate(engine: Any, seed: SearchConfig, rng: random.Random, index: int) -> SearchConfig:
    donor = random_config(engine, rng, index)
    groups = (
        "signal",
        "ema",
        "momentum",
        "filters",
        "htf",
        "exit",
        "hold",
        "sizing",
        "context",
        "vol",
        "session",
    )
    chosen = set(rng.sample(groups, k=rng.choice((1, 2, 2, 3, 3, 4))))
    base = seed.base
    other = donor.base
    updates: dict[str, Any] = {"name": f"BNB_15M_AR_N{index:07d}"}
    mapping = {
        "signal": (
            "style",
            "side_mode",
            "indicator_window",
            "threshold_low",
            "threshold_high",
            "band_k",
            "pullback_atr",
        ),
        "ema": ("ema_fast", "ema_slow", "ema_htf"),
        "momentum": (
            "roc_window",
            "roc_threshold_bps",
            "macd_fast",
            "macd_slow",
            "macd_signal",
        ),
        "filters": (
            "min_adx",
            "max_adx",
            "min_rvol",
            "min_atr_bps",
            "max_atr_bps",
            "min_dir_roc_bps",
            "max_dist_ema_bps",
            "require_macd_turn",
            "require_body_dir",
            "max_aligned_funding_bps",
        ),
        "htf": ("htf_mode",),
        "exit": (
            "exit_kind",
            "tp_atr",
            "sl_atr",
            "trail_activation_atr",
            "trail_atr",
        ),
        "hold": ("max_hold_bars", "cooldown_bars"),
        "sizing": ("sizing_kind", "fixed_leverage", "risk_fraction", "max_leverage"),
    }
    for group in chosen:
        for field in mapping.get(group, ()):  # external groups are handled below
            updates[field] = getattr(other, field)
    mutated = replace(base, **updates, entry_delay_bars=1)
    context = donor.context_mode if "context" in chosen else seed.context_mode
    vol = donor.vol_mode if "vol" in chosen else seed.vol_mode
    session = donor.session_mode if "session" in chosen else seed.session_mode
    return SearchConfig(mutated, context, vol, session)


def candidate_row(candidate: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": candidate.name,
        "kind": candidate.kind,
        "styles": candidate.styles,
        "config_names": candidate.config_names,
        "prefit_score": candidate.prefit_score,
        "prefit_pass": candidate.prefit_pass,
        "target_pass": candidate.target_pass,
    }
    for prefix, values in (
        ("train", candidate.train),
        ("validation", candidate.validation),
        ("prefit", candidate.prefit),
        ("holdout", candidate.holdout or {}),
        ("full", candidate.full or {}),
    ):
        for key, value in values.items():
            row[f"{prefix}_{key}"] = value
    return row


def simulate(
    engine: Any,
    frame: pd.DataFrame,
    cfg: SearchConfig,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    start: pd.Timestamp | None = None,
) -> list[Any]:
    signal = build_signal(engine, frame, cfg)
    if start is not None:
        allowed = frame["ts"] + pd.Timedelta(minutes=15 * cfg.base.entry_delay_bars) >= start
        signal = signal.copy()
        signal[~allowed.to_numpy()] = 0
    return engine.simulate_trades(
        frame, signal, cfg.base, funding_times, funding_cumulative
    )


def metric_gate(metric: dict[str, float], min_trades: int) -> bool:
    return bool(
        metric["trades"] >= min_trades
        and metric["annual_multiple"] >= TARGET_ANNUAL_MULTIPLE
        and metric["win_rate"] >= TARGET_WIN_RATE
        and metric["max_dd"] > TARGET_MAX_DD
    )


def main() -> None:
    args = parse_args()
    engine = load_engine()
    raw_frame, funding, quality = load_data()
    raw_start = pd.Timestamp(raw_frame["ts"].iloc[0])
    full_end = pd.Timestamp(raw_frame["ts"].iloc[-1]) + pd.Timedelta(minutes=15)
    oos_start = full_end - pd.DateOffset(months=OOS_MONTHS)
    train_start = raw_start + pd.Timedelta(days=WARMUP_DAYS)
    train_end = (train_start + (oos_start - train_start) * 0.70).floor("15min")
    split = {
        "raw_start": raw_start.isoformat(),
        "train_start": train_start.isoformat(),
        "train_end": train_end.isoformat(),
        "validation_end": oos_start.isoformat(),
        "oos_start": oos_start.isoformat(),
        "full_end": full_end.isoformat(),
    }
    print(f"data rows={len(raw_frame)} split={split}", flush=True)
    prefit_raw = raw_frame.loc[raw_frame["ts"] < oos_start].copy().reset_index(drop=True)
    prefit_funding = funding.loc[funding["ts"] < oos_start].copy().reset_index(drop=True)
    prefit_frame = add_bnb_features(engine, prefit_raw, prefit_funding)
    funding_times, funding_cumulative = engine.funding_prefix(prefit_funding)

    rng = random.Random(args.seed)
    retained: list[tuple[Any, SearchConfig, list[Any]]] = []
    counts = {
        "random_requested": args.random_configs,
        "first_evaluated": 0,
        "first_eligible": 0,
        "first_prefit_pass": 0,
        "neighbors_requested": args.neighbors,
        "neighbors_evaluated": 0,
        "neighbors_eligible": 0,
        "neighbors_prefit_pass": 0,
    }
    for index in range(args.random_configs):
        cfg = random_config(engine, rng, index)
        signal = build_signal(engine, prefit_frame, cfg)
        if int(np.count_nonzero(signal)) < 12:
            continue
        trades = engine.simulate_trades(
            prefit_frame,
            signal,
            cfg.base,
            funding_times,
            funding_cumulative,
        )
        candidate = candidate_from_trades(
            engine, cfg, trades, train_start, train_end, oos_start
        )
        counts["first_evaluated"] += 1
        if candidate is not None:
            counts["first_eligible"] += 1
            counts["first_prefit_pass"] += int(candidate.prefit_pass)
            retained = retain(retained, (candidate, cfg, trades), args.prefit_keep)
        if (index + 1) % args.progress_every == 0 and retained:
            best = max(retained, key=lambda row: selection_key(row[0]))[0]
            print(
                f"first {index + 1}/{args.random_configs} eligible={counts['first_eligible']} "
                f"passes={counts['first_prefit_pass']} best={best.name} "
                f"ann={best.prefit['annual_multiple']:.3f} dd={best.prefit['max_dd']:.3f} "
                f"win={best.prefit['win_rate']:.3f}",
                flush=True,
            )
    retained = sorted(retained, key=lambda row: selection_key(row[0]), reverse=True)[: args.prefit_keep]
    if not retained:
        raise RuntimeError("No first-pass strategy survived")

    seeds = [row[1] for row in retained[: args.seed_pool]]
    seen = {json.dumps(config_dict(cfg), sort_keys=True) for cfg in seeds}
    for index in range(args.neighbors):
        cfg = mutate(engine, seeds[index % len(seeds)], rng, args.random_configs + index)
        key = json.dumps(config_dict(cfg), sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        signal = build_signal(engine, prefit_frame, cfg)
        if int(np.count_nonzero(signal)) < 12:
            continue
        trades = engine.simulate_trades(
            prefit_frame,
            signal,
            cfg.base,
            funding_times,
            funding_cumulative,
        )
        candidate = candidate_from_trades(
            engine, cfg, trades, train_start, train_end, oos_start
        )
        counts["neighbors_evaluated"] += 1
        if candidate is not None:
            counts["neighbors_eligible"] += 1
            counts["neighbors_prefit_pass"] += int(candidate.prefit_pass)
            retained = retain(retained, (candidate, cfg, trades), args.prefit_keep)
        if (index + 1) % args.progress_every == 0 and retained:
            best = max(retained, key=lambda row: selection_key(row[0]))[0]
            print(
                f"neighbor {index + 1}/{args.neighbors} eligible={counts['neighbors_eligible']} "
                f"passes={counts['neighbors_prefit_pass']} best={best.name} "
                f"ann={best.prefit['annual_multiple']:.3f} dd={best.prefit['max_dd']:.3f} "
                f"win={best.prefit['win_rate']:.3f}",
                flush=True,
            )
    retained = sorted(retained, key=lambda row: selection_key(row[0]), reverse=True)[: args.prefit_keep]
    if args.prefit_only:
        print(json.dumps(json_safe({"status": "prefit_only", "counts": counts, "best": candidate_row(retained[0][0])}), indent=2, ensure_ascii=False))
        return

    ensembles: list[tuple[Any, tuple[SearchConfig, SearchConfig], list[Any], tuple[float, float]]] = []
    if not args.no_ensembles:
        trends = [row for row in retained if row[1].base.style in engine.TREND_STYLES][:30]
        reversions = [row for row in retained if row[1].base.style in engine.REVERSION_STYLES][:30]
        for left, right in product(trends, reversions):
            left_candidate, left_cfg, left_trades = left
            right_candidate, right_cfg, right_trades = right
            merged = engine.merge_trade_sets(
                left_trades,
                right_trades,
                left_candidate.prefit_score,
                right_candidate.prefit_score,
            )
            train = strict_metrics(engine, merged, train_start, train_end)
            validation = strict_metrics(engine, merged, train_end, oos_start)
            prefit = strict_metrics(engine, merged, train_start, oos_start)
            score = engine.prefit_score(train, validation, prefit)
            if score <= -1e8:
                continue
            candidate = engine.Candidate(
                name=f"ENS__{left_cfg.base.name}__{right_cfg.base.name}",
                kind="ensemble",
                styles=f"{left_cfg.base.style}+{right_cfg.base.style}",
                config_names=f"{left_cfg.base.name}+{right_cfg.base.name}",
                prefit_score=score,
                prefit_pass=engine.prefit_gate(train, validation, prefit),
                train=train,
                validation=validation,
                prefit=prefit,
            )
            ensembles.append(
                (
                    candidate,
                    (left_cfg, right_cfg),
                    merged,
                    (left_candidate.prefit_score, right_candidate.prefit_score),
                )
            )
        ensembles.sort(key=lambda row: selection_key(row[0]), reverse=True)
        ensembles = ensembles[:300]
    counts["retained_singles"] = len(retained)
    counts["retained_ensembles"] = len(ensembles)

    prefit_rows: list[dict[str, Any]] = []
    for candidate, cfg, _trades in retained:
        prefit_rows.append({**candidate_row(candidate), "config": json.dumps(config_dict(cfg), sort_keys=True)})
    for candidate, configs, _trades, priorities in ensembles:
        prefit_rows.append(
            {
                **candidate_row(candidate),
                "config": json.dumps([config_dict(cfg) for cfg in configs], sort_keys=True),
                "priorities": json.dumps(priorities),
            }
        )
    pd.DataFrame(prefit_rows).sort_values(
        ["prefit_pass", "prefit_score"], ascending=False
    ).to_csv(PREFIT_CSV, index=False)

    single = retained[0]
    ensemble = ensembles[0] if ensembles else None
    if ensemble is not None and selection_key(ensemble[0]) > selection_key(single[0]):
        primary_candidate = ensemble[0]
        primary_configs = ensemble[1]
        primary_priorities = ensemble[3]
        primary_kind = "ensemble"
    else:
        primary_candidate = single[0]
        primary_configs = (single[1],)
        primary_priorities = (single[0].prefit_score,)
        primary_kind = "single"
    freeze = {
        "frozen_before_oos_unlock": True,
        "family": "BNB-15M-Adaptive-Regime",
        "primary_name": primary_candidate.name,
        "primary_kind": primary_kind,
        "split": split,
        "prefit_metrics": candidate_row(primary_candidate),
        "configs": [config_dict(cfg) for cfg in primary_configs],
        "priorities": primary_priorities,
        "locked_primaries_planned": 1,
    }
    FREEZE_JSON.write_text(json.dumps(json_safe(freeze), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"PRIMARY FROZEN {primary_candidate.name}; unlocking OOS once", flush=True)

    full_frame = add_bnb_features(engine, raw_frame, funding)
    full_funding_times, full_funding_cumulative = engine.funding_prefix(funding)

    def strategy_trades(start: pd.Timestamp | None) -> list[Any]:
        parts = [
            simulate(
                engine,
                full_frame,
                cfg,
                full_funding_times,
                full_funding_cumulative,
                start,
            )
            for cfg in primary_configs
        ]
        if len(parts) == 1:
            return parts[0]
        return engine.merge_trade_sets(parts[0], parts[1], primary_priorities[0], primary_priorities[1])

    full_trades = strategy_trades(None)
    oos_trades = strategy_trades(oos_start)
    full_metrics = strict_metrics(engine, full_trades, train_start, full_end)
    oos_metrics = strict_metrics(engine, oos_trades, oos_start, full_end)
    primary_candidate.full = full_metrics
    primary_candidate.holdout = oos_metrics
    primary_candidate.target_pass = bool(
        metric_gate(full_metrics, MIN_PREFIT_TRADES)
        and metric_gate(oos_metrics, MIN_OOS_TRADES)
    )
    windows = [
        ("train", train_start, train_end, full_trades),
        ("validation", train_end, oos_start, full_trades),
        ("locked_oos", oos_start, full_end, oos_trades),
        ("full", train_start, full_end, full_trades),
    ]
    cursor = train_start
    index = 1
    while cursor < full_end:
        right = min(full_end, cursor + pd.Timedelta(days=90))
        windows.append((f"block_90d_{index:02d}", cursor, right, oos_trades if cursor >= oos_start else full_trades))
        cursor = right
        index += 1
    slices = [
        {"window": name, "start": left, "end": right, **strict_metrics(engine, trades, left, right)}
        for name, left, right, trades in windows
    ]
    pd.DataFrame(slices).to_csv(SLICES_CSV, index=False)
    pd.DataFrame([asdict(trade) for trade in full_trades]).to_csv(TRADES_CSV, index=False)
    status = (
        "hard_gate_hit_pending_robustness_not_promoted"
        if primary_candidate.target_pass
        else "no_go_locked_oos_hard_gate_failed_not_promoted"
    )
    payload = {
        "family": "BNB-15M-Adaptive-Regime",
        "family_id": "BNB-15M-AR",
        "status": status,
        "targets": {
            "annual_multiple": TARGET_ANNUAL_MULTIPLE,
            "win_rate": TARGET_WIN_RATE,
            "max_drawdown_strictly_greater_than": TARGET_MAX_DD,
            "minimum_prefit_trades": MIN_PREFIT_TRADES,
            "minimum_oos_trades": MIN_OOS_TRADES,
        },
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history",
        },
        "quality": quality,
        "split": split,
        "search_counts": counts,
        "primary": candidate_row(primary_candidate),
        "primary_configs": [config_dict(cfg) for cfg in primary_configs],
        "primary_priorities": primary_priorities,
        "slices": slices,
        "oos_protocol": {
            "prefit_frame_excludes_oos": True,
            "primary_frozen_before_full_features": True,
            "locked_primaries_evaluated": 1,
        },
    }
    SUMMARY_JSON.write_text(json.dumps(json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8")

    def pct(value: float) -> str:
        return f"{value * 100:.2f}%"

    def mult(value: float) -> str:
        return f"{value:.2f}x"

    lines = [
        "# BNB-15M-Adaptive-Regime 广泛搜索 - 2026-07-05",
        "",
        "## 结论",
        "",
        (
            "唯一冻结 primary 同时通过 full 与最近三个月 locked OOS 硬门槛；只允许进入稳健性与 live-executable 审计，不代表可实盘。"
            if primary_candidate.target_pass
            else "唯一冻结 primary 未能同时通过 full 与最近三个月 locked OOS 硬门槛，当前为 `NO-GO / not promoted / not live-ready`。"
        ),
        "",
        f"- primary：`{primary_candidate.name}`；kind/styles：`{primary_kind}` / `{primary_candidate.styles}`。",
        f"- full：annual `{mult(full_metrics['annual_multiple'])}`，return `{pct(full_metrics['total_return'])}`，DD `{pct(full_metrics['max_dd'])}`，win `{pct(full_metrics['win_rate'])}`，trades `{int(full_metrics['trades'])}`，PF `{full_metrics['profit_factor']:.3f}`。",
        f"- locked OOS：annual `{mult(oos_metrics['annual_multiple'])}`，return `{pct(oos_metrics['total_return'])}`，DD `{pct(oos_metrics['max_dd'])}`，win `{pct(oos_metrics['win_rate'])}`，trades `{int(oos_metrics['trades'])}`，PF `{oos_metrics['profit_factor']:.3f}`。",
        f"- hard gate：`{primary_candidate.target_pass}`。",
        "",
        "## 数据与协议",
        "",
        f"- Binance `BNBUSDT` perpetual `15m`：`{quality['rows']}` 根；UTC `{quality['first_ts']}` 至 `{quality['last_ts']}`；missing/duplicate=`0/0`。",
        f"- train：`{split['train_start']}` 至 `{split['train_end']}`；validation 至 `{split['validation_end']}`；locked OOS 至 `{split['full_end']}`。",
        "- prefit feature frame 物理排除 OOS；只评估一个预先落盘 primary。",
        "",
        "## 搜索",
        "",
    ]
    lines.extend(f"- {key}：`{value}`。" for key, value in counts.items())
    lines.extend(
        [
            "- 指标面：EMA/MACD、Donchian、Bollinger、RSI、Stochastic、CCI、Williams %R、Keltner、squeeze、ADX/DI、VWAP、momentum、wick、ATR、RVOL、funding、4h/12h/1d 闭合状态。",
            "- BNB 专属上下文：trend stack、volume impulse、shock repair、pullback zone、compression、滚动波动率分位和低权重 UTC session 消融。",
            "- 持有期搜索集中在 `32–384` 根 15m K，避免默认 `28 bps` round-trip 成本下的高换手幻觉。",
            "",
            "## Promotion 边界",
            "",
            (
                "还需逐 K 回撤、成本/延迟、邻域、清算、过滤器、algoOrder 保护单、重启恢复与缺 K 审计；完成前禁止 candidate/paper-live/live。"
                if primary_candidate.target_pass
                else "hard gate 未通过，禁止 candidate、paper-live、dry-run、handoff 或 live。"
            ),
            "",
            "## 产物",
            "",
            f"- `{FREEZE_JSON.relative_to(ROOT)}`",
            f"- `{SUMMARY_JSON.relative_to(ROOT)}`",
            f"- `{PREFIT_CSV.relative_to(ROOT)}`",
            f"- `{SLICES_CSV.relative_to(ROOT)}`",
            f"- `{TRADES_CSV.relative_to(ROOT)}`",
            "",
        ]
    )
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(json_safe({"status": status, "counts": counts, "primary": candidate_row(primary_candidate)}), indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
