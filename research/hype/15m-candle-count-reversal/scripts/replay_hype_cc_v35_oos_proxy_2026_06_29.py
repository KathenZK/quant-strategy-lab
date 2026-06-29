from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
INTRABAR_PATH = (
    ROOT
    / "archive/code/platform/src/strategy_lab/strategies/candle_count_short/intrabar_backtest.py"
)
ARCHIVE_REPLAY_PATH = (
    ROOT / "archive/scripts/research/research_hype_v35_dry_run_recovery.py"
)
ARTIFACT_PATH = (
    ROOT
    / "research/hype/15m-candle-count-reversal/artifacts/"
    "hype_cc_v35_oos_proxy_review_2026-06-29.json"
)


def _load_archive_replay_module():
    spec_b = importlib.util.spec_from_file_location(
        "strategy_lab.strategies.candle_count_short.intrabar_backtest",
        INTRABAR_PATH,
    )
    if spec_b is None or spec_b.loader is None:
        raise RuntimeError(f"cannot load intrabar replay module: {INTRABAR_PATH}")
    intrabar = importlib.util.module_from_spec(spec_b)
    sys.modules.setdefault(
        "strategy_lab.strategies", types.ModuleType("strategy_lab.strategies")
    )
    sys.modules.setdefault(
        "strategy_lab.strategies.candle_count_short",
        types.ModuleType("strategy_lab.strategies.candle_count_short"),
    )
    sys.modules[
        "strategy_lab.strategies.candle_count_short.intrabar_backtest"
    ] = intrabar
    spec_b.loader.exec_module(intrabar)

    spec = importlib.util.spec_from_file_location(
        "hype_v35_replay_2026_06_29", ARCHIVE_REPLAY_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load archived V35 replay: {ARCHIVE_REPLAY_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["hype_v35_replay_2026_06_29"] = module
    spec.loader.exec_module(module)
    return module


def _load_ohlcv_proxy_frame() -> pd.DataFrame:
    root = (
        ROOT
        / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
    )
    files = sorted(root.glob("date=*/symbol=hype_usdt_usdt.parquet"))
    if not files:
        raise FileNotFoundError(f"no HYPEUSDT 15m OHLCV files under {root}")

    trade = pd.concat((pd.read_parquet(path) for path in files), ignore_index=True)
    trade["ts"] = pd.to_datetime(trade["ts"], utc=True)
    if "is_closed" in trade.columns:
        trade = trade.loc[trade["is_closed"].fillna(True)]
    trade = trade.sort_values("ts").drop_duplicates("ts", keep="last").set_index("ts")

    frame = trade[["open", "high", "low", "close", "volume"]].copy()
    frame["mark_high"] = frame["high"]
    frame["mark_low"] = frame["low"]

    funding_root = (
        ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
    )
    funding_files = sorted(funding_root.glob("date=*/symbol=hype_usdt_usdt.parquet"))
    if funding_files:
        funding = pd.concat(
            (pd.read_parquet(path) for path in funding_files), ignore_index=True
        )
        funding["ts"] = pd.to_datetime(funding["ts"], utc=True).dt.floor("15min")
        funding_rate = (
            funding.sort_values("ts")
            .drop_duplicates("ts", keep="last")
            .set_index("ts")["funding_rate"]
        )
        frame["funding_rate"] = funding_rate.reindex(frame.index).fillna(0.0)
    else:
        frame["funding_rate"] = 0.0
    return frame.sort_index()


def _coverage(frame: pd.DataFrame) -> dict[str, Any]:
    index = pd.DatetimeIndex(frame.index)
    expected = pd.date_range(index.min(), index.max(), freq="15min", tz="UTC")
    missing = expected.difference(index)
    return {
        "rows": int(len(frame)),
        "start": index.min().isoformat(),
        "end": index.max().isoformat(),
        "missing_15m_bars": int(len(missing)),
        "columns": list(frame.columns),
    }


def _run_window(module, frame: pd.DataFrame, name: str, start: str, end: str | None):
    config = module.hype_v35_config()
    run = module.run_v35(frame, config, trade_start=start, trade_end=end)
    trades = run.trades.copy()
    equity = run.equity_curve
    drawdown = equity / equity.cummax() - 1.0
    if trades.empty:
        return {
            "name": name,
            "start": equity.index[0].isoformat(),
            "end": equity.index[-1].isoformat(),
            "return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "exit_mix": {},
            "long_short": {},
            "first_entry": None,
            "last_exit": None,
        }
    return {
        "name": name,
        "start": equity.index[0].isoformat(),
        "end": equity.index[-1].isoformat(),
        "return_pct": round(float((equity.iloc[-1] - 1.0) * 100.0), 4),
        "max_drawdown_pct": round(float(drawdown.min() * 100.0), 4),
        "trades": int(len(trades)),
        "wins": int((trades["trade_return"] > 0).sum()),
        "losses": int((trades["trade_return"] <= 0).sum()),
        "exit_mix": {
            str(key): int(value)
            for key, value in trades["exit_reason"].value_counts().to_dict().items()
        },
        "long_short": {
            str(key): int(value)
            for key, value in trades["direction"].value_counts().to_dict().items()
        },
        "first_entry": pd.Timestamp(trades.iloc[0]["entry_ts"]).isoformat(),
        "last_exit": pd.Timestamp(trades.iloc[-1]["exit_ts"]).isoformat(),
        "last_trades": [
            {
                "entry_ts": pd.Timestamp(row["entry_ts"]).isoformat(),
                "exit_ts": pd.Timestamp(row["exit_ts"]).isoformat(),
                "direction": int(row["direction"]),
                "entry_price": float(row["entry_price"]),
                "exit_price": float(row["exit_price"]),
                "exit_reason": str(row["exit_reason"]),
                "trade_return": round(float(row["trade_return"]), 6),
                "risk_multiplier_at_entry": round(
                    float(row["risk_multiplier_at_entry"]), 6
                ),
            }
            for row in trades.tail(5).to_dict("records")
        ],
    }


def main() -> None:
    module = _load_archive_replay_module()

    exact_frame = module.load_hype_frame_from_lake()
    proxy_frame = _load_ohlcv_proxy_frame()
    post_proxy = proxy_frame.loc[
        proxy_frame.index >= pd.Timestamp("2026-06-01T03:00:00Z")
    ]

    windows = [
        ("since_2026_06_01_0300", "2026-06-01T03:00:00Z", None),
        ("since_2026_06_03_0000", "2026-06-03T00:00:00Z", None),
        ("since_2026_06_05_0000", "2026-06-05T00:00:00Z", None),
        ("since_2026_06_10_0000", "2026-06-10T00:00:00Z", None),
        ("since_2026_06_13_0000", "2026-06-13T00:00:00Z", None),
        (
            "until_hl_stop_2026_06_15_1300utc",
            "2026-06-01T03:00:00Z",
            "2026-06-15T13:00:00Z",
        ),
        (
            "until_margin_issue_2026_06_17",
            "2026-06-01T03:00:00Z",
            "2026-06-17T00:00:00Z",
        ),
    ]
    result = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "strategy": "HYPE-Candle-Count-Reversal-V35",
        "exact_mark_replay_data": _coverage(exact_frame),
        "ohlcv_proxy_data": {
            **_coverage(proxy_frame),
            "proxy_assumption": "mark_high=trade high, mark_low=trade low; post-2026-06-01 Binance mark_price_klines are absent locally.",
            "post_2026_06_01_rows": int(len(post_proxy)),
            "post_2026_06_01_start": post_proxy.index.min().isoformat(),
            "post_2026_06_01_end": post_proxy.index.max().isoformat(),
            "post_2026_06_01_nulls": {
                key: int(value) for key, value in post_proxy.isna().sum().to_dict().items()
            },
            "post_2026_06_01_nonzero_funding_rows": int(
                (post_proxy["funding_rate"] != 0).sum()
            ),
        },
        "proxy_windows": [
            _run_window(module, proxy_frame, name, start, end)
            for name, start, end in windows
        ],
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Wrote {ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
