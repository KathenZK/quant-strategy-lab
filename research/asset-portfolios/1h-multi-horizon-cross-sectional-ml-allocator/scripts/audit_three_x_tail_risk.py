from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
REVEAL_NOT_BEFORE = pd.Timestamp("2026-10-20T21:05:00Z")
EXPECTED_MASTER_SHA256 = (
    "64ee12688980673aa2cd348a961553c89d246d1f338eba0192ddcbfdd095fe11"
)
MASTER_FREEZE = FAMILY_DIR / "artifacts/freeze/bin-1h-mhcsml-v1-freeze-r4.json"
THREE_X_RISK_CONTRACT = FAMILY_DIR / (
    "artifacts/freeze/bin-1h-mhcsml-v1-three-x-risk-contract-r4.json"
)
FINAL_ADJUDICATION = FAMILY_DIR / (
    "artifacts/prospective_oos/reveal/final_adjudication.json"
)
REVEAL_REPORT = FAMILY_DIR / (
    "artifacts/prospective_oos/reveal/one_time_oos_report.json"
)
REVEALED_LEGS = FAMILY_DIR / (
    "artifacts/prospective_oos/reveal/revealed_legs.parquet"
)
REVEALED_DECISIONS = FAMILY_DIR / (
    "artifacts/prospective_oos/reveal/revealed_decisions.parquet"
)
OUTPUT_DIR = FAMILY_DIR / "artifacts/prospective_oos/reveal/three_x_tail_risk"
SUMMARY_JSON = OUTPUT_DIR / "summary.json"
SCENARIOS_CSV = OUTPUT_DIR / "scenarios.csv"
HOURLY_PARQUET = OUTPUT_DIR / "hourly_scenarios.parquet"
MARK_INPUT_PARQUET = OUTPUT_DIR / "input_mark_path.parquet"
FUNDING_INPUT_PARQUET = OUTPUT_DIR / "input_funding_events.parquet"
EVIDENCE_RECEIPT = OUTPUT_DIR / "evidence_receipt.json"
EVIDENCE_RECEIPT_SHA = OUTPUT_DIR / "evidence_receipt.sha256"
REPORT_MD = FAMILY_DIR / (
    "diagnostics/binance-1h-mhcsml-v1-r4-three-x-tail-risk.md"
)
MARK_GLOB = ROOT / (
    "data/normalized/mark_price_klines/exchange=binance/market_type=perp/"
    "timeframe=1h/**/*.parquet"
)
FUNDING_GLOB = ROOT / (
    "data/normalized/funding_rates/exchange=binance/market_type=perp/**/*.parquet"
)
LEVERAGE_MULTIPLIER = 3.0
ONE_SIDE_COST = 0.0014
COST_MULTIPLIERS = (1.0, 1.5)
MAINTENANCE_MARGIN_RATES = (0.005, 0.010, 0.025)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the authorized three-x hourly mark and squeeze-risk audit."
    )
    parser.add_argument("--now", help="UTC override; only valid with --validate-only.")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_utc(value: str | pd.Timestamp) -> pd.Timestamp:
    result = pd.Timestamp(value)
    return result.tz_localize("UTC") if result.tzinfo is None else result.tz_convert("UTC")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def validate_three_x_contract() -> dict[str, Any]:
    if not MASTER_FREEZE.is_file() or sha256(MASTER_FREEZE) != EXPECTED_MASTER_SHA256:
        raise RuntimeError("master freeze SHA mismatch")
    contract = load_json(THREE_X_RISK_CONTRACT)
    if contract.get("status") != "PASS":
        raise RuntimeError("three-x risk contract is not frozen PASS")
    authorization = contract.get("authorization", {})
    if authorization.get("prospective_oos_outcomes_read") is not False:
        raise RuntimeError("three-x risk contract was not frozen outcome-blind")

    semantics = contract.get("frozen_semantics", {})
    expected_semantics = {
        "leverage_multiplier": LEVERAGE_MULTIPLIER,
        "base_decision_sleeve_exposure": 0.03125,
        "three_x_decision_sleeve_exposure": 0.09375,
        "base_max_scheduled_gross": 0.375,
        "three_x_max_scheduled_gross": 1.125,
        "cost_multipliers": list(COST_MULTIPLIERS),
        "maintenance_margin_rates": list(MAINTENANCE_MARGIN_RATES),
        "intrahour_short_stress": (
            "simultaneous mark-price high across all open short legs"
        ),
        "funding_interval": "entry_time < funding_ts <= exit_time",
    }
    if semantics != expected_semantics:
        raise RuntimeError("three-x frozen semantics differ from the implementation")

    expected_gates = {
        "all_scenarios_no_liquidation": True,
        "conservative_stress_return_positive": True,
        "all_max_drawdown_lte": 0.5,
        "all_intrahour_drawdown_lte": 0.6,
        "all_margin_buffers_positive": True,
        "all_actual_gross_lte": 1.5,
    }
    if contract.get("risk_gates") != expected_gates:
        raise RuntimeError("three-x risk gates differ from the implementation")

    frozen_files = contract.get("frozen_files", {})
    if not frozen_files:
        raise RuntimeError("three-x risk contract has no frozen files")
    for name, item in frozen_files.items():
        relative = Path(str(item.get("path", "")))
        candidate = (ROOT / relative).resolve()
        try:
            candidate.relative_to(ROOT.resolve())
        except ValueError as error:
            raise RuntimeError(f"three-x frozen path escapes repository: {name}") from error
        expected_sha = item.get("sha256")
        if not candidate.is_file() or sha256(candidate) != expected_sha:
            raise RuntimeError(f"three-x frozen file hash mismatch: {name}")
    return contract


def assert_authorized(now: pd.Timestamp) -> dict[str, Any]:
    if now < REVEAL_NOT_BEFORE:
        raise RuntimeError(f"three-x audit remains sealed until {REVEAL_NOT_BEFORE.isoformat()}")
    if not FINAL_ADJUDICATION.exists():
        raise RuntimeError("base final adjudication is missing")
    adjudication = load_json(FINAL_ADJUDICATION)
    if adjudication.get("master_freeze_sha256") != EXPECTED_MASTER_SHA256:
        raise RuntimeError("base adjudication master SHA mismatch")
    if adjudication.get("status") != "BASE_STRATEGY_RESEARCH_GATES_PASS":
        raise RuntimeError("three-x audit is not authorized because base gates failed")
    if adjudication.get("three_x_evaluation_authorized") is not True:
        raise RuntimeError("base adjudication did not authorize three-x research")
    if adjudication.get("failed_gates"):
        raise RuntimeError("base adjudication contains failed gates")
    return adjudication


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def load_revealed_legs(adjudication: dict[str, Any]) -> pd.DataFrame:
    reveal = load_json(REVEAL_REPORT)
    if sha256(REVEAL_REPORT) != adjudication.get("reveal_report_sha256"):
        raise RuntimeError("revealed report SHA differs from final adjudication")
    legs_spec = reveal.get("outputs", {}).get("legs", {})
    decisions_spec = reveal.get("outputs", {}).get("decisions", {})
    if legs_spec.get("path") != str(REVEALED_LEGS.relative_to(ROOT)):
        raise RuntimeError("revealed legs path mismatch")
    if decisions_spec.get("path") != str(REVEALED_DECISIONS.relative_to(ROOT)):
        raise RuntimeError("revealed decisions path mismatch")
    if not REVEALED_LEGS.is_file() or sha256(REVEALED_LEGS) != legs_spec.get("sha256"):
        raise RuntimeError("revealed legs SHA mismatch")
    if not REVEALED_DECISIONS.is_file() or sha256(
        REVEALED_DECISIONS
    ) != decisions_spec.get("sha256"):
        raise RuntimeError("revealed decisions SHA mismatch")
    legs = pd.read_parquet(REVEALED_LEGS)
    for column in ("ts", "entry_time", "planned_exit_time"):
        legs[column] = pd.to_datetime(legs[column], utc=True)
    legs = legs.loc[legs["strategy"].eq("r4")].copy()
    required = {
        "symbol",
        "entry_time",
        "planned_exit_time",
        "entry_open",
        "exit_open",
        "funding_sum",
        "trade_return",
        "leg_exposure",
    }
    missing = sorted(required - set(legs.columns))
    if missing or legs.empty:
        raise RuntimeError(f"revealed R4 legs are incomplete: {missing}")
    if legs.duplicated(["ts", "symbol"]).any():
        raise RuntimeError("duplicate revealed R4 leg keys")
    return legs.sort_values(["entry_time", "symbol"]).reset_index(drop=True)


def load_mark_path(legs: pd.DataFrame) -> pd.DataFrame:
    symbols = pd.DataFrame({"symbol": sorted(legs["symbol"].unique())})
    start = legs["entry_time"].min()
    end = legs["planned_exit_time"].max()
    connection = duckdb.connect()
    connection.register("requested_symbols", symbols)
    frame = connection.execute(
        f"""
        SELECT ts, symbol, open, high FROM (
            SELECT m.ts, m.symbol, m.open, m.high,
                row_number() OVER (
                    PARTITION BY m.ts, m.symbol
                    ORDER BY CASE
                        WHEN m.source LIKE '%prospective_oos%' THEN 0
                        WHEN m.source LIKE '%freeze_gap%' THEN 1
                        ELSE 2
                    END
                ) AS _rn
            FROM read_parquet(
                '{sql_path(MARK_GLOB)}',
                hive_partitioning=false, union_by_name=true
            ) AS m
            INNER JOIN requested_symbols AS r USING (symbol)
            WHERE m.ts >= TIMESTAMPTZ '{start.isoformat()}'
              AND m.ts <= TIMESTAMPTZ '{end.isoformat()}'
        ) WHERE _rn = 1
        ORDER BY ts, symbol
        """
    ).fetch_df()
    connection.close()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    if frame.duplicated(["ts", "symbol"]).any():
        raise RuntimeError("duplicate mark path keys")
    if frame[["open", "high"]].isna().any().any():
        raise RuntimeError("mark path contains null open/high")
    return frame


def load_funding_events(legs: pd.DataFrame) -> pd.DataFrame:
    symbols = pd.DataFrame({"symbol": sorted(legs["symbol"].unique())})
    start = legs["entry_time"].min()
    end = legs["planned_exit_time"].max()
    connection = duckdb.connect()
    connection.register("requested_symbols", symbols)
    frame = connection.execute(
        f"""
        SELECT ts, symbol, funding_rate FROM (
            SELECT f.ts, f.symbol, f.funding_rate,
                row_number() OVER (
                    PARTITION BY f.ts, f.symbol
                    ORDER BY CASE
                        WHEN f.source LIKE '%prospective_oos%' THEN 0
                        WHEN f.source LIKE '%freeze_gap%' THEN 1
                        ELSE 2
                    END
                ) AS _rn
            FROM read_parquet(
                '{sql_path(FUNDING_GLOB)}',
                hive_partitioning=false, union_by_name=true
            ) AS f
            INNER JOIN requested_symbols AS r USING (symbol)
            WHERE f.ts > TIMESTAMPTZ '{start.isoformat()}'
              AND f.ts <= TIMESTAMPTZ '{end.isoformat()}'
        ) WHERE _rn = 1
        ORDER BY ts, symbol
        """
    ).fetch_df()
    connection.close()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    if frame.duplicated(["ts", "symbol"]).any():
        raise RuntimeError("duplicate funding event keys")
    return frame


def validate_leg_returns(legs: pd.DataFrame, funding: pd.DataFrame) -> float:
    by_symbol = {symbol: group for symbol, group in funding.groupby("symbol")}
    differences: list[float] = []
    for row in legs.itertuples(index=False):
        events = by_symbol.get(row.symbol)
        if events is None:
            event_sum = 0.0
        else:
            mask = events["ts"].gt(row.entry_time) & events["ts"].le(
                row.planned_exit_time
            )
            event_sum = float(events.loc[mask, "funding_rate"].sum())
        if abs(event_sum - float(row.funding_sum)) > 1e-12:
            raise RuntimeError("three-x funding reconstruction differs from reveal")
        expected = 1.0 - float(row.exit_open) / float(row.entry_open) - 0.0028 + event_sum
        differences.append(abs(expected - float(row.trade_return)))
    maximum = max(differences, default=0.0)
    if maximum > 1e-10:
        raise RuntimeError(f"revealed leg-return crosscheck failed: {maximum}")
    return maximum


def mark_values(
    positions: list[dict[str, Any]],
    *,
    ts: pd.Timestamp,
    mark_map: dict[tuple[pd.Timestamp, str], tuple[float, float]],
    use_high: bool,
) -> tuple[float, float]:
    unrealized = 0.0
    mark_notional = 0.0
    index = 1 if use_high else 0
    for position in positions:
        key = (ts, position["symbol"])
        if key not in mark_map:
            raise RuntimeError(f"missing mark path at {ts} for an active position")
        mark = mark_map[key][index]
        entry = position["entry_open"]
        notional = position["notional"]
        unrealized += notional * (1.0 - mark / entry)
        mark_notional += notional * mark / entry
    return unrealized, mark_notional


def simulate_scenario(
    legs: pd.DataFrame,
    marks: pd.DataFrame,
    funding: pd.DataFrame,
    *,
    cost_multiplier: float,
    maintenance_margin_rate: float,
    leverage_multiplier: float = LEVERAGE_MULTIPLIER,
) -> tuple[dict[str, Any], pd.DataFrame]:
    marks = marks.copy()
    mark_map = {
        (row.ts, row.symbol): (float(row.open), float(row.high))
        for row in marks.itertuples(index=False)
    }
    entries = {
        ts: group.copy() for ts, group in legs.groupby("entry_time", sort=True)
    }
    funding_events = {
        ts: group.copy() for ts, group in funding.groupby("ts", sort=True)
    }
    start = legs["entry_time"].min()
    end = legs["planned_exit_time"].max()
    hours = pd.date_range(start, end, freq="1h")
    positions: list[dict[str, Any]] = []
    cash = 1.0
    peak = 1.0
    max_drawdown = 0.0
    worst_drawdown = 0.0
    min_margin_buffer = float("inf")
    min_margin_buffer_ratio = float("inf")
    max_actual_gross = 0.0
    liquidated = False
    liquidation_time: pd.Timestamp | None = None
    records: list[dict[str, Any]] = []
    previous_hour = start - pd.Timedelta(hours=1)
    side_cost = ONE_SIDE_COST * cost_multiplier

    for ts in hours:
        for event_ts, events in funding_events.items():
            if not (previous_hour < event_ts <= ts):
                continue
            rates = events.set_index("symbol")["funding_rate"]
            for position in positions:
                if position["entry_time"] < event_ts <= position["exit_time"]:
                    rate = rates.get(position["symbol"])
                    if rate is not None and np.isfinite(rate):
                        cash += position["notional"] * float(rate)

        remaining: list[dict[str, Any]] = []
        for position in positions:
            if position["exit_time"] == ts:
                cash += position["notional"] * (
                    1.0 - position["exit_open"] / position["entry_open"]
                )
                cash -= position["notional"] * side_cost
            else:
                remaining.append(position)
        positions = remaining

        open_unrealized, _ = mark_values(
            positions, ts=ts, mark_map=mark_map, use_high=False
        )
        pre_entry_equity = cash + open_unrealized
        if pre_entry_equity <= 0.0:
            liquidated = True
            liquidation_time = ts
            records.append(
                {
                    "ts": ts,
                    "equity_open": pre_entry_equity,
                    "worst_equity": pre_entry_equity,
                    "maintenance_margin": 0.0,
                    "margin_buffer": pre_entry_equity,
                    "actual_gross": float("inf"),
                    "position_count": len(positions),
                    "liquidated": True,
                }
            )
            break

        new_legs = entries.get(ts)
        if new_legs is not None:
            new_positions: list[dict[str, Any]] = []
            for row in new_legs.itertuples(index=False):
                notional = (
                    pre_entry_equity
                    * float(row.leg_exposure)
                    * leverage_multiplier
                )
                new_positions.append(
                    {
                        "symbol": row.symbol,
                        "entry_time": row.entry_time,
                        "exit_time": row.planned_exit_time,
                        "entry_open": float(row.entry_open),
                        "exit_open": float(row.exit_open),
                        "notional": notional,
                    }
                )
                cash -= notional * side_cost
            positions.extend(new_positions)

        open_unrealized, open_mark_notional = mark_values(
            positions, ts=ts, mark_map=mark_map, use_high=False
        )
        equity = cash + open_unrealized
        high_unrealized, high_mark_notional = mark_values(
            positions, ts=ts, mark_map=mark_map, use_high=True
        )
        worst_equity = cash + high_unrealized
        maintenance = maintenance_margin_rate * high_mark_notional
        margin_buffer = worst_equity - maintenance
        margin_buffer_ratio = margin_buffer / equity if equity > 0.0 else -float("inf")
        actual_gross = open_mark_notional / equity if equity > 0.0 else float("inf")
        peak = max(peak, equity)
        drawdown = equity / peak - 1.0 if peak > 0.0 else -1.0
        intrahour_drawdown = worst_equity / peak - 1.0 if peak > 0.0 else -1.0
        max_drawdown = min(max_drawdown, drawdown)
        worst_drawdown = min(worst_drawdown, intrahour_drawdown)
        min_margin_buffer = min(min_margin_buffer, margin_buffer)
        min_margin_buffer_ratio = min(min_margin_buffer_ratio, margin_buffer_ratio)
        max_actual_gross = max(max_actual_gross, actual_gross)
        liquidated = worst_equity <= maintenance
        records.append(
            {
                "ts": ts,
                "equity_open": equity,
                "worst_equity": worst_equity,
                "maintenance_margin": maintenance,
                "margin_buffer": margin_buffer,
                "margin_buffer_ratio": margin_buffer_ratio,
                "actual_gross": actual_gross,
                "position_count": len(positions),
                "liquidated": liquidated,
            }
        )
        if liquidated:
            liquidation_time = ts
            break
        previous_hour = ts

    curve = pd.DataFrame(records)
    final_equity = (
        max(0.0, float(curve.iloc[-1]["worst_equity"]))
        if liquidated
        else float(curve.iloc[-1]["equity_open"])
    )
    scenario = {
        "cost_multiplier": cost_multiplier,
        "maintenance_margin_rate": maintenance_margin_rate,
        "leverage_multiplier": leverage_multiplier,
        "total_return": final_equity - 1.0,
        "max_drawdown": max_drawdown,
        "worst_intrahour_drawdown": worst_drawdown,
        "min_margin_buffer": min_margin_buffer,
        "min_margin_buffer_ratio": min_margin_buffer_ratio,
        "max_actual_gross": max_actual_gross,
        "liquidated": liquidated,
        "liquidation_time": liquidation_time.isoformat() if liquidation_time else None,
        "completed_hours": len(curve),
        "completed_legs": len(legs),
    }
    curve["cost_multiplier"] = cost_multiplier
    curve["maintenance_margin_rate"] = maintenance_margin_rate
    return scenario, curve


def atomic_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def atomic_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    frame.to_parquet(temporary, index=False, compression="zstd")
    os.replace(temporary, path)


def artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "size_bytes": path.stat().st_size,
    }


def validate_existing_result() -> dict[str, Any]:
    summary = load_json(SUMMARY_JSON)
    if summary.get("three_x_risk_contract_sha256") != sha256(
        THREE_X_RISK_CONTRACT
    ):
        raise RuntimeError("existing three-x result uses another risk contract")
    if not EVIDENCE_RECEIPT.is_file() or not EVIDENCE_RECEIPT_SHA.is_file():
        raise RuntimeError("existing three-x result has no complete evidence receipt")
    receipt = load_json(EVIDENCE_RECEIPT)
    outputs = receipt.get("outputs", {})
    for name, path in {
        "summary_json": SUMMARY_JSON,
        "scenarios_csv": SCENARIOS_CSV,
        "hourly_parquet": HOURLY_PARQUET,
        "report_md": REPORT_MD,
    }.items():
        item = outputs.get(name, {})
        if not path.is_file() or item.get("sha256") != sha256(path):
            raise RuntimeError(f"existing three-x output SHA mismatch: {name}")
    expected_sidecar = f"{sha256(EVIDENCE_RECEIPT)}  {EVIDENCE_RECEIPT.name}\n"
    if EVIDENCE_RECEIPT_SHA.read_text(encoding="utf-8") != expected_sidecar:
        raise RuntimeError("three-x evidence receipt sidecar mismatch")
    return summary


def write_report(summary: dict[str, Any], scenarios: pd.DataFrame) -> None:
    rows = []
    for row in scenarios.itertuples(index=False):
        rows.append(
            "| {cost:.1f}x | {mmr:.1%} | {ret:.2%} | {dd:.2%} | {worst:.2%} | "
            "{buffer:.4f} | {gross:.2f}x | {liq} |".format(
                cost=row.cost_multiplier,
                mmr=row.maintenance_margin_rate,
                ret=row.total_return,
                dd=abs(row.max_drawdown),
                worst=abs(row.worst_intrahour_drawdown),
                buffer=row.min_margin_buffer,
                gross=row.max_actual_gross,
                liq="是" if row.liquidated else "否",
            )
        )
    gates = [
        f"| `{name}` | `{'PASS' if passed else 'FAIL'}` |"
        for name, passed in summary["gates"].items()
    ]
    text = "\n".join(
        [
            "# BIN-1H-MHCSML-V1 R4 三倍敞口尾部风险审计",
            "",
            f"- 状态：`{summary['status']}`",
            "- Promotion：`not promoted`；Live ready：`false`。",
            "- 三倍只放大冻结腿敞口，不改变信号或退出。",
            "",
            "## 场景",
            "",
            "| 成本 | MMR | 收益 | 普通 DD | 时内最坏 DD | 最小缓冲 | 最大 gross | 强平 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
            *rows,
            "",
            "## 附加风险门禁",
            "",
            "| 门槛 | 结果 |",
            "| --- | --- |",
            *gates,
            "",
            "本结果不改变基础策略裁决，也不授权上线。",
            "",
        ]
    )
    temporary = REPORT_MD.with_suffix(".md.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, REPORT_MD)


def main() -> None:
    args = parse_args()
    if args.now and not args.validate_only:
        raise RuntimeError("--now is forbidden outside --validate-only")
    now = as_utc(args.now) if args.now else pd.Timestamp.now("UTC")
    validate_three_x_contract()
    if args.validate_only and now < REVEAL_NOT_BEFORE:
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "authorization_guard": "SEALED",
                    "leverage_multiplier": LEVERAGE_MULTIPLIER,
                    "cost_multipliers": COST_MULTIPLIERS,
                    "maintenance_margin_rates": MAINTENANCE_MARGIN_RATES,
                    "three_x_risk_contract_sha256": sha256(THREE_X_RISK_CONTRACT),
                    "prospective_oos_outcomes_read": False,
                },
                indent=2,
            )
        )
        return
    adjudication = assert_authorized(now)
    if SUMMARY_JSON.exists():
        existing = validate_existing_result()
        print(json.dumps(existing, indent=2, ensure_ascii=False))
        return
    legs = load_revealed_legs(adjudication)
    marks = load_mark_path(legs)
    funding = load_funding_events(legs)
    maximum_leg_error = validate_leg_returns(legs, funding)
    scenarios: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    for cost in COST_MULTIPLIERS:
        for mmr in MAINTENANCE_MARGIN_RATES:
            scenario, curve = simulate_scenario(
                legs,
                marks,
                funding,
                cost_multiplier=cost,
                maintenance_margin_rate=mmr,
            )
            scenarios.append(scenario)
            curves.append(curve)
    scenario_frame = pd.DataFrame(scenarios)
    conservative = scenario_frame.loc[
        scenario_frame["cost_multiplier"].eq(1.5)
        & scenario_frame["maintenance_margin_rate"].eq(0.025)
    ].iloc[0]
    gates = {
        "all_scenarios_no_liquidation": bool(~scenario_frame["liquidated"].any()),
        "conservative_stress_return_positive": bool(conservative["total_return"] > 0.0),
        "all_max_drawdown_lte_50pct": bool(
            scenario_frame["max_drawdown"].ge(-0.50).all()
        ),
        "all_intrahour_drawdown_lte_60pct": bool(
            scenario_frame["worst_intrahour_drawdown"].ge(-0.60).all()
        ),
        "all_margin_buffers_positive": bool(
            scenario_frame["min_margin_buffer"].gt(0.0).all()
        ),
        "all_actual_gross_lte_1_50x": bool(
            scenario_frame["max_actual_gross"].le(1.50).all()
        ),
    }
    status = (
        "THREE_X_TAIL_RISK_AUDIT_PASS"
        if all(gates.values())
        else "THREE_X_TAIL_RISK_AUDIT_FAILED"
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_parquet(marks, MARK_INPUT_PARQUET)
    atomic_parquet(funding, FUNDING_INPUT_PARQUET)
    atomic_text(scenario_frame.to_csv(index=False), SCENARIOS_CSV)
    atomic_parquet(pd.concat(curves, ignore_index=True), HOURLY_PARQUET)
    summary = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "version": "BIN-1H-MHCSML-V1",
        "freeze_revision": "r4",
        "generated_at": now.isoformat(),
        "status": status,
        "promotion_status": "not promoted",
        "live_ready": False,
        "base_adjudication_sha256": sha256(FINAL_ADJUDICATION),
        "three_x_risk_contract_sha256": sha256(THREE_X_RISK_CONTRACT),
        "revealed_legs_sha256": sha256(REVEALED_LEGS),
        "revealed_decisions_sha256": sha256(REVEALED_DECISIONS),
        "maximum_leg_return_crosscheck_error": maximum_leg_error,
        "leverage_multiplier": LEVERAGE_MULTIPLIER,
        "gates": gates,
        "failed_gates": [name for name, passed in gates.items() if not passed],
        "scenarios": scenarios,
        "inputs": {
            "mark_path": artifact(MARK_INPUT_PARQUET),
            "funding_events": artifact(FUNDING_INPUT_PARQUET),
        },
        "outputs": {
            "scenarios_csv": artifact(SCENARIOS_CSV),
            "hourly_parquet": artifact(HOURLY_PARQUET),
            "report_md": str(REPORT_MD.relative_to(ROOT)),
            "evidence_receipt": str(EVIDENCE_RECEIPT.relative_to(ROOT)),
        },
        "note": "Three-x results never alter the frozen base-strategy adjudication.",
    }
    atomic_json(summary, SUMMARY_JSON)
    write_report(summary, scenario_frame)
    receipt = {
        "family": summary["family"],
        "version": summary["version"],
        "freeze_revision": summary["freeze_revision"],
        "generated_at": now.isoformat(),
        "status": "PASS",
        "sources": {
            "master_freeze": artifact(MASTER_FREEZE),
            "three_x_risk_contract": artifact(THREE_X_RISK_CONTRACT),
            "base_final_adjudication": artifact(FINAL_ADJUDICATION),
            "reveal_report": artifact(REVEAL_REPORT),
            "revealed_legs": artifact(REVEALED_LEGS),
            "revealed_decisions": artifact(REVEALED_DECISIONS),
        },
        "input_slices": {
            "mark_path": artifact(MARK_INPUT_PARQUET),
            "funding_events": artifact(FUNDING_INPUT_PARQUET),
        },
        "outputs": {
            "summary_json": artifact(SUMMARY_JSON),
            "scenarios_csv": artifact(SCENARIOS_CSV),
            "hourly_parquet": artifact(HOURLY_PARQUET),
            "report_md": artifact(REPORT_MD),
        },
        "prospective_oos_outcomes_read": True,
    }
    atomic_json(receipt, EVIDENCE_RECEIPT)
    atomic_text(
        f"{sha256(EVIDENCE_RECEIPT)}  {EVIDENCE_RECEIPT.name}\n",
        EVIDENCE_RECEIPT_SHA,
    )
    print(
        json.dumps(
            {
                **summary,
                "evidence_receipt_sha256": sha256(EVIDENCE_RECEIPT),
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
