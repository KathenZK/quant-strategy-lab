from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator/"
    "scripts/audit_three_x_tail_risk.py"
)
SPEC = importlib.util.spec_from_file_location("audit_three_x_tail_risk", SCRIPT)
assert SPEC and SPEC.loader
risk = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(risk)


def one_leg(*, exit_open: float = 90.0, exposure: float = 0.10) -> pd.DataFrame:
    entry = pd.Timestamp("2026-01-01T00:00:00Z")
    exit_time = entry + pd.Timedelta(hours=2)
    return pd.DataFrame(
        {
            "ts": [entry - pd.Timedelta(hours=1)],
            "symbol": ["TEST/USDT:USDT"],
            "entry_time": [entry],
            "planned_exit_time": [exit_time],
            "entry_open": [100.0],
            "exit_open": [exit_open],
            "funding_sum": [0.0],
            "trade_return": [1.0 - exit_open / 100.0 - 0.0028],
            "leg_exposure": [exposure],
        }
    )


def mark_path(high: float = 110.0) -> pd.DataFrame:
    times = pd.date_range("2026-01-01T00:00:00Z", periods=3, freq="1h")
    return pd.DataFrame(
        {
            "ts": times,
            "symbol": ["TEST/USDT:USDT"] * 3,
            "open": [100.0, 95.0, 90.0],
            "high": [high, high, 90.0],
        }
    )


def test_three_x_profitable_short_without_liquidation() -> None:
    scenario, curve = risk.simulate_scenario(
        one_leg(),
        mark_path(),
        pd.DataFrame(columns=["ts", "symbol", "funding_rate"]),
        cost_multiplier=1.0,
        maintenance_margin_rate=0.01,
    )
    assert not scenario["liquidated"]
    assert scenario["total_return"] == pytest.approx(0.03 - 0.00084)
    assert len(curve) == 3


def test_joint_mark_high_can_trigger_liquidation() -> None:
    scenario, _ = risk.simulate_scenario(
        one_leg(exit_open=90.0, exposure=0.375),
        mark_path(high=250.0),
        pd.DataFrame(columns=["ts", "symbol", "funding_rate"]),
        cost_multiplier=1.0,
        maintenance_margin_rate=0.025,
    )
    assert scenario["liquidated"]
    assert scenario["liquidation_time"] == "2026-01-01T00:00:00+00:00"


def test_three_x_authorization_guard_is_sealed_before_reveal() -> None:
    with pytest.raises(RuntimeError, match="remains sealed"):
        risk.assert_authorized(pd.Timestamp("2026-10-20T21:04:59Z"))


def test_frozen_three_x_contract_matches_implementation() -> None:
    contract = risk.validate_three_x_contract()
    assert contract["authorization"]["prospective_oos_outcomes_read"] is False
    assert contract["frozen_semantics"]["leverage_multiplier"] == 3.0


def test_revealed_decision_sha_is_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reveal_dir = tmp_path / "reveal"
    reveal_dir.mkdir()
    legs_path = reveal_dir / "revealed_legs.parquet"
    decisions_path = reveal_dir / "revealed_decisions.parquet"
    report_path = reveal_dir / "one_time_oos_report.json"
    legs = one_leg()
    legs["strategy"] = "r4"
    legs.to_parquet(legs_path, index=False)
    pd.DataFrame(
        {"ts": legs["ts"], "strategy": ["r4"], "portfolio_return": [0.01]}
    ).to_parquet(decisions_path, index=False)
    report = {
        "outputs": {
            "legs": {
                "path": "reveal/revealed_legs.parquet",
                "sha256": risk.sha256(legs_path),
            },
            "decisions": {
                "path": "reveal/revealed_decisions.parquet",
                "sha256": risk.sha256(decisions_path),
            },
        }
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(risk, "ROOT", tmp_path)
    monkeypatch.setattr(risk, "REVEAL_REPORT", report_path)
    monkeypatch.setattr(risk, "REVEALED_LEGS", legs_path)
    monkeypatch.setattr(risk, "REVEALED_DECISIONS", decisions_path)
    adjudication = {"reveal_report_sha256": risk.sha256(report_path)}
    assert len(risk.load_revealed_legs(adjudication)) == 1

    pd.DataFrame({"tampered": [True]}).to_parquet(decisions_path, index=False)
    with pytest.raises(RuntimeError, match="decisions SHA mismatch"):
        risk.load_revealed_legs(adjudication)


def test_atomic_parquet_and_artifact_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(risk, "ROOT", tmp_path)
    output = tmp_path / "nested" / "frame.parquet"
    frame = pd.DataFrame({"ts": [pd.Timestamp("2026-01-01T00:00:00Z")], "x": [1.0]})
    risk.atomic_parquet(frame, output)
    receipt = risk.artifact(output)
    assert receipt["sha256"] == risk.sha256(output)
    assert receipt["size_bytes"] > 0
