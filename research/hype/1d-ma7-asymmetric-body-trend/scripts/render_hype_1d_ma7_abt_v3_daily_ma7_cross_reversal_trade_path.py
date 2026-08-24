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
    / "scripts/audit_hype_1d_ma7_abt_v3_daily_ma7_cross_reversal.py"
)
AUDIT_SHA256 = (
    "0ef6b119ddaac8b52783ea10f3e570985155edf385c0dc58b3aa007fff39be85"
)
V2_RENDERER_PATH = (
    FAMILY_DIR / "scripts/render_hype_1d_ma7_abt_v2_trade_path.py"
)
V2_RENDERER_SHA256 = (
    "55193758762facf76e5b4200907ce310e53833bc207970c6b228716d2cb80734"
)
OUTPUT_PATH = (
    ARTIFACT_DIR
    / "hype_1d_ma7_abt_v3_daily_ma7_cross_reversal_trade_path_2026-08-07.html"
)
CANDIDATE_EQUITY_MULTIPLE = 1.2080917059122895


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


def build_payload(audit: Any, renderer: Any) -> dict[str, Any]:
    formation = audit.load_formation()
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_daily_cross_chart_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_daily_cross_chart_base",
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
    cross_backtest = audit.build_daily_cross_backtest(engine)
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
    result = cross_backtest(
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
        CANDIDATE_EQUITY_MULTIPLE,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("daily-cross chart anchor drift")
    trades_frame = audit.annotate_trades(
        formation,
        result,
        audit.DAILY_CROSS,
    )
    candles = [
        {
            "t": renderer.timestamp_ms(ts),
            "o": float(book.open[index]),
            "h": float(book.high[index]),
            "l": float(book.low[index]),
            "c": float(book.close[index]),
            "ma": renderer.finite_or_none(features.ma7[index]),
        }
        for index, ts in enumerate(book.ts)
    ]
    trades = []
    for index, row in trades_frame.iterrows():
        side = str(row["side"])
        forced = (
            row["entry_source"]
            == "forced_daily_ma7_close_cross_reversal"
        )
        prefix = "R-S" if forced else ("L" if side == "long" else "S")
        reason = str(row["exit_reason"])
        if forced:
            reason = f"日线收盘跌破MA7反手 · {reason}"
        trades.append(
            {
                "id": f"{prefix}{index + 1:02d}",
                "side": side,
                "entryT": renderer.timestamp_ms(row["entry_ts"]),
                "exitT": renderer.timestamp_ms(row["exit_ts"]),
                "entryTs": str(row["entry_ts"]),
                "exitTs": str(row["exit_ts"]),
                "entry": float(row["entry_price"]),
                "exit": float(row["exit_price"]),
                "bars": int(row["bars_held"]),
                "reason": reason,
                "returnPct": float(row["net_return"]) * 100.0,
                "netPnl": float(row["net_pnl"]),
                "entrySource": str(row["entry_source"]),
            }
        )
    equity = [
        {
            "t": renderer.timestamp_ms(row["ts"]),
            "v": float(row["close_equity"]),
            "position": int(row["position"]),
            "action": str(row["action"]),
        }
        for row in result.path
    ]
    metrics = result.metrics
    return {
        "title": "HYPE V3 日线跌破MA7反手候选：完整交易路径",
        "subtitle": (
            "diagnostic-only · 1x · UTC日K · trailing只平仓 · "
            "前收≥MA7且当收<MA7时，下一日open平多反手short · "
            "2025-05-31至2026-07-30"
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
        },
    }


def validate(payload: dict[str, Any], html: str) -> None:
    if (
        len(payload["trades"]) != payload["metrics"]["trades"]
        or payload["metrics"]["trades"] != 22
    ):
        raise RuntimeError("daily-cross chart trade count mismatch")
    ids = [trade["id"] for trade in payload["trades"]]
    if len(ids) != len(set(ids)):
        raise RuntimeError("daily-cross chart trade IDs are not unique")
    forced = 0
    for trade in payload["trades"]:
        if trade["entryT"] > trade["exitT"]:
            raise RuntimeError(f"trade timestamp order invalid: {trade['id']}")
        if not all(
            key in trade for key in ("entryT", "exitT", "entry", "exit")
        ):
            raise RuntimeError(f"trade endpoint missing: {trade['id']}")
        forced += trade["entrySource"] == (
            "forced_daily_ma7_close_cross_reversal"
        )
    if forced != 6:
        raise RuntimeError("daily-cross forced reversal count mismatch")
    if "__PAYLOAD__" in html:
        raise RuntimeError("HTML template placeholder remains")
    if "ctx.lineTo(x2, y2)" not in html:
        raise RuntimeError("trade connection line renderer missing")


def main() -> None:
    audit = load_pinned(
        AUDIT_PATH,
        AUDIT_SHA256,
        "hype_daily_cross_chart_audit",
    )
    renderer = load_pinned(
        V2_RENDERER_PATH,
        V2_RENDERER_SHA256,
        "hype_daily_cross_chart_renderer",
    )
    template = renderer.load_pinned(
        renderer.TEMPLATE_PATH,
        renderer.TEMPLATE_SHA256,
        "hype_daily_cross_chart_template",
    )
    payload = build_payload(audit, renderer)
    html = template.HTML_TEMPLATE.replace(
        "<title>HYPE MA7 完整交易路径</title>",
        "<title>HYPE V3 日线跌破MA7反手候选</title>",
    ).replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    validate(payload, html)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH.relative_to(ROOT)),
                "candles": len(payload["candles"]),
                "trades": len(payload["trades"]),
                "daily_close_cross_reversal_trades": sum(
                    trade["entrySource"]
                    == "forced_daily_ma7_close_cross_reversal"
                    for trade in payload["trades"]
                ),
                "equity_points": len(payload["equity"]),
                "all_trades_connected": True,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
