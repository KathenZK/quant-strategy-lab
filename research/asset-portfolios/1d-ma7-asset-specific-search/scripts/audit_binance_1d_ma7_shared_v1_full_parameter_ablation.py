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

FIELD_VALUES: dict[str, tuple[Any, ...]] = {
    "entry_mode": (
        "regime",
        "reclaim",
        "pullback_reclaim",
        "breakout",
        "open_regime",
    ),
    "slope_lookback": (1, 2, 3, 5, 7),
    "slope_min_atr": (0.0, 0.02, 0.05, 0.10, 0.20),
    "confirm_days": (1, 2, 3),
    "entry_buffer_atr": (0.0, 0.10, 0.25, 0.50),
    "pullback_lookback": (2, 3, 5, 7, 10),
    "pullback_touch_atr": (-0.50, -0.25, 0.0, 0.10, 0.25),
    "breakout_lookback": (2, 3, 5, 7, 10, 14),
    "exit_confirm_days": (1, 2, 3),
    "exit_buffer_atr": (0.0, 0.10, 0.25, 0.50, 0.75, 1.0),
    "slope_exit_lookback": (0, 1, 2, 3, 5),
    "hard_stop_atr": (0.0, 1.5, 2.0, 3.0, 4.0, 5.0),
    "trail_atr": (0.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0),
    "max_hold_days": (0, 10, 20, 30, 60, 90),
    "cooldown_days": (0, 1, 2, 3, 5),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Development-only OAT ablation of shared BTC/ETH MA7 V1."
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


def variants(config: Any, *, leg: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen = {config.key}
    for field, values in FIELD_VALUES.items():
        for value in values:
            if field == "entry_mode" and leg == "long" and value == "open_regime":
                continue
            candidate = replace(config, **{field: value})
            if candidate.key in seen:
                continue
            seen.add(candidate.key)
            output.append(
                {
                    "variant_id": f"{leg}__{field}__{str(value).replace('.', 'p')}",
                    "leg": leg,
                    "field": field,
                    "base_value": getattr(config, field),
                    "candidate_value": value,
                    "config": candidate,
                }
            )
    return output


def trade_signature(result: Any) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            row["entry_ts"],
            row["exit_ts"],
            row["side"],
            row["exit_reason"],
            round(float(row["entry_price"]), 12),
            round(float(row["exit_price"]), 12),
        )
        for row in result.trades
    )


def compact_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        key: metrics[key]
        for key in (
            "equity_multiple",
            "net_return_pct",
            "max_drawdown_pct",
            "sharpe",
            "closed_trades",
            "long_trades",
            "short_trades",
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


def shared_score(asset_metrics: dict[str, dict[str, Any]]) -> float:
    equities = [float(row["equity_multiple"]) for row in asset_metrics.values()]
    drawdowns = [float(row["max_drawdown_pct"]) for row in asset_metrics.values()]
    if any(equity <= 0.0 for equity in equities):
        return -math.inf
    dd_penalty = sum(max(0.0, abs(drawdown) / 100.0 - 0.20) for drawdown in drawdowns)
    return min(math.log(equity) for equity in equities) - 4.0 * dd_penalty


def main() -> None:
    args = parse_args()
    baseline = load_module(BASELINE_PATH, "binance_ma7_v1_ablation_baseline")
    transfer = baseline.load_module(
        baseline.TRANSFER_PATH,
        baseline.TRANSFER_SHA256,
        "binance_ma7_v1_ablation_transfer",
    )
    engine = transfer.load_engine()
    long_config, short_config = baseline.v1_configs(engine)
    all_variants = [
        *variants(long_config, leg="long"),
        *variants(short_config, leg="short"),
    ]
    if args.self_test:
        keys = [row["config"].key for row in all_variants]
        assert len(keys) == len(set(keys))
        assert all(row["config"].key not in {long_config.key, short_config.key} for row in all_variants)
        assert all("audit" not in row["variant_id"] for row in all_variants)
        print(f"self-test: PASS variants={len(all_variants)}")
        return

    manifest = json.loads(baseline.P0_MANIFEST.read_text(encoding="utf-8"))
    contexts: dict[str, tuple[Any, Any, int, int]] = {}
    baseline_results: dict[str, Any] = {}
    baseline_signatures: dict[str, tuple[tuple[Any, ...], ...]] = {}
    for symbol, slug in baseline.ASSETS.items():
        hourly, funding, quality = baseline.load_snapshot(symbol, slug, manifest)
        book = transfer.build_book(symbol, hourly, quality, phase_hours=0)
        features = engine.build_features(book, hourly, funding)
        start = baseline.boundary(book, baseline.COMMON_START)
        end = baseline.boundary(book, baseline.DEVELOPMENT_END)
        result = baseline.run_window(
            engine,
            book,
            features,
            long_config,
            short_config,
            start=start,
            end=end,
            slippage=engine.BASE_SLIPPAGE,
            signal_lag=0,
            retain=False,
        )
        contexts[symbol] = (book, features, start, end)
        baseline_results[symbol] = result
        baseline_signatures[symbol] = trade_signature(result)

    rows: list[dict[str, Any]] = []
    payload_variants: list[dict[str, Any]] = []
    for index, item in enumerate(all_variants, start=1):
        candidate_long = item["config"] if item["leg"] == "long" else long_config
        candidate_short = item["config"] if item["leg"] == "short" else short_config
        asset_metrics: dict[str, dict[str, Any]] = {}
        asset_details: dict[str, Any] = {}
        for symbol, (book, features, start, end) in contexts.items():
            result = baseline.run_window(
                engine,
                book,
                features,
                candidate_long,
                candidate_short,
                start=start,
                end=end,
                slippage=engine.BASE_SLIPPAGE,
                signal_lag=0,
                retain=False,
            )
            metrics = compact_metrics(result.metrics)
            signature = trade_signature(result)
            asset_metrics[symbol] = metrics
            asset_details[symbol] = {
                "metrics": metrics,
                "path_equal_to_v1": signature == baseline_signatures[symbol],
                "exit_reason_counts": dict(
                    sorted(Counter(row["exit_reason"] for row in result.trades).items())
                ),
                "trade_count_delta": (
                    int(metrics["closed_trades"])
                    - len(baseline_signatures[symbol])
                ),
            }
            rows.append(
                {
                    "variant_id": item["variant_id"],
                    "leg": item["leg"],
                    "field": item["field"],
                    "base_value": item["base_value"],
                    "candidate_value": item["candidate_value"],
                    "symbol": symbol,
                    "path_equal_to_v1": signature == baseline_signatures[symbol],
                    **metrics,
                }
            )
        variant_score = shared_score(asset_metrics)
        payload_variants.append(
            {
                "variant_id": item["variant_id"],
                "leg": item["leg"],
                "field": item["field"],
                "base_value": item["base_value"],
                "candidate_value": item["candidate_value"],
                "candidate_config": asdict(item["config"]),
                "path_equal_all_assets": all(
                    detail["path_equal_to_v1"] for detail in asset_details.values()
                ),
                "shared_score": variant_score,
                "min_equity_multiple": min(
                    float(row["equity_multiple"]) for row in asset_metrics.values()
                ),
                "worst_mdd_pct": min(
                    float(row["max_drawdown_pct"]) for row in asset_metrics.values()
                ),
                "both_assets_mdd_within_20pct": all(
                    float(row["max_drawdown_pct"]) >= -20.0
                    for row in asset_metrics.values()
                ),
                "both_assets_equity_gte_20": all(
                    float(row["equity_multiple"]) >= 20.0
                    for row in asset_metrics.values()
                ),
                "assets": asset_details,
            }
        )
        if index % 20 == 0:
            print(f"ablation {index}/{len(all_variants)}", flush=True)

    ranked = sorted(
        payload_variants,
        key=lambda row: (
            float(row["shared_score"]),
            float(row["min_equity_multiple"]),
            float(row["worst_mdd_pct"]),
        ),
        reverse=True,
    )
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "campaign": "P2-B V1 full-parameter OAT ablation",
        "status": "explore / not promoted / not live-ready",
        "evidence_role": "development-only; researcher-exposed audit not read",
        "development": {
            "start": baseline.COMMON_START.isoformat(),
            "end_exclusive": baseline.DEVELOPMENT_END.isoformat(),
        },
        "baseline": {
            symbol: compact_metrics(result.metrics)
            for symbol, result in baseline_results.items()
        },
        "variant_count": len(payload_variants),
        "path_equal_variant_count": sum(
            row["path_equal_all_assets"] for row in payload_variants
        ),
        "hard_target_hit_count": sum(
            row["both_assets_equity_gte_20"]
            and row["both_assets_mdd_within_20pct"]
            for row in payload_variants
        ),
        "ranking_note": (
            "diagnostic only; score uses development min equity and penalties "
            "for MDD beyond 20%; no audit/OOS result is consumed"
        ),
        "ranked_variants": ranked,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_ma7_shared_v1_full_parameter_ablation_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(clean_json(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame(rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics.csv", index=False
    )
    pd.DataFrame(
        [
            {
                key: value
                for key, value in row.items()
                if key not in {"candidate_config", "assets"}
            }
            for row in ranked
        ]
    ).to_csv(ARTIFACT_DIR / f"{stem}_ranking.csv", index=False)
    print(
        json.dumps(
            clean_json(
                {
                    "variant_count": payload["variant_count"],
                    "path_equal_variant_count": payload[
                        "path_equal_variant_count"
                    ],
                    "hard_target_hit_count": payload["hard_target_hit_count"],
                    "top10": [
                        {
                            key: row[key]
                            for key in (
                                "variant_id",
                                "shared_score",
                                "min_equity_multiple",
                                "worst_mdd_pct",
                                "path_equal_all_assets",
                            )
                        }
                        for row in ranked[:10]
                    ],
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

