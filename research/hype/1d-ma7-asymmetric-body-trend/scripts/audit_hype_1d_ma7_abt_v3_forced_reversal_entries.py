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
V3_RENDERER_PATH = (
    FAMILY_DIR / "scripts/render_hype_1d_ma7_abt_v3_trade_path.py"
)
V3_RENDERER_SHA256 = (
    "c40536e309da6c8f75a794a8a9f06fe75005d9aedb7387cf1be57d3fbed23c24"
)
V3_EQUITY_MULTIPLE = 4.508464159893385


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


def main() -> None:
    renderer = load_pinned(
        V3_RENDERER_PATH,
        V3_RENDERER_SHA256,
        "hype_v3_forced_entry_renderer",
    )
    v2_renderer = renderer.load_pinned(
        renderer.V2_RENDERER_PATH,
        renderer.V2_RENDERER_SHA256,
        "hype_v3_forced_entry_v2_renderer",
    )
    formation = v2_renderer.load_pinned(
        v2_renderer.FORMATION_PATH,
        v2_renderer.FORMATION_SHA256,
        "hype_v3_forced_entry_formation",
    )
    engine = formation.load_pinned(
        formation.ENGINE_PATH,
        formation.ENGINE_SHA256,
        "hype_v3_forced_entry_engine",
    )
    base = formation.load_pinned(
        formation.BASE_PATH,
        formation.BASE_SHA256,
        "hype_v3_forced_entry_base",
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
    result = formation.build_reversal_backtest(engine)(
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
        raise RuntimeError("V3 forced-entry audit anchor drift")
    trades = formation.annotate_trades(
        result,
        "T1_trailing_stop_short_reversal",
    )
    timestamps = pd.DatetimeIndex(book.ts)
    rows = []
    for trade_index, row in trades.iterrows():
        if row["entry_source"] != "forced_trailing_stop_reversal":
            continue
        entry_ts = pd.Timestamp(row["entry_ts"])
        daily_index = int(timestamps.searchsorted(entry_ts.floor("1D")))
        known_index = daily_index - 1
        known_ma7 = float(features.ma7[known_index])
        entry_price = float(row["entry_price"])
        rows.append(
            {
                "trade_id": f"R-S{trade_index + 1:02d}",
                "entry_ts": entry_ts.isoformat(),
                "exit_ts": str(row["exit_ts"]),
                "entry_price": entry_price,
                "last_completed_ma7": known_ma7,
                "entry_minus_ma7": entry_price - known_ma7,
                "entry_below_last_completed_ma7": entry_price < known_ma7,
                "entry_day_eventual_ma7": float(features.ma7[daily_index]),
                "bars_held": int(row["bars_held"]),
                "exit_reason": str(row["exit_reason"]),
                "net_return_pct": float(row["net_return"]) * 100.0,
            }
        )
    frame = pd.DataFrame(rows)
    if len(frame) != 7:
        raise RuntimeError(f"expected 7 V3 forced reversals, got {len(frame)}")
    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "version": "HYPE-1D-MA7-Asymmetric-Body-Trend-V3",
        "status": "registered identity unchanged; live-readiness defect",
        "forced_reversal_count": int(len(frame)),
        "entry_above_last_completed_ma7_count": int(
            (~frame["entry_below_last_completed_ma7"]).sum()
        ),
        "held_one_bar_or_less_count": int((frame["bars_held"] <= 1).sum()),
        "held_one_bar_or_less_loss_count": int(
            (
                (frame["bars_held"] <= 1)
                & (frame["net_return_pct"] < 0.0)
            ).sum()
        ),
        "above_ma_trade_ids": frame.loc[
            ~frame["entry_below_last_completed_ma7"],
            "trade_id",
        ].tolist(),
        "data_quality": {
            "hourly": hourly_quality,
            "funding": funding_quality,
        },
        "evidence_role": "post-reveal audit of frozen registered V3 behavior",
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "hype_1d_v3_forced_reversal_entry_audit_2026-08-07"
    frame.to_csv(ARTIFACT_DIR / f"{stem}.csv", index=False)
    (ARTIFACT_DIR / f"{stem}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(frame.to_string(index=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
