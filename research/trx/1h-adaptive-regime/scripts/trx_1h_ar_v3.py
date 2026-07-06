from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import trx_1h_ar_v1 as v1  # noqa: E402
import trx_1h_ar_v2 as v2  # noqa: E402


ARTIFACT_DIR = ROOT / "research/trx/1h-adaptive-regime/artifacts"
V3_CONFIG_JSON = ARTIFACT_DIR / "trx_1h_ar_v3_config_2026-07-06.json"
TUNE_JSON = ARTIFACT_DIR / "trx_1h_ar_v2_ablation_guided_tune_2026-07-06.json"


@dataclass(frozen=True, slots=True)
class MACDV3Config:
    ema_htf: int = 89
    roc_window: int = 6
    macd_fast: int = 34
    macd_slow: int = 89
    macd_signal: int = 13
    min_adx: float = 20.0
    max_adx: float = 24.0
    min_rvol: float = 0.0
    max_atr_bps: float = 150.0
    min_dir_roc_bps: float = -100.0
    max_dist_ema_bps: float = 10_000.0
    htf_mode: str = "h12"
    require_macd_turn: bool = False
    tp_atr: float = 2.0
    sl_atr: float = 5.0
    max_hold_bars: int = 120
    cooldown_bars: int = 3
    entry_delay_bars: int = 1
    fixed_leverage: float = 5.0


@dataclass(frozen=True, slots=True)
class StochV3Config:
    side_mode: str = "both"
    ema_htf: int = 233
    indicator_window: int = 21
    threshold_low: float = 25.0
    threshold_high: float = 90.0
    roc_window: int = 3
    max_adx: float = 24.0
    min_rvol: float = 1.0
    min_dir_roc_bps: float = -300.0
    require_body_dir: bool = True
    sl_atr: float = 6.0
    trail_activation_atr: float = 3.0
    trail_atr: float = 2.0
    max_hold_bars: int = 120
    cooldown_bars: int = 6
    entry_delay_bars: int = 2
    fixed_leverage: float = 3.5


def load_context() -> tuple[Any, Any, Any, dict[str, Any]]:
    return v2.load_context()


def macd_to_v2(config: MACDV3Config) -> v2.MACDV2Config:
    return v2.MACDV2Config(**asdict(config))


def stoch_to_v2(config: StochV3Config) -> v2.StochV2Config:
    return v2.StochV2Config(**asdict(config))


def simulate_v3(
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    macd: MACDV3Config | None = None,
    stoch: StochV3Config | None = None,
    frozen_priorities: tuple[float, float] | None = None,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    macd = macd or MACDV3Config()
    stoch = stoch or StochV3Config()
    return v2.simulate_v2(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        macd=macd_to_v2(macd),
        stoch=stoch_to_v2(stoch),
        frozen_priorities=frozen_priorities,
    )


def assert_close(observed: float, expected: float, label: str) -> None:
    if math.isfinite(expected) and abs(observed - expected) > 1e-12:
        raise RuntimeError(f"V3 metric drift at {label}: {observed} != {expected}")


def main() -> None:
    engine, frame, funding, quality = load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    trades, _macd_trades, _stoch_trades, priorities = simulate_v3(
        engine,
        frame,
        funding_times,
        funding_cumulative,
    )
    metrics = v1.metrics(engine, trades)
    standard_slices = v1.standard_slices(engine, trades)
    if TUNE_JSON.exists():
        tune = json.loads(TUNE_JSON.read_text(encoding="utf-8"))
        expected = tune["selected"]["metrics"]
        for window in ("train", "validation", "prefit", "reused_holdout", "current_full"):
            for metric in ("annual_multiple", "total_return", "max_dd", "win_rate", "trades"):
                assert_close(
                    float(metrics[window][metric]),
                    float(expected[window][metric]),
                    f"{window}.{metric}",
                )
    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "version": "TRX-1H-Adaptive-Regime-V3",
        "identity": "registered_v2_ablation_guided_tuned_version",
        "status": "registered_diagnostic_tuned_version_no_go_not_live_ready",
        "registered_at": "2026-07-06",
        "source_version": "TRX-1H-Adaptive-Regime-V2",
        "selection_policy": {
            "source": "V2 ablation-guided tune",
            "search_uses": "train_validation_prefit_only",
            "reused_holdout": "read_only_after_freeze_not_used_for_selection",
            "recent_slices": "read_only_after_freeze_not_used_for_selection",
        },
        "macd_flip": asdict(MACDV3Config()),
        "stoch_reversal": asdict(StochV3Config()),
        "component_prefit_priority_scores": priorities,
        "metrics": metrics,
        "standard_slices": standard_slices,
        "data_quality": quality,
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    V3_CONFIG_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
