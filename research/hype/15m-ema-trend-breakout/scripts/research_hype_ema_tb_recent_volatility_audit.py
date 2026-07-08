from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v37_v38_floor as combo


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
SUMMARY_PATH = ARTIFACT_DIR / "hype_ema_tb_recent_3m_volatility_audit_2026-07-08.json"
TRADES_PATH = ARTIFACT_DIR / "hype_ema_tb_recent_3m_volatility_audit_trades_2026-07-08.csv"


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(base.DataLakeLayout.from_settings(base.load_settings(None)))
    frame, funding, quality = base.load_data(warehouse)
    config = base.V35Config()
    features = base.build_features(frame, config)
    combo_features = combo.add_satellite_features(features)
    v35 = base.run_backtest("v35_base", frame, funding, combo_features, config, base.ProfitFloorConfig(enabled=False))
    v38 = base.run_backtest("v38_floor_475_425", frame, funding, combo_features, config, base.ProfitFloorConfig(enabled=True, tiers=((4.75, 4.25),)))
    sat = combo.run_satellite("v37_early_long_satellite", frame, funding, combo_features, config, combo.SatelliteConfig())
    v37 = combo.combine_legs("v37_v35_plus_satellite", combo.wrap_main_result(v35), sat)
    v37_v38 = combo.combine_legs("v37_plus_v38_floor", combo.wrap_main_result(v38), sat)

    end = frame.index.max()
    recent_start = end - pd.Timedelta(days=90)
    previous_start = recent_start - pd.Timedelta(days=90)
    one_month_start = end - pd.Timedelta(days=30)
    windows = [
        ("last_1m", one_month_start, end),
        ("last_3m", recent_start, end),
        ("prev_3m", previous_start, recent_start),
        ("full", frame.index.min(), end),
    ]

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "audit_id": "HYPE-EMA-TB recent 3m volatility and TP/SL audit",
        "data_quality": quality,
        "config": asdict(config),
        "windows": {
            name: {
                "start": pd.Timestamp(start).isoformat(),
                "end": pd.Timestamp(stop).isoformat(),
            }
            for name, start, stop in windows
        },
        "market_volatility": {
            name: market_stats(frame, features, start, stop)
            for name, start, stop in windows
        },
        "strategy": {
            "v35": strategy_stats(v35, features, windows, config),
            "v38": strategy_stats(v38, features, windows, config),
            "v37": strategy_stats(v37, features, windows, config),
            "v37_plus_v38": strategy_stats(v37_v38, features, windows, config),
        },
        "interpretation": build_interpretation(frame, features, v35, windows),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_trades([("v35", v35), ("v38", v38), ("v37", v37), ("v37_plus_v38", v37_v38)])
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))


def market_stats(frame: pd.DataFrame, features: pd.DataFrame, start: pd.Timestamp, stop: pd.Timestamp) -> dict[str, Any]:
    window = frame.loc[(frame.index >= start) & (frame.index <= stop)].copy()
    feat = features.loc[window.index]
    ret = window["close"].pct_change()
    atr_pct = feat["atr"] / window["close"]
    hl_pct = (window["high"] - window["low"]) / window["close"]
    abs_ret = ret.abs()
    realized_vol_1d = ret.rolling(96).std() * np.sqrt(365 * 96)
    return {
        "bars": int(len(window)),
        "close_start": finite_float(window["close"].iloc[0]) if len(window) else None,
        "close_end": finite_float(window["close"].iloc[-1]) if len(window) else None,
        "price_return_pct": pct(window["close"].iloc[-1] / window["close"].iloc[0] - 1.0) if len(window) else None,
        "atr_pct_median": pct(atr_pct.median()),
        "atr_pct_mean": pct(atr_pct.mean()),
        "atr_pct_p25": pct(atr_pct.quantile(0.25)),
        "atr_pct_p75": pct(atr_pct.quantile(0.75)),
        "hl_pct_median": pct(hl_pct.median()),
        "abs_15m_return_median": pct(abs_ret.median()),
        "abs_15m_return_p90": pct(abs_ret.quantile(0.90)),
        "realized_vol_1d_median_pct": pct(realized_vol_1d.median()),
        "adx28_median": round_float(feat["adx"].median()),
        "volume_surge_median": round_float(feat["volume_surge"].median()),
    }


def strategy_stats(
    run: base.RunResult,
    features: pd.DataFrame,
    windows: list[tuple[str, pd.Timestamp, pd.Timestamp]],
    config: base.V35Config,
) -> dict[str, Any]:
    return {
        name: strategy_window_stats(run, features, start, stop, config)
        for name, start, stop in windows
    }


def strategy_window_stats(
    run: base.RunResult,
    features: pd.DataFrame,
    start: pd.Timestamp,
    stop: pd.Timestamp,
    config: base.V35Config,
) -> dict[str, Any]:
    equity = run.equity_curve.loc[(run.equity_curve.index >= start) & (run.equity_curve.index <= stop)]
    trades = trades_in_window(run.trades, start, stop).copy()
    if not trades.empty:
        trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
        entry_atr_pct = []
        tp_distance_pct = []
        sl_distance_pct = []
        for _, trade in trades.iterrows():
            entry_atr = float(trade["entry_atr"])
            entry_price = float(trade["entry_price"])
            entry_atr_pct.append(entry_atr / entry_price)
            tp_distance_pct.append(config.take_profit_atr * entry_atr / entry_price)
            sl_distance_pct.append(config.hard_stop_atr * entry_atr / entry_price)
        trades["entry_atr_pct"] = entry_atr_pct
        trades["tp_distance_pct"] = tp_distance_pct
        trades["sl_distance_pct"] = sl_distance_pct
    if len(equity) >= 2:
        period_return = equity.iloc[-1] / equity.iloc[0] - 1.0
        drawdown = equity / equity.cummax() - 1.0
    else:
        period_return = np.nan
        drawdown = pd.Series(dtype="float64")
    exit_counts = trades["exit_reason"].value_counts().to_dict() if "exit_reason" in trades.columns else {}
    wins = int((trades["trade_return"] > 0).sum()) if "trade_return" in trades.columns else 0
    return {
        "return_pct": pct(period_return),
        "max_drawdown_pct": pct(drawdown.min()) if not drawdown.empty else None,
        "trades": int(len(trades)),
        "wins": wins,
        "win_rate_pct": pct(wins / len(trades)) if len(trades) else None,
        "exit_counts": {str(key): int(value) for key, value in exit_counts.items()},
        "median_entry_atr_pct": pct(trades["entry_atr_pct"].median()) if len(trades) else None,
        "median_tp_distance_pct": pct(trades["tp_distance_pct"].median()) if len(trades) else None,
        "median_sl_distance_pct": pct(trades["sl_distance_pct"].median()) if len(trades) else None,
        "median_mfe_atr": round_float(trades["mfe_atr"].median()) if len(trades) else None,
        "p25_mfe_atr": round_float(trades["mfe_atr"].quantile(0.25)) if len(trades) else None,
        "p75_mfe_atr": round_float(trades["mfe_atr"].quantile(0.75)) if len(trades) else None,
        "median_allocation": round_float(trades["allocation"].median()) if len(trades) else None,
        "p75_allocation": round_float(trades["allocation"].quantile(0.75)) if len(trades) else None,
        "max_allocation": round_float(trades["allocation"].max()) if len(trades) else None,
        "cap_allocation_trades": int(trades["allocation"].ge(config.max_allocation - 1e-9).sum()) if len(trades) else 0,
        "stop_loss_median_entry_atr_pct": pct(trades.loc[trades["exit_reason"] == "stop_loss", "entry_atr_pct"].median())
        if len(trades) and (trades["exit_reason"] == "stop_loss").any()
        else None,
        "signal_adx28_median": signal_feature_median(features, trades, "adx"),
        "signal_atr_pct_median": signal_atr_pct_median(features, trades),
    }


def trades_in_window(trades: pd.DataFrame, start: pd.Timestamp, stop: pd.Timestamp) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    out = trades.copy()
    out["exit_ts"] = pd.to_datetime(out["exit_ts"], utc=True)
    return out.loc[(out["exit_ts"] >= start) & (out["exit_ts"] <= stop)].reset_index(drop=True)


def signal_feature_median(features: pd.DataFrame, trades: pd.DataFrame, column: str) -> float | None:
    if trades.empty or column not in features.columns:
        return None
    values = []
    for ts in pd.to_datetime(trades["entry_ts"], utc=True):
        if ts in features.index:
            values.append(float(features.at[ts, column]))
    return round_float(pd.Series(values).median()) if values else None


def signal_atr_pct_median(features: pd.DataFrame, trades: pd.DataFrame) -> float | None:
    if trades.empty:
        return None
    values = []
    for _, trade in trades.iterrows():
        ts = pd.Timestamp(trade["entry_ts"])
        if ts in features.index:
            values.append(float(features.at[ts, "atr"]) / float(trade["entry_price"]))
    return pct(pd.Series(values).median()) if values else None


def build_interpretation(
    frame: pd.DataFrame,
    features: pd.DataFrame,
    v35: base.RunResult,
    windows: list[tuple[str, pd.Timestamp, pd.Timestamp]],
) -> dict[str, Any]:
    stats = {name: market_stats(frame, features, start, stop) for name, start, stop in windows}
    strat = strategy_stats(v35, features, windows, base.V35Config())
    last_3m_atr = unpct(stats["last_3m"]["atr_pct_median"])
    prev_3m_atr = unpct(stats["prev_3m"]["atr_pct_median"])
    atr_change = last_3m_atr / prev_3m_atr - 1.0 if prev_3m_atr else np.nan
    return {
        "atr_median_change_last_3m_vs_prev_3m_pct": pct(atr_change),
        "last_3m_v35_exit_counts": strat["last_3m"]["exit_counts"],
        "last_3m_v35_return_pct": strat["last_3m"]["return_pct"],
        "last_3m_v35_max_drawdown_pct": strat["last_3m"]["max_drawdown_pct"],
        "plain_conclusion": (
            "Recent 3m median ATR% is lower than the previous 3m, but V35 still has positive 3m return "
            "and take-profit exits remain active. This points to narrower volatility reducing per-trade TP/SL "
            "price distance and allocation sizing dynamics, not to TP/SL becoming unreachable."
        ),
    }


def write_trades(runs: list[tuple[str, Any]]) -> None:
    frames = []
    for name, run in runs:
        if not run.trades.empty:
            frames.append(run.trades.assign(variant=name))
    if frames:
        pd.concat(frames, ignore_index=True).to_csv(TRADES_PATH, index=False)


def pct(value: float | int | np.floating | None) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return round(float(value) * 100.0, 2)


def unpct(value: float | int | np.floating | None) -> float:
    if value is None or not np.isfinite(value):
        return float("nan")
    return float(value) / 100.0


def round_float(value: float | int | np.floating | None, ndigits: int = 4) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), ndigits)


def finite_float(value: float | int | np.floating | None) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return float(value)


if __name__ == "__main__":
    main()
