"""Shared research utilities for BIN-15M-EMAX-LGBM.

Implements the frozen research contract
(specs/bin-15m-emax-lgbm-research-contract-2026-07-23.md): signal definition,
conservative fill rules, cost model, point-in-time universe rules, and the
development/locked-OOS data boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-ema-cross-lightgbm-event-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CACHE_DIR = ROOT / "data/cache/emax_15m"

KLINE_15M_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
FUNDING_ROOT = ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
INVENTORY_CSV = ARTIFACT_DIR / "binance_usdm_15m_inventory_2026-07-23.csv"

# --- frozen contract constants -------------------------------------------------
EMA_FAST = 21
EMA_SLOW = 96
ATR_LEN = 14
HORIZON_BARS = 96
WARMUP_BARS = 4 * EMA_SLOW  # indicator settling before events are valid

BRACKETS = {"b2_1": (2.0, 1.0), "b3_15": (3.0, 1.5), "b4_2": (4.0, 2.0)}

FEE_PER_FILL = 0.001
SLIP_PER_FILL = 0.0004
ROUND_TRIP_COST = 2.0 * (FEE_PER_FILL + SLIP_PER_FILL)

MIN_LISTING_DAYS = 30
MIN_ADV_USDT = 10_000_000.0
MIN_COVERAGE = 0.95
DELIST_GUARD_DAYS = 7
TRADING_POOL_SIZE = 120

DEV_START = pd.Timestamp("2020-01-01", tz="UTC")
LOCKED_OOS_START = pd.Timestamp("2026-01-01", tz="UTC")
LOCKED_OOS_END = pd.Timestamp("2026-07-01", tz="UTC")
# last entry whose 96-bar label window closes strictly before the locked OOS
DEV_ENTRY_CUTOFF = LOCKED_OOS_START - pd.Timedelta(minutes=15 * (HORIZON_BARS + 1))

STABLE_FIAT_BASES = {
    "USDC", "BUSD", "TUSD", "USDP", "FDUSD", "DAI", "SUSD", "EUR", "AEUR",
    "GBP", "AUD", "BRL", "USD1", "USDE", "XUSD", "BFUSD",
}


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET enable_progress_bar=false")
    return con


def sym_key_expr(column: str = "symbol") -> str:
    return f"replace({column}, '/USDT:USDT', '')"


def kline_globs() -> list[str]:
    return [
        str(KLINE_15M_ROOT / "date=*" / "*.parquet"),
        str(KLINE_15M_ROOT / "source=binance_vision_monthly" / "month=*" / "*.parquet"),
    ]


def funding_globs() -> list[str]:
    return [
        str(FUNDING_ROOT / "date=*" / "*.parquet"),
        str(FUNDING_ROOT / "source=binance_vision_monthly" / "month=*" / "*.parquet"),
    ]


def symbol_cache_dir() -> Path:
    return CACHE_DIR / "klines_by_symbol"


def ensure_symbol_partition_cache(*, rebuild: bool = False) -> Path:
    """One-off repartition of the 15m lake into per-symbol parquet partitions."""
    target = symbol_cache_dir()
    marker = target / "_build_complete.json"
    if marker.exists() and not rebuild:
        return target
    if target.exists():
        import shutil

        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    con = connect()
    globs = ", ".join(f"'{glob}'" for glob in kline_globs())
    con.execute(
        f"""
        COPY (
            SELECT
                {sym_key_expr()} AS sym_key,
                ts, open, high, low, close,
                volume, quote_volume, trade_count,
                taker_buy_volume, taker_buy_quote_volume
            FROM read_parquet([{globs}], union_by_name=true)
            WHERE symbol IS NOT NULL
        ) TO '{target}' (FORMAT PARQUET, PARTITION_BY (sym_key), COMPRESSION ZSTD)
        """
    )
    rows = con.execute(
        f"SELECT count(*) FROM read_parquet('{target}/**/*.parquet')"
    ).fetchone()[0]
    import json

    marker.write_text(
        json.dumps(
            {"rows": int(rows), "generated_at": pd.Timestamp.now("UTC").isoformat()}
        ),
        encoding="utf-8",
    )
    return target


def list_cached_symbols() -> list[str]:
    return sorted(
        path.name.removeprefix("sym_key=")
        for path in symbol_cache_dir().glob("sym_key=*")
        if path.is_dir()
    )


def load_symbol_frame(sym_key: str) -> pd.DataFrame:
    con = connect()
    frame = con.execute(
        f"""
        SELECT * FROM read_parquet('{symbol_cache_dir()}/sym_key={sym_key}/*.parquet')
        ORDER BY ts
        """
    ).fetch_df()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    if frame["ts"].duplicated().any():
        raise RuntimeError(f"duplicate 15m timestamps for {sym_key}")
    return frame


def build_daily_stats(*, rebuild: bool = False) -> pd.DataFrame:
    """Per-symbol per-UTC-day quote volume and bar coverage, cached."""
    path = CACHE_DIR / "daily_stats.parquet"
    if path.exists() and not rebuild:
        return pd.read_parquet(path)
    con = connect()
    frame = con.execute(
        f"""
        SELECT
            sym_key,
            CAST(date_trunc('day', ts) AS DATE) AS day,
            sum(quote_volume) AS quote_volume,
            count(*) AS bars
        FROM read_parquet('{symbol_cache_dir()}/**/*.parquet', hive_partitioning=true)
        GROUP BY 1, 2
        ORDER BY 1, 2
        """
    ).fetch_df()
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return frame


@dataclass(slots=True)
class UniverseTables:
    """Point-in-time eligibility and trading-pool membership per symbol-day."""

    eligibility: pd.DataFrame  # sym_key, day, eligible, in_trading_pool, adv_30d
    first_day: dict[str, pd.Timestamp]
    last_day: dict[str, pd.Timestamp]


def excluded_bases(inventory_csv: Path = INVENTORY_CSV) -> set[str]:
    """Stable/fiat bases plus current non-COIN underlyings from the inventory."""
    out = set(STABLE_FIAT_BASES)
    inventory = pd.read_csv(inventory_csv, dtype={"symbol": str})
    known = inventory.loc[inventory["in_current_exchange_info"].fillna(False)]
    non_coin = known.loc[
        known["current_underlying_type"].notna()
        & (known["current_underlying_type"] != "COIN"),
        "symbol",
    ]
    out.update(symbol.removesuffix("USDT") for symbol in non_coin)
    return out


def build_universe(daily: pd.DataFrame) -> UniverseTables:
    """Rolling 30-day point-in-time universe.

    Eligibility for day D uses only days strictly before D. A symbol is
    eligible when listed >= 30 days, trailing 30d mean daily quote volume >=
    MIN_ADV_USDT, trailing 30d bar coverage >= MIN_COVERAGE, and D is at least
    DELIST_GUARD_DAYS before the symbol's final data day (for dead symbols).
    """
    excluded = excluded_bases()
    frames = []
    first_day: dict[str, pd.Timestamp] = {}
    last_day: dict[str, pd.Timestamp] = {}
    archive_end = pd.Timestamp(daily["day"].max())
    for sym_key, group in daily.groupby("sym_key", sort=True):
        group = group.sort_values("day").set_index(pd.DatetimeIndex(group["day"]))
        full = group.reindex(
            pd.date_range(group.index.min(), group.index.max(), freq="D")
        )
        full["quote_volume"] = full["quote_volume"].fillna(0.0)
        full["bars"] = full["bars"].fillna(0)
        adv = full["quote_volume"].rolling(30, min_periods=30).mean().shift(1)
        coverage = (
            full["bars"].rolling(30, min_periods=30).sum().shift(1) / (30.0 * 96.0)
        )
        listed_days = np.arange(len(full))
        sym_first = full.index.min()
        sym_last = full.index.max()
        first_day[sym_key] = sym_first
        last_day[sym_key] = sym_last
        delist_cut = (
            sym_last - pd.Timedelta(days=DELIST_GUARD_DAYS)
            if sym_last < archive_end - pd.Timedelta(days=2)
            else sym_last
        )
        eligible = (
            (listed_days >= MIN_LISTING_DAYS)
            & (adv.to_numpy() >= MIN_ADV_USDT)
            & (coverage.to_numpy() >= MIN_COVERAGE)
            & (full.index <= delist_cut)
            & (sym_key not in excluded)
        )
        frames.append(
            pd.DataFrame(
                {
                    "sym_key": sym_key,
                    "day": full.index,
                    "eligible": eligible,
                    "adv_30d": adv.to_numpy(),
                }
            )
        )
    eligibility = pd.concat(frames, ignore_index=True)
    eligibility["rank"] = (
        eligibility.loc[eligibility["eligible"]]
        .groupby("day")["adv_30d"]
        .rank(ascending=False, method="first")
    )
    eligibility["in_trading_pool"] = eligibility["eligible"] & (
        eligibility["rank"] <= TRADING_POOL_SIZE
    )
    eligibility = eligibility.drop(columns="rank")
    return UniverseTables(eligibility=eligibility, first_day=first_day, last_day=last_day)


def load_funding() -> pd.DataFrame:
    con = connect()
    globs = ", ".join(f"'{glob}'" for glob in funding_globs())
    frame = con.execute(
        f"""
        SELECT {sym_key_expr()} AS sym_key, ts, funding_rate
        FROM read_parquet([{globs}], union_by_name=true)
        WHERE funding_rate IS NOT NULL
        ORDER BY sym_key, ts
        """
    ).fetch_df()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.drop_duplicates(["sym_key", "ts"], keep="last")
    return frame


def compute_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    close = frame["close"]
    frame = frame.copy()
    frame["ema_fast"] = close.ewm(span=EMA_FAST, adjust=False).mean()
    frame["ema_slow"] = close.ewm(span=EMA_SLOW, adjust=False).mean()
    prev_close = close.shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    frame["atr"] = true_range.ewm(alpha=1.0 / ATR_LEN, adjust=False).mean()
    return frame


def detect_cross_indices(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Signal-bar indices for golden (long) and death (short) crosses."""
    fast = frame["ema_fast"].to_numpy()
    slow = frame["ema_slow"].to_numpy()
    prev_le = fast[:-1] <= slow[:-1]
    prev_ge = fast[:-1] >= slow[:-1]
    now_gt = fast[1:] > slow[1:]
    now_lt = fast[1:] < slow[1:]
    golden = np.flatnonzero(prev_le & now_gt) + 1
    death = np.flatnonzero(prev_ge & now_lt) + 1
    return golden, death


@dataclass(slots=True)
class BracketOutcome:
    label: np.ndarray  # 0=SL first, 1=TP first, 2=timeout
    exit_index: np.ndarray
    exit_price: np.ndarray
    gross_ret: np.ndarray  # fraction of notional, signed by side
    holding_bars: np.ndarray


def label_bracket(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    entry_index: np.ndarray,
    side: int,
    entry_price: np.ndarray,
    atr: np.ndarray,
    k_tp: float,
    k_sl: float,
) -> BracketOutcome:
    """First-touch labels over HORIZON_BARS with the frozen conservative rules.

    Bar priority: opening gap through SL -> SL at open; opening gap through TP
    -> TP at open; intrabar SL+TP same bar -> SL at stop price; SL; TP. The
    entry bar itself participates intrabar only (its open is the entry fill).
    """
    events = len(entry_index)
    labels = np.full(events, 2, dtype=np.int8)
    exit_index = entry_index + HORIZON_BARS
    exit_price = open_[np.minimum(exit_index, len(open_) - 1)].astype(float)

    tp_px = entry_price + side * k_tp * atr
    sl_px = entry_price - side * k_sl * atr

    offsets = np.arange(HORIZON_BARS)
    window_index = entry_index[:, None] + offsets[None, :]
    window_open = open_[window_index]
    window_high = high[window_index]
    window_low = low[window_index]

    if side > 0:
        gap_sl = window_open <= sl_px[:, None]
        gap_tp = window_open >= tp_px[:, None]
        hit_sl = window_low <= sl_px[:, None]
        hit_tp = window_high >= tp_px[:, None]
    else:
        gap_sl = window_open >= sl_px[:, None]
        gap_tp = window_open <= tp_px[:, None]
        hit_sl = window_high >= sl_px[:, None]
        hit_tp = window_low <= tp_px[:, None]
    # the entry bar's open is the entry fill; it cannot gap
    gap_sl[:, 0] = False
    gap_tp[:, 0] = False
    sl_any = gap_sl | hit_sl
    tp_any = gap_tp | hit_tp

    first_sl = np.where(sl_any.any(axis=1), sl_any.argmax(axis=1), HORIZON_BARS)
    first_tp = np.where(tp_any.any(axis=1), tp_any.argmax(axis=1), HORIZON_BARS)

    sl_wins = first_sl < first_tp
    tp_wins = first_tp < first_sl
    same_bar = (first_sl == first_tp) & (first_sl < HORIZON_BARS)

    event_rows = np.arange(events)
    # same-bar resolution
    if same_bar.any():
        bar = first_sl[same_bar]
        rows = event_rows[same_bar]
        bar_gap_sl = gap_sl[rows, bar]
        bar_gap_tp = gap_tp[rows, bar] & ~bar_gap_sl
        # gap-through SL -> SL at open; gap-through TP -> TP at open;
        # otherwise conservative SL at stop price
        sl_mask = np.zeros(events, dtype=bool)
        tp_mask = np.zeros(events, dtype=bool)
        sl_mask[rows[~bar_gap_tp]] = True
        tp_mask[rows[bar_gap_tp]] = True
        sl_wins = sl_wins | sl_mask
        tp_wins = tp_wins | tp_mask

    def fills(first: np.ndarray, gap: np.ndarray, barrier_px: np.ndarray) -> np.ndarray:
        rows = event_rows
        bar = np.minimum(first, HORIZON_BARS - 1)
        gap_fill = gap[rows, bar]
        return np.where(gap_fill, window_open[rows, bar], barrier_px)

    sl_fill = fills(first_sl, gap_sl, sl_px)
    tp_fill = fills(first_tp, gap_tp, tp_px)

    labels[sl_wins] = 0
    labels[tp_wins] = 1
    exit_index = np.where(sl_wins, entry_index + first_sl, exit_index)
    exit_index = np.where(tp_wins, entry_index + first_tp, exit_index)
    exit_price = np.where(sl_wins, sl_fill, exit_price)
    exit_price = np.where(tp_wins, tp_fill, exit_price)

    gross = side * (exit_price / entry_price - 1.0)
    holding = exit_index - entry_index
    return BracketOutcome(
        label=labels,
        exit_index=exit_index.astype(np.int64),
        exit_price=exit_price.astype(float),
        gross_ret=gross.astype(float),
        holding_bars=holding.astype(np.int64),
    )


def funding_cost(
    funding_ts: np.ndarray,
    funding_cum: np.ndarray,
    entry_ts: np.ndarray,
    exit_ts: np.ndarray,
    side: int,
) -> np.ndarray:
    """Signed funding cost fraction over (entry_ts, exit_ts]; long pays positive."""
    if len(funding_ts) == 0:
        return np.zeros(len(entry_ts))
    lo = np.searchsorted(funding_ts, entry_ts, side="right")
    hi = np.searchsorted(funding_ts, exit_ts, side="right")
    window_sum = funding_cum[hi] - funding_cum[lo]
    return side * window_sum


def prepare_funding_lookup(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    ts = frame["ts"].to_numpy(dtype="datetime64[ns]")
    cum = np.concatenate([[0.0], np.cumsum(frame["funding_rate"].to_numpy())])
    return ts, cum


class CalibratedModel:
    """LightGBM 3-class model with per-class isotonic calibration.

    Lives in an importable module (not __main__) so joblib pickles stay
    loadable across scripts.
    """

    def __init__(self, model, calibrators):
        self.model = model
        self.calibrators = calibrators

    def predict_proba(self, features) -> np.ndarray:
        raw = self.model.predict_proba(features)
        adjusted = np.column_stack(
            [
                calibrator.predict(raw[:, k]) if calibrator is not None else raw[:, k]
                for k, calibrator in enumerate(self.calibrators)
            ]
        )
        total = adjusted.sum(axis=1, keepdims=True)
        total[total <= 0] = 1.0
        return adjusted / total
