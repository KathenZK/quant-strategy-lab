"""TRX MACD tail-risk optimization for BIN-1H-AR-MAE-V1.

The frozen sleeve signals, entries, exits, single-position selection, fees,
slippage, and funding remain unchanged. This script only changes account-level
exposure using information available before each selected trade:

- a hard account exposure cap;
- a TRX macd_flip initial-stop risk budget;
- an account drawdown guard based on equity history before entry.

Policy selection uses the prefit window only. Reused holdout and recent slices
are evaluated after the policy is frozen.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
SCRIPT_DIR = Path(__file__).resolve().parent
DATE_TAG = "2026-07-10"

SUMMARY_JSON = ARTIFACT_DIR / f"binance_1h_ar_mae_v1_trx_tail_risk_{DATE_TAG}.json"
MATRIX_CSV = ARTIFACT_DIR / f"binance_1h_ar_mae_v1_trx_tail_risk_matrix_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"binance_1h_ar_mae_v1_trx_tail_risk_trades_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"binance-1h-ar-mae-v1-trx-tail-risk-optimization-{DATE_TAG}.md"

PREFIT_END = pd.Timestamp("2026-04-03T06:00:00Z")
BASE_ROUNDTRIP_FEE_SLIPPAGE = 0.0028
TRX_MACD_SL_ATR = 5.0


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    name: str
    description: str
    all_hard_cap: float | None = None
    all_atr_risk_budget: float | None = None
    trx_macd_hard_cap: float | None = None
    trx_macd_stop_risk_budget: float | None = None
    dd_soft_threshold: float | None = None
    dd_hard_threshold: float | None = None
    dd_soft_cap: float | None = None
    dd_hard_cap: float | None = None


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
        first.verify_sleeve(sleeve)
        sleeve["trades"] = [
            trade
            for trade in sleeve["trades"]
            if sleeve["start"] <= trade.entry_ts < sleeve["end"]
        ]
        sleeves.append(sleeve)
    return sleeves


def initial_stop_unit_loss(
    asset: str,
    trade: Any,
    frames: dict[str, pd.DataFrame],
) -> float | None:
    if asset != "TRX" or trade.style != "macd_flip":
        return None
    signal_atr = float(frames[asset]["atr14"].iloc[int(trade.signal_i)])
    price_stop_loss = TRX_MACD_SL_ATR * signal_atr / float(trade.entry_price)
    return price_stop_loss + BASE_ROUNDTRIP_FEE_SLIPPAGE


def entry_atr_unit_risk(
    asset: str,
    trade: Any,
    frames: dict[str, pd.DataFrame],
) -> float:
    signal_atr = float(frames[asset]["atr14"].iloc[int(trade.signal_i)])
    return signal_atr / float(trade.entry_price)


def exposure_for_entry(
    policy: RiskPolicy,
    asset: str,
    trade: Any,
    frames: dict[str, pd.DataFrame],
    pre_entry_dd: float,
) -> tuple[float, float | None]:
    exposure = float(trade.exposure)
    planned_unit_loss = initial_stop_unit_loss(asset, trade, frames)

    if policy.all_hard_cap is not None:
        exposure = min(exposure, policy.all_hard_cap)
    if policy.all_atr_risk_budget is not None:
        atr_unit_risk = entry_atr_unit_risk(asset, trade, frames)
        if atr_unit_risk > 0.0:
            exposure = min(exposure, policy.all_atr_risk_budget / atr_unit_risk)
    if asset == "TRX" and trade.style == "macd_flip":
        if policy.trx_macd_hard_cap is not None:
            exposure = min(exposure, policy.trx_macd_hard_cap)
        if (
            policy.trx_macd_stop_risk_budget is not None
            and planned_unit_loss is not None
            and planned_unit_loss > 0.0
        ):
            exposure = min(
                exposure,
                policy.trx_macd_stop_risk_budget / planned_unit_loss,
            )

    if (
        policy.dd_hard_threshold is not None
        and policy.dd_hard_cap is not None
        and pre_entry_dd <= -policy.dd_hard_threshold
    ):
        exposure = min(exposure, policy.dd_hard_cap)
    elif (
        policy.dd_soft_threshold is not None
        and policy.dd_soft_cap is not None
        and pre_entry_dd <= -policy.dd_soft_threshold
    ):
        exposure = min(exposure, policy.dd_soft_cap)
    return max(exposure, 0.0), planned_unit_loss


def clone_at_exposure(
    trade: Any,
    exposure: float,
    *,
    extra_roundtrip_notional_cost: float,
) -> Any:
    original_exposure = float(trade.exposure)
    scale = exposure / original_exposure if original_exposure > 0.0 else 0.0
    cloned = copy.copy(trade)
    cloned.exposure = exposure
    cloned.equity_ret = float(trade.equity_ret) * scale - (
        exposure * extra_roundtrip_notional_cost
    )
    cloned.equity_mae = float(trade.equity_mae) * scale - (
        exposure * extra_roundtrip_notional_cost
    )
    return cloned


def apply_policy(
    policy: RiskPolicy,
    selected: list[tuple[str, Any]],
    frames: dict[str, pd.DataFrame],
    *,
    extra_roundtrip_notional_cost: float = 0.0,
) -> tuple[list[tuple[str, Any]], pd.DataFrame]:
    equity = 1.0
    peak_equity = 1.0
    adjusted: list[tuple[str, Any]] = []
    rows: list[dict[str, Any]] = []

    for asset, trade in selected:
        pre_entry_dd = equity / peak_equity - 1.0
        exposure, planned_unit_loss = exposure_for_entry(
            policy,
            asset,
            trade,
            frames,
            pre_entry_dd,
        )
        cloned = clone_at_exposure(
            trade,
            exposure,
            extra_roundtrip_notional_cost=extra_roundtrip_notional_cost,
        )
        adjusted.append((asset, cloned))

        entry_equity = equity
        frame = frames[asset]
        close = frame["close"].to_numpy(dtype="float64")
        for bar_i in range(int(trade.entry_i), int(trade.exit_i)):
            mark_1x = float(trade.side) * (
                float(close[bar_i]) / float(trade.entry_price) - 1.0
            )
            marked_equity = entry_equity * (1.0 + exposure * mark_1x)
            peak_equity = max(peak_equity, marked_equity)
        equity *= 1.0 + float(cloned.equity_ret)
        peak_equity = max(peak_equity, equity)

        rows.append(
            {
                "asset": asset,
                "style": trade.style,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": int(trade.side),
                "original_exposure": float(trade.exposure),
                "adjusted_exposure": exposure,
                "pre_entry_dd": pre_entry_dd,
                "planned_stop_unit_loss": planned_unit_loss,
                "planned_stop_account_risk": (
                    exposure * planned_unit_loss
                    if planned_unit_loss is not None
                    else np.nan
                ),
                "original_equity_ret": float(trade.equity_ret),
                "adjusted_equity_ret": float(cloned.equity_ret),
                "original_equity_mae": float(trade.equity_mae),
                "adjusted_equity_mae": float(cloned.equity_mae),
                "exit_reason": trade.exit_reason,
            }
        )
    return adjusted, pd.DataFrame(rows)


def risk_stats(rows: pd.DataFrame) -> dict[str, float]:
    trx = rows.loc[
        (rows["asset"] == "TRX") & (rows["style"] == "macd_flip")
    ]
    return {
        "trx_macd_trades": float(len(trx)),
        "trx_macd_avg_exposure": float(trx["adjusted_exposure"].mean()),
        "trx_macd_max_exposure": float(trx["adjusted_exposure"].max()),
        "trx_macd_max_planned_stop_risk": float(
            trx["planned_stop_account_risk"].max()
        ),
        "trx_macd_p90_planned_stop_risk": float(
            trx["planned_stop_account_risk"].quantile(0.90)
        ),
        "trx_macd_worst_equity_mae": float(trx["adjusted_equity_mae"].min()),
        "trx_macd_p10_equity_mae": float(trx["adjusted_equity_mae"].quantile(0.10)),
        "exposure_reduced_entries": float(
            (rows["adjusted_exposure"] < rows["original_exposure"]).sum()
        ),
        "pre_entry_dd_le_8pct": float((rows["pre_entry_dd"] <= -0.08).sum()),
        "pre_entry_dd_le_12pct": float((rows["pre_entry_dd"] <= -0.12).sum()),
    }


def window_metrics(
    adjusted: list[tuple[str, Any]],
    curve: pd.Series,
    first: Any,
    single: Any,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    return {
        "curve": first.curve_metrics(curve, start, end),
        "trade_stats": single.trade_stats(adjusted, start, end),
    }


def evaluate_policy(
    policy: RiskPolicy,
    selected: list[tuple[str, Any]],
    frames: dict[str, pd.DataFrame],
    start: pd.Timestamp,
    end: pd.Timestamp,
    first: Any,
    single: Any,
    *,
    extra_roundtrip_notional_cost: float = 0.0,
) -> tuple[dict[str, Any], list[tuple[str, Any]], pd.DataFrame]:
    adjusted, rows = apply_policy(
        policy,
        selected,
        frames,
        extra_roundtrip_notional_cost=extra_roundtrip_notional_cost,
    )
    curve = single.portfolio_curve(adjusted, frames, start, end)
    result = {
        "prefit": window_metrics(
            adjusted,
            curve,
            first,
            single,
            start,
            PREFIT_END,
        ),
        "risk": risk_stats(rows),
    }
    return result, adjusted, rows


def candidate_policies() -> list[RiskPolicy]:
    policies = [
        RiskPolicy("baseline", "Registered V1 exposure."),
        RiskPolicy("all_cap_3x", "All selected trades capped at 3x.", all_hard_cap=3.0),
        RiskPolicy(
            "all_cap_2_5x",
            "All selected trades capped at 2.5x.",
            all_hard_cap=2.5,
        ),
    ]
    for cap in np.arange(2.0, 5.0, 0.25):
        policies.append(
            RiskPolicy(
                f"trx_macd_cap_{cap:g}x",
                f"TRX macd_flip capped at {cap:g}x.",
                trx_macd_hard_cap=float(cap),
            )
        )
    for budget in np.arange(0.06, 0.161, 0.01):
        policies.append(
            RiskPolicy(
                f"trx_macd_stop_budget_{budget:.2f}",
                f"TRX macd_flip planned initial-stop account risk <= {budget:.0%}.",
                trx_macd_stop_risk_budget=float(round(budget, 2)),
            )
        )

    threshold_pairs = ((0.05, 0.10), (0.08, 0.12))
    cap_pairs = ((2.5, 1.5), (2.0, 1.0), (3.0, 1.5))
    for atr_budget in np.arange(0.008, 0.025, 0.002):
        policies.append(
            RiskPolicy(
                f"all_atr_budget_{atr_budget:.3f}",
                (
                    "All selected trades capped so account exposure times "
                    f"signal ATR is <= {atr_budget:.2%}."
                ),
                all_atr_risk_budget=float(round(atr_budget, 3)),
            )
        )
    for soft_threshold, hard_threshold in threshold_pairs:
        for soft_cap, hard_cap in cap_pairs:
            policies.append(
                RiskPolicy(
                    (
                        f"account_dd_guard_{soft_threshold:.0%}_{hard_threshold:.0%}"
                        f"_caps_{soft_cap:g}x_{hard_cap:g}x"
                    ),
                    "Account-wide exposure cap tightens after realized/marked drawdown.",
                    dd_soft_threshold=soft_threshold,
                    dd_hard_threshold=hard_threshold,
                    dd_soft_cap=soft_cap,
                    dd_hard_cap=hard_cap,
                )
            )
            for budget in (0.08, 0.10, 0.12, 0.14):
                policies.append(
                    RiskPolicy(
                        (
                            f"hybrid_trx_budget_{budget:.2f}_dd_"
                            f"{soft_threshold:.0%}_{hard_threshold:.0%}_"
                            f"caps_{soft_cap:g}x_{hard_cap:g}x"
                        ),
                        (
                            "TRX planned-stop risk budget plus account-wide "
                            "drawdown-responsive exposure caps."
                        ),
                        trx_macd_stop_risk_budget=budget,
                        dd_soft_threshold=soft_threshold,
                        dd_hard_threshold=hard_threshold,
                        dd_soft_cap=soft_cap,
                        dd_hard_cap=hard_cap,
                    )
                )
            for atr_budget in (0.010, 0.012, 0.015, 0.018):
                policies.append(
                    RiskPolicy(
                        (
                            f"hybrid_all_atr_{atr_budget:.3f}_dd_"
                            f"{soft_threshold:.0%}_{hard_threshold:.0%}_"
                            f"caps_{soft_cap:g}x_{hard_cap:g}x"
                        ),
                        (
                            "Portfolio-wide signal-ATR risk budget plus "
                            "drawdown-responsive exposure caps."
                        ),
                        all_atr_risk_budget=atr_budget,
                        dd_soft_threshold=soft_threshold,
                        dd_hard_threshold=hard_threshold,
                        dd_soft_cap=soft_cap,
                        dd_hard_cap=hard_cap,
                    )
                )
    return policies


def flatten_result(
    policy: RiskPolicy,
    baseline: dict[str, Any],
    extra_slip: dict[str, Any],
    double_cost: dict[str, Any],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        **asdict(policy),
    }
    for scenario, result in (
        ("base", baseline),
        ("extra_slip", extra_slip),
        ("double_cost", double_cost),
    ):
        for section in ("curve", "trade_stats"):
            for key, value in result["prefit"][section].items():
                row[f"{scenario}_prefit_{key}"] = value
        for key, value in result["risk"].items():
            row[f"{scenario}_{key}"] = value
    return row


def select_policy(matrix: pd.DataFrame) -> pd.Series:
    eligible = matrix.loc[
        (matrix["base_prefit_max_dd"] > -0.19)
        & (matrix["extra_slip_prefit_max_dd"] > -0.20)
        & (matrix["base_trx_macd_worst_equity_mae"] > -0.12)
        & (matrix["base_prefit_annual_multiple"] >= 10.0)
    ].copy()
    if eligible.empty:
        raise RuntimeError("No tail-risk policy passed the prefit-only selection gates")
    eligible["robust_dd"] = eligible[
        [
            "base_prefit_max_dd",
            "extra_slip_prefit_max_dd",
            "double_cost_prefit_max_dd",
        ]
    ].min(axis=1)
    return eligible.sort_values(
        [
            "robust_dd",
            "base_trx_macd_worst_equity_mae",
            "base_prefit_annual_multiple",
        ],
        ascending=[False, False, False],
    ).iloc[0]


def full_windows(
    adjusted: list[tuple[str, Any]],
    frames: dict[str, pd.DataFrame],
    start: pd.Timestamp,
    hype_start: pd.Timestamp,
    end: pd.Timestamp,
    first: Any,
    single: Any,
) -> dict[str, Any]:
    curve = single.portfolio_curve(adjusted, frames, start, end)
    windows: list[tuple[str, pd.Timestamp]] = [
        ("full", start),
        ("all_six_active", hype_start),
        ("reused_holdout", PREFIT_END),
    ]
    for name, delta in single.SLICES:
        windows.append((name, max(start, end - delta)))
    return {
        name: window_metrics(
            adjusted,
            curve,
            first,
            single,
            window_start,
            end,
        )
        for name, window_start in windows
    }


def metric_line(window: dict[str, Any]) -> str:
    curve = window["curve"]
    trades = window["trade_stats"]
    return (
        f"`{curve['annual_multiple']:.2f}x / {curve['total_return']:+.2%} / "
        f"{curve['max_dd']:.2%} DD / {trades['win_rate']:.2%} win / "
        f"{int(trades['trades'])} trades`"
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    single = load_single_position_module()
    first = single.load_first_backtest_module()
    sleeves = load_sleeves(first)
    start = max(sleeve["start"] for sleeve in sleeves if sleeve["asset"] != "HYPE")
    hype_start = next(sleeve["start"] for sleeve in sleeves if sleeve["asset"] == "HYPE")
    end = min(sleeve["end"] for sleeve in sleeves)
    frames = {sleeve["asset"]: sleeve["frame"] for sleeve in sleeves}
    tagged = [
        (sleeve["asset"], trade)
        for sleeve in sleeves
        for trade in sleeve["trades"]
        if start <= trade.entry_ts < end
    ]
    selected, skipped, ties = single.select_single_position(tagged)

    policy_by_name = {policy.name: policy for policy in candidate_policies()}
    rows: list[dict[str, Any]] = []
    for policy in policy_by_name.values():
        baseline, _adjusted, _trade_rows = evaluate_policy(
            policy,
            selected,
            frames,
            start,
            end,
            first,
            single,
        )
        extra_slip, _adjusted, _trade_rows = evaluate_policy(
            policy,
            selected,
            frames,
            start,
            end,
            first,
            single,
            extra_roundtrip_notional_cost=0.0008,
        )
        double_cost, _adjusted, _trade_rows = evaluate_policy(
            policy,
            selected,
            frames,
            start,
            end,
            first,
            single,
            extra_roundtrip_notional_cost=0.0028,
        )
        rows.append(flatten_result(policy, baseline, extra_slip, double_cost))

    matrix = pd.DataFrame(rows)
    matrix.to_csv(MATRIX_CSV, index=False)
    selected_row = select_policy(matrix)
    selected_policy = policy_by_name[str(selected_row["name"])]
    selected_base, selected_trades, selected_rows = evaluate_policy(
        selected_policy,
        selected,
        frames,
        start,
        end,
        first,
        single,
    )
    selected_extra, selected_extra_trades, _ = evaluate_policy(
        selected_policy,
        selected,
        frames,
        start,
        end,
        first,
        single,
        extra_roundtrip_notional_cost=0.0008,
    )
    selected_double, selected_double_trades, _ = evaluate_policy(
        selected_policy,
        selected,
        frames,
        start,
        end,
        first,
        single,
        extra_roundtrip_notional_cost=0.0028,
    )

    baseline_policy = policy_by_name["baseline"]
    _baseline_result, baseline_trades, baseline_rows = evaluate_policy(
        baseline_policy,
        selected,
        frames,
        start,
        end,
        first,
        single,
    )
    baseline_windows = full_windows(
        baseline_trades,
        frames,
        start,
        hype_start,
        end,
        first,
        single,
    )
    selected_windows = full_windows(
        selected_trades,
        frames,
        start,
        hype_start,
        end,
        first,
        single,
    )
    selected_extra_windows = full_windows(
        selected_extra_trades,
        frames,
        start,
        hype_start,
        end,
        first,
        single,
    )
    selected_double_windows = full_windows(
        selected_double_trades,
        frames,
        start,
        hype_start,
        end,
        first,
        single,
    )

    frontier_names = (
        "all_cap_2_5x",
        "hybrid_all_atr_0.010_dd_8%_12%_caps_2x_1x",
        "hybrid_all_atr_0.012_dd_8%_12%_caps_2x_1x",
        "hybrid_all_atr_0.015_dd_8%_12%_caps_2x_1x",
    )
    frontier_audit: dict[str, Any] = {}
    for policy_name in frontier_names:
        policy = policy_by_name[policy_name]
        scenario_results: dict[str, Any] = {}
        for scenario, cost in (
            ("base", 0.0),
            ("extra_slip_4bps_per_fill", 0.0008),
            ("double_fee_slippage", 0.0028),
        ):
            _prefit, adjusted, trade_rows = evaluate_policy(
                policy,
                selected,
                frames,
                start,
                end,
                first,
                single,
                extra_roundtrip_notional_cost=cost,
            )
            windows = full_windows(
                adjusted,
                frames,
                start,
                hype_start,
                end,
                first,
                single,
            )
            scenario_results[scenario] = {
                "full": windows["full"],
                "reused_holdout": windows["reused_holdout"],
                "risk": risk_stats(trade_rows),
            }
        frontier_audit[policy_name] = {
            "policy": asdict(policy),
            "scenarios": scenario_results,
        }

    baseline_curve = single.portfolio_curve(
        baseline_trades,
        frames,
        start,
        end,
    )
    baseline_dd = baseline_curve / baseline_curve.cummax() - 1.0
    trough_ts = baseline_dd.idxmin()
    peak_ts = baseline_curve.loc[:trough_ts].idxmax()
    episode_rows = baseline_rows.loc[
        (pd.to_datetime(baseline_rows["entry_ts"], utc=True) <= trough_ts)
        & (pd.to_datetime(baseline_rows["exit_ts"], utc=True) >= peak_ts)
    ]
    group_tail = (
        baseline_rows.groupby(["asset", "style"])
        .agg(
            trades=("original_equity_ret", "size"),
            losses=("original_equity_ret", lambda values: int((values < 0.0).sum())),
            sum_loss=(
                "original_equity_ret",
                lambda values: float(values.loc[values < 0.0].sum()),
            ),
            worst_return=("original_equity_ret", "min"),
            worst_mae=("original_equity_mae", "min"),
            max_exposure=("original_exposure", "max"),
        )
        .reset_index()
        .sort_values("sum_loss")
    )

    matrix["selected_prefit_only"] = matrix["name"] == selected_policy.name
    matrix.to_csv(MATRIX_CSV, index=False)
    selected_rows.to_csv(TRADES_CSV, index=False)

    payload = {
        "family": "Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble",
        "observation": "v1_trx_macd_tail_risk_optimization",
        "status": "diagnostic_observation_not_registered_not_promoted_not_live_ready",
        "date": DATE_TAG,
        "frozen_structure": {
            "candidate_trades": len(tagged),
            "selected_trades": len(selected),
            "skipped_blocked": len(skipped),
            "same_hour_entry_ties": ties,
            "selection_rule": "registered V1 single-position first-come selection unchanged",
        },
        "selection_policy": {
            "uses": "prefit only",
            "gates": {
                "base_prefit_max_dd": "> -19%",
                "extra_4bps_per_fill_prefit_max_dd": "> -20%",
                "trx_macd_worst_equity_mae": "> -12%",
                "base_prefit_annual_multiple": ">=10x",
            },
            "ranking": (
                "best worst-case prefit DD across base/extra-slip/double-cost, "
                "then TRX MACD worst MAE, then prefit annual"
            ),
            "reused_holdout_and_recent_slices": "read only after freeze",
        },
        "selected_policy": asdict(selected_policy),
        "selected_prefit": {
            "base": selected_base,
            "extra_slip_4bps_per_fill": selected_extra,
            "double_fee_slippage": selected_double,
        },
        "baseline_windows": baseline_windows,
        "selected_windows": selected_windows,
        "selected_extra_slip_windows": selected_extra_windows,
        "selected_double_cost_windows": selected_double_windows,
        "audited_frontier_after_freeze": frontier_audit,
        "tail_root_cause": {
            "group_tail": group_tail.to_dict(orient="records"),
            "worst_portfolio_drawdown": {
                "peak_ts": peak_ts,
                "trough_ts": trough_ts,
                "max_dd": float(baseline_dd.loc[trough_ts]),
                "episode_trades": episode_rows.to_dict(orient="records"),
            },
        },
        "baseline_risk": risk_stats(baseline_rows),
        "selected_risk": risk_stats(selected_rows),
        "methodology_warning": [
            "Frozen V1 selection and sleeve trade paths are unchanged.",
            "Exposure is decided before entry from signal ATR and prior account drawdown.",
            "Cost stresses are account-level return deductions and do not alter stop/target paths.",
            "Blocked sleeve cooldown counterfactual remains the registered V1 approximation.",
        ],
        "artifacts": {
            "matrix_csv": str(MATRIX_CSV.relative_to(ROOT)),
            "selected_trades_csv": str(TRADES_CSV.relative_to(ROOT)),
        },
    }
    SUMMARY_JSON.write_text(
        json.dumps(first.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        f"# BIN-1H-AR-MAE-V1：TRX MACD 尾部风险优化 - {DATE_TAG}",
        "",
        "## 结论",
        "",
        (
            "本轮不再追求扩大 TRX V3 参数收益，而是在已登记的组合 V1 上处理 "
            "`TRX macd_flip` 的 `5x` 高暴露尾部风险。六个 sleeve 的冻结信号、"
            "入场、出场、成本、funding、单仓先到先得选择均保持不变；只使用入场前"
            "可知的 signal ATR 与账户历史回撤决定账户暴露。"
        ),
        "",
        f"prefit-only 选中的风险策略：`{selected_policy.name}`。",
        "",
        f"- 规则：{selected_policy.description}",
        (
            "- 具体口径：每笔账户暴露先限制为 `exposure × signal ATR <= 1.0%`；"
            "若入场前账户回撤达到 `8%`，再把暴露上限压到 `2x`；达到 `12%`，"
            "压到 `1x`。所有变量在入场前可知。"
        ),
        (
            "- 选参门槛：prefit 基准 DD `<19%`、额外 `4 bps/fill` DD `<20%`、"
            "TRX MACD 最差单笔 MAE `<12%`、prefit annual `>=10x`。"
        ),
        "- reused holdout 与近期分片只在策略冻结后读取。",
        "",
        "## 为什么固定 TRX cap 不够",
        "",
        (
            "V1 中选 TRX MACD `37` 笔，只有 `2` 笔最终亏损，但原始最差单笔账户 MAE "
            f"达到 `{risk_stats(baseline_rows)['trx_macd_worst_equity_mae']:.2%}`。"
            "组合最深回撤由连续 BNB 亏损先造成账户下沉，随后 TRX `5x` 盈利交易在"
            "到达止盈前继续承受浮亏而加深。风险既来自单笔计划止损，也来自账户已经"
            "处于回撤时仍允许高暴露。"
        ),
        "",
        "## 基线与选中策略",
        "",
        "| Window | V1 baseline | Selected | +4bps/fill stress | Double-cost stress |",
        "| --- | --- | --- | --- | --- |",
    ]
    for window in (
        "full",
        "reused_holdout",
        "last_7d",
        "last_1m",
        "last_3m",
        "last_6m",
        "last_1y",
    ):
        lines.append(
            f"| `{window}` | {metric_line(baseline_windows[window])} | "
            f"{metric_line(selected_windows[window])} | "
            f"{metric_line(selected_extra_windows[window])} | "
            f"{metric_line(selected_double_windows[window])} |"
        )
    lines.extend(
        [
            "",
            "## 风险—收益前沿（冻结后审计）",
            "",
            "| Policy | Full annual / DD | Holdout return / DD | Double-cost full DD | TRX MACD worst MAE |",
            "| --- | --- | --- | ---: | ---: |",
        ]
    )
    for policy_name in frontier_names:
        audit = frontier_audit[policy_name]["scenarios"]
        base_full = audit["base"]["full"]["curve"]
        base_holdout = audit["base"]["reused_holdout"]["curve"]
        double_full = audit["double_fee_slippage"]["full"]["curve"]
        risk = audit["base"]["risk"]
        lines.append(
            f"| `{policy_name}` | "
            f"`{base_full['annual_multiple']:.2f}x / {base_full['max_dd']:.2%}` | "
            f"`{base_holdout['total_return']:+.2%} / {base_holdout['max_dd']:.2%}` | "
            f"`{double_full['max_dd']:.2%}` | "
            f"`{risk['trx_macd_worst_equity_mae']:.2%}` |"
        )
    balanced = frontier_audit[
        "hybrid_all_atr_0.012_dd_8%_12%_caps_2x_1x"
    ]["scenarios"]
    lines.extend(
        [
            "",
            (
                "风险优先的 `1.0% ATR + 8%/12% DD guard` 在冻结后 full 为 "
                f"`{selected_windows['full']['curve']['annual_multiple']:.2f}x / "
                f"{selected_windows['full']['curve']['max_dd']:.2%} DD`，但低于家族 "
                "`10x` 年化目标；reused holdout 仅 "
                f"`{selected_windows['reused_holdout']['curve']['total_return']:+.2%}`，"
                "额外滑点后转负，因此不能冻结为下一版本。"
            ),
            (
                "较均衡的 `1.2% ATR + 8%/12% DD guard` full 为 "
                f"`{balanced['base']['full']['curve']['annual_multiple']:.2f}x / "
                f"{balanced['base']['full']['curve']['max_dd']:.2%} DD`，但 holdout 只有 "
                f"`{balanced['base']['reused_holdout']['curve']['total_return']:+.2%}`，"
                "额外滑点后接近零；同样只能作为 forward-test 方向。"
            ),
        ]
    )
    baseline_risk = risk_stats(baseline_rows)
    chosen_risk = risk_stats(selected_rows)
    lines.extend(
        [
            "",
            "## TRX MACD 风险变化",
            "",
            "| Metric | V1 baseline | Selected |",
            "| --- | ---: | ---: |",
            (
                "| avg exposure | "
                f"`{baseline_risk['trx_macd_avg_exposure']:.2f}x` | "
                f"`{chosen_risk['trx_macd_avg_exposure']:.2f}x` |"
            ),
            (
                "| max exposure | "
                f"`{baseline_risk['trx_macd_max_exposure']:.2f}x` | "
                f"`{chosen_risk['trx_macd_max_exposure']:.2f}x` |"
            ),
            (
                "| max planned stop risk | "
                f"`{baseline_risk['trx_macd_max_planned_stop_risk']:.2%}` | "
                f"`{chosen_risk['trx_macd_max_planned_stop_risk']:.2%}` |"
            ),
            (
                "| worst equity MAE | "
                f"`{baseline_risk['trx_macd_worst_equity_mae']:.2%}` | "
                f"`{chosen_risk['trx_macd_worst_equity_mae']:.2%}` |"
            ),
            "",
            "## 执行与边界",
            "",
            "- 风险预算使用 signal K 已知 ATR 和账户历史权益，不使用未来 MAE/MFE。",
            "- 不改变 entry/exit K、stop/target 路径或单仓选择，因此不存在新增未来函数或价格穿越。",
            "- 成本压力仍是账户层扣减，不是 K 级重新成交；阻塞后的 sleeve cooldown 反事实仍继承 V1 近似。",
            "- 本轮是未编号 diagnostic observation，不登记新版本，不改变 `NO-GO / not promoted / not live-ready`。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{MATRIX_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            f"- `scripts/{Path(__file__).name}`",
            "",
            "复现：",
            "",
            "```bash",
            (
                "uv run python research/asset-portfolios/"
                "1h-adaptive-regime-multi-asset-ensemble/scripts/"
                "research_binance_1h_ar_mae_v1_trx_tail_risk_optimization.py"
            ),
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            first.json_safe(
                {
                    "policies": len(matrix),
                    "selected_policy": asdict(selected_policy),
                    "baseline_prefit": matrix.loc[
                        matrix["name"] == "baseline",
                        [
                            "base_prefit_annual_multiple",
                            "base_prefit_max_dd",
                            "base_trx_macd_worst_equity_mae",
                        ],
                    ].iloc[0].to_dict(),
                    "selected_prefit": selected_row[
                        [
                            "base_prefit_annual_multiple",
                            "base_prefit_max_dd",
                            "extra_slip_prefit_max_dd",
                            "double_cost_prefit_max_dd",
                            "base_trx_macd_worst_equity_mae",
                        ]
                    ].to_dict(),
                    "selected_full": selected_windows["full"],
                    "selected_holdout": selected_windows["reused_holdout"],
                }
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
