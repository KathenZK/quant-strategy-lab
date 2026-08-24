from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-generic-ma7-trend/scripts/"
    "research_binance_1d_generic_ma7_trend_v0.py"
)
CONFIG = (
    ROOT
    / "research/asset-portfolios/1d-generic-ma7-trend/configs/"
    "binance-1d-generic-ma7-trend-v0.json"
)
V71_SCRIPT = (
    ROOT
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "audit_hype_1d_ma7_abt_v7_1_top15_binance_perp_transfer.py"
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


g = load(SCRIPT, "test_binance_1d_generic_ma7_trend_v0_module")
v71 = load(V71_SCRIPT, "test_binance_1d_generic_ma7_trend_v0_v71")


def make_data(closes: list[float], *, gap_day: int | None = None, gap_open: float | None = None):
    daily = []
    hourly = []
    for day_index, close in enumerate(closes):
        ts = day_index * g.MS_DAY
        day_open = closes[day_index - 1] if day_index else close
        if gap_day == day_index and gap_open is not None:
            day_open = gap_open
        daily.append(
            v71.Candle(
                ts=ts,
                open=day_open,
                high=max(day_open, close) + 0.05,
                low=min(day_open, close) - 0.05,
                close=close,
                volume=1.0,
                quote_volume=close,
                trade_count=1,
                close_time=ts + g.MS_DAY - 1,
            )
        )
        for hour_index in range(24):
            hour_open = day_open if hour_index == 0 else close
            hourly.append(
                v71.Candle(
                    ts=ts + hour_index * g.MS_HOUR,
                    open=hour_open,
                    high=max(hour_open, close) + 0.01,
                    low=min(hour_open, close) - 0.01,
                    close=close,
                    volume=1.0,
                    quote_volume=close,
                    trade_count=1,
                    close_time=ts + (hour_index + 1) * g.MS_HOUR - 1,
                )
            )
    return daily, hourly


def test_frozen_config_is_symmetric_and_has_no_hype_arms() -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert payload["entry"]["long_short_symmetric"] is True
    assert payload["risk"]["hard_stop_atr"] == payload["risk"]["trailing_stop_atr"] == 1.5
    assert payload["exit"]["max_hold_days"] is None
    assert payload["removed_hype_modules"] == {
        "oapp": False,
        "short_rsi_exit": False,
        "pehc": False,
        "forced_reversal": False,
        "cooldown_days": 0,
    }


def test_long_reclaim_executes_only_at_next_utc_open() -> None:
    daily, hourly = make_data([10.0, 9.0, 8.0, 8.0, 10.0, 10.2])
    cfg = g.StrategyConfig(
        ma_length=3,
        atr_length=3,
        slope_min_atr=0.0,
        exit_buffer_atr=100.0,
        hard_stop_atr=100.0,
        trail_stop_atr=100.0,
        fee_rate=0.0,
        slippage=0.0,
        funding_enabled=False,
    )
    result = g.run_generic("TESTUSDT", daily, hourly, [], cfg)
    assert result["trades"]
    assert result["trades"][0]["side"] == "long"
    assert result["trades"][0]["entry_ts_ms"] == daily[5].ts
    assert result["trades"][0]["entry_reference"] == daily[5].open


def test_short_rule_is_strict_mirror() -> None:
    daily, hourly = make_data([10.0, 11.0, 12.0, 12.0, 10.0, 9.8])
    cfg = g.StrategyConfig(
        ma_length=3,
        atr_length=3,
        slope_min_atr=0.0,
        exit_buffer_atr=100.0,
        hard_stop_atr=100.0,
        trail_stop_atr=100.0,
        fee_rate=0.0,
        slippage=0.0,
        funding_enabled=False,
    )
    result = g.run_generic("TESTUSDT", daily, hourly, [], cfg)
    assert result["trades"][0]["side"] == "short"
    assert result["trades"][0]["entry_ts_ms"] == daily[5].ts


def test_gap_through_stop_fills_at_hour_open() -> None:
    daily, hourly = make_data(
        [10.0, 9.0, 8.0, 8.0, 10.0, 10.2, 8.0],
        gap_day=6,
        gap_open=8.0,
    )
    cfg = g.StrategyConfig(
        ma_length=3,
        atr_length=3,
        slope_min_atr=0.0,
        exit_buffer_atr=100.0,
        hard_stop_atr=1.5,
        trail_stop_atr=1.5,
        fee_rate=0.0,
        slippage=0.0,
        funding_enabled=False,
    )
    result = g.run_generic("TESTUSDT", daily, hourly, [], cfg)
    trade = result["trades"][0]
    assert trade["exit_reason"] == "gap_protective_stop"
    assert trade["exit_reference"] == 8.0
    assert trade["exit_ts_ms"] == daily[6].ts


def test_market_cap_filter_excludes_pegs_before_counting_30() -> None:
    rows = [
        {
            "market_cap_rank": 1,
            "id": "tether",
            "symbol": "usdt",
            "name": "Tether",
            "market_cap": 10,
            "last_updated": "x",
        }
    ]
    rows.extend(
        {
            "market_cap_rank": index + 2,
            "id": f"coin-{index}",
            "symbol": f"c{index}",
            "name": f"Coin {index}",
            "market_cap": 9 - index,
            "last_updated": "x",
        }
        for index in range(30)
    )
    selected, decisions = g.market_cap_top30_nonpegged(rows)
    assert len(selected) == 30
    assert all(row["id"] != "tether" for row in selected)
    assert decisions[0]["reason"] == "fiat_stablecoin"


def test_trade_path_html_supports_drag_pan_and_synced_timeline(tmp_path: Path) -> None:
    index = g.pd.date_range("2026-01-01", periods=3, freq="1D", tz="UTC")
    frame = g.pd.DataFrame(
        {
            "open": [10.0, 11.0, 12.0],
            "high": [11.0, 12.0, 13.0],
            "low": [9.0, 10.0, 11.0],
            "close": [10.5, 11.5, 12.5],
            "ma": [None, 10.75, 11.75],
            "equity": [1.0, 1.05, 1.1],
        },
        index=index,
    )
    trade = {
        "trade_id": "TEST-0001",
        "side": "long",
        "entry_ts": index[0].isoformat(),
        "entry_ts_ms": int(index[0].timestamp() * 1000),
        "entry_reference": 10.0,
        "exit_ts": index[2].isoformat(),
        "exit_ts_ms": int(index[2].timestamp() * 1000),
        "exit_reference": 12.5,
        "exit_reason": "terminal_flatten",
        "net_pnl": 0.1,
    }
    results = {
        "TESTUSDT": {
            "daily": frame,
            "trades": [trade],
            "metrics": {
                "closed_trades": 1,
                "cagr_pct": 10.0,
                "sharpe": 0.5,
                "chronological_1h_mdd_pct": -2.0,
            },
        }
    }
    summary = {
        "assets": 1,
        "median_sharpe": 0.5,
        "sharpe_gt_0_ratio": 1.0,
        "pf_gt_1_ratio": 1.0,
    }
    output = tmp_path / "trade-path.html"

    g.render_html(output, results, summary, force=False)
    html = output.read_text(encoding="utf-8")

    assert "pointerdown" in html and "pointermove" in html
    assert "setPointerCapture" in html and "touch-action:none" in html
    assert "attachTimelineInteractions(document.getElementById('price'))" in html
    assert "attachTimelineInteractions(document.getElementById('equity'))" in html
    assert "dblclick" in html and "viewStart" in html and 'id="viewRange"' in html
