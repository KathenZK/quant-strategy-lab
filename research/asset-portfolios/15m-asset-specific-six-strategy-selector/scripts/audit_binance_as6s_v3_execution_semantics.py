from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

import audit_binance_as6s_clean_rsi_hf_robustness as clean
import as6s_engine


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v3_execution_semantics_2026-07-14.json"


def market(
    open_: list[float], high: list[float], low: list[float]
) -> clean.mii.MarketArrays:
    n = len(open_)
    ts = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC").to_numpy()
    zeros = np.zeros(n, dtype=np.float64)
    fifties = np.full(n, 50.0, dtype=np.float64)
    ones = np.ones(n, dtype=np.float64)
    return clean.mii.MarketArrays(
        ts=ts,
        open=np.asarray(open_, dtype=np.float64),
        high=np.asarray(high, dtype=np.float64),
        low=np.asarray(low, dtype=np.float64),
        adx14=zeros.copy(),
        rvol96=ones.copy(),
        ret16=zeros.copy(),
        ret48=zeros.copy(),
        ret96=zeros.copy(),
        h1_spread=zeros.copy(),
        h4_spread=zeros.copy(),
        macd_hist=zeros.copy(),
        rsi14=fifties,
        atr_pct96=ones.copy() * 0.01,
        atr_ratio96_672=ones.copy(),
    )


def state(n: int, direction: int = 1) -> clean.mii.SignalState:
    spec = clean.mii.SignalSpec(
        name="synthetic_rsi",
        kind="rsi_reversal",
        window=7,
        low=40.0,
        high=60.0,
    )
    return clean.mii.SignalState(
        spec=spec,
        signal_i=np.array([0], dtype=np.int64),
        directions=np.array([direction], dtype=np.int8),
        previous_signal_age=np.zeros(n, dtype=np.float64),
        churn192=np.zeros(n, dtype=np.float64),
    )


def fixed_exit(*, hold: int = 2) -> clean.mii.ExitSpec:
    return clean.mii.ExitSpec(
        kind="fixed",
        take_profit_pct=0.05,
        stop_pct=0.05,
        max_hold_bars=hold,
    )


def one_trade(
    market_: clean.mii.MarketArrays,
    *,
    delay: int = 1,
) -> clean.mii.EventTrade:
    trades = clean.robust_trades(
        market_,
        state(len(market_.open)),
        fixed_exit(),
        np.array([], dtype=np.int64),
        np.array([0.0], dtype=np.float64),
        slippage=0.0004,
        entry_delay_bars=delay,
    )
    if len(trades) != 1:
        raise AssertionError(f"expected one trade, got {len(trades)}")
    return trades[0]


def audit_timeout_open() -> dict[str, object]:
    # The forced-exit bar has an impossible-looking range.  A live-safe timeout
    # must fill at its open before observing that range.
    trade = one_trade(
        market(
            [100.0, 100.0, 100.0, 101.0, 100.0],
            [100.0, 102.0, 102.0, 130.0, 100.0],
            [100.0, 98.0, 98.0, 70.0, 100.0],
        )
    )
    passed = trade.exit_reason == "max_hold" and trade.exit_i == 3
    if not passed:
        raise AssertionError(
            f"timeout leaked intrabar range: {trade.exit_reason=} {trade.exit_i=}"
        )
    return {
        "pass": passed,
        "exit_reason": trade.exit_reason,
        "exit_i": trade.exit_i,
        "exit_price": trade.exit_price,
    }


def audit_same_bar_stop_first() -> dict[str, object]:
    trade = one_trade(
        market(
            [100.0, 100.0, 100.0, 100.0, 100.0],
            [100.0, 106.0, 100.0, 100.0, 100.0],
            [100.0, 94.0, 100.0, 100.0, 100.0],
        )
    )
    passed = trade.exit_reason == "stop_loss" and trade.exit_i == 1
    if not passed:
        raise AssertionError(
            f"same-bar ambiguity was not stop-first: {trade.exit_reason=}"
        )
    return {
        "pass": passed,
        "exit_reason": trade.exit_reason,
        "exit_i": trade.exit_i,
    }


def audit_gap_stop_open() -> dict[str, object]:
    trade = one_trade(
        market(
            [100.0, 100.0, 90.0, 90.0, 90.0],
            [100.0, 102.0, 91.0, 91.0, 91.0],
            [100.0, 98.0, 89.0, 89.0, 89.0],
        )
    )
    expected = 90.0 * (1.0 - 0.0004)
    passed = (
        trade.exit_reason == "stop_gap"
        and trade.exit_i == 2
        and np.isclose(trade.exit_price, expected)
    )
    if not passed:
        raise AssertionError(
            f"gap stop used stale trigger: {trade.exit_reason=} "
            f"{trade.exit_price=} {expected=}"
        )
    return {
        "pass": passed,
        "exit_reason": trade.exit_reason,
        "exit_i": trade.exit_i,
        "exit_price": trade.exit_price,
        "expected_exit_price": expected,
    }


def audit_k_plus_2_delay() -> dict[str, object]:
    trade = one_trade(
        market(
            [100.0, 150.0, 100.0, 100.0, 100.0],
            [100.0, 160.0, 101.0, 101.0, 101.0],
            [100.0, 140.0, 99.0, 99.0, 99.0],
        ),
        delay=2,
    )
    passed = trade.entry_i == 2 and np.isclose(trade.entry_price, 100.04)
    if not passed:
        raise AssertionError(
            f"K+2 did not enter at second next open: {trade.entry_i=} "
            f"{trade.entry_price=}"
        )
    return {
        "pass": passed,
        "entry_i": trade.entry_i,
        "entry_price": trade.entry_price,
    }


def audit_h1_known_time() -> dict[str, object]:
    ts = pd.date_range("2026-01-01", periods=500, freq="15min", tz="UTC")
    close = np.linspace(100.0, 150.0, len(ts))
    frame = pd.DataFrame(
        {
            "ts": ts,
            "open": close - 0.05,
            "high": close + 0.10,
            "low": close - 0.10,
            "close": close,
            "volume": np.full(len(ts), 1000.0),
        }
    )
    features = as6s_engine.add_features(frame)
    h1 = (
        frame.set_index("ts")
        .resample("1h", label="left", closed="left")
        .agg({"close": "last"})
        .dropna()
        .reset_index()
    )
    h1["known_ts"] = h1["ts"] + pd.Timedelta(hours=1)
    h1["expected"] = h1["close"].ewm(
        span=24, adjust=False, min_periods=24
    ).mean()
    checked = 0
    for row in features.loc[features["h1_ema_24"].notna()].itertuples():
        bar_known = row.ts + pd.Timedelta(minutes=15)
        available = h1.loc[h1["known_ts"] <= bar_known]
        if available.empty:
            continue
        expected = float(available.iloc[-1]["expected"])
        if not np.isclose(float(row.h1_ema_24), expected):
            raise AssertionError(
                f"H1 lookahead at {row.ts}: {row.h1_ema_24=} {expected=}"
            )
        checked += 1
    if checked < 100:
        raise AssertionError(f"insufficient H1 known-time checks: {checked}")
    return {"pass": True, "checked_15m_rows": checked}


def main() -> None:
    checks = {
        "timeout_open_ignores_forced_bar_range": audit_timeout_open(),
        "same_bar_stop_first": audit_same_bar_stop_first(),
        "gap_stop_uses_open_with_slippage": audit_gap_stop_open(),
        "k_plus_2_enters_second_next_open": audit_k_plus_2_delay(),
        "h1_features_respect_known_time": audit_h1_known_time(),
    }
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "execution_semantics_audit",
        "result": "PASS",
        "checks": checks,
    }
    OUTPUT.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            default=lambda value: value.item()
            if isinstance(value, np.generic)
            else str(value),
        ),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUTPUT), "result": "PASS"}, indent=2))


if __name__ == "__main__":
    main()
