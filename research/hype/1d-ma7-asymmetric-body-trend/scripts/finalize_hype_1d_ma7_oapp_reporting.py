"""Recover OAPP final reporting after the frozen renderer rejects terminal-open trades."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any


RESEARCH_PATH = Path(__file__).with_name("research_hype_1d_ma7_opportunity_aware_profit_protection.py")


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def append_terminal_open_candle(candles: list[dict[str, Any]], context: Any) -> list[dict[str, Any]]:
    terminal_ts = context.book.terminal_ts
    terminal_day = terminal_ts.isoformat()[:10]
    if candles and str(candles[-1]["ts"])[:10] == terminal_day:
        return candles
    hourly = context.market.hourly
    match = hourly.loc[hourly["ts"] == terminal_ts]
    if len(match) != 1:
        raise RuntimeError("unique terminal-open hourly row required")
    terminal_open = float(match.iloc[0]["open"])
    return [
        *candles,
        {
            "ts": terminal_ts.isoformat(),
            "open": terminal_open,
            "high": terminal_open,
            "low": terminal_open,
            "close": terminal_open,
            "ma7": float(context.features.ma7[-1]),
            "display_only_terminal_open": True,
        },
    ]


def main() -> None:
    research = load_module(RESEARCH_PATH, "hype_oapp_reporting_research")
    manifest, champion, config, runtime = research.load_champion()
    holdout, holdout_sha = research.read_locked(research.HOLDOUT_PATH)
    leverage, leverage_sha = research.read_locked(research.LEVERAGE_PATH)
    if holdout.get("h_accessed") is not True or holdout.get("hard_gate") != "FAIL":
        raise RuntimeError("report recovery is only for the locked OAPP H FAIL")
    if research.FINAL_PATH.exists() or research.sidecar(research.FINAL_PATH).exists() or research.HTML_PATH.exists() or research.sidecar(research.HTML_PATH).exists():
        raise RuntimeError("final reporting artifact already exists")
    engine, risk, adapter, renderer, context = runtime
    full_control = research.run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=(0, 432), config=None, retain=True)
    full_one_x = research.run_one(engine=engine, risk=risk, adapter=adapter, context=context, window=(0, 432), config=config, retain=True)
    h_rows = [
        {"id": "EXACT_V4_1X", "status": holdout["control"]["status"], "metrics": holdout["control"]["metrics"]},
        {"id": "OAPP_1X", "status": holdout["one_x"]["status"], "metrics": holdout["one_x"]["metrics"]},
    ]
    full_rows = [
        {"id": "EXACT_V4_1X", "status": "PASS", "metrics": full_control["metrics"]},
        {"id": "OAPP_1X", "status": "PASS", "metrics": full_one_x["metrics"]},
    ]
    full_leverage = []
    for frozen, hrow in zip(leverage["rows"], holdout["leverage_rows"]):
        spec = engine.LeverageSpec(**frozen["spec"])
        full = research.safe_run(engine=engine, risk=risk, adapter=adapter, context=context, window=(0, 432), config=config, leverage_spec=spec)
        h_rows.append({"id": spec.id, "status": hrow["base"]["status"], "metrics": hrow["base"].get("metrics")})
        full_rows.append({"id": spec.id, "status": full["status"], "metrics": full.get("metrics")})
        full_leverage.append({"spec": frozen["spec"], "run": full})
    candles = append_terminal_open_candle(renderer.candles_from_context(context), context)
    document, html_audit = renderer.build_document(
        title=f"OAPP {champion['arm_id']} vs exact V4 — full path (H FAIL)",
        candles=candles,
        candidate=full_one_x,
        control=full_control,
    )
    html_write = renderer.write_locked(research.HTML_PATH, document)
    recovery_sha = research.sha256(Path(__file__).resolve())
    payload = {
        "schema": "hype-oapp-final-v1-report-recovery",
        "status": "FAIL",
        "hard_gate": "FAIL",
        "champion_arm_id": champion["arm_id"],
        "manifest_sha256": research.sha256(research.MANIFEST_PATH),
        "champion_sha256": research.sha256(research.CHAMPION_PATH),
        "holdout_sha256": holdout_sha,
        "leverage_sha256": leverage_sha,
        "holdout": {
            "control": holdout["control"]["metrics"],
            "one_x": holdout["one_x"]["metrics"],
            "gate": holdout["one_x_gate"],
            "opportunity_audit": holdout["opportunity_audit"],
        },
        "full": {"control": full_control["metrics"], "one_x": full_one_x["metrics"], "leverage": full_leverage},
        "h_frontier": research._frontier(h_rows),
        "full_frontier": research._frontier(full_rows),
        "h_frontier_rows": h_rows,
        "full_frontier_rows": full_rows,
        "html": {**html_audit, **html_write, "terminal_open_display_point": candles[-1]},
        "report_recovery": {
            "script": str(Path(__file__).resolve()),
            "script_sha256": recovery_sha,
            "reason": "Frozen renderer rejected the terminal-open trade date because only 432 complete daily candles exist; one display-only terminal-open point was appended without changing any strategy metric or path.",
            "strategy_pins_unchanged": manifest["pins"] == champion["implementation_pins"],
        },
        "h_accessed": True,
        "no_retry": True,
        "no_v5": True,
        "not_promoted": True,
    }
    research.assert_pins(manifest["pins"])
    research.write_locked(research.FINAL_PATH, payload)
    print({"status": payload["status"], "final": str(research.FINAL_PATH), "html": str(research.HTML_PATH)})


if __name__ == "__main__":
    main()

