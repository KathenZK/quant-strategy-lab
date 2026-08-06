from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from dstc_data import load_assets
from dstc_engine import Config, run_backtest


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SPLITS = {
    "BTC": {
        "development": (None, "2023-12-31 23:59:59+00:00"),
        "validation": ("2024-01-01 00:00:00+00:00", "2025-06-30 23:59:59+00:00"),
    },
    "ETH": {
        "development": (None, "2023-12-31 23:59:59+00:00"),
        "validation": ("2024-01-01 00:00:00+00:00", "2025-06-30 23:59:59+00:00"),
    },
    "HYPE": {
        "development": (None, "2025-10-31 23:59:59+00:00"),
        "validation": ("2025-11-01 00:00:00+00:00", "2026-02-28 23:59:59+00:00"),
    },
}
CONFIGS = (
    Config(
        name="daily_cross1_probe",
        invalidation="cross1",
        entry_style="immediate_probe",
        max_layers=1,
        max_retry_per_layer=0,
        max_hold_days=0,
    ),
    Config(
        name="dual_state_probe",
        invalidation="band_structure",
        entry_style="restart2",
        max_layers=1,
        max_retry_per_layer=1,
        max_hold_days=0,
    ),
    Config(
        name="dual_state_static_full",
        invalidation="band_structure",
        entry_style="restart2",
        layer_risk=0.01,
        max_layers=1,
        max_retry_per_layer=1,
        max_hold_days=0,
    ),
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not pd.notna(value):
        return None
    return value


def main() -> None:
    assets = load_assets()
    results: list[dict[str, Any]] = []
    retained = None
    for asset, data in assets.items():
        for config in CONFIGS:
            for split, (start, end) in SPLITS[asset].items():
                run = run_backtest(data, config, start=start, end=end)
                results.append(
                    {
                        "asset": asset,
                        "split": split,
                        "config": config.name,
                        **run.metrics,
                    }
                )
                print(
                    asset,
                    split,
                    config.name,
                    f"annual={run.metrics['annual_equity_multiple']:.3f}x",
                    f"dd={run.metrics['max_drawdown_pct']:.2f}%",
                    f"pf={run.metrics['profit_factor']:.2f}",
                    f"campaigns={run.metrics['campaigns']}",
                    flush=True,
                )
                if asset == "HYPE" and split == "validation" and config.name == "dual_state_probe":
                    retained = run

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(results)
    frame.to_csv(ARTIFACT_DIR / "binance_mtf_dstc_baselines_2026-08-04.csv", index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-MTF-Dual-State-Trend-Campaign",
        "status": "baseline diagnostic; historical final audit not revealed",
        "selection_use": "development and mechanism-validation baseline attribution only",
        "configs": [asdict(config) for config in CONFIGS],
        "splits": SPLITS,
        "results": results,
    }
    (ARTIFACT_DIR / "binance_mtf_dstc_baselines_2026-08-04.json").write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if retained is not None:
        retained.actions.to_csv(
            ARTIFACT_DIR / "binance_mtf_dstc_hype_validation_actions_2026-08-04.csv",
            index=False,
        )
        retained.lots.to_csv(
            ARTIFACT_DIR / "binance_mtf_dstc_hype_validation_lots_2026-08-04.csv",
            index=False,
        )
        retained.campaigns.to_csv(
            ARTIFACT_DIR / "binance_mtf_dstc_hype_validation_campaigns_2026-08-04.csv",
            index=False,
        )


if __name__ == "__main__":
    main()
