from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from dstc_data import load_assets
from dstc_engine import Config, run_backtest
from run_dstc_baselines import SPLITS


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CENTER = Config(name="center")
VARIANTS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("center", {}),
    ("ma5", {"ma_length": 5}),
    ("ma10", {"ma_length": 10}),
    ("ma14", {"ma_length": 14}),
    ("persistence1", {"slope_days": 1}),
    ("persistence3", {"slope_days": 3}),
    ("band0", {"candidate_band_atr": 0.0}),
    ("invalidation_slope_structure", {"invalidation": "slope_structure"}),
    ("invalidation_structure_only", {"invalidation": "structure_only"}),
    ("wrong05", {"wrong_side_atr": 0.5}),
    ("wrong1_day1", {"invalid_days": 1}),
    ("immediate", {"entry_style": "immediate_probe"}),
    ("restart4", {"entry_style": "restart4"}),
    ("wait12", {"wait_hours": 12}),
    ("wait36", {"wait_hours": 36}),
    ("pullback025", {"pullback_min_atr": 0.25}),
    ("pullback075", {"pullback_min_atr": 0.75}),
    ("retrace033", {"max_retracement": 0.33}),
    ("retrace0618", {"max_retracement": 0.618}),
    ("structure12", {"structure_bars": 12}),
    ("buffer025", {"stop_buffer_atr": 0.25}),
    ("minstop3pct", {"min_stop_pct": 0.03}),
    ("retry0", {"max_retry_per_layer": 0}),
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _score(dev: dict[str, Any], val: dict[str, Any]) -> float:
    dev_log = math.log(max(float(dev["annual_equity_multiple"]), 1e-9))
    val_log = math.log(max(float(val["annual_equity_multiple"]), 1e-9))
    dd_penalty = max(0.0, abs(float(val["max_drawdown_pct"])) - 20.0) / 20.0
    concentration_penalty = max(0.0, float(val["top3_gross_profit_share"]) - 0.65)
    return (
        min(dev_log, val_log)
        + 0.5 * (dev_log + val_log) / 2.0
        - 0.5 * abs(dev_log - val_log)
        - dd_penalty
        - concentration_penalty
    )


def main() -> None:
    configs = [(variant_id, replace(CENTER, name=variant_id, **changes)) for variant_id, changes in VARIANTS]
    registry_hash = hashlib.sha256(
        json.dumps(
            [(variant_id, asdict(config)) for variant_id, config in configs],
            ensure_ascii=False,
            sort_keys=True,
            default=list,
        ).encode("utf-8")
    ).hexdigest()
    assets = load_assets()
    rows: list[dict[str, Any]] = []
    selections: dict[str, list[dict[str, Any]]] = {}
    for asset, data in assets.items():
        paired: list[dict[str, Any]] = []
        for variant_id, config in configs:
            metrics_by_split: dict[str, dict[str, Any]] = {}
            for split, (start, end) in SPLITS[asset].items():
                run = run_backtest(data, config, start=start, end=end)
                metrics_by_split[split] = run.metrics
                rows.append(
                    {
                        "asset": asset,
                        "variant_id": variant_id,
                        "split": split,
                        **run.metrics,
                    }
                )
            dev = metrics_by_split["development"]
            val = metrics_by_split["validation"]
            qualifies = bool(
                float(dev["end_equity"]) > 1.0
                and float(val["end_equity"]) > 1.0
                and float(val["profit_factor"]) > 1.0
                and int(val["campaigns"]) >= 10
                and abs(float(val["max_drawdown_pct"])) <= 20.0
            )
            paired.append(
                {
                    "variant_id": variant_id,
                    "config": asdict(config),
                    "qualifies": qualifies,
                    "score": _score(dev, val),
                    "development": dev,
                    "validation": val,
                }
            )
            print(
                asset,
                variant_id,
                f"dev={dev['annual_equity_multiple']:.3f}x/{dev['profit_factor']:.2f}",
                f"val={val['annual_equity_multiple']:.3f}x/{val['profit_factor']:.2f}",
                f"n={val['campaigns']}",
                "QUALIFY" if qualifies else "-",
                flush=True,
            )
        qualified = sorted(
            (row for row in paired if row["qualifies"]),
            key=lambda row: row["score"],
            reverse=True,
        )[:5]
        selections[asset] = qualified

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(
        ARTIFACT_DIR / "binance_mtf_dstc_single_variable_2026-08-04.csv", index=False
    )
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-MTF-Dual-State-Trend-Campaign",
        "experiment": "E02 single-variable mechanism search",
        "historical_final_audit_revealed": False,
        "registry_hash": registry_hash,
        "variant_count": len(configs),
        "variants": [
            {"variant_id": variant_id, "config": asdict(config)}
            for variant_id, config in configs
        ],
        "selection_rule": (
            "both development and validation end equity > 1; validation PF > 1; "
            "validation campaigns >= 10; validation MDD <= 20%; top five by frozen score"
        ),
        "selections": selections,
    }
    (ARTIFACT_DIR / "binance_mtf_dstc_single_variable_2026-08-04.json").write_text(
        json.dumps(_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
