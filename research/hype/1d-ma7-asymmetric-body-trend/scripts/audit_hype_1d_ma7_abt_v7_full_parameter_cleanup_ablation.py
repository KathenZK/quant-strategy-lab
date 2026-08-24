"""Run full parameter ablation on registered V7 for V7.1 cleanup."""

from __future__ import annotations

import argparse
from dataclasses import replace
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
    FAMILY_DIR / "specs/hype-1d-ma7-abt-v7-1-parameter-cleanup-contract-2026-08-11.md"
)
V6_ABLATION_PATH = SCRIPT_DIR / "audit_hype_1d_ma7_abt_v6_full_parameter_ablation.py"
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v7_full_parameter_cleanup_ablation_2026-08-11.json"

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


def rename_variant(v6: ModuleType, variant: Any) -> Any:
    if variant.name == "exact_v6":
        return replace(variant, name="exact_v7", change="registered V7")
    if variant.name.startswith("short_cooldown_"):
        # These explicit OAT rows were originally relative to V6 cooldown=5.
        return replace(
            variant,
            name=f"v7_{variant.name}",
            change=variant.change.replace("5", "3", 1),
        )
    return variant


def run(force: bool = False) -> dict[str, Any]:
    v6 = load_module(V6_ABLATION_PATH, "v7_cleanup_v6_ablation")
    engine = v6.load_module(v6.ENGINE_PATH, "v7_cleanup_engine")
    adapter = v6.load_module(v6.ADAPTER_PATH, "v7_cleanup_adapter")
    context = adapter.load_context()
    context = replace(context, short_config=replace(context.short_config, cooldown_days=3))
    variants = [rename_variant(v6, row) for row in v6.build_variants(engine, context)]

    candidates: dict[str, Any] = {}
    control_base: dict[str, Any] | None = None
    for index, variant in enumerate(variants, 1):
        print(f"[{index:03d}/{len(variants)}] {variant.name}")
        stress: dict[str, dict[str, Any]] = {}
        base_full, retained = v6.run_variant(
            engine,
            context,
            variant,
            window=v6.FULL,
            slippage=v6.BASE_SLIPPAGE,
            signal_lag=0,
            include_funding=True,
            retain=True,
        )
        stress["base_full"] = base_full
        stress["slippage_8bps"], _ = v6.run_variant(
            engine,
            context,
            variant,
            window=v6.FULL,
            slippage=v6.STRESS_SLIPPAGE,
            signal_lag=0,
            include_funding=True,
            retain=False,
        )
        stress["funding_off"], _ = v6.run_variant(
            engine,
            context,
            variant,
            window=v6.FULL,
            slippage=v6.BASE_SLIPPAGE,
            signal_lag=0,
            include_funding=False,
            retain=False,
        )
        stress["lag_1d"], _ = v6.run_variant(
            engine,
            context,
            variant,
            window=v6.FULL,
            slippage=v6.BASE_SLIPPAGE,
            signal_lag=1,
            include_funding=True,
            retain=False,
        )
        for block_index, window in enumerate(v6.BLOCKS):
            stress[f"block_{block_index:02d}"], _ = v6.run_variant(
                engine,
                context,
                variant,
                window=window,
                slippage=v6.BASE_SLIPPAGE,
                signal_lag=0,
                include_funding=True,
                retain=False,
            )
        for label, days in v6.RECENT_SLICES.items():
            left = max(0, v6.FULL[1] - days)
            stress[f"recent_{label}"], _ = v6.run_variant(
                engine,
                context,
                variant,
                window=(left, v6.FULL[1]),
                slippage=v6.BASE_SLIPPAGE,
                signal_lag=0,
                include_funding=True,
                retain=False,
            )
        if variant.name == "exact_v7":
            control_base = base_full
            if not math.isclose(base_full["net_return_pct"], EXPECTED_V7_RETURN, abs_tol=0.05):
                raise RuntimeError("V7 return anchor drift")
            if not math.isclose(base_full["chronological_1h_mdd_pct"], EXPECTED_V7_1H_MDD, abs_tol=0.02):
                raise RuntimeError("V7 chronological MDD anchor drift")
            if base_full["closed_trades"] != EXPECTED_V7_TRADES:
                raise RuntimeError("V7 trade-count anchor drift")
        control_for_verdict = control_base if control_base is not None else base_full
        row = {
            "name": variant.name,
            "group": variant.group,
            "change": variant.change,
            "config": {
                "long_config": v6.variant_config(variant.long_config),
                "short_config": v6.variant_config(variant.short_config),
                "oapp_config": v6.variant_config(variant.oapp_config),
                "pehc_config": v6.variant_config(variant.pehc_config),
            },
            "stress": stress,
            "verdict": v6.verdict(control_for_verdict, stress),
            "retained_trade_count": len(retained.raw.trades) if retained is not None else None,
            "source_sha256": base_full["source_sha256"],
        }
        candidates[variant.name] = row
    if control_base is None:
        raise RuntimeError("missing V7 control")

    ranking = sorted(
        (
            {
                "name": name,
                "group": row["group"],
                "change": row["change"],
                "net_return_pct": row["stress"]["base_full"]["net_return_pct"],
                "chronological_1h_mdd_pct": row["stress"]["base_full"]["chronological_1h_mdd_pct"],
                "closed_trades": row["stress"]["base_full"]["closed_trades"],
                **row["verdict"],
            }
            for name, row in candidates.items()
        ),
        key=lambda row: (row["full_dual_better"], row["net_return_pct"]),
        reverse=True,
    )
    inactive_cleanup = {
        "remove_from_v7_1_spec": [
            "long_config.pullback_lookback",
            "long_config.pullback_touch_atr",
            "long_config.breakout_lookback",
            "short_config.pullback_lookback",
            "short_config.pullback_touch_atr",
            "short_config.breakout_lookback",
            "oapp_config.entry.lookback",
            "oapp_config.entry.scope",
            "oapp_config.entry.threshold",
            "oapp_config.short_exit.activation_atr",
            "oapp_config.short_exit.giveback",
            "oapp_config.short_exit.confirm_days",
            "pehc_config.allowed_origin_indices",
            "pehc_config.blocked_origin_indices",
        ],
        "keep_even_if_not_triggered_in_sample": [
            "short_config.hard_stop_atr",
            "long_config.trail_atr",
            "short_config.trail_atr",
            "short_config.max_hold_days",
            "cooldown_days",
            "entry/exit buffers",
            "PEHC enabled/entry_enabled/expiry/execution",
        ],
        "reason": (
            "Cleanup removes dormant/schema fields under reclaim/off modes only; risk guards "
            "and future-behavior parameters stay explicit."
        ),
    }
    payload = {
        "schema": "hype-1d-ma7-abt-v7-full-parameter-cleanup-ablation-v1",
        "status": "COMPLETED_POST_REVEAL_PARAMETER_CLEANUP",
        "research_state": "V7.1 cleanup registration evidence / not promoted / not live-ready",
        "contract": str(CONTRACT_PATH.relative_to(FAMILY_DIR)),
        "control": candidates["exact_v7"],
        "variant_count": len(candidates),
        "candidates": candidates,
        "ranking": ranking,
        "summary_by_group": v6.summarize_by_group(ranking),
        "inactive_cleanup": inactive_cleanup,
        "v7_1_path_equivalence": {
            "same_metrics_as_v7": True,
            "same_trade_path_as_v7": True,
            "changes": "spec cleanup only; no engine or behavior change",
        },
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "audit_script_sha256": sha256(Path(__file__).resolve()),
            "v6_full_ablation_runner_sha256": sha256(V6_ABLATION_PATH),
        },
        "registered": True,
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
                "variant_count": len(candidates),
                "control_return": control_base["net_return_pct"],
                "control_mdd": control_base["chronological_1h_mdd_pct"],
                "top5": [
                    {
                        "name": row["name"],
                        "ret": row["net_return_pct"],
                        "mdd": row["chronological_1h_mdd_pct"],
                        "dual": row["full_dual_better"],
                    }
                    for row in ranking[:5]
                ],
                "cleanup_fields": inactive_cleanup["remove_from_v7_1_spec"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        raise SystemExit("use --run to execute")
    run()


if __name__ == "__main__":
    main()
