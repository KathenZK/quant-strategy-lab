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
ENTRY_PATH = (
    ARTIFACT_DIR
    / "binance_1d_ma7_p2g_entry_information_2026-08-12_entries.csv"
)
ARMS = ("H1_POSITIVE_CLOSE", "H2_POSITIVE_CLOSE", "PDX_PRIOR_DAY_EXTREME")
STRATA = ("growth", "risk", "balanced")
EXPIRY_HOURS = 24
TAIL_THRESHOLD = -0.08


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P2-H finite hourly entry-confirmation attribution."
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


def first_tail_hit(
    row: pd.Series,
    *,
    hourly: pd.DataFrame,
    side: int,
) -> pd.Timestamp | None:
    entry_ts = pd.Timestamp(row["entry_ts"])
    exit_ts = pd.Timestamp(row["exit_ts"])
    horizon = entry_ts + pd.Timedelta(hours=48)
    end = min(exit_ts, horizon)
    entry_price = float(row["entry_price"])
    held = hourly.loc[
        hourly["ts"].ge(entry_ts) & hourly["ts"].lt(end)
    ]
    for bar in held.itertuples(index=False):
        adverse = (
            float(bar.low) / entry_price - 1.0
            if side > 0
            else 1.0 - float(bar.high) / entry_price
        )
        if adverse <= TAIL_THRESHOLD:
            return pd.Timestamp(bar.ts)
    if exit_ts <= horizon:
        exit_return = side * (
            float(row["exit_price"]) - entry_price
        ) / entry_price
        if exit_return <= TAIL_THRESHOLD:
            return exit_ts
    return None


def confirmation_candidates(
    row: pd.Series,
    *,
    hourly: pd.DataFrame,
    daily: pd.DataFrame,
    side: int,
) -> dict[str, dict[str, Any]]:
    entry_ts = pd.Timestamp(row["entry_ts"])
    exit_ts = pd.Timestamp(row["exit_ts"])
    expiry = entry_ts + pd.Timedelta(hours=EXPIRY_HOURS)
    entry_price = float(row["entry_price"])
    known_day = entry_ts.floor("D") - pd.Timedelta(days=1)
    known = daily.loc[daily["ts"].eq(known_day)]
    if len(known) != 1:
        raise RuntimeError(f"missing prior day {known_day}")
    prior_high = float(known.iloc[0]["high"])
    prior_low = float(known.iloc[0]["low"])
    bars = hourly.loc[
        hourly["ts"].ge(entry_ts)
        & hourly["ts"].lt(expiry)
        & hourly["ts"].lt(exit_ts)
    ]
    trigger_close: dict[str, pd.Timestamp | None] = {arm: None for arm in ARMS}
    positive_streak = 0
    for bar in bars.itertuples(index=False):
        close_ts = pd.Timestamp(bar.ts) + pd.Timedelta(hours=1)
        fill_ts = close_ts
        if fill_ts >= expiry or fill_ts >= exit_ts:
            continue
        close_price = float(bar.close)
        positive = side * (close_price - entry_price) > 0.0
        positive_streak = positive_streak + 1 if positive else 0
        if positive and trigger_close["H1_POSITIVE_CLOSE"] is None:
            trigger_close["H1_POSITIVE_CLOSE"] = close_ts
        if positive_streak >= 2 and trigger_close["H2_POSITIVE_CLOSE"] is None:
            trigger_close["H2_POSITIVE_CLOSE"] = close_ts
        extreme = close_price > prior_high if side > 0 else close_price < prior_low
        if extreme and trigger_close["PDX_PRIOR_DAY_EXTREME"] is None:
            trigger_close["PDX_PRIOR_DAY_EXTREME"] = close_ts
    output: dict[str, dict[str, Any]] = {}
    for arm, close_ts in trigger_close.items():
        if close_ts is None:
            output[arm] = {
                "confirm_close_ts": None,
                "candidate_fill_ts": None,
                "candidate_fill_price": math.nan,
                "candidate_valid": False,
                "delay_hours": math.nan,
                "directional_slippage": math.nan,
                "candidate_to_original_exit_gross_return": math.nan,
            }
            continue
        fill = hourly.loc[hourly["ts"].eq(close_ts)]
        if len(fill) != 1:
            raise RuntimeError(f"missing candidate fill bar {close_ts}")
        fill_price = float(fill.iloc[0]["open"])
        output[arm] = {
            "confirm_close_ts": close_ts.isoformat(),
            "candidate_fill_ts": close_ts.isoformat(),
            "candidate_fill_price": fill_price,
            "candidate_valid": True,
            "delay_hours": (close_ts - entry_ts).total_seconds() / 3_600.0,
            "directional_slippage": side
            * (fill_price - entry_price)
            / entry_price,
            "candidate_to_original_exit_gross_return": side
            * (float(row["exit_price"]) - fill_price)
            / fill_price,
        }
    return output


def attribute_row(
    row: pd.Series,
    *,
    hourly: pd.DataFrame,
    daily: pd.DataFrame,
) -> list[dict[str, Any]]:
    side = 1 if row["side"] == "long" else -1
    tail_hit = first_tail_hit(row, hourly=hourly, side=side)
    original_tail = bool(row["early_tail"])
    if original_tail != (tail_hit is not None):
        raise RuntimeError(
            f"tail label mismatch for {row['symbol']} {row['entry_ts']}"
        )
    candidates = confirmation_candidates(
        row,
        hourly=hourly,
        daily=daily,
        side=side,
    )
    output: list[dict[str, Any]] = []
    for arm, candidate in candidates.items():
        fill_ts = (
            pd.Timestamp(candidate["candidate_fill_ts"])
            if candidate["candidate_fill_ts"] is not None
            else None
        )
        before_tail = bool(
            fill_ts is not None
            and (tail_hit is None or fill_ts < tail_hit)
        )
        valid = bool(candidate["candidate_valid"])
        output.append(
            {
                "pair_rank": int(row["pair_rank"]),
                "strata": str(row["strata"]),
                "symbol": str(row["symbol"]),
                "side": str(row["side"]),
                "trade_index": int(row["trade_index"]),
                "entry_ts": str(row["entry_ts"]),
                "entry_year": int(row["entry_year"]),
                "exit_ts": str(row["exit_ts"]),
                "original_early_tail": original_tail,
                "original_winner": float(row["final_net_return"]) > 0.0,
                "tail_hit_ts": tail_hit.isoformat() if tail_hit is not None else None,
                "arm": arm,
                **candidate,
                "confirmed_before_tail": before_tail,
                "tail_rejected": bool(original_tail and not before_tail),
                "nontail_retained": bool(not original_tail and valid),
                "winner_retained": bool(
                    float(row["final_net_return"]) > 0.0 and valid
                ),
            }
        )
    return output


def analysis_frames(detail: pd.DataFrame) -> dict[str, pd.DataFrame]:
    expanded = detail.assign(stratum=detail["strata"].str.split(",")).explode(
        "stratum"
    )
    expanded = expanded.loc[expanded["stratum"].isin(STRATA)].copy()
    unique = (
        expanded.sort_values(["pair_rank", "trade_index"])
        .drop_duplicates(
            ["symbol", "side", "entry_ts", "stratum", "arm"]
        )
        .copy()
    )
    return {"pair_weighted": expanded, "unique_entry": unique}


def summarize(group: pd.DataFrame) -> dict[str, Any]:
    tails = group.loc[group["original_early_tail"]]
    nontails = group.loc[~group["original_early_tail"]]
    winners = group.loc[group["original_winner"]]
    valid = group.loc[group["candidate_valid"]]
    return {
        "rows": len(group),
        "tail_count": len(tails),
        "tail_rejection": (
            float(tails["tail_rejected"].mean()) if len(tails) else math.nan
        ),
        "nontail_count": len(nontails),
        "nontail_retention": (
            float(nontails["nontail_retained"].mean())
            if len(nontails)
            else math.nan
        ),
        "winner_count": len(winners),
        "winner_retention": (
            float(winners["winner_retained"].mean())
            if len(winners)
            else math.nan
        ),
        "valid_candidates": len(valid),
        "median_delay_hours": (
            float(valid["delay_hours"].median()) if len(valid) else math.nan
        ),
        "median_directional_slippage": (
            float(valid["directional_slippage"].median())
            if len(valid)
            else math.nan
        ),
        "median_candidate_to_exit_return": (
            float(valid["candidate_to_original_exit_gross_return"].median())
            if len(valid)
            else math.nan
        ),
    }


def metric_rows(detail: pd.DataFrame) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for weighting, frame in analysis_frames(detail).items():
        specs = [
            ("asset_overall", ["arm", "symbol"]),
            ("asset_side_stratum", ["arm", "symbol", "side", "stratum"]),
        ]
        for level, keys in specs:
            for group_key, group in frame.groupby(keys):
                values = group_key if isinstance(group_key, tuple) else (group_key,)
                dimensions = dict(zip(keys, values, strict=True))
                output.append(
                    {
                        "weighting": weighting,
                        "level": level,
                        "arm": dimensions["arm"],
                        "symbol": dimensions["symbol"],
                        "side": dimensions.get("side", "all"),
                        "stratum": dimensions.get("stratum", "all"),
                        **summarize(group),
                    }
                )
    return output


def calendar_gate(frame: pd.DataFrame, *, arm: str, symbol: str) -> dict[str, Any]:
    selected = frame.loc[frame["arm"].eq(arm) & frame["symbol"].eq(symbol)]
    years: list[dict[str, Any]] = []
    for year, group in selected.groupby("entry_year"):
        metrics = summarize(group)
        eligible = metrics["tail_count"] >= 5
        passed = bool(
            eligible
            and metrics["tail_rejection"] >= 0.50
            and metrics["nontail_retention"] >= 0.60
        )
        years.append(
            {
                "year": int(year),
                "eligible": eligible,
                "pass": passed,
                **metrics,
            }
        )
    eligible_rows = [row for row in years if row["eligible"]]
    return {
        "years": years,
        "eligible_years": len(eligible_rows),
        "pass_rate": (
            float(np.mean([row["pass"] for row in eligible_rows]))
            if eligible_rows
            else math.nan
        ),
    }


def decide(detail: pd.DataFrame, metrics: list[dict[str, Any]]) -> dict[str, Any]:
    frames = analysis_frames(detail)
    metric_frame = pd.DataFrame(metrics)
    decisions: dict[str, Any] = {}
    for arm in ARMS:
        rows = metric_frame.loc[
            metric_frame["level"].eq("asset_overall")
            & metric_frame["arm"].eq(arm)
        ]
        weakest_tail = math.inf
        weakest_nontail = math.inf
        weakest_winner = math.inf
        worst_delay = 0.0
        overall: dict[str, Any] = {}
        for weighting in frames:
            overall[weighting] = {}
            for symbol in ("BTCUSDT", "ETHUSDT"):
                row = rows.loc[
                    rows["weighting"].eq(weighting)
                    & rows["symbol"].eq(symbol)
                ].iloc[0]
                summary = {
                    key: row[key]
                    for key in (
                        "rows",
                        "tail_count",
                        "tail_rejection",
                        "nontail_count",
                        "nontail_retention",
                        "winner_count",
                        "winner_retention",
                        "valid_candidates",
                        "median_delay_hours",
                    )
                }
                overall[weighting][symbol] = summary
                weakest_tail = min(weakest_tail, float(row["tail_rejection"]))
                weakest_nontail = min(
                    weakest_nontail, float(row["nontail_retention"])
                )
                weakest_winner = min(
                    weakest_winner, float(row["winner_retention"])
                )
                worst_delay = max(worst_delay, float(row["median_delay_hours"]))
        calendar: dict[str, Any] = {}
        weakest_calendar = math.inf
        for weighting, frame in frames.items():
            calendar[weighting] = {}
            for symbol in ("BTCUSDT", "ETHUSDT"):
                row = calendar_gate(frame, arm=arm, symbol=symbol)
                calendar[weighting][symbol] = row
                weakest_calendar = min(weakest_calendar, float(row["pass_rate"]))
        gates = {
            "tail_rejection_gate": weakest_tail >= 0.60,
            "nontail_retention_gate": weakest_nontail >= 0.70,
            "winner_retention_gate": weakest_winner >= 0.75,
            "delay_gate": worst_delay <= 12.0,
            "calendar_gate": weakest_calendar >= 0.70,
        }
        decisions[arm] = {
            "pass": all(gates.values()),
            **gates,
            "weakest_tail_rejection": weakest_tail,
            "weakest_nontail_retention": weakest_nontail,
            "weakest_winner_retention": weakest_winner,
            "worst_median_delay_hours": worst_delay,
            "weakest_calendar_pass_rate": weakest_calendar,
            "overall": overall,
            "calendar": calendar,
        }
    passed = [arm for arm, row in decisions.items() if row["pass"]]
    passed.sort(
        key=lambda arm: (
            decisions[arm]["weakest_tail_rejection"],
            decisions[arm]["weakest_winner_retention"],
            -decisions[arm]["worst_median_delay_hours"],
        ),
        reverse=True,
    )
    return {
        "arms": decisions,
        "selected_arm": passed[0] if passed else None,
        "passing_arms": passed,
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
            {
                "original_early_tail": [True, False],
                "tail_rejected": [True, False],
                "nontail_retained": [False, True],
                "original_winner": [False, True],
                "winner_retained": [False, True],
                "candidate_valid": [False, True],
                "delay_hours": [math.nan, 2.0],
                "directional_slippage": [math.nan, 0.01],
                "candidate_to_original_exit_gross_return": [math.nan, 0.1],
            }
        )
        result = summarize(frame)
        assert result["tail_rejection"] == 1.0
        assert result["nontail_retention"] == 1.0
        print("self-test: PASS")
        return

    baseline = load_module(BASELINE_PATH, "binance_ma7_p2h_baseline")
    contexts: dict[str, dict[str, pd.DataFrame]] = {}
    for symbol, slug in baseline.ASSETS.items():
        hourly = pd.read_parquet(baseline.P0_DIR / f"{slug}_perp_1h.parquet")
        daily = pd.read_parquet(baseline.P0_DIR / f"{slug}_perp_1d.parquet")
        hourly["ts"] = pd.to_datetime(hourly["ts"], utc=True)
        daily["ts"] = pd.to_datetime(daily["ts"], utc=True)
        contexts[symbol] = {
            "hourly": hourly.sort_values("ts"),
            "daily": daily.sort_values("ts"),
        }
    entries = pd.read_csv(ENTRY_PATH)
    detail_rows: list[dict[str, Any]] = []
    for offset, (_, row) in enumerate(entries.iterrows(), start=1):
        context = contexts[str(row["symbol"])]
        detail_rows.extend(
            attribute_row(
                row,
                hourly=context["hourly"],
                daily=context["daily"],
            )
        )
        if offset % 2_000 == 0 or offset == len(entries):
            print(f"hourly-confirmation: {offset}/{len(entries)} entries", flush=True)
    detail = pd.DataFrame(detail_rows)
    metrics = metric_rows(detail)
    decision = decide(detail, metrics)
    frames = analysis_frames(detail)
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "campaign": "P2-H finite hourly entry confirmation",
        "status": "explore / not promoted / not live-ready",
        "evidence_role": "development-only; audit and prospective not read",
        "raw_entries": len(entries),
        "detail_rows": len(detail),
        "pair_weighted_rows": len(frames["pair_weighted"]),
        "unique_entry_rows": len(frames["unique_entry"]),
        "expiry_hours": EXPIRY_HOURS,
        "tail_threshold": TAIL_THRESHOLD,
        "decision": decision,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_ma7_p2h_hourly_entry_confirmation_{args.run_date}"
    detail.to_csv(ARTIFACT_DIR / f"{stem}_events.csv", index=False)
    pd.DataFrame(metrics).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics.csv", index=False
    )
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(clean_json(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(clean_json(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
