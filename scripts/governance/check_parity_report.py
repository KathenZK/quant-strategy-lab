#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = {
    "schema_version",
    "strategy_id",
    "runner_kind",
    "runner_commit",
    "lab_commit",
    "snapshot_id",
    "gate_level",
    "command",
    "window",
    "trade_path",
    "conclusion",
    "blockers",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    for path in args.reports:
        report = json.loads(path.read_text())
        missing = REQUIRED - report.keys()
        if missing:
            errors.append(f"{path}: missing {sorted(missing)}")
        trade_path = report.get("trade_path", {})
        if report.get("conclusion") == "PASS":
            if report.get("gate_level") != "parity":
                errors.append(f"{path}: PASS report gate_level must be parity")
            if trade_path.get("path_mismatches") != 0:
                errors.append(f"{path}: PASS report has path mismatches")
            if trade_path.get("reference_trades") != trade_path.get("runtime_trades"):
                errors.append(f"{path}: PASS report trade counts differ")
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print(f"validated {len(args.reports)} parity reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
