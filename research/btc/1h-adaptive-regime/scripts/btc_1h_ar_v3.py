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
import research_btc_1h_ar_v1_clean_tune as tune  # noqa: E402


ARTIFACT_DIR = ROOT / "research/btc/1h-adaptive-regime/artifacts"
V3_CONFIG_JSON = ARTIFACT_DIR / "btc_1h_ar_v3_config_2026-07-06.json"


KELTNER = clean.KeltnerCleanConfig(
    indicator_window=20,
    band_k=2.0,
    roc_window=24,
    min_adx=40.0,
    min_rvol=1.25,
    max_atr_bps=200.0,
    min_dir_roc_bps=-200.0,
    htf_mode="h4",
    max_aligned_funding_bps=4.0,
    tp_atr=1.5,
    sl_atr=5.0,
    max_hold_bars=240,
    cooldown_bars=0,
    fixed_leverage=2.4,
)

CCI = clean.CCICleanConfig(
    ema_htf=377,
    indicator_window=20,
    threshold_high=125.0,
    max_adx=40.0,
    min_rvol=1.25,
    min_atr_bps=75.0,
    max_atr_bps=600.0,
    max_dist_ema_bps=750.0,
    tp_atr=5.5,
    sl_atr=1.5,
    max_hold_bars=72,
    cooldown_bars=0,
    fixed_leverage=3.5,
)


def v3_configs(engine: Any) -> tuple[Any, Any]:
    return (
        replace(
            clean.keltner_to_base(engine, KELTNER),
            name="BTC_1H_AR_V3_KELTNER",
        ),
        replace(clean.cci_to_base(engine, CCI), name="BTC_1H_AR_V3_CCI"),
    )


def simulate_v3(
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    keltner: Any | None = None,
    cci: Any | None = None,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    base_keltner, base_cci = v3_configs(engine)
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


def config_payload(engine: Any, metrics: dict[str, dict[str, float]]) -> dict[str, Any]:
    return {
        "family": "BTC-1H-Adaptive-Regime",
        "version": "BTC-1H-Adaptive-Regime-V3",
        "status": "diagnostic_micro_tune_observation_not_live_ready",
        "selection_source": "BTC-1H-AR-V2-MICRO-TUNE-2026-07-06",
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "clean_components": {
            "keltner_break": asdict(KELTNER),
            "cci_reversal": asdict(CCI),
        },
        "metrics": metrics,
    }


def main() -> None:
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    trades, _keltner, _cci, priorities = simulate_v3(
        engine, frame, funding_times, funding_cumulative
    )
    payload = config_payload(engine, v1.metrics(engine, trades))
    payload["component_prefit_priority_scores"] = priorities
    payload["data_quality"] = quality
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    V3_CONFIG_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
