"""Risk-overlay diagnostics for BIN-1H-AR-MAE-V1.

This script keeps the same frozen sleeve trade paths as the registered V1
single-position backtest, then applies account-level overlays only:

- cap all selected trade exposure to 3x / 2.5x;
- cap or remove the TRX macd_flip leg that carries the 5x exposure;
- apply simple post-trade cost pressure to the 3x overlay.

These are diagnostic overlays, not registered versions. They still inherit the
same caveat as V1: cross-asset blocking removes frozen trades but does not
replay each sleeve's cooldown/signal state after a blocked trade.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SCRIPT_DIR = Path(__file__).resolve().parent
DATE_TAG = "2026-07-09"

SUMMARY_JSON = ARTIFACT_DIR / f"binance_1h_ar_mae_v1_risk_overlay_diagnostics_{DATE_TAG}.json"
MATRIX_CSV = ARTIFACT_DIR / f"binance_1h_ar_mae_v1_risk_overlay_matrix_{DATE_TAG}.csv"


TradeFilter = Callable[[str, Any], bool]
TradeOverlay = Callable[[str, Any], Any]


@dataclass(frozen=True)
class Variant:
    name: str
    description: str
    candidate_filter: TradeFilter
    overlay: TradeOverlay


def load_module(name: str, path: Path) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_single_position_module() -> Any:
    return load_module(
        "research_binance_1h_ar_mae_single_position_backtest",
        SCRIPT_DIR / "research_binance_1h_ar_mae_single_position_backtest.py",
    )


def load_sleeves(first: Any) -> list[dict[str, Any]]:
    sleeves: list[dict[str, Any]] = []
    for loader in (
        first.load_trx,
        first.load_sol,
        first.load_hype,
        first.load_eth,
        first.load_btc,
        first.load_bnb,
    ):
        sleeve = loader()
        metric = first.verify_sleeve(sleeve)
        sleeve["trades"] = [
            trade
            for trade in sleeve["trades"]
            if sleeve["start"] <= trade.entry_ts < sleeve["end"]
        ]
        sleeves.append(sleeve)
        print(
            f"verified {sleeve['asset']} {sleeve['version']}: "
            f"annual={metric['annual_multiple']:.4f}x trades={int(metric['trades'])}",
            flush=True,
        )
    return sleeves


def unchanged(_asset: str, trade: Any) -> Any:
    return trade


def pass_all(_asset: str, _trade: Any) -> bool:
    return True


def clone_with_overlay(
    trade: Any,
    *,
    exposure_cap: float | None = None,
    extra_roundtrip_notional_cost: float = 0.0,
) -> Any:
    """Return a copied trade after a simple account-risk overlay.

    The original sleeve return is assumed to scale linearly with notional
    exposure. Extra cost is account-level impact: capped_exposure * cost_rate.
    """
    original_exposure = float(trade.exposure)
    scale = 1.0
    if exposure_cap is not None and original_exposure > exposure_cap:
        scale = exposure_cap / original_exposure

    cloned = copy.copy(trade)
    capped_exposure = original_exposure * scale
    cloned.exposure = capped_exposure
    cloned.equity_ret = float(trade.equity_ret) * scale - (
        capped_exposure * extra_roundtrip_notional_cost
    )
    if hasattr(cloned, "equity_mae"):
        cloned.equity_mae = float(trade.equity_mae) * scale - (
            capped_exposure * extra_roundtrip_notional_cost
        )
    return cloned


def cap_all(exposure_cap: float, extra_roundtrip_notional_cost: float = 0.0) -> TradeOverlay:
    def overlay(_asset: str, trade: Any) -> Any:
        return clone_with_overlay(
            trade,
            exposure_cap=exposure_cap,
            extra_roundtrip_notional_cost=extra_roundtrip_notional_cost,
        )

    return overlay


def cap_trx_macd(exposure_cap: float) -> TradeOverlay:
    def overlay(asset: str, trade: Any) -> Any:
        if asset == "TRX" and trade.style == "macd_flip":
            return clone_with_overlay(trade, exposure_cap=exposure_cap)
        return trade

    return overlay


def no_trx_macd(asset: str, trade: Any) -> bool:
    return not (asset == "TRX" and trade.style == "macd_flip")


def exposure_le(max_exposure: float) -> TradeFilter:
    def include(_asset: str, trade: Any) -> bool:
        return float(trade.exposure) <= max_exposure

    return include


def selected_to_frame(selected: list[tuple[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "asset": asset,
                "style": trade.style,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": int(trade.side),
                "exposure": float(trade.exposure),
                "equity_ret": float(trade.equity_ret),
                "exit_reason": trade.exit_reason,
                "hold_hours": (trade.exit_ts - trade.entry_ts).total_seconds() / 3600.0,
            }
            for asset, trade in selected
        ]
    )


def summarize_selection(
    tagged: list[tuple[str, Any]],
    selected: list[tuple[str, Any]],
    skipped: list[tuple[str, Any]],
    ties: int,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    exposures = [float(trade.exposure) for _asset, trade in selected]
    hold_hours = [
        (trade.exit_ts - trade.entry_ts).total_seconds() / 3600.0
        for _asset, trade in selected
    ]
    total_hours = float((end - start).total_seconds() / 3600.0)
    in_position_hours = float(sum(hold_hours))
    return {
        "candidate_trades": len(tagged),
        "selected_trades": len(selected),
        "skipped_blocked": len(skipped),
        "same_hour_entry_ties": ties,
        "per_asset_candidates": {
            asset: int(sum(1 for a, _trade in tagged if a == asset))
            for asset in ("TRX", "SOL", "HYPE", "ETH", "BTC", "BNB")
        },
        "per_asset_selected": {
            asset: int(sum(1 for a, _trade in selected if a == asset))
            for asset in ("TRX", "SOL", "HYPE", "ETH", "BTC", "BNB")
        },
        "per_style_selected": {
            f"{asset}:{style}": int(count)
            for (asset, style), count in selected_to_frame(selected)
            .groupby(["asset", "style"])
            .size()
            .items()
        }
        if selected
        else {},
        "avg_exposure": float(np.mean(exposures)) if exposures else 0.0,
        "median_exposure": float(np.median(exposures)) if exposures else 0.0,
        "max_exposure": float(np.max(exposures)) if exposures else 0.0,
        "avg_hold_hours": float(np.mean(hold_hours)) if hold_hours else 0.0,
        "median_hold_hours": float(np.median(hold_hours)) if hold_hours else 0.0,
        "over_48h_trades": int(sum(1 for value in hold_hours if value > 48.0)),
        "in_position_hours_pct": in_position_hours / total_hours if total_hours else 0.0,
    }


def run_variant(
    variant: Variant,
    tagged_source: list[tuple[str, Any]],
    frames: dict[str, pd.DataFrame],
    start: pd.Timestamp,
    hype_start: pd.Timestamp,
    end: pd.Timestamp,
    single: Any,
    first: Any,
) -> dict[str, Any]:
    tagged = [
        (asset, trade)
        for asset, trade in tagged_source
        if variant.candidate_filter(asset, trade)
    ]
    selected_raw, skipped, ties = single.select_single_position(tagged)
    selected = [
        (asset, variant.overlay(asset, trade))
        for asset, trade in selected_raw
    ]
    curve = single.portfolio_curve(selected, frames, start, end)

    windows: list[tuple[str, pd.Timestamp]] = [
        ("full", start),
        ("all_six_active", hype_start),
        ("reused_holdout", pd.Timestamp("2026-04-03T00:00:00Z")),
    ]
    for name, delta in single.SLICES:
        windows.append((name, max(start, end - delta)))

    portfolio_windows: dict[str, Any] = {}
    for window_name, window_start in windows:
        portfolio_windows[window_name] = {
            "start": window_start,
            "end": end,
            "curve": first.curve_metrics(curve, window_start, end),
            "trade_stats": single.trade_stats(selected, window_start, end),
        }

    worst_dd = min(
        float(window["curve"]["max_dd"])
        for window in portfolio_windows.values()
    )
    return {
        "name": variant.name,
        "description": variant.description,
        "selection": summarize_selection(tagged, selected, skipped, ties, start, end),
        "portfolio_windows": portfolio_windows,
        "worst_window_max_dd": worst_dd,
        "passes_20pct_dd_gate": worst_dd > -0.20,
    }


def flatten_matrix(variants: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant in variants:
        row: dict[str, Any] = {
            "variant": variant["name"],
            "description": variant["description"],
            "candidate_trades": variant["selection"]["candidate_trades"],
            "selected_trades": variant["selection"]["selected_trades"],
            "skipped_blocked": variant["selection"]["skipped_blocked"],
            "avg_exposure": variant["selection"]["avg_exposure"],
            "max_exposure": variant["selection"]["max_exposure"],
            "worst_window_max_dd": variant["worst_window_max_dd"],
            "passes_20pct_dd_gate": variant["passes_20pct_dd_gate"],
        }
        for window_name in (
            "full",
            "reused_holdout",
            "last_7d",
            "last_1m",
            "last_3m",
            "last_6m",
            "last_1y",
        ):
            window = variant["portfolio_windows"][window_name]
            row[f"{window_name}_annual_multiple"] = window["curve"]["annual_multiple"]
            row[f"{window_name}_total_return"] = window["curve"]["total_return"]
            row[f"{window_name}_max_dd"] = window["curve"]["max_dd"]
            row[f"{window_name}_trades"] = window["trade_stats"]["trades"]
            row[f"{window_name}_win_rate"] = window["trade_stats"]["win_rate"]
            row[f"{window_name}_profit_factor"] = window["trade_stats"]["profit_factor"]
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    single = load_single_position_module()
    first = single.load_first_backtest_module()
    sleeves = load_sleeves(first)

    start = max(sleeve["start"] for sleeve in sleeves if sleeve["asset"] != "HYPE")
    hype_start = next(sleeve["start"] for sleeve in sleeves if sleeve["asset"] == "HYPE")
    end = min(sleeve["end"] for sleeve in sleeves)
    frames = {sleeve["asset"]: sleeve["frame"] for sleeve in sleeves}
    tagged_source = [
        (sleeve["asset"], trade)
        for sleeve in sleeves
        for trade in sleeve["trades"]
        if start <= trade.entry_ts < end
    ]

    variants = [
        Variant(
            "v1_baseline_reproduced",
            "Registered V1 structure reproduced without overlays.",
            pass_all,
            unchanged,
        ),
        Variant(
            "v1_overlay_cap3x_all_selected",
            "Keep V1 selection, cap every selected trade's account exposure to 3x.",
            pass_all,
            cap_all(3.0),
        ),
        Variant(
            "v1_overlay_cap2_5x_all_selected",
            "Keep V1 selection, cap every selected trade's account exposure to 2.5x.",
            pass_all,
            cap_all(2.5),
        ),
        Variant(
            "v1_overlay_trx_macd_cap3x",
            "Keep V1 selection, cap only TRX macd_flip selected trades to 3x.",
            pass_all,
            cap_trx_macd(3.0),
        ),
        Variant(
            "v1_overlay_trx_macd_cap2_5x",
            "Keep V1 selection, cap only TRX macd_flip selected trades to 2.5x.",
            pass_all,
            cap_trx_macd(2.5),
        ),
        Variant(
            "v1_filter_no_trx_macd_candidates",
            "Remove TRX macd_flip candidates before account-level first-come selection.",
            no_trx_macd,
            unchanged,
        ),
        Variant(
            "v1_filter_no_exposure_gt3x_candidates",
            "Remove any frozen candidate whose sleeve exposure is above 3x before selection.",
            exposure_le(3.0),
            unchanged,
        ),
        Variant(
            "v1_overlay_cap3x_extra_slippage_4bps_per_fill",
            "Cap all selected trades to 3x, then add 4 bps adverse slippage per fill.",
            pass_all,
            cap_all(3.0, extra_roundtrip_notional_cost=0.0008),
        ),
        Variant(
            "v1_overlay_cap3x_double_fee_slippage",
            "Cap all selected trades to 3x, then add another full baseline fee+slippage roundtrip.",
            pass_all,
            cap_all(3.0, extra_roundtrip_notional_cost=0.0028),
        ),
        Variant(
            "v1_overlay_cap2_5x_extra_slippage_4bps_per_fill",
            "Cap all selected trades to 2.5x, then add 4 bps adverse slippage per fill.",
            pass_all,
            cap_all(2.5, extra_roundtrip_notional_cost=0.0008),
        ),
        Variant(
            "v1_overlay_cap2_5x_double_fee_slippage",
            "Cap all selected trades to 2.5x, then add another full baseline fee+slippage roundtrip.",
            pass_all,
            cap_all(2.5, extra_roundtrip_notional_cost=0.0028),
        ),
    ]

    results = [
        run_variant(
            variant,
            tagged_source,
            frames,
            start,
            hype_start,
            end,
            single,
            first,
        )
        for variant in variants
    ]

    matrix = flatten_matrix(results)
    matrix.to_csv(MATRIX_CSV, index=False)
    payload = {
        "family": "Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble",
        "observation": "v1_risk_overlay_diagnostics",
        "status": "diagnostic_observation_not_registered_not_promoted_not_live_ready",
        "date": DATE_TAG,
        "portfolio_start": start,
        "hype_sleeve_start": hype_start,
        "portfolio_end": end,
        "costs": {
            "baseline_fee_per_fill": 0.001,
            "baseline_slippage_per_fill": 0.0004,
            "funding": "actual_binance_history_per_trade",
            "stress_costs": "post-trade notional overlays; not a full K-level re-simulation",
        },
        "methodology_warning": [
            "All variants are account-level overlays on frozen V1 sleeve trades.",
            "Cross-asset blocking is not replayed through each sleeve's signal/cooldown state.",
            "Cost pressure variants subtract extra cost at trade exit; they do not alter stop/target path.",
        ],
        "variants": results,
    }
    SUMMARY_JSON.write_text(
        json.dumps(first.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    brief = matrix[
        [
            "variant",
            "selected_trades",
            "max_exposure",
            "full_annual_multiple",
            "full_total_return",
            "full_max_dd",
            "reused_holdout_annual_multiple",
            "reused_holdout_total_return",
            "reused_holdout_max_dd",
            "last_7d_total_return",
            "last_7d_max_dd",
            "worst_window_max_dd",
            "passes_20pct_dd_gate",
        ]
    ]
    print(brief.to_string(index=False), flush=True)
    print(f"wrote {SUMMARY_JSON}", flush=True)
    print(f"wrote {MATRIX_CSV}", flush=True)


if __name__ == "__main__":
    main()
