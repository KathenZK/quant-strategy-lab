from __future__ import annotations

from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "render_hype_1d_ma7_intent_optimization_trade_path.py"
)


def _load_renderer():
    spec = importlib.util.spec_from_file_location(
        "hype_1d_ma7_intent_optimization_trade_path", RENDERER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RENDERER = _load_renderer()


class _DocumentAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.external_resources: list[tuple[str, str]] = []
        self.scripts = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(str(attributes["id"]))
        if tag == "script":
            self.scripts += 1
        for name in ("src", "href"):
            if attributes.get(name):
                self.external_resources.append((tag, str(attributes[name])))


def _point(
    day: int,
    *,
    side: int,
    equity: float,
    terminal: bool = False,
    armed_side: int = 0,
    pending_reason: str = "",
    band_width: float = 1.5,
) -> dict[str, object]:
    open_price = 100.0 + day
    return {
        "ts": f"2026-01-{day + 1:02d}T00:00:00+00:00",
        "open": open_price,
        "high": open_price + (0.0 if terminal else 2.0),
        "low": open_price - (0.0 if terminal else 1.0),
        "close": open_price + (0.0 if terminal else 1.0),
        "ma7": None if terminal else open_price - 0.25,
        "atr7": None if terminal else 2.0,
        "rsi6": None if terminal else 45.0 + day,
        "slope_atr": None if terminal else 0.01 * (day - 1),
        "upper_band": None if terminal else open_price - 0.25 + band_width,
        "lower_band": None if terminal else open_price - 0.25 - band_width,
        "equity": equity,
        "side": side,
        "armed_side": armed_side,
        "pending_reason": pending_reason,
        "terminal": terminal,
    }


def _trade(
    trade_id: str,
    side: str,
    entry_day: int,
    exit_day: int,
    net_return: float,
    net_pnl: float,
) -> dict[str, object]:
    return {
        "trade_id": trade_id,
        "side": side,
        "entry_signal_ts": f"2026-01-{entry_day:02d}T00:00:00+00:00",
        "entry_ts": f"2026-01-{entry_day + 1:02d}T00:00:00+00:00",
        "exit_ts": f"2026-01-{exit_day + 1:02d}T00:00:00+00:00",
        "entry_price": 100.0 + entry_day,
        "exit_price": 100.0 + exit_day,
        "entry_reason": "fresh_ma7_cross",
        "exit_reason": "terminal_flatten" if exit_day == 5 else "armed_reversal",
        "net_return": net_return,
        "net_pnl": net_pnl,
        "gross_return": net_return + 0.0028,
        "mfe_return": max(net_return, 0.04),
        "mae_return": min(net_return, -0.01),
        "giveback_return": max(0.0, 0.04 - net_return),
    }


def _bundle() -> dict[str, object]:
    candidate_path = [
        _point(0, side=0, equity=1.0, pending_reason="fresh_long"),
        _point(1, side=1, equity=1.01),
        _point(
            2,
            side=1,
            equity=1.04,
            armed_side=-1,
            pending_reason="armed_short_confirm",
        ),
        _point(3, side=-1, equity=1.05),
        _point(4, side=-1, equity=1.07),
        _point(5, side=0, equity=1.08, terminal=True),
    ]
    canonical_v4_path = [
        _point(0, side=0, equity=1.0, band_width=1.0),
        _point(1, side=0, equity=1.0, band_width=1.0),
        _point(2, side=1, equity=1.005, band_width=1.0),
        _point(3, side=1, equity=1.015, band_width=1.0),
        _point(4, side=1, equity=1.025, band_width=1.0),
        _point(5, side=0, equity=1.03, terminal=True, band_width=1.0),
    ]
    # The registered V4 engine has a deliberately different retained schema.
    v4_path = [
        {
            "ts": point["ts"],
            "pre_action_equity": point["equity"],
            "post_action_equity": point["equity"],
            "close_equity": point["equity"],
            "favorable_equity": point["equity"],
            "adverse_equity": point["equity"],
            "position": point["side"],
            "action": "terminal_flatten" if point["terminal"] else "hold",
        }
        for point in canonical_v4_path
    ]
    candidate_trades = [
        _trade("CAND-001", "long", 1, 3, 0.03, 0.03),
        _trade("CAND-002", "short", 3, 5, 0.0285714286, 0.03),
    ]
    v4_trade = _trade("V4-001", "long", 2, 5, 0.03, 0.03)
    for field in (
        "trade_id",
        "entry_signal_ts",
        "entry_reason",
        "net_pnl",
        "gross_return",
        "mfe_return",
        "mae_return",
        "giveback_return",
    ):
        v4_trade.pop(field)
    v4_trades = [v4_trade]
    trace_rows = []
    for index, point in enumerate(candidate_path[:-1]):
        armed = int(point["armed_side"])
        trace_rows.append(
            {
                "index": index,
                "ts": point["ts"],
                "side": point["side"],
                "armed_side": armed,
                "armed_age": 0,
                "armed_origin": "fresh_down_cross" if armed else None,
                "armed_overbought_qualified": bool(armed),
                "slope_loss_run": 1 if index == 4 else 0,
                "short_rsi_run": 1 if index == 4 else 0,
                "pending_reason": point["pending_reason"] or None,
                "pending_from_side": 1 if index == 2 else None,
                "pending_target_side": -1 if index == 2 else None,
                "pending_fills": 2 if index == 2 else None,
                "open_fill_reason": (
                    "fresh_long"
                    if index == 1
                    else "armed_short_confirm"
                    if index == 3
                    else None
                ),
                "relation": 1,
                "slope_atr": point["slope_atr"],
                "rsi6": point["rsi6"],
                "complete": True,
            }
        )
    state_trace = {
        "start_index": 0,
        "active_start": 0,
        "terminal_index": 5,
        "rows": trace_rows,
        "events": [
            {"event": "decision_signal", "ts": candidate_path[0]["ts"], "index": 0},
            {"event": "arm_create", "ts": candidate_path[2]["ts"], "index": 2},
            {"event": "terminal_flatten", "ts": candidate_path[-1]["ts"], "index": 5},
        ],
        "activation_counts": {
            "decision_signal": 2,
            "decision_fills": 3,
            "arm_create": 1,
            "arm_confirm": 1,
            "slope_loss_day": 1,
            "short_rsi_day": 1,
        },
        "terminal": {
            "ts": candidate_path[-1]["ts"],
            "open": candidate_path[-1]["open"],
            "pending_suppressed": False,
            "pending": None,
            "state_before": {
                "side": -1,
                "armed_side": 0,
                "armed_age": 0,
                "armed_origin": None,
                "armed_overbought_qualified": False,
                "slope_loss_run": 1,
                "short_rsi_run": 1,
            },
            "state_after": {
                "side": 0,
                "armed_side": 0,
                "armed_age": 0,
                "armed_origin": None,
                "armed_overbought_qualified": False,
                "slope_loss_run": 0,
                "short_rsi_run": 0,
            },
        },
    }
    return {
        "candidate_path": candidate_path,
        "v4_path": v4_path,
        "candidate_trades": candidate_trades,
        "v4_trades": v4_trades,
        "candidate_metrics": {
            "label": "SYNTHETIC-CANDIDATE",
            "equity_multiple": 1.08,
            "net_return_pct": 8.0,
            "max_drawdown_pct": -2.0,
            "closed_trades": 2,
            "long_trades": 1,
            "short_trades": 1,
            "win_rate": 1.0,
            "sharpe": 1.2,
            "profit_factor": 2.4,
            "exposure_pct": 80.0,
            "cost": 0.004,
            "funding_payment": 0.001,
        },
        "v4_metrics": {
            "label": "EXACT-V4",
            "equity_multiple": 1.03,
            "net_return_pct": 3.0,
            "max_drawdown_pct": -4.0,
            "closed_trades": 1,
            "long_trades": 1,
            "short_trades": 0,
            "win_rate": 1.0,
            "sharpe": 0.7,
            "profit_factor": 1.5,
            "exposure_pct": 60.0,
            "cost": 0.002,
            "funding_payment": 0.0,
        },
        "state_trace": state_trace,
        "title": "Synthetic HYPE MA7 intent path",
        "meta": {"window": "synthetic-only", "gate": "PASS"},
    }


def _embedded_payload(document: str) -> dict[str, object]:
    match = re.search(
        r"/\*PAYLOAD_START\*/const DATA=(.*?);/\*PAYLOAD_END\*/",
        document,
        flags=re.DOTALL,
    )
    assert match is not None
    return json.loads(match.group(1))


def test_renderer_writes_openable_self_contained_comparison(tmp_path: Path) -> None:
    output = tmp_path / "intent-path.html"
    bundle = _bundle()
    document_bytes, build_audit = RENDERER.build_trade_path_html_document(
        **bundle
    )

    assert isinstance(document_bytes, bytes)
    assert not output.exists()
    assert build_audit["sha256"] == hashlib.sha256(document_bytes).hexdigest()
    assert build_audit["bytes"] == len(document_bytes)
    assert build_audit["candidate_trade_links"] == 2
    assert build_audit["exact_v4_trade_links"] == 1
    assert build_audit["status"] == "PASS"

    result = RENDERER.render_trade_path_html(output, **bundle)

    assert output.is_file()
    assert output.read_bytes() == document_bytes
    assert result == {"path": str(output.resolve()), **build_audit}
    document = output.read_text(encoding="utf-8")
    assert document.startswith("<!doctype html>")
    assert document.rstrip().endswith("</html>")
    assert "__PAYLOAD__" not in document
    assert "https://" not in document and "http://" not in document
    assert "fetch(" not in document and "XMLHttpRequest" not in document
    assert result["status"] == "PASS"
    assert result["candidate_trade_links"] == 2
    assert result["exact_v4_trade_links"] == 1

    parser = _DocumentAudit()
    parser.feed(document)
    assert parser.scripts == 1
    assert parser.external_resources == []
    assert {
        "strategySelect",
        "priceChart",
        "slopeChart",
        "rsiChart",
        "stateChart",
        "equityChart",
        "tradeRows",
    } <= parser.ids

    payload = _embedded_payload(document)
    assert set(payload["strategies"]) == {"candidate", "exact_v4"}
    assert payload["audit"] == {
        "sharedMarketRows": 6,
        "candidateTradeLinks": 2,
        "exactV4TradeLinks": 1,
        "allTradeLinksRenderable": True,
        "pathTradeTraceConsistency": "PASS",
        "exactV4SourceSchema": (
            "exact_v4_legacy_ledger+shared_market_from_candidate"
        ),
        "exactV4MarketSource": "shared_market_from_candidate",
    }
    candidate = payload["strategies"]["candidate"]
    assert all(trade["link"]["renderable"] for trade in candidate["trades"])
    assert candidate["path"][2]["armedOrigin"] == "fresh_down_cross"
    assert candidate["path"][2]["armedOverboughtQualified"] is True
    assert candidate["path"][4]["slopeLossRun"] == 1
    assert candidate["path"][4]["shortRsiRun"] == 1
    assert payload["status"]["promotion"] == "not promoted"
    assert payload["status"]["timezone"] == "UTC"
    assert payload["strategies"]["exact_v4"]["trades"][0]["id"] == "EXACT-V4-001"
    assert payload["strategies"]["exact_v4"]["trades"][0]["netPnl"] is None


@pytest.mark.parametrize("drift", ["trace", "trade"])
def test_renderer_fails_closed_on_inconsistent_bundle(
    tmp_path: Path, drift: str
) -> None:
    bundle = deepcopy(_bundle())
    if drift == "trace":
        bundle["state_trace"]["rows"][3]["side"] = 1
    else:
        bundle["candidate_trades"][0]["exit_price"] = 999.0
    output = tmp_path / f"bad-{drift}.html"

    with pytest.raises(ValueError):
        RENDERER.render_trade_path_html(output, **bundle)
    assert not output.exists()


def test_renderer_refuses_to_overwrite_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "locked.html"
    output.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        RENDERER.render_trade_path_html(output, **_bundle())
    assert output.read_text(encoding="utf-8") == "keep"
