"""Render P6/V7.1 training-only paths with the 80-day internal confirmation overlay."""

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
STEM = "hype_1d_ma7_mlt_p6_v7_anchor_three_head_lifecycle_2026-08-28"

SUMMARY = ARTIFACT_DIR / f"{STEM}_development_summary.json"
DEVELOPMENT_MANIFEST = ARTIFACT_DIR / f"{STEM}_development_manifest.json"
FEATURE_FRAME = ARTIFACT_DIR / f"{STEM}_training_feature_frame.csv"
TRAIN_SCORES = ARTIFACT_DIR / f"{STEM}_training_scores.csv"
CONFIRMATION_SCORES = ARTIFACT_DIR / f"{STEM}_internal_confirmation_scores.csv"
TRAIN_P6_TRADES = ARTIFACT_DIR / f"{STEM}_training_trades.csv"
TRAIN_V7_TRADES = ARTIFACT_DIR / f"{STEM}_training_v7_1_trades.csv"
CONFIRMATION_P6_TRADES = ARTIFACT_DIR / f"{STEM}_internal_confirmation_trades.csv"
TRAIN_EPISODES = ARTIFACT_DIR / f"{STEM}_training_episode_capture.csv"

OUTPUT_PATH = ARTIFACT_DIR / f"{STEM}_v7_1_training_trade_paths.html"
MANIFEST_PATH = ARTIFACT_DIR / f"{STEM}_v7_1_training_trade_paths_manifest.json"

TRAIN_DAYS = 365
DEVELOPMENT_DAYS = 285
STRATEGIES = {
    "P6_FULL": {
        "label": "P6 完整训练拟合",
        "code": "P6-F",
        "color": "#e6a15c",
        "dash": [9, 5],
        "group": "full",
    },
    "V7_FULL": {
        "label": "exact V7.1",
        "code": "V7-F",
        "color": "#69b7c9",
        "dash": [],
        "group": "full",
    },
    "P6_IC": {
        "label": "P6 最后80日内部确认",
        "code": "P6-I",
        "color": "#c58ad9",
        "dash": [3, 4],
        "group": "confirmation",
    },
    "V7_IC": {
        "label": "V7.1 最后80日基准",
        "code": "V7-I",
        "color": "#9ccdd7",
        "dash": [2, 4],
        "group": "confirmation",
    },
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
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
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
    rows = [{"t": timestamp_ms(ts), "v": last_at_timestamp[ts]} for ts in timestamps]
    if not math.isclose(rows[-1]["v"], terminal_equity, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError("daily equity terminal parity failed")
    return rows


def trade_rows(
    strategy: str,
    segment: str,
    trades: list[dict[str, Any]],
    returns: list[float],
) -> list[dict[str, Any]]:
    if len(trades) != len(returns):
        raise RuntimeError(f"{strategy} trade return parity failed")
    rows: list[dict[str, Any]] = []
    for order, (trade, net_return) in enumerate(zip(trades, returns, strict=True), start=1):
        source = str(trade.get("source", ""))
        if source == "nan":
            source = "V7.1 core"
        rows.append(
            {
                "id": f"{STRATEGIES[strategy]['code']}-{order:02d}",
                "strategy": strategy,
                "strategyLabel": STRATEGIES[strategy]["label"],
                "segment": segment,
                "side": str(trade["side"]),
                "entryT": timestamp_ms(trade["entry_ts"]),
                "exitT": timestamp_ms(trade["exit_ts"]),
                "entry": float(trade["entry_price"]),
                "exit": float(trade["exit_price"]),
                "barsHeld": int(trade.get("bars_held", 0)),
                "netReturnPct": float(net_return) * 100.0,
                "exitReason": str(trade["exit_reason"]),
                "entryProbability": finite_or_none(trade.get("entry_probability")),
                "source": source,
            }
        )
    return rows


def episode_rows(path: Path) -> list[dict[str, Any]]:
    frame = pd.read_csv(path)
    full = frame.loc[frame["strategy"].isin(["P6", "V7.1"])].copy()
    rows: list[dict[str, Any]] = []
    for episode_id, group in full.groupby("episode_id", sort=False):
        lookup = group.set_index("strategy")
        if "P6" not in lookup.index or "V7.1" not in lookup.index:
            raise RuntimeError(f"episode strategy pair missing: {episode_id}")
        p6 = lookup.loc["P6"]
        v7 = lookup.loc["V7.1"]
        p6_capture = float(p6["capture_ratio"])
        v7_capture = float(v7["capture_ratio"])
        if p6_capture > 0 and v7_capture == 0:
            classification = "P6_NEW_CAPTURE"
        elif p6_capture > v7_capture:
            classification = "P6_MORE"
        elif p6_capture < v7_capture:
            classification = "V7_MORE"
        else:
            classification = "SAME"
        rows.append(
            {
                "id": str(episode_id),
                "side": int(p6["side"]),
                "startT": timestamp_ms(p6["start_ts"]),
                "endT": timestamp_ms(p6["end_ts"]) + 86_400_000,
                "durationDays": int(p6["duration_days"]),
                "p6Days": int(p6["covered_days"]),
                "v7Days": int(v7["covered_days"]),
                "p6Capture": p6_capture,
                "v7Capture": v7_capture,
                "classification": classification,
            }
        )
    return rows


def score_lookup(path: Path) -> dict[int, dict[str, float]]:
    frame = pd.read_csv(path)
    output: dict[int, dict[str, float]] = {}
    for row in frame.to_dict("records"):
        output.setdefault(int(row["index"]), {})[str(row["head"])] = float(row["probability"])
    return output


def build_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    sources = (
        SUMMARY,
        DEVELOPMENT_MANIFEST,
        FEATURE_FRAME,
        TRAIN_SCORES,
        CONFIRMATION_SCORES,
        TRAIN_P6_TRADES,
        TRAIN_V7_TRADES,
        CONFIRMATION_P6_TRADES,
        TRAIN_EPISODES,
    )
    for path in sources:
        verify_sidecar(path)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    frozen = json.loads(DEVELOPMENT_MANIFEST.read_text(encoding="utf-8"))
    if frozen["holdout_permitted"] is not False:
        raise RuntimeError("P6 renderer expects the holdout to remain locked")

    p4 = load_module(P4_SCRIPT, "hype_p6_trade_path_p4")
    slice_audit = load_module(SLICE_SCRIPT, "hype_p6_trade_path_slices")
    _, v6, _, _, context = p4.load_dependencies(train_only=True)
    if context.book.count != TRAIN_DAYS:
        raise RuntimeError("renderer must use the physical 365-day training context")
    boundary_ts = pd.Timestamp(context.book.ts[DEVELOPMENT_DAYS])

    trade_sets = {
        "P6_FULL": load_trades(TRAIN_P6_TRADES),
        "V7_FULL": load_trades(TRAIN_V7_TRADES),
        "P6_IC": load_trades(CONFIRMATION_P6_TRADES),
    }
    # The internal-confirmation V7.1 schedule is an independently flat-started
    # slice. Its core rows are embedded in the P6 confirmation trade export;
    # slicing the full-year V7.1 schedule would retain a different prior state.
    trade_sets["V7_IC"] = [
        row for row in trade_sets["P6_IC"] if pd.isna(row.get("source"))
    ]
    replays = {
        strategy: p4.replay_metrics(v6, context, rows)
        for strategy, rows in trade_sets.items()
    }
    expected = {
        "P6_FULL": summary["full_training_resubstitution"]["p6"],
        "V7_FULL": summary["full_training_resubstitution"]["v7_1"],
        "P6_IC": summary["development_gate"]["internal_confirmation"]["p6"],
        "V7_IC": summary["development_gate"]["internal_confirmation"]["v7_1"],
    }
    for strategy in STRATEGIES:
        for metric in ("net_return_pct", "chronological_1h_mdd_pct", "cost_pct_initial"):
            if not math.isclose(
                float(replays[strategy][metric]),
                float(expected[strategy][metric]),
                rel_tol=0.0,
                abs_tol=1e-9,
            ):
                raise RuntimeError(f"{strategy} {metric} replay parity failed")

    frame = pd.read_csv(FEATURE_FRAME)
    full_scores = score_lookup(TRAIN_SCORES)
    confirmation_scores = score_lookup(CONFIRMATION_SCORES)
    candles: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        index = int(row["index"])
        full = full_scores.get(index, {})
        confirmation = confirmation_scores.get(index, {})
        candles.append(
            {
                "t": timestamp_ms(row["ts"]),
                "o": float(row["open"]),
                "h": float(row["high"]),
                "l": float(row["low"]),
                "c": float(row["close"]),
                "ma7": finite_or_none(row["ma7"]),
                "slopeAtr": finite_or_none(row["slope1_atr"]),
                "rootSide": int(row["root_side"]),
                "fullEntry": finite_or_none(full.get("entry")),
                "fullSurvival": finite_or_none(full.get("survival")),
                "fullReversal": finite_or_none(full.get("reversal")),
                "icEntry": finite_or_none(confirmation.get("entry")),
                "icSurvival": finite_or_none(confirmation.get("survival")),
                "icReversal": finite_or_none(confirmation.get("reversal")),
            }
        )

    trades: list[dict[str, Any]] = []
    for strategy in STRATEGIES:
        trades.extend(
            trade_rows(
                strategy,
                STRATEGIES[strategy]["group"],
                trade_sets[strategy],
                replays[strategy]["per_trade_returns"],
            )
        )
    episodes = episode_rows(TRAIN_EPISODES)
    equity = {
        "P6_FULL": daily_equity(slice_audit, p4, v6, context, trade_sets["P6_FULL"], 0),
        "V7_FULL": daily_equity(slice_audit, p4, v6, context, trade_sets["V7_FULL"], 0),
        "P6_IC": daily_equity(
            slice_audit, p4, v6, context, trade_sets["P6_IC"], DEVELOPMENT_DAYS
        ),
        "V7_IC": daily_equity(
            slice_audit, p4, v6, context, trade_sets["V7_IC"], DEVELOPMENT_DAYS
        ),
    }

    capture = {
        "P6_FULL": summary["full_training_resubstitution"]["p6_episode_capture"],
        "V7_FULL": summary["full_training_resubstitution"]["v7_1_episode_capture"],
        "P6_IC": summary["development_gate"]["internal_confirmation"]["p6_episode_capture"],
        "V7_IC": summary["development_gate"]["internal_confirmation"]["v7_1_episode_capture"],
    }
    metrics: dict[str, Any] = {}
    for strategy in STRATEGIES:
        metrics[strategy] = {
            **{
                key: expected[strategy][key]
                for key in (
                    "net_return_pct",
                    "chronological_1h_mdd_pct",
                    "trades",
                    "win_rate",
                    "profit_factor",
                    "cost_pct_initial",
                    "exposure_days",
                )
            },
            **capture[strategy],
        }
        count = int(metrics[strategy]["trades"])
        metrics[strategy]["average_hold_days"] = (
            float(metrics[strategy]["exposure_days"]) / count if count else 0.0
        )

    payload = {
        "title": "P6 为什么样本内很漂亮，时间外推却失败？",
        "subtitle": "HYPEUSDT · 1D · 只画前365日 · 前285日开发 + 最后80日内部确认",
        "status": "DEVELOPMENT_FAILED_HOLDOUT_LOCKED · 后81日未读取",
        "generatedAt": datetime.now(UTC).isoformat(),
        "window": {
            "start": pd.Timestamp(context.book.ts[0]).isoformat(),
            "boundary": boundary_ts.isoformat(),
            "boundaryT": timestamp_ms(boundary_ts),
            "lastDay": pd.Timestamp(context.book.ts[-1]).isoformat(),
            "terminal": pd.Timestamp(context.book.terminal_ts).isoformat(),
            "terminalT": timestamp_ms(context.book.terminal_ts),
            "days": TRAIN_DAYS,
            "developmentDays": DEVELOPMENT_DAYS,
            "confirmationDays": TRAIN_DAYS - DEVELOPMENT_DAYS,
        },
        "strategies": STRATEGIES,
        "metrics": metrics,
        "oof": {
            head: {
                "auc": summary["oof"][head]["auc"],
                "rows": summary["oof"][head]["rows"],
            }
            for head in ("entry", "survival", "reversal")
        },
        "candles": candles,
        "equity": equity,
        "trades": trades,
        "episodes": episodes,
    }
    manifest = {
        "schema": "hype-1d-ma7-mlt-p6-v7-1-training-trade-path-v1",
        "generated_at": payload["generatedAt"],
        "renderer": Path(__file__).name,
        "holdout_read": False,
        "sources": {path.name: sha256(path) for path in sources},
        "window": payload["window"],
        "candles": len(candles),
        "ma7_points": sum(row["ma7"] is not None for row in candles),
        "full_probability_points": {
            head: sum(row[f"full{head.title()}"] is not None for row in candles)
            for head in ("entry", "survival", "reversal")
        },
        "confirmation_probability_points": {
            head: sum(row[f"ic{head.title()}"] is not None for row in candles)
            for head in ("entry", "survival", "reversal")
        },
        "equity_points": {key: len(value) for key, value in equity.items()},
        "trades_by_strategy": {
            key: sum(row["strategy"] == key for row in trades) for key in STRATEGIES
        },
        "episodes": len(episodes),
        "new_captures": sum(row["classification"] == "P6_NEW_CAPTURE" for row in episodes),
        "line_render_count": len(trades),
        "external_dependencies": 0,
    }
    return payload, manifest


HTML_TEMPLATE = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>P6 vs V7.1 训练期交易路径</title><style>
:root{color-scheme:dark;--bg:#0b0f12;--panel:#11171b;--panel2:#151d22;--line:#2a353b;--grid:#202a30;--text:#e8edef;--muted:#89979e;--up:#72b29b;--down:#c87878;--ma:#d7b869;--v7:#69b7c9;--p6:#e6a15c;--ic:#c58ad9;--accent:#d7b869}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.48 Geist,Satoshi,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.shell{max-width:1880px;margin:auto;padding:24px}.hero{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(360px,.85fr);gap:42px;align-items:end;padding:20px 0 24px;border-bottom:1px solid var(--line)}.eyebrow{color:var(--accent);font:600 11px/1.2 "Geist Mono",ui-monospace,monospace;letter-spacing:.16em}.hero h1{max-width:980px;margin:11px 0 10px;font-size:clamp(30px,4vw,58px);line-height:.98;letter-spacing:-.045em;font-weight:620}.subtitle,.status,.note{color:var(--muted)}.verdict{border-left:2px solid var(--down);padding:6px 0 6px 18px}.verdict b{display:block;font-size:18px;margin-bottom:6px}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);margin:28px 0 18px}.metric-group{background:var(--panel);padding:17px 18px}.metric-group h2{font-size:14px;margin:0 0 13px}.metric-grid{display:grid;grid-template-columns:1.1fr repeat(4,1fr)}.metric-grid>div{border-left:1px solid var(--line);padding:4px 12px}.metric-grid>div:first-child{border-left:0}.metric-grid span{display:block;color:var(--muted);font-size:11px}.metric-grid b{display:block;margin-top:6px;font:550 16px "Geist Mono",monospace}.p6c{color:var(--p6)}.v7c{color:var(--v7)}.icc{color:var(--ic)}.positive{color:var(--up)}.negative{color:var(--down)}.diagnosis{display:grid;grid-template-columns:1.25fr .75fr;gap:1px;background:var(--line);margin-bottom:18px}.diagnosis>div{background:var(--panel);padding:18px 20px}.diagnosis h2{font-size:15px;margin:0 0 9px}.diagnosis p{margin:0;color:#c5ced2}.equation{font:500 14px/1.65 "Geist Mono",monospace;color:var(--accent)}.toolbar{position:sticky;top:0;z-index:3;display:flex;flex-wrap:wrap;align-items:center;gap:8px 15px;padding:10px 12px;border:1px solid var(--line);background:rgba(17,23,27,.94);backdrop-filter:blur(14px)}button{color:var(--text);border:1px solid #394850;background:#172127;padding:7px 11px;cursor:pointer;font:12px "Geist Mono",monospace}button:hover{border-color:#64757e}label{color:var(--muted);user-select:none;font:12px "Geist Mono",monospace}input{vertical-align:-2px}.chart{border:1px solid var(--line);border-top:0;background:var(--panel);overflow:hidden}canvas{width:100%;display:block}#priceChart{height:610px;cursor:crosshair}#probChart{height:220px;border-top:1px solid var(--line)}#equityFull{height:230px;border-top:1px solid var(--line)}#equityIc{height:190px;border-top:1px solid var(--line)}.chart-note{padding:10px 12px;border:1px solid var(--line);border-top:0;color:var(--muted);font:11px "Geist Mono",monospace}.sections{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr);gap:18px;margin-top:24px}.table-wrap{max-height:680px;overflow:auto;border:1px solid var(--line);background:var(--panel)}.table-head{position:sticky;top:0;z-index:2;padding:14px 16px;background:var(--panel2);border-bottom:1px solid var(--line)}.table-head h2{font-size:14px;margin:0}.table-head p{color:var(--muted);font-size:11px;margin:4px 0 0}table{width:100%;border-collapse:collapse;min-width:900px;font:11px "Geist Mono",monospace}th,td{padding:9px 10px;border-bottom:1px solid var(--grid);text-align:right;white-space:nowrap}th{color:var(--muted);background:var(--panel2);position:sticky;top:64px;z-index:1;font-weight:500}th:nth-child(-n+4),td:nth-child(-n+4),th:last-child,td:last-child{text-align:left}tbody tr{cursor:pointer}tbody tr:hover,tbody tr.active{background:#1b272d}tbody tr.new{background:rgba(215,184,105,.07)}.badge{padding:2px 6px;border:1px solid #6f6040;color:#e3c67d}.tooltip{position:fixed;z-index:8;display:none;pointer-events:none;max-width:600px;padding:11px 13px;border:1px solid #4b5c64;background:rgba(11,15,18,.97);white-space:pre-line;font:11px/1.55 "Geist Mono",monospace}@media(max-width:1100px){.shell{padding:12px}.hero,.metrics,.diagnosis,.sections{grid-template-columns:1fr}.metric-grid{grid-template-columns:1fr 1fr}.metric-grid>div{border-left:0;border-top:1px solid var(--line);padding:9px}#priceChart{height:500px}}@media(max-width:720px){.hero h1{font-size:34px}.toolbar{position:static}}
</style></head><body><main class="shell"><section class="hero"><div><div class="eyebrow">HYPE · MA7 THREE-HEAD LIFECYCLE AUDIT</div><h1 id="title"></h1><div id="subtitle" class="subtitle"></div><div id="status" class="status"></div></div><div class="verdict"><b>结论：样本内超越，时间外推失败</b><span class="note">橙线会利用完整365日标签重新拟合；紫线只用前285日训练，再走最后80日，更接近模型真正面对未知行情时的表现。</span></div></section><section id="metrics" class="metrics"></section><section class="diagnosis"><div><h2>看图重点</h2><p id="diagnosisText"></p></div><div><h2>三个 OOF AUC</h2><div id="equation" class="equation"></div></div></section>
<div class="toolbar"><button id="reset">完整365日</button><button id="focusDev">前285日</button><button id="focusIc">最后80日内部确认</button><button id="focusExtra">下一笔P6补单</button><button id="focusIcLoss">下一笔内部确认亏损</button><button id="zoomIn">放大</button><button id="zoomOut">缩小</button><label><input id="showMa" type="checkbox" checked> MA7</label><label><input id="showTrends" type="checkbox" checked> 稳定趋势区间</label><label><input id="showLabels" type="checkbox" checked> 交易编号</label><label><input class="strategy-toggle" data-strategy="P6_FULL" type="checkbox" checked><span class="p6c"> P6完整拟合</span></label><label><input class="strategy-toggle" data-strategy="V7_FULL" type="checkbox" checked><span class="v7c"> V7.1</span></label><label><input class="strategy-toggle" data-strategy="P6_IC" type="checkbox" checked><span class="icc"> P6内部确认</span></label><label><input class="strategy-toggle" data-strategy="V7_IC" type="checkbox"> V7.1内部确认</label></div>
<div class="chart"><canvas id="priceChart"></canvas><canvas id="probChart"></canvas><canvas id="equityFull"></canvas><canvas id="equityIc"></canvas></div><div class="chart-note">▲/▼ 入场 · ● 退出 · 金线 MA7 · 橙虚线 P6完整365日重拟合 · 蓝实线 exact V7.1 · 紫点划线 P6最后80日内部确认 · 竖虚线为前285日/最后80日边界。概率图：橙=ENTRY、绿=SURVIVAL、紫=REVERSAL；淡线为完整重拟合，亮线为最后80日内部确认。滚轮缩放，拖动平移，双击复位。<br>后81日冻结窗口没有读取，也没有出现在本图。</div>
<section class="sections"><div class="table-wrap"><div class="table-head"><h2>完整训练拟合的趋势覆盖</h2><p>点击聚焦；黄色行表示 V7.1 完全漏掉、P6完整拟合补到。</p></div><table><thead><tr><th>趋势</th><th>方向</th><th>分类</th><th>区间</th><th>天数</th><th>P6覆盖</th><th>V7覆盖</th><th>覆盖差</th></tr></thead><tbody id="episodeRows"></tbody></table></div><div class="table-wrap"><div class="table-head"><h2>全部交易路径</h2><p>包括完整365日重拟合和最后80日内部确认；点击任意一笔聚焦。</p></div><table><thead><tr><th>口径</th><th>策略</th><th>交易</th><th>方向</th><th>入场</th><th>退出</th><th>持有</th><th>净收益</th><th>入场概率</th><th>来源/退出</th></tr></thead><tbody id="tradeRows"></tbody></table></div></section></main><div id="tooltip" class="tooltip"></div><script>
const DATA=__PAYLOAD__,DAY=86400000,C={bg:'#11171b',bg2:'#0e1417',grid:'#202a30',muted:'#89979e',up:'#72b29b',down:'#c87878',ma:'#d7b869',v7:'#69b7c9',p6:'#e6a15c',ic:'#c58ad9',survival:'#78b59b'};
const $=id=>document.getElementById(id),candles=DATA.candles,trades=DATA.trades,episodes=DATA.episodes,equity=DATA.equity,priceCanvas=$('priceChart'),probCanvas=$('probChart'),equityFull=$('equityFull'),equityIc=$('equityIc'),tooltip=$('tooltip');const domainMin=candles[0].t,domainMax=DATA.window.terminalT;let viewStart=domainMin,viewEnd=domainMax,hoverT=null,activeId=null,dragging=false,dragX=0,dragStart=0,extraIndex=0,lossIndex=0;
function activeStrategies(){return new Set([...document.querySelectorAll('.strategy-toggle:checked')].map(x=>x.dataset.strategy))}function signed(v,d=2){return(v>=0?'+':'')+Number(v).toFixed(d)}function fmt(v,d=3){return v==null?'—':Number(v).toFixed(d)}function pct(v,d=1){return fmt(v*100,d)+'%'}function day(t){return new Date(t).toISOString().slice(0,10)}function clamp(v,a,b){return Math.max(a,Math.min(b,v))}function setup(c){const r=c.getBoundingClientRect(),d=devicePixelRatio||1;c.width=Math.round(r.width*d);c.height=Math.round(r.height*d);const x=c.getContext('2d');x.setTransform(d,0,0,d,0,0);return{ctx:x,w:r.width,h:r.height}}function xs(t,l,w){return l+(t-viewStart)/(viewEnd-viewStart)*w}function visCandles(){return candles.filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY)}function visTrades(){const a=activeStrategies();return trades.filter(p=>a.has(p.strategy)&&p.exitT>=viewStart&&p.entryT<=viewEnd)}function visEpisodes(){return episodes.filter(p=>p.endT>=viewStart&&p.startT<=viewEnd)}
function ticks(lo,hi,n){const span=Math.max(1e-9,hi-lo),raw=span/n,p=10**Math.floor(Math.log10(raw)),q=raw/p,s=(q<1.5?1:q<3?2:q<7?5:10)*p,o=[];for(let v=Math.ceil(lo/s)*s;v<=hi+s*.1;v+=s)o.push(v);return o}function axes(ctx,m,pw,ph,lo,hi,y){ctx.font='11px "Geist Mono",monospace';for(const v of ticks(lo,hi,5)){const yy=y(v);ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(m.l,yy);ctx.lineTo(m.l+pw,yy);ctx.stroke();ctx.fillStyle=C.muted;ctx.textAlign='right';ctx.fillText(v.toFixed(Math.abs(v)<10?2:1),m.l-8,yy+4)}for(let i=0;i<=8;i++){const z=viewStart+(viewEnd-viewStart)*i/8,x=xs(z,m.l,pw);ctx.strokeStyle=C.grid;ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.fillStyle=C.muted;ctx.textAlign=i===0?'left':i===8?'right':'center';ctx.fillText(day(z),x,m.t+ph+18)}}function boundary(ctx,m,pw,ph,label){const t=DATA.window.boundaryT;if(t<viewStart||t>viewEnd)return;const x=xs(t,m.l,pw);ctx.strokeStyle='#d5dde0';ctx.globalAlpha=.7;ctx.setLineDash([6,5]);ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;if(label){ctx.fillStyle='#d5dde0';ctx.textAlign='center';ctx.fillText('前285日开发 ← | → 最后80日内部确认',x,m.t+13)}}function crosshair(ctx,m,pw,ph){if(hoverT==null)return;const x=xs(hoverT,m.l,pw);ctx.strokeStyle=C.muted;ctx.globalAlpha=.5;ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(x,m.t);ctx.lineTo(x,m.t+ph);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1}function line(ctx,vals,key,color,y,l,w,dash=[],width=1.8,offset=DAY/2){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.beginPath();let on=false;for(const p of vals){if(p[key]==null){on=false;continue}const x=xs(p.t+offset,l,w),yy=y(p[key]);on?ctx.lineTo(x,yy):(ctx.moveTo(x,yy),on=true)}ctx.stroke();ctx.setLineDash([])}function marker(ctx,x,y,side,entry,color,size){ctx.fillStyle=color;ctx.strokeStyle=C.bg2;ctx.lineWidth=1.2;ctx.beginPath();if(entry){if(side==='long'){ctx.moveTo(x,y-size);ctx.lineTo(x-size,y+size);ctx.lineTo(x+size,y+size)}else{ctx.moveTo(x,y+size);ctx.lineTo(x-size,y-size);ctx.lineTo(x+size,y-size)}ctx.closePath()}else ctx.arc(x,y,size-1,0,Math.PI*2);ctx.fill();ctx.stroke()}
function shadeEpisodes(ctx,m,pw,ph){if(!$('showTrends').checked)return;for(const e of visEpisodes()){const x1=xs(Math.max(e.startT,viewStart),m.l,pw),x2=xs(Math.min(e.endT,viewEnd),m.l,pw);ctx.fillStyle=e.side>0?'rgba(114,178,155,.075)':'rgba(200,120,120,.075)';ctx.fillRect(x1,m.t,Math.max(1,x2-x1),ph);if(e.classification==='P6_NEW_CAPTURE'){ctx.strokeStyle='rgba(215,184,105,.7)';ctx.setLineDash([3,4]);ctx.strokeRect(x1+.5,m.t+.5,Math.max(1,x2-x1-1),ph-1);ctx.setLineDash([])}}}
function drawPrice(){const{ctx,w,h}=setup(priceCanvas),m={l:72,r:25,t:24,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,vis=visCandles(),vtr=visTrades();ctx.fillStyle=C.bg;ctx.fillRect(0,0,w,h);if(!vis.length)return;let lo=Math.min(...vis.map(p=>p.l),...vtr.map(t=>Math.min(t.entry,t.exit))),hi=Math.max(...vis.map(p=>p.h),...vtr.map(t=>Math.max(t.entry,t.exit))),pad=(hi-lo)*.07||1;lo-=pad;hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y);shadeEpisodes(ctx,m,pw,ph);const bw=clamp(pw/Math.max(1,(viewEnd-viewStart)/DAY)*.62,1,13);for(const p of vis){const x=xs(p.t+DAY/2,m.l,pw),col=p.c>=p.o?C.up:C.down;ctx.strokeStyle=col;ctx.beginPath();ctx.moveTo(x,y(p.h));ctx.lineTo(x,y(p.l));ctx.stroke();ctx.fillStyle=col;ctx.fillRect(x-bw/2,y(Math.max(p.o,p.c)),bw,Math.max(1,y(Math.min(p.o,p.c))-y(Math.max(p.o,p.c))))}if($('showMa').checked)line(ctx,vis,'ma7',C.ma,y,m.l,pw,[],1.7);for(const t of vtr.sort((a,b)=>a.strategy.includes('V7')?-1:1)){const cfg=DATA.strategies[t.strategy],hot=t.id===activeId,x1=xs(t.entryT,m.l,pw),x2=xs(t.exitT,m.l,pw),y1=y(t.entry),y2=y(t.exit);ctx.strokeStyle=cfg.color;ctx.globalAlpha=hot?1:cfg.group==='confirmation'?.98:.76;ctx.lineWidth=hot?4:cfg.group==='confirmation'?3.1:t.strategy==='V7_FULL'?2.8:2.25;ctx.setLineDash(cfg.dash);ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.setLineDash([]);ctx.globalAlpha=1;marker(ctx,x1,y1,t.side,true,cfg.color,hot?9:7);marker(ctx,x2,y2,t.side,false,cfg.color,hot?9:7);if($('showLabels').checked||hot){ctx.fillStyle=cfg.color;ctx.textAlign='center';ctx.font='10px "Geist Mono",monospace';ctx.fillText(t.id,x2,y2+(cfg.group==='confirmation'?18:-11))}}boundary(ctx,m,pw,ph,true);crosshair(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign='left';ctx.fillText('PRICE · HYPEUSDT 1D · MA7 · 交易路径',m.l,15)}
function drawProbability(){const{ctx,w,h}=setup(probCanvas),m={l:72,r:25,t:18,b:28},pw=w-m.l-m.r,ph=h-m.t-m.b,vis=visCandles();ctx.fillStyle=C.bg2;ctx.fillRect(0,0,w,h);const y=v=>m.t+(1-v)*ph;for(const v of[0,.35,.5,.6,.65,.7,1]){const yy=y(v);ctx.strokeStyle=[.35,.6,.65,.7].includes(v)?'rgba(215,184,105,.28)':C.grid;ctx.setLineDash([.35,.6,.65,.7].includes(v)?[4,4]:[]);ctx.beginPath();ctx.moveTo(m.l,yy);ctx.lineTo(m.l+pw,yy);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle=C.muted;ctx.textAlign='right';ctx.fillText(v.toFixed(2),m.l-8,yy+4)}shadeEpisodes(ctx,m,pw,ph);line(ctx,vis,'fullEntry','rgba(230,161,92,.28)',y,m.l,pw,[],1);line(ctx,vis,'fullSurvival','rgba(120,181,155,.25)',y,m.l,pw,[],1);line(ctx,vis,'fullReversal','rgba(197,138,217,.23)',y,m.l,pw,[],1);line(ctx,vis,'icEntry',C.p6,y,m.l,pw,[6,4],2.1);line(ctx,vis,'icSurvival',C.survival,y,m.l,pw,[6,4],2.1);line(ctx,vis,'icReversal',C.ic,y,m.l,pw,[3,4],2.1);boundary(ctx,m,pw,ph,false);crosshair(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign='left';ctx.fillText('THREE HEAD PROBABILITIES · ENTRY .65 · SURVIVAL .60/.35 · REVERSAL .70',m.l,13)}
function drawEquity(canvas,keys,title){const{ctx,w,h}=setup(canvas),m={l:72,r:25,t:20,b:34},pw=w-m.l-m.r,ph=h-m.t-m.b,a=activeStrategies(),series=keys.filter(k=>a.has(k)).map(k=>({k,v:equity[k].filter(p=>p.t>=viewStart-DAY&&p.t<=viewEnd+DAY)})).filter(s=>s.v.length);ctx.fillStyle=C.bg2;ctx.fillRect(0,0,w,h);if(!series.length){ctx.fillStyle=C.muted;ctx.fillText(title+' · 请启用对应策略',m.l,15);return}let lo=Math.min(...series.flatMap(s=>s.v.map(p=>p.v))),hi=Math.max(...series.flatMap(s=>s.v.map(p=>p.v))),pad=(hi-lo)*.08||.02;lo=Math.max(0,lo-pad);hi+=pad;const y=v=>m.t+(hi-v)/(hi-lo)*ph;axes(ctx,m,pw,ph,lo,hi,y);for(const s of series){const cfg=DATA.strategies[s.k];ctx.strokeStyle=cfg.color;ctx.lineWidth=2.6;ctx.setLineDash(cfg.dash);ctx.beginPath();s.v.forEach((p,i)=>{const x=xs(p.t,m.l,pw);i?ctx.lineTo(x,y(p.v)):ctx.moveTo(x,y(p.v))});ctx.stroke();ctx.setLineDash([])}boundary(ctx,m,pw,ph,false);crosshair(ctx,m,pw,ph);ctx.fillStyle=C.muted;ctx.textAlign='left';ctx.fillText(title,m.l,13)}function draw(){drawPrice();drawProbability();drawEquity(equityFull,['P6_FULL','V7_FULL'],'EQUITY · 完整365日重拟合');drawEquity(equityIc,['P6_IC','V7_IC'],'EQUITY · 最后80日内部确认（独立从1开始）');for(const r of document.querySelectorAll('tbody tr'))r.classList.toggle('active',r.dataset.id===activeId)}
function reset(){viewStart=domainMin;viewEnd=domainMax;activeId=null;draw()}function focusRange(a,b){viewStart=Math.max(domainMin,a);viewEnd=Math.min(domainMax,b);activeId=null;draw()}function zoom(f,a=(viewStart+viewEnd)/2){const cur=viewEnd-viewStart,next=clamp(cur*f,8*DAY,domainMax-domainMin),q=(a-viewStart)/cur;viewStart=a-next*q;viewEnd=viewStart+next;if(viewStart<domainMin){viewEnd+=domainMin-viewStart;viewStart=domainMin}if(viewEnd>domainMax){viewStart-=viewEnd-domainMax;viewEnd=domainMax}draw()}function focusItem(item,aKey,bKey){const a=item[aKey],b=item[bKey],span=Math.max(18*DAY,(b-a)*2.8),mid=(a+b)/2;viewStart=clamp(mid-span/2,domainMin,Math.max(domainMin,domainMax-span));viewEnd=Math.min(domainMax,viewStart+span);activeId=item.id;draw();priceCanvas.scrollIntoView({behavior:'smooth',block:'center'})}function nextExtra(){const x=trades.filter(t=>t.strategy==='P6_FULL'&&t.source==='p6_supplemental');if(x.length)focusItem(x[extraIndex++%x.length],'entryT','exitT')}function nextIcLoss(){const x=trades.filter(t=>t.strategy==='P6_IC'&&t.netReturnPct<0);if(x.length)focusItem(x[lossIndex++%x.length],'entryT','exitT')}
function metricGroup(title,a,b,cls){const x=DATA.metrics[a],y=DATA.metrics[b];return`<div class="metric-group"><h2>${title}</h2><div class="metric-grid"><div><span>策略</span><b class="${cls}">${DATA.strategies[a].label}</b><span>${DATA.strategies[b].label}</span></div><div><span>收益 · MDD</span><b>${signed(x.net_return_pct)}% · ${signed(x.chronological_1h_mdd_pct)}%</b><span>${signed(y.net_return_pct)}% · ${signed(y.chronological_1h_mdd_pct)}%</span></div><div><span>交易 · 胜率</span><b>${x.trades} · ${pct(x.win_rate)}</b><span>${y.trades} · ${pct(y.win_rate)}</span></div><div><span>按天趋势覆盖</span><b>${pct(x.duration_weighted_capture)}</b><span>${pct(y.duration_weighted_capture)}</span></div><div><span>平均持有 · 成本</span><b>${fmt(x.average_hold_days,1)}d · ${fmt(x.cost_pct_initial,2)}%</b><span>${fmt(y.average_hold_days,1)}d · ${fmt(y.cost_pct_initial,2)}%</span></div></div></div>`}function renderMetrics(){$('metrics').innerHTML=metricGroup('完整365日重拟合：P6看似超越','P6_FULL','V7_FULL','p6c')+metricGroup('最后80日内部确认：P6真实失效','P6_IC','V7_IC','icc');$('diagnosisText').textContent='完整训练拟合中，P6比V7.1多覆盖35个趋势日、收益高214.07个百分点；但最后80日新增三笔补单全部亏损，趋势覆盖只多1天，净收益反而少12.36个百分点。橙色路径不能替代紫色时间外推路径。';$('equation').innerHTML=`ENTRY ${DATA.oof.entry.auc.toFixed(3)}<br>SURVIVAL ${DATA.oof.survival.auc.toFixed(3)}<br>REVERSAL ${DATA.oof.reversal.auc.toFixed(3)}<br>≈ 随机排序`}
function renderEpisodes(){const body=$('episodeRows');body.innerHTML=episodes.map(e=>{const label=e.classification==='P6_NEW_CAPTURE'?'<span class="badge">P6新识别</span>':e.classification==='P6_MORE'?'P6更多':e.classification==='V7_MORE'?'V7更多':'相同';return`<tr data-id="${e.id}" class="${e.classification==='P6_NEW_CAPTURE'?'new':''}"><td>${e.id}</td><td>${e.side>0?'多头':'空头'}</td><td>${label}</td><td>${day(e.startT)} → ${day(e.endT-DAY)}</td><td>${e.durationDays}</td><td class="p6c">${e.p6Days} · ${pct(e.p6Capture)}</td><td class="v7c">${e.v7Days} · ${pct(e.v7Capture)}</td><td class="${e.p6Capture>=e.v7Capture?'positive':'negative'}">${signed((e.p6Capture-e.v7Capture)*100,1)}pp</td></tr>`}).join('');for(const r of body.querySelectorAll('tr'))r.onclick=()=>focusItem(episodes.find(e=>e.id===r.dataset.id),'startT','endT')}
function renderTrades(){const body=$('tradeRows');body.innerHTML=trades.sort((a,b)=>a.entryT-b.entryT||a.strategy.localeCompare(b.strategy)).map(t=>`<tr data-id="${t.id}"><td>${t.segment==='full'?'完整拟合':'内部确认'}</td><td style="color:${DATA.strategies[t.strategy].color}">${t.strategyLabel}</td><td>${t.id}</td><td>${t.side==='long'?'做多':'做空'}</td><td>${day(t.entryT)} · ${fmt(t.entry)}</td><td>${day(t.exitT)} · ${fmt(t.exit)}</td><td>${t.barsHeld}d</td><td class="${t.netReturnPct>=0?'positive':'negative'}">${signed(t.netReturnPct)}%</td><td>${fmt(t.entryProbability,3)}</td><td>${t.source||'V7.1 core'} · ${t.exitReason}</td></tr>`).join('');for(const r of body.querySelectorAll('tr'))r.onclick=()=>focusItem(trades.find(t=>t.id===r.dataset.id),'entryT','exitT')}
function pointerMove(e){if(dragging){const r=priceCanvas.getBoundingClientRect(),span=viewEnd-viewStart,shift=-(e.clientX-dragX)/Math.max(1,r.width-97)*span;viewStart=clamp(dragStart+shift,domainMin,domainMax-span);viewEnd=viewStart+span;draw();return}const r=priceCanvas.getBoundingClientRect(),q=clamp((e.clientX-r.left-72)/Math.max(1,r.width-97),0,1);hoverT=viewStart+q*(viewEnd-viewStart);const c=candles.reduce((a,b)=>Math.abs(b.t+DAY/2-hoverT)<Math.abs(a.t+DAY/2-hoverT)?b:a,candles[0]),near=trades.filter(t=>activeStrategies().has(t.strategy)&&Math.min(Math.abs(t.entryT-hoverT),Math.abs(t.exitT-hoverT))<DAY*.7),ep=episodes.find(x=>x.startT<=c.t&&x.endT>c.t);let s=`${day(c.t)} UTC\nO ${fmt(c.o)} H ${fmt(c.h)} L ${fmt(c.l)} C ${fmt(c.c)}\nMA7 ${fmt(c.ma7)} · slope/ATR ${signed(c.slopeAtr,4)}\n完整拟合 E/S/R ${fmt(c.fullEntry,3)} / ${fmt(c.fullSurvival,3)} / ${fmt(c.fullReversal,3)}\n内部确认 E/S/R ${fmt(c.icEntry,3)} / ${fmt(c.icSurvival,3)} / ${fmt(c.icReversal,3)}`;if(ep)s+=`\n${ep.id} ${ep.side>0?'稳定多头':'稳定空头'} · P6 ${pct(ep.p6Capture)} / V7 ${pct(ep.v7Capture)}`;for(const t of near)s+=`\n${t.id} ${t.strategyLabel} ${t.side==='long'?'多':'空'} · ${signed(t.netReturnPct)}%`;tooltip.textContent=s;tooltip.style.display='block';tooltip.style.left=Math.min(innerWidth-620,e.clientX+15)+'px';tooltip.style.top=Math.min(innerHeight-250,e.clientY+15)+'px';draw()}
$('title').textContent=DATA.title;$('subtitle').textContent=DATA.subtitle;$('status').textContent=`${DATA.status} · ${DATA.window.start.slice(0,10)} → ${DATA.window.terminal.slice(0,10)}`;$('reset').onclick=reset;$('focusDev').onclick=()=>focusRange(domainMin,DATA.window.boundaryT);$('focusIc').onclick=()=>focusRange(DATA.window.boundaryT,domainMax);$('focusExtra').onclick=nextExtra;$('focusIcLoss').onclick=nextIcLoss;$('zoomIn').onclick=()=>zoom(.65);$('zoomOut').onclick=()=>zoom(1.55);$('showMa').onchange=draw;$('showTrends').onchange=draw;$('showLabels').onchange=draw;for(const x of document.querySelectorAll('.strategy-toggle'))x.onchange=draw;priceCanvas.onwheel=e=>{e.preventDefault();const r=priceCanvas.getBoundingClientRect(),q=clamp((e.clientX-r.left-72)/Math.max(1,r.width-97),0,1);zoom(e.deltaY>0?1.2:.82,viewStart+q*(viewEnd-viewStart))};priceCanvas.onpointerdown=e=>{dragging=true;dragX=e.clientX;dragStart=viewStart;priceCanvas.setPointerCapture(e.pointerId)};priceCanvas.onpointerup=e=>{dragging=false;if(priceCanvas.hasPointerCapture(e.pointerId))priceCanvas.releasePointerCapture(e.pointerId)};priceCanvas.onpointermove=pointerMove;priceCanvas.onpointerleave=()=>{if(!dragging){hoverT=null;tooltip.style.display='none';draw()}};priceCanvas.ondblclick=reset;window.onresize=draw;renderMetrics();renderEpisodes();renderTrades();draw();
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
        "focusIc",
        "nextExtra",
        "nextIcLoss",
        "完整365日",
        "最后80日内部确认",
        "MA7",
        "后81日冻结窗口没有读取",
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
