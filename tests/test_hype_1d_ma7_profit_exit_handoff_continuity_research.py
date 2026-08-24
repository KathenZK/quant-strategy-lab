from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/hype/1d-ma7-asymmetric-body-trend/scripts/research_hype_1d_ma7_profit_exit_handoff_continuity.py"


def load():
    spec = importlib.util.spec_from_file_location("pehc_research_test_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def metrics(return_pct: float, mdd_pct: float) -> dict:
    return {
        "status": "PASS",
        "metrics": {
            "net_return_pct": return_pct,
            "chronological_1h_mdd_pct": mdd_pct,
            "equity_multiple": 1.0 + return_pct / 100.0,
        },
    }


def test_frozen_windows_are_complete_nonoverlapping_blocks() -> None:
    module = load()
    assert module.BLOCKS == (
        (0, 54),
        (54, 108),
        (108, 162),
        (162, 216),
        (216, 270),
        (270, 324),
        (324, 378),
        (378, 432),
    )
    assert module.engine_start((54, 108)) == 55


def test_comparison_uses_strict_dual_improvement_and_materiality() -> None:
    module = load()
    row = module.comparison(metrics(12.0, -8.0), metrics(7.0, -10.0))
    assert row["dual_improvement"]
    assert row["material"]
    equality = module.comparison(metrics(7.0, -9.0), metrics(7.0, -10.0))
    assert not equality["dual_improvement"]


def test_block_aggregate_retains_worst_fold() -> None:
    module = load()
    candidates = [metrics(10.0, -8.0), metrics(-2.0, -12.0)]
    controls = [metrics(5.0, -10.0), metrics(0.0, -10.0)]
    row = module.aggregate_blocks(candidates, controls)
    assert row["dual_improvement_blocks"] == 1
    assert row["worst_return_delta_pp"] == -2.0
    assert row["worst_mdd_delta_pp"] == -2.0


def test_max_winner_origin_matches_accepted_handoff_trade() -> None:
    module = load()
    run = {
        "handoff_events": [
            {"event": "handoff_accept", "ts": "2026-01-01T03:00:00+00:00", "origin_index": 10},
            {"event": "handoff_accept", "ts": "2026-02-01T05:00:00+00:00", "origin_index": 40},
        ],
        "trades": [
            {"entry_ts": "2026-01-01T03:00:00+00:00", "side": "short", "net_pnl": 0.1},
            {"entry_ts": "2026-02-01T05:00:00+00:00", "side": "short", "net_pnl": 0.4},
        ],
    }
    assert module.max_winner_origin(run) == 40


def test_economic_path_key_ignores_arm_label() -> None:
    module = load()
    full = {"trades_sha256": "A"}
    blocks = [{"trades_sha256": str(index)} for index in range(8)]
    assert module.economic_path_key(full, blocks) == module.economic_path_key(
        {**full, "arm_id": "other"}, [{**row, "arm_id": "x"} for row in blocks]
    )

