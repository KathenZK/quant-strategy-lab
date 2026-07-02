from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_hype_1h_adaptive_regime_boundary as boundary  # noqa: E402
import audit_hype_1h_ar_v2_tune_frontier as frontier  # noqa: E402
import research_hype_1h_adaptive_regime_search as base  # noqa: E402
import research_hype_1h_ar_v2_clean_tune as v2  # noqa: E402


DATE_TAG = "2026-07-02"
FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DI_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_di_coordinate_{DATE_TAG}.csv"
STOCH_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_stoch_coordinate_{DATE_TAG}.csv"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_ar_v2_live_robust_tune_{DATE_TAG}.json"
RANKING_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_live_robust_ranking_{DATE_TAG}.csv"
STRESS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_live_robust_stress_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_live_robust_trades_{DATE_TAG}.csv"
REPORT_MD = (
    FAMILY_DIR
    / "research-notes"
    / f"hype-1h-ar-v2-live-robust-prefit-tune-{DATE_TAG}.md"
)

PREFIT_SCENARIOS = (
    ("base_k1", 0.0010, 0.0004, 1),
    ("delay_k2", 0.0010, 0.0004, 2),
    ("slip_8bps", 0.0010, 0.0008, 1),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="V2 prefit-only live-robust pair search"
    )
    parser.add_argument("--pool-size", type=int, default=400)
    return parser.parse_args()


def bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().eq("true")


def retain_pool(frame: pd.DataFrame, pool_size: int) -> pd.DataFrame:
    eligible = frame.loc[
        (frame["prefit_trades"] >= base.MIN_PREFIT_TRADES)
        & (frame["validation_trades"] >= base.MIN_VALIDATION_TRADES)
        & (frame["prefit_annual_multiple"] > 0.0)
        & (frame["validation_total_return"] > 0.0)
        & (frame["prefit_max_dd"] > -0.30)
    ].copy()
    eligible["prefit_robust_bool"] = bool_series(eligible["prefit_robust_pass"])
    eligible["prefit_strict_bool"] = bool_series(
        eligible["prefit_strict_dominance"]
    )
    ranked = eligible.sort_values(
        ["prefit_strict_bool", "prefit_robust_bool", "selection_score"],
        ascending=False,
    )
    annual = eligible.loc[eligible["prefit_max_dd"] > -0.20].sort_values(
        "prefit_annual_multiple", ascending=False
    )
    drawdown = eligible.sort_values(
        ["prefit_max_dd", "prefit_annual_multiple"], ascending=False
    )
    chunks = pd.concat(
        [
            ranked.head(max(1, int(pool_size * 0.60))),
            annual.head(max(1, int(pool_size * 0.25))),
            drawdown.head(max(1, int(pool_size * 0.15))),
            ranked,
        ],
        ignore_index=True,
    )
    return chunks.drop_duplicates("config_id").head(pool_size)


def simulate_pool(
    *,
    pool: pd.DataFrame,
    component: str,
    scenario: str,
    fee: float,
    slippage: float,
    delay: int,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
) -> dict[str, list[base.Trade]]:
    base.FEE_PER_FILL = fee
    base.SLIPPAGE_PER_FILL = slippage
    output: dict[str, list[base.Trade]] = {}
    cls = v2.DICleanConfig if component == "di_cross" else v2.StochCleanConfig
    for index, row in enumerate(pool.itertuples(index=False)):
        series = pd.Series(row._asdict())
        clean = frontier.config_from_row(series, cls)
        cfg = (
            v2.di_to_base(clean, str(row.config_id))
            if component == "di_cross"
            else v2.stoch_to_base(clean, str(row.config_id))
        )
        cfg = replace(cfg, entry_delay_bars=delay)
        output[str(row.config_id)] = boundary.component_trades(
            frame, funding_times, funding_cumulative, cfg
        )
        if (index + 1) % 200 == 0:
            print(
                f"simulate {scenario} {component}: {index + 1}/{len(pool)}",
                flush=True,
            )
    return output


def scenario_gate(values: dict[str, Any], *, require_improvement: bool) -> bool:
    gate = bool(
        values["prefit_trades"] >= base.MIN_PREFIT_TRADES
        and values["prefit_total_return"] > 0.0
        and values["prefit_win_rate"] >= base.TARGET_WIN_RATE
        and values["prefit_max_dd"] > base.TARGET_MAX_DD
        and values["validation_trades"] >= base.MIN_VALIDATION_TRADES
        and values["validation_total_return"] > 0.0
        and values["validation_win_rate"] >= base.TARGET_WIN_RATE
        and values["validation_max_dd"] > base.TARGET_MAX_DD
        and values["eligible_folds"] >= 3
        and values["positive_folds"] >= 3
        and values["worst_fold_dd"] > base.TARGET_MAX_DD
    )
    if not require_improvement:
        return gate
    return bool(
        gate
        and values["prefit_annual_multiple"]
        > 11.666474  # frozen V2 baseline on the refreshed dataset
        and values["prefit_max_dd"] > -0.169312
    )


def robust_score(metrics: dict[str, dict[str, Any]]) -> float:
    annuals = [
        max(metrics[name]["prefit_annual_multiple"], 1e-9)
        for name, *_rest in PREFIT_SCENARIOS
    ]
    validations = [
        max(metrics[name]["validation_annual_multiple"], 1e-9)
        for name, *_rest in PREFIT_SCENARIOS
    ]
    worst_dd = min(
        metrics[name]["prefit_max_dd"] for name, *_rest in PREFIT_SCENARIOS
    )
    worst_win = min(
        metrics[name]["prefit_win_rate"] for name, *_rest in PREFIT_SCENARIOS
    )
    return float(
        1.4 * math.log(min(annuals))
        + 0.7 * sum(math.log(item) for item in annuals) / len(annuals)
        + 0.3 * math.log(min(validations))
        + 2.5 * worst_dd
        + 0.8 * worst_win
    )


def pair_search(
    *,
    di_pool: pd.DataFrame,
    stoch_pool: pd.DataFrame,
    trades: dict[str, dict[str, dict[str, list[base.Trade]]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total = len(di_pool) * len(stoch_pool)
    checked = 0
    for di_id in di_pool["config_id"].astype(str):
        for stoch_id in stoch_pool["config_id"].astype(str):
            checked += 1
            merged_base = base.merge_trade_sets(
                trades["base_k1"]["di"][di_id],
                trades["base_k1"]["stoch"][stoch_id],
                1.0,
                0.0,
            )
            base_values = v2.selection_metrics(merged_base)
            if not scenario_gate(base_values, require_improvement=True):
                continue
            by_scenario = {"base_k1": base_values}
            rejected = False
            for scenario in ("delay_k2", "slip_8bps"):
                merged = base.merge_trade_sets(
                    trades[scenario]["di"][di_id],
                    trades[scenario]["stoch"][stoch_id],
                    1.0,
                    0.0,
                )
                values = v2.selection_metrics(merged)
                by_scenario[scenario] = values
                if not scenario_gate(values, require_improvement=False):
                    rejected = True
                    break
            if rejected:
                continue
            row: dict[str, Any] = {
                "di_id": di_id,
                "stoch_id": stoch_id,
                "robust_score": robust_score(by_scenario),
            }
            for scenario, values in by_scenario.items():
                for key, value in values.items():
                    row[f"{scenario}_{key}"] = value
            rows.append(row)
            if checked % 25_000 == 0:
                print(
                    f"pairs {checked}/{total}; robust={len(rows)}",
                    flush=True,
                )
    return sorted(rows, key=lambda item: item["robust_score"], reverse=True)


def main() -> None:
    args = parse_args()
    if args.pool_size < 50:
        raise ValueError("--pool-size must be >= 50")
    frame, funding, quality = base.load_data()
    frame = base.add_features(frame, funding)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    di_all = pd.read_csv(DI_CSV)
    stoch_all = pd.read_csv(STOCH_CSV)
    di_pool = retain_pool(di_all, args.pool_size)
    stoch_pool = retain_pool(stoch_all, args.pool_size)
    print(
        f"pools: di={len(di_pool)} stoch={len(stoch_pool)} "
        f"pairs={len(di_pool) * len(stoch_pool)}",
        flush=True,
    )

    original_fee = base.FEE_PER_FILL
    original_slippage = base.SLIPPAGE_PER_FILL
    scenario_trades: dict[str, dict[str, dict[str, list[base.Trade]]]] = {}
    try:
        for scenario, fee, slippage, delay in PREFIT_SCENARIOS:
            scenario_trades[scenario] = {
                "di": simulate_pool(
                    pool=di_pool,
                    component="di_cross",
                    scenario=scenario,
                    fee=fee,
                    slippage=slippage,
                    delay=delay,
                    frame=frame,
                    funding_times=funding_times,
                    funding_cumulative=funding_cumulative,
                ),
                "stoch": simulate_pool(
                    pool=stoch_pool,
                    component="stoch_reversal",
                    scenario=scenario,
                    fee=fee,
                    slippage=slippage,
                    delay=delay,
                    frame=frame,
                    funding_times=funding_times,
                    funding_cumulative=funding_cumulative,
                ),
            }
        ranking = pair_search(
            di_pool=di_pool, stoch_pool=stoch_pool, trades=scenario_trades
        )
    finally:
        base.FEE_PER_FILL = original_fee
        base.SLIPPAGE_PER_FILL = original_slippage

    selected_row = ranking[0] if ranking else None
    selected_di: v2.DICleanConfig | None = None
    selected_stoch: v2.StochCleanConfig | None = None
    selected_current: dict[str, Any] | None = None
    selected_stress: list[dict[str, Any]] = []
    selected_trades: list[base.Trade] = []
    if selected_row is not None:
        di_row = di_all.set_index("config_id").loc[selected_row["di_id"]]
        stoch_row = stoch_all.set_index("config_id").loc[selected_row["stoch_id"]]
        selected_di = frontier.config_from_row(di_row, v2.DICleanConfig)
        selected_stoch = frontier.config_from_row(stoch_row, v2.StochCleanConfig)
        assert isinstance(selected_di, v2.DICleanConfig)
        assert isinstance(selected_stoch, v2.StochCleanConfig)
        selected_trades = base.merge_trade_sets(
            scenario_trades["base_k1"]["di"][selected_row["di_id"]],
            scenario_trades["base_k1"]["stoch"][selected_row["stoch_id"]],
            1.0,
            0.0,
        )
        selected_current = v2.current_metrics(selected_trades, full_end)
        selected_stress = v2.stress_rows(
            di_cfg=selected_di,
            stoch_cfg=selected_stoch,
            frame=frame,
            funding_times=funding_times,
            funding_cumulative=funding_cumulative,
            full_end=full_end,
        )

    tune_id = (
        f"HYPE-1H-Adaptive-Regime-V2-LIVE-ROBUST-TUNE__{selected_row['di_id']}__{selected_row['stoch_id']}"
        if selected_row
        else None
    )
    stress_map = {row["scenario"]: row for row in selected_stress}
    current_target_pass = False
    stress_shape_pass = False
    if selected_current is not None:
        holdout = {
            key.removeprefix("reused_holdout_"): value
            for key, value in selected_current.items()
            if key.startswith("reused_holdout_")
        }
        full = {
            key.removeprefix("current_full_"): value
            for key, value in selected_current.items()
            if key.startswith("current_full_")
        }
        current_target_pass = base.target_gate(holdout, full)
        stress_shape_pass = all(
            stress_map[name]["reused_holdout_total_return"] > 0.0
            and stress_map[name]["reused_holdout_max_dd"] > base.TARGET_MAX_DD
            and stress_map[name]["reused_holdout_win_rate"] >= base.TARGET_WIN_RATE
            and stress_map[name]["current_full_total_return"] > 0.0
            and stress_map[name]["current_full_max_dd"] > base.TARGET_MAX_DD
            and stress_map[name]["current_full_win_rate"] >= base.TARGET_WIN_RATE
            for name in ("delay_k2", "slip_8bps")
        )

    pd.DataFrame(ranking[:1000]).to_csv(RANKING_CSV, index=False)
    pd.DataFrame(selected_stress).to_csv(STRESS_CSV, index=False)
    pd.DataFrame(base.trade_rows(selected_trades)).to_csv(TRADES_CSV, index=False)
    payload = {
        "family": "HYPE-1H-Adaptive-Regime",
        "version_base": "HYPE-1H-Adaptive-Regime-V2",
        "status": "research_observation_not_live_ready_not_promoted",
        "selection_used_reused_holdout": False,
        "selection_used_current_full": False,
        "data_quality": quality,
        "pool_size_requested": args.pool_size,
        "di_pool": len(di_pool),
        "stoch_pool": len(stoch_pool),
        "pair_evaluations": len(di_pool) * len(stoch_pool),
        "prefit_live_robust_pairs": len(ranking),
        "tune_id": tune_id,
        "selected_prefit": selected_row,
        "selected_di_config": asdict(selected_di) if selected_di else None,
        "selected_stoch_config": asdict(selected_stoch) if selected_stoch else None,
        "selected_current_diagnostics": selected_current,
        "current_target_pass": current_target_pass,
        "stress_shape_pass": stress_shape_pass,
        "selected_stress": selected_stress,
        "promotion_blockers": [
            "reused holdout is no longer untouched OOS",
            "no new forward trades after freeze",
            "no production runner/restart recovery/exchange reconciliation",
            "no real stop-market slippage evidence",
        ],
    }
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# HYPE-1H-Adaptive-Regime-V2 实盘稳健性前置微调 - 2026-07-02",
        "",
        "## 结论",
        "",
        "`research observation / not live-ready / not promoted`。",
        "",
        f"本轮不再先追 K+1 年化再验尸，而是在 prefit 内把 base K+1、K+2 延迟与 8 bps/fill 滑点共同纳入筛选。DI pool `{len(di_pool)}`、Stoch pool `{len(stoch_pool)}`、组合 `{len(di_pool) * len(stoch_pool)}`；prefit 三场景稳健命中 `{len(ranking)}`。参数排序没有使用 reused holdout 或 current full。",
        "",
    ]
    if selected_row is None:
        lines.extend(
            [
                "没有组合通过 prefit live-robust gate，因此没有冻结新观察。V2 clean baseline 保持不变。",
                "",
            ]
        )
    else:
        assert selected_current is not None
        lines.extend(
            [
                f"冻结观察：`{tune_id}`。",
                "",
                "| Window | Annual multiple | Max DD | Win rate | Trades |",
                "| --- | ---: | ---: | ---: | ---: |",
                f"| Prefit base K+1 | `{base.mult(selected_row['base_k1_prefit_annual_multiple'])}` | `{base.pct(selected_row['base_k1_prefit_max_dd'])}` | `{base.pct(selected_row['base_k1_prefit_win_rate'])}` | `{int(selected_row['base_k1_prefit_trades'])}` |",
                f"| Prefit K+2 | `{base.mult(selected_row['delay_k2_prefit_annual_multiple'])}` | `{base.pct(selected_row['delay_k2_prefit_max_dd'])}` | `{base.pct(selected_row['delay_k2_prefit_win_rate'])}` | `{int(selected_row['delay_k2_prefit_trades'])}` |",
                f"| Prefit 8 bps slip | `{base.mult(selected_row['slip_8bps_prefit_annual_multiple'])}` | `{base.pct(selected_row['slip_8bps_prefit_max_dd'])}` | `{base.pct(selected_row['slip_8bps_prefit_win_rate'])}` | `{int(selected_row['slip_8bps_prefit_trades'])}` |",
                f"| Reused holdout | `{base.mult(selected_current['reused_holdout_annual_multiple'])}` | `{base.pct(selected_current['reused_holdout_max_dd'])}` | `{base.pct(selected_current['reused_holdout_win_rate'])}` | `{int(selected_current['reused_holdout_trades'])}` |",
                f"| Current full | `{base.mult(selected_current['current_full_annual_multiple'])}` | `{base.pct(selected_current['current_full_max_dd'])}` | `{base.pct(selected_current['current_full_win_rate'])}` | `{int(selected_current['current_full_trades'])}` |",
                "",
                f"Current full + reused holdout 完整硬门槛：`{current_target_pass}`；K+2 与 8 bps 下 full/holdout 均保持正收益、胜率 >=50%、DD <20%：`{stress_shape_pass}`。",
                "",
                "## Promotion 边界",
                "",
                "- 参数冻结只使用 prefit 三场景，流程上没有用后段选参。",
                "- 但 reused holdout 此前已在本家族多轮研究中解锁，不能重新包装为 untouched OOS。",
                "- 在新增 forward trades、生产 runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据完成前，不提升为 candidate、paper-live、dry-run、handoff 或 live。",
                "",
            ]
        )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
