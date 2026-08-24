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
V2_RENDERER_PATH = (
    FAMILY_DIR / "scripts/render_hype_1d_ma7_abt_v2_trade_path.py"
)
V2_RENDERER_SHA256 = (
    "55193758762facf76e5b4200907ce310e53833bc207970c6b228716d2cb80734"
)
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_abt_v3_trade_path_2026-08-07.html"
V3_EQUITY_MULTIPLE = 4.508464159893385
SLOPE_AFFECTED_ENTRY = pd.Timestamp("2026-03-29T00:00:00Z")


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


def build_payload(renderer: Any) -> dict[str, Any]:
    formation = renderer.load_pinned(
        renderer.FORMATION_PATH,
        renderer.FORMATION_SHA256,
        "hype_v3_trade_path_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v3_trade_path_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v3_trade_path_base",
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
    backtest = formation.build_reversal_backtest(engine)
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
    if not math.isclose(
        result.metrics["equity_multiple"],
        V3_EQUITY_MULTIPLE,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("V3 chart anchor drift")

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
    trades_frame = formation.annotate_trades(
        result,
        "T1_trailing_stop_short_reversal",
    )
    trades: list[dict[str, Any]] = []
    for index, row in trades_frame.iterrows():
        side = str(row["side"])
        forced = row["entry_source"] == "forced_trailing_stop_reversal"
        entry_ts = pd.Timestamp(row["entry_ts"])
        slope_affected = (
            side == "long"
            and not forced
            and entry_ts == SLOPE_AFFECTED_ENTRY
        )
        entry_index = int(pd.DatetimeIndex(book.ts).searchsorted(entry_ts))
        signal_index = entry_index - 1
        slope_atr = (
            float(
                (features.ma7[signal_index] - features.ma7[signal_index - 1])
                / features.atr7[signal_index]
            )
            if slope_affected
            else None
        )
        prefix = "R-S" if forced else ("L" if side == "long" else "S")
        reason = str(row["exit_reason"])
        if forced:
            reason = f"trailing反手 · {reason}"
        if slope_affected:
            reason = (
                f"★ 斜率敏感：0.02入场，0.04会过滤 · {reason}"
            )
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
                "slopeAffected": slope_affected,
                "slopeAtr": slope_atr,
                "currentSlopeThreshold": 0.02 if slope_affected else None,
                "alternativeSlopeThreshold": 0.04 if slope_affected else None,
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
        "title": "HYPE 日线 MA7 非对称趋势 V3：完整交易路径",
        "subtitle": (
            "V3 registered 1x · UTC 日K · short退出迟滞0.75×ATR7 · "
            "2025-05-31至2026-07-30 · 金色★L15为long slope "
            "0.02→0.04时会被过滤的交易"
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
        "slopeAnnotation": {
            "affectedTradeId": "L15",
            "signalDay": "2026-03-28",
            "slopeAtr": next(
                trade["slopeAtr"]
                for trade in trades
                if trade["slopeAffected"]
            ),
            "currentThreshold": 0.02,
            "alternativeThreshold": 0.04,
            "effect": "0.04 threshold filters this -6.87% long trade",
        },
    }


def highlight_template(template: str) -> str:
    template = template.replace(
        'const color = t.side === "long" ? COLORS.long : COLORS.short;',
        (
            'const color = t.slopeAffected ? "#ffd166" : '
            '(t.side === "long" ? COLORS.long : COLORS.short);'
        ),
    )
    template = template.replace(
        "ctx.globalAlpha = isActive ? 1 : .72;\n"
        "      ctx.lineWidth = isActive ? 3 : 1.5;\n"
        "      ctx.setLineDash(t.returnPct >= 0 ? [] : [5, 4]);",
        "ctx.globalAlpha = t.slopeAffected || isActive ? 1 : .72;\n"
        "      ctx.lineWidth = t.slopeAffected ? 4 : "
        "(isActive ? 3 : 1.5);\n"
        "      ctx.setLineDash(t.slopeAffected ? [10, 4] : "
        "(t.returnPct >= 0 ? [] : [5, 4]));",
    )
    template = template.replace(
        "ctx.fillText(t.id, x2, y2 - 10);\n"
        "      }\n"
        "    }\n"
        "  }",
        "ctx.fillText(t.id, x2, y2 - 10);\n"
        "      }\n"
        "      if (t.slopeAffected) {\n"
        '        ctx.fillStyle = "#ffd166";\n'
        '        ctx.font = "bold 12px ui-monospace";\n'
        '        ctx.fillText("0.04 会过滤此笔", '
        "(x1 + x2) / 2, Math.min(y1, y2) - 18);\n"
        "      }\n"
        "    }\n"
        "  }",
    )
    template = template.replace(
        '<tr data-id="${t.id}">',
        (
            '<tr data-id="${t.id}" style="${t.slopeAffected ? '
            "'background:rgba(255,209,102,.16);"
            "outline:1px solid #ffd166' : ''}\">"
        ),
    )
    template = template.replace(
        '<td class="${t.side}">${t.id}</td>',
        (
            '<td class="${t.side}">${t.id}'
            '${t.slopeAffected ? " ★斜率敏感" : ""}</td>'
        ),
    )
    return template


def validate(payload: dict[str, Any], html: str) -> None:
    if (
        len(payload["trades"]) != payload["metrics"]["trades"]
        or payload["metrics"]["trades"] != 19
    ):
        raise RuntimeError("V3 chart trade count mismatch")
    ids = [trade["id"] for trade in payload["trades"]]
    if len(ids) != len(set(ids)):
        raise RuntimeError("V3 chart trade IDs are not unique")
    for trade in payload["trades"]:
        if trade["entryT"] > trade["exitT"]:
            raise RuntimeError(f"trade timestamp order invalid: {trade['id']}")
        if not all(
            key in trade for key in ("entryT", "exitT", "entry", "exit")
        ):
            raise RuntimeError(f"trade endpoint missing: {trade['id']}")
    if "__PAYLOAD__" in html:
        raise RuntimeError("HTML template placeholder remains")
    if "ctx.lineTo(x2, y2)" not in html:
        raise RuntimeError("trade connection line renderer missing")
    affected = [
        trade for trade in payload["trades"] if trade["slopeAffected"]
    ]
    if len(affected) != 1 or affected[0]["id"] != "L15":
        raise RuntimeError("slope-affected trade annotation drift")
    if not (
        affected[0]["currentSlopeThreshold"]
        <= affected[0]["slopeAtr"]
        < affected[0]["alternativeSlopeThreshold"]
    ):
        raise RuntimeError("slope-affected trade value outside thresholds")
    if "0.04 会过滤此笔" not in html or "★斜率敏感" not in html:
        raise RuntimeError("slope annotation renderer missing")


def main() -> None:
    renderer = load_pinned(
        V2_RENDERER_PATH,
        V2_RENDERER_SHA256,
        "hype_v3_trade_path_v2_renderer",
    )
    template = renderer.load_pinned(
        renderer.TEMPLATE_PATH,
        renderer.TEMPLATE_SHA256,
        "hype_v3_trade_path_template",
    )
    payload = build_payload(renderer)
    html = highlight_template(template.HTML_TEMPLATE).replace(
        "<title>HYPE MA7 完整交易路径</title>",
        "<title>HYPE MA7 V3 完整交易路径</title>",
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
                "forced_reversal_trades": sum(
                    trade["entrySource"] == "forced_trailing_stop_reversal"
                    for trade in payload["trades"]
                ),
                "slope_affected_trade": payload["slopeAnnotation"],
                "equity_points": len(payload["equity"]),
                "all_trades_connected": True,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
