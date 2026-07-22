"""核对 HYPE-EMA-TB-V35.1 Python 冻结逐笔与 quant-runner replay。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path("research/hype/15m-ema-trend-breakout")
DEFAULT_REFERENCE = ROOT / "artifacts/hype_ema_tb_v35_1_2026-07-20_trades.csv"
DEFAULT_RUNTIME = ROOT / "artifacts/HYPE-EMA-TB-V35.1_runner_replay_2026-07-20.json"
DEFAULT_OUTPUT = ROOT / "artifacts/HYPE-EMA-TB-V35.1_parity_2026-07-20.json"

REASON_MAP = {
    "target": "take_profit",
    "target_gap_or_open": "take_profit",
    "stop_market": "stop_loss",
    "stop_gap_open": "stop_loss",
    "indicator_exit": "indicator_exit",
    "timeout": "max_hold",
    "time_open": "max_hold",
}
FLOAT_FIELDS = ("entry_price", "exit_price", "allocation")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runner-commit", default="2c5df6a+uncommitted")
    parser.add_argument("--lab-commit", default="97f7d4c+uncommitted")
    return parser.parse_args()


def iso_utc(value: Any) -> str:
    return pd.Timestamp(value).tz_convert("UTC").isoformat()


def normalized_reference(path: Path) -> list[dict[str, Any]]:
    frame = pd.read_csv(path)
    frame = frame.loc[frame["variant"] == "v35_1"].reset_index(drop=True)
    return [
        {
            "entry_ts": iso_utc(row.entry_ts),
            "exit_ts": iso_utc(row.exit_ts),
            "side": int(row.direction),
            "entry_price": float(row.entry_price),
            "exit_price": float(row.exit_price),
            "allocation": float(row.allocation),
            "exit_reason": str(row.exit_reason),
        }
        for row in frame.itertuples(index=False)
    ]


def normalized_runtime(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        {
            "entry_ts": iso_utc(row["entry_ts"]),
            "exit_ts": iso_utc(row["exit_ts"]),
            "side": int(row["side"]),
            "entry_price": float(row["entry_price"]),
            "exit_price": float(row["exit_price"]),
            "allocation": float(row["allocation"]),
            "exit_reason": REASON_MAP.get(row["exit_reason"], row["exit_reason"]),
        }
        for row in payload["trades"]
    ]
    return payload, rows


def mismatch_fields(
    reference: dict[str, Any], runtime: dict[str, Any], tolerance: float = 1e-9
) -> list[str]:
    mismatches = []
    for field in ("entry_ts", "exit_ts", "side", "exit_reason"):
        if reference[field] != runtime[field]:
            mismatches.append(field)
    for field in FLOAT_FIELDS:
        if abs(reference[field] - runtime[field]) > tolerance:
            mismatches.append(field)
    return mismatches


def main() -> None:
    args = parse_args()
    reference = normalized_reference(args.reference)
    runtime_payload, runtime = normalized_runtime(args.runtime)
    mismatch_count = abs(len(reference) - len(runtime))
    first_mismatches: list[dict[str, Any]] = []
    for index, (expected, actual) in enumerate(zip(reference, runtime, strict=False)):
        fields = mismatch_fields(expected, actual)
        if fields:
            mismatch_count += 1
            if len(first_mismatches) < 5:
                first_mismatches.append(
                    {
                        "index": index,
                        "fields": fields,
                        "reference": expected,
                        "runtime": actual,
                    }
                )

    conclusion = "PASS" if mismatch_count == 0 else "FAIL"
    report = {
        "schema_version": "1.0",
        "strategy_id": "HYPE-EMA-TB-V35.1",
        "runner_kind": "hype_ema_tb",
        "runner_commit": args.runner_commit,
        "lab_commit": args.lab_commit,
        "snapshot_id": "hype-ema-tb-v35-1-2026-07-17",
        "gate_level": "parity",
        "command": (
            "quant-runner replay-dry-run --name hype-ema-tb-v35-1-dry-run "
            "--limit 40000 --end-ts 2026-07-17T08:45:00Z"
        ),
        "window": {
            "start": runtime_payload["replay_start_ts"],
            "end": runtime_payload["replay_end_ts"],
            "bars": int(runtime_payload["bars_replayed"]),
        },
        "trade_path": {
            "reference_trades": len(reference),
            "runtime_trades": len(runtime),
            "path_mismatches": mismatch_count,
            "fields_compared": [
                "entry_ts",
                "exit_ts",
                "side",
                "entry_price",
                "exit_price",
                "allocation",
                "exit_reason",
            ],
        },
        "conclusion": conclusion,
        "blockers": [
            "Rust replay 尚未计入 funding，因此权益指标不作为本次逐笔路径 parity 字段。",
            "live 保护单 workingType、真实成交滑点与线上重启恢复不在离线 parity 覆盖范围。",
        ],
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if first_mismatches:
        print(json.dumps(first_mismatches, ensure_ascii=False, indent=2))
    print(
        f"{conclusion}: reference={len(reference)} runtime={len(runtime)} "
        f"path_mismatches={mismatch_count} -> {args.output}"
    )
    if conclusion != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
