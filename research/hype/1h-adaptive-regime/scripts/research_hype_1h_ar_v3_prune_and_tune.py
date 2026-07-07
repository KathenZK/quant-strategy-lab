from __future__ import annotations

import itertools
import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_hype_1h_adaptive_regime_boundary as boundary  # noqa: E402
import research_hype_1h_adaptive_regime_search as base  # noqa: E402
import research_hype_1h_ar_v1_full_ablation as v1_ablation  # noqa: E402
import research_hype_1h_ar_v2_clean_tune as v2  # noqa: E402
import research_hype_1h_ar_v3_full_ablation as v3ab  # noqa: E402


DATE_TAG = "2026-07-07"
FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTE_DIR = FAMILY_DIR / "research-notes"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_ar_v3_prune_and_tune_{DATE_TAG}.json"
LEGS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v3_prune_and_tune_legs_{DATE_TAG}.csv"
COMBOS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v3_prune_and_tune_combos_{DATE_TAG}.csv"
REPORT_MD = NOTE_DIR / f"hype-1h-ar-v3-prune-and-tune-{DATE_TAG}.md"

TRAIN_START = v1_ablation.TRAIN_START
PREFIT_END = v1_ablation.PREFIT_END

MAX_DD_GATE = -0.20
MIN_WIN_GATE = 0.50
MIN_LEG_PREFIT_TRADES = 15
TOP_LEGS = 12
TOP_COMBOS_FOR_STRESS = 16
FINAL_FROZEN = 5

SCENARIOS = (
    ("base_k1", 0.0010, 0.0004, 1),
    ("delay_k2", 0.0010, 0.0004, 2),
    ("slip_8bps", 0.0010, 0.0008, 1),
)

DD_TOLERANCE = 1e-9


# 剪枝后的 DI 配置：删除 ema_htf、max_adx、roc_window、min_dir_roc_bps、
# max_dist_ema_bps、max_aligned_funding_bps 共 6 个 dormant 字段槽。
@dataclass(frozen=True, slots=True)
class DIPrunedConfig:
    min_adx: float = 12.0
    min_rvol: float = 2.0
    max_atr_bps: float = 250.0
    htf_mode: str = "h12"
    require_body_dir: bool = True
    tp_atr: float = 1.5
    sl_atr: float = 4.0
    max_hold_bars: int = 18
    fixed_leverage: float = 3.0


# 剪枝后的 Stoch 配置：删除 ema_htf、max_dist_ema_bps 和 sl_atr（硬止损在
# 3-6 ATR 全 dormant，固化为 4.0 作为安全兜底，不再作为可调槽）。
@dataclass(frozen=True, slots=True)
class StochPrunedConfig:
    indicator_window: int = 21
    threshold_low: float = 25.0
    threshold_high: float = 55.0
    min_adx: float = 12.0
    min_rvol: float = 1.0
    min_atr_bps: float = 200.0
    max_atr_bps: float = 400.0
    macd_fast: int = 8
    macd_slow: int = 21
    macd_signal: int = 5
    require_macd_turn: bool = True
    trail_activation_atr: float = 1.0
    trail_atr: float = 1.0
    max_hold_bars: int = 8
    cooldown_bars: int = 24
    fixed_leverage: float = 2.0


def di_pruned_to_clean(cfg: DIPrunedConfig) -> v2.DICleanConfig:
    return v2.DICleanConfig(
        ema_htf=89,
        min_adx=cfg.min_adx,
        max_adx=100.0,
        min_rvol=cfg.min_rvol,
        max_atr_bps=cfg.max_atr_bps,
        roc_window=24,
        min_dir_roc_bps=-10_000.0,
        max_dist_ema_bps=10_000.0,
        htf_mode=cfg.htf_mode,
        require_body_dir=cfg.require_body_dir,
        max_aligned_funding_bps=10_000.0,
        tp_atr=cfg.tp_atr,
        sl_atr=cfg.sl_atr,
        max_hold_bars=cfg.max_hold_bars,
        fixed_leverage=cfg.fixed_leverage,
    )


def stoch_pruned_to_clean(cfg: StochPrunedConfig) -> v2.StochCleanConfig:
    return v2.StochCleanConfig(
        indicator_window=cfg.indicator_window,
        threshold_low=cfg.threshold_low,
        threshold_high=cfg.threshold_high,
        ema_htf=55,
        min_adx=cfg.min_adx,
        min_rvol=cfg.min_rvol,
        min_atr_bps=cfg.min_atr_bps,
        max_atr_bps=cfg.max_atr_bps,
        max_dist_ema_bps=10_000.0,
        macd_fast=cfg.macd_fast,
        macd_slow=cfg.macd_slow,
        macd_signal=cfg.macd_signal,
        require_macd_turn=cfg.require_macd_turn,
        sl_atr=4.0,
        trail_activation_atr=cfg.trail_activation_atr,
        trail_atr=cfg.trail_atr,
        max_hold_bars=cfg.max_hold_bars,
        cooldown_bars=cfg.cooldown_bars,
        fixed_leverage=cfg.fixed_leverage,
    )


def di_grid() -> list[DIPrunedConfig]:
    combos = itertools.product(
        [10.0, 12.0, 14.0],
        [1.75, 2.0, 2.25],
        [225.0, 250.0],
        [True, False],
        [1.25, 1.5, 1.75],
        [3.5, 4.0, 4.5],
        [15, 18, 21],
    )
    return [
        DIPrunedConfig(
            min_adx=min_adx,
            min_rvol=min_rvol,
            max_atr_bps=max_atr,
            require_body_dir=body,
            tp_atr=tp,
            sl_atr=sl,
            max_hold_bars=hold,
        )
        for min_adx, min_rvol, max_atr, body, tp, sl, hold in combos
    ]


def stoch_grid() -> list[StochPrunedConfig]:
    combos = itertools.product(
        [14, 21],
        [20.0, 25.0],
        [50.0, 55.0],
        [0.0, 12.0],
        [1.0, 1.25],
        [175.0, 200.0],
        [400.0, 500.0],
        [21, 55],
        [True, False],
        [0.5, 1.0],
        [6, 8],
        [24, 36, 48],
    )
    return [
        StochPrunedConfig(
            indicator_window=window,
            threshold_low=low,
            threshold_high=high,
            min_adx=min_adx,
            min_rvol=min_rvol,
            min_atr_bps=min_atr,
            max_atr_bps=max_atr,
            macd_slow=macd_slow,
            require_macd_turn=macd_turn,
            trail_atr=trail,
            max_hold_bars=hold,
            cooldown_bars=cooldown,
        )
        for (
            window,
            low,
            high,
            min_adx,
            min_rvol,
            min_atr,
            max_atr,
            macd_slow,
            macd_turn,
            trail,
            hold,
            cooldown,
        ) in combos
    ]


class Simulator:
    def __init__(self, frame: pd.DataFrame, funding_times: Any, funding_cumulative: Any):
        self.frame = frame
        self.funding_times = funding_times
        self.funding_cumulative = funding_cumulative
        self.cache: dict[tuple[Any, ...], list[base.Trade]] = {}

    def leg(
        self,
        *,
        component: str,
        clean: v2.DICleanConfig | v2.StochCleanConfig,
        fee: float,
        slippage: float,
        delay: int,
    ) -> list[base.Trade]:
        key = (component, clean, fee, slippage, delay)
        if key in self.cache:
            return self.cache[key]
        cfg = (
            v2.di_to_base(clean, "PRUNE_DI")
            if component == "di_cross"
            else v2.stoch_to_base(clean, "PRUNE_STOCH")
        )
        cfg = replace(cfg, entry_delay_bars=delay)
        original = (base.FEE_PER_FILL, base.SLIPPAGE_PER_FILL)
        try:
            base.FEE_PER_FILL = fee
            base.SLIPPAGE_PER_FILL = slippage
            trades = boundary.component_trades(
                self.frame, self.funding_times, self.funding_cumulative, cfg
            )
        finally:
            base.FEE_PER_FILL, base.SLIPPAGE_PER_FILL = original
        self.cache[key] = trades
        return trades


def window_metrics(trades: list[base.Trade], full_end: pd.Timestamp) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, start, end in (
        ("prefit", TRAIN_START, PREFIT_END),
        ("reused_holdout", PREFIT_END, full_end),
        ("current_full", TRAIN_START, full_end),
    ):
        values = base.metrics(trades, start, end)
        output.update({f"{name}_{key}": value for key, value in values.items()})
    return output


def prefit_ok(metric: dict[str, Any]) -> bool:
    return (
        float(metric["max_dd"]) > MAX_DD_GATE
        and float(metric["win_rate"]) >= MIN_WIN_GATE
        and int(metric["trades"]) >= MIN_LEG_PREFIT_TRADES
    )


def pct(value: float) -> str:
    return base.pct(float(value))


def mult(value: float) -> str:
    return base.mult(float(value), digits=4)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)

    frame, funding, quality = base.load_data()
    frame = base.add_features(frame, funding)
    frame = v3ab.ensure_extra_macd_features(frame)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    sim = Simulator(frame, funding_times, funding_cumulative)

    # ---------- Stage A：剪枝等价性审计 ----------
    v3_di = v3ab.v3_di_config()
    v3_stoch = v3ab.v3_stoch_config()
    v3_di_trades = sim.leg(component="di_cross", clean=v3_di, fee=0.0010, slippage=0.0004, delay=1)
    v3_stoch_trades = sim.leg(
        component="stoch_reversal", clean=v3_stoch, fee=0.0010, slippage=0.0004, delay=1
    )
    v3_merged = base.merge_trade_sets(v3_di_trades, v3_stoch_trades, 1.0, 0.0)
    v3_sig = v1_ablation.signature(v3_merged)

    pruned_di_default = DIPrunedConfig()
    pruned_stoch_default = StochPrunedConfig()
    pruned_di_trades = sim.leg(
        component="di_cross",
        clean=di_pruned_to_clean(pruned_di_default),
        fee=0.0010,
        slippage=0.0004,
        delay=1,
    )
    pruned_stoch_trades = sim.leg(
        component="stoch_reversal",
        clean=stoch_pruned_to_clean(pruned_stoch_default),
        fee=0.0010,
        slippage=0.0004,
        delay=1,
    )
    pruned_merged = base.merge_trade_sets(pruned_di_trades, pruned_stoch_trades, 1.0, 0.0)
    prune_equal = {
        "di_path_equal": v1_ablation.signature(pruned_di_trades)
        == v1_ablation.signature(v3_di_trades),
        "stoch_path_equal": v1_ablation.signature(pruned_stoch_trades)
        == v1_ablation.signature(v3_stoch_trades),
        "merged_path_equal": v1_ablation.signature(pruned_merged) == v3_sig,
    }
    print(f"prune equivalence: {prune_equal}", flush=True)
    if not all(prune_equal.values()):
        raise RuntimeError(f"pruned config is not path-equal to V3: {prune_equal}")

    v3_windows = window_metrics(v3_merged, full_end)

    # ---------- Stage B：单腿 prefit 微调 ----------
    leg_rows: list[dict[str, Any]] = []
    leg_candidates: dict[str, list[tuple[str, Any, dict[str, Any]]]] = {
        "di_cross": [],
        "stoch_reversal": [],
    }
    for component, grid, to_clean in (
        ("di_cross", di_grid(), di_pruned_to_clean),
        ("stoch_reversal", stoch_grid(), stoch_pruned_to_clean),
    ):
        print(f"{component}: {len(grid)} grid configs", flush=True)
        for index, cfg in enumerate(grid):
            trades = sim.leg(
                component=component,
                clean=to_clean(cfg),
                fee=0.0010,
                slippage=0.0004,
                delay=1,
            )
            metric = base.metrics(trades, TRAIN_START, PREFIT_END)
            ok = prefit_ok(metric)
            leg_rows.append(
                {
                    "component": component,
                    "leg_id": f"{component}_{index:05d}",
                    "prefit_ok": ok,
                    "prefit_annual_multiple": metric["annual_multiple"],
                    "prefit_max_dd": metric["max_dd"],
                    "prefit_win_rate": metric["win_rate"],
                    "prefit_trades": metric["trades"],
                    **{f"cfg_{key}": value for key, value in asdict(cfg).items()},
                }
            )
            if ok:
                leg_candidates[component].append((f"{component}_{index:05d}", cfg, metric))
            if (index + 1) % 1000 == 0:
                print(f"  {component} {index + 1}/{len(grid)}", flush=True)

    legs_frame = pd.DataFrame(leg_rows)
    legs_frame.to_csv(LEGS_CSV, index=False)

    top_legs: dict[str, list[tuple[str, Any]]] = {}
    for component, candidates in leg_candidates.items():
        ranked = sorted(candidates, key=lambda item: item[2]["annual_multiple"], reverse=True)
        selected = [(leg_id, cfg) for leg_id, cfg, _metric in ranked[:TOP_LEGS]]
        default_cfg = pruned_di_default if component == "di_cross" else pruned_stoch_default
        if all(cfg != default_cfg for _leg_id, cfg in selected):
            selected.append((f"{component}_v3_default", default_cfg))
        top_legs[component] = selected
        print(f"{component}: {len(candidates)} prefit-ok, kept {len(selected)}", flush=True)

    # ---------- Stage C：组合 prefit 排名 ----------
    combo_rows: list[dict[str, Any]] = []
    for di_id, di_cfg in top_legs["di_cross"]:
        di_trades = sim.leg(
            component="di_cross",
            clean=di_pruned_to_clean(di_cfg),
            fee=0.0010,
            slippage=0.0004,
            delay=1,
        )
        for stoch_id, stoch_cfg in top_legs["stoch_reversal"]:
            stoch_trades = sim.leg(
                component="stoch_reversal",
                clean=stoch_pruned_to_clean(stoch_cfg),
                fee=0.0010,
                slippage=0.0004,
                delay=1,
            )
            merged = base.merge_trade_sets(di_trades, stoch_trades, 1.0, 0.0)
            prefit = base.metrics(merged, TRAIN_START, PREFIT_END)
            combo_rows.append(
                {
                    "combo_id": f"{di_id}__{stoch_id}",
                    "di_id": di_id,
                    "stoch_id": stoch_id,
                    "di_config": asdict(di_cfg),
                    "stoch_config": asdict(stoch_cfg),
                    "prefit_annual_multiple": prefit["annual_multiple"],
                    "prefit_max_dd": prefit["max_dd"],
                    "prefit_win_rate": prefit["win_rate"],
                    "prefit_trades": prefit["trades"],
                    "prefit_ok": prefit_ok(prefit),
                }
            )
    combo_rows.sort(key=lambda row: (row["prefit_ok"], row["prefit_annual_multiple"]), reverse=True)
    stress_set = combo_rows[:TOP_COMBOS_FOR_STRESS]
    baseline_combo_id = "di_cross_v3_default__stoch_reversal_v3_default"
    if all(row["combo_id"] != baseline_combo_id for row in stress_set):
        baseline_row = next(
            (row for row in combo_rows if row["combo_id"] == baseline_combo_id), None
        )
        if baseline_row is not None:
            stress_set.append(baseline_row)

    # ---------- Stage D：三场景 prefit 稳健排名，冻结后揭示 holdout ----------
    cfg_by_leg = {leg_id: cfg for legs in top_legs.values() for leg_id, cfg in legs}
    for row in stress_set:
        di_cfg = cfg_by_leg[row["di_id"]]
        stoch_cfg = cfg_by_leg[row["stoch_id"]]
        scenario_prefit_ok = True
        min_prefit_annual = float("inf")
        for scenario, fee, slippage, delay in SCENARIOS:
            di_trades = sim.leg(
                component="di_cross",
                clean=di_pruned_to_clean(di_cfg),
                fee=fee,
                slippage=slippage,
                delay=delay,
            )
            stoch_trades = sim.leg(
                component="stoch_reversal",
                clean=stoch_pruned_to_clean(stoch_cfg),
                fee=fee,
                slippage=slippage,
                delay=delay,
            )
            merged = base.merge_trade_sets(di_trades, stoch_trades, 1.0, 0.0)
            windows = window_metrics(merged, full_end)
            row.update({f"{scenario}_{key}": value for key, value in windows.items()})
            scenario_prefit = {
                "max_dd": windows["prefit_max_dd"],
                "win_rate": windows["prefit_win_rate"],
                "trades": windows["prefit_trades"],
            }
            if not prefit_ok(scenario_prefit):
                scenario_prefit_ok = False
            min_prefit_annual = min(min_prefit_annual, float(windows["prefit_annual_multiple"]))
        row["all_scenario_prefit_ok"] = scenario_prefit_ok
        row["min_scenario_prefit_annual"] = min_prefit_annual

    stress_set.sort(
        key=lambda row: (row["all_scenario_prefit_ok"], row["min_scenario_prefit_annual"]),
        reverse=True,
    )
    frozen = stress_set[:FINAL_FROZEN]
    for row in stress_set:
        row["frozen_reveal"] = any(row is item for item in frozen)
        row["beats_v3_base"] = (
            float(row.get("base_k1_current_full_annual_multiple", 0.0))
            > float(v3_windows["current_full_annual_multiple"])
            and float(row.get("base_k1_current_full_max_dd", -1.0))
            >= float(v3_windows["current_full_max_dd"]) - DD_TOLERANCE
            and float(row.get("base_k1_current_full_win_rate", 0.0))
            > float(v3_windows["current_full_win_rate"])
        )

    pd.DataFrame(base.json_safe(combo_rows)).to_csv(COMBOS_CSV, index=False)

    payload = {
        "family": "HYPE-1H-Adaptive-Regime",
        "base_version": "HYPE-1H-Adaptive-Regime-V3",
        "status": "prune_audit_and_prefit_tune_not_promoted",
        "date": DATE_TAG,
        "data_quality": quality,
        "full_end": full_end,
        "prune": {
            "di_removed_fields": [
                "ema_htf",
                "max_adx",
                "roc_window",
                "min_dir_roc_bps",
                "max_dist_ema_bps",
                "max_aligned_funding_bps",
            ],
            "stoch_removed_fields": ["ema_htf", "max_dist_ema_bps", "sl_atr"],
            "field_counts": {"before": 34, "after": 25},
            "path_equal": prune_equal,
        },
        "v3_baseline_windows": v3_windows,
        "grid_sizes": {
            "di_cross": len(di_grid()),
            "stoch_reversal": len(stoch_grid()),
        },
        "leg_prefit_ok_counts": {
            component: int(len(items)) for component, items in leg_candidates.items()
        },
        "combos_ranked": len(combo_rows),
        "stress_evaluated": len(stress_set),
        "frozen_reveal": base.json_safe(frozen),
    }
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ---------- 报告 ----------
    lines = [
        f"# HYPE-1H-Adaptive-Regime-V3 参数剪枝与预拟合微调 - {DATE_TAG}",
        "",
        "## 结论",
        "",
        (
            "V3 的 `34` 个字段槽中有 `9` 个在当前数据上 dormant：DI 腿 `ema_htf`、`max_adx`、"
            "`roc_window`、`min_dir_roc_bps`、`max_dist_ema_bps`、`max_aligned_funding_bps`；"
            "Stoch 腿 `ema_htf`、`max_dist_ema_bps`、`sl_atr`。"
            "全部移除后逐笔交易路径与 V3 exact equal（DI、Stoch、merged 三层签名一致），"
            "剪枝后剩 `25` 个字段槽（DI `9` + Stoch `16`）。"
        ),
        "",
        (
            f"微调只用 prefit 选参：DI 网格 `{len(di_grid())}`、Stoch 网格 `{len(stoch_grid())}`，"
            f"单腿 prefit 达标后取 top `{TOP_LEGS}` 组合成 `{len(combo_rows)}` 个 ensemble，"
            f"前 `{len(stress_set)}` 名再跑 K+1/K+2/8bps 三场景 prefit 稳健排名，"
            f"冻结前 `{len(frozen)}` 名后才揭示 reused holdout 与 current full。"
        ),
        "",
        "## V3 基线（对照）",
        "",
        "| Window | Annual | DD | Win | Trades |",
        "| --- | ---: | ---: | ---: | ---: |",
        (
            f"| Prefit | `{mult(v3_windows['prefit_annual_multiple'])}` | "
            f"`{pct(v3_windows['prefit_max_dd'])}` | `{pct(v3_windows['prefit_win_rate'])}` | "
            f"`{int(v3_windows['prefit_trades'])}` |"
        ),
        (
            f"| Reused holdout | `{mult(v3_windows['reused_holdout_annual_multiple'])}` | "
            f"`{pct(v3_windows['reused_holdout_max_dd'])}` | "
            f"`{pct(v3_windows['reused_holdout_win_rate'])}` | "
            f"`{int(v3_windows['reused_holdout_trades'])}` |"
        ),
        (
            f"| Current full | `{mult(v3_windows['current_full_annual_multiple'])}` | "
            f"`{pct(v3_windows['current_full_max_dd'])}` | "
            f"`{pct(v3_windows['current_full_win_rate'])}` | "
            f"`{int(v3_windows['current_full_trades'])}` |"
        ),
        "",
        "## 冻结揭示组合",
        "",
        (
            "| Combo | Robust prefit min annual | Base full annual | Base full DD | Base full win | "
            "Holdout annual | Holdout DD | K+2 full/DD | 8bps full/DD | 超越 V3 |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in frozen:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['combo_id']}`",
                    mult(row["min_scenario_prefit_annual"]),
                    mult(row["base_k1_current_full_annual_multiple"]),
                    pct(row["base_k1_current_full_max_dd"]),
                    pct(row["base_k1_current_full_win_rate"]),
                    mult(row["base_k1_reused_holdout_annual_multiple"]),
                    pct(row["base_k1_reused_holdout_max_dd"]),
                    (
                        f"{mult(row['delay_k2_current_full_annual_multiple'])} / "
                        f"{pct(row['delay_k2_current_full_max_dd'])}"
                    ),
                    (
                        f"{mult(row['slip_8bps_current_full_annual_multiple'])} / "
                        f"{pct(row['slip_8bps_current_full_max_dd'])}"
                    ),
                    "yes" if row["beats_v3_base"] else "no",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 剪枝证据",
            "",
            f"- DI/Stoch/merged 三层签名等价：`{prune_equal}`。",
            "- DI 移除：`ema_htf`、`max_adx`、`roc_window`、`min_dir_roc_bps`、`max_dist_ema_bps`、`max_aligned_funding_bps`。",
            "- Stoch 移除：`ema_htf`、`max_dist_ema_bps`；`sl_atr` 固化为 `4.0` 安全兜底（3-6 ATR 变体全 path-equal，从未触发）。",
            "",
            "## 方法与防过拟合边界",
            "",
            "- 选参只使用 prefit（训练段），并要求 K+1、K+2、8bps 三场景 prefit 同时 DD 不破 `20%`、胜率 `>=50%`。",
            "- Reused holdout 只在冻结排名后揭示，仅作诊断，不参与选参；它不是 untouched OOS。",
            "- 本轮不改变 promotion 状态；任何登记需另行完成 live-executable 审计。",
            "",
            "## 机器证据",
            "",
            f"- JSON：`artifacts/{SUMMARY_JSON.name}`",
            f"- 单腿 CSV：`artifacts/{LEGS_CSV.name}`",
            f"- 组合 CSV：`artifacts/{COMBOS_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v3_prune_and_tune.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            base.json_safe(
                {
                    "prune_equal": prune_equal,
                    "leg_ok": payload["leg_prefit_ok_counts"],
                    "frozen": [
                        {
                            "combo_id": row["combo_id"],
                            "min_prefit_annual": row["min_scenario_prefit_annual"],
                            "base_full": row["base_k1_current_full_annual_multiple"],
                            "base_full_dd": row["base_k1_current_full_max_dd"],
                            "base_full_win": row["base_k1_current_full_win_rate"],
                            "holdout": row["base_k1_reused_holdout_annual_multiple"],
                            "k2_full": row["delay_k2_current_full_annual_multiple"],
                            "k2_dd": row["delay_k2_current_full_max_dd"],
                            "slip_full": row["slip_8bps_current_full_annual_multiple"],
                            "slip_dd": row["slip_8bps_current_full_max_dd"],
                            "beats_v3": row["beats_v3_base"],
                            "di_config": row["di_config"],
                            "stoch_config": row["stoch_config"],
                        }
                        for row in frozen
                    ],
                }
            ),
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
