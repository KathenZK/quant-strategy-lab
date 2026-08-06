from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT = Path(
    "research/asset-portfolios/1h-price-impulse-campaign/scripts/"
    "research_binance_1h_pic_v1.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("test_binance_1h_pic_v1_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_position(module):
    import pandas as pd

    return module.LayeredPosition(
        side=1,
        signal_ts=pd.Timestamp("2026-01-01", tz="UTC"),
        entry_ts=pd.Timestamp("2026-01-01 01:00", tz="UTC"),
        raw_entry=100.0,
        initial_fill=100.0,
        entry_equity=1.0,
        r_log=0.05,
        r_price=5.0,
        initial_stop=95.0,
        stop=95.0,
        planned_full_quantity=0.0018,
        initial_probe_quantity=0.00045,
        lots=[module.Lot(0.00045, 100.0, 0.25)],
    )


def test_lifo_reduction_removes_latest_layer_first() -> None:
    module = load_module()
    position = sample_position(module)
    position.lots.append(module.Lot(0.00045, 105.0, 0.50))
    balance, price_pnl, fee = module.close_lifo(
        1.0, position, 0.00045, 110.0, 0.001
    )
    assert position.quantity == pytest.approx(position.initial_probe_quantity)
    assert position.lots[0].fill == 100.0
    assert price_pnl == pytest.approx(0.00045 * 5.0)
    assert fee == pytest.approx(0.00045 * 110.0 * 0.001)
    assert balance == pytest.approx(1.0 + price_pnl - fee)


def test_safe_add_cannot_break_campaign_stopout_floor() -> None:
    module = load_module()
    shared = module.load_v0_module()
    position = sample_position(module)
    config = module.V1Config()
    add_fill = shared.adverse_fill(102.5, 1, config.slippage)
    safe = module.maximum_safe_add_quantity(
        1.0,
        position,
        add_fill,
        102.5,
        10.0,
        config,
        shared.adverse_fill,
    )
    assert safe > 0.0
    fee = safe * add_fill * config.fee_rate
    position.lots.append(module.Lot(safe, add_fill, 0.5))
    stop_fill = shared.adverse_fill(position.stop, -1, config.slippage)
    projected = module.stopout_equity(1.0 - fee, position, stop_fill, config.fee_rate)
    assert projected >= position.entry_equity * (1.0 - module.RISK_BUDGET) - 1e-12


def test_probe_is_one_quarter_of_frozen_full_quantity() -> None:
    module = load_module()
    assert module.PROBE_FRACTION == 0.25
    assert module.LAYER_THRESHOLDS == (0.5, 1.0, 2.0)
    assert module.LAYER_FRACTIONS == (0.50, 0.75, 1.00)


def test_risk_trim_quantity_restores_operational_floor() -> None:
    module = load_module()
    shared = module.load_v0_module()
    position = sample_position(module)
    position.lots.append(module.Lot(0.001, 105.0, 1.0))
    config = module.V1Config(
        operational_risk_budget=0.009,
        maintain_risk_after_funding=True,
    )
    balance = 0.999
    quantity = module.quantity_to_restore_stopout(
        balance,
        position,
        110.0,
        config,
        shared.adverse_fill,
    )
    assert 0.0 < quantity <= 0.001
    fill = shared.adverse_fill(110.0, -1, config.slippage)
    balance, _, _ = module.close_lifo(
        balance, position, quantity, fill, config.fee_rate
    )
    stop_fill = shared.adverse_fill(position.stop, -1, config.slippage)
    projected = module.stopout_equity(balance, position, stop_fill, config.fee_rate)
    assert projected >= position.entry_equity * (1.0 - 0.009) - 1e-12


def test_marked_equity_sums_lot_level_unrealized_pnl() -> None:
    module = load_module()
    position = sample_position(module)
    position.lots.append(module.Lot(0.00045, 105.0, 0.50))
    expected = 1.0 + 0.00045 * (110.0 - 100.0) + 0.00045 * (110.0 - 105.0)
    assert module.marked_equity(1.0, position, 110.0) == pytest.approx(expected)
