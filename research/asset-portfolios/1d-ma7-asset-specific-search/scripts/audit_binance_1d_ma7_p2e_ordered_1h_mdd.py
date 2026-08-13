from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
import importlib.util
import json
import math
import multiprocessing as mp
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
P2E_STEM = "binance_1d_ma7_p2e_hard_mdd_shared_search_2026-08-12"
CHUNK_SIZE = 20
DEFAULT_WORKERS = 6

_ENGINE: Any = None
_CONTEXTS: dict[str, dict[str, Any]] = {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ordered-1h MDD repair for all fixed P2-E pairs."
    )
    parser.add_argument(
        "--run-date", default=datetime.now(UTC).date().isoformat()
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
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


def target_from_flat(
    equity: float,
    side: int,
    price: float,
    cost_rate: float,
) -> tuple[float, float]:
    post_equity = equity / (1.0 + cost_rate)
    qty = side * post_equity / price
    return qty, post_equity


def trade_entry_equity(
    trade: dict[str, Any],
    *,
    fallback: float,
) -> float:
    net_return = float(trade["net_return"])
    net_pnl = float(trade["net_pnl"])
    if abs(net_return) > 1e-14:
        return net_pnl / net_return
    return fallback


def protective_stop_hour(
    hourly: pd.DataFrame,
    *,
    exit_ts: pd.Timestamp,
    exit_price: float,
) -> pd.Timestamp | None:
    """Return the preceding hit hour, or None for an open-gap stop."""
    exit_rows = hourly.loc[hourly["ts"].eq(exit_ts), "open"]
    if not exit_rows.empty and math.isclose(
        float(exit_rows.iloc[0]),
        exit_price,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        return None
    return exit_ts - pd.Timedelta(hours=1)


def ordered_mdd_replay(
    result: Any,
    *,
    hourly: pd.DataFrame,
    funding: pd.DataFrame,
    cost_rate: float,
) -> dict[str, Any]:
    hourly_work = hourly[["ts", "open", "high", "low", "close"]].copy()
    hourly_work["ts"] = pd.to_datetime(hourly_work["ts"], utc=True)
    funding_work = funding[["ts", "funding_rate", "mark_price"]].copy()
    funding_work["ts"] = pd.to_datetime(funding_work["ts"], utc=True)
    peak = 1.0
    max_drawdown = 0.0
    mdd_event: dict[str, Any] | None = None
    previous_exit_equity = 1.0
    replay_errors: list[float] = []

    def observe(
        equity: float,
        *,
        ts: pd.Timestamp,
        point: str,
        side: int,
        trade_index: int,
    ) -> None:
        nonlocal peak, max_drawdown, mdd_event
        peak = max(peak, equity)
        drawdown = equity / peak - 1.0
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            mdd_event = {
                "ts": ts.isoformat(),
                "point": point,
                "side": "long" if side > 0 else "short",
                "trade_index": trade_index,
                "equity": equity,
                "peak_equity": peak,
                "drawdown_pct": drawdown * 100.0,
            }

    for trade_index, trade in enumerate(result.trades, start=1):
        side = 1 if trade["side"] == "long" else -1
        entry_ts = pd.Timestamp(trade["entry_ts"])
        exit_ts = pd.Timestamp(trade["exit_ts"])
        entry_price = float(trade["entry_price"])
        exit_price = float(trade["exit_price"])
        entry_equity = trade_entry_equity(
            trade, fallback=previous_exit_equity
        )
        if trade_index > 1:
            replay_errors.append(entry_equity - previous_exit_equity)
        observe(
            entry_equity,
            ts=entry_ts,
            point="pre_entry",
            side=side,
            trade_index=trade_index,
        )
        qty, post_entry_equity = target_from_flat(
            entry_equity, side, entry_price, cost_rate
        )
        observe(
            post_entry_equity,
            ts=entry_ts,
            point="post_entry_cost",
            side=side,
            trade_index=trade_index,
        )
        held = hourly_work.loc[
            hourly_work["ts"].ge(entry_ts)
            & hourly_work["ts"].lt(exit_ts)
        ]
        events = funding_work.loc[
            funding_work["ts"].ge(entry_ts)
            & funding_work["ts"].lt(exit_ts)
        ]
        cumulative_funding = 0.0
        event_groups = {
            ts: group
            for ts, group in events.groupby(events["ts"].dt.floor("h"))
        }
        stop_exit = trade["exit_reason"] == "protective_stop"
        stop_hour = (
            protective_stop_hour(
                hourly_work,
                exit_ts=exit_ts,
                exit_price=exit_price,
            )
            if stop_exit
            else None
        )
        for row in held.itertuples(index=False):
            ts = pd.Timestamp(row.ts)
            event_group = event_groups.get(ts)
            if event_group is not None:
                for event in event_group.itertuples(index=False):
                    cumulative_funding += (
                        qty
                        * float(event.mark_price)
                        * float(event.funding_rate)
                    )
            prices = [float(row.open)]
            favorable = float(row.high) if side > 0 else float(row.low)
            adverse = float(row.low) if side > 0 else float(row.high)
            if stop_exit and ts == stop_hour:
                if side > 0:
                    adverse = max(adverse, exit_price)
                else:
                    adverse = min(adverse, exit_price)
                prices.extend([favorable, adverse])
                labels = ("open", "favorable", "adverse_stop")
            else:
                prices.extend([favorable, adverse, float(row.close)])
                labels = ("open", "favorable", "adverse", "close")
            for label, price in zip(labels, prices, strict=True):
                equity = (
                    post_entry_equity
                    + qty * (price - entry_price)
                    - cumulative_funding
                )
                observe(
                    equity,
                    ts=ts,
                    point=label,
                    side=side,
                    trade_index=trade_index,
                )
        exit_equity = entry_equity * (1.0 + float(trade["net_return"]))
        observe(
            exit_equity,
            ts=exit_ts,
            point="post_exit_cost",
            side=side,
            trade_index=trade_index,
        )
        previous_exit_equity = exit_equity
    terminal_equity = float(result.metrics["equity_multiple"])
    terminal_error = previous_exit_equity - terminal_equity
    if abs(terminal_error) > 1e-9:
        raise RuntimeError(
            f"ordered replay terminal drift: {terminal_error}"
        )
    max_continuity_error = max(
        (abs(value) for value in replay_errors), default=0.0
    )
    if max_continuity_error > 1e-9:
        raise RuntimeError(
            f"ordered replay trade continuity drift: {max_continuity_error}"
        )
    return {
        "ordered_1h_mdd_pct": max_drawdown * 100.0,
        "conservative_daily_extrema_mdd_pct": float(
            result.metrics["max_drawdown_pct"]
        ),
        "equity_multiple": terminal_equity,
        "closed_trades": int(result.metrics["closed_trades"]),
        "mdd_event": mdd_event,
        "terminal_replay_error": terminal_error,
        "max_trade_continuity_error": max_continuity_error,
    }


def pair_worker(
    batch: list[tuple[dict[str, Any], dict[str, Any]]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for long_dict, short_dict in batch:
        long_config = _ENGINE.Config(**long_dict)
        short_config = _ENGINE.Config(**short_dict)
        assets: dict[str, Any] = {}
        for symbol, context in _CONTEXTS.items():
            result = _ENGINE.backtest(
                context["book"],
                context["features"],
                long_config=long_config,
                short_config=short_config,
                start_index=context["start"],
                terminal_index=context["end"],
                retain=False,
            )
            assets[symbol] = ordered_mdd_replay(
                result,
                hourly=context["hourly"],
                funding=context["funding"],
                cost_rate=_ENGINE.FEE + _ENGINE.BASE_SLIPPAGE,
            )
        dd_safe = all(
            row["ordered_1h_mdd_pct"] >= -20.0
            for row in assets.values()
        )
        hard_target = dd_safe and all(
            row["equity_multiple"] >= 20.0 for row in assets.values()
        )
        output.append(
            {
                "long_config": long_dict,
                "short_config": short_dict,
                "dd_safe": dd_safe,
                "hard_target": hard_target,
                "min_equity_multiple": min(
                    row["equity_multiple"] for row in assets.values()
                ),
                "worst_ordered_1h_mdd_pct": min(
                    row["ordered_1h_mdd_pct"] for row in assets.values()
                ),
                "worst_conservative_mdd_pct": min(
                    row["conservative_daily_extrema_mdd_pct"]
                    for row in assets.values()
                ),
                "assets": assets,
            }
        )
    return output


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
    global _ENGINE, _CONTEXTS
    args = parse_args()
    baseline = load_module(BASELINE_PATH, "binance_ma7_p2e_mdd_baseline")
    transfer = baseline.load_module(
        baseline.TRANSFER_PATH,
        baseline.TRANSFER_SHA256,
        "binance_ma7_p2e_mdd_transfer",
    )
    _ENGINE = transfer.load_engine()
    if args.self_test:
        qty, post = target_from_flat(1.0, 1, 100.0, 0.0014)
        assert math.isclose(post, 1.0 / 1.0014)
        assert math.isclose(qty, post / 100.0)
        print("self-test: PASS")
        return

    manifest = json.loads(baseline.P0_MANIFEST.read_text(encoding="utf-8"))
    for symbol, slug in baseline.ASSETS.items():
        hourly, _, quality = baseline.load_snapshot(symbol, slug, manifest)
        funding = pd.read_parquet(
            baseline.P0_DIR / f"{slug}_perp_funding_mark.parquet"
        )
        funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
        book = transfer.build_book(
            symbol,
            hourly,
            quality,
            phase_hours=0,
        )
        features = _ENGINE.build_features(
            book,
            hourly,
            funding[["ts", "funding_rate"]],
        )
        _CONTEXTS[symbol] = {
            "book": book,
            "features": features,
            "hourly": hourly,
            "funding": funding,
            "start": baseline.boundary(book, baseline.COMMON_START),
            "end": baseline.boundary(book, baseline.DEVELOPMENT_END),
        }
    stable = {}
    for side in ("long", "short"):
        frame = pd.read_csv(
            ARTIFACT_DIR / f"{P2E_STEM}_stability_{side}.csv"
        )
        stable[side] = [json.loads(value) for value in frame["config_json"]]
    pair_inputs = [
        (long_config, short_config)
        for long_config in stable["long"]
        for short_config in stable["short"]
    ]
    batches = [
        pair_inputs[index : index + CHUNK_SIZE]
        for index in range(0, len(pair_inputs), CHUNK_SIZE)
    ]
    rows: list[dict[str, Any]] = []
    context = mp.get_context("fork")
    with ProcessPoolExecutor(
        max_workers=args.workers, mp_context=context
    ) as pool:
        for index, batch_rows in enumerate(
            pool.map(pair_worker, batches), start=1
        ):
            rows.extend(batch_rows)
            if index % 25 == 0 or index == len(batches):
                print(
                    f"ordered-mdd: {index}/{len(batches)} batches, "
                    f"{len(rows)} pairs",
                    flush=True,
                )
    rows.sort(
        key=lambda row: (
            row["hard_target"],
            row["dd_safe"],
            row["min_equity_multiple"],
            row["worst_ordered_1h_mdd_pct"],
        ),
        reverse=True,
    )
    dd_safe_rows = [row for row in rows if row["dd_safe"]]
    hard_rows = [row for row in rows if row["hard_target"]]
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "campaign": "P2-E ordered-1h MDD repair",
        "status": "explore / not promoted / not live-ready",
        "evidence_role": "development-only; audit and prospective not read",
        "pair_count": len(rows),
        "ordered_dd_safe_pairs": len(dd_safe_rows),
        "ordered_hard_target_pairs": len(hard_rows),
        "best_pair": rows[0],
        "best_dd_safe_pair": dd_safe_rows[0] if dd_safe_rows else None,
        "hard_target_pairs": hard_rows,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_ma7_p2e_ordered_1h_mdd_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(clean_json(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    flat_rows: list[dict[str, Any]] = []
    for rank, row in enumerate(rows, start=1):
        flat = {
            "rank": rank,
            "dd_safe": row["dd_safe"],
            "hard_target": row["hard_target"],
            "min_equity_multiple": row["min_equity_multiple"],
            "worst_ordered_1h_mdd_pct": row[
                "worst_ordered_1h_mdd_pct"
            ],
            "worst_conservative_mdd_pct": row[
                "worst_conservative_mdd_pct"
            ],
            "long_config_json": json.dumps(
                row["long_config"], sort_keys=True
            ),
            "short_config_json": json.dumps(
                row["short_config"], sort_keys=True
            ),
        }
        for symbol, metrics in row["assets"].items():
            flat.update(
                {
                    f"{symbol.lower()}_{key}": value
                    for key, value in metrics.items()
                    if key != "mdd_event"
                }
            )
        flat_rows.append(flat)
    pd.DataFrame(flat_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_pairs.csv", index=False
    )
    print(json.dumps(clean_json(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
