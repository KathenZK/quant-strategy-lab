from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_h4_rsi6_entry_filter_2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


@dataclass(frozen=True, slots=True)
class FilterVariant:
    name: str
    lower: float | None = None
    upper: float | None = None
    mode: str = "none"


VARIANTS = [
    FilterVariant("v35_base"),
    FilterVariant("symmetric_10_90", lower=10.0, upper=90.0, mode="symmetric"),
    FilterVariant("symmetric_20_80", lower=20.0, upper=80.0, mode="symmetric"),
    FilterVariant("symmetric_30_70", lower=30.0, upper=70.0, mode="symmetric"),
    FilterVariant("directional_20_80", lower=20.0, upper=80.0, mode="directional"),
    FilterVariant("directional_30_70", lower=30.0, upper=70.0, mode="directional"),
]


def wilder_rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    relative_strength = avg_gain / avg_loss.replace(0.0, np.nan)
    result = 100.0 - 100.0 / (1.0 + relative_strength)
    result = result.mask((avg_loss == 0.0) & (avg_gain > 0.0), 100.0)
    result = result.mask((avg_gain == 0.0) & (avg_loss > 0.0), 0.0)
    return result.mask((avg_gain == 0.0) & (avg_loss == 0.0), 50.0)


def entry_time_h4_rsi6(frame: pd.DataFrame) -> pd.Series:
    h4 = base.resample_ohlcv(frame, "4h")
    # 4h bucket 的 label 是区间起点；shift(1) 后才是当前 15m 时点已完整收盘的上一根 4h K。
    closed_h4_rsi6 = wilder_rsi(h4["close"], 6).shift(1)
    return closed_h4_rsi6.reindex(frame.index, method="ffill").rename("entry_h4_rsi6")


def load_data(
    warehouse: base.DuckDBWarehouse,
) -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    columns = [
        "ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "is_closed",
        "source",
        "timeframe",
    ]
    normalized_before_dedup = warehouse.load_dataset(
        layer="normalized",
        kind=base.DatasetKind.OHLCV,
        exchange=base.EXCHANGE,
        market_type=base.MarketType.PERP,
        symbol=base.SYMBOL,
        timeframe=base.TIMEFRAME,
        columns=columns,
    )
    if normalized_before_dedup.empty:
        raise RuntimeError("Missing normalized Binance HYPEUSDT 15m OHLCV data.")
    normalized_before_dedup["ts"] = pd.to_datetime(
        normalized_before_dedup["ts"], utc=True
    )
    frame = (
        normalized_before_dedup.sort_values("ts")
        .drop_duplicates("ts", keep="last")
        .set_index("ts")
    )
    if "is_closed" in frame.columns:
        frame = frame.loc[frame["is_closed"].fillna(False).astype(bool)].copy()
    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
    ]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    funding_frame = warehouse.load_dataset(
        layer="normalized",
        kind=base.DatasetKind.FUNDING_RATES,
        exchange=base.EXCHANGE,
        market_type=base.MarketType.PERP,
        symbol=base.SYMBOL,
        columns=["ts", "funding_rate", "source"],
    )
    if funding_frame.empty:
        funding = pd.Series(0.0, index=frame.index, name="funding_rate")
        funding_quality = {"rows": 0, "non_zero_aligned_rows": 0, "null_rates": 0}
    else:
        funding_frame["ts"] = pd.to_datetime(
            funding_frame["ts"], utc=True
        ).dt.floor("15min")
        funding_frame["funding_rate"] = pd.to_numeric(
            funding_frame["funding_rate"], errors="coerce"
        )
        funding_raw = (
            funding_frame.sort_values("ts")
            .drop_duplicates("ts", keep="last")
            .set_index("ts")["funding_rate"]
        )
        funding = funding_raw.reindex(frame.index).fillna(0.0).rename("funding_rate")
        funding_quality = {
            "rows": int(len(funding_frame)),
            "start": funding_frame["ts"].min().isoformat(),
            "end": funding_frame["ts"].max().isoformat(),
            "null_rates": int(funding_frame["funding_rate"].isna().sum()),
            "non_zero_aligned_rows": int(funding.ne(0.0).sum()),
            "aligned_sum_rate": float(funding.sum()),
        }

    quality = build_quality_report(
        warehouse, normalized_before_dedup, frame, funding_quality
    )
    return frame[["open", "high", "low", "close", "volume"]].copy(), funding, quality


def compare_raw_normalized(
    warehouse: base.DuckDBWarehouse, normalized: pd.DataFrame
) -> dict[str, Any]:
    # Raw Binance kline 文件保留交易所原始 schema（open_time，无 identity 内嵌列）；
    # identity 已由 canonical partition path 固定，因此先按路径选文件，再读取内容。
    files = warehouse._filtered_dataset_files(
        layer="raw",
        kind=base.DatasetKind.OHLCV,
        exchange=base.EXCHANGE,
        market_type=base.MarketType.PERP,
        symbol=base.SYMBOL,
        timeframe=base.TIMEFRAME,
    )
    if not files:
        return {"available": False, "reason": "canonical raw OHLCV files not found"}
    with warehouse.connect() as connection:
        raw = connection.execute(
            """
            SELECT open_time AS ts, open, high, low, close, volume,
                   quote_volume, trade_count
            FROM read_parquet(?, hive_partitioning = false, union_by_name = true)
            ORDER BY open_time
            """,
            [files],
        ).fetch_df()
    raw["ts"] = pd.to_datetime(raw["ts"], utc=True)
    raw = raw.sort_values("ts").drop_duplicates("ts", keep="last").set_index("ts")
    common_columns = [
        column
        for column in [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "trade_count",
        ]
        if column in raw.columns and column in normalized.columns
    ]
    joined = raw[common_columns].join(
        normalized[common_columns],
        how="inner",
        lsuffix="_raw",
        rsuffix="_normalized",
    )
    max_abs_diff: dict[str, float] = {}
    mismatch_rows: dict[str, int] = {}
    for column in common_columns:
        raw_values = pd.to_numeric(joined[f"{column}_raw"], errors="coerce")
        normalized_values = pd.to_numeric(
            joined[f"{column}_normalized"], errors="coerce"
        )
        difference = (raw_values - normalized_values).abs()
        max_abs_diff[column] = (
            float(difference.max()) if not difference.empty else 0.0
        )
        mismatch_rows[column] = int(difference.gt(1e-12).sum())
    return {
        "available": True,
        "raw_files": int(len(files)),
        "raw_rows": int(len(raw)),
        "compared_rows": int(len(joined)),
        "common_columns": common_columns,
        "max_abs_diff": max_abs_diff,
        "mismatch_rows": mismatch_rows,
        "identity_source": "canonical partition path",
    }


def build_quality_report(
    warehouse: base.DuckDBWarehouse,
    normalized_before_dedup: pd.DataFrame,
    frame: pd.DataFrame,
    funding_quality: dict[str, Any],
) -> dict[str, Any]:
    expected = pd.date_range(
        frame.index.min(), frame.index.max(), freq="15min", tz="UTC"
    )
    missing = expected.difference(frame.index)
    critical_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
    ]
    nulls = {
        column: int(frame[column].isna().sum())
        for column in critical_columns
        if column in frame.columns
    }
    invalid_ohlc = int(
        (
            frame["high"].lt(frame[["open", "close"]].max(axis=1))
            | frame["low"].gt(frame[["open", "close"]].min(axis=1))
            | frame["high"].lt(frame["low"])
            | frame["volume"].lt(0)
        ).sum()
    )
    source_counts = (
        frame["source"].astype("string").value_counts(dropna=False).to_dict()
        if "source" in frame.columns
        else {}
    )
    return {
        "normalized_rows_before_dedup": int(len(normalized_before_dedup)),
        "rows": int(len(frame)),
        "start": frame.index.min().isoformat(),
        "end": frame.index.max().isoformat(),
        "duplicate_ts_before_dedup": int(
            normalized_before_dedup["ts"].duplicated().sum()
        ),
        "missing_15m_bars": int(len(missing)),
        "first_missing_15m_bars": [ts.isoformat() for ts in missing[:10]],
        "critical_nulls": nulls,
        "invalid_ohlc_rows": invalid_ohlc,
        "is_utc_index": str(frame.index.tz) == "UTC",
        "is_closed_false_or_null_before_filter": int(
            (
                ~normalized_before_dedup.get(
                    "is_closed",
                    pd.Series(True, index=normalized_before_dedup.index),
                )
                .fillna(False)
                .astype(bool)
            ).sum()
        ),
        "source_counts": {str(key): int(value) for key, value in source_counts.items()},
        "raw_vs_normalized": compare_raw_normalized(warehouse, frame),
        "funding": funding_quality,
    }


def quality_gate(quality: dict[str, Any]) -> dict[str, Any]:
    raw_compare = quality.get("raw_vs_normalized", {})
    mismatch_rows = raw_compare.get("mismatch_rows", {})
    checks = {
        "missing_15m_bars": int(quality["missing_15m_bars"]),
        "duplicate_ts_before_dedup": int(quality["duplicate_ts_before_dedup"]),
        "critical_nulls_total": int(sum(quality["critical_nulls"].values())),
        "invalid_ohlc_rows": int(quality["invalid_ohlc_rows"]),
        "is_utc_index": bool(quality["is_utc_index"]),
        "raw_vs_normalized_available": bool(raw_compare.get("available", False)),
        "raw_vs_normalized_mismatch_rows": int(sum(mismatch_rows.values())),
    }
    passed = (
        checks["missing_15m_bars"] == 0
        and checks["duplicate_ts_before_dedup"] == 0
        and checks["critical_nulls_total"] == 0
        and checks["invalid_ohlc_rows"] == 0
        and checks["is_utc_index"]
        and checks["raw_vs_normalized_available"]
        and checks["raw_vs_normalized_mismatch_rows"] == 0
    )
    if not passed:
        raise ValueError(f"data-quality gate failed: {json.dumps(checks)}")
    return {"passed": True, **checks}


def filtered_features(
    features: pd.DataFrame,
    entry_rsi6: pd.Series,
    config: base.V35Config,
    variant: FilterVariant,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    result = features.copy()
    # V35 在 signal bar K0 后的 K2 open 入场。把 K2 open 当时可见的 RSI 映射回 K0，
    # 仅为了复用 canonical backtest engine；策略决策本身仍发生在 K2 open，没有前视。
    rsi_at_entry_for_signal = entry_rsi6.shift(-config.entry_delay_bars)
    original_long = result["long_signal"].astype(bool)
    original_short = result["short_signal"].astype(bool)

    if variant.mode == "none":
        long_allowed = pd.Series(True, index=result.index)
        short_allowed = pd.Series(True, index=result.index)
    elif variant.mode == "symmetric":
        long_allowed = rsi_at_entry_for_signal.gt(float(variant.lower)) & rsi_at_entry_for_signal.lt(
            float(variant.upper)
        )
        short_allowed = long_allowed
    elif variant.mode == "directional":
        long_allowed = rsi_at_entry_for_signal.lt(float(variant.upper))
        short_allowed = rsi_at_entry_for_signal.gt(float(variant.lower))
    else:
        raise ValueError(f"unsupported filter mode: {variant.mode}")

    result["long_signal"] = original_long & long_allowed.fillna(False)
    result["short_signal"] = original_short & short_allowed.fillna(False)
    audit = {
        "raw_long_signal_bars": int(original_long.sum()),
        "raw_short_signal_bars": int(original_short.sum()),
        "blocked_long_signal_bars": int((original_long & ~long_allowed.fillna(False)).sum()),
        "blocked_short_signal_bars": int((original_short & ~short_allowed.fillna(False)).sum()),
        "remaining_long_signal_bars": int(result["long_signal"].sum()),
        "remaining_short_signal_bars": int(result["short_signal"].sum()),
    }
    return result, audit


def annotate_trades(run: base.RunResult, entry_rsi6: pd.Series) -> pd.DataFrame:
    trades = run.trades.copy()
    if trades.empty:
        trades["entry_h4_rsi6"] = pd.Series(dtype="float64")
        return trades
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["entry_h4_rsi6"] = entry_rsi6.reindex(pd.DatetimeIndex(entry_ts)).to_numpy()
    return trades


def comparison_row(run: base.RunResult, baseline: base.RunResult) -> dict[str, Any]:
    final_equity = 1.0 + float(run.metrics["return_pct"]) / 100.0
    base_final_equity = 1.0 + float(baseline.metrics["return_pct"]) / 100.0
    return {
        "variant": run.name,
        "final_equity_retained_pct": round(final_equity / base_final_equity * 100.0, 2),
        "return_delta_pp": round(
            float(run.metrics["return_pct"]) - float(baseline.metrics["return_pct"]), 2
        ),
        "max_drawdown_delta_pp": round(
            float(run.metrics["max_drawdown_pct"])
            - float(baseline.metrics["max_drawdown_pct"]),
            2,
        ),
        "sharpe_delta": round(float(run.metrics["sharpe"]) - float(baseline.metrics["sharpe"]), 2),
        "trade_delta": int(run.metrics["trades"] - baseline.metrics["trades"]),
        "slice_return_delta_pp": {
            run_slice["window"]: round(
                float(run_slice["return_pct"]) - float(base_slice["return_pct"]), 2
            )
            for run_slice, base_slice in zip(run.slices, baseline.slices, strict=True)
        },
    }


def base_trade_extreme_audit(
    baseline: base.RunResult, entry_rsi6: pd.Series
) -> dict[str, Any]:
    trades = annotate_trades(baseline, entry_rsi6)
    rows: dict[str, Any] = {}
    for lower, upper in ((10.0, 90.0), (20.0, 80.0), (30.0, 70.0)):
        extreme = trades["entry_h4_rsi6"].le(lower) | trades["entry_h4_rsi6"].ge(upper)
        selected = trades.loc[extreme]
        rows[f"{int(lower)}_{int(upper)}"] = {
            "base_trades_in_extreme": int(len(selected)),
            "long": int(selected["direction"].eq(1).sum()),
            "short": int(selected["direction"].eq(-1).sum()),
            "wins": int(selected["trade_return"].gt(0.0).sum()),
            "mean_trade_return_pct": round(float(selected["trade_return"].mean() * 100.0), 4)
            if len(selected)
            else None,
            "compound_trade_return_pct": round(
                float(((1.0 + selected["trade_return"]).prod() - 1.0) * 100.0), 4
            )
            if len(selected)
            else None,
        }
    return rows


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = load_data(warehouse)
    gate = quality_gate(quality)
    config = base.V35Config()
    features = base.build_features(frame, config)
    entry_rsi6 = entry_time_h4_rsi6(frame)
    no_floor = base.ProfitFloorConfig(enabled=False)

    runs: list[base.RunResult] = []
    signal_audits: dict[str, Any] = {}
    trade_frames: list[pd.DataFrame] = []
    for variant in VARIANTS:
        variant_features, signal_audit = filtered_features(
            features, entry_rsi6, config, variant
        )
        run = base.run_backtest(
            variant.name,
            frame,
            funding,
            variant_features,
            config,
            no_floor,
        )
        runs.append(run)
        signal_audits[variant.name] = signal_audit
        trades = annotate_trades(run, entry_rsi6)
        trades.insert(0, "variant", variant.name)
        trade_frames.append(trades)

    baseline = runs[0]
    canonical = base.run_backtest(
        "canonical_parity",
        frame,
        funding,
        features,
        config,
        no_floor,
    )
    parity_max_equity_diff = float(
        (baseline.equity_curve - canonical.equity_curve).abs().max()
    )
    if parity_max_equity_diff > 1e-12:
        raise ValueError(
            f"baseline parity failed: max equity diff={parity_max_equity_diff}"
        )

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "strategy_id": "HYPE-EMA-TB-V35",
        "audit_id": "4h RSI6 entry extreme filter diagnostic",
        "run_date": "2026-07-17",
        "status": "diagnostic_only_not_registered",
        "data_quality": quality,
        "gates": {
            "data_quality": gate,
            "baseline_vs_canonical_max_equity_diff": parity_max_equity_diff,
        },
        "assumptions": {
            "market": "Binance USD-M perpetual HYPE/USDT:USDT",
            "timeframe": "15m execution; 4h RSI6 filter",
            "v35_execution": (
                "K0 close signal, skip K1, K2 open entry; entry ATR from closed K1; "
                "5ATR TP / 7ATR SL stop-first; ADX22 delayed3; 384-bar timeout"
            ),
            "cost": "0.00085 per fill plus Binance funding",
            "rsi": (
                "Wilder RSI(6): gains/losses ewm(alpha=1/6, adjust=False, "
                "min_periods=6) on resampled 4h close"
            ),
            "alignment": (
                "15m OHLCV resample(4h, label=left, closed=left); RSI shift(1), "
                "then ffill to 15m. Filter reads the latest fully closed 4h RSI at K2 open."
            ),
            "primary_interpretation": (
                "symmetric_20_80 blocks every V35 entry when RSI6 <=20 or >=80, "
                "regardless of trade direction"
            ),
            "sensitivity": (
                "symmetric 10/90 tests a narrower extreme definition; symmetric 30/70 "
                "tests a wider extreme band; directional variants only block "
                "long-overbought and short-oversold entries"
            ),
        },
        "base_config": asdict(config),
        "filter_variants": [asdict(variant) for variant in VARIANTS],
        "signal_audits": signal_audits,
        "base_trade_extreme_audit": base_trade_extreme_audit(
            baseline, entry_rsi6
        ),
        "runs": [
            {
                "name": run.name,
                "metrics": run.metrics,
                "slices": run.slices,
                "open_position": run.open_position,
            }
            for run in runs
        ],
        "comparison_to_base": [
            comparison_row(run, baseline) for run in runs[1:]
        ],
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    pd.concat(trade_frames, ignore_index=True).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [run.equity_curve.rename(run.name) for run in runs], axis=1
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"quality_gate={gate['passed']}"
    )
    print(f"baseline parity max equity diff: {parity_max_equity_diff:.2e}")
    print(
        f"{'variant':>22}  {'return%':>10}  {'maxDD%':>8}  {'sharpe':>6}  "
        f"{'trades':>6}  {'win%':>7}  {'retained%':>10}"
    )
    for run in runs:
        retained = (
            100.0
            if run is baseline
            else comparison_row(run, baseline)["final_equity_retained_pct"]
        )
        metrics = run.metrics
        print(
            f"{run.name:>22}  {metrics['return_pct']:>10.2f}  "
            f"{metrics['max_drawdown_pct']:>8.2f}  {metrics['sharpe']:>6.2f}  "
            f"{metrics['trades']:>6}  {metrics['win_rate_pct']:>7.2f}  "
            f"{retained:>10.2f}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
