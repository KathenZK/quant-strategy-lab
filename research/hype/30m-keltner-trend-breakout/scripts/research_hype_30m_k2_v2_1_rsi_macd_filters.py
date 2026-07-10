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
import research_hype_30m_k2_v2_full_ablation_and_tune as tune  # noqa: E402


RUN_DATE = "2026-07-10"
ARTIFACT_DIR = base.ARTIFACT_DIR
SUMMARY_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_rsi_macd_filters_{RUN_DATE}.json"
SEARCH_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_rsi_macd_filter_search_{RUN_DATE}.csv"
OOS_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_rsi_macd_filter_oos_{RUN_DATE}.csv"
MC_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_rsi_macd_filter_mc_{RUN_DATE}.csv"
START_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_rsi_macd_filter_start_{RUN_DATE}.csv"
PHASE_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_rsi_macd_filter_phase_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_DIR / f"hype_30m_k2_v2_1_rsi_macd_filter_trades_{RUN_DATE}.csv"

RETURN_RETENTION_FLOOR = 0.80
VALIDATION_RETENTION_FLOOR = 0.70
MDD_IMPROVEMENT_MIN_PP = 0.25
RSI_LOWER = (50.0, 52.0, 55.0, 58.0)
RSI_UPPER = (65.0, 70.0, 75.0, 80.0, 100.0)
SOURCES = ("30m", "1h")
MACD_MODES = ("hist_sign", "line_zero", "hist_and_zero", "hist_momentum")


@dataclass(frozen=True, slots=True)
class FilterConfig:
    rsi_source: str | None = None
    rsi_lower: float = 50.0
    rsi_upper: float = 100.0
    macd_source: str | None = None
    macd_mode: str | None = None


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = base.rma(gain, window)
    avg_loss = base.rma(loss, window)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    output = 100.0 - 100.0 / (1.0 + rs)
    output = output.where(avg_loss.ne(0.0), 100.0)
    return output


def map_htf_numeric(
    frame: pd.DataFrame,
    htf: pd.DataFrame,
    column: str,
) -> np.ndarray:
    h1_close_times = (htf.index + pd.Timedelta(hours=1)).to_numpy()
    b30_close_times = (frame.index + pd.Timedelta(minutes=30)).to_numpy()
    mapped = np.searchsorted(h1_close_times, b30_close_times, side="right") - 1
    output = np.full(len(frame), np.nan, dtype="float64")
    valid = mapped >= 0
    values = pd.to_numeric(htf[column], errors="coerce").to_numpy("float64")
    output[valid] = values[mapped[valid]]
    return output


def indicator_frame(
    b30: pd.DataFrame,
    h1: pd.DataFrame,
    cfg: base.StrategyConfig,
) -> pd.DataFrame:
    frame = dynamic.v21_features(b30, h1, cfg)
    frame["rsi_30m"] = rsi(frame["close"])
    frame["macd_30m"] = base.ema(frame["close"], 12) - base.ema(frame["close"], 26)
    frame["macd_signal_30m"] = base.ema(frame["macd_30m"], 9)
    frame["macd_hist_30m"] = frame["macd_30m"] - frame["macd_signal_30m"]
    frame["macd_hist_delta_30m"] = frame["macd_hist_30m"].diff()

    htf = h1.copy()
    htf["rsi_1h"] = rsi(htf["close"])
    htf["macd_1h"] = base.ema(htf["close"], 12) - base.ema(htf["close"], 26)
    htf["macd_signal_1h"] = base.ema(htf["macd_1h"], 9)
    htf["macd_hist_1h"] = htf["macd_1h"] - htf["macd_signal_1h"]
    htf["macd_hist_delta_1h"] = htf["macd_hist_1h"].diff()
    for column in [
        "rsi_1h",
        "macd_1h",
        "macd_signal_1h",
        "macd_hist_1h",
        "macd_hist_delta_1h",
    ]:
        frame[column] = map_htf_numeric(frame, htf, column)
    return frame


def filtered_features(
    indicators: pd.DataFrame,
    config: FilterConfig,
) -> pd.DataFrame:
    frame = indicators.copy()
    long_filter = pd.Series(True, index=frame.index)
    short_filter = pd.Series(True, index=frame.index)
    if config.rsi_source is not None:
        column = f"rsi_{config.rsi_source}"
        long_filter &= frame[column].ge(config.rsi_lower)
        long_filter &= frame[column].le(config.rsi_upper)
        short_filter &= frame[column].le(100.0 - config.rsi_lower)
        short_filter &= frame[column].ge(100.0 - config.rsi_upper)
    if config.macd_source is not None and config.macd_mode is not None:
        source = config.macd_source
        macd = frame[f"macd_{source}"]
        hist = frame[f"macd_hist_{source}"]
        hist_delta = frame[f"macd_hist_delta_{source}"]
        if config.macd_mode == "hist_sign":
            long_filter &= hist.gt(0.0)
            short_filter &= hist.lt(0.0)
        elif config.macd_mode == "line_zero":
            long_filter &= macd.gt(0.0)
            short_filter &= macd.lt(0.0)
        elif config.macd_mode == "hist_and_zero":
            long_filter &= hist.gt(0.0) & macd.gt(0.0)
            short_filter &= hist.lt(0.0) & macd.lt(0.0)
        elif config.macd_mode == "hist_momentum":
            long_filter &= hist.gt(0.0) & hist_delta.gt(0.0)
            short_filter &= hist.lt(0.0) & hist_delta.lt(0.0)
        else:
            raise ValueError(f"unknown MACD mode: {config.macd_mode}")
    frame["long_signal"] = frame["long_signal"] & long_filter.fillna(False)
    frame["short_signal"] = frame["short_signal"] & short_filter.fillna(False)
    return frame


def label(config: FilterConfig) -> str:
    rsi_part = (
        "none"
        if config.rsi_source is None
        else f"{config.rsi_source}_{config.rsi_lower:g}_{config.rsi_upper:g}"
    )
    macd_part = (
        "none"
        if config.macd_source is None
        else f"{config.macd_source}_{config.macd_mode}"
    )
    return f"rsi_{rsi_part}_macd_{macd_part}"


def filter_configs() -> list[FilterConfig]:
    configs: dict[str, FilterConfig] = {}

    def add(config: FilterConfig) -> None:
        configs[label(config)] = config

    add(FilterConfig())
    rsi_configs = []
    for source in SOURCES:
        for lower in RSI_LOWER:
            for upper in RSI_UPPER:
                if lower >= upper:
                    continue
                config = FilterConfig(
                    rsi_source=source,
                    rsi_lower=lower,
                    rsi_upper=upper,
                )
                rsi_configs.append(config)
                add(config)
    macd_configs = []
    for source in SOURCES:
        for mode in MACD_MODES:
            config = FilterConfig(macd_source=source, macd_mode=mode)
            macd_configs.append(config)
            add(config)
    for rsi_config in rsi_configs:
        for macd_config in macd_configs:
            add(
                FilterConfig(
                    rsi_source=rsi_config.rsi_source,
                    rsi_lower=rsi_config.rsi_lower,
                    rsi_upper=rsi_config.rsi_upper,
                    macd_source=macd_config.macd_source,
                    macd_mode=macd_config.macd_mode,
                )
            )
    return list(configs.values())


def log_retention(candidate_return: float, baseline_return: float) -> float:
    candidate_log = np.log(max(1e-12, 1.0 + candidate_return / 100.0))
    baseline_log = np.log(max(1e-12, 1.0 + baseline_return / 100.0))
    return float(candidate_log / baseline_log) if baseline_log > 0.0 else 0.0


def split_score(
    candidate: strict.StrictResult,
    baseline: strict.StrictResult,
) -> float:
    metrics = candidate.metrics
    base_metrics = baseline.metrics
    if metrics["return_pct"] <= -99.0 or metrics["trades"] < 0.45 * base_metrics["trades"]:
        return -1e9
    retention = log_retention(metrics["return_pct"], base_metrics["return_pct"])
    win_gain = (metrics["win_rate_pct"] - base_metrics["win_rate_pct"]) / 5.0
    mdd_gain = (
        abs(base_metrics["max_drawdown_pct"]) - abs(metrics["max_drawdown_pct"])
    ) / max(1e-12, abs(base_metrics["max_drawdown_pct"]))
    return float(retention + 1.5 * win_gain + 2.0 * mdd_gain)


def run_search(
    indicators: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[
    pd.DataFrame,
    dict[str, Any] | None,
    dict[str, strict.StrictResult],
    dict[str, dict[str, Any]],
]:
    execution = strict.ExecutionConfig()
    baseline_features = filtered_features(indicators, FilterConfig())
    baseline = {
        "full": strict.simulate(
            "filter_baseline_full",
            baseline_features,
            funding,
            cfg,
            execution,
            start_ts=start,
            end_ts=end,
        ),
        "train": strict.simulate(
            "filter_baseline_train",
            baseline_features,
            funding,
            cfg,
            execution,
            start_ts=start,
            end_ts=tune.TRAIN_END,
        ),
        "validation": strict.simulate(
            "filter_baseline_validation",
            baseline_features,
            funding,
            cfg,
            execution,
            start_ts=tune.VALIDATION_START,
            end_ts=tune.VALIDATION_END,
        ),
        "holdout": strict.simulate(
            "filter_baseline_holdout",
            baseline_features,
            funding,
            cfg,
            execution,
            start_ts=tune.HOLDOUT_START,
            end_ts=end,
        ),
    }
    rows = []
    evaluated = {}
    for config in filter_configs():
        name = label(config)
        features = filtered_features(indicators, config)
        full = strict.simulate(
            f"{name}_full",
            features,
            funding,
            cfg,
            execution,
            start_ts=start,
            end_ts=end,
        )
        train = strict.simulate(
            f"{name}_train",
            features,
            funding,
            cfg,
            execution,
            start_ts=start,
            end_ts=tune.TRAIN_END,
        )
        validation = strict.simulate(
            f"{name}_validation",
            features,
            funding,
            cfg,
            execution,
            start_ts=tune.VALIDATION_START,
            end_ts=tune.VALIDATION_END,
        )
        retention = full.metrics["return_pct"] / baseline["full"].metrics["return_pct"]
        validation_retention = (
            validation.metrics["return_pct"]
            / baseline["validation"].metrics["return_pct"]
        )
        meets_full_goal = bool(
            full.metrics["win_rate_pct"] > baseline["full"].metrics["win_rate_pct"]
            and full.metrics["max_drawdown_pct"]
            >= baseline["full"].metrics["max_drawdown_pct"] + MDD_IMPROVEMENT_MIN_PP
            and retention >= RETURN_RETENTION_FLOOR
        )
        meets_goal = bool(
            meets_full_goal
            and validation.metrics["win_rate_pct"]
            >= baseline["validation"].metrics["win_rate_pct"]
            and validation.metrics["max_drawdown_pct"]
            >= baseline["validation"].metrics["max_drawdown_pct"]
            + MDD_IMPROVEMENT_MIN_PP
            and validation_retention >= VALIDATION_RETENTION_FLOOR
        )
        score = 0.45 * split_score(train, baseline["train"]) + 0.55 * split_score(
            validation,
            baseline["validation"],
        )
        row = {
            "variant": name,
            **asdict(config),
            "score": score,
            "full_return_pct": full.metrics["return_pct"],
            "full_mdd_pct": full.metrics["max_drawdown_pct"],
            "full_win_rate_pct": full.metrics["win_rate_pct"],
            "full_sharpe": full.metrics["sharpe"],
            "full_trades": full.metrics["trades"],
            "return_retention": retention,
            "train_return_pct": train.metrics["return_pct"],
            "train_mdd_pct": train.metrics["max_drawdown_pct"],
            "train_win_rate_pct": train.metrics["win_rate_pct"],
            "validation_return_pct": validation.metrics["return_pct"],
            "validation_mdd_pct": validation.metrics["max_drawdown_pct"],
            "validation_win_rate_pct": validation.metrics["win_rate_pct"],
            "validation_return_retention": validation_retention,
            "meets_full_goal": meets_full_goal,
            "meets_goal": meets_goal,
        }
        rows.append(row)
        evaluated[name] = {
            "config": config,
            "features": features,
            "full": full,
            "train": train,
            "validation": validation,
            "row": row,
        }
    frame = pd.DataFrame(rows).sort_values(
        ["meets_goal", "score"],
        ascending=[False, False],
    )
    feasible = frame.loc[frame["meets_goal"]]
    selected = (
        None
        if feasible.empty
        else evaluated[
            str(
                feasible.sort_values(
                    ["return_retention", "full_mdd_pct", "score"],
                    ascending=[False, False, False],
                ).iloc[0]["variant"]
            )
        ]
    )
    return frame, selected, baseline, evaluated


def phase_feature_sets(
    m1: pd.DataFrame,
    cfg: base.StrategyConfig,
    filter_config: FilterConfig,
) -> tuple[dict[int, pd.DataFrame], dict[int, pd.DataFrame]]:
    bars30 = {
        phase: base.aggregate_ohlcv(
            m1,
            freq="30min",
            phase_min=phase,
            expected_rows=30,
        )[0]
        for phase in strict.PHASES_30M
    }
    bars1h = {
        phase: base.aggregate_ohlcv(
            m1,
            freq="60min",
            phase_min=phase,
            expected_rows=60,
        )[0]
        for phase in strict.PHASES_1H
    }
    phase30 = {
        phase: filtered_features(
            indicator_frame(frame, bars1h[0], cfg),
            filter_config,
        )
        for phase, frame in bars30.items()
    }
    phase1h = {
        phase: filtered_features(
            indicator_frame(bars30[0], frame, cfg),
            filter_config,
        )
        for phase, frame in bars1h.items()
    }
    return phase30, phase1h


def robustness(
    target: dict[str, Any],
    m1: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: base.StrategyConfig,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    execution = strict.ExecutionConfig()
    features = target["features"]
    full = target["full"]
    holdout = strict.simulate(
        "filter_target_holdout",
        features,
        funding,
        cfg,
        execution,
        start_ts=tune.HOLDOUT_START,
        end_ts=end,
    )
    oos = strict.run_rolling_oos(features, funding, cfg, execution, start, end)
    trade_mc = strict.run_trade_mc(full.trades, 5000)
    mc2 = trade_mc.loc[trade_mc["mc_type"].eq("mc2_shuffle")]
    mc3 = trade_mc.loc[trade_mc["mc_type"].eq("mc3_bootstrap")]
    mc2_p05 = float(mc2["max_drawdown_pct"].quantile(0.05))
    mc2_limit = -1.5 * abs(float(full.metrics["max_drawdown_pct"]))
    daily = full.equity.resample("1D").last().pct_change().dropna()
    significance = strict.probabilistic_sharpe(daily)
    significance["dsr_n1000"] = strict.deflated_sharpe(daily, 1000)
    starts = strict.run_start_sensitivity(
        features,
        funding,
        cfg,
        execution,
        start,
        end,
    )
    cagr_mean = float(starts["cagr_pct"].mean())
    start_cv = float(starts["cagr_pct"].std(ddof=1) / abs(cagr_mean))
    phase30, phase1h = phase_feature_sets(m1, cfg, target["config"])
    phase_starts = [pd.Timestamp(value) for value in starts["start_ts"].iloc[:20]]
    phases = strict.run_phase_gate(
        phase30,
        phase1h,
        funding,
        cfg,
        execution,
        phase_starts,
        end,
    )
    phase_summary = {
        "30m": strict.phase_gate_status(phases, "30m"),
        "1h": strict.phase_gate_status(phases, "1h"),
    }
    summary = {
        "holdout": holdout.metrics,
        "rolling_oos": {
            "windows": int(len(oos)),
            "positive_fraction": float(oos["return_pct"].gt(0.0).mean()),
            "median_return_pct": float(oos["return_pct"].median()),
            "zero_trade_windows": int(oos["trades"].eq(0).sum()),
        },
        "monte_carlo": {
            "status": "pass" if mc2_p05 >= mc2_limit else "fail",
            "mc2_mdd_p05_pct": mc2_p05,
            "mc2_mdd_min_pct": float(mc2["max_drawdown_pct"].min()),
            "mc2_mdd_limit_pct": mc2_limit,
            "mc3_return_p05_pct": float(mc3["return_pct"].quantile(0.05)),
        },
        "significance": significance,
        "start_time": {
            "starts": int(len(starts)),
            "positive_fraction": float(starts["return_pct"].gt(0.0).mean()),
            "cagr_cv": start_cv,
        },
        "phase": phase_summary,
    }
    return summary, {
        "oos": oos,
        "mc": trade_mc,
        "starts": starts,
        "phases": phases,
    }


def serializable(result: strict.StrictResult) -> dict[str, Any]:
    return {"metrics": result.metrics, "slices": result.slices}


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    args = type(
        "Args",
        (),
        {
            "since": "2025-05-30T00:00:00Z",
            "until": "",
            "refresh_cache": False,
            "timeout": 45.0,
        },
    )()
    funding_args = type("FundingArgs", (), {"refresh_data": False, "timeout": 45.0})()
    m1 = base.load_or_fetch_1m(args)
    funding = strict.load_or_fetch_funding(funding_args, m1)
    cfg = dynamic.v21_config()
    b30 = base.aggregate_ohlcv(m1, freq="30min", phase_min=0, expected_rows=30)[0]
    h1 = base.aggregate_ohlcv(m1, freq="60min", phase_min=0, expected_rows=60)[0]
    indicators = indicator_frame(b30, h1, cfg)
    start = strict.ready_start(indicators)
    end = b30.index.max() + pd.Timedelta(minutes=30)

    search, selected, baseline, evaluated = run_search(
        indicators,
        funding,
        cfg,
        start,
        end,
    )
    target = selected
    if target is None:
        near = search.loc[
            search["full_win_rate_pct"].gt(baseline["full"].metrics["win_rate_pct"])
            & search["return_retention"].ge(RETURN_RETENTION_FLOOR)
        ].sort_values(
            ["full_mdd_pct", "score", "return_retention"],
            ascending=[False, False, False],
        )
        if not near.empty:
            target = evaluated[str(near.iloc[0]["variant"])]
    target_payload = None
    robustness_payload = None
    if target is not None:
        robustness_payload, frames = robustness(
            target,
            m1,
            funding,
            cfg,
            start,
            end,
        )
        target["full"].trades.to_csv(TRADES_PATH, index=False)
        frames["oos"].to_csv(OOS_PATH, index=False)
        frames["mc"].to_csv(MC_PATH, index=False)
        frames["starts"].to_csv(START_PATH, index=False)
        frames["phases"].to_csv(PHASE_PATH, index=False)
        target_payload = {
            "accepted": selected is not None,
            "config": asdict(target["config"]),
            "full": serializable(target["full"]),
            "train": serializable(target["train"]),
            "validation": serializable(target["validation"]),
            "row": target["row"],
        }

    summary = {
        "strategy": "HYPE-30M-Keltner-Trend-Breakout-V2.1",
        "study": "RSI14 and MACD(12,26,9) entry filters",
        "run_date": RUN_DATE,
        "objective": {
            "higher_win_rate": True,
            "lower_mdd": True,
            "minimum_mdd_improvement_pp": MDD_IMPROVEMENT_MIN_PP,
            "full_return_retention_floor": RETURN_RETENTION_FLOOR,
            "validation_return_retention_floor": VALIDATION_RETENTION_FLOOR,
        },
        "baseline": {
            split: serializable(result)
            for split, result in baseline.items()
        },
        "search": {
            "variants": int(len(search)),
            "meeting_full_goal": int(search["meets_full_goal"].sum()),
            "meeting_full_and_validation_goal": int(search["meets_goal"].sum()),
        },
        "target": target_payload,
        "robustness": robustness_payload,
        "decision": (
            "filter_candidate_found"
            if selected is not None
            else "keep_v2_1_no_filter_met_constraints"
        ),
        "warning": "Historical data is not true OOS; no filter may be promoted solely from this search.",
    }
    search.to_csv(SEARCH_PATH, index=False)
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print("baseline", baseline["full"].metrics)
    print(
        "search",
        len(search),
        "full goal",
        int(search["meets_full_goal"].sum()),
        "full+validation goal",
        int(search["meets_goal"].sum()),
    )
    if target_payload is None:
        print("target NONE")
    else:
        print("target", target_payload)
        print("robustness", robustness_payload)
    print(search.head(12).to_string(index=False))
    print("summary", SUMMARY_PATH)


if __name__ == "__main__":
    main()
