from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


EMA_PAIRS = ((8, 32), (16, 64), (32, 128), (64, 256))
EMA_WEIGHTS = (0.2, 0.3, 0.3, 0.2)
RECENT_WINDOWS = {
    "1d": pd.Timedelta(days=1),
    "7d": pd.Timedelta(days=7),
    "1m": pd.Timedelta(days=30),
    "3m": pd.Timedelta(days=90),
    "6m": pd.Timedelta(days=180),
    "1y": pd.Timedelta(days=365),
}


@dataclass(frozen=True, slots=True)
class ForecastConfig:
    ema_pairs: tuple[tuple[int, int], ...] = EMA_PAIRS
    weights: tuple[float, ...] = EMA_WEIGHTS
    volatility_span: int = 64
    calibration_window_slow_multiple: int = 4
    target_median_abs_forecast: float = 0.5
    max_abs_forecast: float = 1.0
    max_abs_position: float = 1.0
    fee_per_turnover: float = 0.001
    slippage_per_turnover: float = 0.0004

    def validate(self) -> None:
        if len(self.ema_pairs) != len(self.weights):
            raise ValueError("ema_pairs and weights must have equal length")
        if not math.isclose(sum(self.weights), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("weights must sum to one")
        if any(weight < 0.0 for weight in self.weights):
            raise ValueError("weights must be non-negative")
        if self.target_median_abs_forecast <= 0.0:
            raise ValueError("target_median_abs_forecast must be positive")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    name: str
    buffer: float
    metrics: dict[str, Any]
    slices: list[dict[str, Any]]
    path: pd.DataFrame


def timeframe_delta(timeframe: str) -> pd.Timedelta:
    if timeframe == "15m":
        return pd.Timedelta(minutes=15)
    if timeframe == "1h":
        return pd.Timedelta(hours=1)
    raise ValueError(f"unsupported timeframe: {timeframe}")


def periods_per_year(timeframe: str) -> int:
    if timeframe == "15m":
        return 365 * 24 * 4
    if timeframe == "1h":
        return 365 * 24
    raise ValueError(f"unsupported timeframe: {timeframe}")


def _load_partitions(root: Path, timeframe: str, *, normalized: bool) -> pd.DataFrame:
    layer = "normalized" if normalized else "raw"
    base = root / f"data/{layer}/ohlcv/exchange=binance/market_type=perp/timeframe={timeframe}"
    files = sorted(base.glob("date=*/symbol=hype_usdt_usdt.parquet"))
    if not files:
        raise FileNotFoundError(f"no HYPE {timeframe} {layer} partitions under {base}")
    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    key = "ts" if normalized or "ts" in frame.columns else "open_time"
    frame[key] = pd.to_datetime(frame[key], utc=True)
    return frame.sort_values(key).reset_index(drop=True)


def audit_and_load_market(root: Path, timeframe: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    normalized = _load_partitions(root, timeframe, normalized=True)
    raw = _load_partitions(root, timeframe, normalized=False)
    delta = timeframe_delta(timeframe)

    normalized["ts"] = pd.to_datetime(normalized["ts"], utc=True)
    raw_key = "ts" if "ts" in raw.columns else "open_time"
    raw[raw_key] = pd.to_datetime(raw[raw_key], utc=True)
    duplicate_normalized = int(normalized["ts"].duplicated().sum())
    duplicate_raw = int(raw[raw_key].duplicated().sum())
    normalized = normalized.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    raw = raw.drop_duplicates(raw_key, keep="last").sort_values(raw_key).reset_index(drop=True)

    expected = pd.date_range(normalized["ts"].iloc[0], normalized["ts"].iloc[-1], freq=delta)
    missing = expected.difference(pd.DatetimeIndex(normalized["ts"]))
    required = [
        "ts",
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
    missing_columns = sorted(set(required).difference(normalized.columns))
    if missing_columns:
        raise RuntimeError(f"normalized data missing columns: {missing_columns}")

    nulls = {column: int(normalized[column].isna().sum()) for column in required}
    invalid_ohlc = int(
        (
            (normalized[["open", "high", "low", "close"]] <= 0.0).any(axis=1)
            | normalized["high"].lt(normalized[["open", "close", "low"]].max(axis=1))
            | normalized["low"].gt(normalized[["open", "close", "high"]].min(axis=1))
        ).sum()
    )
    closed_violations = int((~normalized["is_closed"].astype(bool)).sum())
    source_values = sorted(str(value) for value in normalized["source"].dropna().unique())
    unknown_source = int(not source_values or any(value in {"", "unknown", "nan"} for value in source_values))

    compare = normalized[["ts", "open", "high", "low", "close", "volume", "quote_volume", "trade_count"]].merge(
        raw[[raw_key, "open", "high", "low", "close", "volume", "quote_volume", "trade_count"]],
        left_on="ts",
        right_on=raw_key,
        how="outer",
        suffixes=("_normalized", "_raw"),
        indicator=True,
    )
    unmatched = int(compare["_merge"].ne("both").sum())
    mismatch: dict[str, int] = {}
    both = compare.loc[compare["_merge"].eq("both")]
    for column in ("open", "high", "low", "close", "volume", "quote_volume", "trade_count"):
        left = pd.to_numeric(both[f"{column}_normalized"], errors="coerce").to_numpy("float64")
        right = pd.to_numeric(both[f"{column}_raw"], errors="coerce").to_numpy("float64")
        tolerance = 0.0 if column == "trade_count" else 1e-12
        mismatch[column] = int((~np.isclose(left, right, rtol=0.0, atol=tolerance)).sum())

    blocker_count = (
        len(missing)
        + duplicate_normalized
        + duplicate_raw
        + sum(nulls.values())
        + invalid_ohlc
        + closed_violations
        + unknown_source
        + unmatched
        + sum(mismatch.values())
    )
    quality = {
        "exchange": "binance",
        "market_type": "perp",
        "symbol": "HYPE/USDT:USDT",
        "timeframe": timeframe,
        "rows": int(len(normalized)),
        "first_ts": normalized["ts"].iloc[0].isoformat(),
        "last_ts": normalized["ts"].iloc[-1].isoformat(),
        "expected_rows": int(len(expected)),
        "missing_bars": int(len(missing)),
        "first_missing": missing[0].isoformat() if len(missing) else None,
        "duplicate_normalized": duplicate_normalized,
        "duplicate_raw": duplicate_raw,
        "critical_nulls": nulls,
        "invalid_ohlc_rows": invalid_ohlc,
        "non_closed_rows": closed_violations,
        "source_values": source_values,
        "raw_normalized_unmatched_rows": unmatched,
        "raw_normalized_mismatch": mismatch,
        "blocker_count": int(blocker_count),
    }
    if blocker_count:
        raise RuntimeError(f"HYPE {timeframe} data-quality blockers: {quality}")
    return normalized, quality


def load_and_audit_funding(root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = (
        root
        / "data/normalized/funding/exchange=binance/market_type=perp"
        / "symbol=hype_usdt_usdt/funding.parquet"
    )
    if not path.exists():
        raise FileNotFoundError(f"funding data not found: {path}")
    frame = pd.read_parquet(path)
    required = {"ts", "funding_rate"}
    missing_columns = sorted(required.difference(frame.columns))
    if missing_columns:
        raise RuntimeError(f"funding data missing columns: {missing_columns}")
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame["funding_rate"] = pd.to_numeric(frame["funding_rate"], errors="coerce")
    frame = frame.sort_values("ts").reset_index(drop=True)
    duplicate = int(frame["ts"].duplicated().sum())
    nulls = int(frame[["ts", "funding_rate"]].isna().any(axis=1).sum())
    gaps = frame["ts"].diff().dropna()
    max_gap_hours = float(gaps.max().total_seconds() / 3600.0) if len(gaps) else None
    blocker_count = duplicate + nulls + int(max_gap_hours is not None and max_gap_hours > 8.01)
    quality = {
        "rows": int(len(frame)),
        "first_ts": frame["ts"].iloc[0].isoformat(),
        "last_ts": frame["ts"].iloc[-1].isoformat(),
        "duplicate_ts": duplicate,
        "critical_null_rows": nulls,
        "max_gap_hours": max_gap_hours,
        "source_values": (
            sorted(str(value) for value in frame["source"].dropna().unique())
            if "source" in frame.columns
            else []
        ),
        "blocker_count": int(blocker_count),
    }
    if blocker_count:
        raise RuntimeError(f"HYPE funding data-quality blockers: {quality}")
    return frame[["ts", "funding_rate"]].copy(), quality


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def build_forecasts(market: pd.DataFrame, config: ForecastConfig) -> pd.DataFrame:
    config.validate()
    frame = market.copy().sort_values("ts").reset_index(drop=True)
    close = pd.to_numeric(frame["close"], errors="coerce")
    log_return = np.log(close / close.shift(1))
    volatility = log_return.ewm(
        span=config.volatility_span,
        adjust=False,
        min_periods=config.volatility_span,
    ).std(bias=False)
    frame["bar_volatility"] = volatility

    forecast_columns: list[str] = []
    for fast, slow in config.ema_pairs:
        fast_ema = ema(close, fast)
        slow_ema = ema(close, slow)
        spread = fast_ema / slow_ema.replace(0.0, np.nan) - 1.0
        raw = spread / volatility.replace(0.0, np.nan)
        calibration_window = config.calibration_window_slow_multiple * slow
        scale = (
            raw.abs()
            .rolling(calibration_window, min_periods=slow)
            .median()
            .shift(1)
        )
        denominator = scale / config.target_median_abs_forecast
        forecast = (raw / denominator.replace(0.0, np.nan)).clip(
            -config.max_abs_forecast,
            config.max_abs_forecast,
        )
        stem = f"{fast}_{slow}"
        frame[f"ema_fast_{stem}"] = fast_ema
        frame[f"ema_slow_{stem}"] = slow_ema
        frame[f"raw_forecast_{stem}"] = raw
        frame[f"calibration_scale_{stem}"] = scale
        frame[f"forecast_{stem}"] = forecast
        forecast_columns.append(f"forecast_{stem}")

    forecasts = frame[forecast_columns]
    frame["forecast"] = forecasts.mul(np.asarray(config.weights), axis=1).sum(axis=1, min_count=len(forecast_columns))
    frame["forecast"] = frame["forecast"].clip(-config.max_abs_forecast, config.max_abs_forecast)
    return frame


def apply_position_buffer(desired: pd.Series, buffer: float, max_abs_position: float) -> pd.Series:
    if buffer < 0.0:
        raise ValueError("buffer must be non-negative")
    output = np.zeros(len(desired), dtype="float64")
    current = 0.0
    values = desired.to_numpy("float64")
    for index, value in enumerate(values):
        if not np.isfinite(value):
            target = 0.0
        else:
            target = float(np.clip(value, -max_abs_position, max_abs_position))
        if abs(target - current) + 1e-15 >= buffer:
            current = target
        output[index] = current
    return pd.Series(output, index=desired.index, name="position")


def _funding_by_open_interval(
    opens: pd.Series,
    funding: pd.DataFrame,
) -> np.ndarray:
    open_ns = pd.to_datetime(opens, utc=True).astype("int64").to_numpy()
    funding_ns = pd.to_datetime(funding["ts"], utc=True).astype("int64").to_numpy()
    rates = funding["funding_rate"].to_numpy("float64")
    interval_rates = np.zeros(len(opens), dtype="float64")
    if not len(funding_ns):
        return interval_rates
    for index in range(1, len(opens)):
        left = np.searchsorted(funding_ns, open_ns[index - 1], side="right")
        right = np.searchsorted(funding_ns, open_ns[index], side="right")
        if right > left:
            interval_rates[index] = float(rates[left:right].sum())
    return interval_rates


def backtest_target(
    market: pd.DataFrame,
    funding: pd.DataFrame,
    desired_close: pd.Series,
    *,
    name: str,
    timeframe: str,
    buffer: float,
    config: ForecastConfig,
    start_index: int,
) -> BacktestResult:
    if start_index < 1 or start_index >= len(market):
        raise ValueError("start_index must leave at least one prior signal bar")
    frame = market.loc[start_index:].copy().reset_index(drop=True)
    desired = desired_close.shift(1).loc[start_index:].reset_index(drop=True)
    position = apply_position_buffer(desired, buffer, config.max_abs_position)
    open_price = pd.to_numeric(frame["open"], errors="coerce").to_numpy("float64")
    timestamps = pd.to_datetime(frame["ts"], utc=True).reset_index(drop=True)
    interval_funding = _funding_by_open_interval(timestamps, funding)
    cost_rate = config.fee_per_turnover + config.slippage_per_turnover

    gross_equity = 1.0
    net_equity = 1.0
    previous_position = 0.0
    previous_open = float(open_price[0])
    rows: list[dict[str, Any]] = []
    total_cost_amount = 0.0
    total_funding_amount = 0.0

    for index in range(len(frame)):
        price = float(open_price[index])
        market_return = 0.0
        funding_amount = 0.0
        if index > 0:
            market_return = price / previous_open - 1.0
            gross_equity *= 1.0 + previous_position * market_return
            net_equity *= 1.0 + previous_position * market_return
            funding_amount = net_equity * previous_position * interval_funding[index]
            net_equity -= funding_amount
            total_funding_amount += funding_amount

        target = float(position.iloc[index])
        turnover = abs(target - previous_position)
        cost_amount = net_equity * turnover * cost_rate
        net_equity -= cost_amount
        total_cost_amount += cost_amount
        rows.append(
            {
                "ts": timestamps.iloc[index],
                "open": price,
                "desired_position": float(desired.iloc[index]) if np.isfinite(desired.iloc[index]) else 0.0,
                "position": target,
                "turnover": turnover,
                "market_return": market_return,
                "funding_rate_interval": float(interval_funding[index]),
                "cost_amount": cost_amount,
                "funding_amount": funding_amount,
                "equity_gross": gross_equity,
                "equity_net": net_equity,
            }
        )
        previous_position = target
        previous_open = price

    path = pd.DataFrame(rows)
    metrics = compute_metrics(
        path,
        timeframe=timeframe,
        total_cost_amount=total_cost_amount,
        total_funding_amount=total_funding_amount,
    )
    slices = compute_slices(path, timeframe=timeframe)
    return BacktestResult(name=name, buffer=buffer, metrics=metrics, slices=slices, path=path)


def compute_metrics(
    path: pd.DataFrame,
    *,
    timeframe: str,
    total_cost_amount: float,
    total_funding_amount: float,
) -> dict[str, Any]:
    net = path["equity_net"].astype("float64")
    gross = path["equity_gross"].astype("float64")
    returns = net.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    drawdown = net / net.cummax() - 1.0
    years = max(
        (pd.Timestamp(path["ts"].iloc[-1]) - pd.Timestamp(path["ts"].iloc[0])).total_seconds()
        / (365.25 * 24 * 3600),
        1.0 / periods_per_year(timeframe),
    )
    net_return = float(net.iloc[-1] - 1.0)
    gross_return = float(gross.iloc[-1] - 1.0)
    annual_return = float(net.iloc[-1] ** (1.0 / years) - 1.0) if net.iloc[-1] > 0.0 else -1.0
    standard_deviation = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    sharpe = (
        float(returns.mean() / standard_deviation * math.sqrt(periods_per_year(timeframe)))
        if standard_deviation > 0.0
        else 0.0
    )
    max_drawdown = float(drawdown.min())
    calmar = annual_return / abs(max_drawdown) if max_drawdown < 0.0 else math.nan
    position = path["position"].to_numpy("float64")
    prior = np.r_[0.0, position[:-1]]
    sign_flips = int(((position * prior) < 0.0).sum())
    directional_entries = int(((position != 0.0) & (prior == 0.0)).sum() + sign_flips)
    days = max(
        (pd.Timestamp(path["ts"].iloc[-1]) - pd.Timestamp(path["ts"].iloc[0])).total_seconds() / 86400.0,
        1.0 / 24.0,
    )
    return {
        "start_ts": pd.Timestamp(path["ts"].iloc[0]).isoformat(),
        "end_ts": pd.Timestamp(path["ts"].iloc[-1]).isoformat(),
        "bars": int(len(path)),
        "gross_return_pct": gross_return * 100.0,
        "net_return_pct": net_return * 100.0,
        "cagr_net_pct": annual_return * 100.0,
        "max_drawdown_net_pct": max_drawdown * 100.0,
        "sharpe_net": sharpe,
        "calmar_net": calmar,
        "average_abs_position": float(np.abs(position).mean()),
        "max_abs_position": float(np.abs(position).max()),
        "time_in_market_pct": float((np.abs(position) > 1e-12).mean() * 100.0),
        "total_turnover": float(path["turnover"].sum()),
        "annualized_turnover": float(path["turnover"].sum() * 365.25 / days),
        "rebalance_count": int((path["turnover"] > 1e-12).sum()),
        "directional_entries": directional_entries,
        "sign_flips": sign_flips,
        "trading_cost_pct_initial_equity": total_cost_amount * 100.0,
        "funding_paid_pct_initial_equity": total_funding_amount * 100.0,
    }


def compute_slices(path: pd.DataFrame, *, timeframe: str) -> list[dict[str, Any]]:
    end = pd.Timestamp(path["ts"].iloc[-1])
    rows: list[dict[str, Any]] = []
    for label, delta in RECENT_WINDOWS.items():
        sliced = path.loc[pd.to_datetime(path["ts"], utc=True) >= end - delta].copy()
        if len(sliced) < 2:
            continue
        normalized = sliced["equity_net"] / float(sliced["equity_net"].iloc[0])
        returns = normalized.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        drawdown = normalized / normalized.cummax() - 1.0
        standard_deviation = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
        sharpe = (
            float(returns.mean() / standard_deviation * math.sqrt(periods_per_year(timeframe)))
            if standard_deviation > 0.0
            else 0.0
        )
        rows.append(
            {
                "window": label,
                "start_ts": pd.Timestamp(sliced["ts"].iloc[0]).isoformat(),
                "end_ts": pd.Timestamp(sliced["ts"].iloc[-1]).isoformat(),
                "return_pct": float((normalized.iloc[-1] - 1.0) * 100.0),
                "max_drawdown_pct": float(drawdown.min() * 100.0),
                "sharpe": sharpe,
                "turnover": float(sliced["turnover"].sum()),
                "rebalance_count": int((sliced["turnover"] > 1e-12).sum()),
                "average_abs_position": float(sliced["position"].abs().mean()),
            }
        )
    return rows


def run_suite(
    root: Path,
    *,
    timeframe: str,
    config: ForecastConfig | None = None,
    buffers: tuple[float, ...] = (0.0, 0.1),
) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    cfg = config or ForecastConfig()
    cfg.validate()
    market, market_quality = audit_and_load_market(root, timeframe)
    funding, funding_quality = load_and_audit_funding(root)
    features = build_forecasts(market, cfg)
    forecast_columns = [f"forecast_{fast}_{slow}" for fast, slow in cfg.ema_pairs]
    valid = features[["forecast", *forecast_columns]].notna().all(axis=1)
    valid_indices = np.flatnonzero(valid.to_numpy())
    if not len(valid_indices):
        raise RuntimeError("forecast calibration produced no fully valid rows")
    first_signal_index = int(valid_indices[0])
    start_index = first_signal_index + 1
    if start_index >= len(features):
        raise RuntimeError("no bar available after first valid forecast")

    results: list[BacktestResult] = []
    for buffer in buffers:
        results.append(
            backtest_target(
                features,
                funding,
                features["forecast"],
                name=f"ensemble_buffer_{buffer:.2f}",
                timeframe=timeframe,
                buffer=buffer,
                config=cfg,
                start_index=start_index,
            )
        )
    for fast, slow in cfg.ema_pairs:
        results.append(
            backtest_target(
                features,
                funding,
                features[f"forecast_{fast}_{slow}"],
                name=f"sleeve_{fast}_{slow}",
                timeframe=timeframe,
                buffer=0.0,
                config=cfg,
                start_index=start_index,
            )
        )
    buy_hold_signal = pd.Series(1.0, index=features.index)
    results.append(
        backtest_target(
            features,
            funding,
            buy_hold_signal,
            name="perpetual_buy_hold_1x",
            timeframe=timeframe,
            buffer=0.0,
            config=cfg,
            start_index=start_index,
        )
    )

    payload = {
        "strategy_family_mechanism": "multi-horizon volatility-normalized EMA forecast fusion",
        "market": "Binance USD-M Futures",
        "symbol": "HYPEUSDT",
        "display_symbol": "HYPE/USDT:USDT",
        "timeframe": timeframe,
        "status": "explore / not promoted / not live-ready",
        "data_quality": market_quality,
        "funding_quality": funding_quality,
        "config": {
            **asdict(cfg),
            "ema_pairs": [list(pair) for pair in cfg.ema_pairs],
            "weights": list(cfg.weights),
            "buffers": list(buffers),
            "execution": "closed bar forecast at t; target position executed at t+1 open",
            "funding_ordering": "funding in (previous open, current open] is charged to the previously held position before rebalance",
            "end_of_sample": "open position is marked at the final open and is not forcibly liquidated",
        },
        "forecast_start_ts": pd.Timestamp(features["ts"].iloc[first_signal_index]).isoformat(),
        "backtest_start_ts": pd.Timestamp(features["ts"].iloc[start_index]).isoformat(),
        "results": [
            {
                "name": result.name,
                "buffer": result.buffer,
                "metrics": result.metrics,
                "slices": result.slices,
            }
            for result in results
        ],
    }
    paths = {result.name: result.path for result in results}
    feature_columns = [
        "ts",
        "open",
        "high",
        "low",
        "close",
        "bar_volatility",
        *forecast_columns,
        "forecast",
    ]
    paths["forecasts"] = features.loc[start_index:, feature_columns].reset_index(drop=True)
    return payload, paths


def write_suite_outputs(
    *,
    family_dir: Path,
    artifact_stem: str,
    payload: dict[str, Any],
    paths: dict[str, pd.DataFrame],
) -> dict[str, str]:
    artifact_dir = family_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary_path = artifact_dir / f"{artifact_stem}-summary.json"
    forecast_path = artifact_dir / f"{artifact_stem}-forecasts.csv"
    path_file = artifact_dir / f"{artifact_stem}-paths.csv"
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    paths["forecasts"].to_csv(forecast_path, index=False)
    combined = pd.concat(
        [frame.assign(run=name) for name, frame in paths.items() if name != "forecasts"],
        ignore_index=True,
    )
    combined.to_csv(path_file, index=False)
    return {
        "summary": str(summary_path),
        "forecasts": str(forecast_path),
        "paths": str(path_file),
    }


def _number(value: object, digits: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not np.isfinite(number):
        return "n/a"
    return f"{number:.{digits}f}"


def _pct(value: object, digits: int = 2) -> str:
    number = _number(value, digits)
    return "n/a" if number == "n/a" else f"{number}%"


def render_markdown_report(
    *,
    payload: dict[str, Any],
    family_name: str,
    family_alias: str,
    artifact_stem: str,
    kernel_sha256: str,
    run_date: str,
) -> str:
    results = {str(item["name"]): item for item in payload["results"]}
    exact = results["ensemble_buffer_0.00"]
    buffered = results["ensemble_buffer_0.10"]
    buy_hold = results["perpetual_buy_hold_1x"]
    timeframe = str(payload["timeframe"])
    quality = payload["data_quality"]
    funding_quality = payload["funding_quality"]

    headline_rows: list[str] = []
    order = [
        "ensemble_buffer_0.00",
        "ensemble_buffer_0.10",
        "sleeve_8_32",
        "sleeve_16_64",
        "sleeve_32_128",
        "sleeve_64_256",
        "perpetual_buy_hold_1x",
    ]
    for name in order:
        metrics = results[name]["metrics"]
        headline_rows.append(
            "| `{name}` | {gross} | {net} | {mdd} | {sharpe} | {avg_pos} | {turnover} | {cost} |".format(
                name=name,
                gross=_pct(metrics["gross_return_pct"]),
                net=_pct(metrics["net_return_pct"]),
                mdd=_pct(metrics["max_drawdown_net_pct"]),
                sharpe=_number(metrics["sharpe_net"]),
                avg_pos=_number(metrics["average_abs_position"], 3),
                turnover=_number(metrics["total_turnover"], 1),
                cost=_pct(metrics["trading_cost_pct_initial_equity"]),
            )
        )

    slice_rows: list[str] = []
    exact_slices = {str(item["window"]): item for item in exact["slices"]}
    buffered_slices = {str(item["window"]): item for item in buffered["slices"]}
    for label in RECENT_WINDOWS:
        if label not in exact_slices or label not in buffered_slices:
            continue
        exact_slice = exact_slices[label]
        buffered_slice = buffered_slices[label]
        slice_rows.append(
            "| `{label}` | {exact_ret} | {exact_dd} | {buffer_ret} | {buffer_dd} | {buffer_turnover} |".format(
                label=label,
                exact_ret=_pct(exact_slice["return_pct"]),
                exact_dd=_pct(exact_slice["max_drawdown_pct"]),
                buffer_ret=_pct(buffered_slice["return_pct"]),
                buffer_dd=_pct(buffered_slice["max_drawdown_pct"]),
                buffer_turnover=_number(buffered_slice["turnover"], 1),
            )
        )

    exact_metrics = exact["metrics"]
    buffered_metrics = buffered["metrics"]
    buy_hold_metrics = buy_hold["metrics"]
    conclusion = (
        f"`{family_name}` 在本次未调参基线上未形成可用 alpha。"
        f"精确调仓净收益为 `{_pct(exact_metrics['net_return_pct'])}`，"
        f"固定 `0.10` 缓冲后为 `{_pct(buffered_metrics['net_return_pct'])}`，"
        f"同期 1x 永续买入持有为 `{_pct(buy_hold_metrics['net_return_pct'])}`。"
        f"缓冲降低了换手，但组合毛收益仍为 `{_pct(buffered_metrics['gross_return_pct'])}`，"
        "因此问题不只是手续费：这组 EMA 参数在该周期上的方向预测本身也没有足够优势。"
    )
    return "\n".join(
        [
            f"# {family_name} 多周期 EMA Forecast 基线回测（{run_date}）",
            "",
            f"- Family：`{family_name}`（`{family_alias}`）",
            "- 状态：`explore / not promoted / not live-ready`",
            f"- 市场：Binance USD-M Futures `HYPEUSDT` perpetual，`{timeframe}`",
            f"- 数据区间：`{quality['first_ts']}` → `{quality['last_ts']}`；回测从首个完整 forecast 后的 `{payload['backtest_start_ts']}` 开始",
            "- 成本：每单位换手手续费 `0.001` + adverse slippage `0.0004`；纳入实际 Binance funding",
            "- 切片用途：仅作事后审计，不用于参数选择",
            "",
            "## 结论",
            "",
            conclusion,
            "",
            "当前结果不应登记版本，也不应进入 promotion gate。若继续研究，优先检查更低频调仓、forecast 持有/滞后结构或更长 EMA 参数，而不是在本基线上加杠杆。",
            "",
            "## 策略定义",
            "",
            "- 四条 EMA：`8/32`、`16/64`、`32/128`、`64/256`；权重依次为 `0.2/0.3/0.3/0.2`。",
            "- EMA：`close.ewm(span=N, adjust=False, min_periods=N).mean()`。",
            "- 每条 raw forecast：`(EMA_fast / EMA_slow - 1) / EWMAStd(log_return, span=64)`。",
            "- 因果校准：用该 raw forecast 过去 `4 × slow` 根的绝对值滚动中位数（至少 `slow` 个有效值，并 `shift(1)`）把历史中位绝对 forecast 对齐到 `0.5`，再裁剪到 `[-1, 1]`。",
            "- 最终 forecast：四条 forecast 加权求和并裁剪到 `[-1,1]`；目标仓位直接等于 forecast，最大绝对仓位 `1x`。",
            "- 当前闭合 K 收盘计算 forecast，下一根 K 开盘调整仓位；按 `abs(target - current)` 收取换手成本。",
            "- `ensemble_buffer_0.10` 只有当目标仓位与当前仓位相差至少 `0.10` 才调仓；其余逻辑不变。",
            "- 无固定止盈、止损、timeout 或额外过滤；样本末按最后一根开盘 mark，不强制平仓。",
            "",
            "## 全区间结果",
            "",
            "| 运行 | 毛收益 | 净收益 | 最大回撤 | Sharpe | 平均绝对仓位 | 总换手 | 成本/初始权益 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *headline_rows,
            "",
            "## 最近区间",
            "",
            "| 窗口 | 精确调仓收益 | 精确调仓回撤 | 0.10 缓冲收益 | 0.10 缓冲回撤 | 缓冲换手 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
            *slice_rows,
            "",
            "## 数据质量与执行审计",
            "",
            f"- 标准数据湖 normalized rows：`{quality['rows']}`，expected `{quality['expected_rows']}`，missing `{quality['missing_bars']}`，blocker `{quality['blocker_count']}`。",
            f"- Raw/normalized unmatched：`{quality['raw_normalized_unmatched_rows']}`；字段 mismatch：`{sum(quality['raw_normalized_mismatch'].values())}`。",
            f"- Funding：`{funding_quality['rows']}` 条，`{funding_quality['first_ts']}` → `{funding_quality['last_ts']}`，最大间隔 `{_number(funding_quality['max_gap_hours'], 1)}h`，blocker `{funding_quality['blocker_count']}`。",
            "- 正 funding 由多头支付、空头收取；`(previous open, current open]` 的 funding 在当前开盘调仓前按上一持仓结算。",
            "- 连续目标仓位会产生频繁小额订单；本回测未模拟最小名义、数量步长和拒单，因此即使收益转正也仍非 live-ready。",
            "",
            "## 证据",
            "",
            f"- Summary：[../artifacts/{artifact_stem}-summary.json](../artifacts/{artifact_stem}-summary.json)",
            f"- Forecast path：[../artifacts/{artifact_stem}-forecasts.csv](../artifacts/{artifact_stem}-forecasts.csv)",
            f"- Equity / turnover paths：[../artifacts/{artifact_stem}-paths.csv](../artifacts/{artifact_stem}-paths.csv)",
            f"- 共享内核：[../../../_shared-kernels/multi-horizon-ema-forecast/v1/engine.py](../../../_shared-kernels/multi-horizon-ema-forecast/v1/engine.py)，SHA256 `{kernel_sha256}`",
            "",
            "## 后续状态",
            "",
            "`explore / not promoted / not live-ready`。本轮只回答“这组多周期 EMA forecast 在 HYPE 上表现如何”，不构成版本登记、live spec 或 runner handoff。",
            "",
        ]
    )
