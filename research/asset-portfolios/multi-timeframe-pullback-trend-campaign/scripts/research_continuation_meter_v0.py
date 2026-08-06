from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/multi-timeframe-pullback-trend-campaign"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
LOADER_PATH = ROOT / "research/asset-portfolios/1h-price-impulse-campaign/scripts/research_binance_1h_pic_v0.py"
ASSETS = ("BTC", "ETH", "HYPE")
ONSET_HOURS = (4, 12, 24)
LABEL_HOURS = (24, 72, 168)
FEATURES = ("scaled_move", "efficiency", "jump_concentration", "path_r2", "acceleration", "atr_expansion", "directional_rsi")
SPLITS = {
    "BTC": (pd.Timestamp("2023-12-31 23:59:59", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2025-06-30 23:59:59", tz="UTC")),
    "ETH": (pd.Timestamp("2023-12-31 23:59:59", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2025-06-30 23:59:59", tz="UTC")),
    "HYPE": (pd.Timestamp("2025-10-31 23:59:59", tz="UTC"), pd.Timestamp("2025-11-01", tz="UTC"), pd.Timestamp("2026-02-28 23:59:59", tz="UTC")),
}


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("bin_mtf_ptc_continuation_loader", LOADER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load loader: {LOADER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def rolling_r2(values: np.ndarray) -> float:
    if not np.isfinite(values).all() or len(values) < 3:
        return math.nan
    x = np.arange(len(values), dtype=float)
    corr = np.corrcoef(x, values)[0, 1]
    return float(corr * corr) if np.isfinite(corr) else 0.0


def build_events(hourly: pd.DataFrame, onset: int) -> pd.DataFrame:
    frame = hourly.copy()
    log_close = np.log(frame["close"].astype(float))
    returns = log_close.diff()
    past_rms = returns.rolling(720, min_periods=720).apply(lambda x: float(np.sqrt(np.mean(x * x))), raw=True).shift(onset)
    impulse = log_close - log_close.shift(onset)
    direction = np.sign(impulse)
    abs_steps = returns.abs().rolling(onset, min_periods=onset).sum()
    efficiency = impulse.abs() / abs_steps.replace(0.0, np.nan)
    max_step = returns.abs().rolling(onset, min_periods=onset).max()
    jump = max_step / abs_steps.replace(0.0, np.nan)
    path_r2 = log_close.rolling(onset + 1, min_periods=onset + 1).apply(rolling_r2, raw=True)
    half = max(2, onset // 2)
    recent = log_close - log_close.shift(half)
    prior = log_close.shift(half) - log_close.shift(2 * half)
    acceleration = direction * (recent - prior) / (past_rms * math.sqrt(onset))
    prev_close = frame["close"].shift(1)
    tr = pd.concat([(frame["high"] - frame["low"]), (frame["high"] - prev_close).abs(), (frame["low"] - prev_close).abs()], axis=1).max(axis=1) / prev_close
    atr_expansion = tr.rolling(12, min_periods=12).mean() / tr.rolling(168, min_periods=168).median()
    delta = frame["close"].diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    rsi = 100.0 - 100.0 / (1.0 + gain / loss.replace(0.0, np.nan))
    events = pd.DataFrame(index=frame.index)
    events["close"] = frame["close"].astype(float)
    events["direction"] = direction
    events["r_log"] = past_rms * math.sqrt(24.0)
    events["scaled_move"] = impulse.abs() / (past_rms * math.sqrt(onset))
    events["efficiency"] = efficiency
    events["jump_concentration"] = jump
    events["path_r2"] = path_r2
    events["acceleration"] = acceleration
    events["atr_expansion"] = atr_expansion
    events["directional_rsi"] = direction * (rsi - 50.0) / 50.0
    events = events.loc[(events.index.hour % 4 == 0) & events["scaled_move"].ge(0.5) & events["direction"].ne(0)]
    return events.dropna(subset=[*FEATURES, "r_log"])


def label_events(events: pd.DataFrame, hourly: pd.DataFrame, horizon: int) -> pd.Series:
    positions = hourly.index.get_indexer(events.index)
    highs = hourly["high"].to_numpy(float)
    lows = hourly["low"].to_numpy(float)
    labels: list[float] = []
    for (_, event), pos in zip(events.iterrows(), positions, strict=True):
        if pos < 0 or pos + horizon >= len(hourly):
            labels.append(math.nan)
            continue
        side = int(event["direction"])
        close = float(event["close"])
        r_log = float(event["r_log"])
        favorable = close * math.exp(side * r_log)
        adverse = close * math.exp(-side * 0.5 * r_log)
        outcome = math.nan
        for j in range(pos + 1, pos + horizon + 1):
            success = highs[j] >= favorable if side > 0 else lows[j] <= favorable
            failure = lows[j] <= adverse if side > 0 else highs[j] >= adverse
            if failure:
                outcome = 0.0
                break
            if success:
                outcome = 1.0
                break
        labels.append(outcome)
    return pd.Series(labels, index=events.index, dtype=float)


def evaluate(asset: str, onset: int, horizon: int, hourly: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    events = build_events(hourly, onset)
    events["label"] = label_events(events, hourly, horizon)
    dev_end, val_start, val_end = SPLITS[asset]
    purge_end = dev_end - pd.Timedelta(days=14)
    complete_end = val_end - pd.Timedelta(hours=horizon)
    dev = events.loc[(events.index <= purge_end) & events["label"].notna()].copy()
    val_all = events.loc[(events.index >= val_start) & (events.index <= complete_end)].copy()
    val = val_all.loc[val_all["label"].notna()].copy()
    if len(dev) < 100 or len(val) < 30 or dev["label"].nunique() < 2 or val["label"].nunique() < 2:
        return {"asset": asset, "onset_hours": onset, "label_hours": horizon, "status": "insufficient", "n_dev": len(dev), "n_val": len(val)}, pd.DataFrame()
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    model.fit(dev[list(FEATURES)], dev["label"].astype(int))
    probability = model.predict_proba(val[list(FEATURES)])[:, 1]
    val["probability"] = probability
    val["quintile"] = pd.qcut(val["probability"], 5, labels=False, duplicates="drop")
    quintiles = val.groupby("quintile", observed=True).agg(events=("label", "size"), continuation_rate=("label", "mean"), mean_probability=("probability", "mean")).reset_index()
    rates = quintiles["continuation_rate"].to_numpy(float)
    rho = float(spearmanr(np.arange(len(rates)), rates).statistic) if len(rates) >= 3 else math.nan
    result = {
        "asset": asset,
        "onset_hours": onset,
        "label_hours": horizon,
        "status": "ok",
        "n_dev": int(len(dev)),
        "n_val": int(len(val)),
        "unresolved_val": int(val_all["label"].isna().sum()),
        "base_rate_dev": float(dev["label"].mean()),
        "base_rate_val": float(val["label"].mean()),
        "auc_val": float(roc_auc_score(val["label"], probability)),
        "brier_val": float(brier_score_loss(val["label"], probability)),
        "top_bottom_spread": float(rates[-1] - rates[0]),
        "quintile_spearman": rho,
    }
    quintiles.insert(0, "label_hours", horizon)
    quintiles.insert(0, "onset_hours", onset)
    quintiles.insert(0, "asset", asset)
    return result, quintiles


def main() -> None:
    loader = load_module()
    frames, _ = loader.load_assets()
    results: list[dict[str, Any]] = []
    quintiles: list[pd.DataFrame] = []
    for asset in ASSETS:
        hourly = frames[asset]
        for onset in ONSET_HOURS:
            for horizon in LABEL_HOURS:
                result, groups = evaluate(asset, onset, horizon, hourly)
                results.append(result)
                if not groups.empty:
                    quintiles.append(groups)
    result_frame = pd.DataFrame(results)
    quintile_frame = pd.concat(quintiles, ignore_index=True) if quintiles else pd.DataFrame()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    result_frame.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_continuation_meter_v0_metrics_2026-08-03.csv", index=False)
    quintile_frame.to_csv(ARTIFACT_DIR / "binance_mtf_ptc_continuation_meter_v0_quintiles_2026-08-03.csv", index=False)
    payload = {"contract": {"onset_hours": ONSET_HOURS, "label_hours": LABEL_HOURS, "features": FEATURES, "locked_evaluation_used": False}, "results": result_frame.to_dict(orient="records")}
    (ARTIFACT_DIR / "binance_mtf_ptc_continuation_meter_v0_2026-08-03.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(result_frame.to_string(index=False))


if __name__ == "__main__":
    main()
