#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy-id", required=True)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--window", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--status-json", type=Path, required=True)
    parser.add_argument("--trades-json", type=Path, required=True)
    parser.add_argument("--events-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    status = json.loads(args.status_json.read_text())
    trades = json.loads(args.trades_json.read_text()).get("trades", [])
    events = json.loads(args.events_json.read_text()).get("events", [])
    closed = [trade for trade in trades if trade.get("status") == "closed"]
    opened = len(trades)
    cycle_errors = [event for event in events if event.get("event_type") == "cycle_error"]
    text = f"""# {args.strategy_id} Runner Tracking

- Instance: `{args.instance_id}`
- Observation window: `{args.window}`
- Runner config: `{args.config}`
- Source status: `{args.status_json}`
- Source trades: `{args.trades_json}`
- Source events: `{args.events_json}`

## Summary

- Trade rows: `{opened}`
- Closed trades: `{len(closed)}`
- Cycle errors: `{len(cycle_errors)}`
- Health rows: `{len(status.get('health', []))}`

## Required reconciliation

This generated summary is not a match decision. Before promotion, append expected
research signal/entry/exit timestamps, actual order/fill IDs, side, quantity,
prices, fees, slippage and a per-trade match/mismatch conclusion.

## Decision

`keep / stop / adjust`: pending human review.
"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
