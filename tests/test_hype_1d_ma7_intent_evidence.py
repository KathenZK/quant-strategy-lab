from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "hype_1d_ma7_intent_evidence.py"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = load_module(SCRIPT_PATH, "hype_1d_ma7_intent_evidence_test")


def trade(
    side: str,
    entry_ts: str,
    exit_ts: str,
    *,
    entry_reason: str = "fresh_cross_long",
    exit_reason: str = "terminal_flatten",
    trade_id: str = "RUN-001",
    label: str = "SEARCH_LABEL",
):
    return {
        "trade_id": trade_id,
        "label": label,
        "trial_id": "A099",
        "side": side,
        "entry_ts": entry_ts,
        "exit_ts": exit_ts,
        "entry_reason": entry_reason,
        "exit_reason": exit_reason,
        "entry_price": 100.0,
        "exit_price": 110.0,
        "nested": {"run_id": "ignored", "economic": 1},
    }


def test_trade_signature_multiset_is_label_free_and_preserves_duplicates() -> None:
    first = trade(
        "long",
        "2026-01-01T00:00:00+00:00",
        "2026-01-05T00:00:00+00:00",
        trade_id="ANCHOR-1",
        label="ANCHOR",
    )
    duplicate = {**first, "trade_id": "ANCHOR-2", "label": "ANOTHER_LABEL"}
    variant = {**first, "trade_id": "VARIANT-9", "label": "VARIANT"}

    diff = EVIDENCE.diff_trade_signatures([first, duplicate], [variant])

    assert diff["unchanged_count"] == 1
    assert diff["added"] == []
    assert len(diff["removed"]) == 1
    encoded = json.dumps(diff, sort_keys=True)
    assert "trade_id" not in encoded
    assert "trial_id" not in encoded
    assert "ANCHOR" not in encoded
    assert diff["removed"][0]["nested"] == {"economic": 1}


def test_signatures_normalize_json_values_without_mutating_input() -> None:
    source = trade(
        "short",
        "2026-02-01T00:00:00+00:00",
        "2026-02-03T00:00:00+00:00",
    )
    source["created_at"] = datetime(2026, 2, 1, tzinfo=timezone.utc)
    source["not_finite"] = float("nan")
    original = deepcopy(source)

    signature = EVIDENCE.trade_signatures([source])[0]

    assert signature["created_at"] == "2026-02-01T00:00:00+00:00"
    assert signature["not_finite"] is None
    assert source["trade_id"] == original["trade_id"]
    assert source["not_finite"] != source["not_finite"]


def test_candidate_v4_matching_reports_early_late_reasons_and_unmatched() -> None:
    v4 = [
        trade(
            "long",
            "2026-01-10T00:00:00+00:00",
            "2026-01-20T00:00:00+00:00",
            entry_reason="v4_long_entry",
            exit_reason="v4_long_exit",
        ),
        trade(
            "short",
            "2026-02-01T00:00:00+00:00",
            "2026-02-10T00:00:00+00:00",
            entry_reason="v4_short_entry",
            exit_reason="v4_short_exit",
        ),
    ]
    candidate = [
        trade(
            "long",
            "2026-01-08T00:00:00+00:00",
            "2026-01-22T00:00:00+00:00",
            entry_reason="flat_armed_slope_confirm_long",
            exit_reason="long_slope_loss",
        ),
        trade(
            "short",
            "2026-02-03T00:00:00+00:00",
            "2026-02-08T00:00:00+00:00",
            entry_reason="fresh_cross_short",
            exit_reason="short_rsi_take_profit",
        ),
        trade(
            "long",
            "2026-03-01T00:00:00+00:00",
            "2026-03-02T00:00:00+00:00",
        ),
    ]

    result = EVIDENCE.candidate_v4_trade_attribution(candidate, v4)

    assert [row["side"] for row in result["matched"]] == ["long", "short"]
    first, second = result["matched"]
    assert first["entry_timing"] == {
        "candidate_minus_v4_days": -2.0,
        "relative": "earlier",
    }
    assert first["exit_timing"] == {
        "candidate_minus_v4_days": 2.0,
        "relative": "later",
    }
    assert first["entry_reason"]["candidate"] == "flat_armed_slope_confirm_long"
    assert first["candidate_classification"]["armed_entry"] is True
    assert first["candidate_classification"]["slope_loss_exit"] is True
    assert second["entry_timing"]["relative"] == "later"
    assert second["exit_timing"]["relative"] == "earlier"
    assert second["candidate_classification"]["rsi_take_profit_exit"] is True
    assert result["summary"]["candidate_unmatched_count"] == 1
    assert result["summary"]["exact_v4_unmatched_count"] == 0


def test_matching_prefers_overlap_then_nearest_entry_deterministically() -> None:
    control = [
        trade(
            "long",
            "2026-01-01T00:00:00+00:00",
            "2026-01-03T00:00:00+00:00",
            entry_reason="control_first",
        ),
        trade(
            "long",
            "2026-01-20T00:00:00+00:00",
            "2026-01-25T00:00:00+00:00",
            entry_reason="control_second",
        ),
    ]
    candidate = [
        trade(
            "long",
            "2026-01-19T00:00:00+00:00",
            "2026-01-24T00:00:00+00:00",
            entry_reason="candidate_overlap",
        )
    ]

    first = EVIDENCE.candidate_v4_trade_attribution(candidate, control)
    second = EVIDENCE.candidate_v4_trade_attribution(candidate, control)

    assert first == second
    assert first["matched"][0]["exact_v4"]["entry_reason"] == "control_second"
    assert first["matched"][0]["match_basis"] == "maximum_interval_overlap"
    assert first["exact_v4_unmatched"][0]["trade"]["entry_reason"] == "control_first"


def test_atomic_reversal_roles_are_classified_from_actions_and_adjacency() -> None:
    candidate = [
        trade(
            "long",
            "2026-01-01T00:00:00+00:00",
            "2026-01-05T00:00:00+00:00",
            exit_reason="held_arm_band_confirm_short",
        ),
        trade(
            "short",
            "2026-01-05T00:00:00+00:00",
            "2026-01-09T00:00:00+00:00",
            entry_reason="held_arm_band_confirm_short",
            exit_reason="short_slope_loss",
        ),
    ]
    actions = [
        {
            "ts": "2026-01-05T00:00:00+00:00",
            "signal_ts": "2026-01-04T00:00:00+00:00",
            "from_side": 1,
            "target_side": -1,
            "reason": "held_arm_band_confirm_short",
            "fills": 2,
        }
    ]

    result = EVIDENCE.candidate_v4_trade_attribution(
        candidate, candidate, candidate_actions=actions
    )

    first, second = result["matched"]
    assert first["candidate_classification"]["atomic_reversal_role"] == "exit_leg"
    assert second["candidate_classification"]["atomic_reversal_role"] == "entry_leg"
    assert second["candidate_classification"]["armed_entry"] is True


def test_r0_r1_trade_diff_attributes_hard_stop_and_earlier_exit() -> None:
    r0 = [
        trade(
            "long",
            "2026-01-01T00:00:00+00:00",
            "2026-01-10T00:00:00+00:00",
            exit_reason="long_slope_loss",
        ),
        trade(
            "short",
            "2026-02-01T00:00:00+00:00",
            "2026-02-10T00:00:00+00:00",
        ),
    ]
    r1 = [
        trade(
            "long",
            "2026-01-01T00:00:00+00:00",
            "2026-01-05T12:00:00+00:00",
            exit_reason="emergency_hard_stop",
        )
    ]

    result = EVIDENCE.r0_r1_trade_diff(r0, r1)

    assert result["matched"][0]["exit_timing"] == {
        "r1_minus_r0_days": -4.5,
        "relative": "earlier",
    }
    assert result["matched"][0]["r1_hard_stop_changed_exit"] is True
    assert result["summary"]["r1_hard_stop_exit_count"] == 1
    assert result["summary"]["r0_unmatched_count"] == 1


def full_activation_anchor() -> dict:
    actions = [
        {
            "ts": "2026-01-02T00:00:00+00:00",
            "signal_ts": "2026-01-01T00:00:00+00:00",
            "from_side": 0,
            "target_side": 1,
            "reason": "fresh_cross_long",
            "fills": 1,
        },
        {
            "ts": "2026-01-03T00:00:00+00:00",
            "signal_ts": "2026-01-02T00:00:00+00:00",
            "from_side": 1,
            "target_side": -1,
            "reason": "held_arm_band_confirm_short_overbought",
            "fills": 2,
        },
        {
            "ts": "2026-01-04T00:00:00+00:00",
            "signal_ts": "2026-01-03T00:00:00+00:00",
            "from_side": -1,
            "target_side": 0,
            "reason": "short_rsi_take_profit",
            "fills": 1,
        },
        {
            "ts": "2026-01-05T00:00:00+00:00",
            "signal_ts": "2026-01-04T00:00:00+00:00",
            "from_side": 0,
            "target_side": -1,
            "reason": "fresh_cross_short",
            "fills": 1,
        },
        {
            "ts": "2026-01-06T00:00:00+00:00",
            "signal_ts": "2026-01-05T00:00:00+00:00",
            "from_side": -1,
            "target_side": 0,
            "reason": "short_slope_loss",
            "fills": 1,
        },
    ]
    confirm_decision = {
        "signal_ts": "2026-01-02T00:00:00+00:00",
        "from_side": 1,
        "target_side": -1,
        "reason": "held_arm_band_confirm_short_overbought",
        "fills": 2,
    }
    rows = [
        {"ts": "2026-01-01T00:00:00+00:00", "slope_atr": 0.03},
        {"ts": "2026-01-02T00:00:00+00:00", "slope_atr": -0.04},
        {"ts": "2026-01-03T00:00:00+00:00", "slope_atr": -0.01},
        {"ts": "2026-01-04T00:00:00+00:00", "slope_atr": -0.05},
        {"ts": "2026-01-05T00:00:00+00:00", "slope_atr": 0.01},
    ]
    return {
        "id": "CHAMPION_FULL",
        "label": "IGNORED",
        "config": {
            "entry_slope_required": True,
            "slope_min_atr": 0.02,
            "hold_slope_exit_enabled": True,
            "tolerance_atr": 0.75,
            "direct_reversal_enabled": True,
            "arm_expiry_days": 1,
            "short_rsi_exit_enabled": True,
            "overbought_mode": "slope_or_memory",
        },
        "actions": actions,
        "state_trace": {
            "events": [
                {
                    "event": "arm_create",
                    "ts": "2026-01-02T00:00:00+00:00",
                    "index": 1,
                    "armed_side": -1,
                    "armed_overbought_qualified": True,
                },
                {
                    "event": "arm_confirm",
                    "ts": "2026-01-02T00:00:00+00:00",
                    "index": 1,
                    "armed_side": -1,
                    "armed_overbought_qualified": True,
                    "decision": confirm_decision,
                },
            ],
            "rows": rows,
        },
        "path": [{"equity": 999.0, "upper_band": 999.0}],
        "path_hash": "ignored-display-path",
    }


def test_champion_module_activation_counts_every_required_mechanism() -> None:
    result = EVIDENCE.champion_module_activation(full_activation_anchor())

    assert result["counts"] == {
        "fresh_cross_rooted_entries": 3,
        "arm_create": 1,
        "arm_confirm": 1,
        "entry_slope_qualified_decisions": 3,
        "held_band_confirms": 1,
        "slope_loss_exits": 1,
        "short_rsi_take_profit_exits": 1,
        "overbought_qualified_decisions": 1,
        "atomic_reversals": 1,
    }
    assert result["all_applicable_module_gates_pass"] is True
    assert all(
        gate["pass"] is True
        for oat_id, gate in result["gate_evidence"].items()
        if oat_id != "CHAMPION_FULL" and gate["applicable"]
    )
    assert result["source_contract"]["uses_display_path"] is False
    assert result["source_contract"]["uses_trial_id_or_label"] is False


def _remove_activation(anchor: dict, oat_id: str) -> None:
    if oat_id == "CHAMPION_PERSISTENT_REGIME":
        for action in anchor["actions"]:
            if action["target_side"] != 0:
                action["reason"] = "persistent_regime_long"
    elif oat_id == "CHAMPION_NO_ARMED":
        anchor["state_trace"]["events"] = []
    elif oat_id == "CHAMPION_NO_ENTRY_SLOPE":
        for row in anchor["state_trace"]["rows"]:
            row["slope_atr"] = 0.0
    elif oat_id == "CHAMPION_NO_SLOPE_LOSS":
        anchor["actions"] = [
            row for row in anchor["actions"] if "slope_loss" not in row["reason"]
        ]
    elif oat_id == "CHAMPION_NO_BAND":
        anchor["actions"] = [
            row
            for row in anchor["actions"]
            if not row["reason"].startswith("held_arm_band_confirm_")
        ]
    elif oat_id == "CHAMPION_NO_RSI_TP":
        anchor["actions"] = [
            row
            for row in anchor["actions"]
            if row["reason"] != "short_rsi_take_profit"
        ]
    elif oat_id == "CHAMPION_NO_OVERBOUGHT":
        for action in anchor["actions"]:
            action["reason"] = action["reason"].replace("_overbought", "")
        for event in anchor["state_trace"]["events"]:
            event["armed_overbought_qualified"] = False
            if "decision" in event:
                event["decision"]["reason"] = event["decision"]["reason"].replace(
                    "_overbought", ""
                )
    elif oat_id == "CHAMPION_NO_REVERSAL":
        for action in anchor["actions"]:
            if action["from_side"] != 0 and action["target_side"] != 0:
                action["target_side"] = 0
                action["fills"] = 1
    else:  # pragma: no cover - guards the test's exhaustive mapping
        raise AssertionError(oat_id)


@pytest.mark.parametrize(
    "oat_id",
    [
        "CHAMPION_PERSISTENT_REGIME",
        "CHAMPION_NO_ARMED",
        "CHAMPION_NO_ENTRY_SLOPE",
        "CHAMPION_NO_SLOPE_LOSS",
        "CHAMPION_NO_BAND",
        "CHAMPION_NO_RSI_TP",
        "CHAMPION_NO_OVERBOUGHT",
        "CHAMPION_NO_REVERSAL",
    ],
)
def test_each_champion_module_gate_fails_when_its_activation_is_absent(
    oat_id: str,
) -> None:
    anchor = full_activation_anchor()
    _remove_activation(anchor, oat_id)

    result = EVIDENCE.champion_module_activation(anchor)

    assert result["gate_evidence"][oat_id]["pass"] is False
    assert result["all_applicable_module_gates_pass"] is False


def test_activation_ignores_display_path_and_marks_disabled_modules_inapplicable() -> None:
    anchor = full_activation_anchor()
    first = EVIDENCE.champion_module_activation(anchor)
    anchor["path"] = [{"equity": -123.0, "armed_side": 99}]
    anchor["path_hash"] = "different-display-only-hash"
    second = EVIDENCE.champion_module_activation(anchor)
    assert first == second

    anchor["config"].update(
        {
            "arm_expiry_days": 0,
            "short_rsi_exit_enabled": False,
            "overbought_mode": "disabled",
        }
    )
    disabled = EVIDENCE.champion_module_activation(anchor)
    assert disabled["gate_evidence"]["CHAMPION_NO_ARMED"]["applicable"] is False
    assert disabled["gate_evidence"]["CHAMPION_NO_ARMED"]["pass"] is None
    assert disabled["gate_evidence"]["CHAMPION_NO_RSI_TP"]["applicable"] is False
    assert disabled["gate_evidence"]["CHAMPION_NO_OVERBOUGHT"]["applicable"] is False
