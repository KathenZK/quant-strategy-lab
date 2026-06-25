from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_filter_refinement import feature_values
from research_hype_5m_indicator_search import (
    DATA_ROOT,
    SYMBOL_FILE,
    SearchConfig,
    Trade,
    add_features,
    build_signal,
    simulate_trades,
)


REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_positive_payoff_search.json")
RANKING_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_positive_payoff_search_ranking.csv")
TARGET_HITS_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_positive_payoff_search_target_hits.csv")
TRADES_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_positive_payoff_search_top_trades.csv")

TARGET_ANNUALIZED_MULTIPLE = 20.0
TARGET_WIN_RATE = 0.60
TARGET_PAYOFF_RATIO = 1.0
LEVERAGE_GRID = (1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search HYPE 5m positive-payoff strategies across all Binance data.")
    parser.add_argument("--max-configs", type=int, default=6000)
    parser.add_argument("--seed", type=int, default=20260623)
    parser.add_argument("--top", type=int, default=120)
    parser.add_argument("--refine-configs", type=int, default=60)
    parser.add_argument("--max-filter-combos", type=int, default=180)
    parser.add_argument("--min-full-trades", type=int, default=80)
    parser.add_argument("--min-slice-trades", type=int, default=12)
    parser.add_argument("--min-forward-trades", type=int, default=5)
    return parser.parse_args()


def load_all_hype_5m() -> pd.DataFrame:
    files = sorted(DATA_ROOT.glob(f"date=*/{SYMBOL_FILE}"))
    if not files:
        raise FileNotFoundError(f"no local HYPE 5m parquet files under {DATA_ROOT}")
    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    expected = pd.date_range(frame["ts"].iloc[0], frame["ts"].iloc[-1], freq="5min")
    missing = expected.difference(frame["ts"])
    if len(missing):
        raise RuntimeError(f"HYPE 5m data has {len(missing)} missing bars, first={missing[0]}")
    return frame


def validation_slices(frame: pd.DataFrame, args: argparse.Namespace) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return [
        {"name": "full", "start": start, "end": end, "min_trades": args.min_full_trades},
        {
            "name": "slice_2025_05_30_2025_09_01",
            "start": start,
            "end": pd.Timestamp("2025-09-01T00:00:00Z"),
            "min_trades": args.min_slice_trades,
        },
        {
            "name": "slice_2025_09_01_2025_12_01",
            "start": pd.Timestamp("2025-09-01T00:00:00Z"),
            "end": pd.Timestamp("2025-12-01T00:00:00Z"),
            "min_trades": args.min_slice_trades,
        },
        {
            "name": "slice_2025_12_01_2026_03_01",
            "start": pd.Timestamp("2025-12-01T00:00:00Z"),
            "end": pd.Timestamp("2026-03-01T00:00:00Z"),
            "min_trades": args.min_slice_trades,
        },
        {
            "name": "slice_2026_03_01_2026_06_01",
            "start": pd.Timestamp("2026-03-01T00:00:00Z"),
            "end": pd.Timestamp("2026-06-01T00:00:00Z"),
            "min_trades": args.min_slice_trades,
        },
        {
            "name": "forward_2026_06_01_latest",
            "start": pd.Timestamp("2026-06-01T00:00:00Z"),
            "end": end,
            "min_trades": args.min_forward_trades,
        },
    ]


def metric_from_trades(trades: list[Trade], leverage: float, *, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, float | int]:
    selected = [trade for trade in trades if start <= trade.entry_ts < end]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    if not selected:
        return {
            "trades": 0,
            "equity_multiple": 1.0,
            "annualized_multiple": 1.0,
            "total_return": 0.0,
            "max_dd": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade": 0.0,
            "avg_win": 0.0,
            "avg_loss_abs": 0.0,
            "payoff_ratio": 0.0,
            "worst_trade": 0.0,
            "best_trade": 0.0,
        }
    raw_rets = np.array([trade.net_ret_1x for trade in selected], dtype=float)
    rets = raw_rets * leverage
    maes = np.array([trade.mae_1x * leverage for trade in selected], dtype=float)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for ret, mae in zip(rets, maes, strict=True):
        trough = equity * max(0.001, 1.0 + mae)
        max_dd = min(max_dd, trough / peak - 1.0)
        equity *= max(0.001, 1.0 + ret)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    wins = raw_rets[raw_rets > 0]
    losses = raw_rets[raw_rets <= 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss_abs = float(abs(losses.mean())) if len(losses) else 0.0
    payoff_ratio = float(avg_win / avg_loss_abs) if avg_loss_abs > 0 else float("inf") if avg_win > 0 else 0.0
    profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else float("inf")
    annualized = float(equity ** (365.25 / days)) if equity > 0 else 0.0
    return {
        "trades": int(len(selected)),
        "equity_multiple": float(equity),
        "annualized_multiple": annualized,
        "total_return": float(equity - 1.0),
        "max_dd": float(max_dd),
        "win_rate": float((raw_rets > 0).mean()),
        "profit_factor": profit_factor,
        "avg_trade": float(rets.mean()),
        "avg_win": avg_win,
        "avg_loss_abs": avg_loss_abs,
        "payoff_ratio": payoff_ratio,
        "worst_trade": float(rets.min()),
        "best_trade": float(rets.max()),
    }


def slice_pass(metrics: dict[str, Any], min_trades: int) -> bool:
    return (
        int(metrics["trades"]) >= min_trades
        and float(metrics["annualized_multiple"]) >= TARGET_ANNUALIZED_MULTIPLE
        and float(metrics["win_rate"]) >= TARGET_WIN_RATE
        and float(metrics["payoff_ratio"]) > TARGET_PAYOFF_RATIO
    )


def slice_gap(metrics: dict[str, Any], min_trades: int) -> float:
    annualized = float(metrics["annualized_multiple"])
    win_rate = float(metrics["win_rate"])
    payoff = float(metrics["payoff_ratio"])
    if not np.isfinite(payoff):
        payoff = 10.0
    return (
        max(0.0, TARGET_ANNUALIZED_MULTIPLE - annualized) / TARGET_ANNUALIZED_MULTIPLE
        + max(0.0, TARGET_WIN_RATE - win_rate) * 6.0
        + max(0.0, TARGET_PAYOFF_RATIO - payoff) * 4.0
        + max(0.0, min_trades - float(metrics["trades"])) / max(float(min_trades), 1.0)
    )


def row_from_eval(
    *,
    cfg: SearchConfig,
    filter_name: str,
    stage: str,
    leverage: float,
    trades: list[Trade],
    slices: list[dict[str, Any]],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": cfg.name if filter_name == "all" else f"{cfg.name}__{filter_name}",
        "base_name": cfg.name,
        "filter_name": filter_name,
        "stage": stage,
        "leverage": leverage,
        **asdict(cfg),
    }
    passes: list[bool] = []
    gaps: list[float] = []
    for item in slices:
        metrics = metric_from_trades(trades, leverage, start=item["start"], end=item["end"])
        ok = slice_pass(metrics, int(item["min_trades"]))
        passes.append(ok)
        gaps.append(slice_gap(metrics, int(item["min_trades"])))
        for key, value in metrics.items():
            row[f"{item['name']}_{key}"] = value
        row[f"{item['name']}_pass"] = bool(ok)
    row["target_pass"] = bool(all(passes))
    row["target_gap"] = float(np.mean(gaps) + np.max(gaps))
    row["worst_slice_win_rate"] = min(float(row[f"{item['name']}_win_rate"]) for item in slices)
    row["worst_slice_payoff_ratio"] = min(float(row[f"{item['name']}_payoff_ratio"]) for item in slices)
    row["worst_slice_annualized_multiple"] = min(float(row[f"{item['name']}_annualized_multiple"]) for item in slices)
    row["worst_slice_max_dd"] = min(float(row[f"{item['name']}_max_dd"]) for item in slices)
    row["score"] = (
        min(200.0, float(row["full_annualized_multiple"]))
        + 60.0 * float(row["worst_slice_win_rate"])
        + 25.0 * min(3.0, float(row["worst_slice_payoff_ratio"]))
        + 8.0 * float(row["worst_slice_max_dd"])
        - 20.0 * float(row["target_gap"])
    )
    return row


def curated_configs() -> list[SearchConfig]:
    rows: list[SearchConfig] = []
    idx = 0
    ema_pairs = [(9, 55), (12, 96), (21, 96), (34, 144), (55, 192), (96, 384)]
    for side_mode in ("both", "long", "short"):
        for entry_style in ("breakout", "momentum", "pullback_resume", "squeeze_breakout", "channel_reclaim"):
            for ema_fast, ema_slow in ema_pairs:
                for stop_atr, tp_atr in ((1.0, 2.0), (1.5, 3.0), (2.0, 4.0), (2.5, 5.0), (3.0, 6.0)):
                    idx += 1
                    rows.append(
                        SearchConfig(
                            name=f"HYPE_PP_C{idx:04d}",
                            side_mode=side_mode,
                            ema_fast=ema_fast,
                            ema_slow=ema_slow,
                            entry_style=entry_style,
                            donchian=48,
                            roc_window=24,
                            min_regime_age=0,
                            max_regime_age=768,
                            breakout_buffer=0.0,
                            pullback_buffer=0.005,
                            max_dist_ema=0.12,
                            min_dir_roc=0.0 if entry_style in {"breakout", "momentum"} else -0.01,
                            min_dir_rsi=45.0,
                            max_dir_rsi=82.0,
                            min_adx=14.0,
                            max_chop=70.0,
                            max_atr_ratio=2.0,
                            min_rvol=0.0,
                            min_dir_cmf=-0.15,
                            require_macd=False,
                            require_obv=False,
                            require_htf=True,
                            min_efficiency=0.0,
                            stop_atr=stop_atr,
                            tp_atr=tp_atr,
                            trail_atr=0.0,
                            max_hold_bars=96,
                            min_hold_bars=0,
                            exit_ema=0,
                            cooldown_bars=6,
                        )
                    )
    return rows


def random_config(rng: random.Random, idx: int) -> SearchConfig:
    ema_fast, ema_slow = rng.choice([(9, 55), (12, 96), (21, 96), (34, 144), (55, 192), (96, 384)])
    stop_atr = rng.choice([0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0])
    tp_atr = stop_atr * rng.choice([1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0])
    entry_style = rng.choice(
        [
            "breakout",
            "breakout",
            "momentum",
            "pullback_resume",
            "squeeze_breakout",
            "channel_reclaim",
            "trend_rsi_rebound",
            "bb_reversion",
            "ema_deviation_revert",
        ]
    )
    min_age = rng.choice([0, 3, 6, 12, 24, 48])
    max_age = rng.choice([48, 96, 192, 384, 768, 2000])
    if min_age >= max_age:
        min_age = 0
    max_dir_rsi = rng.choice([68.0, 72.0, 76.0, 82.0, 90.0, 100.0])
    return SearchConfig(
        name=f"HYPE_PP_R{idx:05d}",
        side_mode=rng.choice(["both", "both", "long", "short"]),
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        entry_style=entry_style,
        donchian=rng.choice([24, 48, 96, 192, 288]),
        roc_window=rng.choice([24, 48, 96, 192]),
        min_regime_age=min_age,
        max_regime_age=max_age,
        breakout_buffer=rng.choice([0.0, 0.001, 0.002, 0.004, 0.006]),
        pullback_buffer=rng.choice([0.0, 0.0025, 0.005, 0.01, 0.015, 0.025]),
        max_dist_ema=rng.choice([0.02, 0.04, 0.06, 0.08, 0.12, 0.18]),
        min_dir_roc=rng.choice([-0.01, -0.0025, 0.0, 0.0025, 0.005, 0.01, 0.02]),
        min_dir_rsi=rng.choice([35.0, 40.0, 45.0, 50.0, 55.0]),
        max_dir_rsi=max_dir_rsi,
        min_adx=rng.choice([0.0, 10.0, 14.0, 18.0, 22.0, 28.0, 34.0]),
        max_chop=rng.choice([42.0, 48.0, 55.0, 62.0, 70.0, 100.0]),
        max_atr_ratio=rng.choice([0.9, 1.05, 1.2, 1.5, 2.0, 99.0]),
        min_rvol=rng.choice([0.0, 0.6, 0.8, 1.0, 1.2, 1.6, 2.0]),
        min_dir_cmf=rng.choice([-0.30, -0.15, -0.05, 0.0, 0.05, 0.10]),
        require_macd=rng.choice([False, False, True]),
        require_obv=rng.choice([False, False, True]),
        require_htf=rng.choice([False, True, True]),
        min_efficiency=rng.choice([0.0, 0.025, 0.05, 0.10, 0.15, 0.25]),
        stop_atr=stop_atr,
        tp_atr=tp_atr,
        trail_atr=rng.choice([0.0, 0.0, stop_atr, stop_atr * 1.5, stop_atr * 2.0]),
        max_hold_bars=rng.choice([12, 24, 48, 96, 192, 384, 576]),
        min_hold_bars=rng.choice([0, 0, 1, 3, 6]),
        exit_ema=rng.choice([0, 0, 9, 21, 55, 96]),
        cooldown_bars=rng.choice([0, 3, 6, 12, 24]),
    )


def filter_bank(values: dict[str, np.ndarray], min_signals: int) -> list[tuple[str, np.ndarray]]:
    filters: list[tuple[str, np.ndarray]] = []
    for name, value in values.items():
        clean = value[np.isfinite(value)]
        if len(clean) < min_signals:
            continue
        for q in (0.15, 0.25, 0.35, 0.50, 0.65, 0.75, 0.85):
            threshold = float(np.quantile(clean, q))
            for op in ("ge", "le"):
                keep = value >= threshold if op == "ge" else value <= threshold
                count = int(np.count_nonzero(keep))
                if min_signals <= count <= len(value) - min_signals:
                    filters.append((f"{name}_{op}_{threshold:.6g}", keep))
    return filters


def apply_keep(signal: np.ndarray, sig_idx: np.ndarray, keep: np.ndarray) -> np.ndarray:
    filtered = np.zeros_like(signal)
    filtered[sig_idx[keep]] = signal[sig_idx[keep]]
    previous_same = np.r_[False, (filtered[1:] != 0) & (filtered[1:] == filtered[:-1])]
    filtered[previous_same] = 0
    return filtered


def evaluate_config(
    *,
    cfg: SearchConfig,
    trades: list[Trade],
    stage: str,
    filter_name: str,
    slices: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        row_from_eval(cfg=cfg, filter_name=filter_name, stage=stage, leverage=leverage, trades=trades, slices=slices)
        for leverage in LEVERAGE_GRID
    ]


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    frame = add_features(load_all_hype_5m())
    slices = validation_slices(frame, args)
    configs = curated_configs()
    while len(configs) < args.max_configs:
        configs.append(random_config(rng, len(configs) + 1))

    rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    base_cache: list[tuple[SearchConfig, np.ndarray, list[Trade], float]] = []

    for index, cfg in enumerate(configs[: args.max_configs], start=1):
        if index % 250 == 0:
            print(f"base={index}/{args.max_configs} rows={len(rows)}", flush=True)
        signal = build_signal(frame, cfg)
        trades = simulate_trades(frame, signal, cfg)
        if len(trades) < args.min_full_trades // 2:
            continue
        eval_rows = evaluate_config(cfg=cfg, trades=trades, stage="base", filter_name="all", slices=slices)
        rows.extend(eval_rows)
        best_gap = min(float(row["target_gap"]) for row in eval_rows)
        base_cache.append((cfg, signal, trades, best_gap))

    if not rows:
        raise RuntimeError("no base rows generated")
    base_rank = pd.DataFrame(rows).sort_values(["target_pass", "target_gap", "score"], ascending=[False, True, False])
    refine_jobs = sorted(base_cache, key=lambda item: item[3])[: args.refine_configs]

    for job_index, (cfg, signal, _trades, _gap) in enumerate(refine_jobs, start=1):
        print(f"refine={job_index}/{len(refine_jobs)} cfg={cfg.name}", flush=True)
        sig_idx = np.flatnonzero(signal)
        if len(sig_idx) < args.min_full_trades:
            continue
        values = feature_values(frame, cfg, signal, sig_idx)
        filters = filter_bank(values, min_signals=max(args.min_forward_trades, 5))
        candidates: list[tuple[str, np.ndarray]] = []
        for name, keep in filters:
            candidates.append((name, keep))
        rng.shuffle(filters)
        for left_name, left_keep in filters[:80]:
            for right_name, right_keep in filters[80:140]:
                if left_name.split("_", 1)[0] == right_name.split("_", 1)[0]:
                    continue
                candidates.append((f"{left_name}&{right_name}", left_keep & right_keep))
                if len(candidates) >= args.max_filter_combos:
                    break
            if len(candidates) >= args.max_filter_combos:
                break

        seen: set[str] = set()
        for filter_name, keep in candidates[: args.max_filter_combos]:
            if filter_name in seen or int(np.count_nonzero(keep)) < args.min_forward_trades:
                continue
            seen.add(filter_name)
            filtered_signal = apply_keep(signal, sig_idx, keep)
            trades = simulate_trades(frame, filtered_signal, cfg)
            if len(trades) < args.min_full_trades // 2:
                continue
            rows.extend(evaluate_config(cfg=cfg, trades=trades, stage="refined", filter_name=filter_name, slices=slices))

    final = pd.DataFrame(rows).sort_values(["target_pass", "target_gap", "score"], ascending=[False, True, False])
    target_hits = final.loc[final["target_pass"]].copy()
    top_names = final.head(args.top)["name"].drop_duplicates().tolist()
    # Rebuild top trade rows for inspection.
    name_to_cfg = {cfg.name: cfg for cfg in configs}
    for _, row in final.head(args.top).iterrows():
        base_name = str(row["base_name"])
        cfg = name_to_cfg.get(base_name)
        if cfg is None:
            continue
        signal = build_signal(frame, cfg)
        filter_name = str(row["filter_name"])
        if filter_name != "all":
            sig_idx = np.flatnonzero(signal)
            values = feature_values(frame, cfg, signal, sig_idx)
            keep = np.ones(len(sig_idx), dtype=bool)
            for part in filter_name.split("&"):
                feature, op, threshold = part.rsplit("_", 2)
                threshold_value = float(threshold)
                keep &= values[feature] >= threshold_value if op == "ge" else values[feature] <= threshold_value
            signal = apply_keep(signal, sig_idx, keep)
        trades = simulate_trades(frame, signal, cfg)
        for trade in trades:
            item = asdict(trade)
            item["name"] = str(row["name"])
            item["base_name"] = base_name
            item["filter_name"] = filter_name
            trade_rows.append(item)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(RANKING_PATH, index=False)
    target_hits.to_csv(TARGET_HITS_PATH, index=False)
    pd.DataFrame(trade_rows).to_csv(TRADES_PATH, index=False)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "data": {
                    "symbol": "HYPE/USDT:USDT",
                    "exchange": "binance",
                    "market_type": "perp",
                    "timeframe": "5m",
                    "first_bar": frame["ts"].iloc[0].isoformat(),
                    "latest_bar": frame["ts"].iloc[-1].isoformat(),
                    "rows": int(len(frame)),
                    "missing_bars": 0,
                },
                "targets": {
                    "annualized_multiple_each_slice": TARGET_ANNUALIZED_MULTIPLE,
                    "win_rate_each_slice": TARGET_WIN_RATE,
                    "payoff_ratio_each_slice": TARGET_PAYOFF_RATIO,
                    "payoff_definition": "avg winning trade net_ret_1x / abs(avg losing trade net_ret_1x), must be > 1",
                },
                "slices": [
                    {
                        "name": item["name"],
                        "start": item["start"].isoformat(),
                        "end": item["end"].isoformat(),
                        "min_trades": item["min_trades"],
                    }
                    for item in slices
                ],
                "search": {
                    "max_configs": args.max_configs,
                    "base_rows": int(len(base_rank)),
                    "final_rows": int(len(final)),
                    "target_hits": int(len(target_hits)),
                    "top_trade_names": top_names,
                },
                "target_hit_rows": target_hits.head(args.top).to_dict(orient="records"),
                "top_rows": final.head(args.top).to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    print(f"wrote={REPORT_PATH}")
    print(f"ranking={RANKING_PATH}")
    print(f"target_hits={TARGET_HITS_PATH} count={len(target_hits)}")
    cols = [
        "name",
        "stage",
        "target_pass",
        "target_gap",
        "leverage",
        "full_annualized_multiple",
        "full_win_rate",
        "full_payoff_ratio",
        "full_trades",
        "worst_slice_annualized_multiple",
        "worst_slice_win_rate",
        "worst_slice_payoff_ratio",
        "worst_slice_max_dd",
        "forward_2026_06_01_latest_annualized_multiple",
        "forward_2026_06_01_latest_win_rate",
        "forward_2026_06_01_latest_payoff_ratio",
        "forward_2026_06_01_latest_trades",
        "entry_style",
        "side_mode",
        "ema_fast",
        "ema_slow",
        "stop_atr",
        "tp_atr",
        "trail_atr",
        "max_hold_bars",
        "filter_name",
    ]
    print(final[cols].head(args.top).to_string(index=False))


if __name__ == "__main__":
    main()
