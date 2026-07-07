from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import btc_1h_ar_v1 as v1  # noqa: E402
import btc_1h_ar_v1_clean as clean  # noqa: E402
import btc_1h_ar_v3 as v3  # noqa: E402
import research_btc_1h_ar_v1_clean_tune as tune  # noqa: E402


ARTIFACT_DIR = ROOT / "research/btc/1h-adaptive-regime/artifacts"
V4_CONFIG_JSON = ARTIFACT_DIR / "btc_1h_ar_v4_config_2026-07-07.json"

KELTNER_NECESSARY_PARAMS = (
    "indicator_window",
    "band_k",
    "min_adx",
    "min_rvol",
    "htf_mode",
    "tp_atr",
    "sl_atr",
    "fixed_leverage",
)
CCI_NECESSARY_PARAMS = (
    "ema_htf",
    "indicator_window",
    "threshold_high",
    "max_adx",
    "min_rvol",
    "min_atr_bps",
    "max_dist_ema_bps",
    "tp_atr",
    "sl_atr",
    "max_hold_bars",
    "fixed_leverage",
)

KELTNER_REMOVED_PARAMS = {
    "max_atr_bps": 10000.0,
    "min_dir_roc_bps": -10000.0,
    "roc_window": "inert_after_min_dir_roc_removed",
    "max_aligned_funding_bps": 10000.0,
    "max_hold_bars": 100000,
    "cooldown_bars": 0,
}
CCI_REMOVED_PARAMS = {
    "max_atr_bps": 10000.0,
    "cooldown_bars": 0,
}

KELTNER = replace(
    v3.KELTNER,
    max_atr_bps=10000.0,
    min_dir_roc_bps=-10000.0,
    max_aligned_funding_bps=10000.0,
    max_hold_bars=100000,
    cooldown_bars=0,
)
CCI = replace(v3.CCI, max_atr_bps=10000.0, cooldown_bars=0)


def necessary_dict(config: Any, names: tuple[str, ...]) -> dict[str, Any]:
    return {name: getattr(config, name) for name in names}


def v4_configs(engine: Any) -> tuple[Any, Any]:
    return (
        replace(
            clean.keltner_to_base(engine, KELTNER),
            name="BTC_1H_AR_V4_KELTNER",
        ),
        replace(clean.cci_to_base(engine, CCI), name="BTC_1H_AR_V4_CCI"),
    )


def simulate_v4(
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    keltner: Any | None = None,
    cci: Any | None = None,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    base_keltner, base_cci = v4_configs(engine)
    keltner = keltner or base_keltner
    cci = cci or base_cci
    keltner_trades = v1.simulate_component(
        engine, frame, funding_times, funding_cumulative, keltner
    )
    cci_trades = v1.simulate_component(
        engine, frame, funding_times, funding_cumulative, cci
    )
    priorities = (
        tune.leg_score(tune.prefit_metrics(engine, keltner_trades)),
        tune.leg_score(tune.prefit_metrics(engine, cci_trades)),
    )
    merged = engine.merge_trade_sets(
        keltner_trades,
        cci_trades,
        priorities[0],
        priorities[1],
    )
    return merged, keltner_trades, cci_trades, priorities


def config_payload(
    engine: Any,
    metrics: dict[str, dict[str, float]],
    *,
    v3_trade_path_equal: bool,
) -> dict[str, Any]:
    return {
        "family": "BTC-1H-Adaptive-Regime",
        "version": "BTC-1H-Adaptive-Regime-V4",
        "status": "registered_minimal_equivalent_observation_not_live_ready",
        "source": "BTC-1H-Adaptive-Regime-V3 minimal equivalent surface",
        "trade_path_equal_to_v3": v3_trade_path_equal,
        "clean_slots_before": 27,
        "necessary_slots": {
            "keltner": list(KELTNER_NECESSARY_PARAMS),
            "cci": list(CCI_NECESSARY_PARAMS),
            "total": len(KELTNER_NECESSARY_PARAMS) + len(CCI_NECESSARY_PARAMS),
        },
        "removed_slots": {
            "keltner": KELTNER_REMOVED_PARAMS,
            "cci": CCI_REMOVED_PARAMS,
            "total": 8,
        },
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "necessary_components": {
            "keltner_break": necessary_dict(KELTNER, KELTNER_NECESSARY_PARAMS),
            "cci_reversal": necessary_dict(CCI, CCI_NECESSARY_PARAMS),
        },
        "engine_components_with_neutralized_removed_slots": {
            "keltner_break": asdict(KELTNER),
            "cci_reversal": asdict(CCI),
        },
        "metrics": metrics,
    }


def main() -> None:
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    v4_trades, _keltner, _cci, priorities = simulate_v4(
        engine, frame, funding_times, funding_cumulative
    )
    v3_trades, *_ = v3.simulate_v3(engine, frame, funding_times, funding_cumulative)
    v3_trade_path_equal = v1.trade_signature(v4_trades) == v1.trade_signature(v3_trades)
    if not v3_trade_path_equal:
        raise RuntimeError("V4 minimal surface is not trade-path equivalent to V3")

    payload = config_payload(
        engine,
        v1.metrics(engine, v4_trades),
        v3_trade_path_equal=v3_trade_path_equal,
    )
    payload["component_prefit_priority_scores"] = priorities
    payload["data_quality"] = quality
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    V4_CONFIG_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
