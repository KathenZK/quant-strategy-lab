"""Render the complete 365d training + 81d validation P5/V7.1 comparison."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-machine-learning-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
P4_SCRIPT = FAMILY_DIR / "scripts/run_hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual.py"
SLICE_SCRIPT = FAMILY_DIR / "scripts/audit_hype_1d_ma7_mlt_p4_recent_slices.py"
STEM = "hype_1d_ma7_mlt_p5_opportunity_repair_lifecycle_2026-08-28"

DEVELOPMENT_SUMMARY = ARTIFACT_DIR / f"{STEM}_development_summary.json"
VALIDATION_SUMMARY = ARTIFACT_DIR / f"{STEM}_validation_summary.json"
DEVELOPMENT_MANIFEST = ARTIFACT_DIR / f"{STEM}_development_manifest.json"
TRAIN_P5_TRADES = ARTIFACT_DIR / f"{STEM}_training_trades.csv"
TRAIN_V7_TRADES = ARTIFACT_DIR / f"{STEM}_training_v7_1_trades.csv"
VALIDATION_P5_TRADES = ARTIFACT_DIR / f"{STEM}_validation_trades.csv"
VALIDATION_V7_TRADES = ARTIFACT_DIR / f"{STEM}_validation_v7_1_trades.csv"
TRAIN_DECISIONS = ARTIFACT_DIR / f"{STEM}_training_decisions.csv"
VALIDATION_DECISIONS = ARTIFACT_DIR / f"{STEM}_validation_decisions.csv"
TRAIN_EPISODES = ARTIFACT_DIR / f"{STEM}_training_episode_capture.csv"
VALIDATION_EPISODES = ARTIFACT_DIR / f"{STEM}_validation_episode_capture.csv"

OUTPUT_PATH = ARTIFACT_DIR / f"{STEM}_v7_1_comparison_trade_paths.html"
MANIFEST_PATH = ARTIFACT_DIR / f"{STEM}_v7_1_comparison_trade_paths_manifest.json"

STRATEGIES = {
    "P5": {"label": "P5 lifecycle", "code": "P5", "color": "#e7aa61", "dash": [9, 5]},
    "V7_1": {"label": "exact V7.1", "code": "V7", "color": "#6cb7c8", "dash": []},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sidecar(path: Path) -> None:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not sidecar.exists():
        raise RuntimeError(f"missing sidecar: {sidecar}")
    if sidecar.read_text(encoding="utf-8").split()[0] != sha256(path):
        raise RuntimeError(f"source artifact hash mismatch: {path}")


def timestamp_ms(value: Any) -> int:
    return int(pd.Timestamp(value).timestamp() * 1_000)


def finite_or_none(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def load_trades(path: Path) -> list[dict[str, Any]]:
    return pd.read_csv(path).to_dict("records")


def daily_equity(
    slice_audit: Any,
    p4: Any,
    v6: Any,
    context: Any,
    trades: list[dict[str, Any]],
    start_index: int,
) -> list[dict[str, Any]]:
    observations, _, terminal_equity = slice_audit.equity_observations(
        p4, v6, context, trades
    )
    last_at_timestamp: dict[pd.Timestamp, float] = {}
    for ts, value in observations:
        last_at_timestamp[pd.Timestamp(ts)] = float(value)
    timestamps = [pd.Timestamp(ts) for ts in context.book.ts[start_index:]]
    timestamps.append(pd.Timestamp(context.book.terminal_ts))
    rows: list[dict[str, Any]] = []
    for ts in timestamps:
        if ts not in last_at_timestamp:
            raise RuntimeError(f"missing daily equity timestamp: {ts}")
        rows.append({"t": timestamp_ms(ts), "v": last_at_timestamp[ts]})
    if not math.isclose(rows[-1]["v"], terminal_equity, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError("daily equity terminal parity failed")
    return rows


def episode_rows(path: Path, segment: str, segment_label: str) -> list[dict[str, Any]]:
    frame = pd.read_csv(path)
    frame = frame.loc[frame["strategy"].isin(["P5", "V7.1"])].copy()
    rows: list[dict[str, Any]] = []
    for episode_id, group in frame.groupby("episode_id", sort=False):
        lookup = group.set_index("strategy")
        if "P5" not in lookup.index or "V7.1" not in lookup.index:
            raise RuntimeError(f"episode strategy pair missing: {episode_id}")
        p5 = lookup.loc["P5"]
        v7 = lookup.loc["V7.1"]
        p5_capture = float(p5["capture_ratio"])
        v7_capture = float(v7["capture_ratio"])
        if p5_capture > 0.0 and v7_capture == 0.0:
            classification = "P5_NEW_CAPTURE"
        elif p5_capture > v7_capture:
            classification = "P5_MORE"
        elif p5_capture < v7_capture:
            classification = "V7_MORE"
        else:
            classification = "SAME"
        rows.append(
            {
                "id": str(episode_id),
                "segment": segment,
                "segmentLabel": segment_label,
                "direction": str(p5["direction"]),
                "side": int(p5["side"]),
                "startT": timestamp_ms(p5["start_ts"]),
                "endT": timestamp_ms(p5["end_ts"]) + 86_400_000,
                "start": str(p5["start_ts"]),
                "end": str(p5["end_ts"]),
                "durationDays": int(p5["duration_days"]),
                "p5Days": int(p5["covered_days"]),
                "v7Days": int(v7["covered_days"]),
                "p5Capture": p5_capture,
                "v7Capture": v7_capture,
                "classification": classification,
            }
        )
    return rows


def trade_rows(
    strategy: str,
    segment: str,
    segment_label: str,
    trades: list[dict[str, Any]],
    returns: list[float],
) -> list[dict[str, Any]]:
    if len(trades) != len(returns):
        raise RuntimeError(f"{strategy} trade return parity failed")
    rows: list[dict[str, Any]] = []
    for order, (trade, net_return) in enumerate(zip(trades, returns, strict=True), start=1):
        rows.append(
            {
                "id": f"{STRATEGIES[strategy]['code']}-{segment[:2].upper()}-{order:02d}",
                "strategy": strategy,
                "strategyLabel": STRATEGIES[strategy]["label"],
                "segment": segment,
                "segmentLabel": segment_label,
                "side": str(trade["side"]),
                "entryT": timestamp_ms(trade["entry_ts"]),
                "exitT": timestamp_ms(trade["exit_ts"]),
                "entry": float(trade["entry_price"]),
                "exit": float(trade["exit_price"]),
                "barsHeld": int(trade.get("bars_held", 0)),
                "netReturnPct": float(net_return) * 100.0,
                "exitReason": str(trade["exit_reason"]),
                "entryProbability": finite_or_none(trade.get("entry_probability", math.nan)),
                "directReversal": bool(trade.get("direct_reversal", False)),
            }
        )
    return rows


def build_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    sources = (
        DEVELOPMENT_SUMMARY,
        VALIDATION_SUMMARY,
        DEVELOPMENT_MANIFEST,
        TRAIN_P5_TRADES,
        TRAIN_V7_TRADES,
        VALIDATION_P5_TRADES,
        VALIDATION_V7_TRADES,
        TRAIN_DECISIONS,
        VALIDATION_DECISIONS,
        TRAIN_EPISODES,
        VALIDATION_EPISODES,
    )
    for path in sources:
        verify_sidecar(path)

    development = json.loads(DEVELOPMENT_SUMMARY.read_text(encoding="utf-8"))
    validation = json.loads(VALIDATION_SUMMARY.read_text(encoding="utf-8"))
    p4 = load_module(P4_SCRIPT, "hype_p5_v7_comparison_p4")
    slice_audit = load_module(SLICE_SCRIPT, "hype_p5_v7_comparison_slices")
    train_diag, train_v6, train_engine, _, train_context = p4.load_dependencies(train_only=True)
    _, v6, engine, _, context = p4.load_dependencies(train_only=False)

    trade_sets = {
        ("training", "P5"): load_trades(TRAIN_P5_TRADES),
        ("training", "V7_1"): load_trades(TRAIN_V7_TRADES),
        ("validation", "P5"): load_trades(VALIDATION_P5_TRADES),
        ("validation", "V7_1"): load_trades(VALIDATION_V7_TRADES),
    }
    replays = {
        ("training", strategy): p4.replay_metrics(train_v6, train_context, trade_sets[("training", strategy)])
        for strategy in STRATEGIES
    }
    replays.update(
        {
            ("validation", strategy): p4.replay_metrics(v6, context, trade_sets[("validation", strategy)])
            for strategy in STRATEGIES
        }
    )
    expected = {
        ("training", "P5"): development["full_training_resubstitution"]["p5"],
        ("training", "V7_1"): development["full_training_resubstitution"]["v7_1"],
        ("validation", "P5"): validation["p5"],
        ("validation", "V7_1"): validation["v7_1"],
    }
    for key, replay in replays.items():
        for metric in ("net_return_pct", "chronological_1h_mdd_pct", "cost_pct_initial"):
            if not math.isclose(
                float(replay[metric]), float(expected[key][metric]), rel_tol=0.0, abs_tol=1e-9
            ):
                raise RuntimeError(f"{key} {metric} replay parity failed")

    train_equity = {
        strategy: daily_equity(
            slice_audit, p4, train_v6, train_context, trade_sets[("training", strategy)], 0
        )
        for strategy in STRATEGIES
    }
    validation_equity = {
        strategy: daily_equity(
            slice_audit,
            p4,
            v6,
            context,
            trade_sets[("validation", strategy)],
            p4.TRAIN_DAYS,
        )
        for strategy in STRATEGIES
    }
    equity: dict[str, list[dict[str, Any]]] = {}
    for strategy in STRATEGIES:
        terminal = float(train_equity[strategy][-1]["v"])
        equity[strategy] = train_equity[strategy] + [
            {"t": row["t"], "v": float(row["v"]) * terminal}
            for row in validation_equity[strategy][1:]
        ]

    decisions = pd.concat(
        [pd.read_csv(TRAIN_DECISIONS), pd.read_csv(VALIDATION_DECISIONS)], ignore_index=True
    )
    decision_by_index = decisions.set_index(decisions["decision_index"].astype(int)).to_dict("index")
    rsi6 = engine._BASE.wilder_rsi6(context.book.close)
    candles: list[dict[str, Any]] = []
    for index in range(context.book.count):
        ma7 = float(context.features.ma7[index])
        atr = float(context.features.atr7[index])
        prior_ma = float(context.features.ma7[index - 1]) if index else math.nan
        decision = decision_by_index.get(index, {})
        candles.append(
            {
                "t": timestamp_ms(context.book.ts[index]),
                "o": float(context.book.open[index]),
                "h": float(context.book.high[index]),
                "l": float(context.book.low[index]),
                "c": float(context.book.close[index]),
                "ma7": finite_or_none(ma7),
                "slopeAtr": finite_or_none((ma7 - prior_ma) / atr),
                "rsi6": finite_or_none(rsi6[index]),
                "p5Raw": finite_or_none(decision.get("raw_probability", math.nan)),
                "p5Smooth": finite_or_none(decision.get("smoothed_probability", math.nan)),
                "p5Position": int(decision.get("position_after_action", 0)),
                "p5Action": str(decision.get("action", "")),
                "rootSide": int(decision.get("root_side", 0)),
            }
        )

    trades: list[dict[str, Any]] = []
    for segment, label in (("training", "训练"), ("validation", "验证")):
        for strategy in STRATEGIES:
            trades.extend(
                trade_rows(
                    strategy,
                    segment,
                    label,
                    trade_sets[(segment, strategy)],
                    replays[(segment, strategy)]["per_trade_returns"],
                )
            )
    episodes = episode_rows(TRAIN_EPISODES, "training", "训练") + episode_rows(
        VALIDATION_EPISODES, "validation", "验证"
    )

    metrics: dict[str, Any] = {}
    capture_lookup = {
        ("training", "P5"): development["full_training_resubstitution"]["p5_episode_capture"],
        ("training", "V7_1"): development["full_training_resubstitution"]["v7_1_episode_capture"],
        ("validation", "P5"): validation["p5_episode_capture"],
        ("validation", "V7_1"): validation["v7_1_episode_capture"],
    }
    for strategy in STRATEGIES:
        metrics[strategy] = {
            "label": STRATEGIES[strategy]["label"],
            "color": STRATEGIES[strategy]["color"],
            "training": {
                **{key: expected[("training", strategy)][key] for key in (
                    "net_return_pct",
                    "chronological_1h_mdd_pct",
                    "trades",
                    "win_rate",
                    "profit_factor",
                    "cost_pct_initial",
                    "exposure_days",
                )},
                **capture_lookup[("training", strategy)],
            },
            "validation": {
                **{key: expected[("validation", strategy)][key] for key in (
                    "net_return_pct",
                    "chronological_1h_mdd_pct",
                    "trades",
                    "win_rate",
                    "profit_factor",
                    "cost_pct_initial",
                    "exposure_days",
                )},
                **capture_lookup[("validation", strategy)],
            },
        }
        for segment in ("training", "validation"):
            count = int(metrics[strategy][segment]["trades"])
            metrics[strategy][segment]["average_hold_days"] = (
                float(metrics[strategy][segment]["exposure_days"]) / count if count else 0.0
            )

    insights = {
        "training": {
            "extraEpisodes": int(
                metrics["P5"]["training"]["episodes_with_any_exposure"]
                - metrics["V7_1"]["training"]["episodes_with_any_exposure"]
            ),
            "extraTrades": int(metrics["P5"]["training"]["trades"] - metrics["V7_1"]["training"]["trades"]),
            "extraCostPct": float(
                metrics["P5"]["training"]["cost_pct_initial"]
                - metrics["V7_1"]["training"]["cost_pct_initial"]
            ),
            "holdRatio": float(
                metrics["P5"]["training"]["average_hold_days"]
                / metrics["V7_1"]["training"]["average_hold_days"]
            ),
        },
        "validation": {
            "extraEpisodes": int(
                metrics["P5"]["validation"]["episodes_with_any_exposure"]
                - metrics["V7_1"]["validation"]["episodes_with_any_exposure"]
            ),
            "extraTrades": int(metrics["P5"]["validation"]["trades"] - metrics["V7_1"]["validation"]["trades"]),
            "extraCostPct": float(
                metrics["P5"]["validation"]["cost_pct_initial"]
                - metrics["V7_1"]["validation"]["cost_pct_initial"]
            ),
            "holdRatio": float(
                metrics["P5"]["validation"]["average_hold_days"]
                / metrics["V7_1"]["validation"]["average_hold_days"]
            ),
        },
    }

    payload = {
        "title": "P5 识别得更多，为什么反而不赚钱？",
        "subtitle": "HYPEUSDT · 1D · 完整446日 · 训练365日 + 冻结验证81日",
        "status": "V7_1_NOT_BEATEN · diagnostic-only · reused holdout · not live-ready",
        "generatedAt": datetime.now(UTC).isoformat(),
        "window": {
            "start": pd.Timestamp(context.book.ts[0]).isoformat(),
            "boundary": pd.Timestamp(context.book.ts[p4.TRAIN_DAYS]).isoformat(),
            "boundaryT": timestamp_ms(context.book.ts[p4.TRAIN_DAYS]),
            "lastDay": pd.Timestamp(context.book.ts[-1]).isoformat(),
            "terminal": pd.Timestamp(context.book.terminal_ts).isoformat(),
            "days": context.book.count,
            "trainDays": p4.TRAIN_DAYS,
            "validationDays": context.book.count - p4.TRAIN_DAYS,
        },
        "strategies": STRATEGIES,
        "metrics": metrics,
        "insights": insights,
        "equityNote": "权益线为了连续观察而拼接：训练终值 × 验证相对权益；验证账户实际独立从1开始。",
        "candles": candles,
        "equity": equity,
        "trades": trades,
        "episodes": episodes,
    }
    manifest = {
        "schema": "hype-1d-ma7-mlt-p5-v7-1-comparison-trade-path-v1",
        "generated_at": payload["generatedAt"],
        "renderer": Path(__file__).name,
        "sources": {path.name: sha256(path) for path in sources},
        "window": payload["window"],
        "candles": len(candles),
        "ma7_points": sum(row["ma7"] is not None for row in candles),
        "probability_points": sum(row["p5Smooth"] is not None for row in candles),
        "equity_points": {key: len(value) for key, value in equity.items()},
        "trades_by_strategy": {
            key: sum(row["strategy"] == key for row in trades) for key in STRATEGIES
        },
        "trades_by_segment": {
            key: sum(row["segment"] == key for row in trades)
            for key in ("training", "validation")
        },
        "episodes": len(episodes),
        "new_captures": sum(row["classification"] == "P5_NEW_CAPTURE" for row in episodes),
        "line_render_count": len(trades),
        "external_dependencies": 0,
    }
    return payload, manifest


HTML_TEMPLATE = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>P5 vs V7.1 完整交易路径</title><style>
:root{color-scheme:dark;--bg:#0b0f12;--panel:#11171b;--panel2:#151d22;--line:#2a353b;--grid:#202a30;--text:#e8edef;--muted:#89979e;--up:#72b29b;--down:#c87878;--ma:#d7b869;--v7:#6cb7c8;--p5:#e7aa61;--accent:#d7b869;--trendLong:rgba(114,178,155,.075);--trendShort:rgba(200,120,120,.075)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.48 Geist,Satoshi,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.shell{max-width:1880px;margin:auto;padding:24px}.hero{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(360px,.8fr);gap:42px;align-items:end;padding:20px 0 24px;border-bottom:1px solid var(--line)}.eyebrow{color:var(--accent);font:600 11px/1.2 "Geist Mono",ui-monospace,monospace;letter-spacing:.16em;text-transform:uppercase}.hero h1{max-width:920px;margin:11px 0 10px;font-size:clamp(30px,4vw,58px);line-height:.98;letter-spacing:-.045em;font-weight:620}.subtitle,.status,.note{color:var(--muted)}.verdict{border-left:2px solid var(--accent);padding:6px 0 6px 18px}.verdict b{display:block;font-size:18px;margin-bottom:6px}.metrics{display:grid;grid-template-columns:1.25fr 1fr;margin:28px 0 18px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}.strategy-block{display:grid;grid-template-columns:160px repeat(4,minmax(120px,1fr));min-height:116px;align-items:stretch}.strategy-block+ .strategy-block{border-left:1px solid var(--line)}.strategy-name,.datum{padding:17px 16px;border-right:1px solid var(--line)}.strategy-name{display:flex;flex-direction:column;justify-content:space-between}.strategy-name b{font-size:18px}.strategy-name span,.datum span{color:var(--muted);font-size:11px}.datum{font-family:"Geist Mono",ui-monospace,monospace}.datum b{display:block;margin-top:7px;font-size:18px;font-weight:550}.p5c{color:var(--p5)}.v7c{color:var(--v7)}.positive{color:var(--up)}.negative{color:var(--down)}.diagnosis{display:grid;grid-template-columns:1.25fr .75fr;gap:1px;background:var(--line);margin-bottom:18px}.diagnosis>div{background:var(--panel);padding:18px 20px}.diagnosis h2{font-size:15px;margin:0 0 10px}.diagnosis p{max-width:90ch;margin:0;color:#c5ced2}.equation{font:500 14px/1.6 "Geist Mono",ui-monospace,monospace;color:var(--accent)}.toolbar{position:sticky;top:0;z-index:3;display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;padding:10px 12px;border:1px solid var(--line);background:rgba(17,23,27,.94);backdrop-filter:blur(14px);box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}button{color:var(--text);border:1px solid #394850;background:#172127;padding:7px 11px;cursor:pointer;font:12px "Geist Mono",ui-monospace,monospace;transition:transform .2s cubic-bezier(.16,1,.3,1),border-color .2s}button:hover{border-color:#64757e}button:active{transform:translateY(1px) scale(.98)}label{color:var(--muted);user-select:none;font:12px "Geist Mono",ui-monospace,monospace}input{vertical-align:-2px}.chart{border:1px solid var(--line);border-top:0;background:var(--panel);overflow:hidden}canvas{width:100%;display:block}#priceChart{height:610px;cursor:crosshair}#probChart{height:165px;border-top:1px solid var(--line)}#equityChart{height:230px;border-top:1px solid var(--line)}.chart-note{padding:9px 12px;border:1px solid var(--line);border-top:0;color:var(--muted);font:11px "Geist Mono",ui-monospace,monospace}.legend-chip{display:inline-flex;gap:6px;align-items:center;margin-right:16px}.dot{width:8px;height:8px;display:inline-block}.dot.long{background:rgba(114,178,155,.6)}.dot.short{background:rgba(200,120,120,.6)}.sections{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr);gap:18px;margin-top:24px}.table-wrap{max-height:660px;overflow:auto;border:1px solid var(--line);background:var(--panel)}.table-head{position:sticky;top:0;z-index:2;padding:14px 16px;background:var(--panel2);border-bottom:1px solid var(--line)}.table-head h2{font-size:14px;margin:0}.table-head p{color:var(--muted);font-size:11px;margin:4px 0 0}table{width:100%;border-collapse:collapse;min-width:900px;font:11px "Geist Mono",ui-monospace,monospace}th,td{padding:9px 10px;border-bottom:1px solid var(--grid);text-align:right;white-space:nowrap}th{color:var(--muted);background:var(--panel2);position:sticky;top:64px;z-index:1;font-weight:500}th:nth-child(-n+4),td:nth-child(-n+4),th:last-child,td:last-child{text-align:left}tbody tr{cursor:pointer;transition:background .18s}tbody tr:hover,tbody tr.active{background:#1b272d}tbody tr.new{background:rgba(215,184,105,.07)}.badge{padding:2px 6px;border:1px solid #6f6040;color:#e3c67d}.tooltip{position:fixed;z-index:8;display:none;pointer-events:none;max-width:560px;padding:11px 13px;border:1px solid #4b5c64;background:rgba(11,15,18,.97);box-shadow:0 14px 34px rgba(0,0,0,.3);white-space:pre-line;font:11px/1.55 "Geist Mono",ui-monospace,monospace}@media(max-width:1100px){.shell{padding:12px}.hero,.diagnosis,.sections{grid-template-columns:1fr}.metrics{grid-template-columns:1fr}.strategy-block+ .strategy-block{border-left:0;border-top:1px solid var(--line)}#priceChart{height:500px}.sections{gap:12px}}@media(max-width:720px){.strategy-block{grid-template-columns:1fr 1fr}.strategy-name{grid-column:1/-1;border-bottom:1px solid var(--line)}.hero h1{font-size:34px}.toolbar{position:static}}
</style></head><body><main class="shell"><section class="hero"><div><div class="eyebrow">HYPE · MA7 lifecycle audit</div><h1 id="title"></h1><div id="subtitle" class="subtitle"></div><div id="status" class="status"></div></div><div class="verdict"><b>结论：命中数量增加，但持仓质量下降</b><span class="note">P5 把“趋势状态概率”直接当成进出场开关，新增了机会，也新增了错误和过早退出。</span></div></section><section id="metrics" class="metrics"></section><section class="diagnosis"><div><h2>核心矛盾</h2><p id="diagnosisText"></p></div><div><h2>验证期公式</h2><div id="equation" class="equation"></div></div></section>
<div class="toolbar"><button id="reset">完整446日</button><button id="focusTrain">训练365日</button><button id="focusValidation">验证81日</button><button id="focusNew">下一段 P5 新识别</button><button id="focusLoss">下一笔 P5 亏损</button><button id="zoomIn">放大</button><button id="zoomOut">缩小</button><label><input id="showMa" type="checkbox" checked> MA7</label><label><input id="showTrends" type="checkbox" checked> 稳定趋势区间</label><label><input id="showLabels" type="checkbox" checked> 交易编号</label><label><input class="strategy-toggle" data-strategy="P5" type="checkbox" checked><span class="p5c"> P5 虚线</span></label><label><input class="strategy-toggle" data-strategy="V7_1" type="checkbox" checked><span class="v7c"> V7.1 实线</span></label></div>
<div class="chart"><canvas id="priceChart"></canvas><canvas id="probChart"></canvas><canvas id="equityChart"></canvas></div><div class="chart-note"><span class="legend-chip"><i class="dot long"></i>绿色底：事后稳定多头趋势</span><span class="legend-chip"><i class="dot short"></i>红色底：事后稳定空头趋势</span>▲/▼ 入场 · ● 退出 · P5 概率图中 0.55 为入场线、0.45 为退出线 · 竖虚线为训练/验证边界 · 滚轮缩放 · 拖动平移 · 双击复位。<br><span id="equityNote"></span></div>
<section class="sections"><div class="table-wrap"><div class="table-head"><h2>稳定趋势段覆盖</h2><p>点击一行聚焦。黄色行是 V7.1 完全没碰到、P5 新识别的趋势。</p></div><table><thead><tr><th>阶段</th><th>趋势</th><th>方向</th><th>分类</th><th>区间</th><th>天数</th><th>P5覆盖</th><th>V7覆盖</th><th>覆盖差</th></tr></thead><tbody id="episodeRows"></tbody></table></div><div class="table-wrap"><div class="table-head"><h2>全部交易路径</h2><p>P5 39笔、V7.1 20笔。按收益着色，点击聚焦。</p></div><table><thead><tr><th>阶段</th><th>策略</th><th>交易</th><th>方向</th><th>入场</th><th>退出</th><th>持有</th><th>净收益</th><th>入场概率</th><th>退出原因</th></tr></thead><tbody id="tradeRows"></tbody></table></div></section></main><div id="tooltip" class="tooltip"></div><script>
const DATA=__PAYLOAD__,DAY=86400000,C={bg:'#11171b',bg2:'#0e1417',grid:'#202a30',muted:'#89979e',up:'#72b29b',down:'#c87878',ma:'#d7b869',v7:'#6cb7c8',p5:'#e7aa61',accent:'#d7b869'};
const $=id=>document.getElementById(id),candles=DATA.candles,trades=DATA.trades,episodes=DATA.episodes,equity=DATA.equity,priceCanvas=$('priceChart'),probCanvas=$('probChart'),equityCanvas=$('equityChart'),tooltip=$('tooltip');const domainMin=candles[0].t,domainMax=equity.P5.at(-1).t;let viewStart=domainMin,viewEnd=domainMax,hoverT=null,activeId=null,dragging=false,dragX=0,dragStart=0,newIndex=0,lossIndex=0;
function activeStrategies(){return new Set([...document.querySelectorAll('.strategy-toggle:checked')].map(x=>x.dataset.strategy))}function signed(v,d=2){return(v>=0?'+':'')+Number(v).toFixed(d)}function fmt(v,d=3){return v==null?'—':Number(v).toFixed(d)}function pct(v,d=1){return fmt(v*100,d)+'%'}function day(t){return new Date(t).toISOString().slice(0,10)}function clamp(v,a,b){return Math.max(a,Math.min(b,v))}function setup(c){const r=c.getBoundingClientRect(),d=devicePixelRatio||1;c.width=Math.round(r.width*d);c.height=Math.round(r.height*d);const x=c.getContext('2d');x.setTransform(d,0,0,d,0,0);return{ctx:x,w:r.width,h:r.height}}function xs(t,l,w){return l+(t-viewStart)/(viewEnd-viewStart)*w}function visCandles(){return candles.filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY)}function visTrades(){const a=activeStrategies();return trades.filter(p=>a.has(p.strategy)&&p.exitT>=viewStart&&p.entryT<=viewEnd)}function visEpisodes(){return episodes.filter(p=>p.endT>=viewStart&&p.startT<=viewEnd)}
function ticks(lo,hi,n){const span=Math.max(1e-9,hi-lo),raw=span/n,p=10**Math.floor(Math.log10(raw)),q=raw/p,s=(q<1.5?1:q<3?2:q<7?5:10)*p,o=[];for(let v=Math.ceil(lo/s)*s;v<=hi+s*.1;v+=s)o.push(v);return o}function axes(ctx,m,pw,ph,lo,hi,y){ctx.font='11px "Geist Mono",monospace';for(const v of ticks(lo,hi,5)){const yy=y(v);ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(m.l,yy);ctx.lineTo(m.l+pw,yy);ctx.stroke();ctx.fillStyle=C.muted;ctx.textAlign='right';ctx.fillText(v.toFixed(Math.abs(v)<10?2:1),m.l-8,yy+4)}for(let i=0;i<=8;i++){const z=viewStart+(viewEnd-viewStart)*i/8,x=xs(z,m.l,pw);ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.fillStyle=C.muted;ctx.textAlign=i===0?'left':i===8?'right':'center';ctx.fillText(day(z),x,m.t+ph+18)}}function boundary(ctx,m,pw,ph,label){const t=DATA.window.boundaryT;if(t<viewStart||t>viewEnd)return;const x=xs(t,m.l,pw);ctx.strokeStyle='#d5dde0';ctx.globalAlpha=.65;ctx.setLineDash([6,5]);ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;if(label){ctx.fillStyle='#d5dde0';ctx.textAlign='center';ctx.fillText('训练 ← 365 | 81 → 验证',x,m.t+13)}}function crosshair(ctx,m,pw,ph){if(hoverT==null)return;const x=xs(hoverT,m.l,pw);ctx.strokeStyle=C.muted;ctx.globalAlpha=.5;ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1}function line(ctx,vals,key,color,y,l,w,dash=[],width=1.8){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.beginPath();let on=false;for(const p of vals){if(p[key]==null){on=false;continue}const x=xs(p.t+DAY/2,l,w),yy=y(p[key]);on?ctx.lineTo(x,yy):(ctx.moveTo(x,yy),on=true)}ctx.stroke();ctx.setLineDash([])}function marker(ctx,x,y,side,entry,color,size){ctx.fillStyle=color;ctx.strokeStyle=C.bg2;ctx.lineWidth=1.2;ctx.beginPath();if(entry){if(side==='long'){ctx.moveTo(x,y-size);ctx.lineTo(x-size,y+size);ctx.lineTo(x+size,y+size)}else{ctx.moveTo(x,y+size);ctx.lineTo(x-size,y-size);ctx.lineTo(x+size,y-size)}ctx.closePath()}else ctx.arc(x,y,size-1,0,Math.PI*2);ctx.fill();ctx.stroke()}
function shadeEpisodes(ctx,m,pw,ph){if(!$('showTrends').checked)return;for(const e of visEpisodes()){const x1=xs(Math.max(e.startT,viewStart),m.l,pw),x2=xs(Math.min(e.endT,viewEnd),m.l,pw);ctx.fillStyle=e.side>0?'rgba(114,178,155,.075)':'rgba(200,120,120,.075)';ctx.fillRect(x1,m.t,Math.max(1,x2-x1),ph);if(e.classification==='P5_NEW_CAPTURE'){ctx.strokeStyle='rgba(215,184,105,.7)';ctx.setLineDash([3,4]);ctx.strokeRect(x1+.5,m.t+.5,Math.max(1,x2-x1-1),ph-1);ctx.setLineDash([])}}}
function drawPrice(){const{ctx,w,h}=setup(priceCanvas),m={l:72,r:25,t:24,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,vis=visCandles(),vtr=visTrades();ctx.fillStyle=C.bg;ctx.fillRect(0,0,w,h);if(!vis.length)return;let lo=Math.min(...vis.map(p=>p.l),...vtr.map(t=>Math.min(t.entry,t.exit))),hi=Math.max(...vis.map(p=>p.h),...vtr.map(t=>Math.max(t.entry,t.exit))),pad=(hi-lo)*.07||1;lo-=pad;hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y);shadeEpisodes(ctx,m,pw,ph);const bw=clamp(pw/Math.max(1,(viewEnd-viewStart)/DAY)*.62,1,13);for(const p of vis){const x=xs(p.t+DAY/2,m.l,pw),col=p.c>=p.o?C.up:C.down;ctx.strokeStyle=col;ctx.beginPath();ctx.moveTo(x,y(p.h));ctx.lineTo(x,y(p.l));ctx.stroke();ctx.fillStyle=col;ctx.fillRect(x-bw/2,y(Math.max(p.o,p.c)),bw,Math.max(1,y(Math.min(p.o,p.c))-y(Math.max(p.o,p.c))))}if($('showMa').checked)line(ctx,vis,'ma7',C.ma,y,m.l,pw,[],1.7);for(const t of vtr.sort((a,b)=>a.strategy==='V7_1'?-1:1)){const cfg=DATA.strategies[t.strategy],hot=t.id===activeId,x1=xs(t.entryT,m.l,pw),x2=xs(t.exitT,m.l,pw),y1=y(t.entry),y2=y(t.exit);ctx.strokeStyle=cfg.color;ctx.globalAlpha=hot?1:t.strategy==='P5'?.94:.74;ctx.lineWidth=hot?4:t.strategy==='V7_1'?3:2.35;ctx.setLineDash(cfg.dash);ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;marker(ctx,x1,y1,t.side,true,cfg.color,hot?9:7);marker(ctx,x2,y2,t.side,false,cfg.color,hot?9:7);if($('showLabels').checked||hot){ctx.fillStyle=cfg.color;ctx.textAlign='center';ctx.font='10px "Geist Mono",monospace';ctx.fillText(t.id,x2,y2+(t.strategy==='V7_1'?-11:17))}}boundary(ctx,m,pw,ph,true);crosshair(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign='left';ctx.fillText('PRICE · HYPEUSDT 1D · MA7 · 稳定趋势区间',m.l,15)}
function drawProbability(){const{ctx,w,h}=setup(probCanvas),m={l:72,r:25,t:18,b:28},pw=w-m.l-m.r,ph=h-m.t-m.b,vis=visCandles();ctx.fillStyle=C.bg2;ctx.fillRect(0,0,w,h);const y=v=>m.t+(1-v)*ph;for(const v of[0,.25,.45,.55,.75,1]){const yy=y(v);ctx.strokeStyle=v===.45||v===.55?(v===.55?'rgba(114,178,155,.6)':'rgba(200,120,120,.6)'):C.grid;ctx.setLineDash(v===.45||v===.55?[5,4]:[]);ctx.beginPath();ctx.moveTo(m.l,yy);ctx.lineTo(m.l+pw,yy);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle=C.muted;ctx.textAlign='right';ctx.fillText(v.toFixed(2),m.l-8,yy+4)}shadeEpisodes(ctx,m,pw,ph);line(ctx,vis,'p5Raw','rgba(231,170,97,.35)',y,m.l,pw,[],1);line(ctx,vis,'p5Smooth',C.p5,y,m.l,pw,[],2);boundary(ctx,m,pw,ph,false);crosshair(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign='left';ctx.fillText('P5 TREND PROBABILITY · 0.55入场 / 0.45退出',m.l,13)}
function drawEquity(){const{ctx,w,h}=setup(equityCanvas),m={l:72,r:25,t:20,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,a=activeStrategies(),series=[...a].map(k=>({k,v:equity[k].filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY)})).filter(s=>s.v.length);ctx.fillStyle=C.bg2;ctx.fillRect(0,0,w,h);if(!series.length)return;let lo=Math.min(...series.flatMap(s=>s.v.map(p=>p.v))),hi=Math.max(...series.flatMap(s=>s.v.map(p=>p.v))),pad=(hi-lo)*.08||.02;lo=Math.max(0,lo-pad);hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y);for(const s of series){const cfg=DATA.strategies[s.k];ctx.strokeStyle=cfg.color;ctx.lineWidth=s.k==='V7_1'?2.8:2.2;ctx.setLineDash(cfg.dash);ctx.beginPath();s.v.forEach((p,i)=>{const x=xs(p.t,m.l,pw);i?ctx.lineTo(x,y(p.v)):ctx.moveTo(x,y(p.v))});ctx.stroke();ctx.setLineDash([])}boundary(ctx,m,pw,ph,false);crosshair(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign='left';ctx.fillText('EQUITY · 连续视觉拼接',m.l,13)}function draw(){drawPrice();drawProbability();drawEquity();for(const r of document.querySelectorAll('tbody tr'))r.classList.toggle('active',r.dataset.id===activeId)}
function reset(){viewStart=domainMin;viewEnd=domainMax;activeId=null;draw()}function focusRange(a,b){viewStart=Math.max(domainMin,a);viewEnd=Math.min(domainMax,b);activeId=null;draw()}function zoom(f,a=(viewStart+viewEnd)/2){const cur=viewEnd-viewStart,next=clamp(cur*f,8*DAY,domainMax-domainMin),q=(a-viewStart)/cur;viewStart=a-next*q;viewEnd=viewStart+next;if(viewStart<domainMin){viewEnd+=domainMin-viewStart;viewStart=domainMin}if(viewEnd>domainMax){viewStart-=viewEnd-domainMax;viewEnd=domainMax}draw()}function focusItem(item,startKey,endKey){const a=item[startKey],b=item[endKey],span=Math.max(18*DAY,(b-a)*2.8),mid=(a+b)/2;viewStart=clamp(mid-span/2,domainMin,Math.max(domainMin,domainMax-span));viewEnd=Math.min(domainMax,viewStart+span);activeId=item.id;draw();priceCanvas.scrollIntoView({behavior:'smooth',block:'center'})}function nextNew(){const x=episodes.filter(e=>e.classification==='P5_NEW_CAPTURE');if(x.length)focusItem(x[newIndex++%x.length],'startT','endT')}function nextLoss(){const x=trades.filter(t=>t.strategy==='P5'&&t.netReturnPct<0);if(x.length)focusItem(x[lossIndex++%x.length],'entryT','exitT')}
function metricBlock(strategy){const m=DATA.metrics[strategy],tr=m.training,va=m.validation,cls=strategy==='P5'?'p5c':'v7c';return`<div class="strategy-block"><div class="strategy-name"><b class="${cls}">${m.label}</b><span>训练 / 验证</span></div><div class="datum"><span>收益 · MDD</span><b>${signed(tr.net_return_pct)}% · ${signed(tr.chronological_1h_mdd_pct)}%</b><span>${signed(va.net_return_pct)}% · ${signed(va.chronological_1h_mdd_pct)}%</span></div><div class="datum"><span>交易 · 胜率</span><b>${tr.trades} · ${pct(tr.win_rate)}</b><span>${va.trades} · ${pct(va.win_rate)}</span></div><div class="datum"><span>任意覆盖 · 按天覆盖</span><b>${tr.episodes_with_any_exposure}/${tr.reference_episodes} · ${pct(tr.duration_weighted_capture)}</b><span>${va.episodes_with_any_exposure}/${va.reference_episodes} · ${pct(va.duration_weighted_capture)}</span></div><div class="datum"><span>平均持有 · 成本</span><b>${fmt(tr.average_hold_days,1)}d · ${fmt(tr.cost_pct_initial,2)}%</b><span>${fmt(va.average_hold_days,1)}d · ${fmt(va.cost_pct_initial,2)}%</span></div></div>`}function renderMetrics(){$('metrics').innerHTML=metricBlock('P5')+metricBlock('V7_1');const t=DATA.insights.training,v=DATA.insights.validation;$('diagnosisText').textContent=`训练期 P5 多碰到 ${t.extraEpisodes} 段趋势，却多做 ${t.extraTrades} 笔交易、成本多 ${t.extraCostPct.toFixed(2)} 个百分点，平均持有只有 V7.1 的 ${(t.holdRatio*100).toFixed(0)}%。验证期同样多碰到 ${v.extraEpisodes} 段，但平均持有只剩 V7.1 的 ${(v.holdRatio*100).toFixed(0)}%，所以“碰到”没有转化成“吃到”。`;$('equation').innerHTML=`更多候选 + 更短持有<br>+ 更高换手成本<br>+ 低胜率<br>= 更差净收益`}
function renderEpisodes(){const body=$('episodeRows');body.innerHTML=episodes.map(e=>{const label=e.classification==='P5_NEW_CAPTURE'?'<span class="badge">P5新识别</span>':e.classification==='P5_MORE'?'P5更多':e.classification==='V7_MORE'?'V7更多':'相同';return`<tr data-id="${e.id}" class="${e.classification==='P5_NEW_CAPTURE'?'new':''}"><td>${e.segmentLabel}</td><td>${e.id}</td><td>${e.side>0?'多头':'空头'}</td><td>${label}</td><td>${day(e.startT)} → ${day(e.endT-DAY)}</td><td>${e.durationDays}</td><td class="p5c">${e.p5Days} · ${pct(e.p5Capture)}</td><td class="v7c">${e.v7Days} · ${pct(e.v7Capture)}</td><td class="${e.p5Capture>=e.v7Capture?'positive':'negative'}">${signed((e.p5Capture-e.v7Capture)*100,1)}pp</td></tr>`}).join('');for(const r of body.querySelectorAll('tr'))r.onclick=()=>focusItem(episodes.find(e=>e.id===r.dataset.id),'startT','endT')}
function renderTrades(){const body=$('tradeRows');body.innerHTML=trades.sort((a,b)=>a.entryT-b.entryT||a.strategy.localeCompare(b.strategy)).map(t=>`<tr data-id="${t.id}"><td>${t.segmentLabel}</td><td class="${t.strategy==='P5'?'p5c':'v7c'}">${t.strategyLabel}</td><td>${t.id}</td><td>${t.side==='long'?'做多':'做空'}</td><td>${day(t.entryT)} · ${fmt(t.entry)}</td><td>${day(t.exitT)} · ${fmt(t.exit)}</td><td>${t.barsHeld}d</td><td class="${t.netReturnPct>=0?'positive':'negative'}">${signed(t.netReturnPct)}%</td><td>${fmt(t.entryProbability,3)}</td><td>${t.exitReason}${t.directReversal?' · 直接反手':''}</td></tr>`).join('');for(const r of body.querySelectorAll('tr'))r.onclick=()=>focusItem(trades.find(t=>t.id===r.dataset.id),'entryT','exitT')}
function pointerMove(e){if(dragging){const r=priceCanvas.getBoundingClientRect(),span=viewEnd-viewStart,shift=-(e.clientX-dragX)/Math.max(1,r.width-97)*span;viewStart=clamp(dragStart+shift,domainMin,domainMax-span);viewEnd=viewStart+span;draw();return}const r=priceCanvas.getBoundingClientRect(),q=clamp((e.clientX-r.left-72)/Math.max(1,r.width-97),0,1);hoverT=viewStart+q*(viewEnd-viewStart);const c=candles.reduce((a,b)=>Math.abs(b.t+DAY/2-hoverT)<Math.abs(a.t+DAY/2-hoverT)?b:a,candles[0]),near=trades.filter(t=>activeStrategies().has(t.strategy)&&Math.min(Math.abs(t.entryT-hoverT),Math.abs(t.exitT-hoverT))<DAY*.7),ep=episodes.find(x=>x.startT<=c.t&&x.endT>c.t);let s=`${day(c.t)} UTC\nO ${fmt(c.o)} H ${fmt(c.h)} L ${fmt(c.l)} C ${fmt(c.c)}\nMA7 ${fmt(c.ma7)} · slope/ATR ${signed(c.slopeAtr,4)} · RSI6 ${fmt(c.rsi6,1)}\nP5 raw ${fmt(c.p5Raw,3)} · smooth ${fmt(c.p5Smooth,3)} · ${c.p5Action||'无动作'}`;if(ep)s+=`\n${ep.id} ${ep.side>0?'稳定多头':'稳定空头'} · P5 ${pct(ep.p5Capture)} / V7 ${pct(ep.v7Capture)}`;for(const t of near)s+=`\n${t.id} ${t.strategyLabel} ${t.side==='long'?'多':'空'} · ${signed(t.netReturnPct)}%`;tooltip.textContent=s;tooltip.style.display='block';tooltip.style.left=Math.min(innerWidth-575,e.clientX+15)+'px';tooltip.style.top=Math.min(innerHeight-230,e.clientY+15)+'px';draw()}
$('title').textContent=DATA.title;$('subtitle').textContent=DATA.subtitle;$('status').textContent=`${DATA.status} · ${DATA.window.start.slice(0,10)} → ${DATA.window.terminal.slice(0,10)}`;$('equityNote').textContent=DATA.equityNote;$('reset').onclick=reset;$('focusTrain').onclick=()=>focusRange(domainMin,DATA.window.boundaryT);$('focusValidation').onclick=()=>focusRange(DATA.window.boundaryT,domainMax);$('focusNew').onclick=nextNew;$('focusLoss').onclick=nextLoss;$('zoomIn').onclick=()=>zoom(.65);$('zoomOut').onclick=()=>zoom(1.55);$('showMa').onchange=draw;$('showTrends').onchange=draw;$('showLabels').onchange=draw;for(const x of document.querySelectorAll('.strategy-toggle'))x.onchange=draw;priceCanvas.onwheel=e=>{e.preventDefault();const r=priceCanvas.getBoundingClientRect(),q=clamp((e.clientX-r.left-72)/Math.max(1,r.width-97),0,1);zoom(e.deltaY>0?1.2:.82,viewStart+q*(viewEnd-viewStart))};priceCanvas.onpointerdown=e=>{dragging=true;dragX=e.clientX;dragStart=viewStart;priceCanvas.setPointerCapture(e.pointerId)};priceCanvas.onpointerup=e=>{dragging=false;if(priceCanvas.hasPointerCapture(e.pointerId))priceCanvas.releasePointerCapture(e.pointerId)};priceCanvas.onpointermove=pointerMove;priceCanvas.onpointerleave=()=>{if(!dragging){hoverT=null;tooltip.style.display='none';draw()}};priceCanvas.ondblclick=reset;window.onresize=draw;renderMetrics();renderEpisodes();renderTrades();draw();
</script></body></html>'''


def main() -> None:
    args = parse_args()
    outputs = (
        OUTPUT_PATH,
        MANIFEST_PATH,
        OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".sha256"),
        MANIFEST_PATH.with_suffix(MANIFEST_PATH.suffix + ".sha256"),
    )
    if any(path.exists() for path in outputs) and not args.force:
        raise RuntimeError(f"comparison artifact exists: {OUTPUT_PATH.name}; use --force")
    payload, manifest = build_payload()
    html = HTML_TEMPLATE.replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
    )
    required = (
        "setPointerCapture",
        "releasePointerCapture",
        "ondblclick=reset",
        "focusValidation",
        "nextNew",
        "nextLoss",
        "p5Smooth",
        "0.55入场 / 0.45退出",
        "稳定趋势区间",
        "MA7",
    )
    for token in required:
        if token not in html:
            raise RuntimeError(f"required comparison interaction missing: {token}")
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    manifest.update(
        {
            "html": OUTPUT_PATH.name,
            "html_sha256": sha256(OUTPUT_PATH),
            "html_bytes": OUTPUT_PATH.stat().st_size,
            "renderer_sha256": sha256(Path(__file__).resolve()),
        }
    )
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    for path in (OUTPUT_PATH, MANIFEST_PATH):
        path.with_suffix(path.suffix + ".sha256").write_text(
            f"{sha256(path)}  {path.name}\n", encoding="utf-8"
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
