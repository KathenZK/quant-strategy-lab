from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/15m-ema-trend-breakout"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
AUDIT_PATH = ARTIFACT_DIR / "btc_binance_15m_data_quality_latest.json"
SPLITS_PATH = ARTIFACT_DIR / "btc_15m_v40_frozen_splits_2026-07-17.json"
SELECTION_PATH = ARTIFACT_DIR / "btc_15m_v40_frozen_selection_2026-07-17.json"

KERNEL_PATH = ROOT / "research/_shared-kernels/ema-trend-breakout/v2/engine.py"
KERNEL_SHA256 = "36e5d10c0d281701c46446344dd50af7a7589ec03285be3289e82362e1c2917a"

OHLCV_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
FUNDING_ROOT = ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
SYMBOL_FILE = "symbol=btc_usdt_usdt.parquet"
BAR = pd.Timedelta(minutes=15)

FEE_PER_FILL = 0.001
SLIPPAGE_PER_FILL = 0.0004
TOP_TRADE_SHARE_MAX = 0.35
TOP3_TRADE_SHARE_MAX = 0.70
NEIGHBOR_POSITIVE_RATIO_MIN = 0.60

LONG_ADX_GRID = [20.0, 24.0, 28.0, 32.0]
LONG_VOL_GRID = [0.0, 0.25, 0.50]
H1_LONG_ADX_GRID = [14.0, 18.0, 22.0]
BRACKET_GRID = [(4.0, 5.0), (5.0, 7.0), (6.0, 7.0)]
COOLDOWN_GRID = [0, 1]
SHORT_ADX_GRID = [24.0, 30.0, 36.0, 42.0]
SHORT_VOL_GRID = [0.0, 0.25, 0.50]
SHORT_H1_GRID = ["none", "ema"]
STAGE2_VOLUME_QUANTILES = [0.55, 0.65, 0.75]
STAGE2_ATR_REGIMES = ["all", "gte_q40", "q20_to_q80"]
STAGE2_EXIT_PROFILES = [
    (5.0, 7.0),
    (6.0, 7.0),
    (4.0, 5.0),
    (3.0, 5.0),
]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def payload_sha256(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "payload_sha256"}
    return sha256_bytes(canonical_json_bytes(body))


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(rendered + "\n", encoding="utf-8")
    temporary.replace(path)


def atomic_write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def load_kernel() -> Any:
    actual = sha256_bytes(KERNEL_PATH.read_bytes())
    if actual != KERNEL_SHA256:
        raise RuntimeError(
            "ema-trend-breakout v2 SHA mismatch: "
            f"expected {KERNEL_SHA256}, got {actual}"
        )
    module_name = "btc_15m_ema_tb_frozen_v2"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, KERNEL_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load frozen kernel from {KERNEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def read_verified_payload(path: Path, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = payload.get("payload_sha256")
    actual = payload_sha256(payload)
    if not isinstance(expected, str) or expected != actual:
        raise RuntimeError(
            f"{label} payload SHA mismatch: expected {expected}, got {actual}"
        )
    return payload


def parse_splits(payload: dict[str, Any]) -> dict[str, pd.Timestamp]:
    names = [
        "data_end_exclusive",
        "train_start",
        "validation_start",
        "holdout_start",
        "holdout_end",
    ]
    splits = {name: pd.Timestamp(payload[name]) for name in names}
    if any(value.tzinfo is None for value in splits.values()):
        raise RuntimeError("all frozen split timestamps must be timezone-aware")
    if not (
        splits["train_start"]
        < splits["validation_start"]
        < splits["holdout_start"]
        == splits["holdout_end"] - pd.Timedelta(days=181)
        < splits["data_end_exclusive"] + BAR
    ):
        raise RuntimeError("frozen split ordering is invalid")
    if splits["data_end_exclusive"] != splits["holdout_end"]:
        raise RuntimeError("data_end_exclusive must equal holdout_end")
    return splits


def _date_paths(root: Path, start: pd.Timestamp, end: pd.Timestamp) -> list[Path]:
    dates = pd.date_range(
        start.normalize(),
        (end - pd.Timedelta(nanoseconds=1)).normalize(),
        freq="1d",
    )
    paths = [root / f"date={date:%Y-%m-%d}" / SYMBOL_FILE for date in dates]
    missing = [path for path in paths if not path.exists()]
    if missing:
        examples = ", ".join(str(path.relative_to(ROOT)) for path in missing[:3])
        raise FileNotFoundError(f"standard data-lake partitions missing: {examples}")
    return paths


def _read_filtered_parquet(
    paths: Iterable[Path],
    *,
    columns: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    pieces = [
        pd.read_parquet(
            path,
            columns=columns,
            filters=[
                ("ts", ">=", start.to_pydatetime()),
                ("ts", "<", end.to_pydatetime()),
            ],
        )
        for path in paths
    ]
    if not pieces:
        raise RuntimeError("no data-lake partitions selected")
    frame = pd.concat(pieces, ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return (
        frame.loc[(frame["ts"] >= start) & (frame["ts"] < end)]
        .sort_values("ts")
        .reset_index(drop=True)
    )


def load_market(
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load only rows in [start, end); Parquet filters enforce the boundary."""
    market_columns = [
        "ts",
        "exchange",
        "symbol",
        "market_type",
        "timeframe",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "is_closed",
        "source",
    ]
    frame = _read_filtered_parquet(
        _date_paths(OHLCV_ROOT, start, end),
        columns=market_columns,
        start=start,
        end=end,
    )
    if frame.empty:
        raise RuntimeError("BTCUSDT 15m market data is empty")
    expected_rows = int((end - start) / BAR)
    checks = {
        "rows": len(frame) == expected_rows,
        "duplicates": not frame["ts"].duplicated().any(),
        "continuity": pd.DatetimeIndex(frame["ts"]).equals(
            pd.date_range(start, end - BAR, freq=BAR)
        ),
        "exchange": bool(frame["exchange"].eq("binance").all()),
        "symbol": bool(frame["symbol"].eq("BTC/USDT:USDT").all()),
        "market_type": bool(frame["market_type"].eq("perp").all()),
        "timeframe": bool(frame["timeframe"].eq("15m").all()),
        "closed": bool(frame["is_closed"].all()),
        "critical_nulls": not frame[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
                "vwap",
            ]
        ]
        .isna()
        .any()
        .any(),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(f"market data-quality checks failed: {failed}")

    funding_columns = [
        "ts",
        "exchange",
        "symbol",
        "market_type",
        "funding_rate",
        "source",
    ]
    funding = _read_filtered_parquet(
        _date_paths(FUNDING_ROOT, start, end),
        columns=funding_columns,
        start=start,
        end=end,
    )
    if funding.empty:
        raise RuntimeError("BTCUSDT funding data is empty")
    funding_checks = {
        "duplicates": not funding["ts"].duplicated().any(),
        "exchange": bool(funding["exchange"].eq("binance").all()),
        "symbol": bool(funding["symbol"].eq("BTC/USDT:USDT").all()),
        "market_type": bool(funding["market_type"].eq("perp").all()),
        "critical_nulls": not funding[["ts", "funding_rate", "source"]]
        .isna()
        .any()
        .any(),
        "max_gap": funding["ts"].diff().dropna().max() <= pd.Timedelta(hours=8),
    }
    failed = [name for name, passed in funding_checks.items() if not passed]
    if failed:
        raise RuntimeError(f"funding data-quality checks failed: {failed}")
    return frame.set_index("ts"), funding[["ts", "funding_rate"]]


def base_config(kernel: Any, **changes: Any) -> Any:
    defaults = {
        "cost_mode": "explicit",
        "fee_per_fill": FEE_PER_FILL,
        "adverse_slippage_per_fill": SLIPPAGE_PER_FILL,
        "fee_multiplier": 1.0,
        "slippage_multiplier": 1.0,
        "execution_mode": "gap_open",
        "sizing_mode": "fixed",
        "fixed_allocation": 1.0,
        "max_allocation": 1.0,
    }
    defaults.update(changes)
    return kernel.v40_config(**defaults)


def config_universe() -> dict[str, Any]:
    payload = {
        "family": "BTC-15M-EMA-Trend-Breakout",
        "research_identity": "BTC-15M-EMA-TB-V40-transfer-search",
        "kernel_sha256": KERNEL_SHA256,
        "execution": {
            "cost_mode": "explicit",
            "fee_per_fill": FEE_PER_FILL,
            "adverse_slippage_per_fill": SLIPPAGE_PER_FILL,
            "execution_mode": "gap_open",
            "sizing_mode": "fixed",
            "fixed_allocation": 1.0,
        },
        "baseline": "kernel v40_config and v40_flags unchanged except execution",
        "stage1a": {
            "role": "long_only_train_seed_search",
            "long_adx_min": LONG_ADX_GRID,
            "long_vol_min": LONG_VOL_GRID,
            "h1_long_adx_min": H1_LONG_ADX_GRID,
            "bracket_take_profit_hard_stop": BRACKET_GRID,
            "cooldown_bars": COOLDOWN_GRID,
            "count": 216,
        },
        "stage1b": {
            "role": "bidirectional_seed_extension",
            "seed_count": 3,
            "short_adx_min": SHORT_ADX_GRID,
            "short_vol_min": SHORT_VOL_GRID,
            "short_h1_filter": SHORT_H1_GRID,
            "count": 72,
        },
        "stage2": {
            "max_near_miss_seeds": 4,
            "stepwise_contract": (
                "step1 adds exactly one component to each near-miss; step2 "
                "takes each seed's best step1 parent and adds exactly one "
                "different component"
            ),
            "step1": {
                "volume_only": {
                    "rolling_days": 60,
                    "min_period_days": 45,
                    "shift_bars": 1,
                    "quantiles": STAGE2_VOLUME_QUANTILES,
                },
                "atr_regime_only": [
                    value for value in STAGE2_ATR_REGIMES if value != "all"
                ],
                "exit_only": STAGE2_EXIT_PROFILES,
                "per_seed_count": 9,
                "max_count": 36,
            },
            "step2": {
                "parent": "best step1 development result per seed",
                "rule": "add one component whose type differs from the parent",
                "max_per_seed_count": 7,
                "max_count": 28,
            },
            "max_count": 64,
        },
        "gates": {
            "train_return_gt_pct": 0.0,
            "validation_return_gt_pct": 0.0,
            "max_drawdown_abs_pct": 25.0,
            "train_trades_min": 24,
            "validation_trades_min": 12,
            "train_profit_factor_min": 1.15,
            "validation_profit_factor_min": 1.05,
            "double_cost_train_and_validation_positive": True,
            "top_trade_positive_pnl_share_max": TOP_TRADE_SHARE_MAX,
            "top3_trade_positive_pnl_share_max": TOP3_TRADE_SHARE_MAX,
            "neighbor_positive_ratio_min": NEIGHBOR_POSITIVE_RATIO_MIN,
        },
    }
    if payload["stage1a"]["count"] != (
        len(LONG_ADX_GRID)
        * len(LONG_VOL_GRID)
        * len(H1_LONG_ADX_GRID)
        * len(BRACKET_GRID)
        * len(COOLDOWN_GRID)
    ):
        raise AssertionError("Stage1A universe is not exactly 216")
    if payload["stage1b"]["count"] != (
        3 * len(SHORT_ADX_GRID) * len(SHORT_VOL_GRID) * len(SHORT_H1_GRID)
    ):
        raise AssertionError("Stage1B universe is not exactly 72")
    step1_per_seed = (
        len(STAGE2_VOLUME_QUANTILES)
        + len([value for value in STAGE2_ATR_REGIMES if value != "all"])
        + len(STAGE2_EXIT_PROFILES)
    )
    step2_per_seed_max = max(
        len(STAGE2_VOLUME_QUANTILES)
        + len([value for value in STAGE2_ATR_REGIMES if value != "all"]),
        len(STAGE2_VOLUME_QUANTILES) + len(STAGE2_EXIT_PROFILES),
        len([value for value in STAGE2_ATR_REGIMES if value != "all"])
        + len(STAGE2_EXIT_PROFILES),
    )
    if step1_per_seed != payload["stage2"]["step1"]["per_seed_count"]:
        raise AssertionError("Stage2 step1 count is inconsistent")
    if step2_per_seed_max != payload["stage2"]["step2"]["max_per_seed_count"]:
        raise AssertionError("Stage2 step2 count is inconsistent")
    if payload["stage2"]["max_count"] != 4 * (step1_per_seed + step2_per_seed_max):
        raise AssertionError("Stage2 stepwise universe count is inconsistent")
    if payload["stage2"]["max_count"] > 144:
        raise AssertionError("Stage2 universe exceeds 144")
    return payload


def config_universe_sha256() -> str:
    return sha256_bytes(canonical_json_bytes(config_universe()))


def build_feature_base(kernel: Any, frame: pd.DataFrame) -> pd.DataFrame:
    return kernel.build_features(frame, base_config(kernel))


def apply_overlays(
    signals: pd.DataFrame,
    *,
    overlay: dict[str, Any] | None,
) -> pd.DataFrame:
    if not overlay:
        return signals
    out = signals.copy()
    bars_per_day = 24 * 4
    rolling = 60 * bars_per_day
    minimum = 45 * bars_per_day
    allowed = pd.Series(True, index=out.index)
    volume_quantile = overlay.get("volume_quantile")
    if volume_quantile is not None:
        volume_threshold = (
            out["volume_surge"]
            .rolling(rolling, min_periods=minimum)
            .quantile(float(volume_quantile))
            .shift(1)
        )
        allowed &= out["volume_surge"].ge(volume_threshold)
    atr_pct = out["atr"] / out["close"]
    regime = overlay.get("atr_regime")
    if regime == "gte_q40":
        q40 = atr_pct.rolling(rolling, min_periods=minimum).quantile(0.40).shift(1)
        allowed &= atr_pct.ge(q40)
    elif regime == "q20_to_q80":
        q20 = atr_pct.rolling(rolling, min_periods=minimum).quantile(0.20).shift(1)
        q80 = atr_pct.rolling(rolling, min_periods=minimum).quantile(0.80).shift(1)
        allowed &= atr_pct.ge(q20) & atr_pct.le(q80)
    elif regime not in {None, "all"}:
        raise ValueError(f"unknown ATR regime: {regime}")
    out["long_signal"] &= allowed.fillna(False)
    out["short_signal"] &= allowed.fillna(False)
    return out


def build_signals_for_selection(
    kernel: Any,
    features: pd.DataFrame,
    selection: dict[str, Any],
) -> tuple[Any, Any, pd.DataFrame]:
    config = base_config(kernel, **selection["config_changes"])
    flags = kernel.SignalFlags(**selection["flags"])
    signals = kernel.build_signals(features, config, flags)
    signals = apply_overlays(signals, overlay=selection.get("overlay"))
    return config, flags, signals


def mask_before(features: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    masked = features.copy()
    before = masked.index < start
    masked.loc[before, ["long_signal", "short_signal"]] = False
    return masked


def profit_factor(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    returns = pd.to_numeric(trades["trade_return"], errors="coerce").dropna()
    gains = float(returns.loc[returns > 0.0].sum())
    losses = abs(float(returns.loc[returns < 0.0].sum()))
    if losses == 0.0:
        return float("inf") if gains > 0.0 else 0.0
    return gains / losses


def concentration_metrics(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty:
        return {
            "top_trade_positive_pnl_share": 1.0,
            "top3_trade_positive_pnl_share": 1.0,
        }
    positive = (
        pd.to_numeric(trades["trade_return"], errors="coerce")
        .dropna()
        .loc[lambda values: values > 0.0]
        .sort_values(ascending=False)
    )
    total = float(positive.sum())
    if total <= 0.0:
        return {
            "top_trade_positive_pnl_share": 1.0,
            "top3_trade_positive_pnl_share": 1.0,
        }
    return {
        "top_trade_positive_pnl_share": float(positive.iloc[:1].sum() / total),
        "top3_trade_positive_pnl_share": float(positive.iloc[:3].sum() / total),
    }


def metrics_for_period(
    run: Any,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    observed_equity = run.equity_curve.loc[
        (run.equity_curve.index >= start) & (run.equity_curve.index < end)
    ]
    if observed_equity.empty:
        raise RuntimeError(f"empty evaluation period {start} -> {end}")
    expected_index = pd.date_range(start, end - BAR, freq=BAR)
    unexpected = observed_equity.index.difference(expected_index)
    if not unexpected.empty:
        raise RuntimeError(
            f"equity contains timestamps outside split: {unexpected[:3]}"
        )
    expected_observed = expected_index[expected_index >= observed_equity.index.min()]
    if not observed_equity.index.equals(expected_observed):
        raise RuntimeError("equity path has a gap inside the accounted split")
    equity = observed_equity.reindex(expected_index).ffill().fillna(1.0)
    returns = run.period_returns.reindex(expected_index).fillna(0.0)
    trades = run.trades.copy()
    if not trades.empty:
        entries = pd.to_datetime(trades["entry_ts"], utc=True)
        trades = trades.loc[(entries >= start) & (entries < end)].copy()
    initial_and_path = np.concatenate(([1.0], equity.to_numpy(dtype=float)))
    drawdown = initial_and_path / np.maximum.accumulate(initial_and_path) - 1.0
    volatility = float(returns.std(ddof=0))
    metrics: dict[str, Any] = {
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "engine_first_accounted_ts": observed_equity.index.min().isoformat(),
        "bars": int(len(equity)),
        "return_pct": float((equity.iloc[-1] - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "sharpe": float(
            0.0
            if volatility == 0.0
            else returns.mean() / volatility * math.sqrt(365 * 24 * 4)
        ),
        "trades": int(len(trades)),
        "profit_factor": float(profit_factor(trades)),
        "win_rate": float(
            0.0 if trades.empty else trades["trade_return"].gt(0.0).mean()
        ),
        "long_trades": int(0 if trades.empty else trades["direction"].eq(1).sum()),
        "short_trades": int(0 if trades.empty else trades["direction"].eq(-1).sum()),
    }
    metrics.update(concentration_metrics(trades))
    return metrics


def evaluate_period(
    kernel: Any,
    *,
    name: str,
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    signals: pd.DataFrame,
    config: Any,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[dict[str, Any], Any]:
    through_end = frame.loc[frame.index < end]
    start_location = int(through_end.index.searchsorted(start))
    warmup = max(config.warmup_bars, config.entry_delay_bars + 1)
    prefix_location = max(0, start_location - warmup)
    cropped_frame = through_end.iloc[prefix_location:]
    cropped_signals = mask_before(signals.reindex(cropped_frame.index), start)
    run = kernel.run_backtest(
        name,
        cropped_frame,
        funding.loc[
            (funding["ts"] >= cropped_frame.index.min()) & (funding["ts"] < end)
        ],
        cropped_signals,
        config,
    )
    return metrics_for_period(run, start=start, end=end), run


def evaluate_train_validation(
    kernel: Any,
    *,
    candidate_id: str,
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    features: pd.DataFrame,
    splits: dict[str, pd.Timestamp],
    selection: dict[str, Any],
) -> dict[str, Any]:
    config, _flags, signals = build_signals_for_selection(
        kernel,
        features,
        selection,
    )
    train, _ = evaluate_period(
        kernel,
        name=f"{candidate_id}_train",
        frame=frame,
        funding=funding,
        signals=signals,
        config=config,
        start=splits["train_start"],
        end=splits["validation_start"],
    )
    validation, _ = evaluate_period(
        kernel,
        name=f"{candidate_id}_validation",
        frame=frame,
        funding=funding,
        signals=signals,
        config=config,
        start=splits["validation_start"],
        end=splits["holdout_start"],
    )
    stress_config = replace(
        config,
        fee_multiplier=2.0,
        slippage_multiplier=2.0,
    )
    stress_train, _ = evaluate_period(
        kernel,
        name=f"{candidate_id}_stress_train",
        frame=frame,
        funding=funding,
        signals=signals,
        config=stress_config,
        start=splits["train_start"],
        end=splits["validation_start"],
    )
    stress_validation, _ = evaluate_period(
        kernel,
        name=f"{candidate_id}_stress_validation",
        frame=frame,
        funding=funding,
        signals=signals,
        config=stress_config,
        start=splits["validation_start"],
        end=splits["holdout_start"],
    )
    return {
        "candidate_id": candidate_id,
        "selection": selection,
        "train": train,
        "validation": validation,
        "stress_2x_train": stress_train,
        "stress_2x_validation": stress_validation,
    }


def buyhold_metrics(
    frame: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    close = frame.loc[(frame.index >= start) & (frame.index < end), "close"]
    if close.empty:
        raise RuntimeError("buy-and-hold evaluation period is empty")
    equity = close / float(close.iloc[0])
    drawdown = equity / equity.cummax() - 1.0
    return {
        "start": close.index.min().isoformat(),
        "end": close.index.max().isoformat(),
        "return_pct": float((equity.iloc[-1] - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
    }


def gate_without_neighbors(row: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    train = row["train"]
    validation = row["validation"]
    if train["return_pct"] <= 0.0:
        failures.append("train_return")
    if validation["return_pct"] <= 0.0:
        failures.append("validation_return")
    if abs(train["max_drawdown_pct"]) > 25.0:
        failures.append("train_mdd")
    if abs(validation["max_drawdown_pct"]) > 25.0:
        failures.append("validation_mdd")
    if train["trades"] < 24:
        failures.append("train_sample")
    if validation["trades"] < 12:
        failures.append("validation_sample")
    if train["profit_factor"] < 1.15:
        failures.append("train_pf")
    if validation["profit_factor"] < 1.05:
        failures.append("validation_pf")
    if row["stress_2x_train"]["return_pct"] <= 0.0:
        failures.append("stress_train_return")
    if row["stress_2x_validation"]["return_pct"] <= 0.0:
        failures.append("stress_validation_return")
    for split_name in ["train", "validation"]:
        metrics = row[split_name]
        if metrics["top_trade_positive_pnl_share"] > TOP_TRADE_SHARE_MAX:
            failures.append(f"{split_name}_top_trade_concentration")
        if metrics["top3_trade_positive_pnl_share"] > TOP3_TRADE_SHARE_MAX:
            failures.append(f"{split_name}_top3_trade_concentration")
    return not failures, failures


def failure_score(row: dict[str, Any]) -> float:
    train = row["train"]
    validation = row["validation"]
    penalties = [
        max(0.0, -train["return_pct"]) / 10.0,
        max(0.0, -validation["return_pct"]) / 10.0,
        max(0.0, abs(train["max_drawdown_pct"]) - 25.0) / 5.0,
        max(0.0, abs(validation["max_drawdown_pct"]) - 25.0) / 5.0,
        max(0.0, 24 - train["trades"]) / 6.0,
        max(0.0, 12 - validation["trades"]) / 3.0,
        max(0.0, 1.15 - train["profit_factor"]) * 10.0,
        max(0.0, 1.05 - validation["profit_factor"]) * 10.0,
        max(0.0, -row["stress_2x_train"]["return_pct"]) / 10.0,
        max(0.0, -row["stress_2x_validation"]["return_pct"]) / 10.0,
    ]
    return float(sum(penalties))


def flatten_candidate(row: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {
        "candidate_id": row["candidate_id"],
        "stage": row["selection"]["stage"],
        "seed_id": row["selection"].get("seed_id"),
        "ablation_id": row["selection"].get("ablation_id"),
        "stage2_step": row["selection"].get("stage2_step"),
        "component_type": row["selection"].get("component_type"),
        "added_component_type": row["selection"].get("added_component_type"),
        "parent_candidate_id": row["selection"].get("parent_candidate_id"),
        "neighbor_group": row["selection"].get("neighbor_group"),
        "components_json": json.dumps(
            row["selection"].get("components"),
            sort_keys=True,
        ),
        "parent_delta_json": json.dumps(
            row["selection"].get("parent_delta"),
            sort_keys=True,
        ),
        "config_changes_json": json.dumps(
            row["selection"]["config_changes"],
            sort_keys=True,
        ),
        "flags_json": json.dumps(row["selection"]["flags"], sort_keys=True),
        "overlay_json": json.dumps(
            row["selection"].get("overlay"),
            sort_keys=True,
        ),
        "train_seed_gate": row.get("train_seed_gate"),
        "gate_without_neighbors": row.get("gate_without_neighbors"),
        "neighbor_positive_ratio": row.get("neighbor_positive_ratio"),
        "gate_pass": row.get("gate_pass"),
        "gate_failures": "|".join(row.get("gate_failures", [])),
        "failure_score": row.get("failure_score"),
    }
    for split_name in [
        "train",
        "validation",
        "stress_2x_train",
        "stress_2x_validation",
    ]:
        for key, value in row[split_name].items():
            flat[f"{split_name}_{key}"] = value
    return flat


def selection_identity(row: dict[str, Any]) -> dict[str, Any]:
    selected = row["selection"]
    return {
        "candidate_id": row["candidate_id"],
        "stage": selected["stage"],
        "seed_id": selected.get("seed_id"),
        "ablation_id": selected.get("ablation_id"),
        "stage2_step": selected.get("stage2_step"),
        "component_type": selected.get("component_type"),
        "added_component_type": selected.get("added_component_type"),
        "parent_candidate_id": selected.get("parent_candidate_id"),
        "neighbor_group": selected.get("neighbor_group"),
        "components": selected.get("components"),
        "parent_delta": selected.get("parent_delta"),
        "config_changes": selected["config_changes"],
        "flags": selected["flags"],
        "overlay": selected.get("overlay"),
    }


def finite_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: finite_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [finite_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [finite_json_value(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else ("inf" if number > 0 else "-inf")
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value
