from __future__ import annotations

import hashlib
import itertools
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
from search_dstc_single_variable import VARIANTS, _score


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
E02_PATH = ARTIFACT_DIR / "binance_mtf_dstc_single_variable_2026-08-04.json"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def generate_configs(asset: str, selected_ids: list[str]) -> list[tuple[str, Config]]:
    changes_by_id = dict(VARIANTS)
    configs: list[tuple[str, Config]] = []
    for size in range(1, len(selected_ids) + 1):
        for ids in itertools.combinations(selected_ids, size):
            merged: dict[str, Any] = {}
            conflict = False
            for variant_id in ids:
                for key, value in changes_by_id[variant_id].items():
                    if key in merged and merged[key] != value:
                        conflict = True
                    merged[key] = value
            if conflict:
                continue
            combo_id = "+".join(ids)
            configs.append((combo_id, replace(Config(name=combo_id), **merged)))
    if len(configs) > 160:
        raise RuntimeError(f"{asset} generated {len(configs)} configs above frozen cap")
    return configs


def main() -> None:
    e02 = json.loads(E02_PATH.read_text(encoding="utf-8"))
    assets = load_assets()
    all_rows: list[dict[str, Any]] = []
    selections: dict[str, list[dict[str, Any]]] = {}
    generated: dict[str, list[dict[str, Any]]] = {}
    for asset, data in assets.items():
        selected_ids = [row["variant_id"] for row in e02["selections"][asset]]
        configs = generate_configs(asset, selected_ids)
        generated[asset] = [
            {"combo_id": combo_id, "config": asdict(config)} for combo_id, config in configs
        ]
        paired: list[dict[str, Any]] = []
        for combo_id, config in configs:
            metrics_by_split: dict[str, dict[str, Any]] = {}
            for split, (start, end) in SPLITS[asset].items():
                run = run_backtest(data, config, start=start, end=end)
                metrics_by_split[split] = run.metrics
                all_rows.append(
                    {"asset": asset, "combo_id": combo_id, "split": split, **run.metrics}
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
            row = {
                "combo_id": combo_id,
                "config": asdict(config),
                "qualifies": qualifies,
                "score": _score(dev, val),
                "development": dev,
                "validation": val,
            }
            paired.append(row)
            print(
                asset,
                combo_id,
                f"dev={dev['annual_equity_multiple']:.3f}x/{dev['profit_factor']:.2f}",
                f"val={val['annual_equity_multiple']:.3f}x/{val['profit_factor']:.2f}",
                f"n={val['campaigns']}",
                "QUALIFY" if qualifies else "-",
                flush=True,
            )
        selections[asset] = sorted(
            (row for row in paired if row["qualifies"]),
            key=lambda row: row["score"],
            reverse=True,
        )[:10]

    generation_hash = hashlib.sha256(
        json.dumps(generated, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    pd.DataFrame(all_rows).to_csv(
        ARTIFACT_DIR / "binance_mtf_dstc_combinations_2026-08-04.csv", index=False
    )
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-MTF-Dual-State-Trend-Campaign",
        "experiment": "E03 qualified-slot combinations",
        "historical_final_audit_revealed": False,
        "source_e02_hash": e02["registry_hash"],
        "generation_hash": generation_hash,
        "generated": generated,
        "selections": selections,
    }
    (ARTIFACT_DIR / "binance_mtf_dstc_combinations_2026-08-04.json").write_text(
        json.dumps(_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
