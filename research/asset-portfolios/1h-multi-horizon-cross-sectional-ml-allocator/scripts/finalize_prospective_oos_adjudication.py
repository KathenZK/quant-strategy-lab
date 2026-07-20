from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
SCRIPT_DIR = FAMILY_DIR / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_blind_chain_health as chain_health  # noqa: E402


EXPECTED_MASTER_SHA256 = (
    "64ee12688980673aa2cd348a961553c89d246d1f338eba0192ddcbfdd095fe11"
)
REVEAL_NOT_BEFORE = pd.Timestamp("2026-10-20T21:05:00Z")
MASTER_FREEZE = FAMILY_DIR / (
    "artifacts/freeze/bin-1h-mhcsml-v1-freeze-r4.json"
)
ADJUDICATION_CONTRACT = FAMILY_DIR / (
    "artifacts/freeze/bin-1h-mhcsml-v1-final-adjudication-contract-r4.json"
)
ABLATION = FAMILY_DIR / "artifacts/historical_factor_group_ablation_2026-07-19.json"
REVEAL_DIR = FAMILY_DIR / "artifacts/prospective_oos/reveal"
REVEAL_RECEIPT = REVEAL_DIR / "reveal_started.json"
REVEAL_REPORT = REVEAL_DIR / "one_time_oos_report.json"
OUTPUT_JSON = REVEAL_DIR / "final_adjudication.json"
OUTPUT_MARKDOWN = FAMILY_DIR / (
    "diagnostics/binance-1h-mhcsml-prospective-oos-final-adjudication-2026-10-20.md"
)
EXPECTED_REVEAL_GATES = {
    "three_month_return_gte_18_92pct",
    "annualized_return_gte_100pct",
    "max_drawdown_lte_20pct",
    "decision_win_rate_gte_55pct",
    "sharpe_gte_1_5",
    "profit_factor_gte_1_30",
    "active_decisions_gte_45",
    "completed_legs_gte_300",
    "positive_month_cohorts_gte_2",
    "stress_return_positive",
    "stress_drawdown_lte_25pct",
    "symbol_concentration_lte_25pct",
    "month_concentration_lte_35pct",
    "lgbm_beats_ridge_baseline",
    "lgbm_beats_rule_baseline",
}
EXPECTED_STRATEGIES = {"r4", "ridge_compact", "rule_carry_momentum"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine frozen OOS and historical gates into one adjudication."
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


def assert_reveal_time(now: pd.Timestamp) -> None:
    if now < REVEAL_NOT_BEFORE:
        raise RuntimeError(
            "prospective OOS adjudication remains sealed until "
            f"{REVEAL_NOT_BEFORE.isoformat()}"
        )


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def validate_adjudication_contract() -> dict[str, Any]:
    contract = load_json(ADJUDICATION_CONTRACT)
    if contract.get("status") != "PASS" or contract.get("blockers"):
        raise RuntimeError("final adjudication contract is not PASS")
    if contract.get("master_freeze_sha256") != EXPECTED_MASTER_SHA256:
        raise RuntimeError("adjudication contract master SHA mismatch")
    if contract.get("prospective_oos_outcomes_read") is not False:
        raise RuntimeError("adjudication contract reports prospective outcome access")
    for section in ("inputs", "evaluators"):
        specs = contract.get(section)
        if not isinstance(specs, dict) or not specs:
            raise RuntimeError(f"adjudication contract section missing: {section}")
        for name, spec in specs.items():
            path = ROOT / str(spec.get("path", ""))
            if not path.exists() or sha256(path) != spec.get("sha256"):
                raise RuntimeError(f"adjudication contract component mismatch: {name}")
    return contract


def validate_static_evidence() -> tuple[dict[str, Any], dict[str, Any], dict[str, bool]]:
    validate_adjudication_contract()
    if sha256(MASTER_FREEZE) != EXPECTED_MASTER_SHA256:
        raise RuntimeError("master freeze SHA mismatch")
    master = load_json(MASTER_FREEZE)
    ablation = load_json(ABLATION)
    ablation_gates = ablation.get("gates", {})
    tail = ablation.get("tail_stability", {})
    mae = tail.get("short_mae_quantile", {})
    squeeze = tail.get("short_squeeze_classification", {})
    static_gates = {
        "historical_majority_folds_positive": (
            int(master["development_oof_metrics"]["positive_fold_count"]) >= 4
        ),
        "historical_seed_stability_pass": all(
            bool(value) for value in master["development_seed_gates"].values()
        ),
        "factor_group_stability_pass": (
            ablation.get("status") == "PASS"
            and not ablation.get("blockers")
            and bool(ablation_gates)
            and all(bool(value) for value in ablation_gates.values())
        ),
        "mae_tail_ic_direction_stable": (
            int(mae.get("observations", 0)) == 28
            and int(mae.get("positive_fold_seed_count", 0)) == 28
            and float(mae.get("minimum_fold_seed_ic", 0.0)) > 0.0
        ),
        "squeeze_tail_ic_direction_stable": (
            int(squeeze.get("observations", 0)) == 28
            and int(squeeze.get("positive_fold_seed_count", 0)) == 28
            and float(squeeze.get("minimum_fold_seed_ic", 0.0)) > 0.0
        ),
        "prospective_outcomes_not_used_by_ablation": (
            ablation.get("prospective_oos_outcomes_read") is False
        ),
    }
    return master, ablation, static_gates


def verify_reveal_output(spec: dict[str, Any], expected: Path) -> bool:
    path = ROOT / str(spec.get("path", ""))
    try:
        if path.resolve(strict=True) != expected.resolve(strict=True):
            return False
    except FileNotFoundError:
        return False
    if sha256(path) != spec.get("sha256"):
        return False
    parquet = pq.ParquetFile(path)
    return parquet.metadata.num_rows >= 0 and len(parquet.schema_arrow.names) > 0


def validate_reveal_evidence(
    report: dict[str, Any], receipt: dict[str, Any], chain: dict[str, Any]
) -> tuple[dict[str, bool], dict[str, bool]]:
    if report.get("master_freeze_sha256") != EXPECTED_MASTER_SHA256:
        raise RuntimeError("reveal report master SHA mismatch")
    if receipt.get("master_freeze_sha256") != EXPECTED_MASTER_SHA256:
        raise RuntimeError("reveal receipt master SHA mismatch")
    if receipt.get("chain_tail_sha256") != chain.get("chain_tail_sha256"):
        raise RuntimeError("reveal receipt chain tail mismatch")
    if as_utc(report["revealed_at"]) < REVEAL_NOT_BEFORE:
        raise RuntimeError("reveal report was generated before the guard opened")
    if as_utc(receipt["started_at"]) < REVEAL_NOT_BEFORE:
        raise RuntimeError("reveal receipt was generated before the guard opened")
    metrics = report.get("metrics", {})
    if set(metrics) != EXPECTED_STRATEGIES:
        raise RuntimeError("reveal report omitted or added comparison strategies")
    reveal_gates = report.get("hard_gates", {})
    if set(reveal_gates) != EXPECTED_REVEAL_GATES:
        raise RuntimeError("reveal hard-gate set mismatch")
    if not all(isinstance(value, bool) for value in reveal_gates.values()):
        raise RuntimeError("reveal hard gates must be booleans")
    expected_status = "PASS" if all(reveal_gates.values()) else "HARD-GATE-FAILED"
    if report.get("status") != expected_status:
        raise RuntimeError("reveal report status contradicts its gates")
    outputs = report.get("outputs", {})
    output_gates = {
        "revealed_legs_sha_valid": verify_reveal_output(
            outputs.get("legs", {}), REVEAL_DIR / "revealed_legs.parquet"
        ),
        "revealed_decisions_sha_valid": verify_reveal_output(
            outputs.get("decisions", {}), REVEAL_DIR / "revealed_decisions.parquet"
        ),
    }
    return {name: bool(value) for name, value in reveal_gates.items()}, output_gates


def atomic_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def atomic_json(payload: dict[str, Any], path: Path) -> None:
    atomic_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        path,
    )


def markdown_report(payload: dict[str, Any]) -> str:
    metrics = payload["metrics"]
    rows = []
    for strategy in ("r4", "ridge_compact", "rule_carry_momentum"):
        values = metrics[strategy]
        rows.append(
            "| {strategy} | {ret:.2%} | {ann:.2%} | {dd:.2%} | {wr:.2%} | "
            "{sharpe:.3f} | {pf:.3f} | {decisions} | {legs} |".format(
                strategy=strategy,
                ret=float(values["total_return"]),
                ann=float(values["annualized_return"]),
                dd=abs(float(values["max_drawdown"])),
                wr=float(values["win_rate"]),
                sharpe=float(values["sharpe"]),
                pf=float(values["profit_factor"]),
                decisions=int(values["decision_count"]),
                legs=int(values["trade_count"]),
            )
        )
    gate_rows = [
        f"| `{name}` | `{'PASS' if passed else 'FAIL'}` |"
        for name, passed in payload["all_gates"].items()
    ]
    failed = payload["failed_gates"]
    failed_text = "无" if not failed else "、".join(f"`{name}`" for name in failed)
    return "\n".join(
        [
            "# BIN-1H-MHCSML-V1 prospective OOS 最终裁决",
            "",
            "## 结论",
            "",
            f"- 总状态：`{payload['status']}`",
            "- Promotion：`not promoted`；Live ready：`false`。",
            f"- 失败门槛：{failed_text}",
            f"- 3x 研究授权：`{str(payload['three_x_evaluation_authorized']).lower()}`。",
            "- 本报告同时纳入 OOS、历史 folds、因子组消融、tail IC、盲链和输出 SHA；不以单一收益指标替代硬门槛。",
            "",
            "## 同口径结果",
            "",
            "| 策略 | 累计收益 | 年化 | 最大回撤 | 胜率 | Sharpe | PF | 有效决策 | 腿 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *rows,
            "",
            "## 全部门槛",
            "",
            "| 门槛 | 结果 |",
            "| --- | --- |",
            *gate_rows,
            "",
            "## 状态边界",
            "",
            "基础研究门槛即使全部通过，也不自动成为 live spec；订单、保证金、强平、断线恢复与 runner 审计完成前仍为 `not promoted / not live-ready`。只有基础门槛全部通过，才允许执行独立 3x 尾部风险研究。",
            "",
        ]
    )


def main() -> None:
    args = parse_args()
    if args.now and not args.validate_only:
        raise RuntimeError("--now is forbidden outside --validate-only")
    now = as_utc(args.now) if args.now else pd.Timestamp.now("UTC")
    master, ablation, static_gates = validate_static_evidence()
    if args.validate_only and now < REVEAL_NOT_BEFORE:
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "reveal_guard": "SEALED",
                    "static_gates": static_gates,
                    "prospective_oos_outcomes_read": False,
                },
                indent=2,
            )
        )
        return
    assert_reveal_time(now)
    chain = chain_health.audit_chain(now=now)
    if chain["status"] != "PASS" or chain["actual_nodes"] != 552:
        raise RuntimeError(f"blind chain is not complete: {chain['blockers']}")
    if not REVEAL_REPORT.exists() or not REVEAL_RECEIPT.exists():
        raise RuntimeError("one-time reveal evidence is missing")
    reveal = load_json(REVEAL_REPORT)
    receipt = load_json(REVEAL_RECEIPT)
    reveal_gates, output_gates = validate_reveal_evidence(reveal, receipt, chain)
    governance_gates = {
        "blind_chain_complete_and_valid": (
            chain["status"] == "PASS"
            and chain["expected_nodes"] == 552
            and chain["actual_nodes"] == 552
        ),
        **static_gates,
        **output_gates,
    }
    all_gates = {**reveal_gates, **governance_gates}
    failed = [name for name, passed in all_gates.items() if not passed]
    status = "BASE_STRATEGY_RESEARCH_GATES_PASS" if not failed else "HARD-GATE-FAILED"
    payload = {
        "family": master["family"],
        "version": master["version"],
        "freeze_revision": master["freeze_revision"],
        "adjudicated_at": now.isoformat(),
        "status": status,
        "promotion_status": "not promoted",
        "live_ready": False,
        "three_x_evaluation_authorized": not failed,
        "master_freeze_sha256": EXPECTED_MASTER_SHA256,
        "reveal_report_sha256": sha256(REVEAL_REPORT),
        "ablation_sha256": sha256(ABLATION),
        "chain_tail_sha256": chain["chain_tail_sha256"],
        "metrics": reveal["metrics"],
        "reveal_gates": reveal_gates,
        "governance_gates": governance_gates,
        "all_gates": all_gates,
        "failed_gates": failed,
        "known_risk": ablation["known_risk"],
        "prospective_oos_outcomes_read": True,
        "note": (
            "Research-gate pass never authorizes live deployment. Three-x research "
            "is permitted only when every base gate is true."
        ),
    }
    if OUTPUT_JSON.exists():
        existing = load_json(OUTPUT_JSON)
        if existing.get("reveal_report_sha256") != payload["reveal_report_sha256"]:
            raise RuntimeError("existing adjudication was built from another reveal report")
        print(json.dumps(existing, indent=2, ensure_ascii=False))
        return
    atomic_json(payload, OUTPUT_JSON)
    atomic_text(markdown_report(payload), OUTPUT_MARKDOWN)
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
