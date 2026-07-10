from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/sol/1h-adaptive-regime"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
BASE_SEARCH_PATH = SCRIPT_DIR / "research_sol_1h_adaptive_regime_search.py"
REDESIGN_PATH = SCRIPT_DIR / "research_sol_1h_ar_v2_mechanism_redesign.py"
V2_JSON = ARTIFACT_DIR / "sol_1h_ar_high_win_search_2026-07-07.json"

DATE_TAG = "2026-07-10"
SUMMARY_JSON = ARTIFACT_DIR / f"sol_1h_ar_v2_leg_governor_{DATE_TAG}.json"
CANDIDATES_CSV = ARTIFACT_DIR / f"sol_1h_ar_v2_leg_governor_candidates_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"sol_1h_ar_v2_leg_governor_selected_trades_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"sol-1h-ar-v2-leg-governor-{DATE_TAG}.md"


@dataclass(slots=True)
class LegCandidate:
    name: str
    config: Any
    cooldown_bars: int
    cooldown_trigger: str
    trades: list[Any]
    score: float
    metrics: dict[str, dict[str, float]]


@dataclass(slots=True)
class EnsembleCandidate:
    name: str
    donchian: LegCandidate
    vwap: LegCandidate
    trades: list[Any]
    score: float
    metrics: dict[str, dict[str, float]]


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def apply_loss_cooldown(
    trades: list[Any], cooldown_bars: int, trigger: str
) -> list[Any]:
    if cooldown_bars <= 0:
        return trades
    selected: list[Any] = []
    disabled_until = -1
    for trade in sorted(trades, key=lambda item: (item.entry_i, item.exit_i)):
        if trade.entry_i <= disabled_until:
            continue
        selected.append(trade)
        should_disable = (
            trade.equity_ret <= 0.0
            if trigger == "any_loss"
            else "stop" in trade.exit_reason
        )
        if should_disable:
            disabled_until = trade.exit_i + cooldown_bars
    return selected


def make_donchian(
    engine: Any,
    redesign: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    baseline: Any,
) -> list[LegCandidate]:
    results: list[LegCandidate] = []
    for leverage in (2.0, 2.5, 3.0):
        for tp_atr in (0.75, 1.0, 1.5):
            for sl_atr in (3.0, 4.0):
                for hold in (72, 120):
                    cfg = replace(
                        baseline,
                        name=(
                            f"DON_GOV_L{leverage:g}_TP{tp_atr:g}_"
                            f"SL{sl_atr:g}_H{hold}"
                        ),
                        fixed_leverage=leverage,
                        tp_atr=tp_atr,
                        sl_atr=sl_atr,
                        max_hold_bars=hold,
                    )
                    trades = engine.simulate_trades(
                        frame,
                        engine.build_signal(frame, cfg),
                        cfg,
                        funding_times,
                        funding_cumulative,
                    )
                    score, metrics = redesign.robust_prefit_score(engine, trades)
                    if score > -1e8:
                        results.append(
                            LegCandidate(
                                cfg.name,
                                cfg,
                                0,
                                "none",
                                trades,
                                score,
                                metrics,
                            )
                        )
    return sorted(results, key=lambda item: item.score, reverse=True)


def make_vwap(
    engine: Any,
    redesign: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    baseline: Any,
) -> list[LegCandidate]:
    results: list[LegCandidate] = []
    for leverage in (1.0, 1.5):
        for tp_atr in (0.75, 1.0, 1.5):
            for sl_atr in (1.5, 2.0, 3.0):
                for hold in (12, 18):
                    cfg = replace(
                        baseline,
                        name=(
                            f"VWAP_GOV_L{leverage:g}_TP{tp_atr:g}_"
                            f"SL{sl_atr:g}_H{hold}"
                        ),
                        fixed_leverage=leverage,
                        tp_atr=tp_atr,
                        sl_atr=sl_atr,
                        max_hold_bars=hold,
                    )
                    raw_trades = engine.simulate_trades(
                        frame,
                        engine.build_signal(frame, cfg),
                        cfg,
                        funding_times,
                        funding_cumulative,
                    )
                    for cooldown in (0, 24, 72, 168, 336, 720):
                        triggers = ("none",) if cooldown == 0 else ("stop", "any_loss")
                        for trigger in triggers:
                            trades = (
                                raw_trades
                                if cooldown == 0
                                else apply_loss_cooldown(
                                    raw_trades, cooldown, trigger
                                )
                            )
                            score, metrics = redesign.robust_prefit_score(
                                engine, trades
                            )
                            if score <= -1e8:
                                continue
                            name = (
                                f"{cfg.name}_CD{cooldown}_"
                                f"{trigger}"
                            )
                            results.append(
                                LegCandidate(
                                    name,
                                    cfg,
                                    cooldown,
                                    trigger,
                                    trades,
                                    score,
                                    metrics,
                                )
                            )
    return sorted(results, key=lambda item: item.score, reverse=True)


def build_ensembles(
    engine: Any,
    redesign: Any,
    donchian: list[LegCandidate],
    vwap: list[LegCandidate],
) -> list[EnsembleCandidate]:
    results: list[EnsembleCandidate] = []
    for left in donchian:
        for right in vwap:
            trades = engine.merge_trade_sets(
                left.trades, right.trades, left.score, right.score
            )
            score, metrics = redesign.robust_prefit_score(engine, trades)
            if score <= -1e8:
                continue
            results.append(
                EnsembleCandidate(
                    f"ENS__{left.name}__{right.name}",
                    left,
                    right,
                    trades,
                    score,
                    metrics,
                )
            )
    return sorted(results, key=lambda item: item.score, reverse=True)


def candidate_row(redesign: Any, item: EnsembleCandidate) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": item.name,
        "prefit_score": item.score,
        "donchian_name": item.donchian.name,
        "vwap_name": item.vwap.name,
        "vwap_cooldown_bars": item.vwap.cooldown_bars,
        "vwap_cooldown_trigger": item.vwap.cooldown_trigger,
    }
    for window, metric in item.metrics.items():
        row.update({f"{window}_{key}": value for key, value in metric.items()})
    for window, start, end in (
        ("prefit_tail", redesign.TRAIN_START, redesign.PREFIT_END),
        ("holdout_tail", redesign.PREFIT_END, redesign.FULL_END),
        ("full_tail", redesign.TRAIN_START, redesign.FULL_END),
    ):
        row.update(
            {
                f"{window}_{key}": value
                for key, value in redesign.tail_metrics(
                    item.trades, start, end
                ).items()
            }
        )
    return row


def pct(value: float) -> str:
    return f"{value:.2%}"


def mult(value: float) -> str:
    return f"{value:.4f}x"


def main() -> None:
    base = load_module(BASE_SEARCH_PATH, "sol_v2_governor_base")
    redesign = load_module(REDESIGN_PATH, "sol_v2_governor_redesign")
    engine = base.load_engine()
    frame, funding, quality = base.load_data()
    frame = engine.add_features(frame, funding)
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    source = json.loads(V2_JSON.read_text(encoding="utf-8"))
    configs = [
        engine.StrategyConfig(**config)
        for config in source["best_configs"].values()
    ]
    don_base = next(cfg for cfg in configs if cfg.style == "donchian_break")
    vwap_base = next(cfg for cfg in configs if cfg.style == "vwap_revert")
    donchian = make_donchian(
        engine,
        redesign,
        frame,
        funding_times,
        funding_cumulative,
        don_base,
    )
    vwap = make_vwap(
        engine,
        redesign,
        frame,
        funding_times,
        funding_cumulative,
        vwap_base,
    )
    candidates = build_ensembles(engine, redesign, donchian, vwap)
    if not candidates:
        raise RuntimeError("No governor candidates survived prefit gates")
    selected = candidates[0]
    frozen = candidates[:100]

    pd.DataFrame(
        [candidate_row(redesign, item) for item in frozen]
    ).to_csv(CANDIDATES_CSV, index=False)
    pd.DataFrame(engine.trade_rows(selected.trades)).to_csv(TRADES_CSV, index=False)
    standard_slices = [
        {
            "window": name,
            **engine.metrics(
                selected.trades, redesign.FULL_END - delta, redesign.FULL_END
            ),
        }
        for name, delta in redesign.STANDARD_SLICES
    ]
    payload = {
        "family": "SOL-1H-Adaptive-Regime",
        "baseline_version": "SOL-1H-Adaptive-Regime-V2",
        "observation_id": "SOL-1H-AR-V2-LEG-GOVERNOR-2026-07-10",
        "status": "diagnostic_only_not_registered_not_promoted_not_live_ready",
        "selection_policy": {
            "uses": "train_validation_prefit_only",
            "reused_holdout": "audit_after_identity_freeze_not_used_for_selection",
            "fresh_oos": False,
            "governor": "disable_vwap_leg_for_N_bars_after_completed_loss",
        },
        "data_quality": quality,
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "counts": {
            "donchian_candidates": len(donchian),
            "vwap_governor_candidates": len(vwap),
            "ensemble_candidates": len(candidates),
            "frozen_holdout_audit_set": len(frozen),
        },
        "selected": {
            **candidate_row(redesign, selected),
            "donchian_config": asdict(selected.donchian.config),
            "vwap_config": asdict(selected.vwap.config),
        },
        "standard_slices": standard_slices,
        "top_20": [
            candidate_row(redesign, item) for item in candidates[:20]
        ],
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    prefit = selected.metrics["prefit"]
    holdout = selected.metrics["reused_holdout"]
    full = selected.metrics["current_full"]
    lines = [
        "# SOL-1H-Adaptive-Regime-V2 腿级风险治理诊断 - 2026-07-10",
        "",
        "## 结论",
        "",
        "本轮测试把 VWAP 作为可暂停的 satellite leg：每笔交易完成后，若发生 stop 或任意亏损，则按预设 bars 暂停新 VWAP 入场；Donchian core 不受影响。选择只使用 train/validation/prefit。",
        "",
        f"- Donchian candidates：`{len(donchian)}`；VWAP governor candidates：`{len(vwap)}`；ensemble candidates：`{len(candidates)}`。",
        f"- prefit-only 选中：`{selected.name}`。",
        f"- 选中 governor：trigger `{selected.vwap.cooldown_trigger}`，cooldown `{selected.vwap.cooldown_bars}` bars。",
        "",
        "## 选中观察",
        "",
        f"- prefit：annual `{mult(prefit['annual_multiple'])}`，DD `{pct(prefit['max_dd'])}`，win `{pct(prefit['win_rate'])}`，trades `{int(prefit['trades'])}`。",
        f"- reused holdout：annual `{mult(holdout['annual_multiple'])}`，return `{pct(holdout['total_return'])}`，DD `{pct(holdout['max_dd'])}`，win `{pct(holdout['win_rate'])}`，trades `{int(holdout['trades'])}`。",
        f"- full：annual `{mult(full['annual_multiple'])}`，DD `{pct(full['max_dd'])}`，win `{pct(full['win_rate'])}`，trades `{int(full['trades'])}`。",
        "",
        "## 标准近期分片（锚定数据集末端，仅审计）",
        "",
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in standard_slices:
        lines.append(
            f"| `{row['window']}` | `{mult(row['annual_multiple'])}` | "
            f"`{pct(row['total_return'])}` | `{pct(row['max_dd'])}` | "
            f"`{pct(row['win_rate'])}` | `{int(row['trades'])}` | "
            f"`{row['profit_factor']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## 研究边界",
            "",
            "- governor 只使用已完成交易结果，在线可表达；没有使用未来信息。",
            "- reused holdout 已揭盲，不能用于选择 cooldown 或登记新版本。",
            "- 若 prefit-only 选中的 governor 没有改善 reused holdout，只能说明该治理机制不足；不得倒选 holdout 最优 cooldown。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{CANDIDATES_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_v2_leg_governor.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload["counts"], indent=2))
    print(
        f"selected={selected.name} "
        f"prefit_ann={prefit['annual_multiple']:.4f} "
        f"holdout_ann={holdout['annual_multiple']:.4f} "
        f"holdout_dd={holdout['max_dd']:.4f} "
        f"full_ann={full['annual_multiple']:.4f}",
        flush=True,
    )
    print(f"wrote {REPORT_MD}", flush=True)


if __name__ == "__main__":
    main()
