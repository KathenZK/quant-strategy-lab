from __future__ import annotations

import argparse
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
FRONTIER_PATH = (
    ARTIFACT_DIR
    / "binance_1d_ma7_p2f_frontier_tail_states_2026-08-12_manifest.csv"
)
MDD_EVENTS_PATH = (
    ARTIFACT_DIR
    / "binance_1d_ma7_p2f_frontier_tail_states_2026-08-12_events.csv"
)
FEATURES = ("QV20", "TC20", "RVOL7", "FUND24", "FUND7Z", "CROWD7Z")
STRATA = ("growth", "risk", "balanced")
EARLY_HOURS = 48
EARLY_TAIL_THRESHOLD = -0.08


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P2-G entry-information attribution on frozen frontier."
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


def trailing_percentile(
    values: np.ndarray,
    index: int,
    *,
    window: int,
    min_count: int = 30,
) -> float:
    left = max(0, index - window + 1)
    current = float(values[index])
    history = values[left : index + 1]
    history = history[np.isfinite(history)]
    if not np.isfinite(current) or len(history) < min_count:
        return math.nan
    return float(np.mean(history <= current))


def sum_before(
    event_ns: np.ndarray,
    cumulative: np.ndarray,
    *,
    left: pd.Timestamp,
    right: pd.Timestamp,
) -> float:
    left_ns = left.value
    right_ns = right.value
    left_index = int(np.searchsorted(event_ns, left_ns, side="left"))
    right_index = int(np.searchsorted(event_ns, right_ns, side="left"))
    return float(cumulative[right_index] - cumulative[left_index])


def funding_features(
    entry_ts: pd.Timestamp,
    *,
    event_ns: np.ndarray,
    cumulative: np.ndarray,
) -> dict[str, float]:
    if len(event_ns) == 0:
        return {"FUND24": math.nan, "FUND7Z": math.nan}
    first_event = pd.Timestamp(int(event_ns[0]), tz="UTC")
    fund24 = math.nan
    if entry_ts - pd.Timedelta(hours=24) >= first_event:
        fund24 = sum_before(
            event_ns,
            cumulative,
            left=entry_ts - pd.Timedelta(hours=24),
            right=entry_ts,
        )
    fund7z = math.nan
    if entry_ts - pd.Timedelta(days=187) >= first_event:
        current = sum_before(
            event_ns,
            cumulative,
            left=entry_ts - pd.Timedelta(days=7),
            right=entry_ts,
        )
        history = np.asarray(
            [
                sum_before(
                    event_ns,
                    cumulative,
                    left=entry_ts - pd.Timedelta(days=offset + 7),
                    right=entry_ts - pd.Timedelta(days=offset),
                )
                for offset in range(1, 181)
            ],
            dtype=float,
        )
        standard_deviation = float(history.std(ddof=1))
        if standard_deviation > 0.0:
            fund7z = float((current - history.mean()) / standard_deviation)
    return {"FUND24": fund24, "FUND7Z": fund7z}


def daily_feature_context(daily: pd.DataFrame) -> dict[str, Any]:
    work = daily.copy()
    work["ts"] = pd.to_datetime(work["ts"], utc=True)
    work = work.sort_values("ts").drop_duplicates("ts", keep="last")
    quote_volume = work["quote_volume"].astype(float)
    trade_count = work["trade_count"].astype(float)
    log_return = np.log(work["close"].astype(float)).diff()
    rvol7 = log_return.rolling(7, min_periods=7).std(ddof=1).to_numpy()
    return {
        "frame": work.set_index("ts"),
        "qv20": (
            quote_volume
            / quote_volume.rolling(20, min_periods=20).median()
        ).to_numpy(),
        "tc20": (
            trade_count
            / trade_count.rolling(20, min_periods=20).median()
        ).to_numpy(),
        "rvol7": rvol7,
        "timestamps": pd.DatetimeIndex(work["ts"]),
    }


def entry_features(
    entry_ts: pd.Timestamp,
    *,
    side: int,
    daily_context: dict[str, Any],
    event_ns: np.ndarray,
    cumulative: np.ndarray,
) -> dict[str, float]:
    known_day = entry_ts.floor("D") - pd.Timedelta(days=1)
    timestamps = daily_context["timestamps"]
    known_index = int(timestamps.searchsorted(known_day, side="left"))
    if known_index >= len(timestamps) or timestamps[known_index] != known_day:
        raise RuntimeError(f"missing last-complete daily row {known_day}")
    funding = funding_features(
        entry_ts,
        event_ns=event_ns,
        cumulative=cumulative,
    )
    fund7z = funding["FUND7Z"]
    return {
        "QV20": float(daily_context["qv20"][known_index]),
        "TC20": float(daily_context["tc20"][known_index]),
        "RVOL7": trailing_percentile(
            daily_context["rvol7"], known_index, window=365
        ),
        "FUND24": funding["FUND24"],
        "FUND7Z": fund7z,
        "CROWD7Z": side * fund7z,
    }


def early_outcome(
    trade: dict[str, Any],
    *,
    hourly: pd.DataFrame,
    side: int,
) -> dict[str, float | bool]:
    entry_ts = pd.Timestamp(trade["entry_ts"])
    exit_ts = pd.Timestamp(trade["exit_ts"])
    entry_price = float(trade["entry_price"])
    exit_price = float(trade["exit_price"])
    horizon = entry_ts + pd.Timedelta(hours=EARLY_HOURS)
    held_end = min(horizon, exit_ts)
    held = hourly.loc[
        hourly["ts"].ge(entry_ts) & hourly["ts"].lt(held_end)
    ]
    adverse = 0.0
    if not held.empty:
        if side > 0:
            adverse = float(held["low"].min() / entry_price - 1.0)
        else:
            adverse = float(1.0 - held["high"].max() / entry_price)
    exited_early = exit_ts <= horizon
    if exited_early:
        exit_return = side * (exit_price - entry_price) / entry_price
        adverse = min(adverse, exit_return)
        horizon_return = exit_return
        outcome_ts = exit_ts
    else:
        exact = hourly.loc[hourly["ts"].eq(horizon)]
        if exact.empty:
            prior = hourly.loc[hourly["ts"].lt(horizon)]
            if prior.empty:
                raise RuntimeError(f"no 48h mark for entry {entry_ts}")
            mark_price = float(prior.iloc[-1]["close"])
        else:
            mark_price = float(exact.iloc[0]["open"])
        horizon_return = side * (mark_price - entry_price) / entry_price
        outcome_ts = horizon
    return {
        "early_adverse_return": adverse,
        "early_tail": adverse <= EARLY_TAIL_THRESHOLD,
        "return_48h_or_exit": horizon_return,
        "early_outcome_ts": outcome_ts.isoformat(),
        "exited_within_48h": exited_early,
    }


def rank_effect_auc(
    frame: pd.DataFrame,
    feature: str,
) -> dict[str, Any]:
    valid = frame[[feature, "early_tail"]].dropna()
    tail = valid["early_tail"].astype(bool).to_numpy()
    values = valid[feature].astype(float)
    n_tail = int(tail.sum())
    n_control = int((~tail).sum())
    if n_tail == 0 or n_control == 0:
        effect = auc = math.nan
    else:
        ranks = values.rank(method="average").to_numpy()
        u_statistic = float(ranks[tail].sum() - n_tail * (n_tail + 1) / 2)
        auc = u_statistic / (n_tail * n_control)
        effect = 2.0 * auc - 1.0
    quintiles: list[dict[str, Any]] = []
    if len(valid) >= 5:
        percentile = values.rank(method="average", pct=True).to_numpy()
        bins = np.minimum((percentile * 5).astype(int), 4)
        for quintile in range(5):
            selected = tail[bins == quintile]
            quintiles.append(
                {
                    "quintile": quintile + 1,
                    "count": len(selected),
                    "tail_rate": (
                        float(selected.mean()) if len(selected) else math.nan
                    ),
                }
            )
    return {
        "rows": len(frame),
        "valid": len(valid),
        "missing": len(frame) - len(valid),
        "tail_count": n_tail,
        "tail_rate": float(tail.mean()) if len(tail) else math.nan,
        "rank_biserial_effect": effect,
        "auc": auc,
        "quintiles": quintiles,
    }


def analysis_frames(entries: pd.DataFrame) -> dict[str, pd.DataFrame]:
    expanded = entries.assign(stratum=entries["strata"].str.split(",")).explode(
        "stratum"
    )
    expanded = expanded.loc[expanded["stratum"].isin(STRATA)].copy()
    unique = (
        expanded.sort_values(["pair_rank", "trade_index"])
        .drop_duplicates(["symbol", "side", "entry_ts", "stratum"])
        .copy()
    )
    return {"pair_weighted": expanded, "unique_entry": unique}


def metric_rows(entries: pd.DataFrame) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for weighting, frame in analysis_frames(entries).items():
        group_specs: list[tuple[str, list[str]]] = [
            ("asset_overall", ["symbol"]),
            ("asset_stratum", ["symbol", "stratum"]),
            ("asset_side_stratum", ["symbol", "side", "stratum"]),
        ]
        for level, keys in group_specs:
            for group_key, group in frame.groupby(keys):
                values = (
                    group_key if isinstance(group_key, tuple) else (group_key,)
                )
                dimensions = dict(zip(keys, values, strict=True))
                for feature in FEATURES:
                    output.append(
                        {
                            "weighting": weighting,
                            "level": level,
                            "feature": feature,
                            "symbol": dimensions.get("symbol", "all"),
                            "side": dimensions.get("side", "all"),
                            "stratum": dimensions.get("stratum", "all"),
                            **rank_effect_auc(group, feature),
                        }
                    )
    return output


def sign(value: float) -> int:
    if not np.isfinite(value) or value == 0.0:
        return 0
    return 1 if value > 0.0 else -1


def loyo_consistency(
    frame: pd.DataFrame,
    *,
    symbol: str,
    feature: str,
    expected_sign: int,
) -> dict[str, Any]:
    asset = frame.loc[frame["symbol"].eq(symbol)].copy()
    years = sorted(asset["entry_year"].unique())
    effects: list[dict[str, Any]] = []
    for year in years:
        train = asset.loc[asset["entry_year"].ne(year)]
        effect = float(rank_effect_auc(train, feature)["rank_biserial_effect"])
        effects.append(
            {
                "left_out_year": int(year),
                "effect": effect,
                "consistent": sign(effect) == expected_sign,
            }
        )
    usable = [row for row in effects if np.isfinite(row["effect"])]
    return {
        "folds": effects,
        "usable_folds": len(usable),
        "consistency": (
            float(np.mean([row["consistent"] for row in usable]))
            if usable
            else math.nan
        ),
    }


def decide_features(
    entries: pd.DataFrame,
    metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    metric_frame = pd.DataFrame(metrics)
    frames = analysis_frames(entries)
    decisions: dict[str, Any] = {}
    for feature in FEATURES:
        overall = metric_frame.loc[
            metric_frame["feature"].eq(feature)
            & metric_frame["level"].eq("asset_overall")
        ]
        effects: dict[str, dict[str, float]] = {}
        aucs: dict[str, dict[str, float]] = {}
        valid_unique: dict[str, int] = {}
        direction_ok = True
        asset_signs: list[int] = []
        weakest_auc_edge = math.inf
        for symbol in ("BTCUSDT", "ETHUSDT"):
            effects[symbol] = {}
            aucs[symbol] = {}
            for weighting in frames:
                row = overall.loc[
                    overall["symbol"].eq(symbol)
                    & overall["weighting"].eq(weighting)
                ].iloc[0]
                effects[symbol][weighting] = float(
                    row["rank_biserial_effect"]
                )
                aucs[symbol][weighting] = float(row["auc"])
                weakest_auc_edge = min(
                    weakest_auc_edge, abs(float(row["auc"]) - 0.5)
                )
                if weighting == "unique_entry":
                    valid_unique[symbol] = int(row["valid"])
            pair_sign = sign(effects[symbol]["pair_weighted"])
            unique_sign = sign(effects[symbol]["unique_entry"])
            direction_ok = direction_ok and pair_sign != 0
            direction_ok = direction_ok and pair_sign == unique_sign
            asset_signs.append(pair_sign)
        cross_asset_direction = (
            direction_ok and len(set(asset_signs)) == 1
        )
        expected_sign = asset_signs[0] if cross_asset_direction else 0

        stratum_pass_counts: dict[str, int] = {}
        stratum_detail: dict[str, Any] = {}
        for symbol in ("BTCUSDT", "ETHUSDT"):
            count = 0
            stratum_detail[symbol] = {}
            for stratum in STRATA:
                rows = metric_frame.loc[
                    metric_frame["feature"].eq(feature)
                    & metric_frame["level"].eq("asset_stratum")
                    & metric_frame["symbol"].eq(symbol)
                    & metric_frame["stratum"].eq(stratum)
                ]
                by_weight = {
                    row["weighting"]: float(row["rank_biserial_effect"])
                    for _, row in rows.iterrows()
                }
                conservative = min(
                    (
                        abs(by_weight.get("pair_weighted", math.nan)),
                        abs(by_weight.get("unique_entry", math.nan)),
                    )
                )
                passed = bool(
                    expected_sign != 0
                    and all(
                        sign(value) == expected_sign
                        for value in by_weight.values()
                    )
                    and np.isfinite(conservative)
                    and conservative >= 0.15
                )
                count += int(passed)
                stratum_detail[symbol][stratum] = {
                    "effects": by_weight,
                    "conservative_abs_effect": conservative,
                    "pass": passed,
                }
            stratum_pass_counts[symbol] = count

        loyo: dict[str, Any] = {}
        weakest_loyo = math.inf
        for weighting, frame in frames.items():
            loyo[weighting] = {}
            for symbol in ("BTCUSDT", "ETHUSDT"):
                row = loyo_consistency(
                    frame,
                    symbol=symbol,
                    feature=feature,
                    expected_sign=expected_sign,
                )
                loyo[weighting][symbol] = row
                weakest_loyo = min(weakest_loyo, float(row["consistency"]))
        valid_count_gate = all(value >= 30 for value in valid_unique.values())
        stratum_gate = all(value >= 2 for value in stratum_pass_counts.values())
        auc_gate = weakest_auc_edge >= 0.08
        loyo_gate = weakest_loyo >= 0.70
        passed = all(
            (
                cross_asset_direction,
                valid_count_gate,
                stratum_gate,
                auc_gate,
                loyo_gate,
            )
        )
        feature_values = entries[feature]
        decisions[feature] = {
            "pass": passed,
            "expected_effect_sign": expected_sign,
            "cross_asset_and_weighting_direction_gate": cross_asset_direction,
            "valid_unique_entries": valid_unique,
            "valid_count_gate": valid_count_gate,
            "stratum_pass_counts": stratum_pass_counts,
            "stratum_effect_gate": stratum_gate,
            "stratum_detail": stratum_detail,
            "weakest_auc_edge": weakest_auc_edge,
            "auc_gate": auc_gate,
            "weakest_loyo_consistency": weakest_loyo,
            "loyo_gate": loyo_gate,
            "overall_effects": effects,
            "overall_aucs": aucs,
            "missing_rate": float(feature_values.isna().mean()),
            "loyo": loyo,
        }
    passed_names = [name for name, row in decisions.items() if row["pass"]]
    if "QV20" in passed_names and "TC20" in passed_names:
        weaker = min(
            ("QV20", "TC20"),
            key=lambda name: decisions[name]["weakest_auc_edge"],
        )
        passed_names.remove(weaker)
        decisions[weaker]["pass"] = False
        decisions[weaker]["deduplicated_as_correlated_weaker"] = True
    passed_names.sort(
        key=lambda name: (
            -decisions[name]["missing_rate"],
            decisions[name]["weakest_auc_edge"],
        ),
        reverse=True,
    )
    return {
        "features": decisions,
        "selected_feature": passed_names[0] if passed_names else None,
        "passing_features_after_dedup": passed_names,
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
        frame = pd.DataFrame(
            {"x": [1.0, 2.0, 3.0, 4.0], "early_tail": [0, 0, 1, 1]}
        )
        result = rank_effect_auc(frame, "x")
        assert result["rank_biserial_effect"] == 1.0
        assert result["auc"] == 1.0
        print("self-test: PASS")
        return

    baseline = load_module(BASELINE_PATH, "binance_ma7_p2g_baseline")
    transfer = baseline.load_module(
        baseline.TRANSFER_PATH,
        baseline.TRANSFER_SHA256,
        "binance_ma7_p2g_transfer",
    )
    engine = transfer.load_engine()
    manifest = json.loads(baseline.P0_MANIFEST.read_text(encoding="utf-8"))
    contexts: dict[str, dict[str, Any]] = {}
    for symbol, slug in baseline.ASSETS.items():
        hourly, _, quality = baseline.load_snapshot(symbol, slug, manifest)
        hourly["ts"] = pd.to_datetime(hourly["ts"], utc=True)
        daily = pd.read_parquet(baseline.P0_DIR / f"{slug}_perp_1d.parquet")
        funding = pd.read_parquet(
            baseline.P0_DIR / f"{slug}_perp_funding_mark.parquet"
        )
        funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
        funding = funding.sort_values("ts")
        book = transfer.build_book(symbol, hourly, quality, phase_hours=0)
        features = engine.build_features(
            book, hourly, funding[["ts", "funding_rate"]]
        )
        rates = funding["funding_rate"].astype(float).to_numpy()
        contexts[symbol] = {
            "book": book,
            "features": features,
            "hourly": hourly,
            "daily": daily_feature_context(daily),
            "event_ns": (
                pd.DatetimeIndex(funding["ts"])
                .to_numpy(dtype="datetime64[ns]")
                .astype(np.int64)
            ),
            "funding_cumulative": np.concatenate(([0.0], np.cumsum(rates))),
            "start": baseline.boundary(book, baseline.COMMON_START),
            "end": baseline.boundary(book, baseline.DEVELOPMENT_END),
        }

    frontier = pd.read_csv(FRONTIER_PATH)
    mdd_events = pd.read_csv(MDD_EVENTS_PATH)
    mdd_keys = {
        (int(row.pair_rank), str(row.symbol), int(row.trade_index))
        for row in mdd_events.itertuples(index=False)
    }
    feature_cache: dict[tuple[str, int, str], dict[str, float]] = {}
    entries: list[dict[str, Any]] = []
    for pair_offset, pair in frontier.iterrows():
        long_config = engine.Config(**json.loads(pair["long_config_json"]))
        short_config = engine.Config(**json.loads(pair["short_config_json"]))
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
            for trade_index, trade in enumerate(result.trades, start=1):
                side = 1 if trade["side"] == "long" else -1
                entry_ts = pd.Timestamp(trade["entry_ts"])
                cache_key = (symbol, side, entry_ts.isoformat())
                if cache_key not in feature_cache:
                    feature_cache[cache_key] = entry_features(
                        entry_ts,
                        side=side,
                        daily_context=context["daily"],
                        event_ns=context["event_ns"],
                        cumulative=context["funding_cumulative"],
                    )
                row = {
                    "pair_rank": int(pair["rank"]),
                    "strata": str(pair["strata"]),
                    "symbol": symbol,
                    "side": trade["side"],
                    "trade_index": trade_index,
                    "entry_ts": entry_ts.isoformat(),
                    "entry_year": entry_ts.year,
                    "exit_ts": trade["exit_ts"],
                    "entry_price": float(trade["entry_price"]),
                    "exit_price": float(trade["exit_price"]),
                    "exit_reason": trade["exit_reason"],
                    "final_net_return": float(trade["net_return"]),
                    "is_account_mdd_trade": (
                        int(pair["rank"]), symbol, trade_index
                    )
                    in mdd_keys,
                    **feature_cache[cache_key],
                    **early_outcome(
                        trade,
                        hourly=context["hourly"],
                        side=side,
                    ),
                }
                entries.append(row)
        if (pair_offset + 1) % 25 == 0 or pair_offset + 1 == len(frontier):
            print(
                f"entry-information: {pair_offset + 1}/{len(frontier)} pairs",
                flush=True,
            )
    entry_frame = pd.DataFrame(entries)
    metrics = metric_rows(entry_frame)
    decision = decide_features(entry_frame, metrics)
    frames = analysis_frames(entry_frame)
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "campaign": "P2-G entry-information attribution",
        "status": "explore / not promoted / not live-ready",
        "evidence_role": "development-only; audit and prospective not read",
        "frontier_pairs": len(frontier),
        "pair_weighted_entries": len(frames["pair_weighted"]),
        "unique_entry_rows": len(frames["unique_entry"]),
        "raw_trade_rows": len(entry_frame),
        "early_tail_threshold": EARLY_TAIL_THRESHOLD,
        "early_horizon_hours": EARLY_HOURS,
        "decision": decision,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_ma7_p2g_entry_information_{args.run_date}"
    entry_frame.to_csv(ARTIFACT_DIR / f"{stem}_entries.csv", index=False)
    pd.DataFrame(
        [
            {key: value for key, value in row.items() if key != "quintiles"}
            for row in metrics
        ]
    ).to_csv(ARTIFACT_DIR / f"{stem}_metrics.csv", index=False)
    (ARTIFACT_DIR / f"{stem}_metrics.json").write_text(
        json.dumps(clean_json(metrics), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(clean_json(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(clean_json(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
