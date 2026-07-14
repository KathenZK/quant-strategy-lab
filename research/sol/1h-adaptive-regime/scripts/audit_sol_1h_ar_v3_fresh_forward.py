from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/sol/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
VCB_SEARCH = (
    ROOT
    / "research/sol/1h-volatility-compression-breakout/scripts"
    / "research_sol_1h_vcb_search.py"
)
STATE_MACHINE = FAMILY_DIR / "scripts/research_sol_1h_ar_v2_vwap_state_machine.py"
REDESIGN = FAMILY_DIR / "scripts/research_sol_1h_ar_v2_mechanism_redesign.py"
V2_SOURCE = ARTIFACT_DIR / "sol_1h_ar_high_win_search_2026-07-07.json"

DATE_TAG = "2026-07-13"
SUMMARY_JSON = ARTIFACT_DIR / f"sol_1h_ar_v3_fresh_forward_{DATE_TAG}.json"
REPORT_MD = DIAGNOSTIC_DIR / f"sol-1h-ar-v3-fresh-forward-{DATE_TAG}.md"

PREFIT_START = pd.Timestamp("2024-08-17T05:00:00Z")
PREFIT_END = pd.Timestamp("2026-04-03T05:00:00Z")
REUSED_END = pd.Timestamp("2026-07-03T05:00:00Z")
FRESH_END = pd.Timestamp("2026-07-13T07:00:00Z")


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    vcb = load_module(VCB_SEARCH, "sol_v3_forward_vcb")
    sm = load_module(STATE_MACHINE, "sol_v3_forward_sm")
    redesign = load_module(REDESIGN, "sol_v3_forward_redesign")
    engine = vcb.load_engine()
    frame, funding, quality = vcb.load_data()
    frame = engine.add_features(frame, funding)
    funding_times, funding_cumulative = engine.funding_prefix(funding)

    source = json.loads(V2_SOURCE.read_text(encoding="utf-8"))
    configs = [
        engine.StrategyConfig(**config)
        for config in source["best_configs"].values()
    ]
    donchian = next(cfg for cfg in configs if cfg.style == "donchian_break")
    vwap = next(cfg for cfg in configs if cfg.style == "vwap_revert")
    donchian = replace(
        donchian,
        name="DON_SM_L3_TP1_SL4_H72",
        tp_atr=1.0,
        sl_atr=4.0,
        max_hold_bars=72,
        fixed_leverage=3.0,
    )
    vwap = replace(
        vwap,
        name="VWAP_SM_W3_roc6_macd_L1_TP1.5_SL1.5_H12",
        tp_atr=1.5,
        sl_atr=1.5,
        max_hold_bars=12,
        fixed_leverage=1.0,
    )
    don_trades = engine.simulate_trades(
        frame,
        engine.build_signal(frame, donchian),
        donchian,
        funding_times,
        funding_cumulative,
    )
    vwap_signal, event_count, confirmed_count = sm.armed_vwap_signal(
        engine, frame, vwap, 3, "roc6_macd"
    )
    vwap_trades = engine.simulate_trades(
        frame,
        vwap_signal,
        vwap,
        funding_times,
        funding_cumulative,
    )
    don_score, _ = redesign.robust_prefit_score(engine, don_trades)
    vwap_score, _ = redesign.robust_prefit_score(engine, vwap_trades)
    trades = engine.merge_trade_sets(
        don_trades, vwap_trades, don_score, vwap_score
    )
    windows = {
        "prefit": engine.metrics(trades, PREFIT_START, PREFIT_END),
        "reused_holdout": engine.metrics(trades, PREFIT_END, REUSED_END),
        "fresh_forward": engine.metrics(trades, REUSED_END, FRESH_END),
        "current_full": engine.metrics(trades, PREFIT_START, FRESH_END),
    }
    slices = [
        {
            "window": name,
            **engine.metrics(trades, FRESH_END - delta, FRESH_END),
        }
        for name, delta in vcb.STANDARD_SLICES
    ]
    fresh_trades = [
        engine.trade_rows([trade])[0]
        for trade in trades
        if REUSED_END <= trade.entry_ts < FRESH_END
    ]
    payload = {
        "family": "SOL-1H-Adaptive-Regime",
        "version": "SOL-1H-Adaptive-Regime-V3",
        "status": "registered_not_promoted_not_live_ready",
        "audit": "fresh_forward_2026-07-03_to_2026-07-13",
        "data_quality": quality,
        "vwap_events_full_frame": event_count,
        "vwap_confirmed_full_frame": confirmed_count,
        "metrics": windows,
        "slices": slices,
        "fresh_trades": fresh_trades,
    }
    SUMMARY_JSON.write_text(
        json.dumps(vcb.json_safe(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    fresh = windows["fresh_forward"]
    lines = [
        "# SOL-1H-Adaptive-Regime-V3 Fresh Forward 审计 - 2026-07-13",
        "",
        "## 结论",
        "",
        "`2026-07-03T05:00:00Z` 至 `2026-07-13T07:00:00Z` 没有产生 V3 交易。该窗口不能验证、也不能否定 V3；版本状态保持 `registered / not promoted / not live-ready`。",
        "",
        f"- fresh forward：trades `{int(fresh['trades'])}`，return `{fresh['total_return']:.2%}`，DD `{fresh['max_dd']:.2%}`。",
        f"- 更新后 current full：annual `{windows['current_full']['annual_multiple']:.4f}x`，DD `{windows['current_full']['max_dd']:.2%}`，win `{windows['current_full']['win_rate']:.2%}`，trades `{int(windows['current_full']['trades'])}`。",
        "- 数据为 2026-07-13 刷新的最近两年闭合 SOLUSDT perpetual 1h 帧，质量 blocker `0`。",
        "",
        "## 标准近期分片",
        "",
        "| Window | Annual | Return | DD | Win | Trades | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in slices:
        lines.append(
            f"| `{row['window']}` | `{row['annual_multiple']:.4f}x` | "
            f"`{row['total_return']:.2%}` | `{row['max_dd']:.2%}` | "
            f"`{row['win_rate']:.2%}` | `{int(row['trades'])}` | "
            f"`{row['profit_factor']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 零交易不是通过 forward gate。",
            "- 至少等待足够新增交易后再判断 V3；不得因本窗口净值不变而 promotion。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/sol/1h-adaptive-regime/scripts/audit_sol_1h_ar_v3_fresh_forward.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"fresh": fresh, "report": str(REPORT_MD)}, indent=2))


if __name__ == "__main__":
    main()
