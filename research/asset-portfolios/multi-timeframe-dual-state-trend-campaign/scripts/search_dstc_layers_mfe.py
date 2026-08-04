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
E03_PATH = ARTIFACT_DIR / "binance_mtf_dstc_combinations_2026-08-04.json"

ARMS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("probe_no_mfe", {"max_layers": 1, "mfe_mode": "no_mfe"}),
    ("probe_mfe50_all", {"max_layers": 1, "mfe_mode": "mfe50_all"}),
    ("layers2_no_mfe", {"max_layers": 2, "mfe_mode": "no_mfe"}),
    ("layers2_mfe50_all", {"max_layers": 2, "mfe_mode": "mfe50_all"}),
    ("layers2_mfe50_adds", {"max_layers": 2, "mfe_mode": "mfe50_adds"}),
    ("layers4_no_mfe", {"max_layers": 4, "mfe_mode": "no_mfe"}),
    ("layers4_mfe50_all", {"max_layers": 4, "mfe_mode": "mfe50_all"}),
    ("layers4_mfe50_adds", {"max_layers": 4, "mfe_mode": "mfe50_adds"}),
    (
        "layers4_ladder_alt_no_mfe",
        {"max_layers": 4, "add_thresholds_r": (0.5, 1.5, 3.0), "mfe_mode": "no_mfe"},
    ),
    (
        "layers4_ladder_alt_mfe50_all",
        {"max_layers": 4, "add_thresholds_r": (0.5, 1.5, 3.0), "mfe_mode": "mfe50_all"},
    ),
    (
        "layers4_budget15",
        {"max_layers": 4, "campaign_loss_budget": 0.015, "mfe_mode": "mfe50_all"},
    ),
    (
        "layers4_budget30",
        {"max_layers": 4, "campaign_loss_budget": 0.03, "mfe_mode": "mfe50_all"},
    ),
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _qualifies(dev: dict[str, Any], val: dict[str, Any]) -> bool:
    return bool(
        float(dev["end_equity"]) > 1.0
        and float(val["end_equity"]) > 1.0
        and float(val["profit_factor"]) >= 1.3
        and int(val["campaigns"]) >= 10
        and abs(float(val["max_drawdown_pct"])) <= 20.0
        and float(val["max_effective_leverage"]) <= 3.0
        and int(val["risk_violations"]) == 0
    )


def _behavior_key(config_row: dict[str, Any]) -> str:
    config = dict(config_row)
    config.pop("name", None)
    if config.get("invalidation") in {"slope_structure", "structure_only"}:
        config["wrong_side_atr"] = "dormant"
        config["invalid_days"] = "dormant"
    return json.dumps(config, sort_keys=True, default=list)


def main() -> None:
    e03 = json.loads(E03_PATH.read_text(encoding="utf-8"))
    assets = load_assets()
    generated: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    selections: dict[str, list[dict[str, Any]]] = {}
    for asset, data in assets.items():
        bases = e03["selections"].get(asset, [])
        attribution_only = not bool(bases)
        if attribution_only:
            bases = [{"combo_id": "center", "config": asdict(Config(name="center"))}]
        else:
            deduplicated: list[dict[str, Any]] = []
            seen: set[str] = set()
            for base in bases:
                key = _behavior_key(base["config"])
                if key not in seen:
                    deduplicated.append(base)
                    seen.add(key)
            bases = deduplicated
        paired: list[dict[str, Any]] = []
        for base in bases:
            base_config = Config(**base["config"])
            for arm_id, changes in ARMS:
                config_id = f"{base['combo_id']}::{arm_id}"
                config = replace(base_config, name=config_id, **changes)
                generated.append(
                    {
                        "asset": asset,
                        "config_id": config_id,
                        "attribution_only": attribution_only,
                        "config": asdict(config),
                    }
                )
                metrics_by_split: dict[str, dict[str, Any]] = {}
                for split, (start, end) in SPLITS[asset].items():
                    run = run_backtest(data, config, start=start, end=end)
                    metrics_by_split[split] = run.metrics
                    results.append(
                        {
                            "asset": asset,
                            "config_id": config_id,
                            "split": split,
                            "attribution_only": attribution_only,
                            **run.metrics,
                        }
                    )
                dev = metrics_by_split["development"]
                val = metrics_by_split["validation"]
                qualifies = _qualifies(dev, val) and not attribution_only
                row = {
                    "config_id": config_id,
                    "config": asdict(config),
                    "attribution_only": attribution_only,
                    "qualifies": qualifies,
                    "development": dev,
                    "validation": val,
                }
                paired.append(row)
                print(
                    asset,
                    config_id,
                    f"dev={dev['annual_equity_multiple']:.3f}x/{dev['profit_factor']:.2f}",
                    f"val={val['annual_equity_multiple']:.3f}x/{val['profit_factor']:.2f}",
                    f"dd={val['max_drawdown_pct']:.1f}%",
                    f"n={val['campaigns']}",
                    "QUALIFY" if qualifies else ("ATTR" if attribution_only else "-"),
                    flush=True,
                )
        selections[asset] = [row for row in paired if row["qualifies"]]

    generation_hash = hashlib.sha256(
        json.dumps(generated, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    pd.DataFrame(results).to_csv(
        ARTIFACT_DIR / "binance_mtf_dstc_layers_mfe_2026-08-04.csv", index=False
    )
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-MTF-Dual-State-Trend-Campaign",
        "experiment": "E04 Probe/Add/MFE attribution",
        "historical_final_audit_revealed": False,
        "source_e03_hash": e03["generation_hash"],
        "generation_hash": generation_hash,
        "arms": [{"arm_id": arm_id, "changes": changes} for arm_id, changes in ARMS],
        "generated": generated,
        "selections": selections,
    }
    (ARTIFACT_DIR / "binance_mtf_dstc_layers_mfe_2026-08-04.json").write_text(
        json.dumps(_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
