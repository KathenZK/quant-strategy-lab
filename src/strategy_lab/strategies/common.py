from __future__ import annotations

from strategy_lab.allocators.common import apply_liquidation_risk_overlay as _apply_liquidation_risk_overlay


def apply_liquidation_risk_overlay(*args, **kwargs):
    if "liquidation_features" in kwargs:
        kwargs["risk_features"] = kwargs.pop("liquidation_features")
    return _apply_liquidation_risk_overlay(*args, **kwargs)
