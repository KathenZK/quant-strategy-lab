"""Audit V7 max-hold extension and PEHC entry contribution variants."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR / "specs/hype-1d-ma7-abt-v7-issue-optimization-omnibus-contract-2026-08-11.md"
)
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v7_state_control_variants_2026-08-11.json"
SHORT_SLOPE_SCRIPT = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v7_short_slope_exit_variants.py"


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
class StateVariant:
    name: str
    group: str
    description: str
    mode: str = "native"
    short_slope_exit_lookback: int = 1
    close_above_ma_buffer_atr: float | None = None
    maxhold_extra_days: int = 0
    maxhold_min_distance_atr: float = 0.0
    pehc_entry_enabled: bool = True

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


def variants() -> list[StateVariant]:
    return [
        StateVariant("CTRL_EXACT_V7", "control", "exact registered V7"),
        StateVariant(
            "SHORT_MAXHOLD_EXTEND_5",
            "maxhold_extension",
            "extend short max_hold by up to 5d if close<MA7 and MA7 still falling",
            mode="custom_maxhold",
            maxhold_extra_days=5,
        ),
        StateVariant(
            "SHORT_MAXHOLD_EXTEND_10",
            "maxhold_extension",
            "extend short max_hold by up to 10d if close<MA7 and MA7 still falling",
            mode="custom_maxhold",
            maxhold_extra_days=10,
        ),
        StateVariant(
            "SHORT_MAXHOLD_EXTEND_5_D0P25",
            "maxhold_extension",
            "extend short max_hold by up to 5d if favorable and at least 0.25ATR below MA7",
            mode="custom_maxhold",
            maxhold_extra_days=5,
            maxhold_min_distance_atr=0.25,
        ),
        StateVariant(
            "SHORT_MAXHOLD_EXTEND_10_D0P25",
            "maxhold_extension",
            "extend short max_hold by up to 10d if favorable and at least 0.25ATR below MA7",
            mode="custom_maxhold",
            maxhold_extra_days=10,
            maxhold_min_distance_atr=0.25,
        ),
        StateVariant(
            "PEHC_ENTRY_DISABLED",
            "pehc_contribution",
            "disable PEHC entries while preserving native entries and OAPP",
            pehc_entry_enabled=False,
        ),
    ]


def maxhold_signal_exit(variant: StateVariant) -> Any:
    def signal_exit(config: Any, book: Any, features: Any, index: int, bars_held: int) -> str:
        left = index - int(config.exit_confirm_days) + 1
        if left >= 0:
            crossed = True
            for offset in range(left, index + 1):
                ma = features.ma7[offset]
                atr = features.atr7[offset]
                if (
                    not np.isfinite(ma)
                    or not np.isfinite(atr)
                    or int(config.side) * (book.close[offset] - ma)
                    >= -float(config.exit_buffer_atr) * atr
                ):
                    crossed = False
                    break
            if crossed:
                return "ma7_hysteresis_exit"
        if int(config.slope_exit_lookback) > 0:
            prior = index - int(config.slope_exit_lookback)
            if (
                prior >= 0
                and np.isfinite(features.ma7[index])
                and np.isfinite(features.ma7[prior])
                and int(config.side) * (features.ma7[index] - features.ma7[prior]) <= 0.0
            ):
                return "ma7_slope_exit"
        if int(config.max_hold_days) > 0 and bars_held >= int(config.max_hold_days):
            if int(config.side) < 0 and bars_held < int(config.max_hold_days) + variant.maxhold_extra_days:
                prior = index - 1
                ma = features.ma7[index]
                prev_ma = features.ma7[prior] if prior >= 0 else math.nan
                atr = features.atr7[index]
                close = book.close[index]
                favorable = (
                    np.isfinite(ma)
                    and np.isfinite(prev_ma)
                    and np.isfinite(atr)
                    and np.isfinite(close)
                    and atr > 0.0
                    and close < ma
                    and ma < prev_ma
                    and (ma - close) / atr >= variant.maxhold_min_distance_atr
                )
                if favorable:
                    return ""
            return "max_hold"
        return ""

    return signal_exit


def run_with_variant(ss: ModuleType, base: ModuleType, transition: ModuleType, full_ablation: ModuleType, context: Any, variant: StateVariant, **kwargs: Any) -> dict[str, Any]:
    original_custom = ss.custom_signal_exit
    original_fixed = transition.fixed_v6_config
    try:
        if variant.mode == "custom_maxhold":
            ss.custom_signal_exit = maxhold_signal_exit
            run_variant = replace(variant, mode="slope_up_close_above_ma")
        else:
            run_variant = variant
        if not variant.pehc_entry_enabled:
            def fixed_without_entry() -> Any:
                return replace(original_fixed(), entry_enabled=False)

            transition.fixed_v6_config = fixed_without_entry
        return ss.run_once(
            base,
            transition,
            full_ablation,
            context,
            run_variant,
            **kwargs,
        )
    finally:
        ss.custom_signal_exit = original_custom
        transition.fixed_v6_config = original_fixed


def run_stress(ss: ModuleType, base: ModuleType, transition: ModuleType, full_ablation: ModuleType, context: Any, variant: StateVariant) -> dict[str, Any]:
    stress = {}
    for key, window, slippage, include_funding, signal_lag in [
        ("base_full", ss.FULL, ss.BASE_SLIPPAGE, True, 0),
        ("slippage_8bps", ss.FULL, ss.STRESS_SLIPPAGE, True, 0),
        ("funding_off", ss.FULL, ss.BASE_SLIPPAGE, False, 0),
        ("lag_1d", ss.FULL, ss.BASE_SLIPPAGE, True, 1),
    ]:
        stress[key] = run_with_variant(
            ss,
            base,
            transition,
            full_ablation,
            context,
            variant,
            window=window,
            slippage=slippage,
            include_funding=include_funding,
            signal_lag=signal_lag,
            retain=False,
        )
    for block_index, window in enumerate(ss.BLOCKS):
        stress[f"block_{block_index:02d}"] = run_with_variant(
            ss,
            base,
            transition,
            full_ablation,
            context,
            variant,
            window=window,
            slippage=ss.BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
    terminal = ss.FULL[1]
    for label, span in ss.RECENT_SLICES.items():
        left = max(0, terminal - span)
        stress[f"recent_{label}"] = run_with_variant(
            ss,
            base,
            transition,
            full_ablation,
            context,
            variant,
            window=(left, terminal),
            slippage=ss.BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=False,
        )
    return stress


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute")

    ss = load_module(SHORT_SLOPE_SCRIPT, "state_short_slope")
    base = ss.load_module(ss.BASE_ABLATION_PATH, "state_base")
    transition = ss.load_module(base.TRANSITION_PATH, "state_transition")
    full_ablation = ss.load_module(base.FULL_ABLATION_PATH, "state_full_ablation")
    v7_audit = ss.load_module(base.V7_AUDIT_PATH, "state_v7_context")
    base2 = v7_audit.load_module(v7_audit.BASE_2X_AUDIT_PATH, "state_base2")
    _, _, _, _, context, _ = v7_audit.load_runtime(base2)

    varlist = variants()
    control_variant = varlist[0]
    control = run_with_variant(
        ss,
        base,
        transition,
        full_ablation,
        context,
        control_variant,
        window=ss.FULL,
        slippage=ss.BASE_SLIPPAGE,
        include_funding=True,
        signal_lag=0,
        retain=True,
    )
    if not (
        math.isclose(control["net_return_pct"], ss.EXPECTED_V7_RETURN, abs_tol=0.08)
        and math.isclose(control["chronological_1h_mdd_pct"], ss.EXPECTED_V7_1H_MDD, abs_tol=0.03)
        and int(control["closed_trades"]) == ss.EXPECTED_V7_TRADES
    ):
        raise RuntimeError(f"V7 anchor drift: {control}")

    rows = {
        control_variant.name: {
            "variant": control_variant.canonical(),
            "base_full": control,
            "base_verdict": {
                "ret_delta_vs_v7_pp": 0.0,
                "mdd_delta_vs_v7_pp": 0.0,
                "trade_delta_vs_v7": 0,
                "full_dual_better": False,
                "interesting": False,
            },
        }
    }
    selected = []
    for variant in varlist[1:]:
        print(f"[base] {variant.name}")
        row = run_with_variant(
            ss,
            base,
            transition,
            full_ablation,
            context,
            variant,
            window=ss.FULL,
            slippage=ss.BASE_SLIPPAGE,
            include_funding=True,
            signal_lag=0,
            retain=True,
        )
        verdict = ss.base_verdict(row, control)
        rows[variant.name] = {
            "variant": variant.canonical(),
            "base_full": row,
            "base_verdict": verdict,
        }
        if verdict["interesting"] or verdict["full_dual_better"]:
            selected.append(variant)
    if not selected:
        selected = varlist[1:]

    stressed = {}
    for variant in selected:
        print(f"[stress] {variant.name}")
        stress = run_stress(ss, base, transition, full_ablation, context, variant)
        stressed[variant.name] = {
            "variant": variant.canonical(),
            "stress": stress,
            "verdict": ss.stress_verdict(stress, control),
        }

    payload = {
        "schema": "hype-1d-ma7-abt-v7-state-control-variants-v1",
        "status": "COMPLETED_POST_REVEAL_DIAGNOSTIC",
        "research_state": "V7 unchanged / maxhold and PEHC contribution diagnostic only / not promoted / not live-ready",
        "contract": str(CONTRACT_PATH.relative_to(FAMILY_DIR)),
        "control": rows[control_variant.name],
        "results": rows,
        "stressed": stressed,
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "audit_script_sha256": sha256(Path(__file__).resolve()),
            "short_slope_runner_sha256": sha256(SHORT_SLOPE_SCRIPT),
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
                "base": [
                    {
                        "name": name,
                        "ret": round(row["base_full"]["net_return_pct"], 2),
                        "mdd": round(row["base_full"]["chronological_1h_mdd_pct"], 2),
                        "trades": row["base_full"]["closed_trades"],
                        "decision": stressed.get(name, {}).get("verdict", {}).get("decision"),
                    }
                    for name, row in rows.items()
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
