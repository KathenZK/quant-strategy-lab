from __future__ import annotations

import json
from argparse import ArgumentParser
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_recent_volatility_tp_reassessment_2026-07-15"
DEFAULT_UNTIL = "2026-07-15T03:15:00Z"
TP_GRID = (4.0, 4.25, 4.5, 4.6, 4.7, 4.75, 4.8, 4.85, 4.9, 4.95, 5.0, 5.05, 5.1, 5.25, 5.5)


def parse_args() -> Any:
    parser = ArgumentParser()
    parser.add_argument("--since", default=base.DEFAULT_SINCE)
    parser.add_argument("--until", default=DEFAULT_UNTIL)
    return parser.parse_args()


def pct(value: float | np.floating | None) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return round(float(value) * 100.0, 2)


def rounded(value: float | np.floating | None, digits: int = 4) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), digits)


def rolling_efficiency(log_return: pd.Series, bars: int) -> pd.Series:
    displacement = log_return.rolling(bars).sum().abs()
    path = log_return.abs().rolling(bars).sum()
    return displacement / path.replace(0.0, np.nan)


def market_series(frame: pd.DataFrame, features: pd.DataFrame) -> dict[str, pd.Series]:
    simple_return = frame["close"].pct_change()
    log_return = np.log(frame["close"]).diff()
    return {
        "atr_pct": features["atr"] / frame["close"],
        "hl_pct": (frame["high"] - frame["low"]) / frame["close"],
        "abs_return": simple_return.abs(),
        "rv_1d": simple_return.rolling(96).std() * np.sqrt(365 * 96),
        "efficiency_1d": rolling_efficiency(log_return, 96),
        "efficiency_7d": rolling_efficiency(log_return, 672),
    }


def market_stats(
    frame: pd.DataFrame,
    features: pd.DataFrame,
    series: dict[str, pd.Series],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    mask = (frame.index >= start) & (frame.index <= end)
    window = frame.loc[mask]
    feat = features.loc[mask]
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "bars": int(mask.sum()),
        "price_return_pct": pct(window["close"].iloc[-1] / window["close"].iloc[0] - 1.0),
        "atr_pct_median": pct(series["atr_pct"].loc[mask].median()),
        "atr_pct_mean": pct(series["atr_pct"].loc[mask].mean()),
        "atr_pct_p25": pct(series["atr_pct"].loc[mask].quantile(0.25)),
        "atr_pct_p75": pct(series["atr_pct"].loc[mask].quantile(0.75)),
        "hl_pct_median": pct(series["hl_pct"].loc[mask].median()),
        "abs_15m_return_median": pct(series["abs_return"].loc[mask].median()),
        "abs_15m_return_p90": pct(series["abs_return"].loc[mask].quantile(0.90)),
        "realized_vol_1d_median_pct": pct(series["rv_1d"].loc[mask].median()),
        "directional_efficiency_1d_median": rounded(
            series["efficiency_1d"].loc[mask].median()
        ),
        "directional_efficiency_7d_median": rounded(
            series["efficiency_7d"].loc[mask].median()
        ),
        "adx28_median": rounded(feat["adx"].median()),
    }


def window_definitions(end: pd.Timestamp) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    return {
        "last_1m": (end - pd.Timedelta(days=30), end),
        "prev_1m": (end - pd.Timedelta(days=60), end - pd.Timedelta(days=30)),
        "last_2m": (end - pd.Timedelta(days=60), end),
        "prev_2m": (end - pd.Timedelta(days=120), end - pd.Timedelta(days=60)),
        "last_3m": (end - pd.Timedelta(days=90), end),
        "prev_3m": (end - pd.Timedelta(days=180), end - pd.Timedelta(days=90)),
        "month_0_30d": (end - pd.Timedelta(days=30), end),
        "month_30_60d": (end - pd.Timedelta(days=60), end - pd.Timedelta(days=30)),
        "month_60_90d": (end - pd.Timedelta(days=90), end - pd.Timedelta(days=60)),
    }


def trades_by_exit(
    trades: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    out = trades.copy()
    out["entry_ts"] = pd.to_datetime(out["entry_ts"], utc=True)
    out["exit_ts"] = pd.to_datetime(out["exit_ts"], utc=True)
    return out.loc[(out["exit_ts"] >= start) & (out["exit_ts"] <= end)].copy()


def strategy_window_stats(
    run: base.RunResult,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    equity = run.equity_curve.loc[
        (run.equity_curve.index >= start) & (run.equity_curve.index <= end)
    ]
    trades = trades_by_exit(run.trades, start, end)
    if len(equity) >= 2:
        normalized = equity / equity.iloc[0]
        drawdown = normalized / normalized.cummax() - 1.0
        return_pct = pct(normalized.iloc[-1] - 1.0)
        max_drawdown_pct = pct(drawdown.min())
    else:
        return_pct = None
        max_drawdown_pct = None
    take_profit = trades.loc[trades["exit_reason"] == "take_profit"]
    exit_counts = trades["exit_reason"].value_counts().to_dict()
    return {
        "return_pct": return_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "closed_trades": int(len(trades)),
        "win_rate_pct": pct((trades["trade_return"] > 0.0).mean()) if len(trades) else None,
        "exit_counts": {str(key): int(value) for key, value in exit_counts.items()},
        "median_hold_hours": rounded(trades["hold_bars"].median() * 0.25, 2)
        if len(trades)
        else None,
        "max_hold_hours": rounded(trades["hold_bars"].max() * 0.25, 2)
        if len(trades)
        else None,
        "tp_median_hold_hours": rounded(take_profit["hold_bars"].median() * 0.25, 2)
        if len(take_profit)
        else None,
        "tp_max_hold_hours": rounded(take_profit["hold_bars"].max() * 0.25, 2)
        if len(take_profit)
        else None,
    }


def latest_trades(run: base.RunResult, count: int = 10) -> list[dict[str, Any]]:
    trades = run.trades.tail(count).copy()
    trades["hold_hours"] = trades["hold_bars"] * 0.25
    trades["trade_return_pct"] = trades["trade_return"] * 100.0
    columns = [
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_price",
        "entry_atr",
        "mfe_atr",
        "hold_hours",
        "exit_reason",
        "trade_return_pct",
    ]
    return trades[columns].to_dict("records")


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = base.load_binance_api_data(args.since, args.until)
    config = base.V35Config()
    features = base.build_features(frame, config)
    no_floor = base.ProfitFloorConfig(enabled=False)
    end = frame.index.max()
    windows = window_definitions(end)
    series = market_series(frame, features)
    runs = [
        base.run_backtest(
            f"v35_tp_{str(tp).replace('.', '')}",
            frame,
            funding,
            features,
            replace(config, take_profit_atr=tp),
            no_floor,
        )
        for tp in TP_GRID
    ]
    baseline = runs[TP_GRID.index(5.0)]
    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "diagnostic_id": "HYPE-EMA-TB-V35 recent volatility and TP reassessment 2026-07-15",
        "market": {
            "exchange": "Binance",
            "market_type": "USD-M perpetual",
            "symbol": base.SYMBOL,
            "timeframe": base.TIMEFRAME,
        },
        "data_quality": quality,
        "cost_model": (
            "V35 canonical override: 0.00085 per fill, including fee and 4 bps "
            "adverse slippage; Binance funding included."
        ),
        "execution_model": (
            "K0 close signal, skip K1, K2 open entry; entry ATR from closed K1; "
            "fixed entry-ATR TP and 7ATR SL; 15m intrabar stop-first."
        ),
        "selection_disclosure": (
            "The latest two operational observations motivated this post-hoc diagnostic. "
            "Last 1m/2m/3m windows participate in evaluation and are not independent OOS."
        ),
        "baseline_config": asdict(config),
        "windows": {
            name: {"start": start.isoformat(), "end": stop.isoformat()}
            for name, (start, stop) in windows.items()
        },
        "market_volatility": {
            name: market_stats(frame, features, series, start, stop)
            for name, (start, stop) in windows.items()
        },
        "tp_grid": [
            {
                "tp_atr": tp,
                "metrics": run.metrics,
                "capital_retention_vs_tp5_pct": rounded(
                    run.equity_curve.iloc[-1] / baseline.equity_curve.iloc[-1] * 100.0,
                    2,
                ),
                "windows": {
                    name: strategy_window_stats(run, start, stop)
                    for name, (start, stop) in windows.items()
                    if name in {"last_1m", "last_2m", "last_3m"}
                },
                "latest_trades": latest_trades(run, 4),
            }
            for tp, run in zip(TP_GRID, runs, strict=True)
        ],
        "baseline_latest_trades": latest_trades(baseline, 10),
    }
    summary_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    trades_path = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
    equity_path = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
    summary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    base.write_artifacts(runs, trades_path=trades_path, equity_path=equity_path)

    print(
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"gaps={quality['missing_15m_bars']}"
    )
    for name in ("last_1m", "prev_1m", "last_2m", "prev_2m", "last_3m", "prev_3m"):
        row = payload["market_volatility"][name]
        print(
            f"{name:>9} atr={row['atr_pct_median']:.2f}% "
            f"range={row['hl_pct_median']:.2f}% rv={row['realized_vol_1d_median_pct']:.2f}% "
            f"eff7d={row['directional_efficiency_7d_median']:.4f}"
        )
    for row in payload["tp_grid"]:
        metrics = row["metrics"]
        print(
            f"tp={row['tp_atr']:>4} full={metrics['return_pct']:>8.2f}% "
            f"dd={metrics['max_drawdown_pct']:>7.2f}% sh={metrics['sharpe']:>4.2f} "
            f"retain={row['capital_retention_vs_tp5_pct']:>6.2f}% "
            f"1m={row['windows']['last_1m']['return_pct']:>7.2f}% "
            f"2m={row['windows']['last_2m']['return_pct']:>7.2f}% "
            f"3m={row['windows']['last_3m']['return_pct']:>7.2f}%"
        )
    print(f"summary -> {summary_path}")
    print(f"trades  -> {trades_path}")
    print(f"equity  -> {equity_path}")


if __name__ == "__main__":
    main()
