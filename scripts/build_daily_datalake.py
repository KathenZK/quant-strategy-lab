"""
从 data/binance-recent1y 重采样到 data/binance-recent1y-daily（1d 粒度）。

- OHLCV  1h -> 1d: open=first, high=max, low=min, close=last, volume=sum
- funding 8h -> 1d: sum（日内累计资金费）
- OI      4h -> 1d: last
- basis   1h -> 1d: last
- liquidations: 原样复制（事件级），后续由策略侧按 frequency 聚合
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from signal_lab.data import DataLakeLayout, DatasetKind, MarketType, write_dataframe


SRC_ROOT = Path("data/binance-recent1y")
DST_ROOT = Path("data/binance-recent1y-daily")

SYMBOLS = ["btc_usdt_usdt", "eth_usdt_usdt", "sol_usdt_usdt"]
EXCHANGE = "binance"
MARKET_TYPE = MarketType.PERP


def _load_concat(glob_root: Path, symbol: str) -> pd.DataFrame:
    files = sorted(glob_root.glob(f"**/symbol={symbol}/**/*.parquet"))
    if not files:
        return pd.DataFrame()
    frames = [pd.read_parquet(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.drop_duplicates(subset=["ts", "symbol"], keep="last").sort_values("ts").reset_index(drop=True)


def _resample_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    index_df = df.set_index("ts")
    agg = index_df.resample("1D").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    ).dropna(subset=["open", "close"])
    meta_cols = [c for c in ("exchange", "symbol", "market_type", "base_asset", "quote_asset", "source") if c in df.columns]
    for col in meta_cols:
        agg[col] = df[col].iloc[0]
    agg = agg.reset_index().rename(columns={"ts": "ts"})
    return agg[["ts", "exchange", "symbol", "market_type", "base_asset", "quote_asset", "open", "high", "low", "close", "volume", "source"]]


def _resample_single_column(df: pd.DataFrame, columns: list[str], how: str) -> pd.DataFrame:
    index_df = df.set_index("ts")
    agg = index_df[columns].resample("1D").agg(how)
    meta_cols = [c for c in ("exchange", "symbol", "market_type", "base_asset", "quote_asset", "source") if c in df.columns]
    for col in meta_cols:
        agg[col] = df[col].iloc[0]
    agg = agg.dropna(subset=columns[:1])
    return agg.reset_index()


def _write(kind: DatasetKind, df: pd.DataFrame, symbol: str, layout: DataLakeLayout) -> None:
    if df.empty:
        return
    df = df.copy()
    df["date"] = df["ts"].dt.date.astype("string")
    partition_date = df["ts"].max().date()
    write_dataframe(
        df,
        layout=layout,
        layer="normalized",
        kind=kind,
        exchange=EXCHANGE,
        market_type=MARKET_TYPE,
        symbol=symbol.replace("_", "/").upper().replace("/USDT/USDT", "/USDT:USDT"),
        partition_date=partition_date,
    )


def _symbol_to_ccxt(symbol_underscore: str) -> str:
    # btc_usdt_usdt -> BTC/USDT:USDT
    parts = symbol_underscore.upper().split("_")
    return f"{parts[0]}/{parts[1]}:{parts[2]}"


def main() -> None:
    layout = DataLakeLayout(
        root_dir=DST_ROOT,
        raw_dir=DST_ROOT / "raw",
        normalized_dir=DST_ROOT / "normalized",
        features_dir=DST_ROOT / "features",
        reports_dir=Path("reports/binance-recent1y-daily"),
    )
    layout.ensure_directories()

    for symbol in SYMBOLS:
        ccxt_symbol = _symbol_to_ccxt(symbol)
        print(f"==> {ccxt_symbol}")

        ohlcv = _load_concat(SRC_ROOT / "normalized" / "ohlcv", symbol)
        ohlcv_daily = _resample_ohlcv(ohlcv)
        print(f"   ohlcv  {len(ohlcv)} -> {len(ohlcv_daily)}")
        _write(DatasetKind.OHLCV, ohlcv_daily, symbol, layout)

        funding = _load_concat(SRC_ROOT / "normalized" / "funding_rates", symbol)
        if not funding.empty:
            funding_daily = _resample_single_column(funding, ["funding_rate"], "sum")
            funding_daily["next_funding_ts"] = pd.NaT
            print(f"   funding  {len(funding)} -> {len(funding_daily)}")
            _write(DatasetKind.FUNDING_RATES, funding_daily, symbol, layout)

        oi = _load_concat(SRC_ROOT / "normalized" / "open_interest", symbol)
        if not oi.empty:
            extra_cols = [c for c in ("open_interest", "open_interest_value") if c in oi.columns]
            oi_daily = _resample_single_column(oi, extra_cols, "last")
            print(f"   oi     {len(oi)} -> {len(oi_daily)}")
            _write(DatasetKind.OPEN_INTEREST, oi_daily, symbol, layout)

        basis = _load_concat(SRC_ROOT / "normalized" / "basis_or_premium", symbol)
        if not basis.empty:
            num_cols = [c for c in basis.columns if c in {"basis", "basis_rate", "annualized_basis", "futures_price", "index_price", "mark_price", "premium_index"}]
            basis_daily = _resample_single_column(basis, num_cols, "last")
            print(f"   basis  {len(basis)} -> {len(basis_daily)}")
            _write(DatasetKind.BASIS, basis_daily, symbol, layout)

        liq = _load_concat(SRC_ROOT / "normalized" / "liquidations", symbol)
        if not liq.empty:
            liq_out = liq.copy()
            liq_out["date"] = liq_out["ts"].dt.date.astype("string")
            partition_date = liq_out["ts"].max().date()
            write_dataframe(
                liq_out,
                layout=layout,
                layer="normalized",
                kind=DatasetKind.LIQUIDATIONS,
                exchange=EXCHANGE,
                market_type=MARKET_TYPE,
                symbol=ccxt_symbol,
                partition_date=partition_date,
            )
            print(f"   liquidations  {len(liq)} rows (copied)")


if __name__ == "__main__":
    main()
