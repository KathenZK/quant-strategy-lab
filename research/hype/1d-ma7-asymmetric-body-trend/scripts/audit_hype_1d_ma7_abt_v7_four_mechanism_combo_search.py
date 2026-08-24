"""Post-reveal combo search for four V7 repair mechanisms."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-abt-v7-four-mechanism-combo-search-contract-2026-08-11.md"
)
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v7_four_mechanism_combo_search_2026-08-11.json"

BASE_ABLATION_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v7_four_mechanism_ablation.py"
FULL = (0, 432)
BLOCKS = tuple((left, left + 54) for left in range(0, 432, 54))
RECENT_SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
TOP_N_STRESS = 20

EXPECTED_V7_RETURN = 711.035936775286
EXPECTED_V7_1H_MDD = -18.395542229660567
EXPECTED_V7_TRADES = 20


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if hasattr(value, "item"):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_locked(payload: dict[str, Any]) -> str:
    sidecar = Path(f"{OUTPUT_PATH}.sha256")
    if OUTPUT_PATH.exists() or sidecar.exists():
        raise RuntimeError(f"locked artifact exists: {OUTPUT_PATH.name}")
    encoded = (
        json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    with OUTPUT_PATH.open("xb") as handle:
        handle.write(encoded)
    with sidecar.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {OUTPUT_PATH.name}\n")
    return digest


@dataclass(frozen=True, slots=True)
class PendingOption:
    code: str
    episode_enabled: bool
    episode_max_age_days: int = 3
    maturity_mode: str = "NONE"
    anti_chase_cap_atr: float = math.inf


@dataclass(frozen=True, slots=True)
class RsiOption:
    code: str
    threshold: float
    days: int


@dataclass(frozen=True, slots=True)
class CooldownOption:
    code: str
    mode: str


@dataclass(frozen=True, slots=True)
class OverboughtOption:
    code: str
    enabled: bool
    threshold: float = 70.0
    min_days: int = 3
    lookback: int = 5
    distance_atr: float = 0.10


@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    pending: PendingOption
    rsi: RsiOption
    cooldown: CooldownOption
    overbought: OverboughtOption
    arm: Any


class FlexibleOverboughtEntrySignal:
    """Same interface as the base ablation signal wrapper, with frozen params."""

    option = OverboughtOption("O0", False)

    def __init__(self, base: Any, *, enabled: bool, rsi6: Any) -> None:
        self.base = base
        self.enabled = bool(enabled)
        self.rsi6 = rsi6
        self.events = base.events

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base, name)

    @staticmethod
    def _finite(*values: float) -> bool:
        return all(math.isfinite(float(value)) for value in values)

    def _overbought_short(self, book: Any, features: Any, index: int) -> bool:
        option = self.option
        if not self.enabled or not option.enabled or index < option.lookback:
            return False
        close = float(book.close[index])
        prior_close = float(book.close[index - 1])
        ma7 = float(features.ma7[index])
        atr7 = float(features.atr7[index])
        if not self._finite(close, prior_close, ma7, atr7) or atr7 <= 0.0:
            return False
        start = index - option.lookback + 1
        recent = [float(self.rsi6[offset]) for offset in range(start, index + 1)]
        rsi_hits = sum(math.isfinite(value) and value >= option.threshold for value in recent)
        distance = (ma7 - close) / atr7
        if not (rsi_hits >= option.min_days and distance > option.distance_atr and close < prior_close):
            return False
        self.base._record(
            "overbought_exhaustion_short",
            index,
            -1,
            rsi_threshold=option.threshold,
            rsi_hit_days=rsi_hits,
            lookback=option.lookback,
            distance_atr=distance,
            close=close,
            ma7=ma7,
        )
        return True

    def __call__(self, config: Any, book: Any, features: Any, index: int) -> bool:
        result = bool(self.base(config, book, features, index))
        if result or int(config.side) > 0:
            return result
        if self.base.cached_index != index:
            self.base._evaluate(book, features, index)
        if self.base.cached_decisions[-1]:
            return True
        if self._overbought_short(book, features, index):
            self.base.cached_decisions[-1] = True
            self.base.cached_sources[-1] = "overbought_exhaustion"
            return True
        return False


def pending_options() -> list[PendingOption]:
    return [
        PendingOption("P0", False),
        PendingOption("P_BOTH_D3_A075", True, 3, "BOTH", 0.75),
        PendingOption("P_BOTH_D3_A100", True, 3, "BOTH", 1.00),
        PendingOption("P_BOTH_D3_A150", True, 3, "BOTH", 1.50),
        PendingOption("P_SLOPE_D3_A100", True, 3, "SLOPE", 1.00),
        PendingOption("P_BUFFER_D3_A100", True, 3, "BUFFER", 1.00),
    ]


def rsi_options() -> list[RsiOption]:
    return [
        RsiOption("R20x2", 20.0, 2),
        RsiOption("R20x1", 20.0, 1),
        RsiOption("R25x1", 25.0, 1),
        RsiOption("R25x2", 25.0, 2),
        RsiOption("R30x1", 30.0, 1),
    ]


def cooldown_options() -> list[CooldownOption]:
    return [CooldownOption("CG", "GLOBAL_BASE"), CooldownOption("CD", "DIRECTIONAL")]


def overbought_options() -> list[OverboughtOption]:
    return [
        OverboughtOption("O0", False),
        OverboughtOption("O70_3of5_D010", True, 70.0, 3, 5, 0.10),
        OverboughtOption("O70_4of6_D025", True, 70.0, 4, 6, 0.25),
        OverboughtOption("O75_3of5_D010", True, 75.0, 3, 5, 0.10),
    ]


def make_candidates(base: ModuleType, transition: ModuleType) -> list[Candidate]:
    rows: list[Candidate] = []
    cfg = transition.TransitionRepairConfig
    for pending in pending_options():
        for rsi in rsi_options():
            for cooldown in cooldown_options():
                for overbought in overbought_options():
                    name = "__".join([pending.code, rsi.code, cooldown.code, overbought.code])
                    transition_config = cfg(
                        name,
                        cooldown_mode=cooldown.mode,
                        episode_enabled=pending.episode_enabled,
                        episode_max_age_days=pending.episode_max_age_days,
                        maturity_mode=pending.maturity_mode,
                        anti_chase_cap_atr=pending.anti_chase_cap_atr,
                    )
                    arm = base.Arm(
                        name=name,
                        group="combo_search",
                        description="post-reveal fixed combo search",
                        transition_config=transition_config,
                        short_rsi_threshold=rsi.threshold,
                        short_rsi_days=rsi.days,
                        overbought_exhaustion_short=overbought.enabled,
                    )
                    rows.append(Candidate(name, pending, rsi, cooldown, overbought, arm))
    if len(rows) != 240:
        raise RuntimeError("combo search grid cardinality drift")
    if len({row.name for row in rows}) != len(rows):
        raise RuntimeError("duplicate candidate names")
    return rows


def run_once(base: ModuleType, transition: ModuleType, full_ablation: ModuleType, context: Any, candidate: Candidate, *, window: tuple[int, int], slippage: float, include_funding: bool, signal_lag: int, retain: bool) -> dict[str, Any]:
    FlexibleOverboughtEntrySignal.option = candidate.overbought
    base.OverboughtEntrySignal = FlexibleOverboughtEntrySignal
    result = base.run_raw(
        transition,
        context,
        candidate.arm,
        window=window,
        slippage=slippage,
        include_funding=include_funding,
        signal_lag=signal_lag,
        retain=retain,
    )
    return base.normalize(
        full_ablation,
        context,
        result,
        days=window[1] - window[0],
        slippage=slippage,
        include_funding=include_funding,
    ) | {
        "activation_counts": dict(result.activation_counts),
        "signal_event_count": len(result.signal_events),
        "cooldown_event_count": len(result.cooldown_events),
        "handoff_event_count": len(result.handoff_events),
    }


def candidate_payload(candidate: Candidate) -> dict[str, Any]:
    return {
        "name": candidate.name,
        "pending": asdict(candidate.pending),
        "rsi": asdict(candidate.rsi),
        "cooldown": asdict(candidate.cooldown),
        "overbought": asdict(candidate.overbought),
    }


def base_verdict(row: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    ret_delta = row["net_return_pct"] - control["net_return_pct"]
    mdd_delta = row["chronological_1h_mdd_pct"] - control["chronological_1h_mdd_pct"]
    return {
        "ret_delta_vs_v7_pp": ret_delta,
        "mdd_delta_vs_v7_pp": mdd_delta,
        "trade_delta_vs_v7": row["closed_trades"] - control["closed_trades"],
        "full_dual_better": ret_delta > 0.0 and mdd_delta >= -1e-8,
    }


def stress_verdict(stress: dict[str, dict[str, Any]], control: dict[str, Any]) -> dict[str, Any]:
    base_row = stress["base_full"]
    ret_delta = base_row["net_return_pct"] - control["net_return_pct"]
    mdd_delta = base_row["chronological_1h_mdd_pct"] - control["chronological_1h_mdd_pct"]
    blocks = [row for key, row in stress.items() if key.startswith("block_")]
    block_positive = sum(row["net_return_pct"] > 0.0 for row in blocks)
    search_hit = (
        ret_delta > 0.0
        and mdd_delta >= -1e-8
        and stress["slippage_8bps"]["net_return_pct"] > 0.0
        and stress["lag_1d"]["net_return_pct"] > 0.0
        and block_positive == len(blocks)
    )
    if search_hit:
        decision = "POST_REVEAL_CANDIDATE_ONLY"
    elif base_row["closed_trades"] > control["closed_trades"] + 5:
        decision = "FAIL / noise-releasing"
    elif ret_delta > 0.0 and mdd_delta < 0.0:
        decision = "FAIL / higher-return-higher-risk"
    else:
        decision = "FAIL"
    return {
        "ret_delta_vs_v7_pp": ret_delta,
        "mdd_delta_vs_v7_pp": mdd_delta,
        "trade_delta_vs_v7": base_row["closed_trades"] - control["closed_trades"],
        "block_positive_count": block_positive,
        "block_count": len(blocks),
        "decision": decision,
    }


def run_stress(base: ModuleType, transition: ModuleType, full_ablation: ModuleType, context: Any, candidate: Candidate) -> dict[str, Any]:
    stress: dict[str, dict[str, Any]] = {}
    for key, window, slippage, include_funding, signal_lag in [
        ("base_full", FULL, BASE_SLIPPAGE, True, 0),
        ("slippage_8bps", FULL, STRESS_SLIPPAGE, True, 0),
        ("funding_off", FULL, BASE_SLIPPAGE, False, 0),
        ("lag_1d", FULL, BASE_SLIPPAGE, True, 1),
    ]:
        stress[key] = run_once(
            base,
            transition,
            full_ablation,
            context,
            candidate,
            window=window,
            slippage=slippage,
            include_funding=include_funding,
            signal_lag=signal_lag,
            retain=False,
        )
    for block_index, window in enumerate(BLOCKS):
        stress[f"block_{block_index:02d}"] = run_once(
            base,
            transition,
            full_ablation,
            context,
            candidate,
            window=window,
            slippage=BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
    recent: dict[str, dict[str, Any]] = {}
    for label, days in RECENT_SLICES.items():
        window = (max(0, FULL[1] - days), FULL[1])
        recent[label] = run_once(
            base,
            transition,
            full_ablation,
            context,
            candidate,
            window=window,
            slippage=BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
    return {"stress": stress, "recent": recent}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute the frozen combo search")

    base = load_module(BASE_ABLATION_PATH, "v7_combo_base_ablation")
    v7_audit = load_module(base.V7_AUDIT_PATH, "v7_combo_context")
    base2 = v7_audit.load_module(v7_audit.BASE_2X_AUDIT_PATH, "v7_combo_base2")
    _, _, _, _, context, _ = v7_audit.load_runtime(base2)
    transition = load_module(base.TRANSITION_PATH, "v7_combo_transition")
    full_ablation = load_module(base.FULL_ABLATION_PATH, "v7_combo_full_ablation")

    candidates = make_candidates(base, transition)
    base_rows: dict[str, dict[str, Any]] = {}
    for index, candidate in enumerate(candidates, 1):
        print(f"[base {index:03d}/{len(candidates)}] {candidate.name}")
        base_rows[candidate.name] = run_once(
            base,
            transition,
            full_ablation,
            context,
            candidate,
            window=FULL,
            slippage=BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
    control_name = "P0__R20x2__CG__O0"
    control = base_rows[control_name]
    if not (
        math.isclose(control["net_return_pct"], EXPECTED_V7_RETURN, abs_tol=0.05)
        and math.isclose(control["chronological_1h_mdd_pct"], EXPECTED_V7_1H_MDD, abs_tol=0.02)
        and int(control["closed_trades"]) == EXPECTED_V7_TRADES
    ):
        raise RuntimeError(f"V7 anchor drift: {control}")
    base_ranking = []
    for candidate in candidates:
        verdict = base_verdict(base_rows[candidate.name], control)
        base_ranking.append(
            {
                "candidate": candidate_payload(candidate),
                "base_full": base_rows[candidate.name],
                "base_verdict": verdict,
            }
        )
    base_ranking.sort(
        key=lambda row: (
            row["base_verdict"]["full_dual_better"],
            row["base_full"]["net_return_pct"],
            row["base_verdict"]["mdd_delta_vs_v7_pp"],
        ),
        reverse=True,
    )
    selected_names: list[str] = []
    for row in base_ranking:
        if row["base_verdict"]["full_dual_better"]:
            selected_names.append(row["candidate"]["name"])
    for row in base_ranking:
        name = row["candidate"]["name"]
        if name != control_name and name not in selected_names:
            selected_names.append(name)
        if len([name for name in selected_names if name != control_name]) >= TOP_N_STRESS:
            break
    if control_name not in selected_names:
        selected_names.insert(0, control_name)
    selected = {candidate.name: candidate for candidate in candidates if candidate.name in selected_names}
    stressed: dict[str, Any] = {}
    for index, name in enumerate(selected_names, 1):
        print(f"[stress {index:02d}/{len(selected_names)}] {name}")
        candidate = selected[name]
        row = run_stress(base, transition, full_ablation, context, candidate)
        row["candidate"] = candidate_payload(candidate)
        row["verdict"] = (
            {"decision": "CONTROL"}
            if name == control_name
            else stress_verdict(row["stress"], control)
        )
        stressed[name] = row
    payload = {
        "schema": "hype-1d-ma7-abt-v7-four-mechanism-combo-search-v1",
        "status": "COMPLETED_POST_REVEAL_SEARCH",
        "research_state": "V7 unchanged / exploratory diagnostic only / not promoted / not live-ready",
        "contract": str(CONTRACT_PATH.relative_to(FAMILY_DIR)),
        "control": control_name,
        "grid_size": len(candidates),
        "stress_evaluated": selected_names,
        "market": "Binance USD-M HYPEUSDT perpetual",
        "timeframes": {"decision": "1d UTC", "risk_replay": "1h"},
        "data_range": {
            "start": str(context.book.ts[FULL[0]]),
            "end": str(context.book.ts[FULL[1] - 1]),
            "terminal_ts": str(context.book.terminal_ts),
            "daily_bars": FULL[1] - FULL[0],
        },
        "cost_model": {
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": "actual Binance funding events when include_funding=true",
        },
        "base_ranking": base_ranking,
        "stressed": stressed,
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "audit_script_sha256": sha256(Path(__file__).resolve()),
            "base_ablation_script_sha256": sha256(BASE_ABLATION_PATH),
        },
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "exact_v7_changed": False,
        "clean_oos_claim": False,
    }
    digest = write_locked(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "artifact": str(OUTPUT_PATH),
                "artifact_sha256": digest,
                "top5_base": [
                    {
                        "name": row["candidate"]["name"],
                        "ret": row["base_full"]["net_return_pct"],
                        "mdd": row["base_full"]["chronological_1h_mdd_pct"],
                        "trades": row["base_full"]["closed_trades"],
                        "dual": row["base_verdict"]["full_dual_better"],
                    }
                    for row in base_ranking[:5]
                ],
                "stress_decisions": {
                    name: row["verdict"]["decision"] for name, row in stressed.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
