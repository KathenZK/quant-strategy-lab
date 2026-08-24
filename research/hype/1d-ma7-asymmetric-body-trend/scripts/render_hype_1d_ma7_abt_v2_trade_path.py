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
FORMATION_PATH = (
    FAMILY_DIR / "scripts/audit_hype_v1_trailing_stop_short_reversal.py"
)
FORMATION_SHA256 = (
    "35185bbdba87732a806ef3d5e0ff9fc9da9e314e8369695646e7b3f07cbb1166"
)
TEMPLATE_PATH = (
    FAMILY_DIR / "scripts/render_hype_1d_ma7_separated_trade_path.py"
)
TEMPLATE_SHA256 = (
    "549eeeac7c1e4a618ac1d2e607b909e2dd059c22edda2d68c9a7b4c6553ffcd4"
)
OUTPUT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_abt_v2_trade_path_2026-08-06.html"
)
V2_EQUITY_MULTIPLE = 4.225904698992523


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
    formation = load_pinned(
        FORMATION_PATH,
        FORMATION_SHA256,
        "hype_v2_trade_path_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v2_trade_path_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v2_trade_path_base",
    )
    summary = formation.read_pinned_json(
        formation.SUMMARY_PATH,
        formation.SUMMARY_SHA256,
    )
    selected = summary["historically_profitable_all_checks"][0]
    long_config = engine.Config(**selected["long_config"])
    short_config = engine.Config(**selected["short_config"])
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
        V2_EQUITY_MULTIPLE,
        rel_tol=1e-10,
        abs_tol=1e-10,
    ):
        raise RuntimeError("V2 chart anchor drift")

    candles = [
        {
            "t": timestamp_ms(ts),
            "o": float(book.open[index]),
            "h": float(book.high[index]),
            "l": float(book.low[index]),
            "c": float(book.close[index]),
            "ma": finite_or_none(features.ma7[index]),
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
        prefix = "R-S" if forced else ("L" if side == "long" else "S")
        reason = str(row["exit_reason"])
        if forced:
            reason = f"trailing反手 · {reason}"
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
                "reason": reason,
                "returnPct": float(row["net_return"]) * 100.0,
                "netPnl": float(row["net_pnl"]),
                "entrySource": str(row["entry_source"]),
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
        "title": "HYPE 日线 MA7 非对称趋势 V2：完整交易路径",
        "subtitle": (
            "V2 registered 1x · UTC 日 K · 2025-05-31 至 2026-07-30 · "
            "每笔入场与对应出场使用同色线连接 · R-S 为 trailing-stop 反手空"
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


def main() -> None:
    template = load_pinned(
        TEMPLATE_PATH,
        TEMPLATE_SHA256,
        "hype_v2_trade_path_template",
    )
    payload = build_payload()
    if len(payload["trades"]) != 19:
        raise RuntimeError("V2 chart must contain all 19 closed trades")
    for trade in payload["trades"]:
        if trade["entryT"] > trade["exitT"]:
            raise RuntimeError(f"trade timestamp order invalid: {trade['id']}")
    html = template.HTML_TEMPLATE.replace(
        "<title>HYPE MA7 完整交易路径</title>",
        "<title>HYPE MA7 V2 完整交易路径</title>",
    ).replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
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
                "equity_points": len(payload["equity"]),
                "all_trades_connected": True,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
