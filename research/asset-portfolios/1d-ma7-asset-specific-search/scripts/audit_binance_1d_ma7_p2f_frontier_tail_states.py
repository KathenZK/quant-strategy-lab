from __future__ import annotations

import argparse
from collections import Counter
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
    FAMILY_DIR / "scripts/audit_binance_1d_ma7_shared_v1_long_history.py"
)
ORDERED_PATH = (
    FAMILY_DIR / "scripts/audit_binance_1d_ma7_p2e_ordered_1h_mdd.py"
)
P2E_PAIRS = (
    ARTIFACT_DIR
    / "binance_1d_ma7_p2e_ordered_1h_mdd_2026-08-12_pairs.csv"
)
STRATUM_SIZE = 100
SLOW_WINDOWS = (30, 90, 200)
SLOW_SLOPE_DAYS = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Attribute P2-E frontier ordered-MDD event states."
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


def balanced_score(row: pd.Series) -> float:
    min_equity = max(float(row["min_equity_multiple"]), 1e-12)
    drawdown = abs(float(row["worst_ordered_1h_mdd_pct"])) / 100.0
    return math.log(min_equity) - 3.0 * max(0.0, drawdown - 0.20)


def select_frontier(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    work["balanced_score"] = work.apply(balanced_score, axis=1)
    memberships: dict[tuple[str, str], set[str]] = {}
    selected_rows: dict[tuple[str, str], pd.Series] = {}
    strata = {
        "growth": work.nlargest(STRATUM_SIZE, "min_equity_multiple"),
        "risk": work.nlargest(STRATUM_SIZE, "worst_ordered_1h_mdd_pct"),
        "balanced": work.nlargest(STRATUM_SIZE, "balanced_score"),
    }
    for stratum, rows in strata.items():
        for _, row in rows.iterrows():
            key = (
                str(row["long_config_json"]),
                str(row["short_config_json"]),
            )
            memberships.setdefault(key, set()).add(stratum)
            selected_rows[key] = row
    output: list[dict[str, Any]] = []
    for key, row in selected_rows.items():
        payload = row.to_dict()
        payload["strata"] = ",".join(sorted(memberships[key]))
        output.append(payload)
    return pd.DataFrame(output).sort_values("rank").reset_index(drop=True)


def percentile_rank(values: np.ndarray, index: int, window: int) -> float:
    left = max(0, index - window + 1)
    current = float(values[index])
    history = values[left : index + 1]
    history = history[np.isfinite(history)]
    if not np.isfinite(current) or len(history) < 30:
        return math.nan
    return float(np.mean(history <= current))


def event_price(
    event: dict[str, Any],
    hourly: pd.DataFrame,
    *,
    side: int,
) -> float:
    ts = pd.Timestamp(event["ts"])
    rows = hourly.loc[hourly["ts"].eq(ts)]
    if rows.empty:
        raise RuntimeError(f"missing event hour {ts}")
    row = rows.iloc[0]
    point = str(event["point"])
    if point.startswith("adverse"):
        return float(row["low"] if side > 0 else row["high"])
    if point == "favorable":
        return float(row["high"] if side > 0 else row["low"])
    if point == "close":
        return float(row["close"])
    return float(row["open"])


def path_excursions(
    trade: dict[str, Any],
    event: dict[str, Any],
    hourly: pd.DataFrame,
    *,
    side: int,
) -> dict[str, float | bool]:
    entry_ts = pd.Timestamp(trade["entry_ts"])
    event_ts = pd.Timestamp(event["ts"])
    entry_price = float(trade["entry_price"])
    held = hourly.loc[
        hourly["ts"].ge(entry_ts) & hourly["ts"].le(event_ts)
    ]
    if held.empty:
        mfe = mae = 0.0
    elif side > 0:
        mfe = float(held["high"].max() / entry_price - 1.0)
        mae = float(held["low"].min() / entry_price - 1.0)
    else:
        mfe = float(1.0 - held["low"].min() / entry_price)
        mae = float(1.0 - held["high"].max() / entry_price)
    at_event = side * (event_price(event, hourly, side=side) - entry_price)
    at_event /= entry_price
    giveback = max(0.0, mfe - at_event)
    fraction = giveback / mfe if mfe > 0.0 else math.nan
    return {
        "intrahour_mfe_to_event": mfe,
        "intrahour_mae_to_event": mae,
        "event_gross_return": at_event,
        "intrahour_giveback_from_mfe": giveback,
        "intrahour_giveback_fraction": fraction,
    }


def closed_daily_lifecycle(
    trade: dict[str, Any],
    event: dict[str, Any],
    *,
    side: int,
    book_ts: pd.DatetimeIndex,
    close: np.ndarray,
    known_index: int,
    hourly: pd.DataFrame,
) -> dict[str, float | bool]:
    entry_ts = pd.Timestamp(trade["entry_ts"])
    entry_day = entry_ts.floor("D")
    entry_index = int(book_ts.searchsorted(entry_day, side="left"))
    entry_price = float(trade["entry_price"])
    known_closes = close[entry_index : known_index + 1]
    if len(known_closes) == 0:
        mfe = 0.0
    elif side > 0:
        mfe = float(known_closes.max() / entry_price - 1.0)
    else:
        mfe = float(1.0 - known_closes.min() / entry_price)
    event_return = side * (
        event_price(event, hourly, side=side) - entry_price
    ) / entry_price
    giveback = max(0.0, mfe - event_return)
    fraction = giveback / mfe if mfe > 0.0 else math.nan
    return {
        "prior_daily_close_mfe": mfe,
        "prior_daily_close_giveback_to_event": giveback,
        "prior_daily_close_giveback_fraction": fraction,
        "lifecycle_label": bool(mfe > 0.0 and fraction >= 0.50),
    }


def attribute_event(
    *,
    symbol: str,
    pair_row: pd.Series,
    result: Any,
    replay: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    event = replay["mdd_event"]
    if event is None:
        raise RuntimeError("frontier path unexpectedly has no MDD event")
    trade = result.trades[int(event["trade_index"]) - 1]
    side = 1 if trade["side"] == "long" else -1
    event_ts = pd.Timestamp(event["ts"])
    day = event_ts.floor("D")
    book_ts = pd.DatetimeIndex(context["book"].ts)
    known_index = int(book_ts.searchsorted(day, side="left")) - 1
    if known_index < 29:
        raise RuntimeError(f"insufficient known history at {event_ts}")
    close = context["close"]
    row: dict[str, Any] = {
        "pair_rank": int(pair_row["rank"]),
        "strata": str(pair_row["strata"]),
        "symbol": symbol,
        "event_ts": event_ts.isoformat(),
        "event_year": event_ts.year,
        "event_month": event_ts.strftime("%Y-%m"),
        "side": trade["side"],
        "trade_index": int(event["trade_index"]),
        "entry_ts": trade["entry_ts"],
        "exit_ts": trade["exit_ts"],
        "trade_age_days": (
            event_ts - pd.Timestamp(trade["entry_ts"])
        ).total_seconds()
        / 86_400.0,
        "entry_mode": (
            json.loads(
                pair_row[
                    "long_config_json" if side > 0 else "short_config_json"
                ]
            )["entry_mode"]
        ),
        "exit_reason": trade["exit_reason"],
        "trade_net_return": float(trade["net_return"]),
        "ordered_1h_mdd_pct": float(replay["ordered_1h_mdd_pct"]),
        "natr7": float(context["natr7"][known_index]),
        "natr7_trailing_365_percentile": percentile_rank(
            context["natr7"], known_index, 365
        ),
        "vol_state_label": bool(
            percentile_rank(context["natr7"], known_index, 365) >= 0.80
        ),
    }
    for window in SLOW_WINDOWS:
        slow = context[f"sma{window}"]
        available = bool(
            known_index >= SLOW_SLOPE_DAYS
            and np.isfinite(slow[known_index])
            and np.isfinite(slow[known_index - SLOW_SLOPE_DAYS])
        )
        level = bool(
            available
            and side * (close[known_index] - slow[known_index]) > 0.0
        )
        slope = bool(
            available
            and side
            * (slow[known_index] - slow[known_index - SLOW_SLOPE_DAYS])
            > 0.0
        )
        row[f"sma{window}_available"] = available
        row[f"sma{window}_level_aligned"] = level
        row[f"sma{window}_slope_aligned"] = slope
        row[f"sma{window}_level_slope_conflict"] = bool(
            available and not (level and slope)
        )
    row.update(
        path_excursions(
            trade,
            event,
            context["hourly"],
            side=side,
        )
    )
    row.update(
        closed_daily_lifecycle(
            trade,
            event,
            side=side,
            book_ts=book_ts,
            close=close,
            known_index=known_index,
            hourly=context["hourly"],
        )
    )
    return row


def coverage(rows: pd.DataFrame) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    labels = {
        **{
            f"SLOW_REGIME_SMA{window}": (
                f"sma{window}_level_slope_conflict"
            )
            for window in SLOW_WINDOWS
        },
        "VOL_STATE": "vol_state_label",
        "LIFECYCLE": "lifecycle_label",
    }
    expanded = rows.assign(stratum=rows["strata"].str.split(",")).explode(
        "stratum"
    )
    for (symbol, stratum), group in expanded.groupby(
        ["symbol", "stratum"]
    ):
        for mechanism, column in labels.items():
            output.append(
                {
                    "symbol": symbol,
                    "stratum": stratum,
                    "mechanism": mechanism,
                    "event_count": len(group),
                    "covered_count": int(group[column].sum()),
                    "coverage": float(group[column].mean()),
                }
            )
    return output


def gate_decision(coverage_rows: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(coverage_rows)
    decisions: dict[str, Any] = {}
    for mechanism, group in frame.groupby("mechanism"):
        minimum = float(group["coverage"].min())
        decisions[mechanism] = {
            "minimum_asset_stratum_coverage": minimum,
            "pass": minimum >= 0.60,
        }
    passed = [
        (name, row["minimum_asset_stratum_coverage"])
        for name, row in decisions.items()
        if row["pass"]
    ]
    priority = {
        "SLOW_REGIME_SMA30": 3,
        "SLOW_REGIME_SMA90": 3,
        "SLOW_REGIME_SMA200": 3,
        "VOL_STATE": 2,
        "LIFECYCLE": 1,
    }
    passed.sort(key=lambda item: (item[1], priority[item[0]]), reverse=True)
    return {
        "mechanisms": decisions,
        "selected_next_mechanism": passed[0][0] if passed else None,
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
    if args.self_test:
        row = pd.Series(
            {
                "min_equity_multiple": math.e,
                "worst_ordered_1h_mdd_pct": -30.0,
            }
        )
        assert math.isclose(balanced_score(row), 0.7)
        print("self-test: PASS")
        return
    baseline = load_module(BASELINE_PATH, "binance_ma7_p2f_baseline")
    ordered = load_module(ORDERED_PATH, "binance_ma7_p2f_ordered")
    transfer = baseline.load_module(
        baseline.TRANSFER_PATH,
        baseline.TRANSFER_SHA256,
        "binance_ma7_p2f_transfer",
    )
    engine = transfer.load_engine()
    ordered._ENGINE = engine
    manifest = json.loads(baseline.P0_MANIFEST.read_text(encoding="utf-8"))
    contexts: dict[str, dict[str, Any]] = {}
    for symbol, slug in baseline.ASSETS.items():
        hourly, _, quality = baseline.load_snapshot(symbol, slug, manifest)
        hourly["ts"] = pd.to_datetime(hourly["ts"], utc=True)
        funding = pd.read_parquet(
            baseline.P0_DIR / f"{slug}_perp_funding_mark.parquet"
        )
        funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
        book = transfer.build_book(symbol, hourly, quality, phase_hours=0)
        features = engine.build_features(
            book, hourly, funding[["ts", "funding_rate"]]
        )
        close = np.asarray(book.close, dtype=float)
        context: dict[str, Any] = {
            "book": book,
            "features": features,
            "hourly": hourly,
            "funding": funding,
            "close": close,
            "natr7": features.atr7 / close,
            "start": baseline.boundary(book, baseline.COMMON_START),
            "end": baseline.boundary(book, baseline.DEVELOPMENT_END),
        }
        for window in SLOW_WINDOWS:
            context[f"sma{window}"] = (
                pd.Series(close)
                .rolling(window, min_periods=window)
                .mean()
                .to_numpy()
            )
        contexts[symbol] = context
    frontier = select_frontier(pd.read_csv(P2E_PAIRS))
    detail: list[dict[str, Any]] = []
    for pair_index, pair_row in frontier.iterrows():
        long_config = engine.Config(
            **json.loads(pair_row["long_config_json"])
        )
        short_config = engine.Config(
            **json.loads(pair_row["short_config_json"])
        )
        for symbol, context in contexts.items():
            result = engine.backtest(
                context["book"],
                context["features"],
                long_config=long_config,
                short_config=short_config,
                start_index=context["start"],
                terminal_index=context["end"],
                retain=False,
            )
            replay = ordered.ordered_mdd_replay(
                result,
                hourly=context["hourly"],
                funding=context["funding"],
                cost_rate=engine.FEE + engine.BASE_SLIPPAGE,
            )
            detail.append(
                attribute_event(
                    symbol=symbol,
                    pair_row=pair_row,
                    result=result,
                    replay=replay,
                    context=context,
                )
            )
        if (pair_index + 1) % 25 == 0 or pair_index + 1 == len(frontier):
            print(
                f"tail-state: {pair_index + 1}/{len(frontier)} pairs",
                flush=True,
            )
    detail_frame = pd.DataFrame(detail)
    coverage_rows = coverage(detail_frame)
    clusters: dict[str, Any] = {}
    for symbol, group in detail_frame.groupby("symbol"):
        clusters[symbol] = {
            "top_months": Counter(group["event_month"]).most_common(10),
            "top_years": Counter(group["event_year"]).most_common(),
            "side_counts": Counter(group["side"]).most_common(),
        }
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "campaign": "P2-F frontier tail-state attribution",
        "status": "explore / not promoted / not live-ready",
        "evidence_role": "development-only; audit and prospective not read",
        "input_pairs": 3600,
        "stratum_size": STRATUM_SIZE,
        "unique_frontier_pairs": len(frontier),
        "detail_rows": len(detail_frame),
        "coverage": coverage_rows,
        "gate_decision": gate_decision(coverage_rows),
        "clusters": clusters,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_ma7_p2f_frontier_tail_states_{args.run_date}"
    frontier.to_csv(ARTIFACT_DIR / f"{stem}_manifest.csv", index=False)
    detail_frame.to_csv(ARTIFACT_DIR / f"{stem}_events.csv", index=False)
    pd.DataFrame(coverage_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_coverage.csv", index=False
    )
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(clean_json(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(clean_json(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
