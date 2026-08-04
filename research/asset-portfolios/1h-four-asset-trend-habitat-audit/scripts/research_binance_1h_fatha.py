from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse
from strategy_lab.data.settings import load_settings


ROOT = Path("research/asset-portfolios/1h-four-asset-trend-habitat-audit")
ARTIFACT_DIR = ROOT / "artifacts"
DATA_SCRIPT = Path(
    "research/hype/15m-multidimensional-trend-pyramiding/scripts/"
    "research_hype_15m_mdtp.py"
)
RUN_DATE = "2026-08-03"
SYMBOLS = {
    "HYPE": "HYPE/USDT:USDT",
    "BTC": "BTC/USDT:USDT",
    "ETH": "ETH/USDT:USDT",
    "SOL": "SOL/USDT:USDT",
}
HORIZONS = (72, 168, 336)
DELAYS = (4, 12, 24)
PAST_VOL_HOURS = 720
PAST_FAST_HOURS = 168
PAST_SLOW_HOURS = 672
FEE_RATE = 0.001
SLIPPAGE = 0.0004
ROUNDTRIP_HURDLE = 2.0 * (FEE_RATE + SLIPPAGE)
STRONG_SCALED_AMPLITUDE = 1.5
STRONG_DAILY_EFFICIENCY = 0.35
EFFICIENCY_LADDER = (0.25, 0.40, 0.60)
BOOTSTRAP_SAMPLES = 5_000
BLOCK_DAYS = 14
EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class AssetData:
    asset: str
    symbol: str
    hourly: pd.DataFrame
    quality: dict[str, Any]


def load_data_module() -> Any:
    spec = importlib.util.spec_from_file_location("binance_fatha_data", DATA_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load data module: {DATA_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_complete_hourly(
    frame: pd.DataFrame, funding: pd.Series
) -> tuple[pd.DataFrame, dict[str, Any]]:
    grouped = frame.resample("1h", label="left", closed="left")
    hourly = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        source_bars=("close", "count"),
    )
    incomplete = hourly.loc[hourly["source_bars"].ne(4)]
    hourly = hourly.loc[hourly["source_bars"].eq(4)].copy()
    expected = pd.date_range(
        hourly.index.min(), hourly.index.max(), freq="1h", tz="UTC"
    )
    missing = expected.difference(hourly.index)
    invalid = hourly["high"].lt(
        hourly[["open", "close", "low"]].max(axis=1)
    ) | hourly["low"].gt(hourly[["open", "close", "high"]].min(axis=1))
    funding_hourly = funding.resample("1h", label="left", closed="left").sum()
    hourly["funding_rate"] = funding_hourly.reindex(hourly.index).fillna(0.0)
    hourly.index = hourly.index + pd.Timedelta(hours=1)
    quality = {
        "rows": int(len(hourly)),
        "visible_start": hourly.index.min().isoformat(),
        "visible_end": hourly.index.max().isoformat(),
        "incomplete_source_hours_excluded": int(len(incomplete)),
        "missing_complete_hours": int(len(missing)),
        "invalid_ohlc_rows": int(invalid.sum()),
        "non_zero_funding_hours": int(hourly["funding_rate"].ne(0.0).sum()),
        "accepted": bool(len(missing) == 0 and not invalid.any()),
        "availability": "hour-open index shifted +1h to earliest visible close time",
    }
    if not quality["accepted"]:
        raise RuntimeError(f"hourly quality blocker: {quality}")
    return hourly, quality


def load_assets() -> dict[str, AssetData]:
    module = load_data_module()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    assets: dict[str, AssetData] = {}
    for asset, symbol in SYMBOLS.items():
        frame, funding, source_quality = module.load_symbol_data(
            warehouse, symbol, require_raw_parity=True
        )
        hourly, hourly_quality = build_complete_hourly(frame, funding)
        assets[asset] = AssetData(
            asset=asset,
            symbol=symbol,
            hourly=hourly,
            quality={"source": source_quality, "hourly": hourly_quality},
        )
    return assets


def trend_efficiency(values: np.ndarray) -> float:
    if len(values) < 2 or not np.isfinite(values).all():
        return math.nan
    path = float(np.abs(np.diff(values)).sum())
    return 0.0 if path <= EPSILON else float(abs(values[-1] - values[0]) / path)


def first_passage(progress: np.ndarray, r_value: float) -> str:
    if not np.isfinite(r_value) or r_value <= EPSILON:
        return "none"
    favorable = np.flatnonzero(progress >= r_value)
    adverse = np.flatnonzero(progress <= -r_value)
    if favorable.size and (not adverse.size or favorable[0] < adverse[0]):
        return "favorable"
    if adverse.size and (not favorable.size or adverse[0] < favorable[0]):
        return "adverse"
    if favorable.size and adverse.size and favorable[0] == adverse[0]:
        return "same_hour_ambiguous"
    return "none"


def path_diagnostics(
    log_path: np.ndarray,
    side: int,
    r_value: float,
    horizon: int,
) -> dict[str, Any]:
    progress = side * (log_path[1:] - log_path[0])
    running_peak = np.maximum.accumulate(np.r_[0.0, progress])[1:]
    mfe = max(0.0, float(progress.max()))
    mae = max(0.0, float((-progress).max()))
    drawdown = running_peak - progress
    required_giveback = (
        float(drawdown.max() / mfe) if mfe > EPSILON else math.nan
    )
    eligible = running_peak >= 2.0 * r_value
    half_trigger = bool(np.any(eligible & (progress < 0.5 * running_peak)))
    result: dict[str, Any] = {
        "mfe_r": mfe / max(r_value, EPSILON),
        "mae_r": mae / max(r_value, EPSILON),
        "first_passage": first_passage(progress, r_value),
        "required_giveback_share": required_giveback,
        "terminal_mfe_retention": (
            float(progress[-1] / mfe) if mfe > EPSILON else math.nan
        ),
        "half_mfe_triggered_after_2r": half_trigger,
    }
    final_move = abs(float(log_path[-1] - log_path[0]))
    for delay in DELAYS:
        if delay > horizon:
            continue
        remaining = float(side * (log_path[-1] - log_path[delay]))
        result[f"delay_{delay}h_remaining"] = remaining
        result[f"delay_{delay}h_capture_ratio"] = (
            remaining / final_move if final_move > EPSILON else math.nan
        )
        result[f"delay_{delay}h_cost_positive"] = bool(
            remaining > ROUNDTRIP_HURDLE
        )
    return result


def build_anchor_paths(asset_data: AssetData) -> pd.DataFrame:
    hourly = asset_data.hourly
    log_price = np.log(hourly["close"].to_numpy(float))
    funding = hourly["funding_rate"].to_numpy(float)
    hourly_step = np.diff(log_price, prepend=np.nan)
    past_rms = (
        pd.Series(hourly_step, index=hourly.index)
        .rolling(PAST_VOL_HOURS, min_periods=PAST_VOL_HOURS)
        .apply(lambda values: float(np.sqrt(np.mean(np.square(values)))), raw=True)
        .to_numpy(float)
    )
    positions = np.flatnonzero(hourly.index.hour == 0)
    rows: list[dict[str, Any]] = []
    for position in positions:
        if position < max(PAST_VOL_HOURS, PAST_SLOW_HOURS):
            continue
        past_fast = log_price[position] - log_price[position - PAST_FAST_HOURS]
        past_slow = log_price[position] - log_price[position - PAST_SLOW_HOURS]
        admission_side = (
            1
            if past_fast > 0.0 and past_slow > 0.0
            else -1
            if past_fast < 0.0 and past_slow < 0.0
            else 0
        )
        rms = float(past_rms[position])
        if not np.isfinite(rms) or rms <= EPSILON:
            continue
        r_value = rms * math.sqrt(24.0)
        for horizon in HORIZONS:
            if position + horizon >= len(hourly):
                continue
            path = log_price[position : position + horizon + 1]
            final_return = float(path[-1] - path[0])
            if abs(final_return) <= EPSILON:
                continue
            ex_post_side = 1 if final_return > 0.0 else -1
            scale = rms * math.sqrt(horizon)
            daily_path = path[::24]
            row: dict[str, Any] = {
                "asset": asset_data.asset,
                "symbol": asset_data.symbol,
                "anchor": hourly.index[position],
                "horizon_hours": horizon,
                "horizon_days": horizon // 24,
                "ex_post_side": ex_post_side,
                "ex_post_direction": "long" if ex_post_side > 0 else "short",
                "final_log_return": final_return,
                "amplitude": abs(final_return),
                "scaled_amplitude": abs(final_return) / scale,
                "hourly_efficiency": trend_efficiency(path),
                "daily_efficiency": trend_efficiency(daily_path),
                "past_hourly_rms": rms,
                "r_1d": r_value,
                "past_7d_return": past_fast,
                "past_28d_return": past_slow,
                "admission_side": admission_side,
                "admission_direction": (
                    "long" if admission_side > 0 else "short" if admission_side < 0 else "flat"
                ),
            }
            row.update(path_diagnostics(path, ex_post_side, r_value, horizon))
            row["strong_trend"] = bool(
                row["scaled_amplitude"] >= STRONG_SCALED_AMPLITUDE
                and row["daily_efficiency"] >= STRONG_DAILY_EFFICIENCY
            )
            for threshold in EFFICIENCY_LADDER:
                row[f"daily_efficiency_ge_{int(threshold * 100)}"] = bool(
                    row["daily_efficiency"] >= threshold
                )

            future_funding = float(funding[position + 1 : position + horizon + 1].sum())
            row["future_funding_sum"] = future_funding
            for delay in DELAYS:
                early_move = float(path[delay] - path[0])
                early_side = 1 if early_move > 0.0 else -1 if early_move < 0.0 else 0
                remaining_path = early_side * (path[delay + 1 :] - path[delay])
                remaining_return = float(early_side * (path[-1] - path[delay]))
                remaining_funding = float(
                    funding[position + delay + 1 : position + horizon + 1].sum()
                )
                row[f"onset_{delay}h_side"] = early_side
                row[f"onset_{delay}h_scaled_move"] = abs(early_move) / (
                    rms * math.sqrt(delay)
                )
                row[f"onset_{delay}h_efficiency"] = trend_efficiency(
                    path[: delay + 1]
                )
                row[f"onset_{delay}h_remaining_return"] = remaining_return
                row[f"onset_{delay}h_continuation"] = bool(remaining_return > 0.0)
                row[f"onset_{delay}h_net"] = (
                    remaining_return
                    - ROUNDTRIP_HURDLE
                    - early_side * remaining_funding
                )
                row[f"onset_{delay}h_net_positive"] = bool(
                    row[f"onset_{delay}h_net"] > 0.0
                )
                row[f"onset_{delay}h_mfe_r"] = max(
                    0.0, float(remaining_path.max())
                ) / r_value
                row[f"onset_{delay}h_mae_r"] = max(
                    0.0, float((-remaining_path).max())
                ) / r_value
                row[f"onset_{delay}h_first_passage"] = first_passage(
                    remaining_path, r_value
                )
            for side, name in ((1, "long"), (-1, "short")):
                signed_path = side * (path[1:] - path[0])
                signed_return = side * final_return
                row[f"unconditional_{name}_signed_return"] = signed_return
                row[f"unconditional_{name}_net"] = (
                    signed_return - ROUNDTRIP_HURDLE - side * future_funding
                )
                row[f"unconditional_{name}_mfe_r"] = max(
                    0.0, float(signed_path.max())
                ) / r_value
                row[f"unconditional_{name}_mae_r"] = max(
                    0.0, float((-signed_path).max())
                ) / r_value
                row[f"unconditional_{name}_first_passage"] = first_passage(
                    signed_path, r_value
                )

            if admission_side != 0:
                admission_name = "long" if admission_side > 0 else "short"
                row["admission_signed_return"] = row[
                    f"unconditional_{admission_name}_signed_return"
                ]
                row["admission_scaled_return"] = (
                    row["admission_signed_return"] / scale
                )
                row["admission_net"] = row[f"unconditional_{admission_name}_net"]
                row["admission_mfe_r"] = row[
                    f"unconditional_{admission_name}_mfe_r"
                ]
                row["admission_mae_r"] = row[
                    f"unconditional_{admission_name}_mae_r"
                ]
                row["admission_first_passage"] = row[
                    f"unconditional_{admission_name}_first_passage"
                ]
                row["admission_continuation"] = bool(
                    row["admission_signed_return"] > 0.0
                )
                row["admission_net_positive"] = bool(row["admission_net"] > 0.0)
                row["admission_net_zero_if_flat"] = row["admission_net"]
            else:
                row["admission_signed_return"] = math.nan
                row["admission_scaled_return"] = math.nan
                row["admission_net"] = math.nan
                row["admission_mfe_r"] = math.nan
                row["admission_mae_r"] = math.nan
                row["admission_first_passage"] = "flat"
                row["admission_continuation"] = math.nan
                row["admission_net_positive"] = math.nan
                row["admission_net_zero_if_flat"] = 0.0

            for delay in DELAYS:
                remaining = float(row[f"delay_{delay}h_remaining"])
                row[f"delay_{delay}h_remaining_scaled"] = remaining / scale
            rows.append(row)
    result = pd.DataFrame(rows)
    if not result.empty:
        result["anchor"] = pd.to_datetime(result["anchor"], utc=True)
    return result


def _safe_rate(series: pd.Series, predicate: Any | None = None) -> float:
    values = series.dropna()
    if values.empty:
        return math.nan
    if predicate is None:
        return float(values.astype(float).mean())
    return float(predicate(values).mean())


def summarize_habitat(paths: pd.DataFrame, scope: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (asset, horizon), base in paths.groupby(["asset", "horizon_hours"]):
        for side_name, group in (
            ("all", base),
            ("long", base.loc[base["ex_post_side"].eq(1)]),
            ("short", base.loc[base["ex_post_side"].eq(-1)]),
        ):
            if group.empty:
                continue
            strong = group.loc[group["strong_trend"]]
            row = {
                "scope": scope,
                "asset": asset,
                "horizon_hours": int(horizon),
                "horizon_days": int(horizon // 24),
                "side": side_name,
                "anchors": int(len(group)),
                "independent_14d_blocks": int(
                    ((group["anchor"].max() - group["anchor"].min()).days // BLOCK_DAYS)
                    + 1
                ),
                "median_amplitude": float(group["amplitude"].median()),
                "median_scaled_amplitude": float(group["scaled_amplitude"].median()),
                "median_hourly_efficiency": float(group["hourly_efficiency"].median()),
                "median_daily_efficiency": float(group["daily_efficiency"].median()),
                "strong_trend_rate": float(group["strong_trend"].mean()),
                "favorable_first_passage_rate": float(
                    group["first_passage"].eq("favorable").mean()
                ),
                "median_mfe_r": float(group["mfe_r"].median()),
                "median_mae_r": float(group["mae_r"].median()),
                "median_required_giveback_share": float(
                    group["required_giveback_share"].median()
                ),
                "half_mfe_trigger_rate_after_2r": float(
                    group["half_mfe_triggered_after_2r"].mean()
                ),
                "median_terminal_mfe_retention": float(
                    group["terminal_mfe_retention"].median()
                ),
                "strong_anchors": int(len(strong)),
            }
            for threshold in EFFICIENCY_LADDER:
                row[f"daily_efficiency_ge_{int(threshold * 100)}_rate"] = float(
                    group[f"daily_efficiency_ge_{int(threshold * 100)}"].mean()
                )
            for delay in DELAYS:
                row[f"median_delay_{delay}h_capture_ratio"] = float(
                    group[f"delay_{delay}h_capture_ratio"].median()
                )
                row[f"delay_{delay}h_cost_positive_rate"] = float(
                    group[f"delay_{delay}h_cost_positive"].mean()
                )
                row[f"strong_median_delay_{delay}h_capture_ratio"] = (
                    float(strong[f"delay_{delay}h_capture_ratio"].median())
                    if not strong.empty
                    else math.nan
                )
                row[f"strong_delay_{delay}h_cost_positive_rate"] = (
                    float(strong[f"delay_{delay}h_cost_positive"].mean())
                    if not strong.empty
                    else math.nan
                )
            rows.append(row)
    return pd.DataFrame(rows)


def summarize_admission(paths: pd.DataFrame, scope: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (asset, horizon), base in paths.groupby(["asset", "horizon_hours"]):
        for side, side_name in ((1, "long"), (-1, "short")):
            admitted = base.loc[base["admission_side"].eq(side)]
            unconditional_return = base[f"unconditional_{side_name}_signed_return"]
            unconditional_net = base[f"unconditional_{side_name}_net"]
            unconditional_first = base[f"unconditional_{side_name}_first_passage"]
            if admitted.empty:
                continue
            rows.append(
                {
                    "scope": scope,
                    "asset": asset,
                    "horizon_hours": int(horizon),
                    "horizon_days": int(horizon // 24),
                    "side": side_name,
                    "total_anchors": int(len(base)),
                    "admitted_anchors": int(len(admitted)),
                    "admission_share": float(len(admitted) / len(base)),
                    "continuation_rate": float(admitted["admission_continuation"].mean()),
                    "mean_signed_return": float(admitted["admission_signed_return"].mean()),
                    "median_signed_return": float(admitted["admission_signed_return"].median()),
                    "mean_scaled_return": float(admitted["admission_scaled_return"].mean()),
                    "mean_cost_funding_net": float(admitted["admission_net"].mean()),
                    "median_cost_funding_net": float(admitted["admission_net"].median()),
                    "net_positive_rate": float(admitted["admission_net_positive"].mean()),
                    "median_mfe_r": float(admitted["admission_mfe_r"].median()),
                    "median_mae_r": float(admitted["admission_mae_r"].median()),
                    "favorable_first_passage_rate": float(
                        admitted["admission_first_passage"].eq("favorable").mean()
                    ),
                    "unconditional_mean_signed_return": float(
                        unconditional_return.mean()
                    ),
                    "unconditional_mean_net": float(unconditional_net.mean()),
                    "unconditional_net_positive_rate": float(
                        unconditional_net.gt(0.0).mean()
                    ),
                    "unconditional_favorable_first_passage_rate": float(
                        unconditional_first.eq("favorable").mean()
                    ),
                    "admission_minus_unconditional_net": float(
                        admitted["admission_net"].mean() - unconditional_net.mean()
                    ),
                }
            )
    return pd.DataFrame(rows)


def summarize_onset_followthrough(paths: pd.DataFrame, scope: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (asset, horizon), base in paths.groupby(["asset", "horizon_hours"]):
        for delay in DELAYS:
            working = base.loc[base[f"onset_{delay}h_side"].ne(0)].copy()
            if working.empty:
                continue
            ranks = working[f"onset_{delay}h_scaled_move"].rank(
                method="first", pct=True
            )
            working["strength_tier"] = pd.cut(
                ranks,
                bins=[0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0],
                labels=["low", "mid", "high"],
                include_lowest=True,
            )
            groups: list[tuple[str, pd.DataFrame]] = [("all", working)]
            groups.extend(
                (tier, working.loc[working["strength_tier"].eq(tier)])
                for tier in ("low", "mid", "high")
            )
            for tier, group in groups:
                rows.append(
                    {
                        "scope": scope,
                        "asset": asset,
                        "horizon_hours": int(horizon),
                        "horizon_days": int(horizon // 24),
                        "delay_hours": delay,
                        "strength_tier": tier,
                        "anchors": int(len(group)),
                        "median_early_scaled_move": float(
                            group[f"onset_{delay}h_scaled_move"].median()
                        ),
                        "median_early_efficiency": float(
                            group[f"onset_{delay}h_efficiency"].median()
                        ),
                        "continuation_rate": float(
                            group[f"onset_{delay}h_continuation"].mean()
                        ),
                        "mean_remaining_return": float(
                            group[f"onset_{delay}h_remaining_return"].mean()
                        ),
                        "median_remaining_return": float(
                            group[f"onset_{delay}h_remaining_return"].median()
                        ),
                        "mean_cost_funding_net": float(
                            group[f"onset_{delay}h_net"].mean()
                        ),
                        "median_cost_funding_net": float(
                            group[f"onset_{delay}h_net"].median()
                        ),
                        "net_positive_rate": float(
                            group[f"onset_{delay}h_net_positive"].mean()
                        ),
                        "median_mfe_r": float(group[f"onset_{delay}h_mfe_r"].median()),
                        "median_mae_r": float(group[f"onset_{delay}h_mae_r"].median()),
                        "favorable_first_passage_rate": float(
                            group[f"onset_{delay}h_first_passage"]
                            .eq("favorable")
                            .mean()
                        ),
                    }
                )
    return pd.DataFrame(rows)


def build_daily_states(asset_data: AssetData) -> pd.DataFrame:
    hourly = asset_data.hourly
    log_price = np.log(hourly["close"])
    daily = pd.DataFrame(index=hourly.index[hourly.index.hour == 0])
    daily["log_price"] = log_price.reindex(daily.index)
    daily["past_7d_return"] = daily["log_price"] - log_price.shift(
        PAST_FAST_HOURS
    ).reindex(daily.index)
    daily["past_28d_return"] = daily["log_price"] - log_price.shift(
        PAST_SLOW_HOURS
    ).reindex(daily.index)
    daily["state"] = np.select(
        [
            daily["past_7d_return"].gt(0.0) & daily["past_28d_return"].gt(0.0),
            daily["past_7d_return"].lt(0.0) & daily["past_28d_return"].lt(0.0),
        ],
        [1, -1],
        default=0,
    )
    daily = daily.dropna(subset=["past_7d_return", "past_28d_return"])
    daily["asset"] = asset_data.asset
    return daily


def summarize_episodes(states: pd.DataFrame, scope: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    episode_rows: list[dict[str, Any]] = []
    quarterly_rows: list[dict[str, Any]] = []
    for asset, frame in states.groupby("asset"):
        ordered = frame.sort_index().copy()
        group_id = ordered["state"].ne(ordered["state"].shift()).cumsum()
        for _, episode in ordered.groupby(group_id):
            state = int(episode["state"].iloc[0])
            if state == 0:
                continue
            episode_rows.append(
                {
                    "scope": scope,
                    "asset": asset,
                    "side": "long" if state > 0 else "short",
                    "start": episode.index.min(),
                    "end": episode.index.max(),
                    "duration_days": int(len(episode)),
                }
            )
        temp = ordered.copy()
        temp["quarter"] = temp.index.tz_localize(None).to_period("Q").astype(str)
        for quarter, part in temp.groupby("quarter"):
            quarterly_rows.append(
                {
                    "scope": scope,
                    "asset": asset,
                    "quarter": quarter,
                    "days": int(len(part)),
                    "nonflat_share": float(part["state"].ne(0).mean()),
                    "long_share": float(part["state"].eq(1).mean()),
                    "short_share": float(part["state"].eq(-1).mean()),
                }
            )
    episodes = pd.DataFrame(episode_rows)
    quarterly = pd.DataFrame(quarterly_rows)
    if episodes.empty:
        return episodes, quarterly
    summaries: list[dict[str, Any]] = []
    for (asset, side), group in episodes.groupby(["asset", "side"]):
        values = group["duration_days"]
        source = states.loc[states["asset"].eq(asset), "state"]
        summaries.append(
            {
                "scope": scope,
                "asset": asset,
                "side": side,
                "episodes": int(len(group)),
                "nonflat_share": float(source.ne(0).mean()),
                "median_duration_days": float(values.median()),
                "p75_duration_days": float(values.quantile(0.75)),
                "p90_duration_days": float(values.quantile(0.90)),
                "max_duration_days": int(values.max()),
            }
        )
    return pd.DataFrame(summaries), quarterly


def common_bounds(assets: dict[str, AssetData]) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = max(data.hourly.index.min() for data in assets.values()) + pd.Timedelta(
        hours=PAST_VOL_HOURS
    )
    end = min(data.hourly.index.max() for data in assets.values()) - pd.Timedelta(
        hours=max(HORIZONS)
    )
    return start.ceil("1D"), end.floor("1D")


def block_bootstrap_difference(
    paired: pd.DataFrame,
    left: str,
    right: str,
    metric: str,
) -> dict[str, Any]:
    wide = paired.pivot(index="anchor", columns="asset", values=metric)[[left, right]].dropna()
    if wide.empty:
        return {}
    elapsed = wide.index - wide.index.min()
    blocks = (elapsed.total_seconds() // (BLOCK_DAYS * 86400)).astype(int)
    grouped = {
        int(block): values[left].to_numpy(float) - values[right].to_numpy(float)
        for block, values in wide.groupby(blocks)
    }
    keys = np.array(list(grouped), dtype=int)
    rng = np.random.default_rng(20260803)
    draws = np.empty(BOOTSTRAP_SAMPLES, dtype=float)
    for draw in range(BOOTSTRAP_SAMPLES):
        sampled = rng.choice(keys, size=len(keys), replace=True)
        values = np.concatenate([grouped[int(key)] for key in sampled])
        draws[draw] = float(values.mean())
    ci = np.quantile(draws, [0.025, 0.975])
    delta = wide[left] - wide[right]
    return {
        "paired_anchors": int(len(wide)),
        "independent_14d_blocks": int(len(keys)),
        "mean_difference": float(delta.mean()),
        "median_difference": float(delta.median()),
        "ci_95_low": float(ci[0]),
        "ci_95_high": float(ci[1]),
    }


def build_bootstrap(paths: pd.DataFrame) -> pd.DataFrame:
    metrics = (
        "amplitude",
        "scaled_amplitude",
        "daily_efficiency",
        "strong_trend",
        "delay_24h_remaining_scaled",
        "half_mfe_triggered_after_2r",
        "admission_net_zero_if_flat",
        "onset_24h_net",
    )
    rows: list[dict[str, Any]] = []
    for horizon, horizon_paths in paths.groupby("horizon_hours"):
        for other in ("BTC", "ETH", "SOL"):
            pair = horizon_paths.loc[horizon_paths["asset"].isin(["HYPE", other])].copy()
            for metric in metrics:
                pair[metric] = pd.to_numeric(pair[metric], errors="coerce").astype(float)
                result = block_bootstrap_difference(pair, "HYPE", other, metric)
                rows.append(
                    {
                        "horizon_hours": int(horizon),
                        "horizon_days": int(horizon // 24),
                        "left": "HYPE",
                        "right": other,
                        "metric": metric,
                        **result,
                    }
                )
    return pd.DataFrame(rows)


def overview(paths: pd.DataFrame, admission: pd.DataFrame) -> pd.DataFrame:
    habitat = summarize_habitat(paths, "common")
    all_habitat = habitat.loc[habitat["side"].eq("all")].copy()
    admitted_rows: list[dict[str, Any]] = []
    for (asset, horizon), group in admission.groupby(["asset", "horizon_hours"]):
        count = group["admitted_anchors"].sum()
        weighted_net = (
            float(
                np.average(
                    group["mean_cost_funding_net"],
                    weights=group["admitted_anchors"],
                )
            )
            if count > 0
            else np.nan
        )
        admitted_rows.append(
            {
                "asset": asset,
                "horizon_hours": int(horizon),
                "admitted_anchors": int(count),
                "admission_weighted_net": weighted_net,
                "positive_direction_count": int(
                    (group["mean_cost_funding_net"] > 0.0).sum()
                ),
            }
        )
    admitted = pd.DataFrame(admitted_rows)
    columns = [
        "asset",
        "horizon_hours",
        "horizon_days",
        "anchors",
        "median_amplitude",
        "median_scaled_amplitude",
        "median_daily_efficiency",
        "strong_trend_rate",
        "favorable_first_passage_rate",
        "median_required_giveback_share",
        "half_mfe_trigger_rate_after_2r",
        "strong_median_delay_24h_capture_ratio",
        "strong_delay_24h_cost_positive_rate",
    ]
    return all_habitat[columns].merge(
        admitted, on=["asset", "horizon_hours"], how="left"
    )


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    raise TypeError(f"cannot serialize {type(value)!r}")


def frame_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    assets = load_assets()
    all_paths = pd.concat(
        [build_anchor_paths(data) for data in assets.values()], ignore_index=True
    )
    all_paths.to_parquet(
        ARTIFACT_DIR / f"binance_1h_fatha_anchor_paths_{RUN_DATE}.parquet",
        index=False,
    )
    common_start, common_end = common_bounds(assets)
    common_paths = all_paths.loc[
        all_paths["anchor"].ge(common_start) & all_paths["anchor"].le(common_end)
    ].copy()

    full_habitat = summarize_habitat(all_paths, "full_history")
    common_habitat = summarize_habitat(common_paths, "common")
    habitat = pd.concat([full_habitat, common_habitat], ignore_index=True)
    full_admission = summarize_admission(all_paths, "full_history")
    common_admission = summarize_admission(common_paths, "common")
    admission = pd.concat([full_admission, common_admission], ignore_index=True)
    full_onset = summarize_onset_followthrough(all_paths, "full_history")
    common_onset = summarize_onset_followthrough(common_paths, "common")
    onset = pd.concat([full_onset, common_onset], ignore_index=True)

    all_states = pd.concat(
        [build_daily_states(data) for data in assets.values()]
    ).sort_index()
    common_states = all_states.loc[
        all_states.index.to_series().ge(common_start).to_numpy()
        & all_states.index.to_series().le(common_end).to_numpy()
    ]
    full_episode, full_quarterly = summarize_episodes(all_states, "full_history")
    common_episode, common_quarterly = summarize_episodes(common_states, "common")
    episodes = pd.concat([full_episode, common_episode], ignore_index=True)
    quarterly = pd.concat([full_quarterly, common_quarterly], ignore_index=True)

    bootstrap = build_bootstrap(common_paths)
    common_overview = overview(common_paths, common_admission)

    outputs = {
        "habitat_summary": habitat,
        "admission_summary": admission,
        "onset_followthrough": onset,
        "episode_summary": episodes,
        "quarterly_state_coverage": quarterly,
        "hype_paired_bootstrap": bootstrap,
        "common_asset_overview": common_overview,
    }
    for name, frame in outputs.items():
        frame.to_csv(
            ARTIFACT_DIR / f"binance_1h_fatha_{name}_{RUN_DATE}.csv",
            index=False,
        )

    payload = {
        "family": "Binance-1H-Four-Asset-Trend-Habitat-Audit",
        "alias": "BIN-1H-FATHA",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "run_date": RUN_DATE,
        "data_quality": {asset: data.quality for asset, data in assets.items()},
        "contract": {
            "assets": list(SYMBOLS),
            "horizons_hours": HORIZONS,
            "delays_hours": DELAYS,
            "past_vol_hours": PAST_VOL_HOURS,
            "past_direction_hours": [PAST_FAST_HOURS, PAST_SLOW_HOURS],
            "roundtrip_hurdle": ROUNDTRIP_HURDLE,
            "strong_scaled_amplitude": STRONG_SCALED_AMPLITUDE,
            "strong_daily_efficiency": STRONG_DAILY_EFFICIENCY,
            "efficiency_ladder": EFFICIENCY_LADDER,
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "block_days": BLOCK_DAYS,
            "post_reveal_onset_extension": {
                "delays_hours": DELAYS,
                "direction": "sign of observed anchor-to-delay close move",
                "strength_tiers": ["low", "mid", "high"],
                "promotion_evidence": False,
            },
        },
        "common_window": {
            "start": common_start,
            "end": common_end,
            "anchor_rows": int(len(common_paths)),
        },
        "summaries": {
            name: frame_records(frame) for name, frame in outputs.items()
        },
        "limitations": [
            "Ex-post direction describes habitat and is not an available trading signal.",
            "Daily anchors overlap; inference uses 14-day calendar block bootstrap.",
            "The 7d/28d admission is intentionally simple and frozen; failure does not prove that no external-information selector can work.",
            "The onset-followthrough extension was frozen after the primary habitat/admission aggregate was revealed and is diagnostic only.",
            "No orders, leverage, position sizing, portfolio construction, or strategy return are produced in this diagnostic.",
        ],
    }
    with (ARTIFACT_DIR / f"binance_1h_fatha_research_{RUN_DATE}.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=json_default)

    print("COMMON WINDOW", common_start, common_end)
    print(common_overview.to_string(index=False))
    print("\nCOMMON ADMISSION")
    print(common_admission.to_string(index=False))
    print("\nHYPE PAIRED BOOTSTRAP")
    print(bootstrap.to_string(index=False))


if __name__ == "__main__":
    main()
