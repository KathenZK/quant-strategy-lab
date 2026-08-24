from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
import importlib.util
import json
import math
import multiprocessing as mp
from pathlib import Path
import random
import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-asset-specific-search"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BASELINE_PATH = (
    FAMILY_DIR
    / "scripts/audit_binance_1d_ma7_shared_v1_long_history.py"
)
SEED = 20260812
DEFAULT_SAMPLES = 20_000
DEFAULT_STAGE1_KEEP = 300
DEFAULT_STABLE_KEEP = 60
DEFAULT_PAIR_AUDIT = 100
DEFAULT_WORKERS = 6
CHUNK_SIZE = 40

_ENGINE: Any = None
_CONTEXTS: dict[str, dict[str, Any]] = {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P2-E development-only hard-MDD BTC/ETH shared MA7 search."
    )
    parser.add_argument(
        "--run-date", default=datetime.now(UTC).date().isoformat()
    )
    parser.add_argument("--samples-per-side", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--stage1-keep", type=int, default=DEFAULT_STAGE1_KEEP)
    parser.add_argument("--stable-keep", type=int, default=DEFAULT_STABLE_KEEP)
    parser.add_argument("--pair-audit", type=int, default=DEFAULT_PAIR_AUDIT)
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


def chunks(values: list[Any], size: int = CHUNK_SIZE) -> Iterable[list[Any]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def compact(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        key: metrics[key]
        for key in (
            "equity_multiple",
            "max_drawdown_pct",
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


def score_from_assets(asset_metrics: dict[str, dict[str, Any]]) -> float:
    equities = [float(row["equity_multiple"]) for row in asset_metrics.values()]
    if any(equity <= 0.0 for equity in equities):
        return -math.inf
    violation = sum(
        max(0.0, abs(min(0.0, float(row["max_drawdown_pct"]))) / 100.0 - 0.20)
        for row in asset_metrics.values()
    )
    return min(math.log(equity) for equity in equities) - 5.0 * violation


def hard_target(asset_metrics: dict[str, dict[str, Any]]) -> bool:
    return all(
        float(row["equity_multiple"]) >= 20.0
        and float(row["max_drawdown_pct"]) >= -20.0
        and not bool(row["bankrupt_intraday"])
        for row in asset_metrics.values()
    )


def run_config(
    config: Any,
    *,
    symbol: str,
    short_config: Any | None = None,
    long_config: Any | None = None,
    start: int | None = None,
    end: int | None = None,
    slippage: float | None = None,
    signal_lag: int = 0,
) -> Any:
    context = _CONTEXTS[symbol]
    if config.side > 0 and long_config is None:
        long_config = config
    if config.side < 0 and short_config is None:
        short_config = config
    return _ENGINE.backtest(
        context["book"],
        context["features"],
        long_config=long_config,
        short_config=short_config,
        start_index=context["start"] if start is None else start,
        terminal_index=context["end"] if end is None else end,
        slippage=_ENGINE.BASE_SLIPPAGE if slippage is None else slippage,
        signal_lag=signal_lag,
        retain=False,
    )


def stage1_worker(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for config_dict in batch:
        config = _ENGINE.Config(**config_dict)
        assets: dict[str, dict[str, Any]] = {}
        for symbol in _CONTEXTS:
            assets[symbol] = compact(run_config(config, symbol=symbol).metrics)
        eligible = all(
            not row["bankrupt_intraday"]
            and row["equity_multiple"] > 0.0
            and row["closed_trades"] >= 10
            for row in assets.values()
        )
        output.append(
            {
                "config": config_dict,
                "side": config.side,
                "eligible": eligible,
                "score": score_from_assets(assets) if eligible else -math.inf,
                "assets": assets,
            }
        )
    return output


def stability_worker(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for config_dict in batch:
        config = _ENGINE.Config(**config_dict)
        assets: dict[str, Any] = {}
        all_logs: list[float] = []
        all_positive = True
        total_windows = 0
        positive_windows = 0
        worst_mdd = 0.0
        for symbol, context in _CONTEXTS.items():
            full: dict[str, Any] = {}
            for stress, slippage, lag in (
                ("base", _ENGINE.BASE_SLIPPAGE, 0),
                ("stress_8bps", _ENGINE.STRESS_SLIPPAGE, 0),
                ("one_day_extra_delay", _ENGINE.BASE_SLIPPAGE, 1),
            ):
                metrics = compact(
                    run_config(
                        config,
                        symbol=symbol,
                        slippage=slippage,
                        signal_lag=lag,
                    ).metrics
                )
                full[stress] = metrics
                equity = float(metrics["equity_multiple"])
                all_positive = all_positive and equity > 1.0
                all_logs.append(math.log(max(equity, 1e-12)))
                worst_mdd = min(worst_mdd, float(metrics["max_drawdown_pct"]))
            windows: list[dict[str, Any]] = []
            for scope in ("calendar", "rolling"):
                for label, start, end in context[scope]:
                    metrics = compact(
                        run_config(
                            config,
                            symbol=symbol,
                            start=start,
                            end=end,
                        ).metrics
                    )
                    equity = float(metrics["equity_multiple"])
                    total_windows += 1
                    positive_windows += int(equity > 1.0)
                    all_logs.append(math.log(max(equity, 1e-12)))
                    worst_mdd = min(
                        worst_mdd, float(metrics["max_drawdown_pct"])
                    )
                    windows.append(
                        {"scope": scope, "window": label, **metrics}
                    )
            assets[symbol] = {"full": full, "windows": windows}
        positive_share = positive_windows / total_windows
        violation = max(0.0, abs(worst_mdd) / 100.0 - 0.20)
        stable_score = (
            min(all_logs)
            + 0.5 * float(np.median(all_logs))
            + positive_share
            - 4.0 * violation
            if all_positive
            else -math.inf
        )
        output.append(
            {
                "config": config_dict,
                "side": config.side,
                "eligible": all_positive,
                "stable_score": stable_score,
                "positive_window_share": positive_share,
                "worst_mdd_pct": worst_mdd,
                "assets": assets,
            }
        )
    return output


def pair_worker(batch: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for long_dict, short_dict in batch:
        long_config = _ENGINE.Config(**long_dict)
        short_config = _ENGINE.Config(**short_dict)
        assets: dict[str, dict[str, Any]] = {}
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
            assets[symbol] = compact(result.metrics)
        output.append(
            {
                "long_config": long_dict,
                "short_config": short_dict,
                "score": score_from_assets(assets),
                "hard_target": hard_target(assets),
                "dd_safe": all(
                    row["max_drawdown_pct"] >= -20.0
                    and not row["bankrupt_intraday"]
                    for row in assets.values()
                ),
                "min_equity_multiple": min(
                    row["equity_multiple"] for row in assets.values()
                ),
                "worst_mdd_pct": min(
                    row["max_drawdown_pct"] for row in assets.values()
                ),
                "assets": assets,
            }
        )
    return output


def pair_audit_worker(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for pair in batch:
        long_config = _ENGINE.Config(**pair["long_config"])
        short_config = _ENGINE.Config(**pair["short_config"])
        assets: dict[str, Any] = {}
        development_pass = True
        for symbol, context in _CONTEXTS.items():
            full: dict[str, Any] = {}
            for variant, long_leg, short_leg in (
                ("combined", long_config, short_config),
                ("long_only", long_config, None),
                ("short_only", None, short_config),
            ):
                for stress, slippage, lag in (
                    ("base", _ENGINE.BASE_SLIPPAGE, 0),
                    ("stress_8bps", _ENGINE.STRESS_SLIPPAGE, 0),
                    ("one_day_extra_delay", _ENGINE.BASE_SLIPPAGE, 1),
                ):
                    result = _ENGINE.backtest(
                        context["book"],
                        context["features"],
                        long_config=long_leg,
                        short_config=short_leg,
                        start_index=context["start"],
                        terminal_index=context["end"],
                        slippage=slippage,
                        signal_lag=lag,
                        retain=False,
                    )
                    full[f"{variant}__{stress}"] = compact(result.metrics)
            windows: list[dict[str, Any]] = []
            for scope in ("calendar", "rolling"):
                for label, start, end in context[scope]:
                    result = _ENGINE.backtest(
                        context["book"],
                        context["features"],
                        long_config=long_config,
                        short_config=short_config,
                        start_index=start,
                        terminal_index=end,
                        retain=False,
                    )
                    windows.append(
                        {
                            "scope": scope,
                            "window": label,
                            **compact(result.metrics),
                        }
                    )
            shares = {
                scope: float(
                    np.mean(
                        [
                            row["equity_multiple"] > 1.0
                            for row in windows
                            if row["scope"] == scope
                        ]
                    )
                )
                for scope in ("calendar", "rolling")
            }
            base = full["combined__base"]
            stress = full["combined__stress_8bps"]
            delayed = full["combined__one_day_extra_delay"]
            asset_pass = (
                base["equity_multiple"] >= 20.0
                and base["max_drawdown_pct"] >= -20.0
                and stress["equity_multiple"] > 1.0
                and stress["max_drawdown_pct"] >= -25.0
                and delayed["equity_multiple"] > 1.0
                and shares["calendar"] >= 0.70
                and shares["rolling"] >= 0.70
                and not base["bankrupt_intraday"]
            )
            development_pass = development_pass and asset_pass
            assets[symbol] = {
                "full": full,
                "windows": windows,
                "positive_shares": shares,
                "candidate_gate_pass": asset_pass,
            }
        output.append(
            {
                **pair,
                "development_candidate": development_pass,
                "audit": assets,
            }
        )
    return output


def flatten_stage1(rows: list[dict[str, Any]]) -> pd.DataFrame:
    output: list[dict[str, Any]] = []
    for rank, row in enumerate(rows, start=1):
        flat = {
            "rank": rank,
            "side": row["side"],
            "eligible": row["eligible"],
            "score": row["score"],
            "config_json": json.dumps(row["config"], sort_keys=True),
        }
        for symbol, metrics in row["assets"].items():
            flat.update(
                {f"{symbol.lower()}_{key}": value for key, value in metrics.items()}
            )
        output.append(flat)
    return pd.DataFrame(output)


def flatten_pairs(rows: list[dict[str, Any]]) -> pd.DataFrame:
    output: list[dict[str, Any]] = []
    for rank, row in enumerate(rows, start=1):
        flat = {
            "rank": rank,
            "score": row["score"],
            "hard_target": row["hard_target"],
            "dd_safe": row["dd_safe"],
            "min_equity_multiple": row["min_equity_multiple"],
            "worst_mdd_pct": row["worst_mdd_pct"],
            "long_config_json": json.dumps(row["long_config"], sort_keys=True),
            "short_config_json": json.dumps(row["short_config"], sort_keys=True),
        }
        for symbol, metrics in row["assets"].items():
            flat.update(
                {f"{symbol.lower()}_{key}": value for key, value in metrics.items()}
            )
        output.append(flat)
    return pd.DataFrame(output)


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


def run_parallel(
    worker: Any,
    values: list[Any],
    *,
    workers: int,
    label: str,
) -> list[dict[str, Any]]:
    batches = list(chunks(values))
    output: list[dict[str, Any]] = []
    context = mp.get_context("fork")
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        for index, rows in enumerate(pool.map(worker, batches), start=1):
            output.extend(rows)
            if index % 25 == 0 or index == len(batches):
                print(
                    f"{label}: {index}/{len(batches)} batches, {len(output)} rows",
                    flush=True,
                )
    return output


def main() -> None:
    global _ENGINE, _CONTEXTS
    args = parse_args()
    baseline = load_module(BASELINE_PATH, "binance_ma7_p2e_baseline")
    transfer = baseline.load_module(
        baseline.TRANSFER_PATH,
        baseline.TRANSFER_SHA256,
        "binance_ma7_p2e_transfer",
    )
    _ENGINE = transfer.load_engine()
    if args.self_test:
        rng_a = random.Random(SEED)
        rng_b = random.Random(SEED)
        first = [asdict(row) for row in _ENGINE.unique_configs(1, rng_a, 20)]
        second = [asdict(row) for row in _ENGINE.unique_configs(1, rng_b, 20)]
        assert first == second
        assert len({json.dumps(row, sort_keys=True) for row in first}) == 20
        print("self-test: PASS")
        return

    manifest = json.loads(baseline.P0_MANIFEST.read_text(encoding="utf-8"))
    for symbol, slug in baseline.ASSETS.items():
        hourly, funding, quality = baseline.load_snapshot(symbol, slug, manifest)
        book = transfer.build_book(symbol, hourly, quality, phase_hours=0)
        features = _ENGINE.build_features(book, hourly, funding)
        start = baseline.boundary(book, baseline.COMMON_START)
        end = baseline.boundary(book, baseline.DEVELOPMENT_END)
        timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
        calendar: list[tuple[str, int, int]] = []
        for year in range(2019, 2026):
            left_ts = max(
                baseline.COMMON_START,
                pd.Timestamp(f"{year}-01-01T00:00:00Z"),
            )
            right_ts = min(
                baseline.DEVELOPMENT_END,
                pd.Timestamp(f"{year + 1}-01-01T00:00:00Z"),
            )
            if right_ts > left_ts:
                calendar.append(
                    (
                        str(year),
                        int(timestamps.searchsorted(left_ts)),
                        int(timestamps.searchsorted(right_ts)),
                    )
                )
        rolling = []
        left = start
        while left + 730 <= end:
            rolling.append((f"{left}_{left + 730}", left, left + 730))
            left += 365
        _CONTEXTS[symbol] = {
            "book": book,
            "features": features,
            "start": start,
            "end": end,
            "calendar": calendar,
            "rolling": rolling,
        }

    rng = random.Random(SEED)
    configs = {
        side: [
            asdict(row)
            for row in _ENGINE.unique_configs(
                1 if side == "long" else -1,
                rng,
                args.samples_per_side,
            )
        ]
        for side in ("long", "short")
    }
    stage1: dict[str, list[dict[str, Any]]] = {}
    stable: dict[str, list[dict[str, Any]]] = {}
    for side in ("long", "short"):
        rows = run_parallel(
            stage1_worker,
            configs[side],
            workers=args.workers,
            label=f"stage1-{side}",
        )
        rows.sort(key=lambda row: row["score"], reverse=True)
        stage1[side] = rows[: args.stage1_keep]
        stable_rows = run_parallel(
            stability_worker,
            [row["config"] for row in stage1[side]],
            workers=args.workers,
            label=f"stability-{side}",
        )
        stable_rows = [row for row in stable_rows if row["eligible"]]
        stable_rows.sort(key=lambda row: row["stable_score"], reverse=True)
        stable[side] = stable_rows[: args.stable_keep]

    pair_inputs = [
        (long_row["config"], short_row["config"])
        for long_row in stable["long"]
        for short_row in stable["short"]
    ]
    pairs = run_parallel(
        pair_worker,
        pair_inputs,
        workers=args.workers,
        label="pair-search",
    )
    pairs.sort(
        key=lambda row: (
            row["hard_target"],
            row["dd_safe"],
            row["score"],
            row["min_equity_multiple"],
        ),
        reverse=True,
    )
    hard_rows = [row for row in pairs if row["hard_target"]]
    audit_pool: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in [*hard_rows, *pairs[: args.pair_audit]]:
        key = (
            json.dumps(row["long_config"], sort_keys=True),
            json.dumps(row["short_config"], sort_keys=True),
        )
        if key not in seen:
            seen.add(key)
            audit_pool.append(row)
    audited = run_parallel(
        pair_audit_worker,
        audit_pool,
        workers=args.workers,
        label="pair-audit",
    )
    candidates = [row for row in audited if row["development_candidate"]]
    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "campaign": "P2-E hard-MDD shared search",
        "status": "explore / not promoted / not live-ready",
        "evidence_role": "development-only; audit and prospective not read",
        "contract": {
            "seed": SEED,
            "samples_per_side": args.samples_per_side,
            "stage1_keep": args.stage1_keep,
            "stable_keep": args.stable_keep,
            "pair_count": len(pairs),
            "pair_audit_count": len(audited),
        },
        "counts": {
            "stage1_long": len(stage1["long"]),
            "stage1_short": len(stage1["short"]),
            "stable_long": len(stable["long"]),
            "stable_short": len(stable["short"]),
            "dd_safe_pairs": sum(row["dd_safe"] for row in pairs),
            "hard_target_pairs": len(hard_rows),
            "development_candidates": len(candidates),
        },
        "best_pair": pairs[0] if pairs else None,
        "best_dd_safe_pair": next(
            (row for row in pairs if row["dd_safe"]), None
        ),
        "development_candidates": candidates,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_ma7_p2e_hard_mdd_shared_search_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(clean_json(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for side in ("long", "short"):
        flatten_stage1(stage1[side]).to_csv(
            ARTIFACT_DIR / f"{stem}_stage1_{side}.csv", index=False
        )
        pd.DataFrame(
            [
                {
                    "rank": rank,
                    "side": row["side"],
                    "stable_score": row["stable_score"],
                    "positive_window_share": row["positive_window_share"],
                    "worst_mdd_pct": row["worst_mdd_pct"],
                    "config_json": json.dumps(row["config"], sort_keys=True),
                }
                for rank, row in enumerate(stable[side], start=1)
            ]
        ).to_csv(
            ARTIFACT_DIR / f"{stem}_stability_{side}.csv", index=False
        )
    flatten_pairs(pairs[: max(args.pair_audit, len(hard_rows))]).to_csv(
        ARTIFACT_DIR / f"{stem}_pairs.csv", index=False
    )
    audit_rows: list[dict[str, Any]] = []
    for rank, row in enumerate(audited, start=1):
        for symbol, asset in row["audit"].items():
            for key, metrics in asset["full"].items():
                variant, stress = key.split("__", 1)
                audit_rows.append(
                    {
                        "rank": rank,
                        "development_candidate": row[
                            "development_candidate"
                        ],
                        "symbol": symbol,
                        "scope": "full_development",
                        "window": "full_development",
                        "variant": variant,
                        "stress": stress,
                        **metrics,
                    }
                )
            for metrics in asset["windows"]:
                audit_rows.append(
                    {
                        "rank": rank,
                        "development_candidate": row[
                            "development_candidate"
                        ],
                        "symbol": symbol,
                        "scope": metrics["scope"],
                        "window": metrics["window"],
                        "variant": "combined",
                        "stress": "base",
                        **{
                            key: value
                            for key, value in metrics.items()
                            if key not in {"scope", "window"}
                        },
                    }
                )
    pd.DataFrame(audit_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_audit_metrics.csv", index=False
    )
    print(json.dumps(clean_json(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

