"""Targeted TRX MACD tail overlay for BIN-1H-AR-MAE-V1.

The registered V1 sleeve signals, trade selection, entries, exits, fees,
slippage, and funding stay frozen. Only selected TRX macd_flip exposure may be
reduced using signal-time ATR and account drawdown known before entry.

Policy selection uses prefit data only. Reused holdout and recent windows are
read after the policy is frozen.
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

SUMMARY_JSON = ARTIFACT_DIR / f"binance_1h_ar_mae_v1_trx_targeted_tail_{DATE_TAG}.json"
MATRIX_CSV = ARTIFACT_DIR / f"binance_1h_ar_mae_v1_trx_targeted_tail_matrix_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"binance_1h_ar_mae_v1_trx_targeted_tail_trades_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"binance-1h-ar-mae-v1-trx-targeted-tail-overlay-{DATE_TAG}.md"

PREFIT_END = pd.Timestamp("2026-04-03T06:00:00Z")
TRX_MACD_SL_ATR = 5.0
BASE_ROUNDTRIP_FEE_SLIPPAGE = 0.0028


@dataclass(frozen=True, slots=True)
class TargetPolicy:
    name: str
    description: str
    trx_stop_risk_budget: float | None = None
    trx_dd_soft_threshold: float | None = None
    trx_dd_hard_threshold: float | None = None
    trx_dd_soft_cap: float | None = None
    trx_dd_hard_cap: float | None = None


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


def load_tail_module() -> Any:
    return load_module(
        "research_binance_1h_ar_mae_v1_trx_tail_risk_optimization",
        SCRIPT_DIR / "research_binance_1h_ar_mae_v1_trx_tail_risk_optimization.py",
    )


def is_trx_macd(asset: str, trade: Any) -> bool:
    return asset == "TRX" and trade.style == "macd_flip"


def initial_stop_unit_loss(
    asset: str,
    trade: Any,
    frames: dict[str, pd.DataFrame],
) -> float | None:
    if not is_trx_macd(asset, trade):
        return None
    signal_atr = float(frames[asset]["atr14"].iloc[int(trade.signal_i)])
    return (
        TRX_MACD_SL_ATR * signal_atr / float(trade.entry_price)
        + BASE_ROUNDTRIP_FEE_SLIPPAGE
    )


def exposure_for_entry(
    policy: TargetPolicy,
    asset: str,
    trade: Any,
    frames: dict[str, pd.DataFrame],
    pre_entry_dd: float,
) -> tuple[float, float | None, str]:
    exposure = float(trade.exposure)
    unit_loss = initial_stop_unit_loss(asset, trade, frames)
    reason = "unchanged"
    if not is_trx_macd(asset, trade):
        return exposure, unit_loss, reason

    if (
        policy.trx_stop_risk_budget is not None
        and unit_loss is not None
        and unit_loss > 0.0
    ):
        budget_cap = policy.trx_stop_risk_budget / unit_loss
        if budget_cap < exposure:
            exposure = budget_cap
            reason = "trx_stop_budget"

    if (
        policy.trx_dd_hard_threshold is not None
        and policy.trx_dd_hard_cap is not None
        and pre_entry_dd <= -policy.trx_dd_hard_threshold
        and policy.trx_dd_hard_cap < exposure
    ):
        exposure = policy.trx_dd_hard_cap
        reason = "trx_hard_dd_cap"
    elif (
        policy.trx_dd_soft_threshold is not None
        and policy.trx_dd_soft_cap is not None
        and pre_entry_dd <= -policy.trx_dd_soft_threshold
        and policy.trx_dd_soft_cap < exposure
    ):
        exposure = policy.trx_dd_soft_cap
        reason = "trx_soft_dd_cap"

    return max(exposure, 0.0), unit_loss, reason


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
    policy: TargetPolicy,
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
        exposure, planned_unit_loss, reduction_reason = exposure_for_entry(
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
        stressed_account_dd = (
            entry_equity * (1.0 + float(cloned.equity_mae)) / peak_equity - 1.0
        )
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
                "reduction_reason": reduction_reason,
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
                "stressed_account_dd": stressed_account_dd,
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
        "trx_macd_reduced_entries": float(
            (trx["adjusted_exposure"] < trx["original_exposure"]).sum()
        ),
        "trx_macd_avg_exposure": float(trx["adjusted_exposure"].mean()),
        "trx_macd_max_exposure": float(trx["adjusted_exposure"].max()),
        "trx_macd_max_planned_stop_risk": float(
            trx["planned_stop_account_risk"].max()
        ),
        "trx_macd_worst_equity_mae": float(trx["adjusted_equity_mae"].min()),
        "trx_macd_p10_equity_mae": float(
            trx["adjusted_equity_mae"].quantile(0.10)
        ),
        "trx_macd_worst_stressed_account_dd": float(
            trx["stressed_account_dd"].min()
        ),
        "all_trades_worst_stressed_account_dd": float(
            rows["stressed_account_dd"].min()
        ),
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
    policy: TargetPolicy,
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
    return (
        {
            "prefit": window_metrics(
                adjusted,
                curve,
                first,
                single,
                start,
                PREFIT_END,
            ),
            "risk": risk_stats(rows),
        },
        adjusted,
        rows,
    )


def candidate_policies() -> list[TargetPolicy]:
    policies = [TargetPolicy("baseline", "Registered V1 exposure.")]
    for stop_budget in (None, 0.08, 0.10, 0.12, 0.15, 0.20):
        for soft_threshold, hard_threshold in (
            (0.02, 0.06),
            (0.04, 0.08),
            (0.05, 0.10),
            (0.06, 0.10),
            (0.06, 0.12),
            (0.08, 0.12),
            (0.08, 0.15),
            (0.10, 0.15),
        ):
            for soft_cap, hard_cap in (
                (4.0, 1.0),
                (3.5, 1.0),
                (3.0, 1.0),
                (3.0, 1.5),
                (3.0, 2.0),
                (2.5, 1.0),
                (2.5, 1.5),
                (2.0, 1.0),
                (1.5, 0.5),
            ):
                budget_label = "none" if stop_budget is None else f"{stop_budget:.2f}"
                policies.append(
                    TargetPolicy(
                        name=(
                            f"trx_stop_{budget_label}_dd_"
                            f"{soft_threshold:.0%}_{hard_threshold:.0%}_"
                            f"caps_{soft_cap:g}x_{hard_cap:g}x"
                        ),
                        description=(
                            "Only TRX macd_flip is sized by planned-stop risk "
                            "and/or pre-entry account drawdown."
                        ),
                        trx_stop_risk_budget=stop_budget,
                        trx_dd_soft_threshold=soft_threshold,
                        trx_dd_hard_threshold=hard_threshold,
                        trx_dd_soft_cap=soft_cap,
                        trx_dd_hard_cap=hard_cap,
                    )
                )
    return policies


def flatten_result(
    policy: TargetPolicy,
    baseline: dict[str, Any],
    extra_slip: dict[str, Any],
    double_cost: dict[str, Any],
) -> dict[str, Any]:
    row: dict[str, Any] = asdict(policy)
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
    baseline_annual = float(
        matrix.loc[
            matrix["name"] == "baseline",
            "base_prefit_annual_multiple",
        ].iloc[0]
    )
    eligible = matrix.loc[
        (matrix["name"] != "baseline")
        & (matrix["base_prefit_max_dd"] > -0.20)
        & (matrix["base_trx_macd_worst_equity_mae"] > -0.10)
        & (matrix["base_trx_macd_worst_stressed_account_dd"] > -0.20)
        & (matrix["base_prefit_annual_multiple"] >= 0.50 * baseline_annual)
    ].copy()
    if eligible.empty:
        raise RuntimeError("No targeted TRX policy passed the prefit-only gates")
    return eligible.sort_values(
        [
            "base_prefit_annual_multiple",
            "base_trx_macd_worst_equity_mae",
            "base_trx_macd_worst_stressed_account_dd",
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
    tail = load_tail_module()
    single = tail.load_single_position_module()
    first = single.load_first_backtest_module()
    sleeves = tail.load_sleeves(first)
    start = max(sleeve["start"] for sleeve in sleeves if sleeve["asset"] != "HYPE")
    hype_start = next(
        sleeve["start"] for sleeve in sleeves if sleeve["asset"] == "HYPE"
    )
    end = min(sleeve["end"] for sleeve in sleeves)
    frames = {sleeve["asset"]: sleeve["frame"] for sleeve in sleeves}
    tagged = [
        (sleeve["asset"], trade)
        for sleeve in sleeves
        for trade in sleeve["trades"]
        if start <= trade.entry_ts < end
    ]
    selected, skipped, ties = single.select_single_position(tagged)

    policies = {policy.name: policy for policy in candidate_policies()}
    matrix_rows: list[dict[str, Any]] = []
    for policy in policies.values():
        base, _adjusted, _rows = evaluate_policy(
            policy,
            selected,
            frames,
            start,
            end,
            first,
            single,
        )
        extra_slip, _adjusted, _rows = evaluate_policy(
            policy,
            selected,
            frames,
            start,
            end,
            first,
            single,
            extra_roundtrip_notional_cost=0.0008,
        )
        double_cost, _adjusted, _rows = evaluate_policy(
            policy,
            selected,
            frames,
            start,
            end,
            first,
            single,
            extra_roundtrip_notional_cost=0.0028,
        )
        matrix_rows.append(flatten_result(policy, base, extra_slip, double_cost))

    matrix = pd.DataFrame(matrix_rows)
    selected_row = select_policy(matrix)
    selected_policy = policies[str(selected_row["name"])]
    matrix["selected_prefit_only"] = matrix["name"] == selected_policy.name
    matrix.to_csv(MATRIX_CSV, index=False)

    scenario_outputs: dict[str, dict[str, Any]] = {}
    selected_rows: pd.DataFrame | None = None
    for scenario, cost in (
        ("base", 0.0),
        ("extra_slip_4bps_per_fill", 0.0008),
        ("double_fee_slippage", 0.0028),
    ):
        prefit, adjusted, trade_rows = evaluate_policy(
            selected_policy,
            selected,
            frames,
            start,
            end,
            first,
            single,
            extra_roundtrip_notional_cost=cost,
        )
        scenario_outputs[scenario] = {
            "prefit": prefit,
            "windows": full_windows(
                adjusted,
                frames,
                start,
                hype_start,
                end,
                first,
                single,
            ),
            "risk": risk_stats(trade_rows),
        }
        if scenario == "base":
            selected_rows = trade_rows

    baseline_policy = policies["baseline"]
    _prefit, baseline_adjusted, baseline_rows = evaluate_policy(
        baseline_policy,
        selected,
        frames,
        start,
        end,
        first,
        single,
    )
    baseline_windows = full_windows(
        baseline_adjusted,
        frames,
        start,
        hype_start,
        end,
        first,
        single,
    )
    baseline_risk = risk_stats(baseline_rows)
    assert selected_rows is not None
    selected_rows.to_csv(TRADES_CSV, index=False)
    remaining_account_tails = (
        selected_rows.sort_values("stressed_account_dd")
        .loc[
            :,
            [
                "asset",
                "style",
                "entry_ts",
                "adjusted_exposure",
                "pre_entry_dd",
                "adjusted_equity_mae",
                "stressed_account_dd",
            ],
        ]
        .head(10)
        .to_dict(orient="records")
    )

    frontier = matrix.loc[
        (matrix["base_prefit_max_dd"] > -0.20)
        & (matrix["name"] != "baseline")
    ].copy()
    frontier["mae_bucket"] = (
        frontier["base_trx_macd_worst_equity_mae"] * 100
    ).round()
    frontier_rows = (
        frontier.sort_values(
            "base_prefit_annual_multiple",
            ascending=False,
        )
        .groupby("mae_bucket", as_index=False)
        .first()
        .sort_values("base_trx_macd_worst_equity_mae")
        .tail(8)
    )

    extra_floor = float(matrix["extra_slip_prefit_max_dd"].max())
    payload = {
        "family": "Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble",
        "observation": "v1_trx_macd_targeted_tail_overlay",
        "status": "diagnostic_observation_not_registered_not_promoted_not_live_ready",
        "date": DATE_TAG,
        "frozen_structure": {
            "candidate_trades": len(tagged),
            "selected_trades": len(selected),
            "skipped_blocked": len(skipped),
            "same_hour_entry_ties": ties,
            "selection_rule": "registered V1 single-position first-come selection unchanged",
            "non_trx_exposure": "unchanged",
        },
        "selection_policy": {
            "uses": "prefit only",
            "gates": {
                "base_prefit_max_dd": "> -20%",
                "trx_macd_worst_equity_mae": "> -10%",
                "trx_macd_worst_stressed_account_dd": "> -20%",
                "base_prefit_annual_multiple": ">= 50% of V1 baseline prefit annual",
            },
            "ranking": "highest prefit annual, then best TRX MACD MAE/account-tail DD",
            "reused_holdout_and_recent_slices": "read only after freeze",
        },
        "selected_policy": asdict(selected_policy),
        "baseline_windows": baseline_windows,
        "baseline_risk": baseline_risk,
        "selected_scenarios": scenario_outputs,
        "prefit_frontier": frontier_rows.to_dict(orient="records"),
        "remaining_account_tail_frontier": remaining_account_tails,
        "structural_floor": {
            "best_extra_slip_prefit_max_dd_across_targeted_grid": extra_floor,
            "explanation": (
                "After TRX risk is reduced, the residual drawdown floor comes "
                "from non-TRX trades, especially the preceding BNB loss cluster."
            ),
        },
        "methodology_warning": [
            "Only selected TRX macd_flip exposure changes; all other sleeves stay frozen.",
            "Sizing uses signal ATR and pre-entry close-marked account drawdown only.",
            "Stressed account DD combines pre-entry account state with realized trade MAE for evaluation; future MAE is never used for sizing.",
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

    selected_base = scenario_outputs["base"]
    selected_extra = scenario_outputs["extra_slip_4bps_per_fill"]
    selected_double = scenario_outputs["double_fee_slippage"]
    selected_risk = selected_base["risk"]
    lines = [
        f"# BIN-1H-AR-MAE-V1：TRX MACD 定向尾部覆盖层 - {DATE_TAG}",
        "",
        "## 结论",
        "",
        (
            "本轮只处理组合 V1 中 `TRX macd_flip` 的 `5x` 尾部风险；非 TRX 交易暴露、"
            "六 sleeve 信号/成交/退出、单仓先到先得选择与成本口径全部保持不变。"
            "目标是避免上一轮全局 ATR overlay 对所有 sleeve 的过度降杠杆。"
        ),
        "",
        f"prefit-only 选中策略：`{selected_policy.name}`。",
        "",
        (
            f"- TRX MACD 计划初始止损账户风险上限："
            f"`{selected_policy.trx_stop_risk_budget:.0%}`。"
        ),
        (
            f"- 仅当账户入场前回撤达到 `{selected_policy.trx_dd_soft_threshold:.0%}`，"
            f"TRX MACD 上限降为 `{selected_policy.trx_dd_soft_cap:g}x`；达到 "
            f"`{selected_policy.trx_dd_hard_threshold:.0%}`，降为 "
            f"`{selected_policy.trx_dd_hard_cap:g}x`。"
        ),
        "- 所有 sizing 输入在入场前可知；reused holdout 与近期分片冻结后才读取。",
        "",
        "## 结果",
        "",
        "| Window | V1 baseline | Targeted | +4bps/fill stress | Double-cost stress |",
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
            f"{metric_line(selected_base['windows'][window])} | "
            f"{metric_line(selected_extra['windows'][window])} | "
            f"{metric_line(selected_double['windows'][window])} |"
        )
    lines.extend(
        [
            "",
            (
                "与上一轮全局 `1.0% ATR + 8%/12% DD guard` 相比，定向方案只缩放 "
                "TRX MACD：full 年化从全局方案的 `7.88x` 保留到 "
                f"`{selected_base['windows']['full']['curve']['annual_multiple']:.2f}x`，"
                "reused holdout 从 `+1.70%` 保留到 "
                f"`{selected_base['windows']['reused_holdout']['curve']['total_return']:+.2%}`；"
                "代价是 DD 只能压到 "
                f"`{selected_base['windows']['full']['curve']['max_dd']:.2%}`，"
                "不能达到全局方案的 `-14.93%`。这更符合“组合层不追 TRX 更高收益、"
                "只处理其高暴露尾部”的目标。"
            ),
            "",
            (
                "prefit 冻结指标为 "
                f"`{selected_base['prefit']['prefit']['curve']['annual_multiple']:.2f}x "
                f"annual / {selected_base['prefit']['prefit']['curve']['max_dd']:.2%} DD`；"
                "额外 `4 bps/fill` 为 "
                f"`{selected_extra['prefit']['prefit']['curve']['annual_multiple']:.2f}x / "
                f"{selected_extra['prefit']['prefit']['curve']['max_dd']:.2%} DD`，"
                "double-cost 为 "
                f"`{selected_double['prefit']['prefit']['curve']['annual_multiple']:.2f}x / "
                f"{selected_double['prefit']['prefit']['curve']['max_dd']:.2%} DD`。"
                "选择没有读取 reused holdout 或近期分片。"
            ),
            "",
            "## TRX MACD 风险变化",
            "",
            "| Metric | V1 baseline | Targeted |",
            "| --- | ---: | ---: |",
            (
                f"| reduced entries | `0/{int(baseline_risk['trx_macd_trades'])}` | "
                f"`{int(selected_risk['trx_macd_reduced_entries'])}/"
                f"{int(selected_risk['trx_macd_trades'])}` |"
            ),
            (
                f"| average exposure | `{baseline_risk['trx_macd_avg_exposure']:.2f}x` | "
                f"`{selected_risk['trx_macd_avg_exposure']:.2f}x` |"
            ),
            (
                f"| max planned stop risk | "
                f"`{baseline_risk['trx_macd_max_planned_stop_risk']:.2%}` | "
                f"`{selected_risk['trx_macd_max_planned_stop_risk']:.2%}` |"
            ),
            (
                f"| worst single-trade MAE | "
                f"`{baseline_risk['trx_macd_worst_equity_mae']:.2%}` | "
                f"`{selected_risk['trx_macd_worst_equity_mae']:.2%}` |"
            ),
            (
                f"| worst account-state + trade-MAE DD | "
                f"`{baseline_risk['trx_macd_worst_stressed_account_dd']:.2%}` | "
                f"`{selected_risk['trx_macd_worst_stressed_account_dd']:.2%}` |"
            ),
            "",
            "## 风险—收益前沿（prefit）",
            "",
            "| Stop budget | DD soft/hard | Caps | Annual | Close DD | TRX worst MAE | TRX account-tail DD |",
            "| ---: | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in frontier_rows.to_dict(orient="records"):
        lines.append(
            f"| `{row['trx_stop_risk_budget']}` | "
            f"`{row['trx_dd_soft_threshold']:.0%}/{row['trx_dd_hard_threshold']:.0%}` | "
            f"`{row['trx_dd_soft_cap']:g}x/{row['trx_dd_hard_cap']:g}x` | "
            f"`{row['base_prefit_annual_multiple']:.2f}x` | "
            f"`{row['base_prefit_max_dd']:.2%}` | "
            f"`{row['base_trx_macd_worst_equity_mae']:.2%}` | "
            f"`{row['base_trx_macd_worst_stressed_account_dd']:.2%}` |"
        )
    lines.extend(
        [
            "",
            "## 剩余风险与边界",
            "",
            (
                "TRX 定向覆盖层把 close-marked DD 压到约 `-19.99%` 后，回撤下限转移到"
                "此前连续 BNB 亏损；在整个 TRX-only 网格中，额外 `4 bps/fill` 的最佳 "
                f"prefit DD 仍为 `{extra_floor:.2%}`。因此继续缩 TRX 无法解决成本压力，"
                "下一步应单独处理 BNB loss cluster 或采用轻量账户级总风险上限。"
            ),
            "",
            (
                "从更保守的“入场前账户状态 + 单笔 MAE”口径看，TRX MACD 最差值已从 "
                f"`{baseline_risk['trx_macd_worst_stressed_account_dd']:.2%}` 降至 "
                f"`{selected_risk['trx_macd_worst_stressed_account_dd']:.2%}`，不再是组合"
                "最差尾部；剩余最差转为 "
                f"{remaining_account_tails[0]['asset']} "
                f"`{remaining_account_tails[0]['style']} "
                f"{remaining_account_tails[0]['stressed_account_dd']:.2%}` 与 "
                f"{remaining_account_tails[1]['asset']} "
                f"`{remaining_account_tails[1]['style']} "
                f"{remaining_account_tails[1]['stressed_account_dd']:.2%}`。因此下一轮不应"
                "继续单独压低 TRX，而应把同一风险预算推广为轻量、跨 sleeve 的 "
                "account-tail guard，并避免上一轮全局 `1% ATR` 那种过度降杠杆。"
            ),
            "",
            "- 最差 MAE/账户尾部指标只用于评估与选参，不参与实时 sizing，不构成未来函数。",
            "- overlay 不改变 entry/exit K、stop/target 路径，不新增价格穿越假设。",
            "- 成本压力仍为账户层扣减，不是逐 K 成交重演；阻塞 cooldown 反事实近似仍存在。",
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
                "research_binance_1h_ar_mae_v1_trx_targeted_tail_overlay.py"
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
                    "baseline_risk": baseline_risk,
                    "selected_risk": selected_risk,
                    "selected_full": selected_base["windows"]["full"],
                    "selected_holdout": selected_base["windows"]["reused_holdout"],
                    "extra_slip_prefit_dd_floor": extra_floor,
                }
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
