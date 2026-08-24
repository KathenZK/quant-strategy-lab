from __future__ import annotations

from dataclasses import replace
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
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
AUDIT_PATH = (
    FAMILY_DIR
    / "scripts/audit_hype_1d_ma7_abt_v4_pending_quality_handoff.py"
)
AUDIT_SHA256 = (
    "da473498e9b381eee48c3dc40c0f27206da15582cb11884a7e9cdb4d4f8bfcc8"
)
TEMPLATE_PATH = (
    FAMILY_DIR / "scripts/render_hype_1d_ma7_separated_trade_path.py"
)
TEMPLATE_SHA256 = (
    "549eeeac7c1e4a618ac1d2e607b909e2dd059c22edda2d68c9a7b4c6553ffcd4"
)
OUTPUT_PATH = (
    ARTIFACT_DIR
    / "hype_1d_ma7_abt_v4_pending_quality_handoff_trade_path_2026-08-07.html"
)
EXPECTED_EQUITY = 5.262116792267788
EXPECTED_TRADES = 20


def load_pinned(path: Path, expected: str, name: str) -> Any:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"{path.name} drift: expected {expected}, got {actual}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def timestamp_ms(value: Any) -> int:
    return int(pd.Timestamp(value).timestamp() * 1000)


def finite_or_none(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def build_payload() -> dict[str, Any]:
    audit = load_pinned(AUDIT_PATH, AUDIT_SHA256, "hype_pending_chart_audit")
    parent = audit.load_pinned(
        audit.PENDING_PATH,
        audit.PENDING_SHA256,
        "hype_pending_chart_parent",
    )
    shared = parent.load_pinned(
        parent.TIMING_PATH,
        parent.TIMING_SHA256,
        "hype_pending_chart_shared",
    )
    v4 = shared.load_pinned(
        shared.V4_FORMATION_PATH,
        shared.V4_FORMATION_SHA256,
        "hype_pending_chart_v4",
    )
    formation = v4.load_pinned(
        v4.FORMATION_PATH,
        v4.FORMATION_SHA256,
        "hype_pending_chart_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_pending_chart_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_pending_chart_base",
    )
    selected = formation.read_pinned_json(
        formation.SUMMARY_PATH,
        formation.SUMMARY_SHA256,
    )["historically_profitable_all_checks"][0]
    long_config = engine.Config(**selected["long_config"])
    short_config = replace(
        engine.Config(**selected["short_config"]),
        exit_buffer_atr=0.75,
    )
    backtest = audit.build_handoff_backtest(v4, formation, engine)
    signal = audit.QualityPendingSignal(
        parent,
        engine,
        cap_atr=audit.CAP_ATR,
    )
    audit.install_signal(backtest, signal, engine, handoff=True)
    control_backtest = v4.build_filtered_backtest(
        formation,
        engine,
        v4.MA_ONLY,
    )
    market_parent = base.load_parent()
    market_engine = market_parent.load_engine()
    hourly, hourly_quality = market_engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = market_engine.load_and_audit_funding(ROOT)
    hourly["ts"] = pd.to_datetime(hourly["ts"], utc=True)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    hourly = hourly.loc[
        hourly["ts"] <= formation.HISTORICAL_HOUR_CUTOFF
    ].copy()
    funding = funding.loc[
        funding["ts"] <= formation.HISTORICAL_HOUR_CUTOFF
    ].copy()
    book = base.build_book(
        market_parent,
        hourly,
        hourly_quality,
        funding,
        funding_quality,
        phase_hours=0,
    )
    features = engine.build_features(book, hourly, funding)
    signal.reset()
    result = backtest(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=0,
        terminal_index=book.count,
        slippage=engine.BASE_SLIPPAGE,
        retain=True,
    )
    events = shared.attach_timestamps(list(signal.events), book)
    control = control_backtest(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=0,
        terminal_index=book.count,
        slippage=engine.BASE_SLIPPAGE,
        retain=True,
    )
    if not math.isclose(
        result.metrics["equity_multiple"],
        EXPECTED_EQUITY,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("pending quality chart anchor drift")
    trades_frame = v4.annotate(formation, result)
    control_frame = v4.annotate(formation, control)
    delayed_entry_times = {
        pd.Timestamp(event["signal_ts"]) + pd.Timedelta(days=1)
        for event in events
        if event["event"] == "confirm_pending_entry"
        and bool(event.get("delayed"))
    }
    handoff_entry_times = {
        pd.Timestamp(event["signal_ts"]) + pd.Timedelta(days=1)
        for event in events
        if event["event"] == "delayed_position_opposite_handoff"
    }
    control_keys = {
        (str(row["side"]), str(row["entry_ts"]))
        for _, row in control_frame.iterrows()
    }
    candles = []
    for index, ts in enumerate(book.ts):
        ma = finite_or_none(features.ma7[index])
        atr = finite_or_none(features.atr7[index])
        lower_entry = lower_cap = None
        if ma is not None and atr is not None:
            lower_entry = ma - short_config.entry_buffer_atr * atr
            lower_cap = ma - audit.CAP_ATR * atr
        candles.append(
            {
                "t": timestamp_ms(ts),
                "o": float(book.open[index]),
                "h": float(book.high[index]),
                "l": float(book.low[index]),
                "c": float(book.close[index]),
                "ma": ma,
                "lowerEntry": lower_entry,
                "lowerCap": lower_cap,
            }
        )
    trades = []
    for index, row in trades_frame.iterrows():
        side = str(row["side"])
        entry_ts = pd.Timestamp(row["entry_ts"])
        delayed = entry_ts in delayed_entry_times
        handoff = entry_ts in handoff_entry_times
        forced = row["entry_source"] == "forced_trailing_stop_reversal"
        if delayed:
            prefix = "P-S"
            source = "1日pending确认"
        elif handoff:
            prefix = "H-L" if side == "long" else "H-S"
            source = "原V4 opposite reclaim同open交接"
        elif forced:
            prefix = "R-S"
            source = "V4 trailing反手"
        else:
            prefix = "L" if side == "long" else "S"
            source = "V4原路径"
        key = (side, str(row["entry_ts"]))
        delta = "新增" if key not in control_keys else "V4共享"
        trades.append(
            {
                "id": f"{prefix}{index + 1:02d}",
                "side": side,
                "entryT": timestamp_ms(row["entry_ts"]),
                "exitT": timestamp_ms(row["exit_ts"]),
                "entryTs": str(row["entry_ts"]),
                "exitTs": str(row["exit_ts"]),
                "entry": float(row["entry_price"]),
                "exit": float(row["exit_price"]),
                "bars": int(row["bars_held"]),
                "reason": (
                    f"{source} · {delta} · {row['exit_reason']}"
                ),
                "returnPct": float(row["net_return"]) * 100.0,
                "netPnl": float(row["net_pnl"]),
                "entrySource": source,
            }
        )
    pending_events = []
    event_labels = {
        "confirm_pending_entry": "接受1日pending short",
        "reject_overextended_pending": "超过0.75 ATR，拒绝追空",
        "delayed_position_opposite_handoff": "平short并交接V4 long",
    }
    trade_by_entry = {
        pd.Timestamp(row["entry_ts"]): row
        for _, row in trades_frame.iterrows()
    }
    for event in events:
        kind = event["event"]
        if kind not in event_labels:
            continue
        event_ts = pd.Timestamp(event["signal_ts"])
        marker_ts = event_ts
        price = event.get("close")
        if kind == "delayed_position_opposite_handoff":
            marker_ts = event_ts + pd.Timedelta(days=1)
            trade = trade_by_entry.get(marker_ts)
            if trade is None:
                raise RuntimeError("handoff chart trade missing")
            price = float(trade["entry_price"])
        pending_events.append(
            {
                "t": timestamp_ms(marker_ts),
                "price": float(price),
                "kind": kind,
                "label": event_labels[kind],
                "distanceAtr": event.get("distance_atr"),
            }
        )
    equity = [
        {
            "t": timestamp_ms(row["ts"]),
            "v": float(row["close_equity"]),
            "position": int(row["position"]),
            "action": str(row["action"]),
        }
        for row in result.path
    ]
    metrics = result.metrics
    return {
        "title": "HYPE V4 局部修复：有限pending + anti-chase + handoff",
        "subtitle": (
            "short fresh reclaim最多等待1日 · 延迟确认距离MA7不超过0.75×ATR7 "
            "· 仅原V4 opposite reclaim允许同open交接 · post-reveal"
        ),
        "generatedAt": datetime.now(UTC).isoformat(),
        "candles": candles,
        "trades": trades,
        "pendingEvents": pending_events,
        "equity": equity,
        "metrics": {
            "returnPct": metrics["net_return_pct"],
            "mddPct": metrics["max_drawdown_pct"],
            "sharpe": metrics["sharpe"],
            "profitFactor": metrics["profit_factor"],
            "trades": metrics["closed_trades"],
            "longTrades": metrics["long_trades"],
            "shortTrades": metrics["short_trades"],
        },
    }


def local_repair_template(template: str) -> str:
    output = template.replace(
        "<title>HYPE MA7 完整交易路径</title>",
        "<title>HYPE V4 局部修复交易路径</title>",
    )
    ma_label = (
        '<label><input id="showMa" type="checkbox" checked> '
        '<span class="swatch" style="background:var(--ma)"></span>MA7</label>'
    )
    additions = (
        '<label><input id="showPendingZone" type="checkbox" checked> '
        '<span class="swatch" style="background:#9b7bff"></span>'
        'short pending 0.25–0.75 ATR7区</label>'
        '<label><input id="showPendingEvents" type="checkbox" checked> '
        '<span class="swatch" style="background:#42a5f5"></span>'
        'pending接受 / 拒绝 / handoff</label>'
    )
    if ma_label not in output:
        raise RuntimeError("template MA label missing")
    output = output.replace(ma_label, ma_label + additions, 1)
    output = output.replace(
        'up: "#2dd4a7", down: "#f05c70", ma: "#f6c85f",',
        (
            'up: "#2dd4a7", down: "#f05c70", ma: "#f6c85f", '
            'pending: "#42a5f5", reject: "#ff9f43", handoff: "#b5f56b",'
        ),
        1,
    )
    output = output.replace(
        "const equity = DATA.equity;",
        "const equity = DATA.equity;\n"
        "const pendingEvents = DATA.pendingEvents || [];",
        1,
    )
    old_ma = """\
  if (document.getElementById("showMa").checked) {
    ctx.strokeStyle = COLORS.ma; ctx.lineWidth = 1.6; ctx.beginPath();
    let started = false;
    for (const c of vis) {
      if (c.ma == null) { started = false; continue; }
      const x = xScale(c.t + DAY / 2, margin.left, pw);
      if (!started) { ctx.moveTo(x, y(c.ma)); started = true; }
      else ctx.lineTo(x, y(c.ma));
    }
    ctx.stroke();
  }
"""
    pending_draw = old_ma + """\

  if (document.getElementById("showPendingZone").checked) {
    const drawPendingLine = (field, dash) => {
      ctx.strokeStyle = "#9b7bff"; ctx.globalAlpha = .8;
      ctx.lineWidth = 1.1; ctx.setLineDash(dash); ctx.beginPath();
      let started = false;
      for (const c of vis) {
        if (c[field] == null) { started = false; continue; }
        const x = xScale(c.t + DAY / 2, margin.left, pw);
        if (!started) { ctx.moveTo(x, y(c[field])); started = true; }
        else ctx.lineTo(x, y(c[field]));
      }
      ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
    };
    drawPendingLine("lowerEntry", [3, 3]);
    drawPendingLine("lowerCap", [8, 4]);
  }

  if (document.getElementById("showPendingEvents").checked) {
    const visibleEvents = pendingEvents.filter(
      e => e.t >= viewStart - DAY && e.t <= viewEnd + DAY
    );
    for (const e of visibleEvents) {
      const x = xScale(e.t + DAY / 2, margin.left, pw);
      const py = y(e.price);
      const color = e.kind === "reject_overextended_pending"
        ? COLORS.reject
        : e.kind === "delayed_position_opposite_handoff"
          ? COLORS.handoff
          : COLORS.pending;
      ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 2;
      if (e.kind === "reject_overextended_pending") {
        ctx.beginPath();
        ctx.moveTo(x - 5, py - 5); ctx.lineTo(x + 5, py + 5);
        ctx.moveTo(x + 5, py - 5); ctx.lineTo(x - 5, py + 5);
        ctx.stroke();
      } else {
        ctx.beginPath(); ctx.arc(x, py, 5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.font = "10px ui-monospace"; ctx.textAlign = "left";
      ctx.fillText(e.label, x + 8, py - 7);
    }
  }
"""
    if old_ma not in output:
        raise RuntimeError("template MA drawing block missing")
    output = output.replace(old_ma, pending_draw, 1)
    output = output.replace(
        'document.getElementById("showMa").onchange = draw;',
        'document.getElementById("showMa").onchange = draw;\n'
        'document.getElementById("showPendingZone").onchange = draw;\n'
        'document.getElementById("showPendingEvents").onchange = draw;',
        1,
    )
    tooltip_anchor = (
        "  const nearby = trades.filter(t => Math.min(Math.abs(t.entryT - hoverT), "
        "Math.abs(t.exitT - hoverT)) < DAY * .65);\n"
    )
    tooltip_insert = tooltip_anchor + (
        "  const nearbyPending = pendingEvents.filter("
        "e => Math.abs(e.t + DAY/2 - hoverT) < DAY * .65);\n"
    )
    if tooltip_anchor not in output:
        raise RuntimeError("template tooltip pending anchor missing")
    output = output.replace(tooltip_anchor, tooltip_insert, 1)
    trade_tooltip = """\
  for (const t of nearby) {
    text += `\\n${t.id} ${t.side === "long" ? "多" : "空"} ${signed(t.returnPct)}% · ${t.reason}`;
  }
"""
    event_tooltip = trade_tooltip + """\
  for (const e of nearbyPending) {
    text += `\\n事件 · ${e.label}${e.distanceAtr == null ? "" : " · " + fmt(e.distanceAtr, 3) + " ATR"}`;
  }
"""
    if trade_tooltip not in output:
        raise RuntimeError("template trade tooltip block missing")
    return output.replace(trade_tooltip, event_tooltip, 1)


def main() -> None:
    template = load_pinned(
        TEMPLATE_PATH,
        TEMPLATE_SHA256,
        "hype_pending_chart_template",
    )
    payload = build_payload()
    if len(payload["trades"]) != EXPECTED_TRADES:
        raise RuntimeError(
            f"expected {EXPECTED_TRADES} chart trades, "
            f"got {len(payload['trades'])}"
        )
    for trade in payload["trades"]:
        if trade["entryT"] > trade["exitT"]:
            raise RuntimeError(f"trade timestamp order invalid: {trade['id']}")
    html = local_repair_template(template.HTML_TEMPLATE).replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    if "__PAYLOAD__" in html:
        raise RuntimeError("chart payload replacement failed")
    if "ctx.lineTo(x2, y2)" not in html:
        raise RuntimeError("trade connection renderer missing")
    if "showPendingEvents" not in html or 'drawPendingLine("lowerCap"' not in html:
        raise RuntimeError("pending overlay renderer missing")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH.relative_to(ROOT)),
                "candles": len(payload["candles"]),
                "trades": len(payload["trades"]),
                "pending_events": len(payload["pendingEvents"]),
                "equity_points": len(payload["equity"]),
                "all_trades_connected": True,
                "pending_zone_and_events": True,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
