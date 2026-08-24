#!/usr/bin/env python3
"""Run the fixed GOLD 1D 1M/3M/12M multi-speed TSMOM baseline."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/gold/1d-multi-speed-tsmom"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
RAW_ROOT = (
    ROOT
    / "data/raw/ohlcv/exchange=comex/market_type=futures/timeframe=1d"
    / "source=github_stooq_commodities_snapshot"
)
SYMBOL_FILE = "symbol=gc_f.parquet"

FAMILY_NAME = "GOLD-1D-Multi-Speed-TSMOM"
FAMILY_ALIAS = "GOLD-1D-MS-TSMOM"
STRATEGIES = ("tsmom_1m", "tsmom_3m", "tsmom_12m", "composite_1_3_12m")
STRATEGY_LABELS = {
    "tsmom_1m": "1M",
    "tsmom_3m": "3M",
    "tsmom_12m": "12M",
    "composite_1_3_12m": "Composite",
}
COST_BPS = (0.0, 2.0)
PRIMARY_COST_BPS = 2.0
TARGET_VOL = 0.10
VOL_COM = 60.0
VOL_MIN_PERIODS = 60
ANNUALIZER = 252
RISK_FREE_RATE = 0.0
RECENT_WINDOWS = {
    "1d": pd.Timedelta(days=0),
    "7d": pd.Timedelta(days=6),
    "1m": pd.DateOffset(months=1),
    "3m": pd.DateOffset(months=3),
    "6m": pd.DateOffset(months=6),
    "1y": pd.DateOffset(years=1),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--allow-untrusted", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def atomic_write_bytes(path: Path, content: bytes, *, force: bool) -> None:
    if path.exists() and not force:
        if path.read_bytes() == content:
            return
        raise RuntimeError(f"artifact exists; use --force to replace: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.stem}-",
        suffix=f"{path.suffix}.tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path: Path, payload: Any, *, force: bool) -> None:
    encoded = (
        json.dumps(sanitize(payload), ensure_ascii=False, indent=2, allow_nan=False).encode()
        + b"\n"
    )
    atomic_write_bytes(path, encoded, force=force)


def write_csv(path: Path, frame: pd.DataFrame, *, force: bool) -> None:
    encoded = frame.to_csv(index=False, lineterminator="\n").encode()
    atomic_write_bytes(path, encoded, force=force)


def write_text(path: Path, content: str, *, force: bool) -> None:
    atomic_write_bytes(path, content.encode(), force=force)


def load_raw(*, allow_untrusted: bool) -> tuple[pd.DataFrame, dict[str, Any]]:
    files = sorted(RAW_ROOT.glob(f"date=*/{SYMBOL_FILE}"))
    if not files:
        raise FileNotFoundError(
            "no Stooq GC.F raw partitions; run fetch_gold_gc_stooq_snapshot.py first"
        )
    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    required = {
        "ts",
        "session_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_interest",
        "exchange",
        "symbol",
        "market_type",
        "timeframe",
        "source",
        "source_dataset_id",
        "roll_adjustment",
        "quality_status",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise RuntimeError(f"raw GC.F partitions missing columns: {missing}")
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True, errors="raise")
    frame = frame.sort_values("ts").reset_index(drop=True)
    price_columns = ["open", "high", "low", "close"]
    price_nulls = {column: int(frame[column].isna().sum()) for column in price_columns}
    invalid_ohlc = int(
        (
            frame[price_columns].le(0.0).any(axis=1)
            | frame["high"].lt(frame[["open", "close", "low"]].max(axis=1))
            | frame["low"].gt(frame[["open", "close", "high"]].min(axis=1))
        ).sum()
    )
    identity = {
        "exchange": sorted(frame["exchange"].astype(str).unique().tolist()),
        "symbol": sorted(frame["symbol"].astype(str).unique().tolist()),
        "market_type": sorted(frame["market_type"].astype(str).unique().tolist()),
        "timeframe": sorted(frame["timeframe"].astype(str).unique().tolist()),
        "source": sorted(frame["source"].astype(str).unique().tolist()),
        "quality_status": sorted(frame["quality_status"].astype(str).unique().tolist()),
    }
    identity_ok = identity == {
        "exchange": ["comex"],
        "symbol": ["GC.F"],
        "market_type": ["futures"],
        "timeframe": ["1d"],
        "source": ["github_stooq_commodities_snapshot"],
        "quality_status": ["raw_unaccepted"],
    }
    mechanical_blockers = (
        sum(price_nulls.values())
        + invalid_ohlc
        + int(frame["ts"].duplicated().sum())
        + int(not frame["ts"].is_monotonic_increasing)
        + int(not identity_ok)
    )
    quality = {
        "rows": int(len(frame)),
        "first_ts": frame["ts"].iloc[0].isoformat(),
        "last_ts": frame["ts"].iloc[-1].isoformat(),
        "duplicate_ts": int(frame["ts"].duplicated().sum()),
        "price_nulls": price_nulls,
        "volume_null_rows": int(frame["volume"].isna().sum()),
        "open_interest_null_rows": int(frame["open_interest"].isna().sum()),
        "invalid_ohlc_rows": invalid_ohlc,
        "identity": identity,
        "mechanical_price_blockers": int(mechanical_blockers),
        "quality_status": "raw_unaccepted",
        "accepted_for_strategy_evidence": False,
    }
    if mechanical_blockers:
        raise RuntimeError(f"GC.F mechanical price blockers: {quality}")
    if not allow_untrusted:
        raise RuntimeError(
            "GC.F is raw_unaccepted; rerun with --allow-untrusted for an explicit "
            "exploratory-only backtest"
        )
    return frame, quality


def last_complete_month_cutoff(frame: pd.DataFrame) -> pd.Timestamp:
    final = pd.Timestamp(frame["ts"].iloc[-1])
    final_naive = final.tz_convert("UTC").tz_localize(None)
    prior_month_end = final_naive.to_period("M").start_time - pd.Timedelta(days=1)
    eligible = frame.loc[frame["ts"].dt.tz_localize(None).le(prior_month_end), "ts"]
    if eligible.empty:
        raise RuntimeError("no complete calendar month in source")
    return pd.Timestamp(eligible.iloc[-1])


def build_features(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = raw.copy().sort_values("ts").reset_index(drop=True)
    cutoff = last_complete_month_cutoff(frame)
    frame = frame.loc[frame["ts"].le(cutoff)].reset_index(drop=True)
    frame["daily_return"] = frame["close"].pct_change(fill_method=None)
    shifted_square = frame["daily_return"].shift(1).pow(2)
    frame["ewma_variance"] = shifted_square.ewm(
        com=VOL_COM,
        adjust=False,
        min_periods=VOL_MIN_PERIODS,
    ).mean()
    frame["sigma_ann"] = np.sqrt(frame["ewma_variance"] * ANNUALIZER)
    frame["month"] = frame["ts"].dt.tz_localize(None).dt.to_period("M").astype(str)
    month_end = frame.groupby("month", sort=True, as_index=False).tail(1).copy()
    month_end = month_end.sort_values("ts").reset_index(drop=True)
    month_end["return_1m"] = month_end["close"].pct_change(1, fill_method=None)
    month_end["return_3m"] = month_end["close"].pct_change(3, fill_method=None)
    month_end["return_12m"] = month_end["close"].pct_change(12, fill_method=None)
    month_end["forecast_1m"] = np.sign(month_end["return_1m"])
    month_end["forecast_3m"] = np.sign(month_end["return_3m"])
    month_end["forecast_12m"] = np.sign(month_end["return_12m"])
    month_end["forecast_composite"] = month_end[
        ["forecast_1m", "forecast_3m", "forecast_12m"]
    ].mean(axis=1, skipna=False)
    forecast_map = {
        "tsmom_1m": "forecast_1m",
        "tsmom_3m": "forecast_3m",
        "tsmom_12m": "forecast_12m",
        "composite_1_3_12m": "forecast_composite",
    }
    for strategy, forecast_column in forecast_map.items():
        month_end[f"target_{strategy}"] = (
            month_end[forecast_column] * TARGET_VOL / month_end["sigma_ann"]
        )
    common_valid = month_end[
        ["forecast_1m", "forecast_3m", "forecast_12m", "forecast_composite", "sigma_ann"]
    ].notna().all(axis=1) & month_end["sigma_ann"].gt(0.0)
    month_end["common_valid"] = common_valid
    for strategy in STRATEGIES:
        month_end.loc[~common_valid, f"target_{strategy}"] = np.nan
    month_end["applied_next_month_in_sample"] = month_end["ts"].lt(frame["ts"].iloc[-1])
    return frame, month_end


def expand_positions(
    frame: pd.DataFrame,
    month_end: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    path = frame.copy()
    active_masks: list[pd.Series] = []
    daily_index = pd.DatetimeIndex(path["ts"])
    for strategy in STRATEGIES:
        events = pd.Series(
            month_end[f"target_{strategy}"].to_numpy("float64"),
            index=pd.DatetimeIndex(month_end["ts"]),
        )
        announced = events.reindex(daily_index).ffill()
        held = announced.shift(1)
        active_masks.append(held.notna())
        path[f"position_{strategy}"] = held.fillna(0.0).to_numpy("float64")
        path[f"turnover_{strategy}"] = (
            path[f"position_{strategy}"]
            .diff()
            .fillna(path[f"position_{strategy}"].abs())
            .abs()
        )
        path[f"gross_return_{strategy}"] = (
            path[f"position_{strategy}"] * path["daily_return"]
        ).fillna(0.0)
    common_active = pd.concat(active_masks, axis=1).all(axis=1)
    active_indices = np.flatnonzero(common_active.to_numpy())
    if not len(active_indices):
        raise RuntimeError("no common active sample after 12M warmup and next-day lag")
    first_active = int(active_indices[0])
    start_ts = pd.Timestamp(path["ts"].iloc[first_active])
    path = path.iloc[first_active:].reset_index(drop=True)
    for strategy in STRATEGIES:
        gross = path[f"gross_return_{strategy}"]
        path[f"gross_equity_{strategy}"] = (1.0 + gross).cumprod()
        for cost_bps in COST_BPS:
            slug = cost_slug(cost_bps)
            cost = path[f"turnover_{strategy}"] * (cost_bps / 10_000.0)
            net = gross - cost
            path[f"cost_{strategy}_{slug}"] = cost
            path[f"net_return_{strategy}_{slug}"] = net
            path[f"net_equity_{strategy}_{slug}"] = (1.0 + net).cumprod()
    return path, start_ts


def cost_slug(cost_bps: float) -> str:
    return f"{cost_bps:g}bps".replace(".", "p")


def drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def compounded_return(returns: pd.Series) -> float:
    return float((1.0 + returns.astype("float64")).prod() - 1.0)


def performance_metrics(
    path: pd.DataFrame,
    *,
    strategy: str,
    cost_bps: float,
) -> dict[str, Any]:
    slug = cost_slug(cost_bps)
    net = path[f"net_return_{strategy}_{slug}"].astype("float64")
    gross = path[f"gross_return_{strategy}"].astype("float64")
    turnover = path[f"turnover_{strategy}"].astype("float64")
    position = path[f"position_{strategy}"].astype("float64")
    equity = (1.0 + net).cumprod()
    dd = drawdown(equity)
    start = pd.Timestamp(path["ts"].iloc[0])
    end = pd.Timestamp(path["ts"].iloc[-1])
    years = max((end - start).total_seconds() / (365.25 * 86400.0), 1.0 / ANNUALIZER)
    total_net = float(equity.iloc[-1] - 1.0)
    total_gross = compounded_return(gross)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    annual_return = float(net.mean() * ANNUALIZER)
    annual_vol = float(net.std(ddof=1) * math.sqrt(ANNUALIZER))
    sharpe = (
        float((annual_return - RISK_FREE_RATE) / annual_vol)
        if annual_vol > 0.0
        else math.nan
    )
    downside = np.minimum(net.to_numpy("float64"), 0.0)
    downside_dev = float(np.sqrt(np.mean(np.square(downside))) * math.sqrt(ANNUALIZER))
    sortino = (
        float((annual_return - RISK_FREE_RATE) / downside_dev)
        if downside_dev > 0.0
        else math.nan
    )
    max_drawdown = float(dd.min())
    calmar = float(cagr / abs(max_drawdown)) if max_drawdown < 0.0 else math.nan
    month_key = path["ts"].dt.tz_localize(None).dt.to_period("M")
    monthly = net.groupby(month_key).apply(compounded_return)
    return {
        "strategy": strategy,
        "label": STRATEGY_LABELS[strategy],
        "cost_bps_one_way": cost_bps,
        "start_ts": start.isoformat(),
        "end_ts": end.isoformat(),
        "observations": int(len(path)),
        "months": int(len(monthly)),
        "years": years,
        "cagr": cagr,
        "annualized_arithmetic_return": annual_return,
        "annualized_volatility": annual_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "calmar": calmar,
        "positive_month_ratio": float(monthly.gt(0.0).mean()),
        "positive_months": int(monthly.gt(0.0).sum()),
        "daily_win_rate": float(net.gt(0.0).mean()),
        "annualized_turnover": float(turnover.sum() / years),
        "total_turnover": float(turnover.sum()),
        "gross_total_return": total_gross,
        "net_total_return": total_net,
        "cost_drag_total_return": total_gross - total_net,
        "simple_cost_sum": float((turnover * (cost_bps / 10_000.0)).sum()),
        "average_abs_position": float(position.abs().mean()),
        "max_abs_position": float(position.abs().max()),
    }


def period_returns(
    path: pd.DataFrame,
    *,
    frequency: str,
) -> pd.DataFrame:
    if frequency == "year":
        key = path["ts"].dt.year
        key_name = "year"
    elif frequency == "month":
        key = path["ts"].dt.tz_localize(None).dt.to_period("M").astype(str)
        key_name = "month"
    else:
        raise ValueError(f"unsupported frequency: {frequency}")
    rows: list[dict[str, Any]] = []
    for strategy in STRATEGIES:
        gross_series = path[f"gross_return_{strategy}"]
        for cost_bps in COST_BPS:
            slug = cost_slug(cost_bps)
            net_series = path[f"net_return_{strategy}_{slug}"]
            grouped = path.groupby(key, sort=True).indices
            for period, indices in grouped.items():
                group = path.iloc[indices]
                net = net_series.iloc[indices]
                gross = gross_series.iloc[indices]
                equity = (1.0 + net).cumprod()
                rows.append(
                    {
                        key_name: int(period) if frequency == "year" else str(period),
                        "strategy": strategy,
                        "label": STRATEGY_LABELS[strategy],
                        "cost_bps_one_way": cost_bps,
                        "observations": int(len(group)),
                        "start_ts": pd.Timestamp(group["ts"].iloc[0]).isoformat(),
                        "end_ts": pd.Timestamp(group["ts"].iloc[-1]).isoformat(),
                        "gross_return": compounded_return(gross),
                        "net_return": compounded_return(net),
                        "max_drawdown": float(drawdown(equity).min()),
                        "turnover": float(group[f"turnover_{strategy}"].sum()),
                        "average_abs_position": float(group[f"position_{strategy}"].abs().mean()),
                    }
                )
    result = pd.DataFrame(rows)
    if frequency == "year" and not result.empty:
        min_year = int(result["year"].min())
        max_year = int(result["year"].max())
        result["partial_year"] = result["year"].isin([min_year, max_year])
    return result


def recent_slices(path: pd.DataFrame) -> pd.DataFrame:
    end = pd.Timestamp(path["ts"].iloc[-1])
    rows: list[dict[str, Any]] = []
    for window, offset in RECENT_WINDOWS.items():
        if isinstance(offset, pd.Timedelta):
            start = end - offset
        else:
            start = end - offset
        sliced = path.loc[path["ts"].ge(start)].reset_index(drop=True)
        if sliced.empty:
            continue
        for strategy in STRATEGIES:
            for cost_bps in COST_BPS:
                slug = cost_slug(cost_bps)
                net = sliced[f"net_return_{strategy}_{slug}"]
                equity = (1.0 + net).cumprod()
                annual_vol = float(net.std(ddof=1) * math.sqrt(ANNUALIZER)) if len(net) > 1 else math.nan
                annual_return = float(net.mean() * ANNUALIZER)
                rows.append(
                    {
                        "window": window,
                        "strategy": strategy,
                        "label": STRATEGY_LABELS[strategy],
                        "cost_bps_one_way": cost_bps,
                        "start_ts": pd.Timestamp(sliced["ts"].iloc[0]).isoformat(),
                        "end_ts": pd.Timestamp(sliced["ts"].iloc[-1]).isoformat(),
                        "observations": int(len(sliced)),
                        "net_return": float(equity.iloc[-1] - 1.0),
                        "max_drawdown": float(drawdown(equity).min()),
                        "sharpe": annual_return / annual_vol if annual_vol > 0.0 else math.nan,
                        "turnover": float(sliced[f"turnover_{strategy}"].sum()),
                        "average_abs_position": float(sliced[f"position_{strategy}"].abs().mean()),
                    }
                )
    return pd.DataFrame(rows)


def build_direction_episodes(path: pd.DataFrame) -> pd.DataFrame:
    strategy = "composite_1_3_12m"
    position = path[f"position_{strategy}"].to_numpy("float64")
    direction = np.sign(position).astype("int64")
    net = path[f"net_return_{strategy}_{cost_slug(PRIMARY_COST_BPS)}"]
    rows: list[dict[str, Any]] = []
    start = 0
    episode_id = 1
    for index in range(1, len(path) + 1):
        changed = index == len(path) or direction[index] != direction[start]
        if not changed:
            continue
        if direction[start] != 0:
            group = path.iloc[start:index]
            episode_net = net.iloc[start:index]
            rows.append(
                {
                    "episode_id": episode_id,
                    "side": "long" if direction[start] > 0 else "short",
                    "entry_ts": pd.Timestamp(group["ts"].iloc[0]).isoformat(),
                    "exit_ts": pd.Timestamp(group["ts"].iloc[-1]).isoformat(),
                    "entry_close": float(group["close"].iloc[0]),
                    "exit_close": float(group["close"].iloc[-1]),
                    "sessions": int(len(group)),
                    "start_position": float(group[f"position_{strategy}"].iloc[0]),
                    "max_abs_position": float(group[f"position_{strategy}"].abs().max()),
                    "net_return": compounded_return(episode_net),
                    "closed_by_reversal": bool(index < len(path)),
                }
            )
            episode_id += 1
        start = index
    return pd.DataFrame(rows)


def pct(value: Any, digits: int = 2) -> str:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not math.isfinite(parsed):
        return "n/a"
    return f"{parsed * 100.0:.{digits}f}%"


def number(value: Any, digits: int = 3) -> str:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not math.isfinite(parsed):
        return "n/a"
    return f"{parsed:.{digits}f}"


def render_report(
    *,
    run_date: str,
    payload: dict[str, Any],
    metrics: pd.DataFrame,
    yearly: pd.DataFrame,
    slices: pd.DataFrame,
    artifact_stem: str,
) -> str:
    metric_rows: list[str] = []
    for _, row in metrics.sort_values(["cost_bps_one_way", "strategy"]).iterrows():
        metric_rows.append(
            "| `{label}` | `{cost:g}` | {cagr} | {ann} | {vol} | {sharpe} | {sortino} | {mdd} | {calmar} | {daily_win} | {pm} | {turnover} | {gross} | {net} |".format(
                label=row["label"],
                cost=row["cost_bps_one_way"],
                cagr=pct(row["cagr"]),
                ann=pct(row["annualized_arithmetic_return"]),
                vol=pct(row["annualized_volatility"]),
                sharpe=number(row["sharpe"]),
                sortino=number(row["sortino"]),
                mdd=pct(row["max_drawdown"]),
                calmar=number(row["calmar"]),
                daily_win=pct(row["daily_win_rate"]),
                pm=pct(row["positive_month_ratio"]),
                turnover=number(row["annualized_turnover"], 2),
                gross=pct(row["gross_total_return"]),
                net=pct(row["net_total_return"]),
            )
        )
    primary = metrics.loc[
        metrics["cost_bps_one_way"].eq(PRIMARY_COST_BPS)
    ].set_index("strategy")
    composite = primary.loc["composite_1_3_12m"]
    best_component = primary.loc[["tsmom_1m", "tsmom_3m", "tsmom_12m"]]["sharpe"].idxmax()
    slice_primary = slices.loc[
        slices["strategy"].eq("composite_1_3_12m")
        & slices["cost_bps_one_way"].eq(PRIMARY_COST_BPS)
    ]
    slice_rows = [
        f"| `{row.window}` | {pct(row.net_return)} | {pct(row.max_drawdown)} | {number(row.sharpe)} | {number(row.turnover, 3)} |"
        for row in slice_primary.itertuples(index=False)
    ]
    yearly_primary = yearly.loc[
        yearly["strategy"].eq("composite_1_3_12m")
        & yearly["cost_bps_one_way"].eq(PRIMARY_COST_BPS)
    ]
    year_rows = [
        f"| `{int(row.year)}`{'*' if row.partial_year else ''} | {pct(row.net_return)} | {pct(row.max_drawdown)} | {number(row.turnover, 3)} |"
        for row in yearly_primary.itertuples(index=False)
    ]
    quality = payload["data_quality"]
    return "\n".join(
        [
            f"# {FAMILY_NAME} 黄金多速度 TSMOM 回测（{run_date}）",
            "",
            f"- Family：`{FAMILY_NAME}`（`{FAMILY_ALIAS}`）",
            "- 状态：`explore / not promoted / not live-ready`",
            "- 市场：Stooq `GC.F` Gold-COMEX continuous futures，session-date `1d`",
            f"- Raw 数据：`{quality['first_ts']}` → `{quality['last_ts']}`；回测只保留到最后完整月 `{payload['backtest_end_ts']}`",
            f"- 有效回测：`{payload['backtest_start_ts']}` → `{payload['backtest_end_ts']}`，共 `{payload['backtest_observations']}` 个日收益",
            "- 成本：`0 bps` 对照 + 单边每单位目标仓位换手 `2 bps` 主口径；无单独 roll 成交成本",
            "- 最近切片只作事后审计，不参与任何参数选择",
            "",
            "## 结论",
            "",
            (
                f"Composite 在 `2 bps` 主口径下 CAGR `{pct(composite['cagr'])}`、年化算术收益 "
                f"`{pct(composite['annualized_arithmetic_return'])}`、实现波动 `{pct(composite['annualized_volatility'])}`、"
                f"Sharpe `{number(composite['sharpe'])}`、最大回撤 `{pct(composite['max_drawdown'])}`、"
                f"正收益月份比例 `{pct(composite['positive_month_ratio'])}`。"
            ),
            (
                f"三个单速度中历史 Sharpe 最高的是 `{STRATEGY_LABELS[best_component]}`；"
                "该比较只是固定分支归因，不构成选择或调参。"
            ),
            "",
            (
                "结果只能视为长期历史形态诊断：主数据虽通过价格序列机械检查，但仍为 "
                "`raw_unaccepted`，且截止 2021 年。连续合约换月映射、roll adjustment、"
                "结算价语义和显式换月交易成本未核验，因此本轮不登记版本、不支持当前可交易性或 live-ready 结论。"
            ),
            "",
            "## 全区间四分支 × 两成本版本",
            "",
            "| 分支 | 单边成本 bps | CAGR | 年化收益 | 年化波动 | Sharpe | Sortino | 最大回撤 | Calmar | 日胜率 | 正收益月 | 年换手 | 毛总收益 | 净总收益 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *metric_rows,
            "",
            "说明：年化收益为日均净收益 × `252`；CAGR 使用实际日历跨度；Sharpe/Sortino 的无风险利率为 0。日胜率为正日收益比例，正收益月按月复利收益大于 0 统计。",
            "",
            "## 最近区间（Composite，2 bps，audit-only）",
            "",
            "| 窗口 | 净收益 | 最大回撤 | Sharpe | 换手 |",
            "| --- | ---: | ---: | ---: | ---: |",
            *slice_rows,
            "",
            "## 分年份（Composite，2 bps）",
            "",
            "| 年 | 净收益 | 最大回撤 | 换手 |",
            "| --- | ---: | ---: | ---: |",
            *year_rows,
            "",
            "`*` 表示有效样本的首年或末年，不是完整自然年。",
            "",
            "## 无未来函数检查",
            "",
            "- `1M/3M/12M` 只在每月最后一根可见日线收盘后计算。",
            "- 月末当日收益仍由旧仓位承担；新目标仓位经 `shift(1)` 后从下一交易日收益开始生效。",
            "- 波动率输入先 `shift(1)`，所以月末 `sigma_ann` 不含月末当日收益；EWMA `com=60`、`adjust=False`。",
            "- 四个分支共享 12M warmup 后的同一有效样本，避免用不同起点比较。",
            "",
            "## 数据质量",
            "",
            f"- 保留 raw rows `{quality['rows']}`；price null `{sum(quality['price_nulls'].values())}`、重复 `{quality['duplicate_ts']}`、非法 OHLC `{quality['invalid_ohlc_rows']}`、机械价格 blocker `{quality['mechanical_price_blockers']}`。",
            f"- Volume null `{quality['volume_null_rows']}`；Open Interest null `{quality['open_interest_null_rows']}`；它们不参与本策略计算。",
            "- Yahoo `GC=F` Kaggle v2 候选有 `441` 行 OHLC 不自洽，已拒绝作为主数据且没有静默修补。",
            "- Stooq `GC.F` 仍缺逐合约/换月/日历/闭合字段核验，`accepted_for_strategy_evidence=false`。",
            "",
            "## 证据与复现",
            "",
            f"- 固定配置：[../artifacts/{artifact_stem}-config.json](../artifacts/{artifact_stem}-config.json)",
            f"- 数据审计：[../artifacts/{artifact_stem}-data-audit.json](../artifacts/{artifact_stem}-data-audit.json)",
            f"- 汇总：[../artifacts/{artifact_stem}-summary.json](../artifacts/{artifact_stem}-summary.json)",
            f"- 指标：[../artifacts/{artifact_stem}-metrics.csv](../artifacts/{artifact_stem}-metrics.csv)",
            f"- 月末信号：[../artifacts/{artifact_stem}-month-end-signals.csv](../artifacts/{artifact_stem}-month-end-signals.csv)",
            f"- 日路径：[../artifacts/{artifact_stem}-daily-paths.csv](../artifacts/{artifact_stem}-daily-paths.csv)",
            f"- 年度结果：[../artifacts/{artifact_stem}-yearly-returns.csv](../artifacts/{artifact_stem}-yearly-returns.csv)",
            f"- 分月结果：[../artifacts/{artifact_stem}-monthly-returns.csv](../artifacts/{artifact_stem}-monthly-returns.csv)",
            f"- 最近切片：[../artifacts/{artifact_stem}-recent-slices.csv](../artifacts/{artifact_stem}-recent-slices.csv)",
            f"- Composite episodes：[../artifacts/{artifact_stem}-episodes.csv](../artifacts/{artifact_stem}-episodes.csv)",
            f"- 交互图：[../artifacts/{artifact_stem}-interactive.html](../artifacts/{artifact_stem}-interactive.html)",
            "- 回测脚本：[../scripts/research_gold_1d_multi_speed_tsmom.py](../scripts/research_gold_1d_multi_speed_tsmom.py)",
            "- 图表脚本：[../scripts/render_gold_1d_multi_speed_tsmom.py](../scripts/render_gold_1d_multi_speed_tsmom.py)",
            "",
            "```bash",
            ".venv/bin/python research/gold/1d-multi-speed-tsmom/scripts/fetch_gold_gc_stooq_snapshot.py --run-date 2026-08-18",
            ".venv/bin/python research/gold/1d-multi-speed-tsmom/scripts/research_gold_1d_multi_speed_tsmom.py --run-date 2026-08-18 --allow-untrusted",
            ".venv/bin/python research/gold/1d-multi-speed-tsmom/scripts/render_gold_1d_multi_speed_tsmom.py --run-date 2026-08-18",
            "```",
            "",
            "## 状态",
            "",
            "`explore / not promoted / not live-ready`。本轮不登记版本；要重开 promotion 讨论，先更换为当前、可核验 roll mapping 的官方或逐合约期货数据。",
            "",
        ]
    )


def self_test() -> None:
    rng = np.random.default_rng(17)
    ts = pd.bdate_range("2018-01-01", periods=900, tz="UTC")
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(ts))))
    raw = pd.DataFrame(
        {
            "ts": ts,
            "session_date": ts.strftime("%Y-%m-%d"),
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1.0,
            "open_interest": 1.0,
        }
    )
    frame, month_end = build_features(raw)
    path, _ = expand_positions(frame, month_end)
    allowed = {-1.0, -1.0 / 3.0, 0.0, 1.0 / 3.0, 1.0}
    observed = set(month_end["forecast_composite"].dropna().round(12).tolist())
    if not observed.issubset({round(value, 12) for value in allowed}):
        raise AssertionError(f"unexpected composite forecasts: {observed}")
    events = month_end.loc[month_end["common_valid"]]
    first_event = pd.Timestamp(events["ts"].iloc[0])
    same_day = frame.index[frame["ts"].eq(first_event)][0]
    expected = float(events["target_composite_1_3_12m"].iloc[0])
    full, _ = expand_positions(frame, month_end)
    next_rows = full.loc[full["ts"].gt(first_event)]
    if next_rows.empty or not math.isclose(
        float(next_rows["position_composite_1_3_12m"].iloc[0]), expected, abs_tol=1e-12
    ):
        raise AssertionError("month-end target did not become effective next session")
    if same_day + 1 >= len(frame):
        raise AssertionError("synthetic sample ended at first signal")
    gross = path["gross_return_composite_1_3_12m"]
    cost = path["turnover_composite_1_3_12m"] * (PRIMARY_COST_BPS / 10_000.0)
    net = path[f"net_return_composite_1_3_12m_{cost_slug(PRIMARY_COST_BPS)}"]
    np.testing.assert_allclose(net.to_numpy(), (gross - cost).to_numpy())
    print("self-test passed")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    raw, quality = load_raw(allow_untrusted=args.allow_untrusted)
    frame, month_end = build_features(raw)
    path, start_ts = expand_positions(frame, month_end)
    metrics = pd.DataFrame(
        [
            performance_metrics(path, strategy=strategy, cost_bps=cost_bps)
            for strategy in STRATEGIES
            for cost_bps in COST_BPS
        ]
    )
    yearly = period_returns(path, frequency="year")
    monthly = period_returns(path, frequency="month")
    slices = recent_slices(path)
    episodes = build_direction_episodes(path)
    artifact_stem = f"gold-1d-ms-tsmom-baseline-{args.run_date}"
    config = {
        "family_name": FAMILY_NAME,
        "family_alias": FAMILY_ALIAS,
        "status": "explore / not promoted / not live-ready",
        "strategies": list(STRATEGIES),
        "signal_lookbacks_months": [1, 3, 12],
        "composite_weights": [1.0 / 3.0] * 3,
        "signal_type": "sign(month_end_close_return)",
        "rebalance": "last available session of each calendar month",
        "execution": "target announced at month-end close; effective from next session close-to-close return",
        "volatility": {
            "return_type": "simple close-to-close",
            "center_of_mass_days": VOL_COM,
            "alpha": 1.0 / (1.0 + VOL_COM),
            "lambda": VOL_COM / (1.0 + VOL_COM),
            "adjust": False,
            "min_periods": VOL_MIN_PERIODS,
            "input_lag_sessions": 1,
            "annualizer": ANNUALIZER,
        },
        "target_volatility": TARGET_VOL,
        "position_formula": "forecast * target_volatility / sigma_ann",
        "position_cap": None,
        "portfolio_covariance_scaling": False,
        "cost_bps_one_way": list(COST_BPS),
        "primary_cost_bps_one_way": PRIMARY_COST_BPS,
        "cost_basis": "absolute change in notional target position; initial position from flat included",
        "separate_roll_transaction_cost": False,
        "risk_free_rate": RISK_FREE_RATE,
        "last_source_month_excluded_as_potentially_incomplete": True,
        "selection": "none; all recent slices audit-only",
        "data_quality_status": "raw_unaccepted",
    }
    data_audit_path = ARTIFACT_DIR / f"{artifact_stem}-data-audit.json"
    data_audit = json.loads(data_audit_path.read_text(encoding="utf-8"))
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "run_date": args.run_date,
        "family_name": FAMILY_NAME,
        "family_alias": FAMILY_ALIAS,
        "status": "explore / not promoted / not live-ready",
        "decision": "EXPLORATORY_ONLY_RAW_UNACCEPTED_NOT_REGISTERED",
        "data_quality": {**data_audit, **quality},
        "config": config,
        "backtest_start_ts": start_ts.isoformat(),
        "backtest_end_ts": pd.Timestamp(path["ts"].iloc[-1]).isoformat(),
        "backtest_observations": int(len(path)),
        "metrics": metrics.to_dict(orient="records"),
        "composite_direction_episodes": int(len(episodes)),
        "limitations": data_audit["acceptance_blockers"]
        + [
            "target-position turnover cost does not separately charge contract rolls",
            "continuous fractional notional ignores contract multiplier and integer sizing",
            "single-asset historical result is not cross-market evidence",
        ],
    }

    write_json(ARTIFACT_DIR / f"{artifact_stem}-config.json", config, force=args.force)
    write_json(ARTIFACT_DIR / f"{artifact_stem}-summary.json", payload, force=args.force)
    write_csv(ARTIFACT_DIR / f"{artifact_stem}-metrics.csv", metrics, force=args.force)
    signal_columns = [
        "ts",
        "month",
        "close",
        "return_1m",
        "return_3m",
        "return_12m",
        "forecast_1m",
        "forecast_3m",
        "forecast_12m",
        "forecast_composite",
        "sigma_ann",
        "target_tsmom_1m",
        "target_tsmom_3m",
        "target_tsmom_12m",
        "target_composite_1_3_12m",
        "common_valid",
        "applied_next_month_in_sample",
    ]
    write_csv(
        ARTIFACT_DIR / f"{artifact_stem}-month-end-signals.csv",
        month_end[signal_columns],
        force=args.force,
    )
    path_columns = ["ts", "open", "high", "low", "close", "daily_return", "sigma_ann"]
    for strategy in STRATEGIES:
        path_columns.extend(
            [
                f"position_{strategy}",
                f"turnover_{strategy}",
                f"gross_return_{strategy}",
                f"gross_equity_{strategy}",
                f"net_return_{strategy}_{cost_slug(PRIMARY_COST_BPS)}",
                f"net_equity_{strategy}_{cost_slug(PRIMARY_COST_BPS)}",
            ]
        )
    write_csv(
        ARTIFACT_DIR / f"{artifact_stem}-daily-paths.csv",
        path[path_columns],
        force=args.force,
    )
    write_csv(ARTIFACT_DIR / f"{artifact_stem}-yearly-returns.csv", yearly, force=args.force)
    write_csv(ARTIFACT_DIR / f"{artifact_stem}-monthly-returns.csv", monthly, force=args.force)
    write_csv(ARTIFACT_DIR / f"{artifact_stem}-recent-slices.csv", slices, force=args.force)
    write_csv(ARTIFACT_DIR / f"{artifact_stem}-episodes.csv", episodes, force=args.force)
    report = render_report(
        run_date=args.run_date,
        payload=payload,
        metrics=metrics,
        yearly=yearly,
        slices=slices,
        artifact_stem=artifact_stem,
    )
    report_path = FAMILY_DIR / "diagnostics" / f"gold-1d-ms-tsmom-backtest-{args.run_date}.md"
    write_text(report_path, report, force=args.force)
    headline = metrics.loc[
        metrics["cost_bps_one_way"].eq(PRIMARY_COST_BPS),
        ["label", "cagr", "annualized_volatility", "sharpe", "max_drawdown", "net_total_return"],
    ]
    print(headline.to_json(orient="records", force_ascii=False, indent=2))
    print(f"report -> {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
