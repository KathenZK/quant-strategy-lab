from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    ROOT
    / "research/asset-portfolios/15m-asset-specific-six-strategy-selector/scripts"
)
sys.path.insert(0, str(SCRIPTS))

import reveal_binance_as6s_v6_mark_joint_future_oos as reveal  # noqa: E402


def test_v6_mark_reveal_reconstructs_frozen_historical_metrics() -> None:
    assert reveal.historical_parity()["result"] == "PASS"
