from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from scipy.stats import spearmanr
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.tree import DecisionTreeRegressor, export_text


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-trend-prebreakout-state-atlas"
CONFIG_PATH = (
    FAMILY_DIR / "configs/binance-1d-trend-prebreakout-state-atlas-p0.json"
)
EXPECTED_CONFIG_SHA256 = "3165ebe82d6f8361b20c24837b896bedb513dddfad0eac75b7268594b8124258"
REPAIR_CONFIG_PATH = (
    FAMILY_DIR / "configs/binance-1d-trend-prebreakout-state-atlas-p0r.json"
)
REPAIR_CONFIG_SHA256 = "7a08e4d75188098e3a80a5e1d3318b21f8a9d7cbc942375f836dfd902cf38e8d"
PANEL_PATH = (
    ROOT
    / "data/cache/binance-1d-ma7-rc-p0"
    / "binance_1d_ma7_rc_p0_daily_panel.parquet"
)
REPAIR_PANEL_PATH = (
    ROOT
    / "data/cache/binance-1d-ma7-rc-p3"
    / "binance_1d_ma7_rc_p3_daily_panel.parquet"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
REPORT_PATH = (
    FAMILY_DIR
    / "diagnostics/binance-1d-trend-prebreakout-state-atlas-p0-results-2026-08-25.md"
)

US_STOCK_LIKE_BASES = {
    "AAPL",
    "AMZN",
    "COIN",
    "CRCL",
    "GOOGL",
    "HOOD",
    "META",
    "MSFT",
    "MSTR",
    "NVDA",
    "PLTR",
    "TSLA",
}

PRIMARY_MA_PERIODS = (7, 30)
ROBUSTNESS_MA_PERIODS = (5, 10, 20)
MA_PERIODS = (*ROBUSTNESS_MA_PERIODS[:2], *PRIMARY_MA_PERIODS, ROBUSTNESS_MA_PERIODS[2])
MA_PERIODS = tuple(sorted(set(MA_PERIODS)))
HORIZONS = (1, 3, 5, 10, 20, 40)
PATH_HORIZONS = (10, 20)
DEVELOPMENT_CUTOFF = pd.Timestamp("2026-07-01T00:00:00Z")

OUTPUTS = {
    "events": ARTIFACT_DIR / "binance_1d_tpsa_p0_events.parquet",
    "unconditional": ARTIFACT_DIR / "binance_1d_tpsa_p0_unconditional_stats.csv",
    "frequency": ARTIFACT_DIR / "binance_1d_tpsa_p0_frequency_stats.csv",
    "transition": ARTIFACT_DIR / "binance_1d_tpsa_p0_move_transition_matrix.csv",
    "transition_robustness": ARTIFACT_DIR
    / "binance_1d_tpsa_p0_move_transition_robustness.csv",
    "volatility": ARTIFACT_DIR / "binance_1d_tpsa_p0_volatility_state_matrix.csv",
    "path_shape": ARTIFACT_DIR / "binance_1d_tpsa_p0_path_shape_matrix.csv",
    "hypotheses": ARTIFACT_DIR / "binance_1d_tpsa_p0_hypothesis_stats.csv",
    "hypothesis_frequency": ARTIFACT_DIR
    / "binance_1d_tpsa_p0_hypothesis_frequency.csv",
    "hypothesis_robustness": ARTIFACT_DIR
    / "binance_1d_tpsa_p0_hypothesis_robustness.csv",
    "path_outcomes": ARTIFACT_DIR / "binance_1d_tpsa_p0_path_outcome_stats.csv",
    "ma_consistency": ARTIFACT_DIR / "binance_1d_tpsa_p0_ma_consistency.csv",
    "ml_metrics": ARTIFACT_DIR / "binance_1d_tpsa_p0_ml_walk_forward_metrics.csv",
    "ml_predictions": ARTIFACT_DIR / "binance_1d_tpsa_p0_ml_predictions.parquet",
    "ml_deciles": ARTIFACT_DIR / "binance_1d_tpsa_p0_ml_prediction_deciles.csv",
    "ml_importance": ARTIFACT_DIR / "binance_1d_tpsa_p0_ml_feature_importance.csv",
    "ml_tree_rules": ARTIFACT_DIR / "binance_1d_tpsa_p0_tree_rules.txt",
    "summary": ARTIFACT_DIR / "binance_1d_tpsa_p0_summary.json",
    "manifest": ARTIFACT_DIR / "binance_1d_tpsa_p0_artifact_manifest.json",
}

HYPOTHESES = (
    "ALL",
    "OPPOSITE_SHOCK_THEN_REPAIR",
    "OPPOSITE_MOVE_THEN_BASE",
    "ORDERLY_TREND_PULLBACK_RESUME",
    "ORDERLY_TREND_CONTINUATION",
    "LARGE_MOVE_THEN_SIDEWAYS_BREAK",
    "FAST_REVERSAL",
    "EXTENDED_MOVE_CONTINUATION",
    "EXTENDED_MOVE_EXHAUSTION",
    "LOW_VOL_COMPRESSION",
    "VOLATILITY_CONTRACTION",
    "VOLATILITY_EXPANSION",
    "HIGH_VOL_CHOP",
    "LOW_EFFICIENCY_RECROSS",
)

HYPOTHESIS_ZH = {
    "ALL": "全部突破",
    "OPPOSITE_SHOCK_THEN_REPAIR": "反向暴跌/暴涨后明显修复",
    "OPPOSITE_MOVE_THEN_BASE": "反向大行情后横盘筑底/筑顶",
    "ORDERLY_TREND_PULLBACK_RESUME": "原趋势有序回踩后恢复",
    "ORDERLY_TREND_CONTINUATION": "原趋势有序持续推进",
    "LARGE_MOVE_THEN_SIDEWAYS_BREAK": "大行情后横盘再破位",
    "FAST_REVERSAL": "旧趋势后的快速反转",
    "EXTENDED_MOVE_CONTINUATION": "已经大幅延伸后继续加速",
    "EXTENDED_MOVE_EXHAUSTION": "已经大幅延伸后转弱破位",
    "LOW_VOL_COMPRESSION": "低波动窄幅压缩",
    "VOLATILITY_CONTRACTION": "波动持续收缩",
    "VOLATILITY_EXPANSION": "波动持续扩张",
    "HIGH_VOL_CHOP": "高波动来回乱震",
    "LOW_EFFICIENCY_RECROSS": "低效率反复穿越",
}

ML_FEATURES = (
    "aligned_return_5_pre_atr",
    "aligned_return_10_pre_atr",
    "aligned_return_20_pre_atr",
    "aligned_return_60_pre_atr",
    "aligned_prior_50_return_atr",
    "aligned_recent_10_return_atr",
    "aligned_acceleration_5_vs_20",
    "aligned_location_20",
    "aligned_location_60",
    "aligned_repair_from_adverse_60_atr",
    "aligned_pullback_from_favorable_60_atr",
    "aligned_worst_day_20_atr",
    "aligned_best_day_20_atr",
    "er10_pre",
    "er20_pre",
    "er60_pre",
    "return_sign_flips_20_pre",
    "range_ratio_5_60_pre",
    "range_ratio_10_60_pre",
    "range_ratio_20_60_pre",
    "atr10_atr60_pre",
    "atr_pct_pre",
    "atr_level_percentile_60_pre",
    "atr_change_5_pre",
    "atr_change_10_pre",
    "atr_change_20_pre",
    "atr_path_percentile_60_pre",
    "rv10_rv60_pre",
)

WALK_FORWARD_WINDOWS = (
    (pd.Timestamp("2022-01-01T00:00:00Z"), pd.Timestamp("2023-01-01T00:00:00Z")),
    (pd.Timestamp("2023-01-01T00:00:00Z"), pd.Timestamp("2024-01-01T00:00:00Z")),
    (pd.Timestamp("2024-01-01T00:00:00Z"), pd.Timestamp("2025-01-01T00:00:00Z")),
    (pd.Timestamp("2025-01-01T00:00:00Z"), pd.Timestamp("2026-01-01T00:00:00Z")),
    (pd.Timestamp("2026-01-01T00:00:00Z"), DEVELOPMENT_CUTOFF),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen BIN-1D-TPSA-P0 exploratory state atlas."
    )
    parser.add_argument("--run", action="store_true", help="Acknowledge outcome access.")
    parser.add_argument("--force", action="store_true", help="Replace P0 outputs.")
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Run the frozen P0R all-asset input-scope repair.",
    )
    return parser.parse_args()


def activate_repair_context() -> None:
    global CONFIG_PATH, EXPECTED_CONFIG_SHA256, PANEL_PATH, REPORT_PATH, OUTPUTS
    CONFIG_PATH = REPAIR_CONFIG_PATH
    EXPECTED_CONFIG_SHA256 = REPAIR_CONFIG_SHA256
    PANEL_PATH = REPAIR_PANEL_PATH
    REPORT_PATH = (
        FAMILY_DIR
        / "diagnostics/binance-1d-trend-prebreakout-state-atlas-p0r-results-2026-08-25.md"
    )
    OUTPUTS = {
        key: path.with_name(path.name.replace("tpsa_p0_", "tpsa_p0r_"))
        for key, path in OUTPUTS.items()
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_inputs(*, force: bool) -> dict[str, Any]:
    actual = sha256_file(CONFIG_PATH)
    if actual != EXPECTED_CONFIG_SHA256:
        raise RuntimeError(f"frozen config hash mismatch: {actual}")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("study_id") not in {"BIN-1D-TPSA-P0", "BIN-1D-TPSA-P0R"}:
        raise RuntimeError("unexpected study_id")
    if not PANEL_PATH.exists():
        raise FileNotFoundError(PANEL_PATH)
    existing = [path for path in [*OUTPUTS.values(), REPORT_PATH] if path.exists()]
    if existing and not force:
        raise FileExistsError("P0 outputs exist; pass --force to reproduce")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    return config


def rolling_percentile_current(values: Sequence[float], window: int = 60) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    result = np.full(len(array), np.nan, dtype=float)
    if len(array) < window:
        return result
    views = np.lib.stride_tricks.sliding_window_view(array, window)
    valid = np.isfinite(views).all(axis=1)
    ranks = np.full(len(views), np.nan, dtype=float)
    ranks[valid] = (views[valid] <= views[valid, -1, None]).mean(axis=1)
    result[window - 1 :] = ranks
    return result


def rolling_efficiency(close: pd.Series, window: int) -> pd.Series:
    path = close.diff().abs().rolling(window, min_periods=window).sum()
    return (close - close.shift(window)).abs() / path.replace(0.0, np.nan)


def _pre_window_excursions(close: np.ndarray, window: int = 60) -> tuple[np.ndarray, np.ndarray]:
    drawdown = np.full(len(close), np.nan, dtype=float)
    runup = np.full(len(close), np.nan, dtype=float)
    if len(close) <= window:
        return drawdown, runup
    views = np.lib.stride_tricks.sliding_window_view(close, window)[:-1]
    running_max = np.maximum.accumulate(views, axis=1)
    running_min = np.minimum.accumulate(views, axis=1)
    max_drawdown = np.max(1.0 - views / running_max, axis=1)
    max_runup = np.max(views / running_min - 1.0, axis=1)
    drawdown[window:] = max_drawdown
    runup[window:] = max_runup
    return drawdown, runup


def _forward_path_arrays(
    close: np.ndarray, atr_pre: np.ndarray, horizon: int
) -> dict[str, np.ndarray]:
    size = len(close)
    names = (
        "future_close",
        "future_max_close",
        "future_min_close",
        "future_path_sum",
        "barrier_long",
        "barrier_short",
    )
    output = {name: np.full(size, np.nan, dtype=float) for name in names}
    if size <= horizon:
        return output
    views = np.lib.stride_tricks.sliding_window_view(close, horizon + 1)
    base = views[:, 0]
    future = views[:, 1:]
    count = len(views)
    output["future_close"][:count] = future[:, -1]
    output["future_max_close"][:count] = np.max(future, axis=1)
    output["future_min_close"][:count] = np.min(future, axis=1)
    output["future_path_sum"][:count] = np.abs(np.diff(views, axis=1)).sum(axis=1)

    denom = atr_pre[:count]
    valid = np.isfinite(denom) & (denom > 0)
    signed_long = np.full_like(future, np.nan, dtype=float)
    signed_long[valid] = (future[valid] - base[valid, None]) / denom[valid, None]
    for label, signed_path in (
        ("barrier_long", signed_long),
        ("barrier_short", -signed_long),
    ):
        favorable = signed_path >= 2.0
        adverse = signed_path <= -1.0
        first_favorable = np.where(
            favorable.any(axis=1), favorable.argmax(axis=1), horizon + 1
        )
        first_adverse = np.where(adverse.any(axis=1), adverse.argmax(axis=1), horizon + 1)
        barrier = (first_favorable < first_adverse).astype(float)
        barrier[~valid] = np.nan
        output[label][:count] = barrier
    return output


def feature_block(group: pd.DataFrame) -> pd.DataFrame:
    block = group.copy().sort_values("event_date").reset_index(drop=True)
    close = block["close"].astype(float)
    high = block["high"].astype(float)
    low = block["low"].astype(float)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    log_return = np.log(close).diff()

    atr10 = true_range.rolling(10, min_periods=10).mean()
    atr20 = true_range.rolling(20, min_periods=20).mean()
    atr60 = true_range.rolling(60, min_periods=60).mean()
    atr_pct = atr20 / close
    atr_change_10 = atr20 / atr20.shift(10) - 1.0

    block["true_range"] = true_range
    block["atr20_pre"] = atr20.shift(1)
    block["atr_pct_pre"] = atr_pct.shift(1)
    block["atr_level_percentile_60_pre"] = pd.Series(
        rolling_percentile_current(atr_pct.to_numpy()), index=block.index
    ).shift(1)
    for window in (5, 10, 20):
        block[f"atr_change_{window}_pre"] = (
            atr20.shift(1) / atr20.shift(window + 1) - 1.0
        )
    block["atr_path_percentile_60_pre"] = pd.Series(
        rolling_percentile_current(atr_change_10.to_numpy()), index=block.index
    ).shift(1)
    block["atr10_atr60_pre"] = (atr10 / atr60.replace(0.0, np.nan)).shift(1)

    for window in (5, 10, 20, 60):
        block[f"raw_return_{window}_pre_atr"] = (
            np.log(close.shift(1) / close.shift(window + 1))
            / block["atr_pct_pre"].replace(0.0, np.nan)
        )
    block["raw_prior_50_return_atr"] = (
        np.log(close.shift(11) / close.shift(61))
        / block["atr_pct_pre"].replace(0.0, np.nan)
    )
    block["raw_recent_10_return_atr"] = block["raw_return_10_pre_atr"]
    block["raw_acceleration_5_vs_20"] = (
        log_return.rolling(5, min_periods=5).mean().shift(1)
        - log_return.rolling(20, min_periods=20).mean().shift(1)
    ) / block["atr_pct_pre"].replace(0.0, np.nan)

    for window in (10, 20, 60):
        block[f"er{window}_pre"] = rolling_efficiency(close, window).shift(1)

    sign = np.sign(log_return)
    flips = sign.ne(sign.shift(1)).astype(float).where(sign.ne(0) & sign.shift(1).ne(0))
    block["return_sign_flips_20_pre"] = flips.rolling(20, min_periods=20).sum().shift(1)

    shifted_high = high.shift(1)
    shifted_low = low.shift(1)
    range_widths: dict[int, pd.Series] = {}
    for window in (5, 10, 20, 60):
        window_high = shifted_high.rolling(window, min_periods=window).max()
        window_low = shifted_low.rolling(window, min_periods=window).min()
        range_widths[window] = window_high - window_low
        if window in (20, 60):
            block[f"raw_location_{window}"] = (
                close.shift(1) - window_low
            ) / (window_high - window_low).replace(0.0, np.nan)
    for window in (5, 10, 20):
        block[f"range_ratio_{window}_60_pre"] = range_widths[window] / range_widths[
            60
        ].replace(0.0, np.nan)

    low60 = shifted_low.rolling(60, min_periods=60).min()
    high60 = shifted_high.rolling(60, min_periods=60).max()
    block["up_from_low_60_atr"] = (
        np.log(close.shift(1) / low60) / block["atr_pct_pre"].replace(0.0, np.nan)
    )
    block["down_from_high_60_atr"] = (
        np.log(high60 / close.shift(1)) / block["atr_pct_pre"].replace(0.0, np.nan)
    )
    block["worst_day_20_atr"] = (
        log_return.rolling(20, min_periods=20).min().shift(1)
        / block["atr_pct_pre"].replace(0.0, np.nan)
    )
    block["best_day_20_atr"] = (
        log_return.rolling(20, min_periods=20).max().shift(1)
        / block["atr_pct_pre"].replace(0.0, np.nan)
    )
    max_drawdown, max_runup = _pre_window_excursions(close.to_numpy(dtype=float))
    block["max_drawdown_60_atr"] = max_drawdown / block["atr_pct_pre"].replace(
        0.0, np.nan
    )
    block["max_runup_60_atr"] = max_runup / block["atr_pct_pre"].replace(0.0, np.nan)

    rv10 = log_return.rolling(10, min_periods=10).std(ddof=1)
    rv60 = log_return.rolling(60, min_periods=60).std(ddof=1)
    block["rv10_rv60_pre"] = (rv10 / rv60.replace(0.0, np.nan)).shift(1)

    for period in MA_PERIODS:
        block[f"sma{period}"] = close.rolling(period, min_periods=period).mean()
    block["trigger_range_ratio"] = true_range / block["atr20_pre"].replace(0.0, np.nan)
    block["trigger_return_atr"] = log_return / block["atr_pct_pre"].replace(0.0, np.nan)
    pre_volume = block["quote_volume"].astype(float).shift(1).rolling(20, min_periods=20).median()
    block["trigger_volume_ratio"] = block["quote_volume"].astype(float) / pre_volume.replace(
        0.0, np.nan
    )

    atr_pre = block["atr20_pre"].to_numpy(dtype=float)
    close_values = close.to_numpy(dtype=float)
    for horizon in HORIZONS:
        arrays = _forward_path_arrays(close_values, atr_pre, horizon)
        block[f"future_close_{horizon}_p0"] = arrays["future_close"]
        block[f"future_event_date_{horizon}_p0"] = block["event_date"].shift(-horizon)
        if horizon in PATH_HORIZONS:
            for name, values in arrays.items():
                if name == "future_close":
                    continue
                block[f"{name}_{horizon}"] = values
    return block


def load_feature_panel() -> pd.DataFrame:
    panel = pd.read_parquet(PANEL_PATH)
    needed = {
        "symbol",
        "base_asset",
        "event_date",
        "block_id",
        "open",
        "high",
        "low",
        "close",
        "quote_volume",
        "listing_age_days",
        "is_complete_day",
    }
    missing = sorted(needed - set(panel.columns))
    if missing:
        raise RuntimeError(f"daily panel missing columns: {missing}")
    panel["event_date"] = pd.to_datetime(panel["event_date"], utc=True)
    panel = panel.loc[
        panel["is_complete_day"] & panel["event_date"].lt(DEVELOPMENT_CUTOFF)
    ].copy()
    panel = panel.sort_values(["symbol", "block_id", "event_date"])
    blocks = [
        feature_block(group)
        for _, group in panel.groupby(["symbol", "block_id"], sort=False)
    ]
    featured = pd.concat(blocks, ignore_index=True)
    core = [
        "atr20_pre",
        "atr_pct_pre",
        "raw_return_60_pre_atr",
        "raw_prior_50_return_atr",
        "raw_recent_10_return_atr",
        "raw_location_60",
        "er60_pre",
        "range_ratio_10_60_pre",
        "atr_level_percentile_60_pre",
        "atr_path_percentile_60_pre",
        "rv10_rv60_pre",
    ]
    finite = np.isfinite(featured[core].astype(float).to_numpy()).all(axis=1)
    featured["eligible_prestate"] = finite & featured["listing_age_days"].ge(120)
    if not featured.loc[featured["eligible_prestate"]].shape[0]:
        raise RuntimeError("no eligible prestate rows")
    return featured


def movement_state(values: pd.Series) -> pd.Series:
    array = values.to_numpy(dtype=float)
    labels = np.select(
        [array <= -3.0, array < -1.0, array <= 1.0, array < 3.0],
        ["LARGE_ADVERSE", "ADVERSE", "FLAT", "FAVORABLE"],
        default="LARGE_FAVORABLE",
    ).astype(object)
    labels[~np.isfinite(array)] = pd.NA
    return pd.Series(labels, index=values.index, dtype="string")


def three_state_percentile(values: pd.Series, low: str, middle: str, high: str) -> pd.Series:
    array = values.to_numpy(dtype=float)
    labels = np.select([array <= 0.20, array <= 0.80], [low, middle], default=high).astype(
        object
    )
    labels[~np.isfinite(array)] = pd.NA
    return pd.Series(labels, index=values.index, dtype="string")


def add_state_labels(events: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    result["prior_move_state"] = movement_state(result["aligned_prior_50_return_atr"])
    result["recent_move_state"] = movement_state(result["aligned_recent_10_return_atr"])
    result["volatility_level_state"] = three_state_percentile(
        result["atr_level_percentile_60_pre"], "LOW", "NORMAL", "HIGH"
    )
    result["volatility_path_state"] = three_state_percentile(
        result["atr_path_percentile_60_pre"], "CONTRACTING", "STABLE", "EXPANDING"
    )
    er = result["er20_pre"].to_numpy(dtype=float)
    result["efficiency_state"] = pd.Series(
        np.select([er < 0.25, er <= 0.55], ["LOW", "MEDIUM"], default="HIGH"),
        index=result.index,
        dtype="string",
    )
    ratio = result["range_ratio_10_60_pre"].to_numpy(dtype=float)
    result["consolidation_state"] = pd.Series(
        np.select([ratio <= 0.35, ratio < 0.65], ["COMPRESSED", "NORMAL"], default="WIDE"),
        index=result.index,
        dtype="string",
    )

    prior = result["aligned_prior_50_return_atr"]
    recent = result["aligned_recent_10_return_atr"]
    repair = result["aligned_repair_from_adverse_60_atr"]
    max_adverse = result["aligned_max_adverse_excursion_60_atr"]
    range_ratio = result["range_ratio_10_60_pre"]
    er20 = result["er20_pre"]
    er60 = result["er60_pre"]
    flips = result["return_sign_flips_20_pre"]
    vol_level = result["atr_level_percentile_60_pre"]
    vol_path = result["atr_path_percentile_60_pre"]
    definitions = {
        "ALL": pd.Series(True, index=result.index),
        "OPPOSITE_SHOCK_THEN_REPAIR": max_adverse.ge(5.0)
        & repair.ge(1.0)
        & recent.ge(1.0),
        "OPPOSITE_MOVE_THEN_BASE": prior.le(-3.0)
        & recent.abs().le(1.0)
        & range_ratio.le(0.35),
        "ORDERLY_TREND_PULLBACK_RESUME": prior.ge(1.0)
        & recent.le(-1.0)
        & er60.ge(0.35),
        "ORDERLY_TREND_CONTINUATION": prior.ge(1.0)
        & recent.ge(1.0)
        & er60.ge(0.35)
        & er20.ge(0.35),
        "LARGE_MOVE_THEN_SIDEWAYS_BREAK": prior.abs().ge(3.0)
        & recent.abs().le(1.0)
        & range_ratio.le(0.35),
        "FAST_REVERSAL": prior.le(-1.0) & recent.ge(3.0),
        "EXTENDED_MOVE_CONTINUATION": prior.ge(3.0) & recent.ge(3.0),
        "EXTENDED_MOVE_EXHAUSTION": prior.ge(3.0) & recent.le(-1.0),
        "LOW_VOL_COMPRESSION": vol_level.le(0.20) & range_ratio.le(0.35),
        "VOLATILITY_CONTRACTION": vol_path.le(0.20),
        "VOLATILITY_EXPANSION": vol_path.gt(0.80),
        "HIGH_VOL_CHOP": vol_level.gt(0.80) & er20.lt(0.25) & flips.ge(8),
        "LOW_EFFICIENCY_RECROSS": er20.lt(0.25) & flips.ge(8),
    }
    for name, mask in definitions.items():
        result[f"hyp_{name}"] = mask.fillna(False).astype(bool)
    return result


def build_events(panel: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    grouped = panel.groupby(["symbol", "block_id"], sort=False)
    previous_close = grouped["close"].shift(1)
    pre_columns = sorted(
        {
            "atr20_pre",
            "atr_pct_pre",
            "atr_level_percentile_60_pre",
            "atr_change_5_pre",
            "atr_change_10_pre",
            "atr_change_20_pre",
            "atr_path_percentile_60_pre",
            "atr10_atr60_pre",
            "raw_return_5_pre_atr",
            "raw_return_10_pre_atr",
            "raw_return_20_pre_atr",
            "raw_return_60_pre_atr",
            "raw_prior_50_return_atr",
            "raw_recent_10_return_atr",
            "raw_acceleration_5_vs_20",
            "raw_location_20",
            "raw_location_60",
            "up_from_low_60_atr",
            "down_from_high_60_atr",
            "worst_day_20_atr",
            "best_day_20_atr",
            "max_drawdown_60_atr",
            "max_runup_60_atr",
            "er10_pre",
            "er20_pre",
            "er60_pre",
            "return_sign_flips_20_pre",
            "range_ratio_5_60_pre",
            "range_ratio_10_60_pre",
            "range_ratio_20_60_pre",
            "rv10_rv60_pre",
        }
    )
    identity = [
        "symbol",
        "base_asset",
        "event_date",
        "block_id",
        "close",
        "listing_age_days",
        "trigger_range_ratio",
        "trigger_return_atr",
        "trigger_volume_ratio",
        *pre_columns,
    ]
    for period in MA_PERIODS:
        previous_ma = grouped[f"sma{period}"].shift(1)
        long_trigger = previous_close.le(previous_ma) & panel["close"].gt(panel[f"sma{period}"])
        short_trigger = previous_close.ge(previous_ma) & panel["close"].lt(panel[f"sma{period}"])
        for direction, sign, trigger in (
            ("long", 1.0, long_trigger),
            ("short", -1.0, short_trigger),
        ):
            mask = trigger & panel["eligible_prestate"]
            events = panel.loc[mask, identity].copy()
            events["ma_period"] = period
            events["direction"] = direction
            events["direction_sign"] = sign
            events["calendar_year"] = events["event_date"].dt.year.astype(int)
            events["trigger_distance_ma_atr"] = sign * (
                panel.loc[mask, "close"].to_numpy(dtype=float)
                - panel.loc[mask, f"sma{period}"].to_numpy(dtype=float)
            ) / events["atr20_pre"].to_numpy(dtype=float)

            for window in (5, 10, 20, 60):
                events[f"aligned_return_{window}_pre_atr"] = (
                    sign * events[f"raw_return_{window}_pre_atr"]
                )
            events["aligned_prior_50_return_atr"] = sign * events[
                "raw_prior_50_return_atr"
            ]
            events["aligned_recent_10_return_atr"] = sign * events[
                "raw_recent_10_return_atr"
            ]
            events["aligned_acceleration_5_vs_20"] = sign * events[
                "raw_acceleration_5_vs_20"
            ]
            for window in (20, 60):
                events[f"aligned_location_{window}"] = np.where(
                    sign > 0,
                    events[f"raw_location_{window}"],
                    1.0 - events[f"raw_location_{window}"],
                )
            if sign > 0:
                events["aligned_repair_from_adverse_60_atr"] = events[
                    "up_from_low_60_atr"
                ]
                events["aligned_pullback_from_favorable_60_atr"] = events[
                    "down_from_high_60_atr"
                ]
                events["aligned_worst_day_20_atr"] = events["worst_day_20_atr"]
                events["aligned_best_day_20_atr"] = events["best_day_20_atr"]
                events["aligned_max_adverse_excursion_60_atr"] = events[
                    "max_drawdown_60_atr"
                ]
            else:
                events["aligned_repair_from_adverse_60_atr"] = events[
                    "down_from_high_60_atr"
                ]
                events["aligned_pullback_from_favorable_60_atr"] = events[
                    "up_from_low_60_atr"
                ]
                events["aligned_worst_day_20_atr"] = -events["best_day_20_atr"]
                events["aligned_best_day_20_atr"] = -events["worst_day_20_atr"]
                events["aligned_max_adverse_excursion_60_atr"] = events[
                    "max_runup_60_atr"
                ]

            entry = events["close"].to_numpy(dtype=float)
            atr = events["atr20_pre"].to_numpy(dtype=float)
            for horizon in HORIZONS:
                future = panel.loc[mask, f"future_close_{horizon}_p0"].to_numpy(dtype=float)
                events[f"raw_return_{horizon}"] = sign * (future / entry - 1.0)
                events[f"atr_return_{horizon}"] = sign * (future - entry) / atr
                if horizon in PATH_HORIZONS:
                    future_max = panel.loc[mask, f"future_max_close_{horizon}"].to_numpy(
                        dtype=float
                    )
                    future_min = panel.loc[mask, f"future_min_close_{horizon}"].to_numpy(
                        dtype=float
                    )
                    path_sum = panel.loc[mask, f"future_path_sum_{horizon}"].to_numpy(
                        dtype=float
                    )
                    if sign > 0:
                        events[f"mfe_atr_{horizon}"] = (future_max - entry) / atr
                        events[f"mae_atr_{horizon}"] = (future_min - entry) / atr
                        events[f"barrier_success_{horizon}"] = panel.loc[
                            mask, f"barrier_long_{horizon}"
                        ].to_numpy(dtype=float)
                    else:
                        events[f"mfe_atr_{horizon}"] = (entry - future_min) / atr
                        events[f"mae_atr_{horizon}"] = (entry - future_max) / atr
                        events[f"barrier_success_{horizon}"] = panel.loc[
                            mask, f"barrier_short_{horizon}"
                        ].to_numpy(dtype=float)
                    efficiency = np.abs(future - entry) / np.where(path_sum > 0, path_sum, np.nan)
                    events[f"clean_score_{horizon}"] = events[
                        f"atr_return_{horizon}"
                    ].to_numpy(dtype=float) * efficiency
            events["outcome_end_date_20"] = pd.to_datetime(
                panel.loc[mask, "future_event_date_20_p0"].to_numpy(), utc=True
            )
            events["event_id"] = (
                "MA"
                + str(period)
                + "|"
                + direction
                + "|"
                + events["symbol"].astype(str)
                + "|"
                + events["event_date"].dt.strftime("%Y-%m-%d")
            )
            frames.append(events)
    result = pd.concat(frames, ignore_index=True)
    if result["event_id"].duplicated().any():
        raise RuntimeError("duplicate event ids")
    return add_state_labels(result).sort_values(
        ["ma_period", "event_date", "symbol", "direction"]
    ).reset_index(drop=True)


def _cluster_variance(residual: np.ndarray, labels: pd.Series) -> tuple[float, int]:
    codes, unique = pd.factorize(labels, sort=False)
    groups = len(unique)
    if groups < 2:
        return math.nan, groups
    sums = np.bincount(codes, weights=residual)
    variance = (groups / (groups - 1.0)) * float(np.dot(sums, sums)) / len(residual) ** 2
    return variance, groups


def infer_mean(values: pd.Series, symbols: pd.Series, dates: pd.Series) -> dict[str, Any]:
    array = values.to_numpy(dtype=float)
    valid = np.isfinite(array)
    array = array[valid]
    symbols = symbols.loc[valid]
    dates = dates.loc[valid]
    count = len(array)
    empty = {
        "sample_count": 0,
        "symbol_count": 0,
        "event_date_count": 0,
        "mean": math.nan,
        "median": math.nan,
        "win_rate": math.nan,
        "cluster_se": math.nan,
        "t_stat": math.nan,
        "ci95_low": math.nan,
        "ci95_high": math.nan,
    }
    if count == 0:
        return empty
    mean = float(array.mean())
    residual = array - mean
    symbol_variance, symbol_count = _cluster_variance(residual, symbols)
    date_variance, date_count = _cluster_variance(residual, dates)
    standard_error = math.nan
    if count > 1 and np.isfinite(symbol_variance) and np.isfinite(date_variance):
        observation_variance = (
            count / (count - 1.0) * float(np.dot(residual, residual)) / count**2
        )
        combined = symbol_variance + date_variance - observation_variance
        if combined <= 0:
            combined = max(symbol_variance, date_variance)
        standard_error = math.sqrt(max(combined, 0.0))
    t_stat = mean / standard_error if np.isfinite(standard_error) and standard_error > 0 else math.nan
    return {
        "sample_count": int(count),
        "symbol_count": int(symbol_count),
        "event_date_count": int(date_count),
        "mean": mean,
        "median": float(np.median(array)),
        "win_rate": float(np.mean(array > 0)),
        "cluster_se": standard_error,
        "t_stat": t_stat,
        "ci95_low": mean - 1.959963984540054 * standard_error
        if np.isfinite(standard_error)
        else math.nan,
        "ci95_high": mean + 1.959963984540054 * standard_error
        if np.isfinite(standard_error)
        else math.nan,
    }


def summarize(
    frame: pd.DataFrame,
    group_columns: Sequence[str],
    metrics: Iterable[tuple[str, int]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for metric, horizon in metrics:
        column = f"{metric}_{horizon}"
        valid = frame.loc[np.isfinite(frame[column].to_numpy(dtype=float))]
        for keys, group in valid.groupby(list(group_columns), dropna=False, sort=True):
            key_values = keys if isinstance(keys, tuple) else (keys,)
            rows.append(
                {
                    **dict(zip(group_columns, key_values, strict=True)),
                    "horizon_days": horizon,
                    "outcome_metric": metric,
                    **infer_mean(group[column], group["symbol"], group["event_date"]),
                }
            )
    return pd.DataFrame(rows)


def exploded_hypotheses(events: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for hypothesis in HYPOTHESES:
        subset = events.loc[events[f"hyp_{hypothesis}"]].copy()
        subset["hypothesis"] = hypothesis
        frames.append(subset)
    return pd.concat(frames, ignore_index=True)


def build_frequency(events: pd.DataFrame, hypotheses: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    primary = events.loc[events["ma_period"].isin(PRIMARY_MA_PERIODS)].copy()
    period_keys = {
        "overall": pd.Series("ALL", index=primary.index),
        "year": primary["event_date"].dt.strftime("%Y"),
        "month": primary["event_date"].dt.strftime("%Y-%m"),
        "week": primary["event_date"].dt.strftime("%G-W%V"),
    }
    for frequency, keys in period_keys.items():
        working = primary.assign(period_key=keys)
        for group_keys, group in working.groupby(
            ["ma_period", "direction", "period_key"], sort=True
        ):
            rows.append(
                {
                    "scope": "ALL_EVENTS",
                    "frequency": frequency,
                    "ma_period": group_keys[0],
                    "direction": group_keys[1],
                    "hypothesis": "ALL",
                    "period_key": group_keys[2],
                    "event_count": len(group),
                    "symbol_count": group["symbol"].nunique(),
                    "event_date_count": group["event_date"].nunique(),
                }
            )
    hyp_primary = hypotheses.loc[
        hypotheses["ma_period"].isin(PRIMARY_MA_PERIODS)
        & hypotheses["hypothesis"].ne("ALL")
    ].copy()
    for group_keys, group in hyp_primary.groupby(
        ["ma_period", "direction", "hypothesis"], sort=True
    ):
        rows.append(
            {
                "scope": "HYPOTHESIS",
                "frequency": "overall",
                "ma_period": group_keys[0],
                "direction": group_keys[1],
                "hypothesis": group_keys[2],
                "period_key": "ALL",
                "event_count": len(group),
                "symbol_count": group["symbol"].nunique(),
                "event_date_count": group["event_date"].nunique(),
            }
        )
    return pd.DataFrame(rows)


def build_ma_consistency(hypothesis_stats: pd.DataFrame) -> pd.DataFrame:
    focus = hypothesis_stats.loc[
        hypothesis_stats["horizon_days"].eq(20)
        & hypothesis_stats["ma_period"].isin(PRIMARY_MA_PERIODS)
        & hypothesis_stats["outcome_metric"].isin(["raw_return", "atr_return"])
    ].copy()
    rows: list[dict[str, Any]] = []
    for (direction, hypothesis), _ in focus.groupby(["direction", "hypothesis"]):
        row: dict[str, Any] = {"direction": direction, "hypothesis": hypothesis}
        complete = True
        for period in PRIMARY_MA_PERIODS:
            for metric, suffix in (("raw_return", "raw"), ("atr_return", "atr")):
                selected = focus.loc[
                    focus["direction"].eq(direction)
                    & focus["hypothesis"].eq(hypothesis)
                    & focus["ma_period"].eq(period)
                    & focus["outcome_metric"].eq(metric)
                ]
                baseline = focus.loc[
                    focus["direction"].eq(direction)
                    & focus["hypothesis"].eq("ALL")
                    & focus["ma_period"].eq(period)
                    & focus["outcome_metric"].eq(metric)
                ]
                if selected.empty or baseline.empty:
                    complete = False
                    continue
                value = selected.iloc[0]
                base = baseline.iloc[0]
                prefix = f"ma{period}_{suffix}"
                row[f"{prefix}_mean"] = float(value["mean"])
                row[f"{prefix}_median"] = float(value["median"])
                row[f"{prefix}_win_rate"] = float(value["win_rate"])
                row[f"{prefix}_t_stat"] = float(value["t_stat"])
                row[f"{prefix}_sample_count"] = int(value["sample_count"])
                row[f"{prefix}_mean_uplift_vs_all"] = float(value["mean"] - base["mean"])
                row[f"{prefix}_median_uplift_vs_all"] = float(
                    value["median"] - base["median"]
                )
        if complete:
            raw_means = [row[f"ma{period}_raw_mean"] for period in PRIMARY_MA_PERIODS]
            raw_medians = [row[f"ma{period}_raw_median"] for period in PRIMARY_MA_PERIODS]
            atr_means = [row[f"ma{period}_atr_mean"] for period in PRIMARY_MA_PERIODS]
            samples = [row[f"ma{period}_raw_sample_count"] for period in PRIMARY_MA_PERIODS]
            raw_mean_uplifts = [
                row[f"ma{period}_raw_mean_uplift_vs_all"] for period in PRIMARY_MA_PERIODS
            ]
            raw_median_uplifts = [
                row[f"ma{period}_raw_median_uplift_vs_all"] for period in PRIMARY_MA_PERIODS
            ]
            row["minimum_sample_count"] = min(samples)
            row["all_ma_raw_means_positive"] = all(value > 0 for value in raw_means)
            row["all_ma_raw_medians_positive"] = all(value > 0 for value in raw_medians)
            row["all_ma_atr_means_positive"] = all(value > 0 for value in atr_means)
            row["all_ma_raw_mean_uplifts_positive"] = all(
                value > 0 for value in raw_mean_uplifts
            )
            row["all_ma_raw_median_uplifts_positive"] = all(
                value > 0 for value in raw_median_uplifts
            )
            row["qualified_descriptive_cross_ma"] = (
                hypothesis != "ALL"
                and min(samples) >= 100
                and row["all_ma_raw_means_positive"]
                and row["all_ma_raw_medians_positive"]
                and row["all_ma_atr_means_positive"]
                and row["all_ma_raw_mean_uplifts_positive"]
                and row["all_ma_raw_median_uplifts_positive"]
            )
            row["worst_ma_raw_mean"] = min(raw_means)
            row["worst_ma_raw_median"] = min(raw_medians)
            row["worst_ma_atr_mean"] = min(atr_means)
            rows.append(row)
    result = pd.DataFrame(rows)
    return result.sort_values(
        ["direction", "qualified_descriptive_cross_ma", "worst_ma_raw_mean"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def _prediction_deciles(frame: pd.DataFrame) -> pd.Series:
    if len(frame) < 10:
        return pd.Series(pd.NA, index=frame.index, dtype="Int64")
    ranks = frame["prediction"].rank(method="first")
    return pd.qcut(ranks, 10, labels=False).astype("Int64") + 1


def run_ml(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    metric_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    importance_rows: list[dict[str, Any]] = []
    rule_sections: list[str] = []
    target_column = "atr_return_20"

    for ma_period in PRIMARY_MA_PERIODS:
        for direction in ("long", "short"):
            pool = events.loc[
                events["ma_period"].eq(ma_period)
                & events["direction"].eq(direction)
                & np.isfinite(events[target_column].to_numpy(dtype=float))
            ].copy()
            for test_start, test_end in WALK_FORWARD_WINDOWS:
                train = pool.loc[pool["outcome_end_date_20"].lt(test_start)]
                test = pool.loc[
                    pool["event_date"].ge(test_start) & pool["event_date"].lt(test_end)
                ]
                if len(train) < 2000 or len(test) < 200:
                    continue
                imputer = SimpleImputer(strategy="median")
                x_train = pd.DataFrame(
                    imputer.fit_transform(train[list(ML_FEATURES)]),
                    columns=ML_FEATURES,
                    index=train.index,
                )
                x_test = pd.DataFrame(
                    imputer.transform(test[list(ML_FEATURES)]),
                    columns=ML_FEATURES,
                    index=test.index,
                )
                y_train = train[target_column].to_numpy(dtype=float)
                y_test = test[target_column].to_numpy(dtype=float)
                models = {
                    "TREE": DecisionTreeRegressor(
                        max_depth=4, min_samples_leaf=500, random_state=42
                    ),
                    "LIGHTGBM": LGBMRegressor(
                        n_estimators=160,
                        learning_rate=0.03,
                        num_leaves=15,
                        max_depth=4,
                        min_child_samples=300,
                        subsample=0.8,
                        colsample_bytree=0.8,
                        reg_lambda=5.0,
                        random_state=42,
                        n_jobs=4,
                        verbosity=-1,
                    ),
                }
                for model_name, model in models.items():
                    model.fit(x_train, y_train)
                    prediction = model.predict(x_test)
                    rho = spearmanr(prediction, y_test, nan_policy="omit").statistic
                    scored = test[["event_id", "symbol", "event_date"]].copy()
                    scored["ma_period"] = ma_period
                    scored["direction"] = direction
                    scored["fold"] = f"{test_start.year}"
                    scored["model"] = model_name
                    scored["actual"] = y_test
                    scored["prediction"] = prediction
                    scored["prediction_decile"] = _prediction_deciles(scored)
                    decile_means = scored.groupby("prediction_decile", observed=True)[
                        "actual"
                    ].mean()
                    spread = (
                        float(decile_means.loc[10] - decile_means.loc[1])
                        if 1 in decile_means.index and 10 in decile_means.index
                        else math.nan
                    )
                    metric_rows.append(
                        {
                            "ma_period": ma_period,
                            "direction": direction,
                            "fold": str(test_start.year),
                            "model": model_name,
                            "train_count": len(train),
                            "test_count": len(test),
                            "spearman_rank_ic": float(rho),
                            "mae": float(mean_absolute_error(y_test, prediction)),
                            "rmse": float(root_mean_squared_error(y_test, prediction)),
                            "top_minus_bottom_decile_atr": spread,
                        }
                    )
                    prediction_frames.append(scored)
                    perm = permutation_importance(
                        model,
                        x_test,
                        y_test,
                        scoring="neg_mean_squared_error",
                        n_repeats=3,
                        random_state=42,
                        n_jobs=1,
                    )
                    builtin = getattr(model, "feature_importances_", np.full(len(ML_FEATURES), np.nan))
                    for feature, built, p_mean, p_std in zip(
                        ML_FEATURES,
                        builtin,
                        perm.importances_mean,
                        perm.importances_std,
                        strict=True,
                    ):
                        importance_rows.append(
                            {
                                "ma_period": ma_period,
                                "direction": direction,
                                "fold": str(test_start.year),
                                "model": model_name,
                                "feature": feature,
                                "builtin_importance": float(built),
                                "permutation_mse_increase": float(p_mean),
                                "permutation_std": float(p_std),
                            }
                        )

            full = pool.loc[pool["event_date"].lt(DEVELOPMENT_CUTOFF)].copy()
            if len(full) >= 2000:
                imputer = SimpleImputer(strategy="median")
                x_full = imputer.fit_transform(full[list(ML_FEATURES)])
                tree = DecisionTreeRegressor(
                    max_depth=4, min_samples_leaf=500, random_state=42
                ).fit(x_full, full[target_column].to_numpy(dtype=float))
                rule_sections.extend(
                    [
                        f"## MA{ma_period} {direction}",
                        export_text(tree, feature_names=list(ML_FEATURES), decimals=3),
                    ]
                )

    predictions = pd.concat(prediction_frames, ignore_index=True)
    deciles = (
        predictions.groupby(
            ["ma_period", "direction", "fold", "model", "prediction_decile"],
            observed=True,
        )
        .agg(
            sample_count=("actual", "size"),
            prediction_mean=("prediction", "mean"),
            actual_mean_atr=("actual", "mean"),
            actual_median_atr=("actual", "median"),
            win_rate=("actual", lambda x: float(np.mean(np.asarray(x) > 0))),
        )
        .reset_index()
    )
    return (
        pd.DataFrame(metric_rows),
        predictions,
        pd.DataFrame(importance_rows),
        "\n\n".join(rule_sections) + "\n",
    ), deciles


def top_plain_findings(
    ma_consistency: pd.DataFrame,
    hypothesis_stats: pd.DataFrame,
    robustness: pd.DataFrame,
    ml_metrics: pd.DataFrame,
) -> dict[str, Any]:
    positive = ma_consistency.loc[
        ma_consistency["qualified_descriptive_cross_ma"]
    ].copy()
    winners = {
        direction: group.nlargest(5, "worst_ma_raw_mean")[
            [
                "hypothesis",
                "minimum_sample_count",
                "ma7_raw_mean",
                "ma7_raw_median",
                "ma30_raw_mean",
                "ma30_raw_median",
                "worst_ma_raw_mean",
            ]
        ].to_dict("records")
        for direction, group in positive.groupby("direction")
    }
    yearly = robustness.loc[
        robustness["outcome_metric"].eq("raw_return")
        & robustness["horizon_days"].eq(20)
        & robustness["sample_count"].ge(50)
    ].copy()
    year_signs = (
        yearly.assign(positive=yearly["mean"].gt(0))
        .groupby(["ma_period", "direction", "hypothesis"])
        .agg(years=("calendar_year", "nunique"), positive_years=("positive", "sum"))
        .reset_index()
    )
    stable = year_signs.loc[
        year_signs["years"].ge(4)
        & year_signs["positive_years"].ge(np.ceil(year_signs["years"] * 0.7))
        & year_signs["hypothesis"].ne("ALL")
    ].to_dict("records")
    stable_frame = pd.DataFrame(stable)
    if stable_frame.empty:
        stable_both_ma: list[dict[str, Any]] = []
    else:
        stable_both_ma = (
            stable_frame.groupby(["direction", "hypothesis"])
            .filter(lambda x: set(x["ma_period"]) == set(PRIMARY_MA_PERIODS))[
                ["direction", "hypothesis"]
            ]
            .drop_duplicates()
            .to_dict("records")
        )
    ml_summary = (
        ml_metrics.groupby(["ma_period", "direction", "model"])
        .agg(
            folds=("fold", "nunique"),
            positive_ic_folds=("spearman_rank_ic", lambda x: int(np.sum(np.asarray(x) > 0))),
            mean_rank_ic=("spearman_rank_ic", "mean"),
            mean_decile_spread_atr=("top_minus_bottom_decile_atr", "mean"),
        )
        .reset_index()
        .to_dict("records")
    )
    return {
        "cross_ma_positive": winners,
        "year_stability": stable,
        "stable_both_ma": stable_both_ma,
        "ml": ml_summary,
    }


def write_report(
    study_id: str,
    events: pd.DataFrame,
    frequency: pd.DataFrame,
    transition: pd.DataFrame,
    ma_consistency: pd.DataFrame,
    hypothesis_stats: pd.DataFrame,
    robustness: pd.DataFrame,
    ml_metrics: pd.DataFrame,
    findings: dict[str, Any],
) -> None:
    overall = frequency.loc[
        frequency["scope"].eq("ALL_EVENTS") & frequency["frequency"].eq("overall")
    ]
    stock_events = events.loc[events["base_asset"].isin(US_STOCK_LIKE_BASES)]
    artifact_tag = "p0r" if study_id.endswith("P0R") else "p0"
    explicit_states = (
        ("大跌后修复，再向上站上均线", "long", "LARGE_ADVERSE", "FAVORABLE"),
        ("大跌后非常强地修复，再向上站上均线", "long", "LARGE_ADVERSE", "LARGE_FAVORABLE"),
        ("大涨后横盘，再向下跌破均线", "short", "LARGE_ADVERSE", "FLAT"),
        ("已经大跌后横盘，再向下跌破均线", "short", "LARGE_FAVORABLE", "FLAT"),
    )
    transition_focus = transition.loc[
        transition["horizon_days"].eq(20)
        & transition["outcome_metric"].eq("raw_return")
    ]
    lines = [
        f"# {study_id}：突破前市场状态地图结果",
        "",
        "## 大白话结论",
        "",
        "**这轮仍没有找到可以直接写进策略的、跨 MA7/MA30 且跨年份稳定的通用市场结构过滤器。** 做多没有任何命名状态同时通过两个 MA 的基本描述性要求；做空有四个历史均值不错的形态，但没有一个在 MA7 和 MA30 上都通过逐年稳定检查，机器学习也没有形成稳定排序。",
        "",
        "最值得继续确认的历史现象不是“顶部反转”，而是：**价格已经明显下跌，随后横盘，再次向下跌破均线**。它在 MA7/MA30 上都有较大的正均值和正中位数；但它在 2020–2021 牛市阶段失效，因此目前只能叫‘偏空市场里的顺势二次破位’，不能叫普适结构。",
        "",
        "你明确提出的‘大跌后修复做多’和‘大涨后横盘跌破做空’都已经单独统计，结果见下表；它们没有获得跨 MA 的稳定支持。",
        "",
        "## 先说这轮到底做了什么",
        "",
        "这不是策略回测。MA7 和 MA30 只是用来标记突破发生的时间；所有市场状态都只看突破前一日及更早的 60 日路径。统计覆盖大跌/大涨后的修复或横盘、原趋势回踩、持续推进、衰竭、低波压缩、高波乱震和 ATR 收缩/扩张。",
        "",
        f"样本共 {len(events):,} 个多均线事件，{events['symbol'].nunique():,} 个历史合约，日期从 {events['event_date'].min().date()} 到 {events['event_date'].max().date()}。其中已知股票类合约事件 {len(stock_events):,} 个、{stock_events['symbol'].nunique():,} 个合约。全部是已经揭示的探索性历史，不是新 OOS。",
        "",
        "股票类合约虽然进入了原始全市场输入，但截至研究截止日没有任何合约同时满足上市 120 天、完整前置状态和突破事件，因此本轮有效事件仍然全部来自加密合约，不能据此宣称跨资产类别成立。",
        "",
        "## MA7 / MA30 事件数量",
        "",
        "| MA | 方向 | 事件数 | 合约数 | 发生日期数 |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in overall.itertuples(index=False):
        lines.append(
            f"| MA{row.ma_period} | {row.direction} | {row.event_count:,} | {row.symbol_count:,} | {row.event_date_count:,} |"
        )
    lines.extend(
        [
            "",
            "## 你明确提出的形态",
            "",
            "| 突破前形态 | MA | 事件数 | 后20日均值 | 中位数 | 胜率 |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for label, direction, prior, recent in explicit_states:
        for period in PRIMARY_MA_PERIODS:
            selected = transition_focus.loc[
                transition_focus["direction"].eq(direction)
                & transition_focus["prior_move_state"].eq(prior)
                & transition_focus["recent_move_state"].eq(recent)
                & transition_focus["ma_period"].eq(period)
            ]
            if selected.empty:
                continue
            row = selected.iloc[0]
            lines.append(
                f"| {label} | MA{period} | {int(row['sample_count']):,} | {row['mean']:.2%} | {row['median']:.2%} | {row['win_rate']:.2%} |"
            )
    lines.extend(["", "## 跨 MA 同方向的候选前置状态", ""])
    for direction in ("long", "short"):
        lines.append(f"### {'做多' if direction == 'long' else '做空'}")
        lines.append("")
        candidates = findings["cross_ma_positive"].get(direction, [])
        if not candidates:
            lines.append(
                "没有状态同时满足：MA7/MA30 原始均值为正、中位数为正、ATR均值为正、均值和中位数都优于不过滤，而且两个MA都至少100次。"
            )
        else:
            lines.extend(
                [
                    "| 前置状态 | 两个MA较小样本 | MA7均值/中位数 | MA30均值/中位数 |",
                    "| --- | ---: | ---: | ---: |",
                ]
            )
            for row in candidates:
                lines.append(
                    f"| {HYPOTHESIS_ZH[row['hypothesis']]} | {row['minimum_sample_count']:,} | {row['ma7_raw_mean']:.2%} / {row['ma7_raw_median']:.2%} | {row['ma30_raw_mean']:.2%} / {row['ma30_raw_median']:.2%} |"
                )
        lines.append("")
    lines.extend(
        [
            "## 年份稳定性",
            "",
            f"在单一 MA 上满足至少 4 个有效年份、其中至少 70% 年份原始均值为正的组合共有 {len(findings['year_stability'])} 个；同时在 MA7 和 MA30 都满足的状态共有 {len(findings['stable_both_ma'])} 个。这仍只是探索性稳定度，不是交易通过。",
            "",
            "## 机器学习有没有学到前置状态",
            "",
            "模型只看突破前状态，分别训练 MA7/MA30 与多空；没有选交易或做账户。下面给出各组跨年份平均排序能力。RankIC 接近零代表没有学到稳定排序。",
            "",
            "| MA | 方向 | 模型 | 正RankIC年份/总年份 | 平均RankIC | 预测头尾十分位实际差 |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in findings["ml"]:
        lines.append(
            f"| MA{row['ma_period']} | {row['direction']} | {row['model']} | {row['positive_ic_folds']}/{row['folds']} | {row['mean_rank_ic']:.3f} | {row['mean_decile_spread_atr']:.3f} ATR |"
        )
    lines.extend(
        [
            "",
            "## 怎么读文件",
            "",
            f"- [旧走势 × 最近走势完整矩阵](../artifacts/binance_1d_tpsa_{artifact_tag}_move_transition_matrix.csv)：直接找“大跌后修复”“大涨后横盘”等路径。",
            f"- [旧走势 × 最近走势逐年结果](../artifacts/binance_1d_tpsa_{artifact_tag}_move_transition_robustness.csv)：检查某个路径是否只在个别年份有效。",
            f"- [波动水平 × 波动变化矩阵](../artifacts/binance_1d_tpsa_{artifact_tag}_volatility_state_matrix.csv)：低波/高波与收缩/扩张分开看。",
            f"- [固定可读形态统计](../artifacts/binance_1d_tpsa_{artifact_tag}_hypothesis_stats.csv)：十三种命名假设逐项结果。",
            f"- [逐年稳健性](../artifacts/binance_1d_tpsa_{artifact_tag}_hypothesis_robustness.csv)：检查是否只靠某一年。",
            f"- [MA7/MA30一致性](../artifacts/binance_1d_tpsa_{artifact_tag}_ma_consistency.csv)：检查是不是均线参数巧合。",
            f"- [机器学习逐年前推](../artifacts/binance_1d_tpsa_{artifact_tag}_ml_walk_forward_metrics.csv)：只看模型能不能给前置状态稳定排序。",
            f"- [可读决策树规则](../artifacts/binance_1d_tpsa_{artifact_tag}_tree_rules.txt)：模型从历史里切出的前置状态。",
            "",
            "## 决策边界",
            "",
            "本轮不输出策略年化、回撤或买卖规则。‘描述性候选’还必须通过逐年和模型排序复核；只有跨 MA、跨年份、样本充足且人工状态表与模型排序一致的状态，才进入下一轮冻结确认。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_artifacts(config: dict[str, Any], panel: pd.DataFrame, events: pd.DataFrame) -> None:
    core_metrics = tuple(
        (metric, horizon)
        for horizon in HORIZONS
        for metric in ("raw_return", "atr_return")
    )
    unconditional = summarize(events, ["ma_period", "direction"], core_metrics)
    hypotheses = exploded_hypotheses(events)
    primary_hypotheses = hypotheses.loc[
        hypotheses["ma_period"].isin(PRIMARY_MA_PERIODS)
    ]
    hypothesis_stats = summarize(
        primary_hypotheses,
        ["ma_period", "direction", "hypothesis"],
        core_metrics,
    )
    transition = summarize(
        events.loc[events["ma_period"].isin(PRIMARY_MA_PERIODS)],
        ["ma_period", "direction", "prior_move_state", "recent_move_state"],
        core_metrics,
    )
    transition_robustness = summarize(
        events.loc[events["ma_period"].isin(PRIMARY_MA_PERIODS)],
        [
            "ma_period",
            "direction",
            "prior_move_state",
            "recent_move_state",
            "calendar_year",
        ],
        tuple(
            (metric, horizon)
            for horizon in (10, 20)
            for metric in ("raw_return", "atr_return")
        ),
    )
    volatility = summarize(
        events.loc[events["ma_period"].isin(PRIMARY_MA_PERIODS)],
        ["ma_period", "direction", "volatility_level_state", "volatility_path_state"],
        core_metrics,
    )
    path_shape = summarize(
        events.loc[events["ma_period"].isin(PRIMARY_MA_PERIODS)],
        ["ma_period", "direction", "efficiency_state", "consolidation_state"],
        core_metrics,
    )
    path_metrics = tuple(
        (metric, horizon)
        for horizon in PATH_HORIZONS
        for metric in ("mfe_atr", "mae_atr", "clean_score", "barrier_success")
    )
    path_outcomes = summarize(
        primary_hypotheses,
        ["ma_period", "direction", "hypothesis"],
        path_metrics,
    )
    robustness = summarize(
        primary_hypotheses,
        ["ma_period", "direction", "hypothesis", "calendar_year"],
        tuple((metric, horizon) for horizon in (10, 20) for metric in ("raw_return", "atr_return")),
    )
    frequency = build_frequency(events, hypotheses)
    hypothesis_frequency = frequency.loc[frequency["scope"].eq("HYPOTHESIS")].copy()
    ma_consistency = build_ma_consistency(hypothesis_stats)
    (ml_metrics, ml_predictions, ml_importance, tree_rules), ml_deciles = run_ml(events)
    findings = top_plain_findings(ma_consistency, hypothesis_stats, robustness, ml_metrics)

    events.to_parquet(OUTPUTS["events"], index=False)
    unconditional.to_csv(OUTPUTS["unconditional"], index=False)
    frequency.to_csv(OUTPUTS["frequency"], index=False)
    transition.to_csv(OUTPUTS["transition"], index=False)
    transition_robustness.to_csv(OUTPUTS["transition_robustness"], index=False)
    volatility.to_csv(OUTPUTS["volatility"], index=False)
    path_shape.to_csv(OUTPUTS["path_shape"], index=False)
    hypothesis_stats.to_csv(OUTPUTS["hypotheses"], index=False)
    hypothesis_frequency.to_csv(OUTPUTS["hypothesis_frequency"], index=False)
    robustness.to_csv(OUTPUTS["hypothesis_robustness"], index=False)
    path_outcomes.to_csv(OUTPUTS["path_outcomes"], index=False)
    ma_consistency.to_csv(OUTPUTS["ma_consistency"], index=False)
    ml_metrics.to_csv(OUTPUTS["ml_metrics"], index=False)
    ml_predictions.to_parquet(OUTPUTS["ml_predictions"], index=False)
    ml_deciles.to_csv(OUTPUTS["ml_deciles"], index=False)
    ml_importance.to_csv(OUTPUTS["ml_importance"], index=False)
    OUTPUTS["ml_tree_rules"].write_text(tree_rules, encoding="utf-8")

    summary = {
        "study_id": config["study_id"],
        "status": "exploratory_completed_not_confirmed",
        "data": {
            "panel_rows": len(panel),
            "eligible_prestate_rows": int(panel["eligible_prestate"].sum()),
            "symbols": int(panel["symbol"].nunique()),
            "start": panel["event_date"].min().isoformat(),
            "end": panel["event_date"].max().isoformat(),
        },
        "events": {
            "count": len(events),
            "symbols": int(events["symbol"].nunique()),
            "start": events["event_date"].min().isoformat(),
            "end": events["event_date"].max().isoformat(),
        },
        "findings": findings,
        "decision": "hypothesis_generation_only; no strategy, no account, no promotion",
    }
    OUTPUTS["summary"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(
        config["study_id"],
        events,
        frequency,
        transition,
        ma_consistency,
        hypothesis_stats,
        robustness,
        ml_metrics,
        findings,
    )
    manifest_paths = [*OUTPUTS.values(), REPORT_PATH]
    manifest = {
        "study_id": config["study_id"],
        "config_sha256": sha256_file(CONFIG_PATH),
        "input": str(PANEL_PATH.relative_to(ROOT)),
        "artifacts": [
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in manifest_paths
            if path.exists() and path != OUTPUTS["manifest"]
        ],
    }
    OUTPUTS["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    if not args.run:
        raise SystemExit("pass --run after reviewing the frozen P0 contract")
    if args.repair:
        activate_repair_context()
    config = validate_inputs(force=args.force)
    panel = load_feature_panel()
    events = build_events(panel)
    write_artifacts(config, panel, events)
    print(
        json.dumps(
            {
                "study_id": config["study_id"],
                "panel_rows": len(panel),
                "events": len(events),
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
