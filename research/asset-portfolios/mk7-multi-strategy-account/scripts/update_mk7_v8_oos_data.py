"""Extend mk7-v8 research inputs to the latest common closed UTC hour.

Frozen family artifacts are never modified. Extended 1h candles and current-day
aggTrades are written under data/cache/mk7_v8_binance/ for OOS replay only.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
FAMILY = ROOT / "research/asset-portfolios/mk7-multi-strategy-account"
CACHE = ROOT / "data/cache/mk7_v8_binance"
KLINES = CACHE / "klines"
FUNDING = CACHE / "funding"
FEATURES = CACHE / "features"
TOP_LSR = CACHE / "top_lsr"
AGG = CACHE / "aggTrades/HYPEUSDT"
LOGS = CACHE / "logs"

FAPI = "https://fapi.binance.com"
MID_LO = 2_000.0
MID_HI = 20_000.0

FROZEN_1H = {
    "TRX": ROOT
    / "research/trx/1h-adaptive-regime/artifacts/trx_binance_1h_closed_klines_2y.parquet",
    "SOL": ROOT
    / "research/sol/1h-adaptive-regime/artifacts/sol_binance_1h_closed_klines_2y.parquet",
    "HYPE": ROOT
    / "research/hype/1h-adaptive-regime/artifacts/hype_binance_1h_closed_klines.parquet",
    "ETH": ROOT
    / "research/eth/1h-adaptive-regime/artifacts/eth_binance_1h_closed_klines_2y.parquet",
    "BTC": ROOT
    / "research/btc/1h-adaptive-regime/artifacts/btc_binance_1h_closed_klines_2y.parquet",
    "BNB": ROOT
    / "research/bnb/1h-adaptive-regime/artifacts/bnb_binance_1h_closed_klines_2y.parquet",
}


def load_downloader() -> Any:
    path = FAMILY / "scripts/download_mk7_v8_binance_missing_data.py"
    spec = importlib.util.spec_from_file_location("mk7_downloader", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load downloader: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


DL = load_downloader()


def latest_closed_common_end() -> pd.Timestamp:
    """Exclusive endpoint shared by 1h and lower-frequency closed bars."""
    return pd.Timestamp.now(tz="UTC").floor("h")


def append_kline_file(
    path: Path,
    *,
    symbol: str,
    interval: str,
    end: pd.Timestamp,
    timeout: float = 60.0,
) -> dict[str, Any]:
    frame = pd.read_parquet(path)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    step = pd.Timedelta(interval)
    start = frame["ts"].max() + step
    if start < end:
        extra = DL.fetch_paginated_klines(
            "/fapi/v1/premiumIndexKlines"
            if "premium" in str(path)
            else "/fapi/v1/klines",
            symbol=symbol,
            interval=interval,
            start=start,
            end=end,
            timeout=timeout,
        )
        if not extra.empty:
            now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
            extra = extra.loc[pd.to_numeric(extra["close_time"]) < now_ms].copy()
            frame = pd.concat([frame, extra], ignore_index=True, sort=False)
    frame = (
        frame.drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .loc[lambda x: x["ts"] < end]
        .reset_index(drop=True)
    )
    frame.to_parquet(path, index=False)
    return {
        "path": str(path.relative_to(ROOT)),
        "rows": len(frame),
        "first_ts": frame["ts"].iloc[0].isoformat(),
        "last_ts": frame["ts"].iloc[-1].isoformat(),
    }


def build_extended_1h(
    asset: str, end: pd.Timestamp, timeout: float = 60.0
) -> tuple[Path, dict[str, Any]]:
    frozen = pd.read_parquet(FROZEN_1H[asset])
    frozen["ts"] = pd.to_datetime(frozen["ts"], utc=True)
    start = frozen["ts"].max() + pd.Timedelta(hours=1)
    extra = DL.fetch_paginated_klines(
        "/fapi/v1/klines",
        symbol=f"{asset}USDT",
        interval="1h",
        start=start,
        end=end,
        timeout=timeout,
    )
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    if not extra.empty:
        extra = extra.loc[pd.to_numeric(extra["close_time"]) < now_ms].copy()
        extra["exchange"] = "binance"
        extra["symbol"] = f"{asset.lower()}_usdt"
        extra["market_type"] = "perp"
        extra["timeframe"] = "1h"
        extra["base_asset"] = asset.lower()
        extra["quote_asset"] = "usdt"
        extra["vwap"] = extra["quote_volume"] / extra["volume"].replace(0.0, np.nan)
        extra["is_closed"] = True
        extra["source"] = "binance_futures_kline_api_oos"
    combined = pd.concat([frozen, extra], ignore_index=True, sort=False)
    combined = (
        combined.drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .loc[lambda x: x["ts"] < end]
        .reset_index(drop=True)
    )
    out = KLINES / f"{asset.lower()}usdt_1h_oos_extended.parquet"
    combined.to_parquet(out, index=False)
    return out, {
        "path": str(out.relative_to(ROOT)),
        "rows": len(combined),
        "frozen_last_ts": frozen["ts"].max().isoformat(),
        "last_ts": combined["ts"].max().isoformat(),
        "added_rows": len(combined) - len(frozen),
    }


def fetch_top_lsr_rest(
    start: pd.Timestamp, end: pd.Timestamp, timeout: float = 60.0
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor < end:
        chunk_end = min(end, cursor + pd.Timedelta(days=1))
        params = {
            "symbol": "HYPEUSDT",
            "period": "5m",
            "limit": 500,
            "startTime": DL.ms(cursor),
            "endTime": DL.ms(chunk_end),
        }
        batch = DL.request_json(
            f"{FAPI}/futures/data/topLongShortPositionRatio?{urlencode(params)}",
            timeout=timeout,
        )
        if isinstance(batch, list):
            rows.extend(batch)
        cursor = chunk_end
        time.sleep(0.05)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame["ts"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    frame["top_lsr_pos"] = pd.to_numeric(frame["longShortRatio"], errors="coerce")
    frame["longAccount"] = pd.to_numeric(frame["longAccount"], errors="coerce")
    frame["shortAccount"] = pd.to_numeric(frame["shortAccount"], errors="coerce")
    frame["source"] = "binance_fapi_topLongShortPositionRatio"
    return frame[
        ["ts", "symbol", "longAccount", "shortAccount", "top_lsr_pos", "source"]
    ]


def append_top_lsr(end: pd.Timestamp) -> dict[str, Any]:
    path = TOP_LSR / "hype_usdt_top_lsr_pos_5m.parquet"
    old = pd.read_parquet(path)
    old["ts"] = pd.to_datetime(old["ts"], utc=True)
    start = old["ts"].max() + pd.Timedelta(minutes=5)
    extra = fetch_top_lsr_rest(start, end)
    combined = pd.concat([old, extra], ignore_index=True, sort=False)
    combined = (
        combined.drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .loc[lambda x: x["ts"] < end]
        .dropna(subset=["top_lsr_pos"])
        .reset_index(drop=True)
    )
    combined.to_parquet(path, index=False)
    return {
        "path": str(path.relative_to(ROOT)),
        "rows": len(combined),
        "last_ts": combined["ts"].max().isoformat(),
        "rest_rows_added": len(extra),
    }


def fetch_current_aggtrades(
    start: pd.Timestamp, end: pd.Timestamp, timeout: float = 60.0
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    params = {
        "symbol": "HYPEUSDT",
        "startTime": DL.ms(start),
        "endTime": DL.ms(end) - 1,
        "limit": 1000,
    }
    batch = DL.request_json(f"{FAPI}/fapi/v1/aggTrades?{urlencode(params)}", timeout=timeout)
    while isinstance(batch, list) and batch:
        rows.extend(batch)
        last_id = int(batch[-1]["a"])
        last_ts = pd.Timestamp(int(batch[-1]["T"]), unit="ms", tz="UTC")
        if len(batch) < 1000 or last_ts >= end:
            break
        params = {"symbol": "HYPEUSDT", "fromId": last_id + 1, "limit": 1000}
        batch = DL.request_json(
            f"{FAPI}/fapi/v1/aggTrades?{urlencode(params)}", timeout=timeout
        )
        time.sleep(0.025)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows).rename(
        columns={
            "a": "agg_trade_id",
            "p": "price",
            "q": "quantity",
            "f": "first_trade_id",
            "l": "last_trade_id",
            "T": "transact_time",
            "m": "is_buyer_maker",
        }
    )
    frame["ts"] = pd.to_datetime(frame["transact_time"], unit="ms", utc=True)
    frame = frame.loc[(frame["ts"] >= start) & (frame["ts"] < end)].copy()
    return (
        frame[
            [
                "agg_trade_id",
                "price",
                "quantity",
                "first_trade_id",
                "last_trade_id",
                "transact_time",
                "is_buyer_maker",
                "ts",
            ]
        ]
        .drop_duplicates("agg_trade_id", keep="last")
        .sort_values("agg_trade_id")
        .reset_index(drop=True)
    )


def aggregate_partial_flow(raw: pd.DataFrame) -> pd.DataFrame:
    price = pd.to_numeric(raw["price"], errors="coerce")
    qty = pd.to_numeric(raw["quantity"], errors="coerce")
    maker = raw["is_buyer_maker"].astype(str).str.lower().isin({"true", "1"})
    quote = price * qty
    buy_quote = np.where(~maker, quote, 0.0)
    sell_quote = np.where(maker, quote, 0.0)
    mid_mask = (quote >= MID_LO) & (quote < MID_HI)
    big_mask = quote >= MID_HI
    part = pd.DataFrame(
        {
            "ts": raw["ts"],
            "buy_quote": buy_quote,
            "sell_quote": sell_quote,
            "mid_buy": np.where(mid_mask, buy_quote, 0.0),
            "mid_sell": np.where(mid_mask, sell_quote, 0.0),
            "big_buy": np.where(big_mask, buy_quote, 0.0),
            "big_sell": np.where(big_mask, sell_quote, 0.0),
        }
    ).set_index("ts")
    return part.resample("15min", label="left", closed="left").sum(min_count=1)


def append_current_flow(end: pd.Timestamp) -> dict[str, Any]:
    flow_path = FEATURES / "hype_usdt_15m_cvd_flow_single_venue.parquet"
    flow = pd.read_parquet(flow_path)
    flow["ts"] = pd.to_datetime(flow["ts"], utc=True)
    start = flow["ts"].max() + pd.Timedelta(minutes=15)
    raw = fetch_current_aggtrades(start, end)
    raw_path = AGG / "hypeusdt_aggtrades_current_partial.parquet"
    raw.to_parquet(raw_path, index=False)
    if not raw.empty:
        bars = aggregate_partial_flow(raw).reset_index()
        flow = pd.concat([flow, bars], ignore_index=True, sort=False)
    flow = (
        flow.drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .loc[lambda x: x["ts"] < end]
        .reset_index(drop=True)
    )
    flow["net_flow"] = flow["buy_quote"] - flow["sell_quote"]
    flow["total_flow"] = flow["buy_quote"] + flow["sell_quote"]
    flow["mid_imb"] = (flow["mid_buy"] - flow["mid_sell"]) / (
        flow["mid_buy"] + flow["mid_sell"]
    ).replace(0.0, np.nan)
    flow["big_imb"] = (flow["big_buy"] - flow["big_sell"]) / (
        flow["big_buy"] + flow["big_sell"]
    ).replace(0.0, np.nan)
    flow["cvd_all"] = flow["net_flow"].cumsum()
    flow["cvd_mid"] = (flow["mid_buy"] - flow["mid_sell"]).cumsum()
    flow["cvd_big"] = (flow["big_buy"] - flow["big_sell"]).cumsum()
    flow.to_parquet(flow_path, index=False)
    return {
        "path": str(flow_path.relative_to(ROOT)),
        "rows": len(flow),
        "last_ts": flow["ts"].max().isoformat(),
        "partial_aggtrades_rows": len(raw),
        "partial_path": str(raw_path.relative_to(ROOT)),
    }


def validate_continuity(path: Path, freq: str) -> dict[str, Any]:
    frame = pd.read_parquet(path)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    idx = pd.DatetimeIndex(frame["ts"].sort_values())
    expected = pd.date_range(idx.min(), idx.max(), freq=freq)
    gaps = expected.difference(idx)
    return {
        "rows": len(frame),
        "first_ts": idx.min().isoformat(),
        "last_ts": idx.max().isoformat(),
        "duplicates": int(idx.duplicated().sum()),
        "gaps": len(gaps),
        "first_gaps": [ts.isoformat() for ts in gaps[:10]],
    }


def main() -> None:
    for path in (KLINES, FUNDING, FEATURES, TOP_LSR, AGG, LOGS):
        path.mkdir(parents=True, exist_ok=True)
    end = latest_closed_common_end()
    outputs: dict[str, Any] = {"common_closed_end": end.isoformat()}

    for asset in FROZEN_1H:
        path, detail = build_extended_1h(asset, end)
        outputs[f"{asset.lower()}_1h"] = detail
        outputs[f"{asset.lower()}_1h_quality"] = validate_continuity(path, "1h")

    for name, path, symbol, interval in (
        (
            "hype_1m",
            KLINES / "hypeusdt_1m_with_taker.parquet",
            "HYPEUSDT",
            "1min",
        ),
        (
            "hype_15m",
            KLINES / "hypeusdt_15m_with_taker.parquet",
            "HYPEUSDT",
            "15min",
        ),
        (
            "btc_15m",
            KLINES / "btcusdt_15m_with_taker.parquet",
            "BTCUSDT",
            "15min",
        ),
        (
            "premium_15m",
            CACHE / "premium/hype_usdt_premium_index_15m.parquet",
            "HYPEUSDT",
            "15min",
        ),
    ):
        outputs[name] = append_kline_file(
            path,
            symbol=symbol,
            interval={"1min": "1m", "15min": "15m"}[interval],
            end=end,
        )
        outputs[f"{name}_quality"] = validate_continuity(path, interval)

    outputs["top_lsr"] = append_top_lsr(end)
    outputs["top_lsr_quality"] = validate_continuity(
        TOP_LSR / "hype_usdt_top_lsr_pos_5m.parquet", "5min"
    )
    outputs["cvd_flow"] = append_current_flow(end)
    outputs["cvd_flow_quality"] = validate_continuity(
        FEATURES / "hype_usdt_15m_cvd_flow_single_venue.parquet", "15min"
    )

    funding_quality: dict[str, Any] = {}
    for asset in FROZEN_1H:
        path = (
            ROOT
            / "data/normalized/funding/exchange=binance/market_type=perp"
            / f"symbol={asset.lower()}_usdt_usdt/funding.parquet"
        )
        frame = pd.read_parquet(path)
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        funding_quality[asset] = {
            "rows": len(frame),
            "last_ts": frame["ts"].max().isoformat(),
            "duplicates": int(frame["ts"].duplicated().sum()),
            "nulls": int(frame["funding_rate"].isna().sum()),
        }
    outputs["funding_quality"] = funding_quality

    out = LOGS / "oos_data_update_2026-07-13.json"
    out.write_text(json.dumps(outputs, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(outputs, indent=2, ensure_ascii=False))
    print("wrote", out)


if __name__ == "__main__":
    main()
