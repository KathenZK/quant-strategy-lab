from __future__ import annotations

import json
import sys
from dataclasses import MISSING, asdict, field, make_dataclass, replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import sol_1h_ar_v1 as v1  # noqa: E402


ARTIFACT_DIR = ROOT / "research/sol/1h-adaptive-regime/artifacts"
ABLATION_JSON = ARTIFACT_DIR / "sol_1h_ar_v1_full_ablation_2026-07-03.json"
CLEAN_JSON = ARTIFACT_DIR / "sol_1h_ar_v1_clean_config_2026-07-03.json"


def python_type(value: Any) -> type[Any]:
    if isinstance(value, bool):
        return bool
    if isinstance(value, int):
        return int
    if isinstance(value, float):
        return float
    return str


def clean_types_and_defaults(engine: Any) -> tuple[tuple[type[Any], Any], ...]:
    if not ABLATION_JSON.exists():
        raise FileNotFoundError(
            "Run research_sol_1h_ar_v1_full_ablation.py before clean conversion"
        )
    ablation = json.loads(ABLATION_JSON.read_text(encoding="utf-8"))
    base_configs = v1.v1_configs(engine)
    surfaces = ablation["clean_surface"]
    result: list[tuple[type[Any], Any]] = []
    for index, cfg in enumerate(base_configs):
        component = f"leg{index + 1}_{cfg.style}"
        active_fields = list(surfaces[component])
        definitions = [
            (
                field_name,
                python_type(getattr(cfg, field_name)),
                field(default=getattr(cfg, field_name)),
            )
            for field_name in active_fields
        ]
        clean_type = make_dataclass(
            f"SOL1HARV1Leg{index + 1}CleanConfig",
            definitions,
            frozen=True,
            slots=True,
        )
        defaults: dict[str, Any] = {}
        for definition in definitions:
            default = definition[2].default
            if default is MISSING:
                raise RuntimeError(f"Missing clean default for {definition[0]}")
            defaults[definition[0]] = default
        result.append((clean_type, clean_type(**defaults)))
    return tuple(result)


def to_base_configs(engine: Any, clean_configs: tuple[Any, ...]) -> tuple[Any, ...]:
    base_configs = v1.v1_configs(engine)
    if len(clean_configs) != len(base_configs):
        raise ValueError(
            f"Expected {len(base_configs)} clean legs, got {len(clean_configs)}"
        )
    return tuple(
        replace(base, **asdict(clean_cfg))
        for base, clean_cfg in zip(base_configs, clean_configs, strict=True)
    )


def default_clean_configs(engine: Any) -> tuple[Any, ...]:
    return tuple(default for _clean_type, default in clean_types_and_defaults(engine))


def simulate_clean(
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    clean_configs: tuple[Any, ...] | None = None,
) -> tuple[list[Any], list[list[Any]], list[float]]:
    clean_configs = clean_configs or default_clean_configs(engine)
    return v1.simulate_v1(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        configs=to_base_configs(engine, clean_configs),
    )


def main() -> None:
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    original, _original_legs, _original_priorities = v1.simulate_v1(
        engine, frame, funding_times, funding_cumulative
    )
    clean_configs = default_clean_configs(engine)
    clean_trades, _clean_legs, priorities = simulate_clean(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        clean_configs=clean_configs,
    )
    if v1.trade_signature(original) != v1.trade_signature(clean_trades):
        raise RuntimeError("V1 clean config is not trade-path equivalent to V1")
    original_slots = len(v1.v1_configs(engine)) * len(
        engine.StrategyConfig.__dataclass_fields__
    )
    clean_slots = sum(len(asdict(cfg)) for cfg in clean_configs)
    payload = {
        "family": "SOL-1H-Adaptive-Regime",
        "version": "SOL-1H-Adaptive-Regime-V1",
        "identity": "clean_equivalent_configuration_surface",
        "status": "diagnostic_baseline_not_promoted_not_live_ready",
        "original_strategy_config_slots": original_slots,
        "clean_tunable_slots": clean_slots,
        "removed_or_hardcoded_slots": original_slots - clean_slots,
        "trade_path_equal": True,
        "components": [asdict(cfg) for cfg in clean_configs],
        "component_prefit_priority_scores": priorities,
        "metrics": v1.metrics(engine, clean_trades),
        "data_quality": quality,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
