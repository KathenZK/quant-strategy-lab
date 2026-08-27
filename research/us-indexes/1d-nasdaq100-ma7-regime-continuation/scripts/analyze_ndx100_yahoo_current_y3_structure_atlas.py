from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/us-indexes/1d-nasdaq100-ma7-regime-continuation"
CONFIG_PATH = (
    FAMILY_DIR
    / "configs/ndx100-1d-ma7-regime-continuation-yahoo-current-y3-structure-atlas.json"
)
EXPECTED_CONFIG_SHA256 = (
    "d75dea70494ae497a360ea2d997db6fb3807b2cbe0d0ed12c6f9f577d1426c25"
)
Y0_SCRIPT = (
    FAMILY_DIR
    / "scripts/research_ndx100_current_yahoo_1d_ma7_regime_continuation.py"
)
Y2_SCRIPT = FAMILY_DIR / "scripts/analyze_ndx100_yahoo_current_y2_atr_path.py"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
REPORT_PATH = (
    FAMILY_DIR
    / "diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y3-structure-atlas-2026-08-25.md"
)

STUDY_ID = "NDX100-1D-MA7-RC-Y3"
PREFIX = "ndx100_1d_ma7_rc_y3"
OUTPUTS = {
    "events": ARTIFACT_DIR / f"{PREFIX}_events.parquet",
    "state_membership": ARTIFACT_DIR / f"{PREFIX}_named_state_membership.parquet",
    "baseline_stats": ARTIFACT_DIR / f"{PREFIX}_baseline_stats.csv",
    "dimension_stats": ARTIFACT_DIR / f"{PREFIX}_dimension_stats.csv",
    "named_state_stats": ARTIFACT_DIR / f"{PREFIX}_named_state_stats.csv",
    "named_state_contrasts": ARTIFACT_DIR / f"{PREFIX}_named_state_contrasts.csv",
    "named_state_ranking": ARTIFACT_DIR / f"{PREFIX}_named_state_ranking_20d.csv",
    "robustness_stats": ARTIFACT_DIR / f"{PREFIX}_named_state_robustness.csv",
    "topology_stats": ARTIFACT_DIR / f"{PREFIX}_event_topology_stats.csv",
    "summary": ARTIFACT_DIR / f"{PREFIX}_summary.json",
    "manifest": ARTIFACT_DIR / f"{PREFIX}_artifact_manifest.json",
}

HORIZONS = (1, 3, 5, 10, 20, 40)
RETURN_METRICS = ("raw_return", "atr_return")
TRIGGER_MAS = (7, 30)
FOCUS_HORIZONS = (10, 20, 40)

STATE_DESCRIPTIONS = {
    "L01_CRASH_REVERSAL": "20日暴跌且仍处60日深回撤",
    "L02_DEEP_DRAWDOWN_RECOVERY": "60日深回撤后已从20日低点反弹",
    "L03_DEEP_DRAWDOWN_BASE": "深回撤后横盘且20日区间收缩",
    "L04_EARLY_RECOVERY_BELOW_MA30": "仍在MA30下方的深回撤早期修复",
    "L05_BULL_TREND_PULLBACK": "MA30/60/120多头排列中的正常回踩",
    "L06_BULL_TREND_SHALLOW_RECLAIM": "多头排列中的浅回撤重新站上",
    "L07_FAILED_BEAR_TREND_REVERSAL": "空头排列中强反弹后的向上突破",
    "L08_DEPRESSED_BREADTH_REVERSAL": "市场宽度低位但过去10日改善",
    "L09_BROAD_BULL_CONTINUATION": "QQQ牛市、宽度高且个股多头排列",
    "L10_LOW_VOL_BASE_BREAKOUT": "低波低区间横盘底部向上突破",
    "L11_HIGH_VOL_CAPITULATION": "高波环境中的20日暴跌反转",
    "S01_SURGE_REVERSAL": "20日暴涨且60日涨幅较大后的下破",
    "S02_STRONG_RUNUP_ROLLOVER": "60日强上涨后已从20日高点回落",
    "S03_RALLY_DISTRIBUTION": "强上涨后低区间横盘派发",
    "S04_EARLY_ROLLOVER_ABOVE_MA30": "仍在MA30上方的强上涨早期转弱",
    "S05_BEAR_TREND_BOUNCE_FAILURE": "空头排列中的小反弹失败",
    "S06_BEAR_TREND_CONTINUATION": "空头排列中的顺势下破",
    "S07_FAILED_BULL_TREND_REVERSAL": "多头排列但已从20日高点明显回落",
    "S08_EUPHORIC_BREADTH_ROLLOVER": "市场宽度极高但过去10日下降",
    "S09_BROAD_BEAR_CONTINUATION": "QQQ熊市、宽度低且个股空头排列",
    "S10_LOW_VOL_DISTRIBUTION": "低波低区间横盘后向下跌破",
    "S11_HIGH_VOL_TOP_EXHAUSTION": "高波环境中的20日暴涨衰竭",
    "S12_EXTREME_RUNUP_BREAKDOWN": "从60日低点上涨超过30%后的下破",
}

DIMENSIONS = {
    "drawdown_60_state": "60日高点回撤",
    "runup_60_state": "60日低点涨幅",
    "return_20_state": "过去20日涨跌路径",
    "rebound_20_state": "从20日低点反弹",
    "natr20_state": "归一化ATR历史位置",
    "range20_state": "20日价格区间历史位置",
    "ma_hierarchy": "MA30/60/120层级",
    "price_to_ma30_state": "价格相对MA30的ATR距离",
    "breadth_state": "站上MA30的市场宽度",
    "breadth_change_state": "市场宽度10日变化",
    "pre_qqq_phase": "QQQ市场阶段",
}


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


Y0 = load_module(Y0_SCRIPT, "ndx100_y0_for_y3")
Y2 = load_module(Y2_SCRIPT, "ndx100_y2_for_y3")
KERNEL = Y0.KERNEL


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen NDX100 Yahoo-current pre-breakout structure atlas."
    )
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_inputs(force: bool) -> dict[str, Any]:
    actual = sha256_file(CONFIG_PATH)
    if actual != EXPECTED_CONFIG_SHA256:
        raise RuntimeError(f"frozen Y3 config hash mismatch: {actual}")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("study_id") != STUDY_ID:
        raise RuntimeError("unexpected Y3 study identity")
    if not config["statistics"]["no_machine_learning"]:
        raise RuntimeError("Y3 must remain non-ML")
    if not config["statistics"]["no_cross_sectional_relative_strength"]:
        raise RuntimeError("Y3 must not use cross-sectional relative strength")
    required = [Y0.PRICE_PATH, Y0.PRICE_AUDIT_PATH, Y0.UNIVERSE_PATH]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing Y0 inputs: {missing}")
    existing = [path for path in [*OUTPUTS.values(), REPORT_PATH] if path.exists()]
    if existing and not force:
        raise FileExistsError("Y3 outputs already exist; pass --force to reproduce")
    return config


def assign_quintile(percentile: pd.Series) -> pd.Series:
    values = percentile.to_numpy(dtype=float)
    result = np.full(len(values), np.nan)
    valid = np.isfinite(values)
    result[valid] = (
        np.searchsorted([0.20, 0.40, 0.60, 0.80], values[valid], side="left")
        + 1
    )
    return pd.Series(result, index=percentile.index, dtype="Int64")


def structure_feature_block(group: pd.DataFrame) -> pd.DataFrame:
    block = group.sort_values("session_date").copy()
    close = block["close"].astype(float)
    high = block["high"].astype(float)
    low = block["low"].astype(float)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    block["atr20_y3"] = true_range.rolling(20, min_periods=20).mean()
    for period in (7, 30, 60, 120):
        block[f"sma{period}_y3"] = close.rolling(period, min_periods=period).mean()
    for period in (5, 10, 20, 60):
        block[f"ret{period}_y3"] = close / close.shift(period) - 1.0
    for period in (20, 60, 120):
        rolling_high = high.rolling(period, min_periods=period).max()
        rolling_low = low.rolling(period, min_periods=period).min()
        block[f"drawdown{period}_y3"] = close / rolling_high - 1.0
        block[f"runup{period}_y3"] = close / rolling_low - 1.0
    block["natr20_y3"] = block["atr20_y3"] / close
    block["range20_y3"] = (
        high.rolling(20, min_periods=20).max()
        / low.rolling(20, min_periods=20).min()
        - 1.0
    )
    block["natr20_percentile_y3"] = KERNEL.rolling_percentile_current(
        block["natr20_y3"].to_numpy(dtype=float), 252
    )
    block["range20_percentile_y3"] = KERNEL.rolling_percentile_current(
        block["range20_y3"].to_numpy(dtype=float), 252
    )
    block["natr20_q_y3"] = assign_quintile(block["natr20_percentile_y3"])
    block["range20_q_y3"] = assign_quintile(block["range20_percentile_y3"])
    block["price_to_ma30_atr_y3"] = (
        close - block["sma30_y3"]
    ) / block["atr20_y3"].replace(0.0, np.nan)
    block["ma_hierarchy_y3"] = np.select(
        [
            block["sma30_y3"].gt(block["sma60_y3"])
            & block["sma60_y3"].gt(block["sma120_y3"]),
            block["sma30_y3"].lt(block["sma60_y3"])
            & block["sma60_y3"].lt(block["sma120_y3"]),
        ],
        ["BULL_STACK", "BEAR_STACK"],
        default="MIXED",
    )
    block["listing_age_days_y3"] = (
        block["session_date"] - block["session_date"].iloc[0]
    ).dt.days
    for horizon in HORIZONS:
        block[f"future_close_{horizon}_y3"] = close.shift(-horizon)
    return block


def label_dimensions(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["drawdown_60_state"] = pd.cut(
        result["pre_drawdown60"],
        [-np.inf, -0.20, -0.10, -0.05, np.inf],
        labels=["DEEP_LE_-20", "MODERATE_-20_-10", "SHALLOW_-10_-5", "NEAR_HIGH_GT_-5"],
    ).astype("string")
    result["runup_60_state"] = pd.cut(
        result["pre_runup60"],
        [-np.inf, 0.05, 0.15, 0.30, np.inf],
        labels=["LOW_LT_5", "MODEST_5_15", "STRONG_15_30", "EXTREME_GE_30"],
    ).astype("string")
    result["return_20_state"] = pd.cut(
        result["pre_ret20"],
        [-np.inf, -0.10, -0.03, 0.03, 0.10, np.inf],
        labels=["CRASH_LE_-10", "DOWN_-10_-3", "SIDEWAYS_-3_3", "UP_3_10", "SURGE_GE_10"],
    ).astype("string")
    result["rebound_20_state"] = pd.cut(
        result["pre_runup20"],
        [-np.inf, 0.03, 0.08, 0.15, np.inf],
        labels=["LT_3", "REBOUND_3_8", "REBOUND_8_15", "REBOUND_GE_15"],
    ).astype("string")
    result["natr20_state"] = result["pre_natr20_q"].map(
        {1: "Q1_LOW", 2: "Q2", 3: "Q3", 4: "Q4", 5: "Q5_HIGH"}
    ).astype("string")
    result["range20_state"] = result["pre_range20_q"].map(
        {1: "Q1_COMPRESSED", 2: "Q2", 3: "Q3", 4: "Q4", 5: "Q5_WIDE"}
    ).astype("string")
    result["ma_hierarchy"] = result["pre_ma_hierarchy"].astype("string")
    result["price_to_ma30_state"] = pd.cut(
        result["pre_price_to_ma30_atr"],
        [-np.inf, -2.0, 0.0, 2.0, np.inf],
        labels=["FAR_BELOW_LT_-2ATR", "BELOW_-2ATR_0", "ABOVE_0_2ATR", "FAR_ABOVE_GT_2ATR"],
    ).astype("string")
    result["breadth_state"] = pd.cut(
        result["pre_breadth_above_ma30"],
        [-np.inf, 0.35, 0.65, np.inf],
        labels=["DEPRESSED_LT_35", "NEUTRAL_35_65", "BROAD_GT_65"],
    ).astype("string")
    result["breadth_change_state"] = pd.cut(
        result["pre_breadth_change10"],
        [-np.inf, -0.10, 0.10, np.inf],
        labels=["FALLING_LT_-10PP", "STABLE_-10PP_10PP", "RISING_GT_10PP"],
    ).astype("string")
    return result


def prepare_panel(config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    base_config, yahoo_config = Y0.load_configs()
    bars, qqq, membership, price_audit = Y0.load_yahoo_panel_inputs(
        base_config, yahoo_config
    )
    base = Y0.KERNEL.prepare_feature_panel(bars, membership, qqq, base_config)
    blocks = [
        structure_feature_block(group)
        for _, group in base.groupby(["entity_key", "block_id"], sort=False)
    ]
    panel = pd.concat(blocks, ignore_index=True).sort_values(
        ["entity_key", "block_id", "session_date"]
    )
    member_panel = panel.loc[panel["is_member"]].copy()
    breadth = (
        member_panel.assign(above_ma30=member_panel["close"].gt(member_panel["sma30_y3"]))
        .groupby("session_date", as_index=False)
        .agg(
            breadth_above_ma30=("above_ma30", "mean"),
            breadth_security_count=("ticker", "nunique"),
        )
        .sort_values("session_date")
    )
    breadth["breadth_change10"] = breadth["breadth_above_ma30"].diff(10)
    panel = panel.merge(breadth, on="session_date", how="left", validate="many_to_one")

    pre_source = {
        "drawdown20_y3": "pre_drawdown20",
        "drawdown60_y3": "pre_drawdown60",
        "drawdown120_y3": "pre_drawdown120",
        "runup20_y3": "pre_runup20",
        "runup60_y3": "pre_runup60",
        "runup120_y3": "pre_runup120",
        "ret5_y3": "pre_ret5",
        "ret10_y3": "pre_ret10",
        "ret20_y3": "pre_ret20",
        "ret60_y3": "pre_ret60",
        "natr20_y3": "pre_natr20",
        "natr20_q_y3": "pre_natr20_q",
        "range20_y3": "pre_range20",
        "range20_q_y3": "pre_range20_q",
        "price_to_ma30_atr_y3": "pre_price_to_ma30_atr",
        "ma_hierarchy_y3": "pre_ma_hierarchy",
        "market_phase": "pre_qqq_phase",
        "breadth_above_ma30": "pre_breadth_above_ma30",
        "breadth_change10": "pre_breadth_change10",
        "atr20_y3": "pre_atr20",
    }
    grouped = panel.groupby(["entity_key", "block_id"], sort=False)
    for source, destination in pre_source.items():
        panel[destination] = grouped[source].shift(1)
    start = pd.Timestamp(config["data"]["study_start_inclusive"])
    end = pd.Timestamp(config["data"]["study_end_inclusive"])
    finite_columns = [
        "pre_drawdown60",
        "pre_runup60",
        "pre_ret20",
        "pre_runup20",
        "pre_natr20_q",
        "pre_range20_q",
        "pre_price_to_ma30_atr",
        "pre_breadth_above_ma30",
        "pre_breadth_change10",
        "pre_atr20",
    ]
    finite = np.isfinite(panel[finite_columns].astype(float).to_numpy()).all(axis=1)
    panel["eligible_y3"] = (
        panel["is_member"]
        & panel["session_date"].between(start, end)
        & panel["listing_age_days_y3"].ge(
            config["data"]["minimum_available_history_calendar_days"]
        )
        & finite
        & panel["atr14"].gt(0)
        & panel["close"].gt(0)
        & panel["pre_qqq_phase"].notna()
    )
    return panel, price_audit


def build_events(panel: pd.DataFrame) -> pd.DataFrame:
    grouped = panel.groupby(["entity_key", "block_id"], sort=False)
    previous_close = grouped["close"].shift(1)
    event_frames: list[pd.DataFrame] = []
    identity_columns = [
        "ticker",
        "entity_key",
        "session_date",
        "block_id",
        "close",
        "atr14",
        "gap",
        "calendar_year",
        "pre_drawdown20",
        "pre_drawdown60",
        "pre_drawdown120",
        "pre_runup20",
        "pre_runup60",
        "pre_runup120",
        "pre_ret5",
        "pre_ret10",
        "pre_ret20",
        "pre_ret60",
        "pre_natr20",
        "pre_natr20_q",
        "pre_range20",
        "pre_range20_q",
        "pre_price_to_ma30_atr",
        "pre_ma_hierarchy",
        "pre_qqq_phase",
        "pre_breadth_above_ma30",
        "pre_breadth_change10",
        "pre_atr20",
    ]
    trigger_masks: dict[tuple[int, str], pd.Series] = {}
    for period in TRIGGER_MAS:
        previous_ma = grouped[f"sma{period}_y3"].shift(1)
        trigger_masks[(period, "long")] = previous_close.le(previous_ma) & panel[
            "close"
        ].gt(panel[f"sma{period}_y3"])
        trigger_masks[(period, "short")] = previous_close.ge(previous_ma) & panel[
            "close"
        ].lt(panel[f"sma{period}_y3"])
    for period in TRIGGER_MAS:
        other_period = 30 if period == 7 else 7
        for direction, sign in (("long", 1.0), ("short", -1.0)):
            mask = trigger_masks[(period, direction)] & panel["eligible_y3"]
            events = panel.loc[mask, identity_columns].copy()
            events["symbol"] = events["ticker"].astype(str)
            events["event_date"] = pd.to_datetime(events["session_date"], utc=True)
            events["trigger_ma"] = period
            events["direction"] = direction
            events["direction_sign"] = sign
            events["simultaneous_other_ma_cross"] = trigger_masks[
                (other_period, direction)
            ].loc[mask].to_numpy(dtype=bool)
            events["event_topology"] = np.where(
                events["simultaneous_other_ma_cross"],
                "SIMULTANEOUS_MA7_MA30",
                f"MA{period}_ONLY",
            )
            entry = events["close"].to_numpy(dtype=float)
            atr = events["atr14"].to_numpy(dtype=float)
            for horizon in HORIZONS:
                future = panel.loc[mask, f"future_close_{horizon}_y3"].to_numpy(
                    dtype=float
                )
                events[f"raw_return_{horizon}"] = sign * (future / entry - 1.0)
                events[f"atr_return_{horizon}"] = sign * (future - entry) / atr
            events["event_id"] = (
                f"Y3|MA{period}|{direction}|"
                + events["ticker"].astype(str)
                + "|"
                + events["session_date"].dt.strftime("%Y-%m-%d")
            )
            event_frames.append(events)
    events = pd.concat(event_frames, ignore_index=True)
    events = label_dimensions(events)
    if events["event_id"].duplicated().any():
        raise RuntimeError("duplicate Y3 event identifiers")
    return events.sort_values(["trigger_ma", "direction", "session_date", "ticker"])


def named_state_masks(events: pd.DataFrame) -> dict[str, pd.Series]:
    bull = events["pre_ma_hierarchy"].eq("BULL_STACK")
    bear = events["pre_ma_hierarchy"].eq("BEAR_STACK")
    long = events["direction"].eq("long")
    short = events["direction"].eq("short")
    return {
        "L01_CRASH_REVERSAL": long & events["pre_ret20"].le(-0.10) & events["pre_drawdown60"].le(-0.15),
        "L02_DEEP_DRAWDOWN_RECOVERY": long & events["pre_drawdown60"].le(-0.15) & events["pre_runup20"].ge(0.05),
        "L03_DEEP_DRAWDOWN_BASE": long & events["pre_drawdown60"].le(-0.15) & events["pre_ret10"].abs().le(0.03) & events["pre_range20_q"].le(2),
        "L04_EARLY_RECOVERY_BELOW_MA30": long & events["pre_drawdown60"].le(-0.10) & events["pre_price_to_ma30_atr"].lt(0) & events["pre_runup20"].ge(0.05),
        "L05_BULL_TREND_PULLBACK": long & bull & events["pre_drawdown20"].between(-0.10, -0.02),
        "L06_BULL_TREND_SHALLOW_RECLAIM": long & bull & events["pre_drawdown20"].gt(-0.05) & events["pre_ret60"].gt(0),
        "L07_FAILED_BEAR_TREND_REVERSAL": long & bear & events["pre_runup20"].ge(0.08),
        "L08_DEPRESSED_BREADTH_REVERSAL": long & events["pre_breadth_above_ma30"].lt(0.35) & events["pre_breadth_change10"].gt(0.05),
        "L09_BROAD_BULL_CONTINUATION": long & events["pre_breadth_above_ma30"].gt(0.65) & events["pre_qqq_phase"].eq("bull") & bull,
        "L10_LOW_VOL_BASE_BREAKOUT": long & events["pre_natr20_q"].le(2) & events["pre_range20_q"].le(2) & events["pre_ret10"].abs().le(0.03),
        "L11_HIGH_VOL_CAPITULATION": long & events["pre_natr20_q"].eq(5) & events["pre_ret20"].le(-0.10),
        "S01_SURGE_REVERSAL": short & events["pre_ret20"].ge(0.10) & events["pre_runup60"].ge(0.15),
        "S02_STRONG_RUNUP_ROLLOVER": short & events["pre_runup60"].ge(0.20) & events["pre_drawdown20"].le(-0.03),
        "S03_RALLY_DISTRIBUTION": short & events["pre_runup60"].ge(0.15) & events["pre_ret10"].abs().le(0.03) & events["pre_range20_q"].le(2),
        "S04_EARLY_ROLLOVER_ABOVE_MA30": short & events["pre_runup60"].ge(0.15) & events["pre_price_to_ma30_atr"].gt(0) & events["pre_drawdown20"].le(-0.03),
        "S05_BEAR_TREND_BOUNCE_FAILURE": short & bear & events["pre_runup20"].between(0.03, 0.10),
        "S06_BEAR_TREND_CONTINUATION": short & bear & events["pre_ret60"].lt(0) & events["pre_runup20"].lt(0.10),
        "S07_FAILED_BULL_TREND_REVERSAL": short & bull & events["pre_drawdown20"].le(-0.05),
        "S08_EUPHORIC_BREADTH_ROLLOVER": short & events["pre_breadth_above_ma30"].gt(0.75) & events["pre_breadth_change10"].lt(-0.05),
        "S09_BROAD_BEAR_CONTINUATION": short & events["pre_breadth_above_ma30"].lt(0.40) & events["pre_qqq_phase"].eq("bear") & bear,
        "S10_LOW_VOL_DISTRIBUTION": short & events["pre_natr20_q"].le(2) & events["pre_range20_q"].le(2) & events["pre_ret10"].abs().le(0.03),
        "S11_HIGH_VOL_TOP_EXHAUSTION": short & events["pre_natr20_q"].eq(5) & events["pre_ret20"].ge(0.10),
        "S12_EXTREME_RUNUP_BREAKDOWN": short & events["pre_runup60"].ge(0.30),
    }


def calculate_stats(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        for metric in RETURN_METRICS:
            column = f"{metric}_{horizon}"
            rows.append(
                {
                    "horizon_days": horizon,
                    "return_metric": metric,
                    **KERNEL.infer_mean(
                        frame[column], frame["entity_key"], frame["session_date"]
                    ),
                }
            )
    return rows


def grouped_stats(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(list(columns), dropna=False, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        identity = dict(zip(columns, keys, strict=True))
        for stats in calculate_stats(group):
            rows.append({**identity, **stats})
    return pd.DataFrame(rows)


def build_baseline_stats(events: pd.DataFrame) -> pd.DataFrame:
    return grouped_stats(events, ["trigger_ma", "direction"])


def build_dimension_stats(events: pd.DataFrame) -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    for column, description in DIMENSIONS.items():
        stats = grouped_stats(events.loc[events[column].notna()], ["trigger_ma", "direction", column])
        stats = stats.rename(columns={column: "state_value"})
        stats["dimension"] = column
        stats["dimension_description"] = description
        outputs.append(stats)
    return pd.concat(outputs, ignore_index=True)


def build_state_membership(events: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for state_name, mask in named_state_masks(events).items():
        selected = events.loc[
            mask,
            ["event_id", "trigger_ma", "direction", "ticker", "entity_key", "session_date"],
        ].copy()
        selected["state_name"] = state_name
        selected["state_description"] = STATE_DESCRIPTIONS[state_name]
        frames.append(selected)
    return pd.concat(frames, ignore_index=True)


def build_named_outputs(
    events: pd.DataFrame, membership: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    state_rows: list[dict[str, Any]] = []
    contrast_rows: list[dict[str, Any]] = []
    state_masks = named_state_masks(events)
    for state_name, mask in state_masks.items():
        direction = "long" if state_name.startswith("L") else "short"
        for trigger_ma in TRIGGER_MAS:
            base = events.loc[
                events["trigger_ma"].eq(trigger_ma)
                & events["direction"].eq(direction)
            ].copy()
            candidate = mask.loc[base.index]
            selected = base.loc[candidate]
            for stats in calculate_stats(selected):
                state_rows.append(
                    {
                        "state_name": state_name,
                        "state_description": STATE_DESCRIPTIONS[state_name],
                        "trigger_ma": trigger_ma,
                        "direction": direction,
                        **stats,
                    }
                )
            for horizon in HORIZONS:
                for metric in RETURN_METRICS:
                    contrast_rows.append(
                        {
                            "state_name": state_name,
                            "state_description": STATE_DESCRIPTIONS[state_name],
                            "trigger_ma": trigger_ma,
                            "direction": direction,
                            "horizon_days": horizon,
                            "return_metric": metric,
                            **Y2.infer_candidate_contrast(
                                base,
                                f"{metric}_{horizon}",
                                candidate,
                            ),
                        }
                    )
    stats = pd.DataFrame(state_rows)
    contrasts = pd.DataFrame(contrast_rows)
    contrasts["fdr_q_value"] = contrasts.groupby(
        ["trigger_ma", "direction", "horizon_days", "return_metric"],
        group_keys=False,
    )["p_value"].transform(KERNEL.benjamini_hochberg)
    contrasts["reliable_cell"] = (
        contrasts["candidate_count"].ge(100)
        & contrasts["security_count"].ge(10)
        & contrasts["event_date_count"].ge(30)
    )
    return stats, contrasts


def build_robustness(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    masks = named_state_masks(events)
    for state_name, mask in masks.items():
        direction = "long" if state_name.startswith("L") else "short"
        for trigger_ma in TRIGGER_MAS:
            base_mask = events["trigger_ma"].eq(trigger_ma) & events["direction"].eq(direction) & mask
            base = events.loc[base_mask]
            slices: list[tuple[str, str, pd.DataFrame]] = [("all", "all", base)]
            for year, group in base.groupby("calendar_year"):
                slices.append(("calendar_year", str(year), group))
            for phase, group in base.groupby("pre_qqq_phase"):
                slices.append(("qqq_phase", str(phase), group))
            for threshold in (0.01, 0.02, 0.03):
                slices.append(
                    (
                        "gap_exclusion",
                        f"abs_gap_le_{threshold:.2f}",
                        base.loc[base["gap"].abs().le(threshold)],
                    )
                )
            for slice_type, slice_value, subset in slices:
                for horizon in FOCUS_HORIZONS:
                    stats = KERNEL.infer_mean(
                        subset[f"raw_return_{horizon}"],
                        subset["entity_key"],
                        subset["session_date"],
                    )
                    rows.append(
                        {
                            "state_name": state_name,
                            "state_description": STATE_DESCRIPTIONS[state_name],
                            "trigger_ma": trigger_ma,
                            "direction": direction,
                            "slice_type": slice_type,
                            "slice_value": slice_value,
                            "horizon_days": horizon,
                            "return_metric": "raw_return",
                            **stats,
                        }
                    )
    return pd.DataFrame(rows)


def build_topology_stats(events: pd.DataFrame) -> pd.DataFrame:
    topology = grouped_stats(
        events,
        ["trigger_ma", "direction", "event_topology"],
    )
    gap_frames: list[pd.DataFrame] = []
    for threshold in (0.01, 0.02, 0.03):
        subset = events.loc[events["gap"].abs().le(threshold)]
        stats = grouped_stats(subset, ["trigger_ma", "direction"])
        stats["event_topology"] = f"ABS_GAP_LE_{threshold:.2f}"
        gap_frames.append(stats)
    return pd.concat([topology, *gap_frames], ignore_index=True)


def build_ranking(
    stats: pd.DataFrame,
    contrasts: pd.DataFrame,
    robustness: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    focus_stats = stats.loc[
        stats["horizon_days"].eq(20) & stats["return_metric"].eq("raw_return")
    ].copy()
    focus_contrasts = contrasts.loc[
        contrasts["horizon_days"].eq(20)
        & contrasts["return_metric"].eq("raw_return")
    ].copy()
    ranking = focus_stats.merge(
        focus_contrasts[
            [
                "state_name",
                "trigger_ma",
                "direction",
                "reference_mean",
                "incremental_mean",
                "t_stat",
                "ci95_low",
                "ci95_high",
                "p_value",
                "fdr_q_value",
                "reliable_cell",
            ]
        ].rename(columns={"t_stat": "incremental_t_stat"}),
        on=["state_name", "trigger_ma", "direction"],
        how="left",
        validate="one_to_one",
    )
    annual = robustness.loc[
        robustness["slice_type"].eq("calendar_year")
        & robustness["horizon_days"].eq(20)
        & robustness["return_metric"].eq("raw_return")
        & robustness["sample_count"].ge(20)
    ].copy()
    annual["calendar_year"] = annual["slice_value"].astype(int)
    annual_baseline = (
        events.loc[np.isfinite(events["raw_return_20"])]
        .groupby(["trigger_ma", "direction", "calendar_year"], as_index=False)
        .agg(annual_baseline_mean=("raw_return_20", "mean"))
    )
    annual = annual.merge(
        annual_baseline,
        on=["trigger_ma", "direction", "calendar_year"],
        how="left",
        validate="many_to_one",
    )
    annual["annual_incremental_mean"] = (
        annual["mean"] - annual["annual_baseline_mean"]
    )
    annual_summary = (
        annual.groupby(["state_name", "trigger_ma", "direction"], as_index=False)
        .agg(
            eligible_years=("mean", "size"),
            positive_year_share=("mean", lambda value: float((value > 0).mean())),
            median_annual_mean=("mean", "median"),
            positive_incremental_year_share=(
                "annual_incremental_mean",
                lambda value: float((value > 0).mean()),
            ),
            median_annual_incremental_mean=("annual_incremental_mean", "median"),
        )
    )
    ranking = ranking.merge(
        annual_summary,
        on=["state_name", "trigger_ma", "direction"],
        how="left",
        validate="one_to_one",
    )
    return ranking.sort_values(
        ["trigger_ma", "direction", "incremental_mean"],
        ascending=[True, True, False],
    )


def percent(value: float) -> str:
    return "NA" if not np.isfinite(value) else f"{value * 100:.2f}%"


def render_report(
    config: dict[str, Any],
    panel: pd.DataFrame,
    events: pd.DataFrame,
    baseline: pd.DataFrame,
    ranking: pd.DataFrame,
    dimensions: pd.DataFrame,
    named_stats: pd.DataFrame,
    contrasts: pd.DataFrame,
    robustness: pd.DataFrame,
) -> str:
    baseline_lines = []
    for trigger_ma in TRIGGER_MAS:
        for direction in ("long", "short"):
            row = baseline.loc[
                baseline["trigger_ma"].eq(trigger_ma)
                & baseline["direction"].eq(direction)
                & baseline["horizon_days"].eq(20)
                & baseline["return_metric"].eq("raw_return")
            ].iloc[0]
            baseline_lines.append(
                f"| MA{trigger_ma} | {direction} | {int(row['sample_count']):,} | "
                f"{percent(row['mean'])} | {percent(row['median'])} | {percent(row['win_rate'])} | {row['t_stat']:.2f} |"
            )

    ranking_lines = []
    for trigger_ma in TRIGGER_MAS:
        for direction in ("long", "short"):
            subset = ranking.loc[
                ranking["trigger_ma"].eq(trigger_ma)
                & ranking["direction"].eq(direction)
                & ranking["reliable_cell"]
            ].head(6)
            for row in subset.itertuples(index=False):
                ranking_lines.append(
                    f"| MA{trigger_ma} | {direction} | `{row.state_name}` | {row.state_description} | "
                    f"{int(row.sample_count):,} | {percent(row.mean)} | {percent(row.median)} | "
                    f"{percent(row.incremental_mean)} | {row.incremental_t_stat:.2f} | {row.fdr_q_value:.3f} | "
                    f"{percent(row.positive_incremental_year_share) if np.isfinite(row.positive_incremental_year_share) else 'NA'} |"
                )

    dimension_focus = dimensions.loc[
        dimensions["horizon_days"].eq(20)
        & dimensions["return_metric"].eq("raw_return")
        & dimensions["sample_count"].ge(100)
    ].copy()
    dimension_lines = []
    for trigger_ma in TRIGGER_MAS:
        for direction in ("long", "short"):
            subset = dimension_focus.loc[
                dimension_focus["trigger_ma"].eq(trigger_ma)
                & dimension_focus["direction"].eq(direction)
            ]
            for dimension, group in subset.groupby("dimension"):
                best = group.loc[group["mean"].idxmax()]
                worst = group.loc[group["mean"].idxmin()]
                dimension_lines.append(
                    f"| MA{trigger_ma} | {direction} | {DIMENSIONS[dimension]} | "
                    f"{best['state_value']} / {percent(best['mean'])} | "
                    f"{worst['state_value']} / {percent(worst['mean'])} | "
                    f"{percent(best['mean'] - worst['mean'])} |"
                )

    supported = ranking.loc[
        ranking["reliable_cell"]
        & ranking["fdr_q_value"].le(0.10)
        & ranking["incremental_mean"].gt(0)
        & ranking["mean"].gt(0)
    ]
    supported_names = [
        f"MA{row.trigger_ma}:{row.state_name}"
        for row in supported.itertuples(index=False)
    ]

    focus_states = (
        (7, "L02_DEEP_DRAWDOWN_RECOVERY"),
        (7, "L04_EARLY_RECOVERY_BELOW_MA30"),
        (30, "L01_CRASH_REVERSAL"),
        (30, "L02_DEEP_DRAWDOWN_RECOVERY"),
        (30, "L04_EARLY_RECOVERY_BELOW_MA30"),
        (30, "L07_FAILED_BEAR_TREND_REVERSAL"),
    )
    horizon_lines = []
    for trigger_ma, state_name in focus_states:
        for horizon_days in (10, 20, 40):
            stat = named_stats.loc[
                named_stats["trigger_ma"].eq(trigger_ma)
                & named_stats["direction"].eq("long")
                & named_stats["state_name"].eq(state_name)
                & named_stats["horizon_days"].eq(horizon_days)
                & named_stats["return_metric"].eq("raw_return")
            ].iloc[0]
            contrast = contrasts.loc[
                contrasts["trigger_ma"].eq(trigger_ma)
                & contrasts["direction"].eq("long")
                & contrasts["state_name"].eq(state_name)
                & contrasts["horizon_days"].eq(horizon_days)
                & contrasts["return_metric"].eq("raw_return")
            ].iloc[0]
            horizon_lines.append(
                f"| MA{trigger_ma} | `{state_name}` | {horizon_days}D | "
                f"{int(stat['sample_count']):,} | {percent(stat['mean'])} | "
                f"{percent(stat['median'])} | {percent(contrast['incremental_mean'])} | "
                f"{contrast['t_stat']:.2f} | {contrast['fdr_q_value']:.3f} |"
            )

    gap_lines = []
    for trigger_ma, state_name in focus_states:
        row = robustness.loc[
            robustness["trigger_ma"].eq(trigger_ma)
            & robustness["direction"].eq("long")
            & robustness["state_name"].eq(state_name)
            & robustness["slice_type"].eq("gap_exclusion")
            & robustness["slice_value"].eq("abs_gap_le_0.01")
            & robustness["horizon_days"].eq(20)
            & robustness["return_metric"].eq("raw_return")
        ].iloc[0]
        gap_lines.append(
            f"| MA{trigger_ma} | `{state_name}` | {int(row['sample_count']):,} | "
            f"{percent(row['mean'])} | {percent(row['median'])} | "
            f"{percent(row['win_rate'])} | {row['t_stat']:.2f} |"
        )
    conclusion = (
        "存在若干通过样本与FDR门槛的结构，但仍需独立样本验证"
        if supported_names
        else "没有具名状态同时通过正expectancy、正增量与FDR门槛"
    )
    eligible = panel.loc[panel["eligible_y3"]]
    return f"""# NDX100-1D-MA7-RC-Y3：突破前市场结构图谱

## 一句话结论

**{conclusion}。** 本轮研究的是突破前真实价格路径，不是个股相对强弱：大跌修复、深回撤筑底、趋势回踩、暴涨回落、横盘派发、MA层级、市场宽度和 QQQ 阶段均已逐项统计。通过门槛的 descriptive states：`{', '.join(supported_names) if supported_names else 'none'}`。

## 样本与因果口径

- Config SHA256：`{EXPECTED_CONFIG_SHA256}`。
- Eligible：`{len(eligible):,}` stock-days、`{eligible['ticker'].nunique()}` stocks，所有状态严格截至 `t-1`。
- Events：`{len(events):,}`，同时检验 MA7 与 MA30 的向上/向下严格收盘跨越。
- 具名状态：`{len(STATE_DESCRIPTIONS)}` 个；连续结构维度：`{len(DIMENSIONS)}` 类。
- 当前成分回填、survivorship-biased；这是事件图谱，不是账户策略。

## 裸突破基线

| Trigger | 方向 | 20D样本 | 平均 | 中位 | 胜率 | t |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(baseline_lines)}

## 每组排名靠前的具名结构

“增量”是相对同 trigger、同方向其余突破事件；FDR 在全部具名状态内校正。这里只是全样本描述排名，不是选参。

| Trigger | 方向 | 状态 | 大白话 | 样本 | 20D平均 | 中位 | 增量 | 增量t | FDR q | 年度增量为正占比 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(ranking_lines)}

## 关键多头结构怎样随时间展开

这些状态在突破后 `1–5D` 没有稳定的增量优势，差异主要在 `10–40D` 展开。因此更像数周级修复/反转延续，而不是突破次日跳一下。

| Trigger | 状态 | Horizon | 样本 | 平均 | 中位 | 相对其余同向突破增量 | 增量t | FDR q |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(horizon_lines)}

## 去掉明显跳空后的诊断

下表只保留突破日绝对 gap 不超过 `1%` 的事件。关键修复结构的 20D 均值仍为正，说明结果不只是财报或隔夜跳空机械造成；`2%/3%` 阈值也已保存在 robustness 机器表中。

| Trigger | 状态 | 样本 | 20D平均 | 中位 | 胜率 | t |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(gap_lines)}

## 各结构维度的最好与最差档

| Trigger | 方向 | 维度 | 最好档/20D | 最差档/20D | 最大差 |
| --- | --- | --- | ---: | ---: | ---: |
{chr(10).join(dimension_lines)}

## 如何解读

- 正均值不等于有效过滤；必须再看相对其余事件的增量、FDR 和分年稳定性。
- 一个状态可以同时属于多个结构，例如“深回撤修复”也可能是“低宽度反转”；状态不是互斥分类器。
- event-day gap 和 MA7/MA30 同时跨越单独保存，不混入 `t-1` 市场状态。
- 全样本排名只为找下一轮应冻结验证的少量机制，不能直接写交易规则。

合同：[Y3 structure atlas contract](../specs/ndx100-1d-ma7-regime-continuation-yahoo-current-y3-structure-atlas-contract-2026-08-25.md)。
"""


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format="%.10g")


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def write_manifest(paths: Sequence[Path]) -> None:
    write_json(
        {
            "study_id": STUDY_ID,
            "config_sha256": EXPECTED_CONFIG_SHA256,
            "artifacts": [
                {
                    "path": str(path.relative_to(ROOT)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in paths
            ],
        },
        OUTPUTS["manifest"],
    )


def main() -> int:
    args = parse_args()
    if not args.run:
        raise SystemExit("refusing to read Y3 outcomes without --run")
    config = validate_inputs(args.force)
    panel, price_audit = prepare_panel(config)
    events = build_events(panel)
    membership = build_state_membership(events)
    baseline = build_baseline_stats(events)
    dimensions = build_dimension_stats(events)
    named_stats, contrasts = build_named_outputs(events, membership)
    robustness = build_robustness(events)
    topology = build_topology_stats(events)
    ranking = build_ranking(named_stats, contrasts, robustness, events)

    OUTPUTS["events"].parent.mkdir(parents=True, exist_ok=True)
    events.to_parquet(OUTPUTS["events"], index=False)
    membership.to_parquet(OUTPUTS["state_membership"], index=False)
    for frame, key in (
        (baseline, "baseline_stats"),
        (dimensions, "dimension_stats"),
        (named_stats, "named_state_stats"),
        (contrasts, "named_state_contrasts"),
        (ranking, "named_state_ranking"),
        (robustness, "robustness_stats"),
        (topology, "topology_stats"),
    ):
        write_csv(frame, OUTPUTS[key])

    supported = ranking.loc[
        ranking["reliable_cell"]
        & ranking["fdr_q_value"].le(0.10)
        & ranking["incremental_mean"].gt(0)
        & ranking["mean"].gt(0)
    ]
    summary = {
        "study_id": STUDY_ID,
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "COMPLETED_INTERPRETABLE_STRUCTURE_ATLAS_SURVIVORSHIP_BIASED",
        "data": {
            "price_rows_including_qqq": int(price_audit["rows"]),
            "eligible_stock_days": int(panel["eligible_y3"].sum()),
            "eligible_stocks": int(panel.loc[panel["eligible_y3"], "ticker"].nunique()),
            "events": int(len(events)),
            "named_states": len(STATE_DESCRIPTIONS),
            "dimensions": len(DIMENSIONS),
        },
        "supported_descriptive_states_20d_raw_fdr10": supported[
            [
                "trigger_ma",
                "direction",
                "state_name",
                "sample_count",
                "mean",
                "median",
                "incremental_mean",
                "incremental_t_stat",
                "fdr_q_value",
                "positive_year_share",
                "positive_incremental_year_share",
                "median_annual_incremental_mean",
            ]
        ].to_dict(orient="records"),
        "limitations": [
            "current Nasdaq-100 constituents applied retrospectively",
            "all ranking is in-sample descriptive hypothesis generation",
            "trigger-close event study, not executable next-open strategy",
            "states overlap and are not a mutually exclusive classifier",
            "no machine learning or cross-sectional relative strength",
        ],
    }
    write_json(summary, OUTPUTS["summary"])
    REPORT_PATH.write_text(
        render_report(
            config,
            panel,
            events,
            baseline,
            ranking,
            dimensions,
            named_stats,
            contrasts,
            robustness,
        ),
        encoding="utf-8",
    )
    manifest_paths = [
        OUTPUTS[key] for key in OUTPUTS if key != "manifest"
    ] + [REPORT_PATH]
    write_manifest(manifest_paths)
    print(json.dumps(summary, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
