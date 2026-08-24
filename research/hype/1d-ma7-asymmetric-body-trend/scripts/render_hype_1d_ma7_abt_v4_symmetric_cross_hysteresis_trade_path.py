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
    FAMILY_DIR / "scripts/audit_hype_1d_ma7_abt_v4_symmetric_cross_hysteresis.py"
)
AUDIT_SHA256 = "58665a110fee14d89ded7c352ed15472dbb410a2e65f80fe47e9442e0cf9d75d"
BAND_RENDERER_PATH = (
    FAMILY_DIR / "scripts/render_hype_1d_ma7_abt_v4_band_state_machine_trade_path.py"
)
BAND_RENDERER_SHA256 = (
    "2383728d6d6c5c3f7e3140dcd1c87c7b69c95c0e902adc8b326cc5e4103df2b5"
)
OUTPUT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_abt_v4_symmetric_cross_d075_trade_path_2026-08-07.html"
)
EXPECTED_EQUITY = 1.4411847874815904
EXPECTED_TRADES = 29


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
    audit = load_pinned(AUDIT_PATH, AUDIT_SHA256, "hype_symmetric_chart_audit")
    parent = audit.load_pinned(
        audit.PARENT_PATH,
        audit.PARENT_SHA256,
        "hype_symmetric_chart_parent",
    )
    shared = parent.load_pinned(
        parent.TIMING_PATH,
        parent.TIMING_SHA256,
        "hype_symmetric_chart_shared",
    )
    v4 = shared.load_pinned(
        shared.V4_FORMATION_PATH,
        shared.V4_FORMATION_SHA256,
        "hype_symmetric_chart_v4",
    )
    formation = v4.load_pinned(
        v4.FORMATION_PATH,
        v4.FORMATION_SHA256,
        "hype_symmetric_chart_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_symmetric_chart_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_symmetric_chart_base",
    )
    selected = formation.read_pinned_json(
        formation.SUMMARY_PATH,
        formation.SUMMARY_SHA256,
    )["historically_profitable_all_checks"][0]
    long_config = replace(
        engine.Config(**selected["long_config"]),
        exit_buffer_atr=audit.HYSTERESIS_ATR,
    )
    short_config = replace(
        engine.Config(**selected["short_config"]),
        exit_buffer_atr=audit.HYSTERESIS_ATR,
    )
    candidate_backtest, signal = audit.build_symmetric_backtest(engine)
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
    hourly = hourly.loc[hourly["ts"] <= formation.HISTORICAL_HOUR_CUTOFF].copy()
    funding = funding.loc[funding["ts"] <= formation.HISTORICAL_HOUR_CUTOFF].copy()
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
        raise RuntimeError("symmetric cross chart anchor drift")
    trades_frame = audit.annotate_trades(formation, result)
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
        if row["exit_reason"] not in ("protective_stop", "max_hold"):
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
                f"{row['side'].upper()} cooldown {days - offset + 1}/{days}"
            )
    candles = []
    for index, ts in enumerate(book.ts):
        day = pd.Timestamp(ts).floor("1D")
        ma = finite_or_none(features.ma7[index])
        atr = finite_or_none(features.atr7[index])
        upper = lower = None
        if ma is not None and atr is not None:
            upper = ma + audit.HYSTERESIS_ATR * atr
            lower = ma - audit.HYSTERESIS_ATR * atr
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
                "action": (str(path_row["action"]) if path_row is not None else ""),
            }
        )
    trades = []
    reason_labels = {
        "symmetric_hysteresis_reversal": "持仓越过0.75×ATR7外边界反手",
        "protective_stop": "保护止损转flat",
        "max_hold": "V4 max-hold转flat",
        "terminal_flatten": "样本终点平仓",
    }
    for index, row in trades_frame.iterrows():
        side = str(row["side"])
        source = str(row["entry_source"])
        key = (side, str(row["entry_ts"]))
        control_row = control_by_key.get(key)
        if control_row is None:
            delta_type = "added_vs_v4"
        elif str(control_row["exit_ts"]) != str(row["exit_ts"]) or not math.isclose(
            float(control_row["net_return"]),
            float(row["net_return"]),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            delta_type = "modified_vs_v4"
        else:
            delta_type = "shared_with_v4"
        source_label = (
            "持仓外边界反手"
            if source == "held_hysteresis_reversal"
            else "flat fresh MA7 cross"
        )
        prefix = (
            "R-L"
            if source == "held_hysteresis_reversal" and side == "long"
            else "R-S"
            if source == "held_hysteresis_reversal"
            else "F-L"
            if side == "long"
            else "F-S"
        )
        reason = str(row["exit_reason"])
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
                    f"{source_label} · {delta_type}"
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
    return {
        "title": "HYPE V4 对称 MA7 Cross × 持仓迟滞：完整交易路径",
        "subtitle": (
            "flat入场只看fresh MA7 cross · 持仓反向越过±0.75×ATR7才反手 "
            "· 无slope/entry buffer · V4保护/max-hold/cooldown保留"
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
        "attribution": audit.attribution(trades_frame),
    }


def main() -> None:
    band_renderer = load_pinned(
        BAND_RENDERER_PATH,
        BAND_RENDERER_SHA256,
        "hype_symmetric_chart_band_renderer",
    )
    helper = band_renderer.load_pinned(
        band_renderer.HELPER_PATH,
        band_renderer.HELPER_SHA256,
        "hype_symmetric_chart_helper",
    )
    template = band_renderer.load_pinned(
        band_renderer.TEMPLATE_PATH,
        band_renderer.TEMPLATE_SHA256,
        "hype_symmetric_chart_template",
    )
    payload = build_payload()
    if len(payload["trades"]) != EXPECTED_TRADES:
        raise RuntimeError(
            f"expected {EXPECTED_TRADES} chart trades, got {len(payload['trades'])}"
        )
    ids = [trade["id"] for trade in payload["trades"]]
    if len(ids) != len(set(ids)):
        raise RuntimeError("symmetric chart trade IDs are not unique")
    for trade in payload["trades"]:
        if trade["entryT"] > trade["exitT"]:
            raise RuntimeError(f"trade timestamp order invalid: {trade['id']}")
    html_template = band_renderer.band_template(
        template.HTML_TEMPLATE,
        helper,
    )
    html_template = html_template.replace(
        "<title>HYPE V4 ATR容错趋势状态机</title>",
        "<title>HYPE V4 对称MA7 Cross持仓迟滞</title>",
    ).replace(
        "±0.75×ATR7 target边界",
        "持仓 ±0.75×ATR7 容错边界",
    )
    html = html_template.replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    if "__PAYLOAD__" in html:
        raise RuntimeError("chart payload replacement failed")
    if "ctx.lineTo(x2, y2)" not in html:
        raise RuntimeError("trade connection line renderer missing")
    if 'drawBand("upper"' not in html or "showState" not in html:
        raise RuntimeError("hysteresis/state overlay renderer missing")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH.relative_to(ROOT)),
                "candles": len(payload["candles"]),
                "trades": len(payload["trades"]),
                "equity_points": len(payload["equity"]),
                "fresh_cross_entries": payload["attribution"]["fresh_cross_entries"],
                "hysteresis_reversals": payload["attribution"]["hysteresis_reversals"],
                "all_trades_connected": True,
                "hysteresis_and_state_overlays": True,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
