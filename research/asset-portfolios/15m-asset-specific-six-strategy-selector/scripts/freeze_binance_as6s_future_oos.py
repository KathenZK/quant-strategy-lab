from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
HYBRID = ARTIFACT_DIR / "binance_hybrid_asset_specific_account_2026-07-14.json"
REVEAL = ARTIFACT_DIR / "binance_15m_as6s_reused_holdout_2026-07-14.json"
LEGACY = ARTIFACT_DIR / "binance_legacy_asset_specific_1h_sleeves_2026-07-14.json"
OUTPUT = ARTIFACT_DIR / "binance_as6s_future_oos_freeze_2026-07-14.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    hybrid = json.loads(HYBRID.read_text(encoding="utf-8"))
    reveal = json.loads(REVEAL.read_text(encoding="utf-8"))
    if not all(
        row["current_reused_diagnostic_pass"]
        for row in hybrid["diagnostic_gates"].values()
    ):
        raise RuntimeError("cannot freeze: a current diagnostic route failed")
    selected = set(hybrid["candidate_sleeves"])
    current_configs = {
        f"15m:{symbol}:{mechanism}": row["config"]
        for symbol, mechanisms in reveal["results"].items()
        for mechanism, row in mechanisms.items()
        if f"15m:{symbol}:{mechanism}" in selected
    }
    expected_current = {sleeve for sleeve in selected if sleeve.startswith("15m:")}
    if set(current_configs) != expected_current:
        raise RuntimeError("current config freeze set mismatch")
    exposures = {
        sleeve: hybrid["sleeve_audit"][sleeve]["chosen_exposure"]
        for sleeve in hybrid["candidate_sleeves"]
    }
    scripts = [
        FAMILY_DIR / "scripts/as6s_engine.py",
        FAMILY_DIR / "scripts/audit_legacy_asset_specific_1h_sleeves.py",
        FAMILY_DIR / "scripts/combine_hybrid_asset_specific_account.py",
        ROOT / "research/_shared-kernels/1h-adaptive-regime-search/v1/engine.py",
        ROOT / "research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v2_micro_tune_2026-07-07.json",
    ]
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-15M-Asset-Specific-Six-Strategy-Selector",
        "freeze_id": "BIN-15M-AS6S-FUTURE-OOS-FREEZE-2026-07-14",
        "status": "frozen diagnostic observation / not registered / not promoted / not live-ready",
        "selection_data_end_exclusive": "2026-04-14T09:00:00+00:00",
        "reused_diagnostic_window": [
            "2026-04-14T09:00:00+00:00", "2026-07-14T09:00:00+00:00"
        ],
        "future_final_oos_window": [
            "2026-07-14T09:00:00+00:00", "2026-10-14T09:00:00+00:00"
        ],
        "future_oos_policy": "no parameter, sleeve, exposure, arbitration, or preemption changes before final evaluation",
        "candidate_sleeves": hybrid["candidate_sleeves"],
        "current_15m_configs": current_configs,
        "legacy_1h_mechanism_contract": {
            sleeve: {
                "source": "audit_legacy_asset_specific_1h_sleeves.py frozen implementation",
                "chosen_exposure": exposures[sleeve],
            }
            for sleeve in selected
            if sleeve.startswith("1h:")
        },
        "sleeve_exposures_before_account_scale": exposures,
        "routes": {
            mode: comparison["frozen_params"]
            for mode, comparison in hybrid["comparisons"].items()
        },
        "maximum_effective_exposure": max(
            exposures.values()
        ) * hybrid["comparisons"]["nonpreemptive"]["frozen_params"]["account_scale"],
        "costs": {
            "fee_per_fill": 0.001,
            "base_slippage_per_fill": 0.0004,
            "stress_slippage_per_fill": 0.0008,
            "funding": "actual Binance historical funding",
        },
        "current_diagnostic_gates": hybrid["diagnostic_gates"],
        "input_hashes": {
            str(path.relative_to(ROOT)): digest(path)
            for path in [HYBRID, REVEAL, LEGACY, *scripts]
        },
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"output": str(OUTPUT), "sha256": digest(OUTPUT)}, indent=2))


if __name__ == "__main__":
    main()
