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
FAMILY_DIR = ROOT / "research/hype/4h-ma7-rsi6-asymmetric-reversal"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
STRATEGY_SCRIPT = (
    FAMILY_DIR
    / "scripts/research_hype_4h_ma7_rsi6_asymmetric_reversal.py"
)
STRATEGY_SCRIPT_SHA256 = (
    "c5d521a3b1b804e4b29b46f6734160047aae32e80a29a310906c5da4e9eedf15"
)
NATIVE_TEMPLATE = FAMILY_DIR / "scripts/hype_4h_trade_path_template.html"
NATIVE_TEMPLATE_SHA256 = (
    "c97f67549f838f801196fb6e2163d6c5ede1f61d5470a6f3024044c12384960b"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the full HYPE 4h SMA7-RSI6 trade path."
    )
    parser.add_argument("--run-date", default="2026-08-06")
    parser.add_argument(
        "--variant",
        choices=("baseline", "cross_reentry"),
        default="baseline",
    )
    return parser.parse_args()


def load_module(path: Path, expected_hash: str, name: str) -> Any:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_hash:
        raise RuntimeError(
            f"{path.name} drift: expected {expected_hash}, got {digest}"
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


def load_phase_zero_bundle(strategy: Any) -> Any:
    engine = strategy.load_module(
        strategy.BACKTEST_ENGINE,
        strategy.BACKTEST_ENGINE_SHA256,
        "hype_4h_ma7_rsi6_chart_engine",
    )
    adapter = engine.load_module(
        engine.SOURCE_ADAPTER,
        engine.SOURCE_ADAPTER_SHA256,
        "hype_4h_ma7_rsi6_chart_adapter",
    )
    base = adapter.load_module(
        adapter.BASE_PATH,
        adapter.BASE_SHA256,
        "hype_4h_ma7_rsi6_chart_base",
    )
    parent_digest = hashlib.sha256(base.PARENT_SCRIPT.read_bytes()).hexdigest()
    if parent_digest != engine.PARENT_LOADER_SHA256:
        raise RuntimeError(
            "parent data loader drift: "
            f"expected {engine.PARENT_LOADER_SHA256}, got {parent_digest}"
        )
    parent = base.load_parent()
    data_engine = parent.load_engine()
    hourly, hourly_quality = data_engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = data_engine.load_and_audit_funding(ROOT)
    return engine.build_bundle(
        adapter,
        hourly,
        hourly_quality,
        funding,
        funding_quality,
        phase_hours=0,
    )


def trade_reason(
    side: str,
    raw_reason: str,
    *,
    direct_reversal: bool,
) -> str:
    if raw_reason == "terminal_flatten":
        return "terminal flatten"
    if side == "long":
        return "close<SMA7 且最近3根 RSI6 曾>70"
    if direct_reversal:
        return "close>SMA7，平空反多"
    return "RSI6<30"


def build_payload(run_date: str, variant: str) -> dict[str, Any]:
    strategy = load_module(
        STRATEGY_SCRIPT,
        STRATEGY_SCRIPT_SHA256,
        "hype_4h_ma7_rsi6_chart_strategy",
    )
    bundle = load_phase_zero_bundle(strategy)
    stem = (
        "hype_4h_ma7_rsi6_asymmetric_reversal"
        if variant == "baseline"
        else "hype_4h_ma7_rsi6_v2_cross_reentry"
    )
    indicators_path = ARTIFACT_DIR / f"{stem}_indicators_{run_date}.csv"
    trades_path = ARTIFACT_DIR / f"{stem}_trades_{run_date}.csv"
    path_path = ARTIFACT_DIR / f"{stem}_path_{run_date}.csv"
    summary_path = ARTIFACT_DIR / f"{stem}_summary_{run_date}.json"
    indicators = pd.read_csv(indicators_path)
    if len(indicators) != bundle.count:
        raise RuntimeError(
            f"indicator rows {len(indicators)} != candles {bundle.count}"
        )
    candles = [
        {
            "t": timestamp_ms(ts),
            "o": float(bundle.bars.iloc[index]["open"]),
            "h": float(bundle.bars.iloc[index]["high"]),
            "l": float(bundle.bars.iloc[index]["low"]),
            "c": float(bundle.bars.iloc[index]["close"]),
            "ma": finite_or_none(indicators.iloc[index]["sma7"]),
            "rsi": finite_or_none(indicators.iloc[index]["rsi6"]),
            "target": int(indicators.iloc[index]["target_after_close"]),
        }
        for index, ts in enumerate(bundle.bars["ts"])
    ]
    trades_frame = pd.read_csv(trades_path)
    trades: list[dict[str, Any]] = []
    for index, row in trades_frame.iterrows():
        side = str(row["side"])
        raw_reason = str(row["exit_reason"])
        next_row = (
            trades_frame.iloc[index + 1]
            if index + 1 < len(trades_frame)
            else None
        )
        direct_reversal = bool(
            next_row is not None
            and str(next_row["entry_ts"]) == str(row["exit_ts"])
            and str(next_row["side"]) != side
        )
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
                "reason": trade_reason(
                    side,
                    raw_reason,
                    direct_reversal=direct_reversal,
                ),
                "returnPct": float(row["net_return"]) * 100.0,
                "netPnl": float(row["net_pnl"]),
            }
        )
    path_frame = pd.read_csv(path_path)
    equity = [
        {
            "t": timestamp_ms(row.ts),
            "v": float(row.close_equity),
            "position": int(row.position),
            "action": str(row.action),
        }
        for row in path_frame.itertuples(index=False)
    ]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    full = summary["audits"]["full"]["base"]
    title = (
        "HYPE 4H SMA7-RSI6 非对称反转：完整交易路径"
        if variant == "baseline"
        else "HYPE 4H SMA7-RSI6 Cross-Reentry V2：完整交易路径"
    )
    return {
        "title": title,
        "subtitle": (
            "UTC 4H K · 收盘信号、下一根开盘成交 · "
            "historical observation · explore / not promoted / not live-ready"
        ),
        "generatedAt": datetime.now(UTC).isoformat(),
        "candles": candles,
        "trades": trades,
        "equity": equity,
        "metrics": {
            "returnPct": full["net_return_pct"],
            "mddPct": full["max_drawdown_pct"],
            "sharpe": full["sharpe"],
            "profitFactor": full["profit_factor"],
            "trades": full["closed_trades"],
            "longTrades": full["long_trades"],
            "shortTrades": full["short_trades"],
        },
    }


def load_native_template() -> str:
    digest = hashlib.sha256(NATIVE_TEMPLATE.read_bytes()).hexdigest()
    if digest != NATIVE_TEMPLATE_SHA256:
        raise RuntimeError(
            "native 4h template drift: "
            f"expected {NATIVE_TEMPLATE_SHA256}, got {digest}"
        )
    template = NATIVE_TEMPLATE.read_text(encoding="utf-8")
    if template.count("__PAYLOAD__") != 1:
        raise RuntimeError("native 4h template must contain one payload slot")
    return template


def main() -> None:
    args = parse_args()
    payload = build_payload(args.run_date, args.variant)
    html = load_native_template().replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    stem = (
        "hype_4h_ma7_rsi6_asymmetric_reversal"
        if args.variant == "baseline"
        else "hype_4h_ma7_rsi6_v2_cross_reentry"
    )
    output = ARTIFACT_DIR / f"{stem}_trade_path_{args.run_date}.html"
    output.write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output.relative_to(ROOT)),
                "candles": len(payload["candles"]),
                "trades": len(payload["trades"]),
                "equity_points": len(payload["equity"]),
                "self_contained": True,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
