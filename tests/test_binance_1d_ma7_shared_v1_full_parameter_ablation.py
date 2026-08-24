from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-ma7-asset-specific-search/scripts/"
    "audit_binance_1d_ma7_shared_v1_full_parameter_ablation.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "binance_ma7_shared_v1_ablation_tested", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_oat_variants_are_unique_and_exclude_baseline() -> None:
    module = load_script()
    baseline = module.load_module(
        module.BASELINE_PATH, "binance_ma7_ablation_test_baseline"
    )
    transfer = baseline.load_module(
        baseline.TRANSFER_PATH,
        baseline.TRANSFER_SHA256,
        "binance_ma7_ablation_test_transfer",
    )
    engine = transfer.load_engine()
    long_config, short_config = baseline.v1_configs(engine)
    rows = [
        *module.variants(long_config, leg="long"),
        *module.variants(short_config, leg="short"),
    ]
    ids = [row["variant_id"] for row in rows]
    keys = [(row["leg"], row["config"].key) for row in rows]
    assert len(ids) == len(set(ids))
    assert len(keys) == len(set(keys))
    assert all(row["config"].key != long_config.key for row in rows if row["leg"] == "long")
    assert all(row["config"].key != short_config.key for row in rows if row["leg"] == "short")


def test_ablation_has_no_researcher_exposed_boundary() -> None:
    module = load_script()
    source = module.SCRIPT.read_text(encoding="utf-8") if hasattr(module, "SCRIPT") else SCRIPT.read_text(encoding="utf-8")
    assert "RESEARCHER_EXPOSED" not in source
    assert "researcher_exposed_audit" not in source

