from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
from datetime import UTC, datetime
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-asset-specific-search"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BASELINE_PATH = (
    FAMILY_DIR
    / "scripts/audit_binance_1d_ma7_shared_v1_long_history.py"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Development-only P2-C long pullback episode attribution."
    )
    parser.add_argument(
        "--run-date", default=datetime.now(UTC).date().isoformat()
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def probe_long_config(long_config: Any) -> Any:
    return replace(long_config, entry_mode="pullback_reclaim")


def finite(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def price_excursion(
    hourly: pd.DataFrame,
    *,
    entry_ts: pd.Timestamp,
    exit_ts: pd.Timestamp,
    entry_price: float,
    exit_price: float,
) -> dict[str, float]:
    held = hourly.loc[
        hourly["ts"].ge(entry_ts) & hourly["ts"].lt(exit_ts)
    ]
    if held.empty:
        high = max(entry_price, exit_price)
        low = min(entry_price, exit_price)
    else:
        high = max(entry_price, exit_price, float(held["high"].max()))
        low = min(entry_price, exit_price, float(held["low"].min()))
    return {
        "mfe_pct": (high / entry_price - 1.0) * 100.0,
        "mae_pct": (low / entry_price - 1.0) * 100.0,
        "giveback_pct_entry": (exit_price - high) / entry_price * 100.0,
        "max_favorable_price": high,
        "max_adverse_price": low,
    }


def bucket_trend_age(days: int) -> str:
    if days <= 2:
        return "01_1_2d"
    if days <= 5:
        return "02_3_5d"
    if days <= 10:
        return "03_6_10d"
    return "04_gt10d"


def bucket_flat_gap(days: float | None) -> str:
    if days is None:
        return "00_first"
    if days <= 2:
        return "01_0_2d"
    if days <= 5:
        return "02_3_5d"
    if days <= 10:
        return "03_6_10d"
    return "04_gt10d"


def trend_age(book: Any, features: Any, signal_index: int) -> int:
    age = 0
    for index in range(signal_index, -1, -1):
        ma = features.ma7[index]
        if not np.isfinite(ma) or float(book.close[index]) <= float(ma):
            break
        age += 1
    return age


def enrich_trades(
    trades: list[dict[str, Any]],
    *,
    baseline_entries: set[str],
    book: Any,
    features: Any,
    hourly: pd.DataFrame,
) -> list[dict[str, Any]]:
    timestamp_index = {
        pd.Timestamp(ts): index for index, ts in enumerate(book.ts)
    }
    output: list[dict[str, Any]] = []
    previous_exit: pd.Timestamp | None = None
    loss_cluster = 0
    in_loss_cluster = False
    for trade in trades:
        entry_ts = pd.Timestamp(trade["entry_ts"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        signal_ts = entry_ts - pd.Timedelta(days=1)
        if signal_ts not in timestamp_index:
            raise RuntimeError(f"missing signal day for {entry_ts}")
        signal_index = timestamp_index[signal_ts]
        atr = float(features.atr7[signal_index])
        ma = float(features.ma7[signal_index])
        previous_ma = float(features.ma7[max(0, signal_index - 5)])
        close = float(book.close[signal_index])
        entry_price = float(trade["entry_price"])
        exit_price = float(trade["exit_price"])
        excursion = price_excursion(
            hourly,
            entry_ts=entry_ts,
            exit_ts=exit_ts,
            entry_price=entry_price,
            exit_price=exit_price,
        )
        net_return = float(trade["net_return"])
        if net_return < 0.0:
            if not in_loss_cluster:
                loss_cluster += 1
            in_loss_cluster = True
            cluster_id: int | None = loss_cluster
        else:
            in_loss_cluster = False
            cluster_id = None
        gap_days = (
            None
            if previous_exit is None
            else (entry_ts - previous_exit).total_seconds() / 86_400.0
        )
        row = {
            **trade,
            "entry_kind": (
                "native_entry"
                if trade["entry_ts"] in baseline_entries
                else "added_entry"
            ),
            "signal_ts": signal_ts.isoformat(),
            "signal_close": close,
            "signal_ma7": ma,
            "signal_atr7": atr,
            "signal_distance_atr": (close - ma) / atr,
            "ma7_slope_5d_atr": (ma - previous_ma) / atr,
            "trend_age_days": trend_age(book, features, signal_index),
            "flat_gap_days": gap_days,
            "calendar_year": entry_ts.year,
            "loss_cluster_id": cluster_id,
            **excursion,
            "mfe_atr": (excursion["max_favorable_price"] - entry_price) / atr,
            "mae_atr": (excursion["max_adverse_price"] - entry_price) / atr,
        }
        row["trend_age_bucket"] = bucket_trend_age(row["trend_age_days"])
        row["flat_gap_bucket"] = bucket_flat_gap(gap_days)
        output.append(row)
        previous_exit = exit_ts
    return output


def group_summary(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    frame = pd.DataFrame(rows)
    output: list[dict[str, Any]] = []
    for value, group in frame.groupby(field, dropna=False, sort=True):
        returns = group["net_return"].to_numpy(dtype=float)
        wins = returns[returns > 0.0]
        losses = returns[returns < 0.0]
        output.append(
            {
                "group_field": field,
                "group_value": value,
                "trades": int(len(group)),
                "win_rate": float((returns > 0.0).mean()),
                "mean_return_pct": float(returns.mean() * 100.0),
                "median_return_pct": float(np.median(returns) * 100.0),
                "compound_factor": float(np.prod(1.0 + returns)),
                "profit_factor_return_space": (
                    float(wins.sum() / -losses.sum())
                    if len(losses) and -losses.sum() > 0.0
                    else (math.inf if len(wins) else math.nan)
                ),
                "median_mfe_atr": float(group["mfe_atr"].median()),
                "median_mae_atr": float(group["mae_atr"].median()),
                "median_giveback_pct_entry": float(
                    group["giveback_pct_entry"].median()
                ),
                "p10_return_pct": float(np.quantile(returns, 0.10) * 100.0),
                "p90_mfe_atr": float(group["mfe_atr"].quantile(0.90)),
                "p10_mae_atr": float(group["mae_atr"].quantile(0.10)),
            }
        )
    return output


def loss_cluster_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(rows)
    loss_rows = frame.loc[frame["loss_cluster_id"].notna()].copy()
    output: list[dict[str, Any]] = []
    for cluster_id, group in loss_rows.groupby("loss_cluster_id", sort=True):
        returns = group["net_return"].to_numpy(dtype=float)
        output.append(
            {
                "loss_cluster_id": int(cluster_id),
                "start_entry_ts": group["entry_ts"].iloc[0],
                "end_exit_ts": group["exit_ts"].iloc[-1],
                "trades": int(len(group)),
                "compound_factor": float(np.prod(1.0 + returns)),
                "compound_return_pct": float(
                    (np.prod(1.0 + returns) - 1.0) * 100.0
                ),
                "worst_trade_return_pct": float(returns.min() * 100.0),
                "median_trend_age_days": float(
                    group["trend_age_days"].median()
                ),
                "median_flat_gap_days": finite(
                    group["flat_gap_days"].dropna().median()
                )
                if group["flat_gap_days"].notna().any()
                else None,
                "exit_reason_counts": json.dumps(
                    dict(sorted(Counter(group["exit_reason"]).items())),
                    sort_keys=True,
                ),
            }
        )
    return output


def metrics(result: Any) -> dict[str, Any]:
    return {
        key: result.metrics[key]
        for key in (
            "equity_multiple",
            "net_return_pct",
            "max_drawdown_pct",
            "sharpe",
            "closed_trades",
            "win_rate",
            "profit_factor",
            "turnover_multiple",
            "cost_pct_initial",
            "funding_pct_initial",
            "max_intraday_leverage",
            "bankrupt_intraday",
        )
    }


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    baseline = load_module(BASELINE_PATH, "binance_ma7_p2c_baseline")
    transfer = baseline.load_module(
        baseline.TRANSFER_PATH,
        baseline.TRANSFER_SHA256,
        "binance_ma7_p2c_transfer",
    )
    engine = transfer.load_engine()
    long_config, short_config = baseline.v1_configs(engine)
    probe_long = probe_long_config(long_config)
    if args.self_test:
        before = asdict(long_config)
        after = asdict(probe_long)
        changed = {key for key in before if before[key] != after[key]}
        assert changed == {"entry_mode"}
        assert after["entry_mode"] == "pullback_reclaim"
        print("self-test: PASS")
        return

    manifest = json.loads(baseline.P0_MANIFEST.read_text(encoding="utf-8"))
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "campaign": "P2-C long-pullback episode attribution",
        "status": "explore / not promoted / not live-ready",
        "evidence_role": "development-only; audit and prospective not read",
        "development": {
            "start": baseline.COMMON_START.isoformat(),
            "end_exclusive": baseline.DEVELOPMENT_END.isoformat(),
        },
        "baseline_long_config": asdict(long_config),
        "probe_long_config": asdict(probe_long),
        "short_config": asdict(short_config),
        "assets": {},
    }
    all_trade_rows: list[dict[str, Any]] = []
    all_cluster_rows: list[dict[str, Any]] = []
    all_group_rows: list[dict[str, Any]] = []
    for symbol, slug in baseline.ASSETS.items():
        hourly, funding, quality = baseline.load_snapshot(symbol, slug, manifest)
        book = transfer.build_book(symbol, hourly, quality, phase_hours=0)
        features = engine.build_features(book, hourly, funding)
        start = baseline.boundary(book, baseline.COMMON_START)
        end = baseline.boundary(book, baseline.DEVELOPMENT_END)
        paths: dict[str, Any] = {}
        for label, long_leg, short_leg in (
            ("v1_combined", long_config, short_config),
            ("probe_combined", probe_long, short_config),
            ("v1_long_only", long_config, None),
            ("probe_long_only", probe_long, None),
        ):
            paths[label] = baseline.run_window(
                engine,
                book,
                features,
                long_leg,
                short_leg,
                start=start,
                end=end,
                slippage=engine.BASE_SLIPPAGE,
                signal_lag=0,
                retain=False,
            )
        baseline_entries = {
            row["entry_ts"] for row in paths["v1_long_only"].trades
        }
        enriched = enrich_trades(
            paths["probe_long_only"].trades,
            baseline_entries=baseline_entries,
            book=book,
            features=features,
            hourly=hourly,
        )
        summaries: list[dict[str, Any]] = []
        for field in (
            "entry_kind",
            "exit_reason",
            "trend_age_bucket",
            "flat_gap_bucket",
            "calendar_year",
        ):
            summaries.extend(group_summary(enriched, field))
        clusters = loss_cluster_summary(enriched)
        for row in enriched:
            all_trade_rows.append({"symbol": symbol, **row})
        for row in summaries:
            all_group_rows.append({"symbol": symbol, **row})
        for row in clusters:
            all_cluster_rows.append({"symbol": symbol, **row})
        payload["assets"][symbol] = {
            "paths": {label: metrics(result) for label, result in paths.items()},
            "probe_trade_count": len(enriched),
            "native_entry_count": sum(
                row["entry_kind"] == "native_entry" for row in enriched
            ),
            "added_entry_count": sum(
                row["entry_kind"] == "added_entry" for row in enriched
            ),
            "group_summaries": summaries,
            "loss_clusters": clusters,
        }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_ma7_p2c_long_pullback_episodes_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(clean_json(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame(all_trade_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_trades.csv", index=False
    )
    pd.DataFrame(all_group_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_groups.csv", index=False
    )
    pd.DataFrame(all_cluster_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_loss_clusters.csv", index=False
    )
    print(
        json.dumps(
            clean_json(
                {
                    symbol: {
                        "paths": value["paths"],
                        "native_entry_count": value["native_entry_count"],
                        "added_entry_count": value["added_entry_count"],
                        "entry_kind": [
                            row
                            for row in value["group_summaries"]
                            if row["group_field"] == "entry_kind"
                        ],
                        "loss_clusters": value["loss_clusters"],
                    }
                    for symbol, value in payload["assets"].items()
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

