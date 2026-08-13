from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-asset-specific-search"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
TRANSFER_PATH = (
    ROOT
    / "research/asset-portfolios/1d-ma7-separated-trend-transfer/scripts/"
    "research_binance_1d_ma7_separated_trend_transfer.py"
)
TRANSFER_SHA256 = (
    "d4b68183616c34af1eac5a583fdcf3fbec12778a48f7a4765731cb3750eb895a"
)
P0_DIR = ROOT / "data/features/binance_1d_ma7_rsi6_dapml_p0"
P0_MANIFEST = (
    ROOT
    / "research/asset-portfolios/1d-ma7-rsi6-direction-aligned-pooled-ml/"
    "artifacts/p0_data_2026-08-10/p0_data_quality_manifest.json"
)
ASSETS = {
    "BTCUSDT": "btcusdt",
    "ETHUSDT": "ethusdt",
}
COMMON_START = pd.Timestamp("2019-12-24T00:00:00Z")
DEVELOPMENT_END = pd.Timestamp("2025-08-07T00:00:00Z")
EXPECTED_TERMINAL = pd.Timestamp("2026-08-10T00:00:00Z")
EXPECTED_FRAME_HASHES = {
    "BTCUSDT": {
        "hourly": "3e18066005c9747c040c2686e0b535769f293911e660ad8f923d81b0e2bee1cb",
        "funding": "83e4043d905274dd11d3f7874605cbe05bfea927d80853dd96959d1effd45aca",
    },
    "ETHUSDT": {
        "hourly": "29a5c7ba22831240629d48899b34c7cbfe9f411c139f7dd5220979958a416561",
        "funding": "f16a71928dad18e930db63bfe70d1d949ce79f7061b83717de9c2b50ea7cdb54",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Zero-tuning long-history audit of BTC/ETH shared MA7 V1."
    )
    parser.add_argument(
        "--run-date", default=datetime.now(UTC).date().isoformat()
    )
    parser.add_argument("--self-test", action="store_true")
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


def frame_sha256(
    frame: pd.DataFrame,
    *,
    numeric_columns: list[str] | None = None,
) -> str:
    digest = hashlib.sha256()
    timestamps = (
        pd.to_datetime(frame["ts"], utc=True)
        .to_numpy(dtype="datetime64[ns]")
        .astype("int64")
    )
    digest.update(np.ascontiguousarray(timestamps, dtype="int64").tobytes())
    columns = numeric_columns or [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "vwap",
    ]
    for column in columns:
        values = pd.to_numeric(frame[column], errors="raise").to_numpy(
            dtype="float64"
        )
        digest.update(np.ascontiguousarray(values, dtype="float64").tobytes())
    if "trade_count" in frame.columns:
        counts = pd.to_numeric(
            frame["trade_count"], errors="raise"
        ).to_numpy(dtype="int64")
        digest.update(np.ascontiguousarray(counts, dtype="int64").tobytes())
    return digest.hexdigest()


def v1_configs(engine: Any) -> tuple[Any, Any]:
    long_config = engine.Config(
        side=1,
        entry_mode="reclaim",
        slope_lookback=5,
        slope_min_atr=0.0,
        confirm_days=1,
        entry_buffer_atr=0.25,
        pullback_lookback=10,
        pullback_touch_atr=0.1,
        breakout_lookback=7,
        exit_confirm_days=2,
        exit_buffer_atr=1.0,
        slope_exit_lookback=5,
        hard_stop_atr=0.0,
        trail_atr=0.0,
        max_hold_days=0,
        cooldown_days=0,
    )
    short_config = engine.Config(
        side=-1,
        entry_mode="pullback_reclaim",
        slope_lookback=5,
        slope_min_atr=0.0,
        confirm_days=1,
        entry_buffer_atr=0.1,
        pullback_lookback=5,
        pullback_touch_atr=-0.5,
        breakout_lookback=10,
        exit_confirm_days=2,
        exit_buffer_atr=0.75,
        slope_exit_lookback=0,
        hard_stop_atr=1.5,
        trail_atr=5.0,
        max_hold_days=10,
        cooldown_days=2,
    )
    return long_config, short_config


def load_snapshot(
    symbol: str,
    slug: str,
    manifest: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    result = manifest["results"][symbol]
    if manifest["blocker_count"] != 0:
        raise RuntimeError("P0 manifest has blockers")
    if (
        result["hourly_quality"]["blocker_count"] != 0
        or result["funding_quality"]["blocker_count"] != 0
        or not result["hourly_quality"]["audit"]["trusted"]
    ):
        raise RuntimeError(f"{symbol}: P0 snapshot is not trusted")
    hourly = pd.read_parquet(P0_DIR / f"{slug}_perp_1h.parquet")
    funding = pd.read_parquet(P0_DIR / f"{slug}_perp_funding_mark.parquet")
    hourly["ts"] = pd.to_datetime(hourly["ts"], utc=True)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    hourly = hourly.sort_values("ts").reset_index(drop=True)
    funding = funding.sort_values("ts").reset_index(drop=True)
    hashes = {
        "hourly": frame_sha256(hourly),
        "funding": frame_sha256(
            funding, numeric_columns=["funding_rate", "mark_price"]
        ),
    }
    if hashes != EXPECTED_FRAME_HASHES[symbol]:
        raise RuntimeError(
            f"{symbol}: frozen P0 hash mismatch: {hashes}"
        )
    return hourly, funding[["ts", "funding_rate"]].copy(), {
        "source_manifest": str(P0_MANIFEST.relative_to(ROOT)),
        "hourly_rows": int(len(hourly)),
        "hourly_start": hourly["ts"].iloc[0].isoformat(),
        "hourly_end": hourly["ts"].iloc[-1].isoformat(),
        "funding_rows": int(len(funding)),
        "funding_start": funding["ts"].iloc[0].isoformat(),
        "funding_end": funding["ts"].iloc[-1].isoformat(),
        "hashes": hashes,
        "funding": result["funding_quality"],
        "blocker_count": 0,
    }


def boundary(book: Any, timestamp: pd.Timestamp) -> int:
    index = int(book.ts.searchsorted(timestamp, side="left"))
    if index >= book.count or pd.Timestamp(book.ts[index]) != timestamp:
        raise RuntimeError(f"missing exact boundary {timestamp}")
    return index


def run_window(
    engine: Any,
    book: Any,
    features: Any,
    long_config: Any | None,
    short_config: Any | None,
    *,
    start: int,
    end: int,
    slippage: float,
    signal_lag: int,
    retain: bool,
) -> Any:
    return engine.backtest(
        book,
        features,
        long_config=long_config,
        short_config=short_config,
        start_index=start,
        terminal_index=end,
        slippage=slippage,
        signal_lag=signal_lag,
        retain=retain,
    )


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def portfolio_metrics(results: dict[str, Any]) -> dict[str, Any]:
    frames: list[pd.DataFrame] = []
    for symbol, result in results.items():
        frame = pd.DataFrame(result.path)[["ts", "close_equity"]].copy()
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        frame = frame.rename(columns={"close_equity": symbol})
        frames.append(frame)
    merged = frames[0].merge(frames[1], on="ts", how="inner", validate="one_to_one")
    equity = merged[list(results)].mean(axis=1)
    drawdown = equity / equity.cummax() - 1.0
    return {
        "start_ts": merged["ts"].iloc[0].isoformat(),
        "end_ts": merged["ts"].iloc[-1].isoformat(),
        "equity_multiple": float(equity.iloc[-1]),
        "net_return_pct": float((equity.iloc[-1] - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "rows": int(len(merged)),
    }


def main() -> None:
    args = parse_args()
    transfer = load_module(
        TRANSFER_PATH,
        TRANSFER_SHA256,
        "btc_eth_ma7_v1_long_history_transfer",
    )
    engine = transfer.load_engine()
    long_config, short_config = v1_configs(engine)
    if args.self_test:
        assert asdict(long_config)["entry_mode"] == "reclaim"
        assert asdict(short_config)["entry_mode"] == "pullback_reclaim"
        assert DEVELOPMENT_END > COMMON_START
        print("self-test: PASS")
        return

    manifest = json.loads(P0_MANIFEST.read_text(encoding="utf-8"))
    retained_base: dict[str, Any] = {}
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-MA7-Asset-Specific-Search",
        "campaign": "P2-A V1 long-history zero-tuning audit",
        "status": "explore / not promoted / not live-ready",
        "evidence_role": "historical and researcher-exposed; not clean OOS",
        "contract": {
            "common_start": COMMON_START.isoformat(),
            "development_end_exclusive": DEVELOPMENT_END.isoformat(),
            "expected_terminal": EXPECTED_TERMINAL.isoformat(),
            "fee_per_fill": engine.FEE,
            "base_slippage_per_fill": engine.BASE_SLIPPAGE,
            "stress_slippage_per_fill": engine.STRESS_SLIPPAGE,
            "execution": "closed UTC day signal, next open; real 1h stop path",
            "positioning": "about 1x after fills, fixed quantity while held",
        },
        "v1": {
            "long_config": asdict(long_config),
            "short_config": asdict(short_config),
        },
        "assets": {},
    }
    metric_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    path_rows: list[dict[str, Any]] = []

    for symbol, slug in ASSETS.items():
        hourly, funding, quality = load_snapshot(symbol, slug, manifest)
        book = transfer.build_book(symbol, hourly, quality, phase_hours=0)
        if pd.Timestamp(book.terminal_ts) != EXPECTED_TERMINAL:
            raise RuntimeError(
                f"{symbol}: terminal drift {book.terminal_ts}"
            )
        features = engine.build_features(book, hourly, funding)
        starts = {
            "development": boundary(book, COMMON_START),
            "researcher_exposed_audit": boundary(book, DEVELOPMENT_END),
            "full_history": boundary(book, COMMON_START),
        }
        ends = {
            "development": boundary(book, DEVELOPMENT_END),
            "researcher_exposed_audit": book.count,
            "full_history": book.count,
        }
        asset_payload: dict[str, Any] = {
            "data_quality": quality,
            "terminal_open": book.quality["terminal_open"],
            "windows": {},
        }
        for window in starts:
            asset_payload["windows"][window] = {}
            for variant, long_leg, short_leg in (
                ("combined", long_config, short_config),
                ("long_only", long_config, None),
                ("short_only", None, short_config),
            ):
                stresses = {
                    "base": (engine.BASE_SLIPPAGE, 0),
                    "stress_8bps": (engine.STRESS_SLIPPAGE, 0),
                    "one_day_extra_delay": (engine.BASE_SLIPPAGE, 1),
                }
                asset_payload["windows"][window][variant] = {}
                for stress, (slippage, lag) in stresses.items():
                    retain = (
                        window == "full_history"
                        and variant == "combined"
                        and stress == "base"
                    )
                    result = run_window(
                        engine,
                        book,
                        features,
                        long_leg,
                        short_leg,
                        start=starts[window],
                        end=ends[window],
                        slippage=slippage,
                        signal_lag=lag,
                        retain=retain,
                    )
                    asset_payload["windows"][window][variant][stress] = result.metrics
                    metric_rows.append(
                        {
                            "symbol": symbol,
                            "window": window,
                            "variant": variant,
                            "stress": stress,
                            **result.metrics,
                        }
                    )
                    if retain:
                        retained_base[symbol] = result
                        trade_rows.extend(
                            {"symbol": symbol, **trade} for trade in result.trades
                        )
                        path_rows.extend(
                            {"symbol": symbol, **row} for row in result.path
                        )
        payload["assets"][symbol] = asset_payload

    payload["equal_weight_portfolio"] = portfolio_metrics(retained_base)
    payload["hard_target"] = {
        symbol: {
            "equity_multiple_gte_20": (
                payload["assets"][symbol]["windows"]["full_history"]
                ["combined"]["base"]["equity_multiple"]
                >= 20.0
            ),
            "mdd_within_20pct": (
                payload["assets"][symbol]["windows"]["full_history"]
                ["combined"]["base"]["max_drawdown_pct"]
                >= -20.0
            ),
        }
        for symbol in ASSETS
    }
    payload["hard_target"]["all_pass"] = all(
        all(checks.values())
        for symbol, checks in payload["hard_target"].items()
        if symbol in ASSETS
    )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_ma7_shared_v1_long_history_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(
        json.dumps(clean_json(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame(metric_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_metrics.csv", index=False
    )
    pd.DataFrame(trade_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_trades.csv", index=False
    )
    pd.DataFrame(path_rows).to_csv(
        ARTIFACT_DIR / f"{stem}_path.csv", index=False
    )
    print(
        json.dumps(
            clean_json(
                {
                    "hard_target": payload["hard_target"],
                    "equal_weight_portfolio": payload[
                        "equal_weight_portfolio"
                    ],
                    "assets": {
                        symbol: payload["assets"][symbol]["windows"]
                        ["full_history"]["combined"]
                        for symbol in ASSETS
                    },
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

