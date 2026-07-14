from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_hype_1h_ar_v4_pressure_optimization as pressure  # noqa: E402
import research_hype_1h_adaptive_regime_search as base  # noqa: E402
import research_hype_1h_ar_v1_full_ablation as v1  # noqa: E402
import research_hype_1h_ar_v3_full_ablation as v3ab  # noqa: E402


DATE_TAG = "2026-07-13"
FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_ar_v4_vwap_third_leg_{DATE_TAG}.json"
ALL_CANDIDATES_CSV = (
    ARTIFACT_DIR / f"hype_1h_ar_v4_vwap_third_leg_all_candidates_{DATE_TAG}.csv"
)
FROZEN_TRADES_CSV = (
    ARTIFACT_DIR / f"hype_1h_ar_v4_vwap_third_leg_frozen_trades_{DATE_TAG}.csv"
)

EXPECTED_FIRST_TS = pd.Timestamp("2025-05-30T10:00:00Z")
EXPECTED_LAST_TS = pd.Timestamp("2026-07-02T02:00:00Z")
EXPECTED_FULL_END = pd.Timestamp("2026-07-02T03:00:00Z")
EXPECTED_ROWS = 9_545
SEED = 2026071304
CANDIDATE_COUNT = 2_400
MAX_OVERLAP = 0.40
MAX_BLOCKED_RATIO = 0.70
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_DD = -0.20
MIN_WIN_RATE = 0.80
MIN_VALIDATION_TRADES = 10
MIN_PREFIT_TRADES = 25
MIN_ACCEPTED_VWAP_PREFIT = 8
RESEARCH_WINDOWS = ("train", "validation", "prefit")
REVEAL_WINDOWS = ("reused_holdout", "current_full")
METRIC_KEYS = tuple(base.empty_metrics(1.0))
SCENARIOS = pressure.SCENARIOS


@dataclass(frozen=True, slots=True)
class VWAPCandidate:
    name: str
    config: base.StrategyConfig
    confirm_window: int
    confirm_mode: str
    immediate_control: bool = False


@dataclass(slots=True)
class VWAPDecision:
    trade: base.Trade
    accepted: bool
    reason: str


@dataclass(slots=True)
class JointResult:
    accepted: list[base.Trade]
    vwap_decisions: list[VWAPDecision]


def verify_frozen_data(frame: pd.DataFrame, quality: dict[str, Any]) -> dict[str, Any]:
    first_ts = pd.Timestamp(frame["ts"].iloc[0])
    last_ts = pd.Timestamp(frame["ts"].iloc[-1])
    full_end = last_ts + pd.Timedelta(hours=1)
    if (
        first_ts != EXPECTED_FIRST_TS
        or last_ts != EXPECTED_LAST_TS
        or full_end != EXPECTED_FULL_END
        or len(frame) != EXPECTED_ROWS
    ):
        raise RuntimeError(
            "Frozen data boundary changed: "
            f"first={first_ts}, last={last_ts}, full_end={full_end}, "
            f"rows={len(frame)}"
        )

    raw_files = sorted(base.RAW_ROOT.glob(f"date=*/{base.SYMBOL_FILE}"))
    if len(raw_files) != int(quality["raw_files"]):
        raise RuntimeError(
            "Raw partition count changed during frozen-data verification"
        )
    raw_columns = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "is_closed",
        "source",
    ]
    raw = pd.concat(
        [pd.read_parquet(path, columns=raw_columns) for path in raw_files],
        ignore_index=True,
    )
    raw = (
        raw.rename(columns={"open_time": "ts"})
        .drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    normalized = frame.sort_values("ts").reset_index(drop=True)
    if len(raw) != len(normalized):
        raise RuntimeError(
            f"Raw/normalized row mismatch: raw={len(raw)}, normalized={len(normalized)}"
        )
    ts_mismatch = int(
        np.count_nonzero(
            raw["ts"].astype("int64").to_numpy()
            != normalized["ts"].astype("int64").to_numpy()
        )
    )
    mismatch: dict[str, int] = {"ts": ts_mismatch}
    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
    ):
        mismatch[column] = int(
            np.count_nonzero(
                ~np.isclose(
                    raw[column].to_numpy("float64"),
                    normalized[column].to_numpy("float64"),
                    rtol=0.0,
                    atol=1e-12,
                    equal_nan=True,
                )
            )
        )
    for column in ("trade_count", "is_closed", "source"):
        mismatch[column] = int(
            np.count_nonzero(raw[column].to_numpy() != normalized[column].to_numpy())
        )
    derived_vwap = raw["quote_volume"].to_numpy("float64") / raw["volume"].replace(
        0.0, np.nan
    ).to_numpy("float64")
    mismatch["vwap"] = int(
        np.count_nonzero(
            ~np.isclose(
                derived_vwap,
                normalized["vwap"].to_numpy("float64"),
                rtol=0.0,
                atol=1e-12,
                equal_nan=True,
            )
        )
    )
    if any(mismatch.values()):
        raise RuntimeError(f"Frozen raw/normalized mismatch: {mismatch}")
    return {
        **quality,
        "raw_normalized_mismatch": mismatch,
        "frozen_boundary_asserted": True,
        "refresh_allowed": False,
    }


def confirmation_mask(frame: pd.DataFrame, side: int, mode: str) -> np.ndarray:
    roc = side * frame["roc6_bps"].to_numpy("float64") >= 0.0
    macd = side * frame["macd_hist_8_21_5"].to_numpy("float64") >= 0.0
    di = (
        side * (frame["pdi14"].to_numpy("float64") - frame["mdi14"].to_numpy("float64"))
        >= 0.0
    )
    if mode == "roc6_macd":
        return roc & macd
    if mode == "roc6_di":
        return roc & di
    if mode == "fast_consensus":
        return (roc.astype(np.int8) + macd.astype(np.int8) + di.astype(np.int8)) >= 2
    raise ValueError(f"Unknown confirmation mode: {mode}")


def armed_vwap_signal(
    frame: pd.DataFrame, candidate: VWAPCandidate
) -> tuple[np.ndarray, int, int]:
    cfg = candidate.config
    deviation = frame[f"vwap_dev_atr{cfg.indicator_window}"].to_numpy("float64")
    armed = np.zeros(len(frame), dtype=np.int8)
    armed[base.crossed_down(deviation, cfg.band_k)] = -1
    armed = base.apply_filters(frame, armed, cfg)
    arm_indices = np.flatnonzero(armed)
    if candidate.immediate_control:
        return armed, int(len(arm_indices)), int(len(arm_indices))

    confirmed = np.zeros(len(frame), dtype=np.int8)
    confirm_short = confirmation_mask(frame, -1, candidate.confirm_mode)
    active_arm = -1
    expires_at = -1
    arm_cursor = 0
    for bar_i in range(len(frame)):
        while arm_cursor < len(arm_indices) and int(arm_indices[arm_cursor]) == bar_i:
            active_arm = bar_i
            expires_at = bar_i + candidate.confirm_window
            arm_cursor += 1
        if active_arm < 0:
            continue
        if bar_i > expires_at:
            active_arm = -1
            expires_at = -1
            continue
        if bar_i <= active_arm or not bool(confirm_short[bar_i]):
            continue
        one = np.zeros(len(frame), dtype=np.int8)
        one[bar_i] = -1
        one = base.apply_filters(frame, one, cfg)
        if one[bar_i] != 0:
            confirmed[bar_i] = -1
            active_arm = -1
            expires_at = -1
    return confirmed, int(len(arm_indices)), int(np.count_nonzero(confirmed))


class ThreeLegExactEngine(pressure.ExactJointEngine):
    def __init__(
        self,
        frame: pd.DataFrame,
        funding_times: np.ndarray,
        funding_cumulative: np.ndarray,
    ) -> None:
        super().__init__(frame, funding_times, funding_cumulative)
        self.signal_raw_cache: dict[
            tuple[str, base.StrategyConfig, str], list[base.Trade]
        ] = {}

    def raw_events_from_signal(
        self,
        signal_key: str,
        signal: np.ndarray,
        cfg: base.StrategyConfig,
        scenario: tuple[str, float, float, int],
    ) -> list[base.Trade]:
        scenario_name, fee, slippage, delay = scenario
        scenario_cfg = replace(cfg, entry_delay_bars=delay)
        key = (signal_key, scenario_cfg, scenario_name)
        if key in self.signal_raw_cache:
            return self.signal_raw_cache[key]
        output: list[base.Trade] = []
        original_costs = (base.FEE_PER_FILL, base.SLIPPAGE_PER_FILL)
        try:
            base.FEE_PER_FILL = fee
            base.SLIPPAGE_PER_FILL = slippage
            for signal_i in np.flatnonzero(signal):
                if signal_i + delay >= len(signal):
                    continue
                one_signal = np.zeros(len(signal), dtype=np.int8)
                one_signal[signal_i] = signal[signal_i]
                trades = base.simulate_trades(
                    self.frame,
                    one_signal,
                    scenario_cfg,
                    self.funding_times,
                    self.funding_cumulative,
                )
                if trades:
                    output.append(self._correct_exit_bar_mae(trades[0], fee))
        finally:
            base.FEE_PER_FILL, base.SLIPPAGE_PER_FILL = original_costs
        self.signal_raw_cache[key] = output
        return output

    def exact_three_leg(
        self,
        di_cfg: base.StrategyConfig,
        stoch_cfg: base.StrategyConfig,
        vwap: VWAPCandidate,
        vwap_signal: np.ndarray,
        scenario: tuple[str, float, float, int],
    ) -> JointResult:
        tagged = [(trade, "di_cross", 2) for trade in self.raw_events(di_cfg, scenario)]
        tagged.extend(
            (trade, "stoch_reversal", 1)
            for trade in self.raw_events(stoch_cfg, scenario)
        )
        tagged.extend(
            (trade, "vwap_revert", 0)
            for trade in self.raw_events_from_signal(
                vwap.name, vwap_signal, vwap.config, scenario
            )
        )
        tagged.sort(
            key=lambda item: (
                item[0].entry_i,
                -item[2],
                item[0].signal_i,
                item[0].exit_i,
            )
        )
        cooldowns = {
            "di_cross": di_cfg.cooldown_bars,
            "stoch_reversal": stoch_cfg.cooldown_bars,
            "vwap_revert": vwap.config.cooldown_bars,
        }
        component_cooldown_until = {
            "di_cross": -1,
            "stoch_reversal": -1,
            "vwap_revert": -1,
        }
        global_blocked_until = -1
        accepted: list[base.Trade] = []
        decisions: list[VWAPDecision] = []
        for trade, component, _priority in tagged:
            if trade.entry_i <= global_blocked_until:
                if component == "vwap_revert":
                    decisions.append(
                        VWAPDecision(trade, False, "blocked_global_position")
                    )
                continue
            if trade.entry_i <= component_cooldown_until[component]:
                if component == "vwap_revert":
                    decisions.append(
                        VWAPDecision(trade, False, "blocked_component_cooldown")
                    )
                continue
            accepted.append(trade)
            global_blocked_until = trade.exit_i
            component_cooldown_until[component] = trade.exit_i + cooldowns[component]
            if component == "vwap_revert":
                decisions.append(VWAPDecision(trade, True, "accepted"))
        return JointResult(accepted, decisions)


def candidate_key(candidate: VWAPCandidate) -> tuple[Any, ...]:
    config_values = tuple(
        value for key, value in asdict(candidate.config).items() if key != "name"
    )
    return (
        *config_values,
        candidate.confirm_window,
        candidate.confirm_mode,
        candidate.immediate_control,
    )


def sampled_candidate(
    rng: random.Random,
    index: int,
    template: base.StrategyConfig,
) -> VWAPCandidate:
    exit_kind = rng.choices(("fixed", "trailing"), weights=(3, 1), k=1)[0]
    if exit_kind == "fixed":
        tp_atr = rng.choice((0.75, 1.0, 1.25, 1.5))
        sl_atr = rng.choice((1.5, 2.0, 2.5))
        activation = 1.0
        trail = 1.0
    else:
        tp_atr = 1.0
        sl_atr = rng.choice((1.5, 2.0))
        activation = rng.choice((0.75, 1.0))
        trail = rng.choice((0.75, 1.0))
    confirm_window = rng.choice((3, 6, 12))
    confirm_mode = rng.choice(("roc6_macd", "roc6_di", "fast_consensus"))
    cfg = replace(
        template,
        name=f"HYPE_1H_AR_V4_VWAP3_{index:04d}",
        style="vwap_revert",
        side_mode="short",
        ema_htf=55,
        indicator_window=rng.choice((24, 48, 96, 168)),
        band_k=rng.choice((0.75, 1.0, 1.25, 1.5, 1.75, 2.0)),
        roc_window=6,
        min_adx=0.0,
        max_adx=rng.choice((20.0, 30.0, 40.0)),
        min_rvol=rng.choice((0.0, 1.0)),
        min_atr_bps=rng.choice((100.0, 150.0, 200.0)),
        max_atr_bps=10_000.0,
        min_dir_roc_bps=-10_000.0,
        max_dist_ema_bps=10_000.0,
        htf_mode="none",
        require_macd_turn=False,
        require_body_dir=False,
        max_aligned_funding_bps=10_000.0,
        exit_kind=exit_kind,
        tp_atr=tp_atr,
        sl_atr=sl_atr,
        trail_activation_atr=activation,
        trail_atr=trail,
        max_hold_bars=rng.choice((12, 18, 24)),
        cooldown_bars=rng.choice((0, 6, 12, 24)),
        entry_delay_bars=1,
        sizing_kind="fixed",
        fixed_leverage=1.0,
        risk_fraction=0.01,
        max_leverage=1.0,
    )
    return VWAPCandidate(
        cfg.name,
        cfg,
        confirm_window,
        confirm_mode,
        False,
    )


def immediate_control(template: base.StrategyConfig) -> VWAPCandidate:
    cfg = replace(
        template,
        name="HYPE_1H_AR_V4_VWAP3_IMMEDIATE_CONTROL",
        style="vwap_revert",
        side_mode="short",
        ema_htf=55,
        indicator_window=48,
        band_k=1.25,
        roc_window=6,
        min_adx=0.0,
        max_adx=30.0,
        min_rvol=0.0,
        min_atr_bps=150.0,
        max_atr_bps=10_000.0,
        min_dir_roc_bps=-10_000.0,
        max_dist_ema_bps=10_000.0,
        htf_mode="none",
        require_macd_turn=False,
        require_body_dir=False,
        max_aligned_funding_bps=10_000.0,
        exit_kind="fixed",
        tp_atr=1.0,
        sl_atr=2.0,
        trail_activation_atr=1.0,
        trail_atr=1.0,
        max_hold_bars=18,
        cooldown_bars=6,
        entry_delay_bars=1,
        sizing_kind="fixed",
        fixed_leverage=1.0,
        risk_fraction=0.01,
        max_leverage=1.0,
    )
    return VWAPCandidate(cfg.name, cfg, 0, "immediate", True)


def generate_candidates(template: base.StrategyConfig) -> list[VWAPCandidate]:
    rng = random.Random(SEED)
    seen: set[tuple[Any, ...]] = set()
    output: list[VWAPCandidate] = []
    while len(output) < CANDIDATE_COUNT - 1:
        candidate = sampled_candidate(rng, len(output), template)
        key = candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        output.append(candidate)
    control = immediate_control(template)
    if candidate_key(control) in seen:
        raise RuntimeError("Immediate VWAP control collided with sampled space")
    output.append(control)
    if len(output) != CANDIDATE_COUNT:
        raise RuntimeError("Deterministic VWAP candidate count changed")
    return output


def research_bundle(
    trades: list[base.Trade],
) -> dict[str, dict[str, float]]:
    return {
        "train": base.metrics(trades, v1.TRAIN_START, v1.TRAIN_END),
        "validation": base.metrics(trades, v1.TRAIN_END, v1.PREFIT_END),
        "prefit": base.metrics(trades, v1.TRAIN_START, v1.PREFIT_END),
    }


def simulate_standalone(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: base.StrategyConfig,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    scenario: tuple[str, float, float, int],
) -> list[base.Trade]:
    _name, fee, slippage, delay = scenario
    original_costs = (base.FEE_PER_FILL, base.SLIPPAGE_PER_FILL)
    try:
        base.FEE_PER_FILL = fee
        base.SLIPPAGE_PER_FILL = slippage
        return base.simulate_trades(
            frame,
            signal,
            replace(cfg, entry_delay_bars=delay),
            funding_times,
            funding_cumulative,
        )
    finally:
        base.FEE_PER_FILL, base.SLIPPAGE_PER_FILL = original_costs


def entry_overlap(
    candidate: list[base.Trade],
    reference: list[base.Trade],
    tolerance: int = 3,
) -> float:
    candidate_prefit = [
        trade for trade in candidate if v1.TRAIN_START <= trade.entry_ts < v1.PREFIT_END
    ]
    reference_entries = [
        trade.entry_i
        for trade in reference
        if v1.TRAIN_START <= trade.entry_ts < v1.PREFIT_END
    ]
    if not candidate_prefit:
        return 0.0
    return float(
        sum(
            any(
                abs(trade.entry_i - reference_entry) <= tolerance
                for reference_entry in reference_entries
            )
            for trade in candidate_prefit
        )
        / len(candidate_prefit)
    )


def standalone_gate_parts(
    bundle: dict[str, dict[str, float]], overlap: float
) -> dict[str, bool]:
    parts: dict[str, bool] = {}
    for window in RESEARCH_WINDOWS:
        metric = bundle[window]
        parts[f"{window}_return_positive"] = metric["total_return"] > 0.0
        parts[f"{window}_win_rate"] = metric["win_rate"] >= MIN_WIN_RATE
        parts[f"{window}_drawdown"] = metric["max_dd"] > MAX_DD
    parts["validation_trades"] = bundle["validation"]["trades"] >= MIN_VALIDATION_TRADES
    parts["prefit_trades"] = bundle["prefit"]["trades"] >= MIN_PREFIT_TRADES
    parts["overlap_v4_pm3h"] = overlap < MAX_OVERLAP
    return parts


def decisions_in_window(
    decisions: list[VWAPDecision],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[VWAPDecision]:
    return [
        decision for decision in decisions if start <= decision.trade.entry_ts < end
    ]


def vwap_diagnostics(
    decisions: list[VWAPDecision],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, float]:
    selected = decisions_in_window(decisions, start, end)
    accepted = [decision.trade for decision in selected if decision.accepted]
    blocked = len(selected) - len(accepted)
    denominator = len(selected)
    positive_logs = [
        math.log1p(trade.equity_ret) for trade in accepted if trade.equity_ret > 0.0
    ]
    positive_sum = float(sum(positive_logs))
    max_positive = float(max(positive_logs, default=0.0))
    positive_share = max_positive / positive_sum if positive_sum > 0.0 else math.inf
    return {
        "events": float(denominator),
        "accepted": float(len(accepted)),
        "blocked": float(blocked),
        "blocked_global": float(
            sum(decision.reason == "blocked_global_position" for decision in selected)
        ),
        "blocked_cooldown": float(
            sum(
                decision.reason == "blocked_component_cooldown" for decision in selected
            )
        ),
        "blocked_ratio": float(blocked / denominator) if denominator else 1.0,
        "positive_log_sum": positive_sum,
        "max_positive_log": max_positive,
        "max_positive_log_share": float(positive_share),
    }


def relative_metric_values(
    candidate: dict[str, float], baseline: dict[str, float]
) -> dict[str, float]:
    return {
        "log_final_equity_delta": float(
            math.log(max(candidate["final_equity"], 1e-12))
            - math.log(max(baseline["final_equity"], 1e-12))
        ),
        "win_rate_delta": float(candidate["win_rate"] - baseline["win_rate"]),
        "max_dd_delta": float(candidate["max_dd"] - baseline["max_dd"]),
    }


def ensemble_gate_and_score(
    bundles: dict[str, dict[str, dict[str, float]]],
    baselines: dict[str, dict[str, dict[str, float]]],
    base_prefit_diag: dict[str, float],
) -> tuple[dict[str, bool], float]:
    parts: dict[str, bool] = {}
    relative_values: list[dict[str, float]] = []
    for scenario_name, bundle in bundles.items():
        for window in RESEARCH_WINDOWS:
            relative = relative_metric_values(
                bundle[window], baselines[scenario_name][window]
            )
            relative_values.append(relative)
            equity_delta = relative["log_final_equity_delta"]
            parts[f"{scenario_name}_{window}_equity"] = (
                equity_delta > 0.0 if window == "prefit" else equity_delta >= 0.0
            )
            parts[f"{scenario_name}_{window}_win_rate"] = (
                relative["win_rate_delta"] >= 0.0
            )
            parts[f"{scenario_name}_{window}_drawdown"] = (
                relative["max_dd_delta"] >= -0.01
            )
    parts["base_prefit_accepted_vwap"] = (
        base_prefit_diag["accepted"] >= MIN_ACCEPTED_VWAP_PREFIT
    )
    parts["base_prefit_blocked_ratio"] = (
        base_prefit_diag["blocked_ratio"] < MAX_BLOCKED_RATIO
    )
    parts["base_prefit_positive_concentration"] = (
        base_prefit_diag["positive_log_sum"] > 0.0
        and base_prefit_diag["max_positive_log_share"] <= MAX_SINGLE_POSITIVE_SHARE
    )
    score = float(
        sum(item["log_final_equity_delta"] for item in relative_values)
        + 0.50 * sum(item["win_rate_delta"] for item in relative_values)
        + 2.00 * sum(item["max_dd_delta"] for item in relative_values)
        - 0.20 * base_prefit_diag["blocked_ratio"]
        - 0.10 * base_prefit_diag["max_positive_log_share"]
    )
    return parts, score


def blank_exact_columns() -> dict[str, Any]:
    columns: dict[str, Any] = {}
    for scenario_name, _fee, _slippage, _delay in SCENARIOS:
        for window in (*RESEARCH_WINDOWS, *REVEAL_WINDOWS):
            for metric_key in METRIC_KEYS:
                columns[f"{scenario_name}_{window}_{metric_key}"] = None
            for delta_key in (
                "log_final_equity_delta",
                "win_rate_delta",
                "max_dd_delta",
            ):
                columns[f"{scenario_name}_{window}_{delta_key}"] = None
        for window in RESEARCH_WINDOWS:
            for gate_name in ("equity", "win_rate", "drawdown"):
                columns[f"gate_ensemble_{scenario_name}_{window}_{gate_name}"] = None
    for key in (
        "events",
        "accepted",
        "blocked",
        "blocked_global",
        "blocked_cooldown",
        "blocked_ratio",
        "positive_log_sum",
        "max_positive_log",
        "max_positive_log_share",
    ):
        columns[f"base_prefit_vwap_{key}"] = None
    for gate_name in (
        "base_prefit_accepted_vwap",
        "base_prefit_blocked_ratio",
        "base_prefit_positive_concentration",
    ):
        columns[f"gate_ensemble_{gate_name}"] = None
    return columns


def add_bundle_columns(
    row: dict[str, Any],
    scenario_name: str,
    bundle: dict[str, dict[str, float]],
    baseline: dict[str, dict[str, float]],
    windows: tuple[str, ...],
) -> None:
    for window in windows:
        for key, value in bundle[window].items():
            row[f"{scenario_name}_{window}_{key}"] = value
        relative = relative_metric_values(bundle[window], baseline[window])
        for key, value in relative.items():
            row[f"{scenario_name}_{window}_{key}"] = value


def recent_slices(
    trades: list[base.Trade], full_end: pd.Timestamp
) -> list[dict[str, Any]]:
    definitions = (
        ("1d", 1),
        ("7d", 7),
        ("1m", 30),
        ("3m", 90),
        ("6m", 180),
        ("1y", 365),
    )
    return [
        {
            "window": label,
            "start": max(v1.TRAIN_START, full_end - pd.Timedelta(days=days)),
            "end": full_end,
            **base.metrics(
                trades,
                max(v1.TRAIN_START, full_end - pd.Timedelta(days=days)),
                full_end,
            ),
        }
        for label, days in definitions
    ]


def trade_row(
    role: str,
    candidate: str,
    scenario: str,
    trade: base.Trade,
) -> dict[str, Any]:
    return {
        "role": role,
        "candidate": candidate,
        "scenario": scenario,
        **asdict(trade),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = base.load_data()
    quality = verify_frozen_data(frame, quality)
    frame = base.add_features(frame, funding)
    frame = v3ab.ensure_extra_macd_features(frame)
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    if full_end != EXPECTED_FULL_END:
        raise RuntimeError(f"Unexpected full_end after features: {full_end}")
    funding_times, funding_cumulative = base.funding_prefix(funding)
    engine = ThreeLegExactEngine(frame, funding_times, funding_cumulative)
    v4_di, v4_stoch = pressure.v4_engine_configs()

    print(
        f"frozen data rows={len(frame)} full_end={full_end.isoformat()}",
        flush=True,
    )
    baseline_trades: dict[str, list[base.Trade]] = {}
    baseline_bundles: dict[str, dict[str, dict[str, float]]] = {}
    for scenario in SCENARIOS:
        scenario_name = scenario[0]
        trades = engine.exact_joint(v4_di, v4_stoch, scenario)
        baseline_trades[scenario_name] = trades
        baseline_bundles[scenario_name] = pressure.window_bundle(trades, full_end)
    print(
        "cached V4 DI/Stoch raw events for all scenarios",
        flush=True,
    )

    candidates = generate_candidates(v4_stoch)
    if len(candidates) > 2_500:
        raise RuntimeError("Candidate cap exceeded")
    print(
        f"generated candidates={len(candidates)} seed={SEED}",
        flush=True,
    )

    rows: list[dict[str, Any]] = []
    candidates_by_name: dict[str, VWAPCandidate] = {}
    exact_results: dict[str, dict[str, JointResult]] = {}
    strict_count = 0
    exact_gate_count = 0
    immediate_strict_count = 0
    for index, candidate in enumerate(candidates, start=1):
        candidates_by_name[candidate.name] = candidate
        signal, arm_count, confirmed_count = armed_vwap_signal(frame, candidate)
        standalone = simulate_standalone(
            frame,
            signal,
            candidate.config,
            funding_times,
            funding_cumulative,
            SCENARIOS[0],
        )
        standalone_metrics = research_bundle(standalone)
        overlap = entry_overlap(standalone, baseline_trades["base_k1"], tolerance=3)
        standalone_parts = standalone_gate_parts(standalone_metrics, overlap)
        standalone_pass = all(standalone_parts.values())
        row: dict[str, Any] = {
            "candidate": candidate.name,
            "config": json.dumps(asdict(candidate.config), sort_keys=True),
            "confirm_window": candidate.confirm_window,
            "confirm_mode": candidate.confirm_mode,
            "immediate_control": candidate.immediate_control,
            "arm_count": arm_count,
            "confirmed_count": confirmed_count,
            "prefit_entry_overlap_v4_pm3h": overlap,
            "standalone_strict_gate": standalone_pass,
            "exact_evaluated": False,
            "ensemble_strict_gate": False,
            "selection_score": None,
            "frozen_role": "",
            **blank_exact_columns(),
        }
        for window, metric in standalone_metrics.items():
            for key, value in metric.items():
                row[f"standalone_base_{window}_{key}"] = value
        for key, value in standalone_parts.items():
            row[f"gate_standalone_{key}"] = value

        if standalone_pass:
            strict_count += 1
            immediate_strict_count += int(candidate.immediate_control)
            scenario_results: dict[str, JointResult] = {}
            scenario_bundles: dict[str, dict[str, dict[str, float]]] = {}
            for scenario in SCENARIOS:
                scenario_name = scenario[0]
                result = engine.exact_three_leg(
                    v4_di,
                    v4_stoch,
                    candidate,
                    signal,
                    scenario,
                )
                scenario_results[scenario_name] = result
                scenario_bundles[scenario_name] = research_bundle(result.accepted)
                add_bundle_columns(
                    row,
                    scenario_name,
                    scenario_bundles[scenario_name],
                    baseline_bundles[scenario_name],
                    RESEARCH_WINDOWS,
                )
            base_diag = vwap_diagnostics(
                scenario_results["base_k1"].vwap_decisions,
                v1.TRAIN_START,
                v1.PREFIT_END,
            )
            ensemble_parts, score = ensemble_gate_and_score(
                scenario_bundles, baseline_bundles, base_diag
            )
            ensemble_pass = (
                all(ensemble_parts.values()) and not candidate.immediate_control
            )
            exact_gate_count += int(ensemble_pass)
            row.update(
                {
                    "exact_evaluated": True,
                    "ensemble_strict_gate": ensemble_pass,
                    "selection_score": score,
                    **{
                        f"base_prefit_vwap_{key}": value
                        for key, value in base_diag.items()
                    },
                }
            )
            for key, value in ensemble_parts.items():
                row[f"gate_ensemble_{key}"] = value
            exact_results[candidate.name] = scenario_results
        rows.append(row)
        if index % 100 == 0 or index == len(candidates):
            print(
                f"search {index}/{len(candidates)} "
                f"standalone_strict={strict_count} "
                f"ensemble_strict={exact_gate_count}",
                flush=True,
            )

    exact_rows = [row for row in rows if row["exact_evaluated"]]
    exact_rows.sort(
        key=lambda row: (
            float(row["selection_score"]),
            row["candidate"],
        ),
        reverse=True,
    )
    winner_rows = [row for row in exact_rows if row["ensemble_strict_gate"]]
    primary = winner_rows[0] if winner_rows else None
    controls = [
        row
        for row in exact_rows
        if primary is None or row["candidate"] != primary["candidate"]
    ][:2]
    frozen: list[tuple[str, dict[str, Any]]] = []
    if primary is not None:
        frozen.append(("primary", primary))
    frozen.extend(
        (f"control_{index}", row) for index, row in enumerate(controls, start=1)
    )
    print(
        f"frozen primary={int(primary is not None)} controls={len(controls)}",
        flush=True,
    )

    frozen_payload: list[dict[str, Any]] = []
    frozen_trade_rows: list[dict[str, Any]] = []
    for scenario_name, trades in baseline_trades.items():
        frozen_trade_rows.extend(
            trade_row(
                "v4_baseline",
                "HYPE_1H_AR_V4_EXACT",
                scenario_name,
                trade,
            )
            for trade in trades
        )
    for role, row in frozen:
        candidate_name = str(row["candidate"])
        candidate = candidates_by_name[candidate_name]
        row["frozen_role"] = role
        reveal: dict[str, Any] = {
            "role": role,
            "candidate": candidate_name,
            "config": asdict(candidate.config),
            "confirm_window": candidate.confirm_window,
            "confirm_mode": candidate.confirm_mode,
            "immediate_control": candidate.immediate_control,
            "standalone_strict_gate": row["standalone_strict_gate"],
            "ensemble_strict_gate": row["ensemble_strict_gate"],
            "selection_score": row["selection_score"],
            "scenarios": {},
        }
        for scenario in SCENARIOS:
            scenario_name = scenario[0]
            result = exact_results[candidate_name][scenario_name]
            full_bundle = pressure.window_bundle(result.accepted, full_end)
            add_bundle_columns(
                row,
                scenario_name,
                full_bundle,
                baseline_bundles[scenario_name],
                REVEAL_WINDOWS,
            )
            reveal["scenarios"][scenario_name] = {
                "metrics": full_bundle,
                "vwap_diagnostics": {
                    window: vwap_diagnostics(
                        result.vwap_decisions,
                        (
                            v1.PREFIT_END
                            if window == "reused_holdout"
                            else v1.TRAIN_START
                        ),
                        full_end,
                    )
                    for window in REVEAL_WINDOWS
                },
            }
            frozen_trade_rows.extend(
                trade_row(
                    role,
                    candidate_name,
                    scenario_name,
                    trade,
                )
                for trade in result.accepted
            )
        frozen_payload.append(reveal)

    audit_subject = (
        str(primary["candidate"]) if primary is not None else "HYPE_1H_AR_V4_EXACT"
    )
    audit_trades = (
        exact_results[audit_subject]["base_k1"].accepted
        if primary is not None
        else baseline_trades["base_k1"]
    )
    slices = recent_slices(audit_trades, full_end)

    rows_frame = pd.DataFrame(rows)
    rows_frame = rows_frame.sort_values(
        [
            "ensemble_strict_gate",
            "standalone_strict_gate",
            "selection_score",
            "candidate",
        ],
        ascending=[False, False, False, True],
        na_position="last",
    )
    rows_frame.to_csv(ALL_CANDIDATES_CSV, index=False)
    pd.DataFrame(frozen_trade_rows).to_csv(FROZEN_TRADES_CSV, index=False)

    conclusion = (
        "prefit_strict_gate_hit_frozen_for_reused_holdout_audit_not_promoted"
        if primary is not None
        else "zero_prefit_strict_gate_hit_v4_baseline_slices_only"
    )
    payload = {
        "family": "HYPE-1H-Adaptive-Regime",
        "base_version": "HYPE-1H-Adaptive-Regime-V4",
        "observation": "VWAP short-only third-leg arm-confirm-expire search",
        "status": "diagnostic_only_not_registered_not_promoted_not_live_ready",
        "date": DATE_TAG,
        "quality": quality,
        "data_range": {
            "first_bar": EXPECTED_FIRST_TS,
            "last_bar": EXPECTED_LAST_TS,
            "full_end": full_end,
            "rows": len(frame),
            "frozen": True,
            "refresh": "forbidden",
        },
        "protocol": {
            "seed": SEED,
            "candidate_count": len(candidates),
            "candidate_cap": 2_500,
            "side": "short_only",
            "leverage": 1.0,
            "signal": (
                "VWAP cross arm after filters; confirmation begins on the "
                "first later closed bar and expires after 3/6/12 bars; "
                "filters are rechecked on confirmation"
            ),
            "confirm_modes": [
                "roc6_macd",
                "roc6_di",
                "fast_consensus",
            ],
            "arbitration": (
                "global single position; DI priority 2, Stoch priority 1, "
                "VWAP priority 0; each component cooldown changes only "
                "after its trade is accepted"
            ),
            "selection_data": "train_validation_prefit_only",
            "reveal_data": (
                "reused_holdout_and_current_full_only_after_identity_freeze"
            ),
            "recent_slices": "audit_only_dataset_end_anchored",
            "cost_scenarios": [
                {
                    "name": name,
                    "fee_per_fill": fee,
                    "slippage_per_fill": slippage,
                    "entry_delay_bars": delay,
                }
                for name, fee, slippage, delay in SCENARIOS
            ],
            "standalone_gate": {
                "train_validation_prefit_total_return": ">0",
                "train_validation_prefit_win_rate": ">=0.80",
                "validation_trades": ">=10",
                "prefit_trades": ">=25",
                "train_validation_prefit_max_dd": ">-0.20",
                "prefit_entry_overlap_v4_pm3h": "<0.40",
            },
            "ensemble_gate": {
                "all_scenarios_all_research_windows_log_equity_delta": ">=0",
                "all_scenarios_prefit_log_equity_delta": ">0",
                "all_scenarios_all_research_windows_win_delta": ">=0",
                "all_scenarios_all_research_windows_dd_delta": ">=-0.01",
                "base_prefit_accepted_vwap": ">=8",
                "base_prefit_blocked_ratio": "<0.70",
                "base_prefit_max_positive_log_share": "<=0.40",
            },
            "immediate_control": (
                "included in candidate rows; never eligible for primary"
            ),
        },
        "v4_baselines": baseline_bundles,
        "counts": {
            "generated_candidates": len(candidates),
            "armed_candidates": len(candidates) - 1,
            "immediate_controls": 1,
            "standalone_strict_gate": strict_count,
            "immediate_control_standalone_strict_gate": (immediate_strict_count),
            "three_scenario_exact_evaluated": len(exact_rows),
            "ensemble_strict_gate": len(winner_rows),
            "frozen_primary": int(primary is not None),
            "frozen_controls": len(controls),
        },
        "frozen_reveal": frozen_payload,
        "recent_slices_subject": audit_subject,
        "recent_slices": slices,
        "result_conclusion": conclusion,
        "artifacts": {
            "summary_json": str(SUMMARY_JSON.relative_to(ROOT)),
            "all_candidates_csv": str(ALL_CANDIDATES_CSV.relative_to(ROOT)),
            "frozen_trades_csv": str(FROZEN_TRADES_CSV.relative_to(ROOT)),
        },
    }
    SUMMARY_JSON.write_text(
        json.dumps(
            base.json_safe(payload),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            base.json_safe(
                {
                    "result_conclusion": conclusion,
                    "counts": payload["counts"],
                    "recent_slices_subject": audit_subject,
                }
            ),
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
