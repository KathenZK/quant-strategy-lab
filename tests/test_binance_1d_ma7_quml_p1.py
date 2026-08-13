from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
P1_SCRIPT = ROOT / (
    "research/asset-portfolios/1d-ma7-quantile-utility-meta-label/"
    "scripts/research_binance_1d_ma7_quml_p1.py"
)
SYNC_SCRIPT = ROOT / (
    "research/asset-portfolios/1d-ma7-quantile-utility-meta-label/"
    "scripts/sync_binance_quml_p0_price_funding.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


quml = load_module(P1_SCRIPT, "quml_test_module")
sync = load_module(SYNC_SCRIPT, "quml_sync_test_module")


def passing_summary() -> dict:
    return {
        "side_counts": {"long": 80, "short": 80},
        "choice_frequency": {"alpha=1000|quantile=0.90|route=combined": 24},
        "selected_events": 160,
        "per_asset": {
            asset: {"selected": {"events": 20}} for asset in quml.FRESH_ASSETS
        },
        "selected_90d_blocks": 24,
        "main": {"mean": 0.001, "profit_factor": 1.2},
        "positive_asset_count": 6,
        "positive_outer_fold_count": 24,
        "ranking_spearman": 0.051,
        "positive_ranking_asset_count": 6,
        "cluster_bootstrap": {"positive_probability": 0.90},
        "variants": {
            column: {"mean": 0.001, "profit_factor": 1.1}
            for column in ("z_4bps", "z_funding_off", "z_lag1")
        },
        "lag_executable_rate": 0.75,
        "dual_improved_asset_count": 5,
    }


def test_second_fresh_universe_is_disjoint_and_hype_locked() -> None:
    assert len(quml.LEGACY_ASSETS) == 13
    assert len(quml.FRESH_ASSETS) == 8
    assert not set(quml.LEGACY_ASSETS) & set(quml.FRESH_ASSETS)
    assert len(quml.ALL_ASSETS) == 21
    assert "HYPE" not in quml.ALL_ASSETS
    assert {row[0] for row in sync.SYMBOLS.values()} == set(
        quml.FRESH_ASSETS
    )


def test_quantile_threshold_uses_train_route_predictions_only() -> None:
    base = SimpleNamespace(
        PRICE_FEATURES=("pred",),
        predict_utility=lambda model, frame, features: frame[
            "pred"
        ].to_numpy(dtype="float64"),
        route_mask=lambda frame, route: (
            pd.Series(True, index=frame.index)
            if route == "combined"
            else frame["side"].gt(0)
            if route == "long_only"
            else frame["side"].lt(0)
        ),
    )
    train = pd.DataFrame(
        {
            "pred": [0.0, 1.0, 2.0, 100.0],
            "side": [1, 1, -1, -1],
        }
    )
    assert np.isclose(
        quml.train_quantile_threshold(
            base,
            object(),
            train,
            quantile=0.5,
            route="long_only",
        ),
        0.5,
    )
    assert np.isclose(
        quml.train_quantile_threshold(
            base,
            object(),
            train,
            quantile=0.5,
            route="short_only",
        ),
        51.0,
    )


def test_scaled_gate_requires_quantile_increment_and_fresh_coverage() -> None:
    summary = passing_summary()
    gate = quml.apply_gate(
        capacity={"p0_capacity_pass": True},
        quantile=summary,
        delta={"positive_probability": 0.90},
    )
    assert gate["development_gate_pass"]

    weak_delta = quml.apply_gate(
        capacity={"p0_capacity_pass": True},
        quantile=summary,
        delta={"positive_probability": 0.8999},
    )
    assert not weak_delta["checks"]["quantile_over_absolute_control"]

    insufficient_asset = copy.deepcopy(summary)
    insufficient_asset["per_asset"]["BCH"]["selected"]["events"] = 14
    assert not quml.apply_gate(
        capacity={"p0_capacity_pass": True},
        quantile=insufficient_asset,
        delta={"positive_probability": 0.90},
    )["checks"]["accepted_total_and_per_asset"]


def test_model_contract_remains_price_only_ridge() -> None:
    base = quml.load_base_module()
    assert len(base.PRICE_FEATURES) == 47
    assert len(set(base.PRICE_FEATURES)) == 47
    assert not set(base.FLOW_FEATURES) & set(base.PRICE_FEATURES)
    assert base.ALPHA_GRID == (1.0, 10.0, 100.0, 300.0, 1000.0)
    assert quml.QUANTILE_GRID == (0.80, 0.90, 0.95)
    assert "asset" not in base.PRICE_FEATURES


def test_exposed_global_aggregate_result_is_fail_closed() -> None:
    with pytest.raises(RuntimeError, match="historical 21-asset event panel"):
        quml.enforce_fold_local_aggregate_pipeline()
