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
    / "scripts/audit_hype_1d_ma7_abt_v4_band_state_machine.py"
)
AUDIT_SHA256 = (
    "5d6e0553e57f8747e0c60b30652ef8609192781020bc6fb4f68f51d53ff7c0ae"
)
HELPER_PATH = (
    FAMILY_DIR
    / "scripts/render_hype_1d_ma7_three_state_hysteresis_trade_path.py"
)
HELPER_SHA256 = (
    "dca5cda6d88f876f646765993a2a0c5055298cda249f928efe32d23a0aca06ae"
)
TEMPLATE_PATH = (
    FAMILY_DIR / "scripts/render_hype_1d_ma7_separated_trade_path.py"
)
TEMPLATE_SHA256 = (
    "549eeeac7c1e4a618ac1d2e607b909e2dd059c22edda2d68c9a7b4c6553ffcd4"
)
OUTPUT_PATH = (
    ARTIFACT_DIR
    / "hype_1d_ma7_abt_v4_band_state_machine_trade_path_2026-08-07.html"
)
EXPECTED_EQUITY = 0.7359982012441026
EXPECTED_TRADES = 28


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
    audit = load_pinned(AUDIT_PATH, AUDIT_SHA256, "hype_band_chart_audit")
    shared = audit.load_pinned(
        audit.TIMING_PATH,
        audit.TIMING_SHA256,
        "hype_band_chart_shared",
    )
    v4 = shared.load_pinned(
        shared.V4_FORMATION_PATH,
        shared.V4_FORMATION_SHA256,
        "hype_band_chart_v4",
    )
    formation = v4.load_pinned(
        v4.FORMATION_PATH,
        v4.FORMATION_SHA256,
        "hype_band_chart_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_band_chart_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_band_chart_base",
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
    candidate_backtest = audit.build_band_backtest(engine)
    control_backtest = v4.build_filtered_backtest(
        formation,
        engine,
        v4.MA_ONLY,
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
    result = candidate_backtest(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=0,
        terminal_index=book.count,
        slippage=engine.BASE_SLIPPAGE,
        retain=True,
    )
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
        raise RuntimeError("band state chart anchor drift")
    trades_frame = audit.annotate_state_trades(formation, result)
    control_frame = v4.annotate(formation, control)
    control_by_key = {
        (str(row["side"]), str(row["entry_ts"])): row
        for _, row in control_frame.iterrows()
    }
    path_by_day = {
        pd.Timestamp(row["ts"]).floor("1D"): row
        for row in result.path
        if row["action"] != "terminal"
    }
    cooldown_by_day: dict[pd.Timestamp, str] = {}
    for _, row in trades_frame.iterrows():
        if row["exit_reason"] != "protective_stop":
            continue
        days = (
            long_config.cooldown_days
            if row["side"] == "long"
            else short_config.cooldown_days
        )
        exit_day = pd.Timestamp(row["exit_ts"]).floor("1D")
        for offset in range(1, days + 1):
            day = exit_day + pd.Timedelta(days=offset)
            cooldown_by_day[day] = (
                f"{row['side'].upper()} cooldown "
                f"{days - offset + 1}/{days}"
            )
    candles = []
    for index, ts in enumerate(book.ts):
        day = pd.Timestamp(ts).floor("1D")
        ma = finite_or_none(features.ma7[index])
        atr = finite_or_none(features.atr7[index])
        upper = lower = None
        if ma is not None and atr is not None:
            upper = ma + audit.BAND_ATR * atr
            lower = ma - audit.BAND_ATR * atr
        path_row = path_by_day.get(day)
        position = int(path_row["position"]) if path_row is not None else 0
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
                "neutralUpper": None,
                "neutralLower": None,
                "position": position,
                "state": (
                    "LONG" if position > 0 else "SHORT" if position < 0 else "FLAT"
                ),
                "cooldown": cooldown_by_day.get(day, ""),
                "action": (
                    str(path_row["action"]) if path_row is not None else ""
                ),
            }
        )
    trades = []
    for index, row in trades_frame.iterrows():
        side = str(row["side"])
        key = (side, str(row["entry_ts"]))
        control_row = control_by_key.get(key)
        if control_row is None:
            delta_type = "added_vs_v4"
        elif (
            str(control_row["exit_ts"]) != str(row["exit_ts"])
            or not math.isclose(
                float(control_row["net_return"]),
                float(row["net_return"]),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ):
            delta_type = "modified_vs_v4"
        else:
            delta_type = "shared_with_v4"
        source = str(row["entry_source"])
        prefix = (
            "R" if source == "band_target_reversal"
            else "C" if source == "cooldown_reentry"
            else "L" if side == "long"
            else "S"
        )
        if prefix in ("R", "C"):
            prefix = f"{prefix}-{'L' if side == 'long' else 'S'}"
        reason = str(row["exit_reason"])
        reason_labels = {
            "band_target_reversal": "相反ATR边界+slope确认反手",
            "protective_stop": "保护止损转flat",
            "terminal_flatten": "样本终点平仓",
        }
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
                    f"{reason_labels.get(reason, reason)} · "
                    f"{source} · {delta_type}"
                ),
                "returnPct": float(row["net_return"]) * 100.0,
                "netPnl": float(row["net_pnl"]),
                "entrySource": source,
                "deltaType": delta_type,
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
    attribution = audit.state_attribution(trades_frame)
    return {
        "title": "HYPE V4 ATR容错趋势状态机：完整交易路径",
        "subtitle": (
            "±0.75×ATR7 target边界 · long/short slope确认 · 保护退出只转flat "
            "· 2d/5d cooldown可重入 · diagnostic-only"
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
            "exposurePct": v4.exposure_pct(result),
        },
        "attribution": attribution,
    }


def band_template(template: str, helper: Any) -> str:
    output = helper.extended_template(template)
    output = output.replace(
        "<title>HYPE MA7 三状态迟滞交易路径</title>",
        "<title>HYPE V4 ATR容错趋势状态机</title>",
    ).replace(
        "±0.75 外边界 / ±0.25 震荡区",
        "±0.75×ATR7 target边界",
    )
    band_label = (
        '<label><input id="showBands" type="checkbox" checked> '
        '<span class="swatch" style="background:#9b7bff"></span>'
        '±0.75×ATR7 target边界</label>'
    )
    state_label = (
        '<label><input id="showState" type="checkbox" checked> '
        '<span class="swatch" style="background:#3f6d64"></span>'
        '持仓状态 / cooldown</label>'
    )
    if band_label not in output:
        raise RuntimeError("extended template band label missing")
    output = output.replace(band_label, band_label + state_label, 1)
    output = output.replace(
        'outer: "#9b7bff", neutral: "#4d667a",',
        (
            'outer: "#9b7bff", neutral: "#4d667a", '
            'stateLong: "#2dd4a7", stateShort: "#f05c70", '
            'stateCooldown: "#9b7bff",'
        ),
        1,
    )
    state_anchor = """\
  const bodyW = clamp(pw / visibleDays * .62, 1, 13);
"""
    state_draw = state_anchor + """\
  if (document.getElementById("showState").checked) {
    const dayW = Math.max(1, pw / visibleDays);
    for (const c of vis) {
      const x = xScale(c.t + DAY / 2, margin.left, pw);
      if (c.cooldown) {
        ctx.fillStyle = COLORS.stateCooldown; ctx.globalAlpha = .13;
      } else if (c.position > 0) {
        ctx.fillStyle = COLORS.stateLong; ctx.globalAlpha = .075;
      } else if (c.position < 0) {
        ctx.fillStyle = COLORS.stateShort; ctx.globalAlpha = .075;
      } else {
        continue;
      }
      ctx.fillRect(x - dayW / 2, margin.top, dayW, ph);
    }
    ctx.globalAlpha = 1;
  }
"""
    if state_anchor not in output:
        raise RuntimeError("price body-width anchor missing")
    output = output.replace(state_anchor, state_draw, 1)
    output = output.replace(
        '    drawBand("neutralUpper", COLORS.neutral, [2, 3], 1);\n'
        '    drawBand("neutralLower", COLORS.neutral, [2, 3], 1);\n',
        "",
        1,
    )
    output = output.replace(
        'document.getElementById("showBands").onchange = draw;',
        'document.getElementById("showBands").onchange = draw;\n'
        'document.getElementById("showState").onchange = draw;',
        1,
    )
    old_tooltip_tail = (
        '震荡区 ${candle.neutralLower == null ? "—" : '
        'fmt(candle.neutralLower)} — '
        '${candle.neutralUpper == null ? "—" : '
        'fmt(candle.neutralUpper)}`;'
    )
    new_tooltip_tail = (
        '状态 ${candle.state}'
        '${candle.cooldown ? " · " + candle.cooldown : ""}\\n'
        '动作 ${candle.action || "hold"}`;'
    )
    if old_tooltip_tail not in output:
        raise RuntimeError("extended tooltip tail missing")
    return output.replace(old_tooltip_tail, new_tooltip_tail, 1)


def main() -> None:
    helper = load_pinned(HELPER_PATH, HELPER_SHA256, "hype_band_chart_helper")
    template = load_pinned(
        TEMPLATE_PATH,
        TEMPLATE_SHA256,
        "hype_band_chart_template",
    )
    payload = build_payload()
    if len(payload["trades"]) != EXPECTED_TRADES:
        raise RuntimeError(
            f"expected {EXPECTED_TRADES} chart trades, "
            f"got {len(payload['trades'])}"
        )
    ids = [trade["id"] for trade in payload["trades"]]
    if len(ids) != len(set(ids)):
        raise RuntimeError("band chart trade IDs are not unique")
    for trade in payload["trades"]:
        if trade["entryT"] > trade["exitT"]:
            raise RuntimeError(f"trade timestamp order invalid: {trade['id']}")
    html = band_template(template.HTML_TEMPLATE, helper).replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    if "__PAYLOAD__" in html:
        raise RuntimeError("chart payload replacement failed")
    if "ctx.lineTo(x2, y2)" not in html:
        raise RuntimeError("trade connection line renderer missing")
    if 'drawBand("upper"' not in html or "showState" not in html:
        raise RuntimeError("band/state overlay renderer missing")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH.relative_to(ROOT)),
                "candles": len(payload["candles"]),
                "trades": len(payload["trades"]),
                "equity_points": len(payload["equity"]),
                "band_target_reversals": payload["attribution"][
                    "band_target_reversals"
                ],
                "cooldown_reentries": payload["attribution"][
                    "cooldown_reentries"
                ],
                "all_trades_connected": True,
                "band_and_state_overlays": True,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
