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
    FAMILY_DIR / "scripts/audit_hype_1d_ma7_abt_state_slope_hybrid.py"
)
AUDIT_SHA256 = (
    "16820da66a7d6d954c3ed3387792fa3ab7e410e4fc3dd332ba19599ba99999b5"
)
CHART_HELPER_PATH = (
    FAMILY_DIR
    / "scripts/render_hype_1d_ma7_three_state_hysteresis_trade_path.py"
)
CHART_HELPER_SHA256 = (
    "dca5cda6d88f876f646765993a2a0c5055298cda249f928efe32d23a0aca06ae"
)
OUTPUT_PATH = (
    ARTIFACT_DIR
    / "hype_1d_ma7_state_slope_hybrid_core_trade_path_2026-08-07.html"
)
EXPECTED_EQUITY = 0.6166547611416717
EXPECTED_TRADES = 39


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
        "hype_hybrid_chart_audit",
    )
    formation = audit.load_pinned(
        audit.FORMATION_PATH,
        audit.FORMATION_SHA256,
        "hype_hybrid_chart_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_hybrid_chart_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_hybrid_chart_base",
    )
    selected = formation.read_pinned_json(
        formation.SUMMARY_PATH,
        formation.SUMMARY_SHA256,
    )["historically_profitable_all_checks"][0]
    long_config = replace(
        engine.Config(**selected["long_config"]),
        entry_mode="regime",
        entry_buffer_atr=0.25,
        hard_stop_atr=0.0,
        trail_atr=0.0,
        max_hold_days=0,
        cooldown_days=0,
    )
    short_config = replace(
        engine.Config(**selected["short_config"]),
        entry_mode="regime",
        entry_buffer_atr=0.75,
        hard_stop_atr=0.0,
        trail_atr=0.0,
        max_hold_days=0,
        cooldown_days=0,
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
    result = engine.backtest(
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
        raise RuntimeError("hybrid CORE chart anchor drift")

    candles = []
    for index, ts in enumerate(book.ts):
        ma = finite_or_none(features.ma7[index])
        atr = finite_or_none(features.atr7[index])
        candles.append(
            {
                "t": timestamp_ms(ts),
                "o": float(book.open[index]),
                "h": float(book.high[index]),
                "l": float(book.low[index]),
                "c": float(book.close[index]),
                "ma": ma,
                "upper": None if ma is None or atr is None else ma + 0.25 * atr,
                "lower": None if ma is None or atr is None else ma - 0.75 * atr,
                "neutralUpper": None,
                "neutralLower": None,
            }
        )
    reason_labels = {
        "ma7_hysteresis_exit": "MA7非对称边界退出",
        "ma7_slope_exit": "MA7转向退出空头",
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
                "entrySource": "persistent_regime_with_v2_slope",
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
        "title": "HYPE MA7 状态边界 × V2斜率：HYBRID_CORE交易路径",
        "subtitle": (
            "persistent regime · long +0.25/−0.75 ATR7 · V2 slope gate · "
            "无reclaim/保护层 · diagnostic-only"
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
            "exposurePct": audit.exposure_pct(result),
        },
    }


def main() -> None:
    helper = load_pinned(
        CHART_HELPER_PATH,
        CHART_HELPER_SHA256,
        "hype_hybrid_chart_helper",
    )
    template_module = helper.load_pinned(
        helper.TEMPLATE_PATH,
        helper.TEMPLATE_SHA256,
        "hype_hybrid_chart_template",
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
    html = helper.extended_template(template_module.HTML_TEMPLATE)
    html = html.replace(
        "±0.75 外边界 / ±0.25 震荡区",
        "下边界 −0.75 / 上边界 +0.25 ATR7",
    ).replace(
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
                "asymmetric_bands": True,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
