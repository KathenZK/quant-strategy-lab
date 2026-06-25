from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import (
    END_TS,
    IS_END_TS,
    LEVERAGE_GRID,
    REPORT_PATH as BASE_REPORT_PATH,
    START_TS,
    TARGET_ANNUALIZED_MULTIPLE,
    TARGET_MAX_DD,
    TARGET_WIN_RATE,
    SearchConfig,
    Trade,
    add_features,
    build_signal,
    load_hype_5m,
    metric_from_trades,
    simulate_trades,
)


BASE_RANKING_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_indicator_search_ranking.csv")
REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_filter_refinement.json")
RANKING_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_filter_refinement_ranking.csv")
TARGET_HITS_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_filter_refinement_target_hits.csv")
REFINED_TRADES_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_filter_refinement_top_trades.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refine HYPE 5m candidates with entry-time feature filters.")
    parser.add_argument("--base-configs", type=int, default=18)
    parser.add_argument("--beam", type=int, default=35)
    parser.add_argument("--exact-top", type=int, default=500)
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--top", type=int, default=80)
    return parser.parse_args()


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def row_to_config(row: pd.Series) -> SearchConfig:
    return SearchConfig(
        name=str(row["name"]),
        side_mode=str(row["side_mode"]),
        ema_fast=int(row["ema_fast"]),
        ema_slow=int(row["ema_slow"]),
        entry_style=str(row["entry_style"]),
        donchian=int(row["donchian"]),
        roc_window=int(row["roc_window"]),
        min_regime_age=int(row["min_regime_age"]),
        max_regime_age=int(row["max_regime_age"]),
        breakout_buffer=float(row["breakout_buffer"]),
        pullback_buffer=float(row["pullback_buffer"]),
        max_dist_ema=float(row["max_dist_ema"]),
        min_dir_roc=float(row["min_dir_roc"]),
        min_dir_rsi=float(row["min_dir_rsi"]),
        max_dir_rsi=float(row["max_dir_rsi"]),
        min_adx=float(row["min_adx"]),
        max_chop=float(row["max_chop"]),
        max_atr_ratio=float(row["max_atr_ratio"]),
        min_rvol=float(row["min_rvol"]),
        min_dir_cmf=float(row["min_dir_cmf"]),
        require_macd=coerce_bool(row["require_macd"]),
        require_obv=coerce_bool(row["require_obv"]),
        require_htf=coerce_bool(row["require_htf"]),
        min_efficiency=float(row["min_efficiency"]),
        stop_atr=float(row["stop_atr"]),
        tp_atr=float(row["tp_atr"]),
        trail_atr=float(row["trail_atr"]),
        max_hold_bars=int(row["max_hold_bars"]),
        min_hold_bars=int(row["min_hold_bars"]),
        exit_ema=int(row["exit_ema"]),
        cooldown_bars=int(row["cooldown_bars"]),
    )


def candidate_base_rows(ranking: pd.DataFrame, limit: int) -> list[pd.Series]:
    groups = ranking.sort_values("target_gap").groupby("name", as_index=False).head(1)
    buckets = [
        groups.query("full_annualized_multiple >= 15 and full_max_dd >= -0.30 and full_trades >= 20").sort_values(
            ["full_max_dd", "full_annualized_multiple"], ascending=[False, False]
        ),
        groups.query("full_win_rate >= 0.70 and full_trades >= 20").sort_values(
            ["full_win_rate", "full_annualized_multiple"], ascending=[False, False]
        ),
        groups.query("full_max_dd >= -0.20 and full_trades >= 20").sort_values(
            ["full_annualized_multiple", "full_win_rate"], ascending=[False, False]
        ),
    ]
    rows: list[pd.Series] = []
    seen: set[str] = set()
    for bucket in buckets:
        for _, row in bucket.head(limit).iterrows():
            name = str(row["name"])
            if name in seen:
                continue
            seen.add(name)
            rows.append(row)
            if len(rows) >= limit:
                return rows
    return rows


def signal_indices_by_ts(frame: pd.DataFrame) -> dict[int, int]:
    return {int(ts.value): idx for idx, ts in enumerate(frame["ts"])}


def regime_age_from_direction(direction: np.ndarray) -> np.ndarray:
    age = np.zeros(len(direction), dtype=np.int32)
    last = 0
    current = 0
    for idx, value in enumerate(direction):
        if value == 0 or value != current:
            current = value
            last = idx
        age[idx] = idx - last
    return age


def feature_values(frame: pd.DataFrame, cfg: SearchConfig, signal: np.ndarray, sig_idx: np.ndarray) -> dict[str, np.ndarray]:
    side = signal[sig_idx].astype(float)
    close = frame["close"].to_numpy("float64")
    ema_fast = frame[f"ema{cfg.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{cfg.ema_slow}"].to_numpy("float64")
    spread = ema_fast - ema_slow
    direction = np.where(np.isfinite(spread), np.sign(spread), 0).astype(np.int8)
    age = regime_age_from_direction(direction)
    values = {
        "adx14": frame["adx14"].to_numpy("float64")[sig_idx],
        "chop14": frame["chop14"].to_numpy("float64")[sig_idx],
        "atr_ratio_14_96": frame["atr_ratio_14_96"].to_numpy("float64")[sig_idx],
        "atr_pct_96": frame["atr_pct_96"].to_numpy("float64")[sig_idx],
        "rvol96": frame["rvol96"].to_numpy("float64")[sig_idx],
        "eff96": frame["eff96"].to_numpy("float64")[sig_idx],
        "bb_pos20": frame["bb_pos20"].to_numpy("float64")[sig_idx],
        "bb_width_z192": frame["bb_width_z192"].to_numpy("float64")[sig_idx],
        "regime_age": age[sig_idx].astype(float),
        "abs_dist_ema": np.abs(close[sig_idx] / ema_fast[sig_idx] - 1.0),
        "dir_dist_ema": side * (close[sig_idx] / ema_fast[sig_idx] - 1.0),
        "dir_htf": side * frame["htf_spread"].to_numpy("float64")[sig_idx],
        "dir_macd": side * frame["macd_hist"].to_numpy("float64")[sig_idx],
        "dir_cmf20": side * frame["cmf20"].to_numpy("float64")[sig_idx],
        "dir_obv48": side * frame["obv_slope48"].to_numpy("float64")[sig_idx],
        "dir_roc24": side * frame["roc24"].to_numpy("float64")[sig_idx],
        "dir_roc48": side * frame["roc48"].to_numpy("float64")[sig_idx],
        "dir_roc96": side * frame["roc96"].to_numpy("float64")[sig_idx],
        "dir_rsi14": np.where(side > 0, frame["rsi14"].to_numpy("float64")[sig_idx], 100 - frame["rsi14"].to_numpy("float64")[sig_idx]),
    }
    return {name: np.nan_to_num(value, nan=np.nan, posinf=np.nan, neginf=np.nan) for name, value in values.items()}


def make_filter_bank(values: dict[str, np.ndarray], min_signals: int) -> list[tuple[str, np.ndarray]]:
    filters: list[tuple[str, np.ndarray]] = []
    quantiles = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
    for name, value in values.items():
        clean = value[np.isfinite(value)]
        if len(clean) < min_signals:
            continue
        for q in quantiles:
            threshold = float(np.quantile(clean, q))
            for op in ("ge", "le"):
                keep = value >= threshold if op == "ge" else value <= threshold
                count = int(np.count_nonzero(keep))
                if min_signals <= count <= len(value) - min_signals:
                    filters.append((f"{name}_{op}_{threshold:.6g}", keep))
    return filters


def target_gap(metrics: dict[str, Any], min_trades: int) -> float:
    return (
        max(0.0, TARGET_ANNUALIZED_MULTIPLE - float(metrics["annualized_multiple"])) / TARGET_ANNUALIZED_MULTIPLE
        + max(0.0, TARGET_WIN_RATE - float(metrics["win_rate"])) * 5
        + max(0.0, TARGET_MAX_DD - float(metrics["max_dd"])) * 5
        + max(0.0, min_trades - float(metrics["trades"])) / max(float(min_trades), 1.0)
    )


def row_from_metrics(
    *,
    base_name: str,
    filter_name: str,
    cfg: SearchConfig,
    trades: list[Trade],
    leverage: float,
    min_trades: int,
    exact: bool,
) -> dict[str, Any]:
    full = metric_from_trades(trades, leverage, start=START_TS, end=END_TS)
    in_sample = metric_from_trades(trades, leverage, start=START_TS, end=IS_END_TS)
    oos = metric_from_trades(trades, leverage, start=IS_END_TS, end=END_TS)
    hit = (
        full["trades"] >= min_trades
        and full["annualized_multiple"] >= TARGET_ANNUALIZED_MULTIPLE
        and full["win_rate"] >= TARGET_WIN_RATE
        and full["max_dd"] >= TARGET_MAX_DD
    )
    row = {
        "name": f"{base_name}__{filter_name}",
        "base_name": base_name,
        "filter_name": filter_name,
        "exact": exact,
        "target_pass": bool(hit),
        "target_gap": target_gap(full, min_trades),
        "leverage": leverage,
        **{f"full_{key}": value for key, value in full.items()},
        **{f"is_{key}": value for key, value in in_sample.items()},
        **{f"oos_{key}": value for key, value in oos.items()},
        **asdict(cfg),
    }
    row["score"] = (
        float(row["full_annualized_multiple"])
        + 40 * float(row["full_win_rate"])
        + 10 * float(row["full_max_dd"])
        + 5 * min(float(row["oos_win_rate"]), float(row["is_win_rate"]))
    )
    return row


def approximate_filter_rows(
    *,
    cfg: SearchConfig,
    base_trades: list[Trade],
    sig_idx: np.ndarray,
    filter_keep: np.ndarray,
    filter_name: str,
    ts_to_idx: dict[int, int],
    min_trades: int,
) -> list[dict[str, Any]]:
    keep_indices = set(int(sig_idx[pos]) for pos in np.flatnonzero(filter_keep))
    selected = [trade for trade in base_trades if ts_to_idx.get(int(trade.signal_ts.value)) in keep_indices]
    if len(selected) < max(5, min_trades // 2):
        return []
    return [
        row_from_metrics(base_name=cfg.name, filter_name=filter_name, cfg=cfg, trades=selected, leverage=lev, min_trades=min_trades, exact=False)
        for lev in LEVERAGE_GRID
    ]


def main() -> None:
    args = parse_args()
    if not BASE_REPORT_PATH.exists() or not BASE_RANKING_PATH.exists():
        raise FileNotFoundError("run research_hype_5m_indicator_search.py first")
    frame = add_features(load_hype_5m())
    ranking = pd.read_csv(BASE_RANKING_PATH)
    base_rows = candidate_base_rows(ranking, args.base_configs)
    ts_to_idx = signal_indices_by_ts(frame)
    approximate_rows: list[dict[str, Any]] = []
    exact_jobs: list[tuple[SearchConfig, str, np.ndarray, float]] = []

    for row in base_rows:
        cfg = row_to_config(row)
        signal = build_signal(frame, cfg)
        sig_idx = np.flatnonzero(signal)
        if len(sig_idx) < args.min_trades:
            continue
        base_trades = simulate_trades(frame, signal, cfg)
        values = feature_values(frame, cfg, signal, sig_idx)
        filters = make_filter_bank(values, min_signals=args.min_trades)
        beam: list[tuple[str, np.ndarray, float]] = [("all", np.ones(len(sig_idx), dtype=bool), 999.0)]
        seen: set[str] = set()
        for depth in range(1, 4):
            candidates: list[tuple[str, np.ndarray, float]] = []
            for current_name, current_keep, _ in beam:
                for filter_name, keep in filters:
                    if filter_name in current_name:
                        continue
                    name = filter_name if current_name == "all" else f"{current_name}&{filter_name}"
                    if name in seen:
                        continue
                    seen.add(name)
                    merged = current_keep & keep
                    rows = approximate_filter_rows(
                        cfg=cfg,
                        base_trades=base_trades,
                        sig_idx=sig_idx,
                        filter_keep=merged,
                        filter_name=name,
                        ts_to_idx=ts_to_idx,
                        min_trades=args.min_trades,
                    )
                    if not rows:
                        continue
                    best = min(rows, key=lambda item: (item["target_gap"], -item["score"]))
                    approximate_rows.extend(rows)
                    candidates.append((name, merged, float(best["target_gap"])))
            candidates.sort(key=lambda item: item[2])
            beam = candidates[: args.beam]
        for name, keep, gap in beam[: args.beam]:
            exact_jobs.append((cfg, name, keep, gap))
        print(f"base={cfg.name} signals={len(sig_idx)} trades={len(base_trades)} filters={len(filters)} approx_rows={len(approximate_rows)}", flush=True)

    approx = pd.DataFrame(approximate_rows)
    if approx.empty:
        raise RuntimeError("no approximate refinement rows produced")
    approx = approx.sort_values(["target_pass", "target_gap", "score"], ascending=[False, True, False])
    exact_rows: list[dict[str, Any]] = []
    exact_trade_rows: list[dict[str, Any]] = []
    exact_jobs.sort(key=lambda item: item[3])
    for job_index, (cfg, filter_name, keep, _) in enumerate(exact_jobs[: args.exact_top], start=1):
        if job_index % 25 == 0:
            print(f"exact={job_index}/{min(len(exact_jobs), args.exact_top)}", flush=True)
        full_name = f"{cfg.name}__{filter_name}"
        base_signal = build_signal(frame, cfg)
        sig_idx = np.flatnonzero(base_signal)
        filtered_signal = np.zeros_like(base_signal)
        filtered_signal[sig_idx[keep]] = base_signal[sig_idx[keep]]
        trades = simulate_trades(frame, filtered_signal, cfg)
        for leverage in LEVERAGE_GRID:
            exact_rows.append(
                row_from_metrics(
                    base_name=cfg.name,
                    filter_name=filter_name,
                    cfg=cfg,
                    trades=trades,
                    leverage=leverage,
                    min_trades=args.min_trades,
                    exact=True,
                )
            )
        for trade in trades:
            item = asdict(trade)
            item["refined_name"] = full_name
            exact_trade_rows.append(item)

    exact = pd.DataFrame(exact_rows)
    if exact.empty:
        raise RuntimeError("no exact refinement rows produced")
    final = exact.sort_values(["target_pass", "target_gap", "score"], ascending=[False, True, False])
    target_hits = final.loc[final["target_pass"]].copy()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(RANKING_PATH, index=False)
    target_hits.to_csv(TARGET_HITS_PATH, index=False)
    pd.DataFrame(exact_trade_rows).to_csv(REFINED_TRADES_PATH, index=False)
    report = {
        "source_report": str(BASE_REPORT_PATH),
        "base_configs": [str(row["name"]) for row in base_rows],
        "approx_rows": int(len(approx)),
        "exact_rows": int(len(final)),
        "target_hits": int(len(target_hits)),
        "top": final.head(args.top).to_dict(orient="records"),
        "target_hit_rows": target_hits.head(args.top).to_dict(orient="records"),
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"wrote={REPORT_PATH}")
    print(f"ranking={RANKING_PATH}")
    print(f"target_hits={TARGET_HITS_PATH}")
    print(f"top_trades={REFINED_TRADES_PATH}")
    cols = [
        "name",
        "target_pass",
        "target_gap",
        "leverage",
        "full_annualized_multiple",
        "full_equity_multiple",
        "full_max_dd",
        "full_win_rate",
        "full_trades",
        "is_win_rate",
        "oos_win_rate",
        "filter_name",
        "entry_style",
        "ema_fast",
        "ema_slow",
        "stop_atr",
        "tp_atr",
    ]
    print(final[cols].head(args.top).to_string(index=False))


if __name__ == "__main__":
    main()
