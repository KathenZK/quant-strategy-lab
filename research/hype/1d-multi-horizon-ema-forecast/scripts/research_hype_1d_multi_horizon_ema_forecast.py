from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-multi-horizon-ema-forecast"
ENGINE_PATH = (
    ROOT
    / "research/_shared-kernels/multi-horizon-ema-forecast/v1/engine.py"
)
ENGINE_SHA256 = "63d754088ac55b958b5a5536d4ae8f5049d6b6c9c48a0fca7dc89c770d6e31c4"
FAMILY_NAME = "HYPE-1D-Multi-Horizon-EMA-Forecast"
FAMILY_ALIAS = "HYPE-1D-MHEF"
TIMEFRAME = "1d"

EMA_PAIRS = ((8, 32), (16, 64), (32, 128), (64, 256))
EMA_WEIGHTS = (0.2, 0.3, 0.3, 0.2)
EWMAC_SCALARS = {
    (8, 32): 5.30,
    (16, 64): 3.75,
    (32, 128): 2.65,
    (64, 256): 1.87,
}
DAILY_VOL_SPAN = 35
STANDARD_FORECAST_CAP = 20.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Run {FAMILY_NAME} baseline research.")
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
        help="Date embedded in report and artifact filenames.",
    )
    return parser.parse_args()


def load_engine() -> object:
    digest = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if digest != ENGINE_SHA256:
        raise RuntimeError(
            f"shared kernel SHA mismatch: expected {ENGINE_SHA256}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location(
        "multi_horizon_ema_forecast_v1_daily_adapter",
        ENGINE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import shared kernel: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    original_periods_per_year = module.periods_per_year

    def periods_per_year(timeframe: str) -> int:
        if timeframe == TIMEFRAME:
            return 365
        return original_periods_per_year(timeframe)

    module.periods_per_year = periods_per_year
    return module


def aggregate_complete_daily(hourly: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    source = hourly.copy()
    required = {
        "ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "is_closed",
    }
    missing_columns = sorted(required.difference(source.columns))
    if missing_columns:
        raise ValueError(f"hourly data missing required columns: {missing_columns}")
    source["ts"] = pd.to_datetime(source["ts"], utc=True)
    if not pd.api.types.is_bool_dtype(source["is_closed"].dtype):
        raise ValueError("hourly is_closed must have boolean dtype")
    if source[list(required)].isna().any(axis=None):
        raise ValueError("hourly data contains critical nulls")
    duplicate_hourly = int(source["ts"].duplicated(keep=False).sum())
    if duplicate_hourly:
        raise ValueError(f"hourly data has {duplicate_hourly} duplicate ts rows")

    source = source.sort_values("ts").reset_index(drop=True)
    source["utc_day"] = source["ts"].dt.floor("1D")
    complete_days: list[pd.Timestamp] = []
    for utc_day, group in source.groupby("utc_day", sort=True):
        expected_hours = pd.date_range(utc_day, periods=24, freq="1h")
        actual_hours = pd.DatetimeIndex(group["ts"])
        if (
            len(group) == 24
            and actual_hours.equals(expected_hours)
            and bool(group["is_closed"].all())
        ):
            complete_days.append(pd.Timestamp(utc_day))

    total_bins = int(source["utc_day"].nunique())
    source = source.loc[source["utc_day"].isin(complete_days)].set_index("ts")
    if source.empty:
        raise RuntimeError("HYPE 1d aggregation found no complete closed UTC day")
    grouped = source.resample("1D", label="left", closed="left")
    daily = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        quote_volume=("quote_volume", "sum"),
        trade_count=("trade_count", "sum"),
        source_hours=("open", "count"),
    )
    daily = daily.dropna(subset=["open", "high", "low", "close"])
    daily["vwap"] = daily["quote_volume"] / daily["volume"].replace(0.0, np.nan)
    daily["is_closed"] = True
    daily["ts"] = daily.index
    daily = daily.reset_index(drop=True)

    expected = pd.date_range(daily["ts"].iloc[0], daily["ts"].iloc[-1], freq="1D")
    missing = expected.difference(pd.DatetimeIndex(daily["ts"]))
    duplicate = int(daily["ts"].duplicated().sum())
    null_rows = int(
        daily[
            [
                "ts",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trade_count",
            ]
        ]
        .isna()
        .any(axis=1)
        .sum()
    )
    invalid_ohlc = int(
        (
            (daily[["open", "high", "low", "close"]] <= 0.0).any(axis=1)
            | daily["high"].lt(daily[["open", "close", "low"]].max(axis=1))
            | daily["low"].gt(daily[["open", "close", "high"]].min(axis=1))
        ).sum()
    )
    blocker_count = len(missing) + duplicate + null_rows + invalid_ohlc
    quality = {
        "source_timeframe": "1h",
        "ts_semantics": "candle open timestamp",
        "aggregation": "UTC 1D, label=left, closed=left; retain exactly 24 explicit closed hourly bars",
        "rows": int(len(daily)),
        "first_ts": pd.Timestamp(daily["ts"].iloc[0]).isoformat(),
        "last_ts": pd.Timestamp(daily["ts"].iloc[-1]).isoformat(),
        "expected_rows": int(len(expected)),
        "missing_daily_bars": int(len(missing)),
        "duplicate_ts": duplicate,
        "critical_null_rows": null_rows,
        "invalid_ohlc_rows": invalid_ohlc,
        "dropped_incomplete_daily_bins": total_bins - int(len(daily)),
        "blocker_count": int(blocker_count),
    }
    if blocker_count:
        raise RuntimeError(f"HYPE 1d aggregation quality blockers: {quality}")
    return daily, quality


def build_classic_ewmac_forecasts(daily: pd.DataFrame, engine: object) -> pd.DataFrame:
    frame = daily.copy().sort_values("ts").reset_index(drop=True)
    close = pd.to_numeric(frame["close"], errors="coerce")
    log_return = np.log(close / close.shift(1))
    daily_return_vol = log_return.ewm(
        span=DAILY_VOL_SPAN,
        adjust=False,
        min_periods=DAILY_VOL_SPAN,
    ).std(bias=False)
    daily_price_vol = close * daily_return_vol
    frame["daily_return_volatility"] = daily_return_vol
    frame["daily_price_volatility"] = daily_price_vol

    forecast_columns: list[str] = []
    for fast, slow in EMA_PAIRS:
        fast_ema = engine.ema(close, fast)
        slow_ema = engine.ema(close, slow)
        raw = (fast_ema - slow_ema) / daily_price_vol.replace(0.0, np.nan)
        standard_forecast = (raw * EWMAC_SCALARS[(fast, slow)]).clip(
            -STANDARD_FORECAST_CAP,
            STANDARD_FORECAST_CAP,
        )
        normalized_forecast = standard_forecast / STANDARD_FORECAST_CAP
        stem = f"{fast}_{slow}"
        frame[f"ema_fast_{stem}"] = fast_ema
        frame[f"ema_slow_{stem}"] = slow_ema
        frame[f"raw_forecast_{stem}"] = raw
        frame[f"standard_forecast_{stem}"] = standard_forecast
        frame[f"forecast_{stem}"] = normalized_forecast
        forecast_columns.append(f"forecast_{stem}")

    frame["forecast"] = (
        frame[forecast_columns]
        .mul(np.asarray(EMA_WEIGHTS), axis=1)
        .sum(axis=1, min_count=len(forecast_columns))
        .clip(-1.0, 1.0)
    )
    return frame


def run_daily_suite(engine: object) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    hourly, hourly_quality = engine.audit_and_load_market(ROOT, "1h")
    daily, daily_quality = aggregate_complete_daily(hourly)
    funding, funding_quality = engine.load_and_audit_funding(ROOT)
    features = build_classic_ewmac_forecasts(daily, engine)
    forecast_columns = [f"forecast_{fast}_{slow}" for fast, slow in EMA_PAIRS]
    valid = features[["forecast", *forecast_columns]].notna().all(axis=1)
    valid_indices = np.flatnonzero(valid.to_numpy())
    if not len(valid_indices):
        raise RuntimeError("classic EWMAC produced no complete daily forecast")
    first_signal_index = int(valid_indices[0])
    start_index = first_signal_index + 1
    if start_index >= len(features):
        raise RuntimeError("no daily bar remains after the first complete forecast")

    config = engine.ForecastConfig()
    results = []
    for buffer in (0.0, 0.1):
        results.append(
            engine.backtest_target(
                features,
                funding,
                features["forecast"],
                name=f"ensemble_buffer_{buffer:.2f}",
                timeframe=TIMEFRAME,
                buffer=buffer,
                config=config,
                start_index=start_index,
            )
        )
    for fast, slow in EMA_PAIRS:
        results.append(
            engine.backtest_target(
                features,
                funding,
                features[f"forecast_{fast}_{slow}"],
                name=f"sleeve_{fast}_{slow}",
                timeframe=TIMEFRAME,
                buffer=0.0,
                config=config,
                start_index=start_index,
            )
        )
    results.append(
        engine.backtest_target(
            features,
            funding,
            pd.Series(1.0, index=features.index),
            name="perpetual_buy_hold_1x",
            timeframe=TIMEFRAME,
            buffer=0.0,
            config=config,
            start_index=start_index,
        )
    )

    payload = {
        "family_name": FAMILY_NAME,
        "family_alias": FAMILY_ALIAS,
        "strategy_family_mechanism": "classic daily EWMAC forecast fusion",
        "market": "Binance USD-M Futures",
        "symbol": "HYPEUSDT",
        "display_symbol": "HYPE/USDT:USDT",
        "timeframe": TIMEFRAME,
        "status": "explore / not promoted / not live-ready",
        "hourly_source_quality": hourly_quality,
        "daily_quality": daily_quality,
        "funding_quality": funding_quality,
        "config": {
            "ema_pairs": [list(pair) for pair in EMA_PAIRS],
            "weights": list(EMA_WEIGHTS),
            "ewmac_scalars": {
                f"{fast}_{slow}": scalar
                for (fast, slow), scalar in EWMAC_SCALARS.items()
            },
            "daily_volatility_span": DAILY_VOL_SPAN,
            "standard_forecast_cap": STANDARD_FORECAST_CAP,
            "normalized_position_cap": 1.0,
            "fee_per_turnover": config.fee_per_turnover,
            "slippage_per_turnover": config.slippage_per_turnover,
            "buffers": [0.0, 0.1],
            "execution": "closed UTC daily forecast at t; target position executed at t+1 daily open",
            "funding_ordering": "funding in (previous open, current open] is charged to the previously held position before rebalance",
            "end_of_sample": "open position is marked at the final open and is not forcibly liquidated",
        },
        "forecast_start_ts": pd.Timestamp(
            features["ts"].iloc[first_signal_index]
        ).isoformat(),
        "backtest_start_ts": pd.Timestamp(features["ts"].iloc[start_index]).isoformat(),
        "results": [
            {
                "name": result.name,
                "buffer": result.buffer,
                "metrics": result.metrics,
                "slices": result.slices,
            }
            for result in results
        ],
    }
    paths = {result.name: result.path for result in results}
    paths["forecasts"] = features.loc[
        start_index:,
        [
            "ts",
            "open",
            "high",
            "low",
            "close",
            "daily_return_volatility",
            "daily_price_volatility",
            *forecast_columns,
            "forecast",
        ],
    ].reset_index(drop=True)
    return payload, paths


def number(value: object, digits: int = 2) -> str:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not math.isfinite(parsed):
        return "n/a"
    return f"{parsed:.{digits}f}"


def pct(value: object) -> str:
    parsed = number(value)
    return "n/a" if parsed == "n/a" else f"{parsed}%"


def render_report(
    payload: dict[str, Any],
    *,
    artifact_stem: str,
    run_date: str,
) -> str:
    results = {str(item["name"]): item for item in payload["results"]}
    exact = results["ensemble_buffer_0.00"]["metrics"]
    buffered = results["ensemble_buffer_0.10"]["metrics"]
    buy_hold = results["perpetual_buy_hold_1x"]["metrics"]
    daily_quality = payload["daily_quality"]
    funding_quality = payload["funding_quality"]
    result_order = [
        "ensemble_buffer_0.00",
        "ensemble_buffer_0.10",
        "sleeve_8_32",
        "sleeve_16_64",
        "sleeve_32_128",
        "sleeve_64_256",
        "perpetual_buy_hold_1x",
    ]
    headline_rows = []
    for name in result_order:
        metrics = results[name]["metrics"]
        headline_rows.append(
            "| `{name}` | {gross} | {net} | {mdd} | {sharpe} | {avg_pos} | {turnover} |".format(
                name=name,
                gross=pct(metrics["gross_return_pct"]),
                net=pct(metrics["net_return_pct"]),
                mdd=pct(metrics["max_drawdown_net_pct"]),
                sharpe=number(metrics["sharpe_net"]),
                avg_pos=number(metrics["average_abs_position"], 3),
                turnover=number(metrics["total_turnover"], 1),
            )
        )
    slice_rows = []
    for item in results["ensemble_buffer_0.10"]["slices"]:
        slice_rows.append(
            "| `{window}` | {ret} | {mdd} | {sharpe} | {turnover} |".format(
                window=item["window"],
                ret=pct(item["return_pct"]),
                mdd=pct(item["max_drawdown_pct"]),
                sharpe=number(item["sharpe"]),
                turnover=number(item["turnover"], 1),
            )
        )
    if buffered["net_return_pct"] > 0.0:
        conclusion = (
            f"`0.10` 缓冲组合净收益为 `{pct(buffered['net_return_pct'])}`，"
            "但有效回测区间不足一年，只能视为短样本观察，不能登记或推进。"
        )
    else:
        conclusion = (
            f"`0.10` 缓冲组合净收益为 `{pct(buffered['net_return_pct'])}`，"
            "日线降频仍未形成正收益。"
        )
    return "\n".join(
        [
            f"# {FAMILY_NAME} 经典 EWMAC 日线回测（{run_date}）",
            "",
            f"- Family：`{FAMILY_NAME}`（`{FAMILY_ALIAS}`）",
            "- 状态：`explore / not promoted / not live-ready`",
            "- 市场：Binance USD-M Futures `HYPEUSDT` perpetual，UTC `1d`",
            f"- 日线数据：`{daily_quality['first_ts']}` → `{daily_quality['last_ts']}`；回测从 `{payload['backtest_start_ts']}` 开始",
            "- 成本：每单位换手手续费 `0.001` + adverse slippage `0.0004`；纳入实际 funding",
            "- 切片仅作事后审计，不用于参数选择",
            "",
            "## 结论",
            "",
            conclusion,
            f"同期 1x 永续买入持有净收益为 `{pct(buy_hold['net_return_pct'])}`；精确调仓组合为 `{pct(exact['net_return_pct'])}`。",
            "",
            "HYPE 上市历史较短，EMA `64/256` 使前 256 个交易日只能用于 warmup，剩余有效区间有限。无论结果正负，都不能据此判断跨 regime 稳健性。",
            "",
            "## 日线适配",
            "",
            "- 保留 EMA `8/32`、`16/64`、`32/128`、`64/256` 与权重 `0.2/0.3/0.3/0.2`。",
            "- 由于原 intraday 滚动校准需要约 511 根日 K、超过 HYPE 全部历史，日线改用经典 CTA/EWMAC 固定 scalar。",
            "- `daily_price_vol = close × EWMAStd(log_return, span=35)`。",
            "- `raw = (EMA_fast - EMA_slow) / daily_price_vol`。",
            "- scalar 依次为 `5.30 / 3.75 / 2.65 / 1.87`；标准 forecast 裁剪到 `[-20,20]`，再除以 `20` 映射到 `[-1x,1x]`。",
            "- 当前日 K 收盘确认，下一日 open 调仓；同时测试精确跟踪与 `0.10` no-trade buffer。",
            "",
            "## 全区间结果",
            "",
            "| 运行 | 毛收益 | 净收益 | 最大回撤 | Sharpe | 平均绝对仓位 | 总换手 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            *headline_rows,
            "",
            "## 最近区间（0.10 缓冲）",
            "",
            "| 窗口 | 收益 | 最大回撤 | Sharpe | 换手 |",
            "| --- | ---: | ---: | ---: | ---: |",
            *slice_rows,
            "",
            "## 数据质量",
            "",
            f"- 输入为已通过 raw/normalized 对齐门的标准 `1h` 数据湖，聚合为完整 UTC 日：`{daily_quality['rows']}` 根，missing `{daily_quality['missing_daily_bars']}`，blocker `{daily_quality['blocker_count']}`。",
            f"- Funding：`{funding_quality['rows']}` 条，最大间隔 `{number(funding_quality['max_gap_hours'], 1)}h`，blocker `{funding_quality['blocker_count']}`。",
            "",
            "## 证据",
            "",
            f"- Summary：[../artifacts/{artifact_stem}-summary.json](../artifacts/{artifact_stem}-summary.json)",
            f"- Forecast path：[../artifacts/{artifact_stem}-forecasts.csv](../artifacts/{artifact_stem}-forecasts.csv)",
            f"- Equity / turnover paths：[../artifacts/{artifact_stem}-paths.csv](../artifacts/{artifact_stem}-paths.csv)",
            f"- 脚本：[../scripts/{Path(__file__).name}](../scripts/{Path(__file__).name})",
            f"- 共享执行内核：[../../../_shared-kernels/multi-horizon-ema-forecast/v1/engine.py](../../../_shared-kernels/multi-horizon-ema-forecast/v1/engine.py)，SHA256 `{ENGINE_SHA256}`",
            "",
            "## 状态",
            "",
            "`explore / not promoted / not live-ready`。日线历史长度不足以覆盖多个市场 regime，本结果不构成版本登记或 runner 输入。",
            "",
        ]
    )


def main() -> None:
    args = parse_args()
    engine = load_engine()
    artifact_stem = f"hype-1d-mhef-classic-ewmac-{args.run_date}"
    payload, paths = run_daily_suite(engine)
    payload["run_date"] = args.run_date
    payload["kernel"] = {
        "path": str(ENGINE_PATH.relative_to(ROOT)),
        "sha256": ENGINE_SHA256,
    }
    payload["artifacts"] = {
        "summary": f"artifacts/{artifact_stem}-summary.json",
        "forecasts": f"artifacts/{artifact_stem}-forecasts.csv",
        "paths": f"artifacts/{artifact_stem}-paths.csv",
    }
    engine.write_suite_outputs(
        family_dir=FAMILY_DIR,
        artifact_stem=artifact_stem,
        payload=payload,
        paths=paths,
    )
    report_path = (
        FAMILY_DIR
        / "notes"
        / f"hype-1d-mhef-classic-ewmac-backtest-{args.run_date}.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_report(payload, artifact_stem=artifact_stem, run_date=args.run_date),
        encoding="utf-8",
    )
    headline = {
        result["name"]: result["metrics"]
        for result in payload["results"]
        if result["name"]
        in {"ensemble_buffer_0.00", "ensemble_buffer_0.10", "perpetual_buy_hold_1x"}
    }
    print(json.dumps(headline, ensure_ascii=False, indent=2))
    print(f"report -> {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
