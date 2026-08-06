from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from dstc_data import load_assets
from dstc_engine import Config, run_backtest


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
E04_PATH = ARTIFACT_DIR / "binance_mtf_dstc_layers_mfe_2026-08-04.json"
END = pd.Timestamp("2025-06-30 23:59:59", tz="UTC")
CANDIDATE_IDS = {
    "BTC-BAL": ("BTC", "wrong05+ma14::layers2_mfe50_adds"),
    "BTC-GROWTH": ("BTC", "wrong05+ma14::layers4_ladder_alt_no_mfe"),
    "ETH-BAL": ("ETH", "wrong05::layers4_mfe50_adds"),
    "ETH-CONVEX": ("ETH", "invalidation_slope_structure::layers4_no_mfe"),
}
RISK_SCALES = (1.0, 1.5, 2.0, 3.0)
ROBUSTNESS = (
    ("base", {}),
    ("slippage_8bps", {"slippage": 0.0008}),
    ("slippage_12bps", {"slippage": 0.0012}),
    ("funding_off", {"include_funding": False}),
    ("delay_15m", {"decision_delay_bars": 1}),
    ("long_only", {"side_filter": 1}),
    ("short_only", {"side_filter": -1}),
)
FOLDS = (
    ("F1", "2020-01-01", "2021-06-30 23:59:59"),
    ("F2", "2021-01-01", "2022-06-30 23:59:59"),
    ("F3", "2022-01-01", "2023-06-30 23:59:59"),
    ("F4", "2023-01-01", "2024-06-30 23:59:59"),
    ("F5", "2024-01-01", "2025-06-30 23:59:59"),
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def load_frozen_configs() -> dict[str, tuple[str, Config]]:
    payload = json.loads(E04_PATH.read_text(encoding="utf-8"))
    by_key = {
        (row["asset"], row["config_id"]): row["config"]
        for row in payload["generated"]
    }
    frozen: dict[str, tuple[str, Config]] = {}
    for candidate_id, (asset, config_id) in CANDIDATE_IDS.items():
        config_row = dict(by_key[(asset, config_id)])
        config_row["name"] = candidate_id
        frozen[candidate_id] = (asset, Config(**config_row))
    return frozen


def _hard_gate(metrics: dict[str, Any]) -> dict[str, bool]:
    recent = metrics["recent_returns"]
    return {
        "annual_2x": float(metrics["annual_equity_multiple"]) >= 2.0,
        "mdd_20": abs(float(metrics["max_drawdown_pct"])) <= 20.0,
        "pf_13": float(metrics["profit_factor"]) >= 1.3,
        "campaigns_30": int(metrics["campaigns"]) >= 30,
        "top1_35": float(metrics["top1_gross_profit_share"]) <= 0.35,
        "top3_65": float(metrics["top3_gross_profit_share"]) <= 0.65,
        "remove_top3": float(metrics["remove_top3_net_pnl"]) >= -0.05,
        "recent_not_all_fail": not all(
            float(recent[key]) <= 0.0 for key in ("3m", "6m", "1y")
        ),
        "leverage_3x": float(metrics["max_effective_leverage"]) <= 3.0,
        "risk_violations_zero": int(metrics["risk_violations"]) == 0,
    }


def main() -> None:
    assets = load_assets()
    frozen = load_frozen_configs()
    rows: list[dict[str, Any]] = []
    payload_candidates: dict[str, Any] = {}
    ledger_dir = ARTIFACT_DIR / "stability_ledgers"
    ledger_dir.mkdir(parents=True, exist_ok=True)

    for candidate_id, (asset, base_config) in frozen.items():
        data = assets[asset]
        risk_rows: list[dict[str, Any]] = []
        robustness_rows: list[dict[str, Any]] = []
        fold_rows: list[dict[str, Any]] = []
        for scale in RISK_SCALES:
            config = replace(
                base_config,
                name=f"{candidate_id}::risk{scale:g}",
                layer_risk=base_config.layer_risk * scale,
                total_plan_risk=base_config.total_plan_risk * scale,
                campaign_loss_budget=base_config.campaign_loss_budget * scale,
            )
            run = run_backtest(data, config, end=END)
            gate = _hard_gate(run.metrics)
            row = {
                "candidate_id": candidate_id,
                "asset": asset,
                "section": "risk_scale",
                "scenario": f"risk_{scale:g}",
                "risk_scale": scale,
                **run.metrics,
                "hard_gate_pass": all(gate.values()),
                "hard_gate_detail": gate,
            }
            rows.append(row)
            risk_rows.append(row)
            print(
                candidate_id,
                f"risk={scale:g}%",
                f"annual={run.metrics['annual_equity_multiple']:.3f}x",
                f"dd={run.metrics['max_drawdown_pct']:.1f}%",
                f"pf={run.metrics['profit_factor']:.2f}",
                f"lev={run.metrics['max_effective_leverage']:.2f}",
                "HARD-PASS" if all(gate.values()) else "-",
                flush=True,
            )
            if scale == 1.0:
                stem = candidate_id.lower().replace("-", "_")
                run.campaigns.to_parquet(ledger_dir / f"{stem}_campaigns.parquet", index=False)
                run.lots.to_parquet(ledger_dir / f"{stem}_lots.parquet", index=False)
                run.actions.to_parquet(ledger_dir / f"{stem}_actions.parquet", index=False)
                run.equity.to_parquet(ledger_dir / f"{stem}_equity.parquet")

        for scenario, changes in ROBUSTNESS:
            config = replace(base_config, name=f"{candidate_id}::{scenario}", **changes)
            run = run_backtest(data, config, end=END)
            row = {
                "candidate_id": candidate_id,
                "asset": asset,
                "section": "robustness",
                "scenario": scenario,
                **run.metrics,
            }
            rows.append(row)
            robustness_rows.append(row)
            print(
                candidate_id,
                scenario,
                f"annual={run.metrics['annual_equity_multiple']:.3f}x",
                f"dd={run.metrics['max_drawdown_pct']:.1f}%",
                f"pf={run.metrics['profit_factor']:.2f}",
                flush=True,
            )

        for fold_id, start, end in FOLDS:
            run = run_backtest(data, base_config, start=start, end=end)
            row = {
                "candidate_id": candidate_id,
                "asset": asset,
                "section": "rolling",
                "scenario": fold_id,
                "fold_start": start,
                "fold_end": end,
                **run.metrics,
            }
            rows.append(row)
            fold_rows.append(row)
            print(
                candidate_id,
                fold_id,
                f"annual={run.metrics['annual_equity_multiple']:.3f}x",
                f"dd={run.metrics['max_drawdown_pct']:.1f}%",
                f"pf={run.metrics['profit_factor']:.2f}",
                flush=True,
            )

        base_robust = next(row for row in robustness_rows if row["scenario"] == "base")
        slip8 = next(row for row in robustness_rows if row["scenario"] == "slippage_8bps")
        slip12 = next(row for row in robustness_rows if row["scenario"] == "slippage_12bps")
        delay = next(row for row in robustness_rows if row["scenario"] == "delay_15m")
        positive_folds = sum(float(row["end_equity"]) > 1.0 for row in fold_rows)
        stability_gate = {
            "rolling_majority_positive": positive_folds >= 3,
            "stress_8bps_positive": float(slip8["end_equity"]) > 1.0,
            "stress_12bps_no_collapse": (
                float(slip12["end_equity"]) > 0.95
                and abs(float(slip12["max_drawdown_pct"])) <= 25.0
            ),
            "delay_15m_positive": float(delay["end_equity"]) > 1.0,
            "base_concentration": (
                float(base_robust["top1_gross_profit_share"]) <= 0.35
                and float(base_robust["top3_gross_profit_share"]) <= 0.65
                and float(base_robust["remove_top3_net_pnl"]) >= -0.05
            ),
        }
        payload_candidates[candidate_id] = {
            "asset": asset,
            "base_config": asdict(base_config),
            "risk_scaling": risk_rows,
            "robustness": robustness_rows,
            "rolling": fold_rows,
            "positive_rolling_folds": positive_folds,
            "stability_gate": stability_gate,
            "eligible_for_historical_final_audit": bool(
                any(row["hard_gate_pass"] for row in risk_rows)
                and all(stability_gate.values())
            ),
        }

    generation_hash = hashlib.sha256(
        json.dumps(
            {candidate_id: asdict(config) for candidate_id, (_, config) in frozen.items()},
            ensure_ascii=False,
            sort_keys=True,
            default=list,
        ).encode("utf-8")
    ).hexdigest()
    flat = pd.DataFrame(rows).drop(columns=["config", "recent_returns", "hard_gate_detail"], errors="ignore")
    flat.to_csv(ARTIFACT_DIR / "binance_mtf_dstc_stability_2026-08-04.csv", index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-MTF-Dual-State-Trend-Campaign",
        "experiment": "E05 pre-final stability and risk scaling",
        "generation_hash": generation_hash,
        "historical_final_audit_revealed": False,
        "final_audit_policy": (
            "No historical-final rows are loaded unless a candidate passes all hard and stability gates."
        ),
        "candidates": payload_candidates,
    }
    (ARTIFACT_DIR / "binance_mtf_dstc_stability_2026-08-04.json").write_text(
        json.dumps(_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
