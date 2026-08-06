from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = (
    ROOT / "research/asset-portfolios/1d-ma7-asset-specific-search"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
TRANSFER_PATH = (
    ROOT
    / "research/asset-portfolios/1d-ma7-separated-trend-transfer/scripts/"
    "research_binance_1d_ma7_separated_trend_transfer.py"
)
TRANSFER_SHA256 = (
    "d4b68183616c34af1eac5a583fdcf3fbec12778a48f7a4765731cb3750eb895a"
)
ASSETS = {
    "BTCUSDT": "btc_usdt_usdt",
    "ETHUSDT": "eth_usdt_usdt",
}
PHASES = (0, 12)
HOLDOUT_START = pd.Timestamp("2026-02-01T00:00:00Z")
DEFAULT_SEED = 20260805
DEFAULT_SAMPLES = 20_000
DEFAULT_SHORTLIST = 120
DEFAULT_SHARED_AUDIT_POOL = 240
DEFAULT_PAIR_POOL = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Asset-specific and shared BTC/ETH daily SMA7 parameter search."
        )
    )
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--samples-per-side",
        type=int,
        default=DEFAULT_SAMPLES,
    )
    parser.add_argument(
        "--shortlist",
        type=int,
        default=DEFAULT_SHORTLIST,
    )
    parser.add_argument(
        "--shared-audit-pool",
        type=int,
        default=DEFAULT_SHARED_AUDIT_POOL,
    )
    parser.add_argument(
        "--pair-pool",
        type=int,
        default=DEFAULT_PAIR_POOL,
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Reuse selected configs from the existing dated summary.",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_module(path: Path, expected_hash: str, name: str) -> Any:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_hash:
        raise RuntimeError(
            f"{path.name} drift: expected {expected_hash}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def config_key(config: Any) -> str:
    return json.dumps(
        asdict(config),
        sort_keys=True,
        separators=(",", ":"),
    )


def finite_shared_score(values: list[float]) -> float:
    if not values or not all(np.isfinite(value) for value in values):
        return -math.inf
    logs = np.asarray(values, dtype=float)
    return float(logs.min() + 0.5 * np.median(logs))


def rank_shared_stage1(
    frames: dict[str, pd.DataFrame],
    *,
    limit: int,
) -> list[Any]:
    maps = {
        symbol: {
            config_key(row.config): row
            for row in frame.itertuples(index=False)
        }
        for symbol, frame in frames.items()
    }
    first = next(iter(frames.values()))
    rows: list[dict[str, Any]] = []
    for row in first.itertuples(index=False):
        key = config_key(row.config)
        asset_rows = [mapping[key] for mapping in maps.values()]
        scores = [float(item.score) for item in asset_rows]
        rows.append(
            {
                "config": row.config,
                "shared_score": finite_shared_score(scores),
                "min_equity": min(
                    float(item.equity_multiple) for item in asset_rows
                ),
                "total_trades": sum(
                    int(item.closed_trades) for item in asset_rows
                ),
            }
        )
    ranked = pd.DataFrame(rows).sort_values(
        ["shared_score", "min_equity", "total_trades"],
        ascending=[False, False, False],
    )
    return list(ranked.head(limit)["config"])


def rank_shared_stability(
    engine: Any,
    configs: list[Any],
    books: dict[str, Any],
    features: dict[str, Any],
    prefit_ends: dict[str, int],
    *,
    limit: int,
) -> tuple[list[Any], pd.DataFrame]:
    frames = {
        symbol: engine.stability_audit(
            configs,
            books[symbol],
            features[symbol],
            prefit_end=prefit_ends[symbol],
        )
        for symbol in ASSETS
    }
    maps = {
        symbol: {
            config_key(row.config): row
            for row in frame.itertuples(index=False)
        }
        for symbol, frame in frames.items()
    }
    rows: list[dict[str, Any]] = []
    for config in configs:
        key = config_key(config)
        asset_rows = [mapping[key] for mapping in maps.values()]
        robust_scores = [
            float(item.robust_score) for item in asset_rows
        ]
        rows.append(
            {
                "config": config,
                "shared_robust_score": finite_shared_score(
                    robust_scores
                ),
                "min_prefit_equity": min(
                    float(item.prefit_equity) for item in asset_rows
                ),
                "min_profitable_windows": min(
                    int(item.profitable_windows) for item in asset_rows
                ),
                "worst_window_mdd_pct": min(
                    float(item.worst_window_mdd_pct)
                    for item in asset_rows
                ),
                **{
                    f"{symbol.lower()}_robust_score": float(
                        maps[symbol][key].robust_score
                    )
                    for symbol in ASSETS
                },
                **{
                    f"{symbol.lower()}_prefit_equity": float(
                        maps[symbol][key].prefit_equity
                    )
                    for symbol in ASSETS
                },
            }
        )
    ranked = pd.DataFrame(rows).sort_values(
        [
            "shared_robust_score",
            "min_prefit_equity",
            "worst_window_mdd_pct",
        ],
        ascending=[False, False, False],
    )
    return list(ranked.head(limit)["config"]), ranked


def rank_shared_pairs(
    engine: Any,
    long_configs: list[Any],
    short_configs: list[Any],
    books: dict[str, Any],
    features: dict[str, Any],
    prefit_ends: dict[str, int],
) -> pd.DataFrame:
    frames = {
        symbol: engine.pair_search(
            long_configs,
            short_configs,
            books[symbol],
            features[symbol],
            prefit_end=prefit_ends[symbol],
        )
        for symbol in ASSETS
    }
    maps: dict[str, dict[tuple[str, str], Any]] = {}
    for symbol, frame in frames.items():
        maps[symbol] = {
            (
                config_key(row.long_config),
                config_key(row.short_config),
            ): row
            for row in frame.itertuples(index=False)
        }
    rows: list[dict[str, Any]] = []
    first = next(iter(frames.values()))
    for row in first.itertuples(index=False):
        key = (
            config_key(row.long_config),
            config_key(row.short_config),
        )
        asset_rows = [mapping[key] for mapping in maps.values()]
        scores = [float(item.robust_score) for item in asset_rows]
        rows.append(
            {
                "long_config": row.long_config,
                "short_config": row.short_config,
                "shared_robust_score": finite_shared_score(scores),
                "min_prefit_equity": min(
                    float(item.prefit_equity) for item in asset_rows
                ),
                "min_profitable_windows": min(
                    int(item.profitable_windows) for item in asset_rows
                ),
                "worst_window_mdd_pct": min(
                    float(item.worst_window_mdd_pct)
                    for item in asset_rows
                ),
                **{
                    f"{symbol.lower()}_robust_score": float(
                        maps[symbol][key].robust_score
                    )
                    for symbol in ASSETS
                },
                **{
                    f"{symbol.lower()}_prefit_equity": float(
                        maps[symbol][key].prefit_equity
                    )
                    for symbol in ASSETS
                },
            }
        )
    return pd.DataFrame(rows).sort_values(
        [
            "shared_robust_score",
            "min_prefit_equity",
            "worst_window_mdd_pct",
        ],
        ascending=[False, False, False],
    )


def audit_selection(
    engine: Any,
    label: str,
    long_config: Any,
    short_config: Any,
    book: Any,
    features: Any,
    *,
    prefit_end: int,
) -> dict[str, Any]:
    combined = engine.audit_candidate(
        label,
        long_config,
        short_config,
        book,
        features,
        prefit_end=prefit_end,
        retain_full=True,
    )
    long_only = engine.audit_candidate(
        f"{label}_long_only",
        long_config,
        None,
        book,
        features,
        prefit_end=prefit_end,
        retain_full=False,
    )
    short_only = engine.audit_candidate(
        f"{label}_short_only",
        None,
        short_config,
        book,
        features,
        prefit_end=prefit_end,
        retain_full=False,
    )
    for audit in (combined, long_only, short_only):
        audit["windows"]["researcher_exposed_holdout_flat"] = (
            audit["windows"].pop("researcher_exposed_last_90d_flat")
        )
        checks = audit.pop("historical_profit_check")
        audit["diagnostic_profit_check"] = {
            key.replace("last_90d", "holdout"): value
            for key, value in checks.items()
        }
    return {
        "label": label,
        "long_config": asdict(long_config),
        "short_config": asdict(short_config),
        "combined": combined,
        "long_only": long_only,
        "short_only": short_only,
    }


def phase_rows(
    engine: Any,
    selection: str,
    symbol: str,
    long_config: Any,
    short_config: Any,
    books: dict[int, Any],
    features: dict[int, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for phase in PHASES:
        book = books[phase]
        for variant, long_leg, short_leg in (
            ("combined", long_config, short_config),
            ("long_only", long_config, None),
            ("short_only", None, short_config),
        ):
            metrics = engine.backtest(
                book,
                features[phase],
                long_config=long_leg,
                short_config=short_leg,
                start_index=0,
                terminal_index=book.count,
            ).metrics
            rows.append(
                {
                    "selection": selection,
                    "symbol": symbol,
                    "phase_hours": phase,
                    "variant": variant,
                    **metrics,
                }
            )
    return rows


def top_config_rows(
    frame: pd.DataFrame,
    *,
    symbol: str,
    side: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, row in enumerate(
        frame.sort_values("robust_score", ascending=False)
        .head(limit)
        .itertuples(index=False),
        start=1,
    ):
        rows.append(
            {
                "symbol": symbol,
                "side": side,
                "rank": rank,
                "config_json": config_key(row.config),
                **{
                    key: value
                    for key, value in row._asdict().items()
                    if key != "config"
                },
            }
        )
    return rows


def top_pair_rows(
    frame: pd.DataFrame,
    *,
    selection: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    score_column = (
        "shared_robust_score"
        if "shared_robust_score" in frame.columns
        else "robust_score"
    )
    for rank, row in enumerate(
        frame.sort_values(score_column, ascending=False)
        .head(limit)
        .itertuples(index=False),
        start=1,
    ):
        values = row._asdict()
        rows.append(
            {
                "selection": selection,
                "rank": rank,
                "long_config_json": config_key(values.pop("long_config")),
                "short_config_json": config_key(
                    values.pop("short_config")
                ),
                **values,
            }
        )
    return rows


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: clean_json(item)
            for key, item in value.items()
            if key != "retained"
        }
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    args = parse_args()
    transfer = load_module(
        TRANSFER_PATH,
        TRANSFER_SHA256,
        "btc_eth_ma7_asset_search_transfer",
    )
    engine = transfer.load_engine()
    if args.self_test:
        rng = random.Random(args.seed)
        configs = engine.unique_configs(1, rng, 50)
        assert len(configs) == 50
        assert len({config.key for config in configs}) == 50
        assert HOLDOUT_START == pd.Timestamp("2026-02-01T00:00:00Z")
        print("self-test: PASS")
        return

    books_by_asset: dict[str, dict[int, Any]] = {}
    features_by_asset: dict[str, dict[int, Any]] = {}
    data_quality: dict[str, Any] = {}
    prefit_ends: dict[str, int] = {}
    for symbol, slug in ASSETS.items():
        hourly, funding, quality = transfer.load_and_audit(symbol, slug)
        books = {
            phase: transfer.build_book(
                symbol,
                hourly,
                quality,
                phase_hours=phase,
            )
            for phase in PHASES
        }
        features = {
            phase: engine.build_features(book, hourly, funding)
            for phase, book in books.items()
        }
        prefit_end = int(
            books[0].ts.searchsorted(HOLDOUT_START, side="left")
        )
        if (
            prefit_end <= 365
            or prefit_end >= books[0].count - 90
            or pd.Timestamp(books[0].ts[prefit_end]) != HOLDOUT_START
        ):
            raise RuntimeError(
                f"{symbol}: invalid development/holdout boundary"
            )
        books_by_asset[symbol] = books
        features_by_asset[symbol] = features
        data_quality[symbol] = quality
        prefit_ends[symbol] = prefit_end

    stage1: dict[str, dict[str, pd.DataFrame]] = {}
    stable: dict[str, dict[str, pd.DataFrame]] = {}
    pairs: dict[str, pd.DataFrame] = {}
    selections: dict[str, tuple[Any, Any]] = {}
    shared_pairs = pd.DataFrame()
    if args.audit_only:
        existing_path = ARTIFACT_DIR / (
            "binance_btc_eth_1d_ma7_asset_specific_search_summary_"
            f"{args.run_date}.json"
        )
        existing = json.loads(existing_path.read_text(encoding="utf-8"))
        selections = {
            name: (
                engine.Config(**selection["long_config"]),
                engine.Config(**selection["short_config"]),
            )
            for name, selection in existing["selections"].items()
        }
    else:
        rng = random.Random(args.seed)
        configs = {
            "long": engine.unique_configs(
                1,
                rng,
                args.samples_per_side,
            ),
            "short": engine.unique_configs(
                -1,
                rng,
                args.samples_per_side,
            ),
        }
        for symbol in ASSETS:
            book = books_by_asset[symbol][0]
            features = features_by_asset[symbol][0]
            stage1[symbol] = {}
            stable[symbol] = {}
            for side in ("long", "short"):
                print(f"{symbol} {side} stage1", flush=True)
                frame = engine.stage1_search(
                    configs[side],
                    book,
                    features,
                    end=prefit_ends[symbol],
                )
                stage1[symbol][side] = frame
                shortlist = list(
                    frame.sort_values("score", ascending=False)
                    .head(args.shortlist)["config"]
                )
                stable[symbol][side] = engine.rank_stable(
                    engine.stability_audit(
                        shortlist,
                        book,
                        features,
                        prefit_end=prefit_ends[symbol],
                    ),
                    args.shortlist,
                )
            long_pool = list(
                stable[symbol]["long"]
                .head(args.pair_pool)["config"]
            )
            short_pool = list(
                stable[symbol]["short"]
                .head(args.pair_pool)["config"]
            )
            pairs[symbol] = engine.pair_search(
                long_pool,
                short_pool,
                book,
                features,
                prefit_end=prefit_ends[symbol],
            )
            primary = pairs[symbol].iloc[0]
            selections[f"{symbol}_asset_specific"] = (
                primary["long_config"],
                primary["short_config"],
            )

        shared_stage1 = {
            side: rank_shared_stage1(
                {
                    symbol: stage1[symbol][side]
                    for symbol in ASSETS
                },
                limit=args.shared_audit_pool,
            )
            for side in ("long", "short")
        }
        shared_pools: dict[str, list[Any]] = {}
        for side in ("long", "short"):
            pool, _ = rank_shared_stability(
                engine,
                shared_stage1[side],
                {
                    symbol: books_by_asset[symbol][0]
                    for symbol in ASSETS
                },
                {
                    symbol: features_by_asset[symbol][0]
                    for symbol in ASSETS
                },
                prefit_ends,
                limit=args.pair_pool,
            )
            shared_pools[side] = pool
        shared_pairs = rank_shared_pairs(
            engine,
            shared_pools["long"],
            shared_pools["short"],
            {symbol: books_by_asset[symbol][0] for symbol in ASSETS},
            {
                symbol: features_by_asset[symbol][0]
                for symbol in ASSETS
            },
            prefit_ends,
        )
        shared_primary = shared_pairs.iloc[0]
        selections["BTC_ETH_shared"] = (
            shared_primary["long_config"],
            shared_primary["short_config"],
        )

    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "status": "explore / not promoted / not live-ready",
        "evidence_role": (
            "historical development plus researcher-exposed chronological "
            "holdout; no clean OOS"
        ),
        "contract": {
            "indicator": "fixed SMA7 and ATR7",
            "seed": args.seed,
            "samples_per_side": args.samples_per_side,
            "shortlist_per_side": args.shortlist,
            "pair_pool_per_side": args.pair_pool,
            "development_end_exclusive": HOLDOUT_START.isoformat(),
            "holdout_role": "researcher-exposed; excluded from selection",
            "selection": (
                "asset-specific and shared candidates selected only from "
                "development subwindows, 8bps stress and one-day delay"
            ),
            "costs": {
                "fee_per_fill": engine.FEE,
                "base_slippage_per_fill": engine.BASE_SLIPPAGE,
                "stress_slippage_per_fill": engine.STRESS_SLIPPAGE,
                "funding": (
                    "actual Binance event timestamp/rate while held"
                ),
            },
        },
        "source_engine": {
            "path": str(transfer.ENGINE_PATH.relative_to(ROOT)),
            "sha256": transfer.ENGINE_SHA256,
        },
        "data_quality": data_quality,
        "selections": {},
    }
    frontier_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    phase_output: list[dict[str, Any]] = []
    rolling_output: list[dict[str, Any]] = []
    recent_output: list[dict[str, Any]] = []
    trade_output: list[dict[str, Any]] = []
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    if not args.audit_only:
        for symbol in ASSETS:
            for side in ("long", "short"):
                frontier_rows.extend(
                    top_config_rows(
                        stable[symbol][side],
                        symbol=symbol,
                        side=side,
                        limit=args.shortlist,
                    )
                )
            pair_rows.extend(
                top_pair_rows(
                    pairs[symbol],
                    selection=f"{symbol}_asset_specific",
                    limit=args.shortlist,
                )
            )
        pair_rows.extend(
            top_pair_rows(
                shared_pairs,
                selection="BTC_ETH_shared",
                limit=args.shortlist,
            )
        )

    for selection, (long_config, short_config) in selections.items():
        payload["selections"][selection] = {
            "long_config": asdict(long_config),
            "short_config": asdict(short_config),
            "assets": {},
        }
        for symbol in ASSETS:
            audit = audit_selection(
                engine,
                selection,
                long_config,
                short_config,
                books_by_asset[symbol][0],
                features_by_asset[symbol][0],
                prefit_end=prefit_ends[symbol],
            )
            benchmark = engine.buy_and_hold(
                books_by_asset[symbol][0],
                features_by_asset[symbol][0],
            )
            payload["selections"][selection]["assets"][symbol] = {
                **audit,
                "buy_and_hold": benchmark,
            }
            for variant in ("combined", "long_only", "short_only"):
                variant_audit = audit[variant]
                for window, stresses in variant_audit["windows"].items():
                    for stress, metrics in stresses.items():
                        metric_rows.append(
                            {
                                "selection": selection,
                                "symbol": symbol,
                                "variant": variant,
                                "window": window,
                                "stress": stress,
                                **metrics,
                            }
                        )
            phase_output.extend(
                phase_rows(
                    engine,
                    selection,
                    symbol,
                    long_config,
                    short_config,
                    books_by_asset[symbol],
                    features_by_asset[symbol],
                )
            )
            rolling_output.extend(
                {
                    "selection": selection,
                    **row,
                }
                for row in transfer.rolling_rows(
                    engine,
                    symbol,
                    books_by_asset[symbol][0],
                    features_by_asset[symbol][0],
                    long_config,
                    short_config,
                )
            )
            combined_result = audit["combined"]["retained"]["full"]
            for row in engine.recent_slices(combined_result):
                recent_output.append(
                    {
                        "selection": selection,
                        "symbol": symbol,
                        **row,
                    }
                )
            trade_output.extend(
                {
                    "selection": selection,
                    "symbol": symbol,
                    **trade,
                }
                for trade in combined_result.trades
            )
            pd.DataFrame(combined_result.path).to_csv(
                ARTIFACT_DIR
                / (
                    "binance_btc_eth_1d_ma7_search_"
                    f"{selection.lower()}_{symbol.lower()}_path_"
                    f"{args.run_date}.csv"
                ),
                index=False,
            )

    stem = "binance_btc_eth_1d_ma7_asset_specific_search"
    (ARTIFACT_DIR / f"{stem}_summary_{args.run_date}.json").write_text(
        json.dumps(
            clean_json(payload),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    if not args.audit_only:
        pd.DataFrame(frontier_rows).to_csv(
            ARTIFACT_DIR / f"{stem}_frontier_{args.run_date}.csv",
            index=False,
        )
        pd.DataFrame(pair_rows).to_csv(
            ARTIFACT_DIR / f"{stem}_pairs_{args.run_date}.csv",
            index=False,
        )
    pd.DataFrame(metric_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(phase_output).to_csv(
        ARTIFACT_DIR / f"{stem}_phase_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling_output).to_csv(
        ARTIFACT_DIR / f"{stem}_rolling_180d_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(recent_output).to_csv(
        ARTIFACT_DIR / f"{stem}_recent_{args.run_date}.csv",
        index=False,
    )
    pd.DataFrame(trade_output).to_csv(
        ARTIFACT_DIR / f"{stem}_trades_{args.run_date}.csv",
        index=False,
    )
    print(
        json.dumps(
            clean_json(payload["selections"]),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
