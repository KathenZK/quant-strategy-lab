"""K-family supplement: candlestick morphology at bar / daily / weekly scales.

Implements specs/bin-15m-emax-k-candle-supplement-contract-2026-07-29.md.
Adds 18 candle body/shadow features (signal bar, previous completed day,
previous completed week) to the local+trend set and reruns the scoring
variant. The k_candle_features() helper is reused by the 4h family script.
Family stays archived; 2026H1 untouched.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

import research_feature_ablation_a2 as a2
import research_feature_label_ablation as base

ec = __import__("emax_common")

OUT_DIR = ec.ARTIFACT_DIR / "k_candle_supplement"

K_FEATURES = [
    "kbar_body_atr", "kbar_body_ratio", "kbar_shadow_with", "kbar_shadow_against",
    "kbar_close_bias", "kbar_body3_atr", "kbar_engulf",
    "d1_body_atr", "d1_body_ratio", "d1_shadow_with", "d1_shadow_against",
    "d1_close_bias", "d1_body3_atr",
    "w1_body_atr", "w1_body_ratio", "w1_shadow_with", "w1_shadow_against",
    "w1_close_bias",
]


def _candle_parts(o, h, l, c):  # noqa: E741
    rng = (h - l).replace(0.0, np.nan) if isinstance(h, pd.Series) else np.where(h - l > 0, h - l, np.nan)
    body = c - o
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    return rng, body, upper, lower


def _period_candles(frame: pd.DataFrame, freq: str, **resample_kw) -> pd.DataFrame:
    agg = (
        frame.set_index("ts")
        .resample(freq, **resample_kw)
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
    )
    rng, body, upper, lower = _candle_parts(agg["open"], agg["high"], agg["low"], agg["close"])
    prev_close = agg["close"].shift(1)
    tr = pd.concat(
        [agg["high"] - agg["low"], (agg["high"] - prev_close).abs(),
         (agg["low"] - prev_close).abs()], axis=1,
    ).max(axis=1)
    atr14 = tr.rolling(14, min_periods=14).mean()
    return pd.DataFrame(
        {
            "body_atr": body / atr14,
            "body_ratio": body.abs() / rng,
            "upper": upper / rng,
            "lower": lower / rng,
            "close_bias": 2.0 * (agg["close"] - agg["low"]) / rng - 1.0,
            "body3_atr": body.rolling(3).sum() / atr14,
        }
    )


def _assign_period(block: pd.DataFrame, prefix: str, values: pd.DataFrame, side: np.ndarray) -> None:
    block[f"{prefix}_body_atr"] = values["body_atr"].to_numpy() * side
    block[f"{prefix}_body_ratio"] = values["body_ratio"].to_numpy()
    up, lo = values["upper"].to_numpy(), values["lower"].to_numpy()
    block[f"{prefix}_shadow_with"] = np.where(side == 1, lo, up)
    block[f"{prefix}_shadow_against"] = np.where(side == 1, up, lo)
    block[f"{prefix}_close_bias"] = values["close_bias"].to_numpy() * side
    if "body3_atr" in values:
        block[f"{prefix}_body3_atr"] = values["body3_atr"].to_numpy() * side


def k_candle_features(frame: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    """18 candle-morphology features at the signal bars of `rows`.

    `frame` must carry ts/open/high/low/close/atr; `rows` needs
    signal_idx and side. Returns a positional block aligned to `rows`.
    """
    signal_idx = rows["signal_idx"].to_numpy()
    side = rows["side"].to_numpy()
    signal_ts = pd.DatetimeIndex(frame["ts"].iloc[signal_idx])
    block = pd.DataFrame(index=range(len(rows)))

    o, h, l, c = (frame[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))  # noqa: E741
    atr = frame["atr"].to_numpy(dtype=float)
    rng, body, upper, lower = _candle_parts(o, h, l, c)
    i = signal_idx
    block["kbar_body_atr"] = body[i] / atr[i] * side
    block["kbar_body_ratio"] = np.abs(body[i]) / rng[i]
    up_i, lo_i = upper[i] / rng[i], lower[i] / rng[i]
    block["kbar_shadow_with"] = np.where(side == 1, lo_i, up_i)
    block["kbar_shadow_against"] = np.where(side == 1, up_i, lo_i)
    block["kbar_close_bias"] = (2.0 * (c[i] - l[i]) / rng[i] - 1.0) * side
    body3 = pd.Series(body).rolling(3).sum().to_numpy()
    block["kbar_body3_atr"] = body3[i] / atr[i] * side
    prev_abs = np.abs(np.concatenate([[np.nan], body[:-1]]))
    with np.errstate(divide="ignore", invalid="ignore"):
        engulf = np.where(prev_abs > 0, np.abs(body) / prev_abs, np.nan)
    block["kbar_engulf"] = engulf[i]

    daily = _period_candles(frame, "1D").shift(1)  # previous completed UTC day
    days = signal_ts.normalize()
    _assign_period(block, "d1", daily.reindex(days), side)

    weekly = _period_candles(frame, "1W-MON", label="left", closed="left").drop(columns=["body3_atr"])
    prev_week = days - pd.to_timedelta(days.dayofweek, unit="D") - pd.Timedelta(days=7)
    _assign_period(block, "w1", weekly.reindex(prev_week), side)
    return block


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pool = pd.read_parquet(ec.ARTIFACT_DIR / "af_supplement" / "pool_local_trend_f.parquet")
    for col in ("entry_ts", "signal_ts"):
        pool[col] = pd.to_datetime(pool[col], utc=True)

    blocks = []
    symbols = sorted(pool["sym_key"].unique())
    started = time.monotonic()
    for count, sym in enumerate(symbols, start=1):
        idx = pool.index[pool["sym_key"] == sym]
        frame = ec.compute_indicators(ec.load_symbol_frame(sym))
        blocks.append(k_candle_features(frame, pool.loc[idx]).set_index(idx))
        if count % 100 == 0 or count == len(symbols):
            print(f"K features {count}/{len(symbols)} ({time.monotonic() - started:.0f}s)", flush=True)
    pool = pd.concat([pool, pd.concat(blocks).sort_index()], axis=1)
    nan_share = {c: round(float(pool[c].isna().mean()), 4) for c in K_FEATURES}
    print("K nan share:", nan_share)

    features = base.LOCAL_FEATURES + a2.NEW_FEATURES + K_FEATURES
    scores, top_imp = base.run_variant(pool, features, "abs")
    result = base.evaluate(pool, scores)
    result["top_feature_importance_gain"] = top_imp

    oof = pool.loc[scores.notna()].assign(score=scores.dropna())
    oof["year"] = oof["entry_ts"].dt.year
    oof["decile"] = (
        oof.groupby("year")["score"].rank(pct=True, method="first")
        .mul(10).apply(np.ceil).clip(1, 10).astype(int)
    )
    top = oof.loc[oof["decile"] == 10]
    result["top_decile_gross_atr"] = round(float(top["b4_2_gross_atr"].mean()), 4)

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-15m-emax-k-candle-supplement-contract-2026-07-29.md",
        "variant": "local_trend_k",
        "n_features": len(features),
        "k_nan_share": nan_share,
        "result": result,
        "reference_a2": {"top_decile_net_atr": -0.1338, "top_decile_gross_atr": 0.1668},
    }
    out = OUT_DIR / "k_supplement_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "decile_spearman", "top_decile_mean_net_atr", "top_decile_by_year",
        "top_decile_gross_atr", "gate_a_ranking", "gate_b_monetizable", "passes_both")},
        ensure_ascii=False))
    print("15m K verdict passes_both:", result["passes_both"], "| report ->", out)


if __name__ == "__main__":
    main()
