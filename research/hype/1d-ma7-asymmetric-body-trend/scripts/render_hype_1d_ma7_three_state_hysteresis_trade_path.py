from __future__ import annotations

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
    / "scripts/audit_hype_1d_ma7_abt_three_state_hysteresis.py"
)
AUDIT_SHA256 = (
    "7d6bb8804d7d155f34248c45a836d656abe3e05f33cb8cafeda5ab57444de0c7"
)
TEMPLATE_PATH = (
    FAMILY_DIR / "scripts/render_hype_1d_ma7_separated_trade_path.py"
)
TEMPLATE_SHA256 = (
    "549eeeac7c1e4a618ac1d2e607b909e2dd059c22edda2d68c9a7b4c6553ffcd4"
)
OUTPUT_PATH = (
    ARTIFACT_DIR
    / "hype_1d_ma7_three_state_hysteresis_trade_path_2026-08-07.html"
)
EXPECTED_EQUITY = 1.207906719005383
EXPECTED_TRADES = 32


def load_pinned(path: Path, expected: str, name: str) -> Any:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(
            f"{path.name} drift: expected {expected}, got {actual}"
        )
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
    audit = load_pinned(
        AUDIT_PATH,
        AUDIT_SHA256,
        "hype_three_state_chart_audit",
    )
    formation = audit.load_pinned(
        audit.FORMATION_PATH,
        audit.FORMATION_SHA256,
        "hype_three_state_chart_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_three_state_chart_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_three_state_chart_base",
    )
    parent = base.load_parent()
    market_engine = parent.load_engine()
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
        parent,
        hourly,
        hourly_quality,
        funding,
        funding_quality,
        phase_hours=0,
    )
    features = engine.build_features(book, hourly, funding)
    result = audit.hysteresis_backtest(
        engine,
        book,
        features,
        audit.TRI_CONFIG,
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
        raise RuntimeError("three-state chart anchor drift")

    candles = []
    for index, ts in enumerate(book.ts):
        ma = finite_or_none(features.ma7[index])
        atr = finite_or_none(features.atr7[index])
        if ma is None or atr is None:
            upper = lower = neutral_upper = neutral_lower = None
        else:
            upper = ma + audit.TRI_CONFIG.outer_atr * atr
            lower = ma - audit.TRI_CONFIG.outer_atr * atr
            neutral_upper = ma + audit.TRI_CONFIG.neutral_atr * atr
            neutral_lower = ma - audit.TRI_CONFIG.neutral_atr * atr
        candles.append(
            {
                "t": timestamp_ms(ts),
                "o": float(book.open[index]),
                "h": float(book.high[index]),
                "l": float(book.low[index]),
                "c": float(book.close[index]),
                "ma": ma,
                "upper": upper,
                "lower": lower,
                "neutralUpper": neutral_upper,
                "neutralLower": neutral_lower,
            }
        )

    reason_labels = {
        "lower_boundary_flip": "下边界直接反手",
        "upper_boundary_flip": "上边界直接反手",
        "neutral_timeout_exit": "连续3日震荡转空仓",
        "terminal_flatten": "样本终点平仓",
    }
    trades = []
    for index, row in enumerate(result.trades):
        side = str(row["side"])
        trades.append(
            {
                "id": f"{'L' if side == 'long' else 'S'}{index + 1:02d}",
                "side": side,
                "entryT": timestamp_ms(row["entry_ts"]),
                "exitT": timestamp_ms(row["exit_ts"]),
                "entryTs": str(row["entry_ts"]),
                "exitTs": str(row["exit_ts"]),
                "entry": float(row["entry_price"]),
                "exit": float(row["exit_price"]),
                "bars": int(row["bars_held"]),
                "reason": reason_labels.get(
                    str(row["exit_reason"]),
                    str(row["exit_reason"]),
                ),
                "returnPct": float(row["net_return"]) * 100.0,
                "netPnl": float(row["net_pnl"]),
                "entrySource": str(row["entry_reason"]),
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
        "title": "HYPE 日线 MA7 三状态迟滞：完整交易路径",
        "subtitle": (
            "D=0.75 ATR7 · neutral=±0.25 ATR7×3日 · UTC 日 K · "
            "1x · diagnostic-only · 每笔入场与出场同色连接"
        ),
        "generatedAt": datetime.now(UTC).isoformat(),
        "candles": candles,
        "trades": trades,
        "equity": equity,
        "metrics": {
            "returnPct": metrics["net_return_pct"],
            "mddPct": metrics["max_drawdown_pct"],
            "sharpe": metrics["sharpe"],
            "profitFactor": metrics["profit_factor"],
            "trades": metrics["closed_trades"],
            "longTrades": metrics["long_trades"],
            "shortTrades": metrics["short_trades"],
            "exposurePct": metrics["exposure_pct"],
        },
    }


def extended_template(template: str) -> str:
    template = template.replace(
        "<title>HYPE MA7 完整交易路径</title>",
        "<title>HYPE MA7 三状态迟滞交易路径</title>",
    )
    template = template.replace(
        '<label><input id="showMa" type="checkbox" checked> '
        '<span class="swatch" style="background:var(--ma)"></span>MA7</label>',
        '<label><input id="showMa" type="checkbox" checked> '
        '<span class="swatch" style="background:var(--ma)"></span>MA7</label>'
        '<label><input id="showBands" type="checkbox" checked> '
        '<span class="swatch" style="background:#9b7bff"></span>'
        '±0.75 外边界 / ±0.25 震荡区</label>',
    )
    template = template.replace(
        'up: "#2dd4a7", down: "#f05c70", ma: "#f6c85f",',
        'up: "#2dd4a7", down: "#f05c70", ma: "#f6c85f", '
        'outer: "#9b7bff", neutral: "#4d667a",',
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
    new_ma = old_ma + """\

  if (document.getElementById("showBands").checked) {
    const drawBand = (field, color, dash, width) => {
      ctx.strokeStyle = color; ctx.lineWidth = width; ctx.setLineDash(dash);
      ctx.beginPath(); let started = false;
      for (const c of vis) {
        if (c[field] == null) { started = false; continue; }
        const x = xScale(c.t + DAY / 2, margin.left, pw);
        if (!started) { ctx.moveTo(x, y(c[field])); started = true; }
        else ctx.lineTo(x, y(c[field]));
      }
      ctx.stroke(); ctx.setLineDash([]);
    };
    drawBand("upper", COLORS.outer, [7, 4], 1.25);
    drawBand("lower", COLORS.outer, [7, 4], 1.25);
    drawBand("neutralUpper", COLORS.neutral, [2, 3], 1);
    drawBand("neutralLower", COLORS.neutral, [2, 3], 1);
  }
"""
    if old_ma not in template:
        raise RuntimeError("template MA drawing block not found")
    template = template.replace(old_ma, new_ma, 1)
    template = template.replace(
        '["交易", `${m.trades}（${m.longTrades}L / ${m.shortTrades}S）`]',
        '["交易", `${m.trades}（${m.longTrades}L / ${m.shortTrades}S）`],\n'
        '  ["暴露率", m.exposurePct.toFixed(2) + "%"]',
    )
    template = template.replace(
        'document.getElementById("showMa").onchange = draw;',
        'document.getElementById("showMa").onchange = draw;\n'
        'document.getElementById("showBands").onchange = draw;',
    )
    old_tooltip = (
        'let text = `${dateOnly(candle.t)} UTC\\nO ${fmt(candle.o)}  '
        'H ${fmt(candle.h)}  L ${fmt(candle.l)}  C ${fmt(candle.c)}\\n'
        'MA7 ${candle.ma == null ? "—" : fmt(candle.ma)}  '
        'Equity ${fmt(eq.v, 4)}`;'
    )
    new_tooltip = (
        'let text = `${dateOnly(candle.t)} UTC\\nO ${fmt(candle.o)}  '
        'H ${fmt(candle.h)}  L ${fmt(candle.l)}  C ${fmt(candle.c)}\\n'
        'MA7 ${candle.ma == null ? "—" : fmt(candle.ma)}  '
        'Equity ${fmt(eq.v, 4)}\\n'
        '外边界 ${candle.lower == null ? "—" : fmt(candle.lower)} — '
        '${candle.upper == null ? "—" : fmt(candle.upper)}\\n'
        '震荡区 ${candle.neutralLower == null ? "—" : '
        'fmt(candle.neutralLower)} — '
        '${candle.neutralUpper == null ? "—" : '
        'fmt(candle.neutralUpper)}`;'
    )
    if old_tooltip not in template:
        raise RuntimeError("template tooltip block not found")
    return template.replace(old_tooltip, new_tooltip, 1)


def main() -> None:
    template = load_pinned(
        TEMPLATE_PATH,
        TEMPLATE_SHA256,
        "hype_three_state_chart_template",
    )
    payload = build_payload()
    if len(payload["trades"]) != EXPECTED_TRADES:
        raise RuntimeError(
            f"chart expected {EXPECTED_TRADES} trades, "
            f"got {len(payload['trades'])}"
        )
    for trade in payload["trades"]:
        if trade["entryT"] > trade["exitT"]:
            raise RuntimeError(f"trade timestamp order invalid: {trade['id']}")
    html = extended_template(template.HTML_TEMPLATE).replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    if "__PAYLOAD__" in html:
        raise RuntimeError("chart payload replacement failed")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH.relative_to(ROOT)),
                "candles": len(payload["candles"]),
                "trades": len(payload["trades"]),
                "equity_points": len(payload["equity"]),
                "all_trades_connected": True,
                "outer_and_neutral_bands": True,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
