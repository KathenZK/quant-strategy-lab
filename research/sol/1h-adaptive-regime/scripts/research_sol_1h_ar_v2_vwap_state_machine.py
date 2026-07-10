from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
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
SUMMARY_JSON = ARTIFACT_DIR / f"sol_1h_ar_v2_vwap_state_machine_{DATE_TAG}.json"
CANDIDATES_CSV = (
    ARTIFACT_DIR / f"sol_1h_ar_v2_vwap_state_machine_candidates_{DATE_TAG}.csv"
)
TRADES_CSV = (
    ARTIFACT_DIR / f"sol_1h_ar_v2_vwap_state_machine_selected_trades_{DATE_TAG}.csv"
)
REPORT_MD = DIAGNOSTIC_DIR / f"sol-1h-ar-v2-vwap-state-machine-{DATE_TAG}.md"


@dataclass(slots=True)
class LegCandidate:
    name: str
    mechanism: str
    config: Any
    signal: np.ndarray
    event_count: int
    confirmed_count: int
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


def confirmation_mask(
    frame: pd.DataFrame, side: int, mode: str
) -> np.ndarray:
    roc = side * frame["roc6_bps"].to_numpy("float64") >= 0.0
    macd = (
        side * frame["macd_hist_8_21_5"].to_numpy("float64") >= 0.0
    )
    di = (
        side
        * (
            frame["pdi14"].to_numpy("float64")
            - frame["mdi14"].to_numpy("float64")
        )
        >= 0.0
    )
    if mode == "roc6_macd":
        return roc & macd
    if mode == "roc6_di":
        return roc & di
    if mode == "fast_consensus":
        return (roc.astype(int) + macd.astype(int) + di.astype(int)) >= 2
    raise ValueError(f"Unknown confirmation mode: {mode}")


def armed_vwap_signal(
    engine: Any,
    frame: pd.DataFrame,
    cfg: Any,
    confirm_window: int,
    confirm_mode: str,
) -> tuple[np.ndarray, int, int]:
    deviation = frame[f"vwap_dev_atr{cfg.indicator_window}"].to_numpy(
        "float64"
    )
    events = np.zeros(len(frame), dtype=np.int8)
    if cfg.side_mode in {"long", "both"}:
        events[engine.crossed_up(deviation, -cfg.band_k)] = 1
    if cfg.side_mode in {"short", "both"}:
        events[engine.crossed_down(deviation, cfg.band_k)] = -1
    # The arm event must satisfy the original V2 filters.
    events = engine.apply_filters(frame, events, cfg)
    event_indices = np.flatnonzero(events)
    confirmed = np.zeros(len(frame), dtype=np.int8)
    confirm_long = confirmation_mask(frame, 1, confirm_mode)
    confirm_short = confirmation_mask(frame, -1, confirm_mode)
    active_side = 0
    expires_at = -1
    event_cursor = 0

    for bar_i in range(len(frame)):
        while (
            event_cursor < len(event_indices)
            and event_indices[event_cursor] == bar_i
        ):
            active_side = int(events[bar_i])
            expires_at = bar_i + confirm_window
            event_cursor += 1
        if active_side == 0 or bar_i > expires_at:
            if bar_i > expires_at:
                active_side = 0
            continue
        # Confirmation starts one complete bar after arm.
        arm_i = expires_at - confirm_window
        if bar_i <= arm_i:
            continue
        confirm = confirm_long if active_side > 0 else confirm_short
        if bool(confirm[bar_i]):
            candidate = np.zeros(len(frame), dtype=np.int8)
            candidate[bar_i] = active_side
            # Recheck slow regime, body, funding and volatility at confirm.
            candidate = engine.apply_filters(frame, candidate, cfg)
            if candidate[bar_i] != 0:
                confirmed[bar_i] = active_side
                active_side = 0
                expires_at = -1
    return confirmed, int(len(event_indices)), int(np.count_nonzero(confirmed))


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
                            f"DON_SM_L{leverage:g}_TP{tp_atr:g}_"
                            f"SL{sl_atr:g}_H{hold}"
                        ),
                        fixed_leverage=leverage,
                        tp_atr=tp_atr,
                        sl_atr=sl_atr,
                        max_hold_bars=hold,
                    )
                    signal = engine.build_signal(frame, cfg)
                    trades = engine.simulate_trades(
                        frame,
                        signal,
                        cfg,
                        funding_times,
                        funding_cumulative,
                    )
                    score, metrics = redesign.robust_prefit_score(engine, trades)
                    if score > -1e8:
                        results.append(
                            LegCandidate(
                                cfg.name,
                                "donchian_core",
                                cfg,
                                signal,
                                int(np.count_nonzero(signal)),
                                int(np.count_nonzero(signal)),
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
    for window in (3, 6, 12):
        for mode in ("roc6_macd", "roc6_di", "fast_consensus"):
            for leverage in (1.0, 1.5):
                for tp_atr in (0.75, 1.0, 1.5):
                    for sl_atr in (1.5, 2.0):
                        for hold in (12, 18):
                            cfg = replace(
                                baseline,
                                name=(
                                    f"VWAP_SM_W{window}_{mode}_"
                                    f"L{leverage:g}_TP{tp_atr:g}_"
                                    f"SL{sl_atr:g}_H{hold}"
                                ),
                                fixed_leverage=leverage,
                                tp_atr=tp_atr,
                                sl_atr=sl_atr,
                                max_hold_bars=hold,
                            )
                            signal, event_count, confirmed_count = (
                                armed_vwap_signal(
                                    engine, frame, cfg, window, mode
                                )
                            )
                            trades = engine.simulate_trades(
                                frame,
                                signal,
                                cfg,
                                funding_times,
                                funding_cumulative,
                            )
                            score, metrics = redesign.robust_prefit_score(
                                engine, trades
                            )
                            if score <= -1e8:
                                continue
                            results.append(
                                LegCandidate(
                                    cfg.name,
                                    f"vwap_arm_confirm_expire:{mode}:W{window}",
                                    cfg,
                                    signal,
                                    event_count,
                                    confirmed_count,
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
        "vwap_mechanism": item.vwap.mechanism,
        "vwap_event_count": item.vwap.event_count,
        "vwap_confirmed_count": item.vwap.confirmed_count,
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
    base = load_module(BASE_SEARCH_PATH, "sol_v2_sm_base")
    redesign = load_module(REDESIGN_PATH, "sol_v2_sm_redesign")
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
        raise RuntimeError("No state-machine candidates survived prefit gates")
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
        "observation_id": "SOL-1H-AR-V2-VWAP-STATE-MACHINE-2026-07-10",
        "status": "diagnostic_only_not_registered_not_promoted_not_live_ready",
        "selection_policy": {
            "uses": "train_validation_prefit_only",
            "reused_holdout": "audit_after_identity_freeze_not_used_for_selection",
            "fresh_oos": False,
            "entry_timing": "arm_event_then_closed_bar_confirm_then_next_open",
        },
        "data_quality": quality,
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "counts": {
            "donchian_candidates": len(donchian),
            "vwap_state_machine_candidates": len(vwap),
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
        "# SOL-1H-Adaptive-Regime-V2 VWAP Arm-Confirm-Expire 状态机诊断 - 2026-07-10",
        "",
        "## 结论",
        "",
        "本轮把 VWAP 从偏离回穿即入场改成 `arm → confirm → expire`：arm 事件满足原 V2 慢周期过滤，随后等待快速动量重新与交易方向一致；confirm 使用闭合 K，下一根 open 入场。",
        "",
        f"- Donchian candidates：`{len(donchian)}`；VWAP state-machine candidates：`{len(vwap)}`；ensemble candidates：`{len(candidates)}`。",
        f"- prefit-only 选中：`{selected.name}`。",
        f"- VWAP mechanism：`{selected.vwap.mechanism}`；events `{selected.vwap.event_count}`，confirmed `{selected.vwap.confirmed_count}`。",
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
            "- state machine 在线可表达：arm/confirm 都只使用已闭合 K，订单在下一根 open 执行。",
            "- reused holdout 已揭盲，不用于选择 confirm window 或 mode。",
            "- 即使 reused holdout 改善，也只能冻结为 observation 并等待 fresh forward。",
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
            "uv run python research/sol/1h-adaptive-regime/scripts/research_sol_1h_ar_v2_vwap_state_machine.py",
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
