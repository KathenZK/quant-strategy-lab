from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_30m_k2_fq_v2_atrvt_off_backtest as base  # noqa: E402
import research_hype_30m_k2_strict_validation_gates as strict  # noqa: E402
import research_hype_30m_k2_v2_1_dynamic_atr_bracket as dynamic  # noqa: E402
import research_hype_30m_k2_v2_1_rsi_macd_filters as prior  # noqa: E402
import research_hype_30m_k2_v2_full_ablation_and_tune as tune  # noqa: E402


RUN_DATE = "2026-07-13"
ARTIFACT_DIR = base.ARTIFACT_DIR
SUMMARY_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_loss_regime_filters_{RUN_DATE}.json"
PROFILE_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_loss_regime_profile_{RUN_DATE}.csv"
SEARCH_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_loss_regime_filter_search_{RUN_DATE}.csv"
OOS_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_loss_regime_filter_oos_{RUN_DATE}.csv"
MC_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_loss_regime_filter_mc_{RUN_DATE}.csv"
START_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_loss_regime_filter_start_{RUN_DATE}.csv"
PHASE_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_loss_regime_filter_phase_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_loss_regime_filter_trades_{RUN_DATE}.csv"

RETURN_FLOOR = 0.80
VALIDATION_FLOOR = 0.70
MDD_MIN_PP = 0.25


@dataclass(frozen=True, slots=True)
class FilterSpec:
    family: str
    kind: str
    params: tuple[float, ...]
    components: tuple["FilterSpec", ...] = ()

    @property
    def label(self) -> str:
        if self.components:
            return "combo__" + "__".join(item.label for item in self.components)
        values = "_".join(str(value).replace(".", "p") for value in self.params)
        return f"{self.family}_{self.kind}_{values}"


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    returns = output["close"].pct_change()
    output["atr_pct"] = output["atr96"] / output["close"]
    output["atr_ratio"] = output["atr10"] / output["atr96"]
    output["rv_ratio"] = returns.rolling(12, min_periods=12).std() / returns.rolling(
        48,
        min_periods=48,
    ).std()
    output["quote_ratio"] = output["quote_volume"] / output["quote_volume"].rolling(
        96,
        min_periods=48,
    ).median()
    output["trades_ratio"] = output["trade_count"] / output["trade_count"].rolling(
        96,
        min_periods=48,
    ).median()
    avg_trade = output["quote_volume"] / output["trade_count"].replace(0.0, np.nan)
    output["avg_trade_ratio"] = avg_trade / avg_trade.rolling(
        96,
        min_periods=48,
    ).median()
    output["vwap"] = output["quote_volume"] / output["volume"].replace(0.0, np.nan)
    output["vwap"] = output["vwap"].fillna(output["close"])
    candle_range = (output["high"] - output["low"]).replace(0.0, np.nan)
    output["body_ratio"] = (output["close"] - output["open"]).abs() / candle_range
    output["close_location"] = (output["close"] - output["low"]) / candle_range
    output["long_break_strength"] = (output["close"] - output["upper"]) / output["atr10"]
    output["short_break_strength"] = (output["lower"] - output["close"]) / output["atr10"]
    output["long_vwap_confirm"] = output["close"].ge(output["vwap"])
    output["short_vwap_confirm"] = output["close"].le(output["vwap"])
    return output


def masks(frame: pd.DataFrame, spec: FilterSpec) -> tuple[pd.Series, pd.Series]:
    if spec.components:
        long_mask = pd.Series(True, index=frame.index)
        short_mask = pd.Series(True, index=frame.index)
        for component in spec.components:
            long_part, short_part = masks(frame, component)
            long_mask &= long_part.fillna(False)
            short_mask &= short_part.fillna(False)
        return long_mask, short_mask
    value = frame[spec.kind] if spec.kind in frame else None
    if spec.kind in {"atr_pct", "atr_ratio", "rv_ratio", "quote_ratio", "trades_ratio", "avg_trade_ratio"}:
        lower, upper = spec.params
        mask = value.between(lower, upper)
        return mask, mask
    if spec.kind == "break_strength":
        lower, upper = spec.params
        return (
            frame["long_break_strength"].between(lower, upper),
            frame["short_break_strength"].between(lower, upper),
        )
    if spec.kind == "body_ratio":
        mask = frame["body_ratio"].ge(spec.params[0])
        return mask, mask
    if spec.kind == "close_location":
        threshold = spec.params[0]
        return (
            frame["close_location"].ge(threshold),
            frame["close_location"].le(1.0 - threshold),
        )
    if spec.kind == "vwap_confirm":
        return frame["long_vwap_confirm"], frame["short_vwap_confirm"]
    raise ValueError(spec)


def apply_filter(frame: pd.DataFrame, spec: FilterSpec | None) -> pd.DataFrame:
    output = frame.copy()
    if spec is None:
        return output
    long_mask, short_mask = masks(output, spec)
    output["long_signal"] &= long_mask.fillna(False)
    output["short_signal"] &= short_mask.fillna(False)
    return output


def filter_specs() -> list[FilterSpec]:
    specs: list[FilterSpec] = []
    specs.extend(
        FilterSpec("volatility", "atr_pct", (lower, upper))
        for lower in (0.0, 0.005, 0.0075, 0.010)
        for upper in (0.0125, 0.015, 0.0175, 0.020, 1.0)
        if lower < upper
    )
    specs.extend(
        FilterSpec("volatility", "atr_ratio", (lower, upper))
        for lower in (0.0, 0.6, 0.8, 1.0)
        for upper in (1.0, 1.2, 1.5, 2.0, 100.0)
        if lower < upper
    )
    specs.extend(
        FilterSpec("volatility", "rv_ratio", (lower, upper))
        for lower in (0.0, 0.6, 0.8, 1.0)
        for upper in (1.0, 1.25, 1.5, 2.0, 100.0)
        if lower < upper
    )
    for kind in ("quote_ratio", "trades_ratio", "avg_trade_ratio"):
        specs.extend(
            FilterSpec("liquidity", kind, (lower, upper))
            for lower in (0.0, 0.5, 0.75, 1.0, 1.25, 1.5)
            for upper in (1.5, 2.0, 3.0, 100.0)
            if lower < upper
        )
    specs.extend(
        FilterSpec("quality", "break_strength", (lower, upper))
        for lower in (0.0, 0.1, 0.25, 0.5)
        for upper in (0.5, 1.0, 1.5, 2.0, 100.0)
        if lower < upper
    )
    specs.extend(
        FilterSpec("quality", "body_ratio", (threshold,))
        for threshold in (0.2, 0.4, 0.6, 0.8)
    )
    specs.extend(
        FilterSpec("quality", "close_location", (threshold,))
        for threshold in (0.55, 0.65, 0.75, 0.85)
    )
    specs.append(FilterSpec("quality", "vwap_confirm", ()))
    return specs


def profile_trades(
    features: pd.DataFrame,
    trades: pd.DataFrame,
) -> pd.DataFrame:
    columns = [
        "atr_pct",
        "atr_ratio",
        "rv_ratio",
        "quote_ratio",
        "trades_ratio",
        "avg_trade_ratio",
        "body_ratio",
        "close_location",
        "long_break_strength",
        "short_break_strength",
    ]
    rows = []
    for trade in trades.itertuples():
        entry = pd.Timestamp(trade.entry_ts)
        entry_i = features.index.get_loc(entry)
        signal = features.iloc[entry_i - 1]
        row = {
            "entry_ts": entry,
            "direction": trade.direction,
            "net_return_pct": trade.net_account_return_pct,
            "winner": trade.net_account_return_pct > 0.0,
        }
        row.update({column: signal[column] for column in columns})
        row["break_strength"] = (
            signal["long_break_strength"]
            if trade.direction == "long"
            else signal["short_break_strength"]
        )
        rows.append(row)
    detail = pd.DataFrame(rows)
    summaries = []
    for column in [*columns[:8], "break_strength"]:
        for winner, group in detail.groupby("winner"):
            summaries.append(
                {
                    "feature": column,
                    "group": "winner" if winner else "loser",
                    "count": int(len(group)),
                    "mean": float(group[column].mean()),
                    "median": float(group[column].median()),
                    "p25": float(group[column].quantile(0.25)),
                    "p75": float(group[column].quantile(0.75)),
                }
            )
    return pd.DataFrame(summaries)


def evaluate(
    spec: FilterSpec | None,
    features: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
    baseline: dict[str, strict.StrictResult],
) -> dict[str, Any]:
    filtered = apply_filter(features, spec)
    execution = strict.ExecutionConfig()
    label = "baseline" if spec is None else spec.label
    full = strict.simulate(label + "_full", filtered, funding, cfg, execution, start_ts=start, end_ts=end)
    train = strict.simulate(label + "_train", filtered, funding, cfg, execution, start_ts=start, end_ts=tune.TRAIN_END)
    validation = strict.simulate(
        label + "_validation",
        filtered,
        funding,
        cfg,
        execution,
        start_ts=tune.VALIDATION_START,
        end_ts=tune.VALIDATION_END,
    )
    retention = full.metrics["return_pct"] / baseline["full"].metrics["return_pct"]
    validation_retention = validation.metrics["return_pct"] / baseline["validation"].metrics["return_pct"]
    meets_full = bool(
        full.metrics["win_rate_pct"] > baseline["full"].metrics["win_rate_pct"]
        and full.metrics["max_drawdown_pct"] >= baseline["full"].metrics["max_drawdown_pct"] + MDD_MIN_PP
        and retention >= RETURN_FLOOR
    )
    meets_all = bool(
        meets_full
        and validation.metrics["win_rate_pct"] >= baseline["validation"].metrics["win_rate_pct"]
        and validation.metrics["max_drawdown_pct"] >= baseline["validation"].metrics["max_drawdown_pct"] + MDD_MIN_PP
        and validation_retention >= VALIDATION_FLOOR
    )
    score = 0.45 * prior.split_score(train, baseline["train"]) + 0.55 * prior.split_score(
        validation,
        baseline["validation"],
    )
    return {
        "spec": spec,
        "features": filtered,
        "full": full,
        "train": train,
        "validation": validation,
        "retention": retention,
        "validation_retention": validation_retention,
        "meets_full": meets_full,
        "meets_all": meets_all,
        "score": score,
    }


def row(result: dict[str, Any]) -> dict[str, Any]:
    spec = result["spec"]
    return {
        "variant": "baseline" if spec is None else spec.label,
        "family": "none" if spec is None else spec.family,
        "kind": "baseline" if spec is None else spec.kind,
        "params": "[]" if spec is None else json.dumps(spec.params),
        "components": "[]" if spec is None else json.dumps([asdict(item) for item in spec.components]),
        "score": result["score"],
        "full_return_pct": result["full"].metrics["return_pct"],
        "full_mdd_pct": result["full"].metrics["max_drawdown_pct"],
        "full_win_rate_pct": result["full"].metrics["win_rate_pct"],
        "full_trades": result["full"].metrics["trades"],
        "return_retention": result["retention"],
        "validation_return_pct": result["validation"].metrics["return_pct"],
        "validation_mdd_pct": result["validation"].metrics["max_drawdown_pct"],
        "validation_win_rate_pct": result["validation"].metrics["win_rate_pct"],
        "validation_retention": result["validation_retention"],
        "meets_full": result["meets_full"],
        "meets_all": result["meets_all"],
    }


def run_search(
    features: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, Any] | None, dict[str, Any] | None, dict[str, strict.StrictResult]]:
    execution = strict.ExecutionConfig()
    baseline = {
        "full": strict.simulate("regime_baseline_full", features, funding, cfg, execution, start_ts=start, end_ts=end),
        "train": strict.simulate("regime_baseline_train", features, funding, cfg, execution, start_ts=start, end_ts=tune.TRAIN_END),
        "validation": strict.simulate(
            "regime_baseline_validation",
            features,
            funding,
            cfg,
            execution,
            start_ts=tune.VALIDATION_START,
            end_ts=tune.VALIDATION_END,
        ),
    }
    singles = [evaluate(spec, features, funding, cfg, start, end, baseline) for spec in filter_specs()]
    ranked: dict[str, list[dict[str, Any]]] = {}
    for family in ("volatility", "liquidity", "quality"):
        ranked[family] = sorted(
            [item for item in singles if item["spec"].family == family],
            key=lambda item: item["score"],
            reverse=True,
        )[:8]
    combos = []
    seen: set[bytes] = set()
    for first_family, second_family in (
        ("volatility", "liquidity"),
        ("volatility", "quality"),
        ("liquidity", "quality"),
    ):
        for first in ranked[first_family]:
            for second in ranked[second_family]:
                spec = FilterSpec("combo", "pair", (), (first["spec"], second["spec"]))
                filtered = apply_filter(features, spec)
                signature = filtered["long_signal"].to_numpy(bool).tobytes() + filtered[
                    "short_signal"
                ].to_numpy(bool).tobytes()
                if signature in seen:
                    continue
                seen.add(signature)
                combos.append(evaluate(spec, features, funding, cfg, start, end, baseline))
    results = singles + combos
    table = pd.DataFrame([row(item) for item in results]).sort_values(
        ["meets_all", "score"],
        ascending=[False, False],
    )
    accepted = [item for item in results if item["meets_all"]]
    selected = (
        max(
            accepted,
            key=lambda item: (
                item["full"].metrics["win_rate_pct"],
                item["full"].metrics["max_drawdown_pct"],
                item["retention"],
                item["score"],
            ),
        )
        if accepted
        else None
    )
    near_pool = [item for item in results if item["meets_full"]]
    near = max(near_pool, key=lambda item: item["score"]) if near_pool else None
    return table, selected, near, baseline


def phase_sets(
    m1: pd.DataFrame,
    cfg: base.StrategyConfig,
    spec: FilterSpec,
) -> tuple[dict[int, pd.DataFrame], dict[int, pd.DataFrame]]:
    bars30 = {
        phase: base.aggregate_ohlcv(m1, freq="30min", phase_min=phase, expected_rows=30)[0]
        for phase in strict.PHASES_30M
    }
    bars1h = {
        phase: base.aggregate_ohlcv(m1, freq="60min", phase_min=phase, expected_rows=60)[0]
        for phase in strict.PHASES_1H
    }

    def build(b30: pd.DataFrame, h1: pd.DataFrame) -> pd.DataFrame:
        return apply_filter(add_features(dynamic.v21_features(b30, h1, cfg)), spec)

    return (
        {phase: build(frame, bars1h[0]) for phase, frame in bars30.items()},
        {phase: build(bars30[0], frame) for phase, frame in bars1h.items()},
    )


def robustness(
    target: dict[str, Any],
    m1: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    execution = strict.ExecutionConfig()
    features, full, spec = target["features"], target["full"], target["spec"]
    holdout = strict.simulate(
        "regime_target_holdout",
        features,
        funding,
        cfg,
        execution,
        start_ts=tune.HOLDOUT_START,
        end_ts=end,
    )
    oos = strict.run_rolling_oos(features, funding, cfg, execution, start, end)
    mc = strict.run_trade_mc(full.trades, 5000)
    mc2, mc3 = mc[mc.mc_type.eq("mc2_shuffle")], mc[mc.mc_type.eq("mc3_bootstrap")]
    mc2_p05 = float(mc2.max_drawdown_pct.quantile(0.05))
    mc_limit = -1.5 * abs(float(full.metrics["max_drawdown_pct"]))
    daily = full.equity.resample("1D").last().pct_change().dropna()
    significance = strict.probabilistic_sharpe(daily)
    significance["dsr_n1000"] = strict.deflated_sharpe(daily, 1000)
    starts = strict.run_start_sensitivity(features, funding, cfg, execution, start, end)
    start_cv = float(starts.cagr_pct.std(ddof=1) / abs(starts.cagr_pct.mean()))
    phase30, phase1h = phase_sets(m1, cfg, spec)
    phases = strict.run_phase_gate(
        phase30,
        phase1h,
        funding,
        cfg,
        execution,
        [pd.Timestamp(value) for value in starts.start_ts.iloc[:20]],
        end,
    )
    phase_summary = {
        "30m": strict.phase_gate_status(phases, "30m"),
        "1h": strict.phase_gate_status(phases, "1h"),
    }
    summary = {
        "holdout": holdout.metrics,
        "rolling_oos": {
            "positive_fraction": float(oos.return_pct.gt(0.0).mean()),
            "median_return_pct": float(oos.return_pct.median()),
        },
        "monte_carlo": {
            "status": "pass" if mc2_p05 >= mc_limit else "fail",
            "mc2_mdd_p05_pct": mc2_p05,
            "mc2_mdd_limit_pct": mc_limit,
            "mc3_return_p05_pct": float(mc3.return_pct.quantile(0.05)),
        },
        "significance": significance,
        "start_time": {"cagr_cv": start_cv},
        "phase": phase_summary,
    }
    return summary, {"oos": oos, "mc": mc, "starts": starts, "phases": phases}


def payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "filter": asdict(result["spec"]),
        "full": {"metrics": result["full"].metrics, "slices": result["full"].slices},
        "train": result["train"].metrics,
        "validation": result["validation"].metrics,
        "retention": result["retention"],
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    args = type(
        "Args",
        (),
        {"since": "2025-05-30T00:00:00Z", "until": "", "refresh_cache": False, "timeout": 45.0},
    )()
    funding_args = type("FundingArgs", (), {"refresh_data": False, "timeout": 45.0})()
    m1 = base.load_or_fetch_1m(args)
    funding = strict.load_or_fetch_funding(funding_args, m1)
    cfg = dynamic.v21_config()
    b30 = base.aggregate_ohlcv(m1, freq="30min", phase_min=0, expected_rows=30)[0]
    h1 = base.aggregate_ohlcv(m1, freq="60min", phase_min=0, expected_rows=60)[0]
    features = add_features(dynamic.v21_features(b30, h1, cfg))
    start, end = strict.ready_start(features), b30.index.max() + pd.Timedelta(minutes=30)
    search, selected, near, baseline = run_search(features, funding, cfg, start, end)
    profile = profile_trades(features, baseline["full"].trades)
    target = selected or near
    robustness_result = None
    if target is not None:
        robustness_result, frames = robustness(target, m1, funding, cfg, start, end)
        target["full"].trades.to_csv(TRADES_PATH, index=False)
        frames["oos"].to_csv(OOS_PATH, index=False)
        frames["mc"].to_csv(MC_PATH, index=False)
        frames["starts"].to_csv(START_PATH, index=False)
        frames["phases"].to_csv(PHASE_PATH, index=False)
    summary = {
        "strategy": "HYPE-30M-Keltner-Trend-Breakout-V2.1",
        "study": "loss regime and breakout quality filters",
        "run_date": RUN_DATE,
        "search": {
            "variants": int(len(search)),
            "meeting_full_goal": int(search.meets_full.sum()),
            "meeting_all_goals": int(search.meets_all.sum()),
        },
        "baseline": {key: value.metrics for key, value in baseline.items()},
        "selected": payload(selected) if selected else None,
        "near_miss": payload(near) if near else None,
        "robustness": robustness_result,
        "decision": "candidate_found" if selected else "keep_v2_1_no_filter_met_constraints",
        "warning": "Historical data is not true OOS.",
    }
    profile.to_csv(PROFILE_PATH, index=False)
    search.to_csv(SEARCH_PATH, index=False)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("baseline", baseline["full"].metrics)
    print("search", len(search), "full", int(search.meets_full.sum()), "all", int(search.meets_all.sum()))
    print("selected", summary["selected"])
    print("near", summary["near_miss"])
    print("robustness", robustness_result)
    print(search.head(15).to_string(index=False))
    print("summary", SUMMARY_PATH)


if __name__ == "__main__":
    main()
