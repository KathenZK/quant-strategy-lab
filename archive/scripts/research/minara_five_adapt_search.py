from __future__ import annotations

import itertools
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
import minara_21_approx_backtest as base


REPORT_PREFIX = Path("archive/reports/legacy/minara_five_adapt_btc_hype")
SYMBOLS = ["BTC/USDT:USDT", "HYPE/USDT:USDT"]
FAMILIES = ["kinetic_kalman", "macd_zero", "supertrend", "qullamagi", "hash_momentum"]
SEARCH_DAYS = 720


@dataclass(frozen=True, slots=True)
class CandidateResult:
    family: str
    symbol: str
    timeframe: str
    params: dict[str, Any]
    return_: float
    annualized: float
    max_drawdown: float
    sharpe: float
    calmar: float
    trades: int
    win_rate: float
    first_half_return: float
    first_half_dd: float
    second_half_return: float
    second_half_dd: float
    robustness: str


def main() -> None:
    data = _load_data()
    candidates: list[CandidateResult] = []
    for symbol in SYMBOLS:
        for family in FAMILIES:
            grid = _param_grid(family)
            print(f"running {symbol} {family}: {len(grid)} candidates", flush=True)
            for timeframe, params in grid:
                frame = data[symbol][timeframe]
                rule = _build_rule(family, frame, params)
                equity, trades = base.backtest(
                    frame,
                    rule,
                    allocation=float(params.get("allocation", 1.0)),
                )
                result = _evaluate(
                    family=family,
                    symbol=symbol,
                    timeframe=timeframe,
                    params=params,
                    equity=equity,
                    trades=trades,
                )
                candidates.append(result)

    rows = []
    for candidate in candidates:
        row = asdict(candidate)
        row["return"] = row.pop("return_")
        rows.append(row)
    all_frame = pd.DataFrame(rows)
    ranked = all_frame.sort_values(
        ["calmar", "return", "sharpe"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    # Keep a compact top set per family/symbol plus global top list.
    top_by_group = (
        ranked[ranked["trades"].ge(3)]
        .groupby(["symbol", "family"], group_keys=False)
        .head(8)
        .reset_index(drop=True)
    )
    payload = {
        "disclaimer": "Parameter search over adapted public-rule approximations, not PineScript source replication. Results are research leads, not trading advice.",
        "families": FAMILIES,
        "symbols": SYMBOLS,
        "ranking_rule": "Sort by Calmar, then cumulative return, then Sharpe. Top tables require at least 3 trades.",
        "global_top": ranked[ranked["trades"].ge(3)].head(60).to_dict("records"),
        "top_by_symbol_family": top_by_group.to_dict("records"),
        "data_coverage": {
            symbol: {
                timeframe: _coverage(frame)
                for timeframe, frame in frames.items()
            }
            for symbol, frames in data.items()
        },
    }
    REPORT_PREFIX.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PREFIX.with_suffix(".json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    ranked.to_csv(f"{REPORT_PREFIX}_all.csv", index=False)
    top_by_group.to_csv(f"{REPORT_PREFIX}_top_by_group.csv", index=False)
    print(top_by_group[[
        "symbol",
        "family",
        "timeframe",
        "return",
        "max_drawdown",
        "calmar",
        "trades",
        "robustness",
        "params",
    ]].head(80).to_string(index=False))
    print(f"wrote {REPORT_PREFIX}.json")


def _load_data() -> dict[str, dict[str, pd.DataFrame]]:
    result: dict[str, dict[str, pd.DataFrame]] = {}
    for symbol in SYMBOLS:
        base_15m = base.load_ohlcv(symbol, "15m")
        base_15m = base_15m[base_15m.index >= base_15m.index.max() - pd.Timedelta(days=SEARCH_DAYS)]
        result[symbol] = {
            "15m": base_15m,
            "1h": base.resample_ohlcv(base_15m, "1h"),
            "4h": base.resample_ohlcv(base_15m, "4h"),
            "1d": base.resample_ohlcv(base_15m, "1d"),
        }
    return result


def _coverage(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": int(len(frame)),
        "start": frame.index.min().isoformat(),
        "end": frame.index.max().isoformat(),
    }


def _param_grid(family: str) -> list[tuple[str, dict[str, Any]]]:
    if family == "kinetic_kalman":
        return [
            (tf, {"gain": gain, "lookback": lookback, "band_mult": band, "mode": mode, "stop_pct": stop, "take_pct": take})
            for tf, gain, lookback, band, mode, (stop, take) in itertools.product(
                ["1h", "4h"],
                [0.15, 0.25],
                [200],
                [2.0, 2.8],
                ["both", "long", "short"],
                [(None, None), (0.05, 0.10)],
            )
        ]
    if family == "macd_zero":
        return [
            (tf, {"fast": fast, "slow": slow, "signal_len": sig, "mode": mode, "stop_pct": stop, "take_pct": take})
            for tf, fast, slow, sig, mode, (stop, take) in itertools.product(
                ["4h", "1d"],
                [8, 12],
                [26, 35],
                [9],
                ["long", "both"],
                [(None, None), (0.08, 0.20)],
            )
            if fast < slow
        ]
    if family == "supertrend":
        return [
            (tf, {"window": window, "mult": mult, "mode": mode, "stop_pct": stop, "take_pct": take})
            for tf, window, mult, mode, (stop, take) in itertools.product(
                ["1h", "4h", "1d"],
                [10, 14],
                [3.0, 5.0],
                ["long", "both"],
                [(None, None), (0.10, 0.30)],
            )
        ]
    if family == "qullamagi":
        presets = [
            (5, 15, 67, 200, 350),
            (10, 20, 50, 100, 200),
            (8, 21, 55, 144, 233),
        ]
        return [
            (tf, {"preset": preset, "box": box, "volume_mult": volume, "mode": mode, "stop_pct": stop, "take_pct": take})
            for tf, preset, box, volume, mode, (stop, take) in itertools.product(
                ["4h"],
                presets,
                [20, 36],
                [1.0, 1.5],
                ["both", "long"],
                [(0.06, 0.12), (0.10, 0.25)],
            )
        ]
    if family == "hash_momentum":
        return [
            (tf, {"lookback": lookback, "threshold": threshold, "ema": ema, "mode": mode, "stop_pct": stop, "take_pct": take})
            for tf, lookback, threshold, ema, mode, (stop, take) in itertools.product(
                ["1h", "4h"],
                [12, 24],
                [1.8, 2.5],
                [50, 100],
                ["both", "long"],
                [(0.04, 0.10), (0.08, 0.20)],
            )
        ]
    raise ValueError(f"unknown family: {family}")


def _build_rule(family: str, frame: pd.DataFrame, params: dict[str, Any]) -> base.RuleOutput:
    if family == "kinetic_kalman":
        return _kinetic_rule(frame, params)
    if family == "macd_zero":
        return _macd_rule(frame, params)
    if family == "supertrend":
        return _supertrend_rule(frame, params)
    if family == "qullamagi":
        return _qullamagi_rule(frame, params)
    if family == "hash_momentum":
        return _hash_momentum_rule(frame, params)
    raise ValueError(f"unknown family: {family}")


def _apply_mode(signal: pd.Series, mode: str) -> pd.Series:
    if mode == "long":
        return signal.where(signal >= 0, 0)
    if mode == "short":
        return signal.where(signal <= 0, 0)
    return signal


def _kinetic_rule(frame: pd.DataFrame, params: dict[str, Any]) -> base.RuleOutput:
    close = frame["close"]
    estimate = pd.Series(index=frame.index, dtype="float64")
    previous = np.nan
    gain = float(params["gain"])
    for ts, value in close.items():
        previous = float(value) if pd.isna(previous) else previous + gain * (float(value) - previous)
        estimate.loc[ts] = previous
    mae = (close - estimate).abs().rolling(int(params["lookback"]), min_periods=int(params["lookback"])).mean()
    upper = estimate + mae * float(params["band_mult"])
    lower = estimate - mae * float(params["band_mult"])
    signal = base.signal_from_conditions(frame.index, long=base.cross_above(close, upper), short=base.cross_below(close, lower))
    return base.RuleOutput(
        signal=_apply_mode(signal, str(params["mode"])),
        stop_pct=params["stop_pct"],
        take_pct=params["take_pct"],
    )


def _macd_rule(frame: pd.DataFrame, params: dict[str, Any]) -> base.RuleOutput:
    close = frame["close"]
    fast = close.ewm(span=int(params["fast"]), adjust=False, min_periods=int(params["fast"])).mean()
    slow = close.ewm(span=int(params["slow"]), adjust=False, min_periods=int(params["slow"])).mean()
    line = fast - slow
    signal_line = line.ewm(span=int(params["signal_len"]), adjust=False, min_periods=int(params["signal_len"])).mean()
    raw = pd.Series(0, index=frame.index, dtype="int64")
    raw.loc[base.cross_above(signal_line, 0.0)] = 1
    if params["mode"] == "both":
        raw.loc[base.cross_below(signal_line, 0.0)] = -1
        exit_on_zero = False
    else:
        raw.loc[base.cross_below(signal_line, 0.0)] = 0
        exit_on_zero = True
    return base.RuleOutput(
        signal=raw,
        stop_pct=params["stop_pct"],
        take_pct=params["take_pct"],
        exit_on_zero=exit_on_zero,
        flip=params["mode"] == "both",
    )


def _supertrend_rule(frame: pd.DataFrame, params: dict[str, Any]) -> base.RuleOutput:
    direction = base.supertrend_direction(frame, int(params["window"]), float(params["mult"]))
    raw = base.signal_from_conditions(
        frame.index,
        long=(direction == 1) & (direction.shift(1) != 1),
        short=(direction == -1) & (direction.shift(1) != -1),
    )
    if params["mode"] == "long":
        raw = raw.where(raw >= 0, 0)
        raw.loc[(direction == -1) & (direction.shift(1) == 1)] = 0
        exit_on_zero = True
    else:
        exit_on_zero = False
    return base.RuleOutput(
        signal=raw,
        stop_pct=params["stop_pct"],
        take_pct=params["take_pct"],
        exit_on_zero=exit_on_zero,
        flip=params["mode"] == "both",
    )


def _qullamagi_rule(frame: pd.DataFrame, params: dict[str, Any]) -> base.RuleOutput:
    close = frame["close"]
    p = tuple(int(x) for x in params["preset"])
    ma1 = close.ewm(span=p[0], adjust=False, min_periods=p[0]).mean()
    ma2 = close.ewm(span=p[1], adjust=False, min_periods=p[1]).mean()
    ma3 = close.rolling(p[2], min_periods=p[2]).mean()
    ma4 = close.rolling(p[3], min_periods=p[3]).mean()
    ma5 = close.rolling(p[4], min_periods=p[4]).mean()
    box = int(params["box"])
    high_box = frame["high"].rolling(box, min_periods=box).max().shift(1)
    low_box = frame["low"].rolling(box, min_periods=box).min().shift(1)
    vol_ma = frame["volume"].rolling(20, min_periods=20).mean()
    vol_ok = frame["volume"].gt(vol_ma * float(params["volume_mult"]))
    long_stack = (close > ma1) & (ma1 > ma2) & (ma2 > ma3) & (ma3 > ma4) & (ma4 > ma5)
    short_stack = (close < ma1) & (ma1 < ma2) & (ma2 < ma3) & (ma3 < ma4) & (ma4 < ma5)
    raw = base.signal_from_conditions(
        frame.index,
        long=long_stack & close.gt(high_box) & vol_ok,
        short=short_stack & close.lt(low_box) & vol_ok,
    )
    return base.RuleOutput(
        signal=_apply_mode(raw, str(params["mode"])),
        stop_pct=params["stop_pct"],
        take_pct=params["take_pct"],
    )


def _hash_momentum_rule(frame: pd.DataFrame, params: dict[str, Any]) -> base.RuleOutput:
    lookback = int(params["lookback"])
    momentum = frame["close"] - frame["close"].shift(lookback)
    threshold = base.atr(frame, 14) * float(params["threshold"])
    ema = frame["close"].ewm(span=int(params["ema"]), adjust=False, min_periods=int(params["ema"])).mean()
    raw = base.signal_from_conditions(
        frame.index,
        long=momentum.gt(threshold) & momentum.diff().gt(0) & frame["close"].gt(ema),
        short=momentum.lt(-threshold) & momentum.diff().lt(0) & frame["close"].lt(ema),
    )
    return base.RuleOutput(
        signal=_apply_mode(raw, str(params["mode"])),
        stop_pct=params["stop_pct"],
        take_pct=params["take_pct"],
    )


def _evaluate(
    *,
    family: str,
    symbol: str,
    timeframe: str,
    params: dict[str, Any],
    equity: pd.Series,
    trades: pd.DataFrame,
) -> CandidateResult:
    full = _metrics(equity, trades)
    midpoint = len(equity) // 2
    first_equity = equity.iloc[:midpoint] / equity.iloc[0] if midpoint > 10 else equity
    second_equity = equity.iloc[midpoint:] / equity.iloc[midpoint] if len(equity) - midpoint > 10 else equity
    first = _metrics(first_equity, trades.iloc[:0])
    second = _metrics(second_equity, trades.iloc[:0])
    robustness = _robustness(full, first, second)
    return CandidateResult(
        family=family,
        symbol=symbol,
        timeframe=timeframe,
        params=params,
        return_=full["return"],
        annualized=full["annualized"],
        max_drawdown=full["max_drawdown"],
        sharpe=full["sharpe"],
        calmar=full["calmar"],
        trades=int(len(trades)),
        win_rate=full["win_rate"],
        first_half_return=first["return"],
        first_half_dd=first["max_drawdown"],
        second_half_return=second["return"],
        second_half_dd=second["max_drawdown"],
        robustness=robustness,
    )


def _metrics(equity: pd.Series, trades: pd.DataFrame) -> dict[str, float]:
    if equity.empty:
        return {
            "return": 0.0,
            "annualized": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "calmar": 0.0,
            "win_rate": 0.0,
        }
    returns = equity.pct_change().fillna(0.0)
    ppy = base.periods_per_year(equity.index)
    years = len(equity) / ppy if ppy > 0 else 0.0
    total_return = float(equity.iloc[-1] - 1.0)
    annualized = float(equity.iloc[-1] ** (1 / years) - 1.0) if years > 0 and equity.iloc[-1] > 0 else -1.0
    max_dd = base.max_drawdown(equity)
    vol = returns.std(ddof=0)
    sharpe = float(returns.mean() / vol * np.sqrt(ppy)) if vol > 0 else 0.0
    calmar = annualized / abs(max_dd) if max_dd < 0 else (annualized * 10 if annualized > 0 else 0.0)
    wins = int(trades["net_return"].gt(0).sum()) if not trades.empty else 0
    return {
        "return": total_return,
        "annualized": annualized,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "calmar": calmar,
        "win_rate": float(wins / len(trades)) if len(trades) else 0.0,
    }


def _robustness(full: dict[str, float], first: dict[str, float], second: dict[str, float]) -> str:
    if full["return"] <= 0:
        return "fail"
    if first["return"] > 0 and second["return"] > 0 and full["max_drawdown"] >= -0.25:
        return "strong"
    if second["return"] > 0 and full["max_drawdown"] >= -0.35:
        return "watch"
    return "fragile"


if __name__ == "__main__":
    main()
