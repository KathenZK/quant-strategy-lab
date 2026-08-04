#!/usr/bin/env python3
"""Frozen BIN-1H-PIC-V2 risk-invariant research batch."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = REPO_ROOT / "research/asset-portfolios/1h-price-impulse-campaign"
V1_SCRIPT = FAMILY_DIR / "scripts/research_binance_1h_pic_v1.py"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
RUN_DATE = "2026-08-03"
OPERATIONAL_RISK_BUDGET = 0.009


def load_v1_module() -> Any:
    spec = importlib.util.spec_from_file_location("binance_pic_v1_shared", V1_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load V1 shared module: {V1_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def config_for(
    v1: Any,
    *,
    fee_rate: float | None = None,
    slippage: float | None = None,
    include_funding: bool = True,
    side_filter: int = 0,
    allow_adds: bool = True,
    allow_half_reduce: bool = True,
    operational_risk_budget: float = OPERATIONAL_RISK_BUDGET,
    maintain_risk_after_funding: bool = True,
) -> Any:
    return v1.V1Config(
        fee_rate=v1.FEE_RATE if fee_rate is None else fee_rate,
        slippage=v1.BASE_SLIPPAGE if slippage is None else slippage,
        include_funding=include_funding,
        allow_adds=allow_adds,
        allow_half_reduce=allow_half_reduce,
        side_filter=side_filter,
        operational_risk_budget=operational_risk_budget,
        maintain_risk_after_funding=maintain_risk_after_funding,
    )


def decision(
    metrics: pd.DataFrame,
    slices: pd.DataFrame,
    rolling: pd.DataFrame,
    ablation: pd.DataFrame,
) -> dict[str, Any]:
    base = metrics.loc[
        metrics["asset"].eq("ETH")
        & metrics["cost_model"].eq("base")
        & metrics["arm"].eq("all")
    ].iloc[0]
    stress = metrics.loc[
        metrics["asset"].eq("ETH")
        & metrics["cost_model"].eq("stress_8bps")
        & metrics["arm"].eq("all")
    ].iloc[0]
    recent_6m = slices.loc[slices["slice"].eq("6m")].iloc[0]
    closed_rolling = rolling.loc[rolling["campaigns"].ge(1)].copy()
    rolling_ratio = (
        float(closed_rolling["total_return_pct"].gt(0.0).mean())
        if not closed_rolling.empty
        else 0.0
    )
    full = ablation.loc[ablation["variant"].eq("full")].iloc[0]
    probe = ablation.loc[ablation["variant"].eq("probe_only")].iloc[0]
    gates = {
        "base_return_positive": bool(base["total_return_pct"] > 0.0),
        "base_sharpe_positive": bool(base["sharpe"] > 0.0),
        "mdd_within_20pct": bool(base["max_drawdown_pct"] > -20.0),
        "campaigns_at_least_30": bool(base["campaigns"] >= 30),
        "recent_6m_non_negative": bool(recent_6m["total_return_pct"] >= 0.0),
        "rolling_positive_ratio_at_least_60pct": bool(rolling_ratio >= 0.60),
        "stress_non_negative": bool(stress["total_return_pct"] >= 0.0),
        "no_risk_violation": bool(base["risk_violations"] == 0),
        "leverage_cap_respected": bool(
            base["max_effective_leverage"] <= 3.0 + 1e-12
        ),
        "full_not_worse_than_probe_only": bool(
            full["total_return_pct"] >= probe["total_return_pct"]
        ),
    }
    return {
        "all_minimum_gates_pass": bool(all(gates.values())),
        "rolling_positive_ratio": rolling_ratio,
        "gates": gates,
        "selection_boundary": (
            "V2 was designed after V1 full-history risk reveal; historical results "
            "cannot authorize promotion without new prospective OOS"
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    v1 = load_v1_module()
    shared = v1.load_v0_module()
    assets, quality = shared.load_assets()

    cost_models = {
        "gross": (0.0, 0.0, False),
        "base": (v1.FEE_RATE, v1.BASE_SLIPPAGE, True),
        "stress_8bps": (v1.FEE_RATE, v1.STRESS_SLIPPAGE, True),
    }
    arms = {"all": 0, "long": 1, "short": -1}
    metrics_rows: list[dict[str, Any]] = []
    campaigns: list[pd.DataFrame] = []
    actions: list[pd.DataFrame] = []
    equities: list[pd.DataFrame] = []

    for asset in ("ETH", "BTC", "HYPE", "SOL"):
        for cost_name, (fee_rate, slippage, include_funding) in cost_models.items():
            for arm, side_filter in arms.items():
                config = config_for(
                    v1,
                    fee_rate=fee_rate,
                    slippage=slippage,
                    include_funding=include_funding,
                    side_filter=side_filter,
                )
                result = v1.run_backtest(assets[asset], config, shared)
                metrics_rows.append(
                    {"asset": asset, "cost_model": cost_name, "arm": arm, **result.metrics}
                )
                if cost_name == "base" and arm == "all":
                    for frame, target in (
                        (result.campaigns, campaigns),
                        (result.actions, actions),
                        (result.equity, equities),
                    ):
                        if not frame.empty:
                            copy = frame.copy()
                            copy["asset"] = asset
                            target.append(copy)

    eth = assets["ETH"]
    end = eth.index.max()
    slices_rows: list[dict[str, Any]] = []
    full_config = config_for(v1)
    for name, start in v1.recent_slice_starts(end).items():
        result = v1.run_backtest(eth, full_config, shared, start, end)
        slices_rows.append({"slice": name, "start": start, "end": end, **result.metrics})
    slices = pd.DataFrame(slices_rows)
    rolling = v1.rolling_windows(eth, full_config, shared)

    variants = {
        "full": full_config,
        "probe_only": config_for(
            v1,
            allow_adds=False,
            allow_half_reduce=False,
        ),
        "maintenance_no_buffer": config_for(
            v1,
            operational_risk_budget=v1.RISK_BUDGET,
        ),
        "buffer_no_maintenance": config_for(
            v1,
            maintain_risk_after_funding=False,
        ),
    }
    ablation_rows: list[dict[str, Any]] = []
    for name, config in variants.items():
        result = v1.run_backtest(eth, config, shared)
        ablation_rows.append({"variant": name, **result.metrics})
    ablation = pd.DataFrame(ablation_rows)

    metrics = pd.DataFrame(metrics_rows)
    campaign_frame = pd.concat(campaigns, ignore_index=True) if campaigns else pd.DataFrame()
    action_frame = pd.concat(actions, ignore_index=True) if actions else pd.DataFrame()
    equity_frame = pd.concat(equities, ignore_index=True) if equities else pd.DataFrame()
    verdict = decision(metrics, slices, rolling, ablation)
    outputs = {
        "metrics": metrics,
        "campaigns": campaign_frame,
        "actions": action_frame,
        "equity": equity_frame,
        "recent_slices": slices,
        "rolling_120d": rolling,
        "ablation": ablation,
    }
    for name, frame in outputs.items():
        suffix = "parquet" if name == "equity" else "csv"
        path = ARTIFACT_DIR / f"binance_1h_pic_v2_{name}_{RUN_DATE}.{suffix}"
        if suffix == "parquet":
            frame.to_parquet(path, index=False)
        else:
            frame.to_csv(path, index=False)

    payload = {
        "family": "Binance-1H-Price-Impulse-Campaign",
        "candidate_id": "BIN-1H-PIC-V2",
        "status": "explore / not promoted / not live-ready",
        "data_quality": quality,
        "verdict": verdict,
        "contract": {
            "hard_risk_budget": v1.RISK_BUDGET,
            "operational_risk_budget": OPERATIONAL_RISK_BUDGET,
            "risk_maintenance": "funding then LIFO added-layer trim at same open",
            "max_leverage": v1.MAX_LEVERAGE,
        },
        "summaries": {
            name: v1.frame_records(frame)
            for name, frame in outputs.items()
            if name != "equity"
        },
    }
    with (ARTIFACT_DIR / f"binance_1h_pic_v2_research_{RUN_DATE}.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)

    columns = [
        "asset",
        "cost_model",
        "total_return_pct",
        "sharpe",
        "max_drawdown_pct",
        "campaigns",
        "profit_factor",
        "adds",
        "reductions",
        "risk_trims",
        "max_effective_leverage",
        "risk_violations",
        "max_stopout_loss_pct",
    ]
    print("V2 RISK-INVARIANT METRICS")
    print(metrics.loc[metrics["arm"].eq("all"), columns].to_string(index=False))
    print("\nETH SLICES")
    print(
        slices[
            ["slice", "total_return_pct", "sharpe", "max_drawdown_pct", "campaigns"]
        ].to_string(index=False)
    )
    print("\nETH ABLATION")
    print(
        ablation[
            [
                "variant",
                "total_return_pct",
                "sharpe",
                "max_drawdown_pct",
                "campaigns",
                "risk_trims",
                "risk_violations",
                "max_stopout_loss_pct",
            ]
        ].to_string(index=False)
    )
    print("\nVERDICT")
    print(json.dumps(verdict, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
