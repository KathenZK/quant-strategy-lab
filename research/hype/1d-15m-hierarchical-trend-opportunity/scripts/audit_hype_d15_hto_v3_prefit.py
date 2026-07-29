from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
import random
import tempfile
from typing import Any

import numpy as np
import pandas as pd

import hto_engine as engine
import hto_v2
import tune_hype_d15_hto_v2 as tune


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-15m-hierarchical-trend-opportunity"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
V3_PATH = ARTIFACT_DIR / "hype_d15_hto_v3_tune_2026-07-29.json"
ONE_MINUTE_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1m"
)
ONE_MINUTE_RAW_ROOT = (
    ROOT / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=1m"
)
FILE_NAME = "symbol=hype_usdt_usdt.parquet"
RUN_DATE = "2026-07-29"


def scenario_row(name: str, result: engine.BacktestResult) -> dict[str, Any]:
    return {"scenario": name, **result.metrics}


def slices(
    book: engine.FeatureBook, config: engine.Config
) -> list[dict[str, Any]]:
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
    }
    output: list[dict[str, Any]] = []
    for label, width in windows.items():
        start = max(book.source_start, book.terminal_ts - width)
        result = engine.run_backtest(book, config, start_ts=start)
        output.append({"slice": label, **result.metrics})
    return output


def cpcv_proxy(
    book: engine.FeatureBook, config: engine.Config
) -> list[dict[str, Any]]:
    start = book.source_start + pd.Timedelta(days=120)
    output: list[dict[str, Any]] = []
    while start + pd.Timedelta(days=30) <= book.terminal_ts:
        end = start + pd.Timedelta(days=30)
        result = engine.run_backtest(book, config, start_ts=start, end_ts=end)
        output.append({"fold_start": start.isoformat(), "fold_end": end.isoformat(), **result.metrics})
        start = end
    return output


def bootstrap_trades(
    returns: np.ndarray, *, leverage: float, seed: int = 2026072903, runs: int = 10_000
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    if not len(returns):
        return {"runs": 0}
    sampled = rng.choice(returns, size=(runs, len(returns)), replace=True)
    equity = np.cumprod(1 + sampled, axis=1)
    peaks = np.maximum.accumulate(np.c_[np.ones(runs), equity], axis=1)[:, 1:]
    drawdown = 1 - equity / peaks
    ending = equity[:, -1]
    win_rate = (sampled > 0).mean(axis=1)
    return {
        "runs": runs,
        "trade_count_per_run": int(len(returns)),
        "leverage": leverage,
        "ending_equity": {
            "p05": float(np.quantile(ending, 0.05)),
            "p50": float(np.quantile(ending, 0.50)),
            "p95": float(np.quantile(ending, 0.95)),
        },
        "max_drawdown": {
            "p05": float(np.quantile(drawdown.max(axis=1), 0.05)),
            "p50": float(np.quantile(drawdown.max(axis=1), 0.50)),
            "p95": float(np.quantile(drawdown.max(axis=1), 0.95)),
        },
        "win_rate": {
            "p05": float(np.quantile(win_rate, 0.05)),
            "p50": float(np.quantile(win_rate, 0.50)),
            "p95": float(np.quantile(win_rate, 0.95)),
        },
        "loss_probability": float((ending < 1).mean()),
    }


def neighbor(
    values: tuple[Any, ...], current: Any, rng: random.Random
) -> Any:
    index = values.index(current)
    choices = [index]
    if index:
        choices.append(index - 1)
    if index + 1 < len(values):
        choices.append(index + 1)
    return values[rng.choice(choices)]


def local_configs(
    base: hto_v2.CleanConfig, *, count: int = 1_000
) -> list[hto_v2.CleanConfig]:
    rng = random.Random(2026072904)
    output: list[hto_v2.CleanConfig] = []
    seen: set[tuple[Any, ...]] = set()
    attempts = 0
    while len(output) < count and attempts < count * 100:
        attempts += 1
        daily_fast = neighbor(engine.DAILY_EMA_SPANS[:-1], base.daily_fast, rng)
        daily_slow_values = tuple(
            value for value in engine.DAILY_EMA_SPANS if value > daily_fast
        )
        daily_slow = (
            base.daily_slow
            if base.daily_slow in daily_slow_values
            else daily_slow_values[0]
        )
        daily_slow = neighbor(daily_slow_values, daily_slow, rng)
        micro_fast = neighbor(engine.MICRO_EMA_SPANS[:-1], base.micro_fast, rng)
        micro_slow_values = tuple(
            value for value in engine.MICRO_EMA_SPANS if value > micro_fast
        )
        micro_slow = (
            base.micro_slow
            if base.micro_slow in micro_slow_values
            else micro_slow_values[0]
        )
        micro_slow = neighbor(micro_slow_values, micro_slow, rng)
        config = hto_v2.CleanConfig(
            direction=base.direction,
            daily_fast=daily_fast,
            daily_slow=daily_slow,
            daily_mom_window=neighbor(
                engine.DAILY_MOM_WINDOWS, base.daily_mom_window, rng
            ),
            daily_dmi_window=neighbor(
                engine.DAILY_ADX_WINDOWS, base.daily_dmi_window, rng
            ),
            daily_channel_window=neighbor(
                engine.DAILY_CHANNEL_WINDOWS, base.daily_channel_window, rng
            ),
            micro_fast=micro_fast,
            micro_slow=micro_slow,
            entry_window=neighbor(engine.MICRO_WINDOWS, base.entry_window, rng),
            exit_window=neighbor(engine.MICRO_WINDOWS, base.exit_window, rng),
            atr_window=neighbor(engine.MICRO_ATR_WINDOWS, base.atr_window, rng),
            micro_adx_min=neighbor(
                tune.MICRO_ADX_VALUES, base.micro_adx_min, rng
            ),
            rvol_min=neighbor(tune.RVOL_VALUES, base.rvol_min, rng),
            breakout_atr=neighbor(
                tune.BREAKOUT_VALUES, base.breakout_atr, rng
            ),
            sl_atr=neighbor(tune.SL_VALUES, base.sl_atr, rng),
            tp_atr=neighbor(tune.TP_VALUES, base.tp_atr, rng),
            trail_activation_atr=neighbor(
                tune.TRAIL_ACTIVATION_VALUES, base.trail_activation_atr, rng
            ),
            trail_atr=neighbor(tune.TRAIL_VALUES, base.trail_atr, rng),
            breakeven_trigger_atr=neighbor(
                tune.BREAKEVEN_VALUES, base.breakeven_trigger_atr, rng
            ),
            cooldown_bars=neighbor(
                tune.COOLDOWN_VALUES, base.cooldown_bars, rng
            ),
            leverage=neighbor(tune.LEVERAGE_VALUES, base.leverage, rng),
        )
        if config.key not in seen:
            seen.add(config.key)
            output.append(config)
    return output


def local_audit(
    book: engine.FeatureBook, configs: list[hto_v2.CleanConfig]
) -> pd.DataFrame:
    validation_start = book.terminal_ts - pd.Timedelta(days=60)
    rows: list[dict[str, Any]] = []
    for clean in configs:
        config = hto_v2.to_engine(clean)
        full = engine.run_backtest(book, config).metrics
        validation = engine.run_backtest(
            book, config, start_ts=validation_start
        ).metrics
        rows.append(
            {
                **asdict(clean),
                "prefit_annual_factor": full["annual_factor"],
                "prefit_max_drawdown": full["max_drawdown"],
                "prefit_win_rate": full["win_rate"],
                "prefit_trades": full["trades"],
                "validation_annual_factor": validation["annual_factor"],
                "validation_max_drawdown": validation["max_drawdown"],
                "validation_win_rate": validation["win_rate"],
                "validation_trades": validation["trades"],
            }
        )
    return pd.DataFrame(rows)


def load_one_minute(
    *, terminal: pd.Timestamp
) -> tuple[pd.DataFrame, dict[str, Any]]:
    paths = sorted(ONE_MINUTE_ROOT.glob(f"date=*/{FILE_NAME}"))
    raw_paths = sorted(ONE_MINUTE_RAW_ROOT.glob(f"date=*/{FILE_NAME}"))
    if not paths or not raw_paths:
        raise RuntimeError("standard 1m raw/normalized data is missing")
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    raw = pd.concat([pd.read_parquet(path) for path in raw_paths], ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    raw["ts"] = pd.to_datetime(raw["ts"], utc=True)
    frame = frame.loc[frame["ts"] < terminal].sort_values("ts").drop_duplicates("ts", keep="last")
    raw = raw.loc[raw["ts"] < terminal].sort_values("ts").drop_duplicates("ts", keep="last")
    expected = pd.date_range(frame["ts"].iloc[0], frame["ts"].iloc[-1], freq="1min")
    missing = expected.difference(pd.DatetimeIndex(frame["ts"]))
    mismatch = {}
    for column in ["open", "high", "low", "close", "volume", "quote_volume", "trade_count"]:
        mismatch[column] = int(
            (~np.isclose(
                frame[column].to_numpy("float64"),
                raw[column].to_numpy("float64"),
                rtol=0.0,
                atol=0.0 if column == "trade_count" else 1e-12,
            )).sum()
        )
    nulls = int(
        frame[
            ["ts", "open", "high", "low", "close", "volume", "quote_volume", "trade_count"]
        ].isna().sum().sum()
    )
    blockers = len(missing) + sum(mismatch.values()) + nulls
    quality = {
        "rows": int(len(frame)),
        "first_ts": frame["ts"].iloc[0].isoformat(),
        "last_ts": frame["ts"].iloc[-1].isoformat(),
        "missing": int(len(missing)),
        "critical_nulls": nulls,
        "raw_normalized_mismatch": mismatch,
        "blocker_count": int(blockers),
    }
    if blockers:
        raise RuntimeError(f"1m phase source blockers: {quality}")
    return frame.reset_index(drop=True), quality


def aggregate_phase(frame: pd.DataFrame, offset_minutes: int) -> pd.DataFrame:
    bucket = (
        frame["ts"] - pd.Timedelta(minutes=offset_minutes)
    ).dt.floor("15min") + pd.Timedelta(minutes=offset_minutes)
    source = frame.assign(bucket=bucket)
    grouped = source.groupby("bucket", sort=True).agg(
        rows=("close", "size"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        quote_volume=("quote_volume", "sum"),
        trade_count=("trade_count", "sum"),
    )
    grouped = grouped.loc[grouped["rows"] == 15].reset_index().rename(columns={"bucket": "ts"})
    grouped["exchange"] = "binance"
    grouped["symbol"] = "HYPE/USDT:USDT"
    grouped["market_type"] = "perp"
    grouped["timeframe"] = "15m"
    grouped["base_asset"] = "HYPE"
    grouped["quote_asset"] = "USDT"
    grouped["vwap"] = grouped["quote_volume"] / grouped["volume"]
    grouped["is_closed"] = True
    grouped["source"] = f"binance_1m_real_phase_{offset_minutes}"
    return grouped[
        [
            "ts", "exchange", "symbol", "market_type", "timeframe", "base_asset",
            "quote_asset", "open", "high", "low", "close", "volume",
            "quote_volume", "trade_count", "vwap", "is_closed", "source",
        ]
    ]


def copy_native_daily(
    native: engine.FeatureBook, target: engine.FeatureBook
) -> None:
    native_days = native.ts.floor("D")
    target_days = target.ts.floor("D")

    def mapped(values: np.ndarray) -> np.ndarray:
        first = pd.Series(values, index=native_days).groupby(level=0).first()
        return first.reindex(target_days).to_numpy()

    target.daily_ema = {key: mapped(value) for key, value in native.daily_ema.items()}
    target.daily_momentum = {
        key: mapped(value) for key, value in native.daily_momentum.items()
    }
    target.daily_adx = {key: mapped(value) for key, value in native.daily_adx.items()}
    target.daily_dmi_diff = {
        key: mapped(value) for key, value in native.daily_dmi_diff.items()
    }
    target.daily_breakout_state = {
        key: mapped(value) for key, value in native.daily_breakout_state.items()
    }
    target.daily_supertrend_state = {
        key: mapped(value) for key, value in native.daily_supertrend_state.items()
    }


def phase_audit(
    native_book: engine.FeatureBook, config: engine.Config
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    minute, quality = load_one_minute(terminal=native_book.terminal_ts)
    original_snapshot = engine.SNAPSHOT_PATH
    original_loader = engine.load_manifest
    rows: list[dict[str, Any]] = []
    try:
        for offset in (5, 10):
            phase = aggregate_phase(minute, offset)
            phase = phase.loc[phase["ts"] < native_book.terminal_ts].reset_index(drop=True)
            with tempfile.NamedTemporaryFile(suffix=".parquet") as handle:
                phase.to_parquet(handle.name, index=False)
                engine.SNAPSHOT_PATH = Path(handle.name)
                engine.load_manifest = lambda: {
                    "freeze_contract": {
                        "data_terminal_exclusive": native_book.terminal_ts.isoformat(),
                        "locked_oos_start_inclusive": native_book.terminal_ts.isoformat(),
                    },
                    "rows": {"prefit": len(phase), "all": len(phase)},
                }
                phase_book = engine.build_book(include_locked_oos=False)
                copy_native_daily(native_book, phase_book)
                result = engine.run_backtest(phase_book, config)
                rows.append(
                    {
                        "phase_minutes": offset,
                        "bars": len(phase),
                        **result.metrics,
                    }
                )
    finally:
        engine.SNAPSHOT_PATH = original_snapshot
        engine.load_manifest = original_loader
    return rows, quality


def render_report(summary: dict[str, Any]) -> str:
    base = summary["scenarios"][0]
    cpcv_summary = summary["cpcv_summary"]
    mc = summary["bootstrap"]
    phase = summary["phase"]
    return "\n".join(
        [
            "# HYPE-D15-HTO-V3 prefit 稳健性审计",
            "",
            "- 本报告只读取 locked OOS 之前的数据；未使用 OOS 排名或调参。",
            "- 成本基线：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、实际资金费。",
            "",
            "## 基线",
            "",
            (
                f"年化倍数 `{base['annual_factor']:.3f}x`，净收益 `{base['total_return']:.2%}`，"
                f"胜率 `{base['win_rate']:.2%}`，MDD `{base['max_drawdown']:.2%}`，"
                f"`{base['trades']}` 笔。年化与回撤均未通过用户硬门槛。"
            ),
            "",
            "## 稳健性",
            "",
            (
                f"非重叠 30 日窗口 `{cpcv_summary['folds']}` 组，正收益占比 "
                f"`{cpcv_summary['positive_fraction']:.2%}`，零交易窗口 "
                f"`{cpcv_summary['zero_trade_folds']}`。"
            ),
            (
                f"交易 bootstrap `{mc['runs']}` 次：亏损概率 `{mc['loss_probability']:.2%}`，"
                f"MDD 95 分位 `{mc['max_drawdown']['p95']:.2%}`。"
            ),
            (
                "真实 1m 重聚合相位："
                + "；".join(
                    f"+{row['phase_minutes']}m 收益 {row['total_return']:.2%} / MDD {row['max_drawdown']:.2%}"
                    for row in phase
                )
                + "。"
            ),
            "",
            "## 结论",
            "",
            "`HYPE-D15-HTO-V3` 在揭示 OOS 前已经失败：没有达到 `10x` 年化，且 prefit MDD 超过 `20%`。",
            "因此它只能作为 `registered / not promoted / not live-ready` 的冻结研究版本；",
            "后续一次性 OOS 只用于完成用户指定验证，不得用于救参数。",
            "",
            "## 证据",
            "",
            "- [机器摘要](../artifacts/hype_d15_hto_v3_prefit_audit_2026-07-29.json)",
            "- [场景 CSV](../artifacts/hype_d15_hto_v3_prefit_scenarios_2026-07-29.csv)",
            "- [CPCV CSV](../artifacts/hype_d15_hto_v3_prefit_cpcv_2026-07-29.csv)",
            "- [参数邻域 CSV](../artifacts/hype_d15_hto_v3_prefit_neighbors_2026-07-29.csv)",
            "",
        ]
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.loads(V3_PATH.read_text(encoding="utf-8"))
    if payload["locked_oos_accessed"]:
        raise RuntimeError("V3 unexpectedly accessed locked OOS")
    clean = hto_v2.from_dict(payload["clean_config"])
    config = hto_v2.to_engine(clean)
    book = engine.build_book(include_locked_oos=False)
    base = engine.run_backtest(book, config, detailed=True)
    scenarios = [
        scenario_row("base_4bps_k1", base),
        scenario_row(
            "stress_8bps",
            engine.run_backtest(book, config, slippage_per_fill=engine.STRESS_SLIPPAGE),
        ),
        scenario_row(
            "delay_k2",
            engine.run_backtest(book, config, entry_delay_bars=2),
        ),
        scenario_row(
            "delay_k3",
            engine.run_backtest(book, config, entry_delay_bars=3),
        ),
        scenario_row(
            "long_only",
            engine.run_backtest(book, engine.replace_config(config, direction=1)),
        ),
        scenario_row(
            "short_only",
            engine.run_backtest(book, engine.replace_config(config, direction=2)),
        ),
        scenario_row(
            "leverage_1x",
            engine.run_backtest(book, engine.replace_config(config, leverage=1.0)),
        ),
    ]
    original_fee = engine.BASE_FEE
    try:
        engine.BASE_FEE = 0.0
        zero_cost = engine.run_backtest(book, config, slippage_per_fill=0.0)
    finally:
        engine.BASE_FEE = original_fee
    scenarios.append(scenario_row("zero_fee_zero_slippage", zero_cost))

    recent_slices = slices(book, config)
    cpcv_rows = cpcv_proxy(book, config)
    cpcv_returns = np.asarray([row["total_return"] for row in cpcv_rows])
    cpcv_trades = np.asarray([row["trades"] for row in cpcv_rows])
    cpcv_summary = {
        "folds": len(cpcv_rows),
        "positive_fraction": float((cpcv_returns > 0).mean()),
        "median_return": float(np.median(cpcv_returns)),
        "worst_return": float(cpcv_returns.min()),
        "zero_trade_folds": int((cpcv_trades == 0).sum()),
        "median_trades": float(np.median(cpcv_trades)),
    }
    trade_returns = np.asarray(
        [trade["net_return"] for trade in base.trades], dtype="float64"
    )
    bootstrap = bootstrap_trades(trade_returns, leverage=config.leverage)
    neighbors = local_audit(book, local_configs(clean))
    neighbor_summary = {
        "rows": int(len(neighbors)),
        "positive_prefit_fraction": float((neighbors.prefit_annual_factor > 1).mean()),
        "target_prefit_fraction": float(
            (
                (neighbors.prefit_annual_factor >= 10)
                & (neighbors.prefit_win_rate >= 0.50)
                & (neighbors.prefit_max_drawdown < 0.20)
                & (neighbors.prefit_trades >= 30)
            ).mean()
        ),
        "positive_validation_fraction": float(
            (neighbors.validation_annual_factor > 1).mean()
        ),
        "median_prefit_annual_factor": float(neighbors.prefit_annual_factor.median()),
        "median_prefit_max_drawdown": float(neighbors.prefit_max_drawdown.median()),
    }
    phase_rows, phase_quality = phase_audit(book, config)
    summary = {
        "family": payload["family"],
        "version": payload["version"],
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "locked_oos_accessed": False,
        "scenarios": scenarios,
        "recent_slices": recent_slices,
        "cpcv": cpcv_rows,
        "cpcv_summary": cpcv_summary,
        "bootstrap": bootstrap,
        "parameter_neighbors": neighbor_summary,
        "phase_source_quality": phase_quality,
        "phase": phase_rows,
        "prefit_hard_target_pass": bool(
            base.metrics["annual_factor"] >= 10
            and base.metrics["win_rate"] >= 0.50
            and base.metrics["max_drawdown"] < 0.20
        ),
        "promotion_review": {
            "result": "FAIL",
            "reasons": [
                "prefit annual_factor < 10x",
                "prefit max_drawdown >= 20%",
                "runner restart/rejection/missing-bar parity not implemented",
            ],
        },
    }
    (ARTIFACT_DIR / f"hype_d15_hto_v3_prefit_audit_{RUN_DATE}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    pd.DataFrame(scenarios).to_csv(
        ARTIFACT_DIR / f"hype_d15_hto_v3_prefit_scenarios_{RUN_DATE}.csv",
        index=False,
    )
    pd.DataFrame(cpcv_rows).to_csv(
        ARTIFACT_DIR / f"hype_d15_hto_v3_prefit_cpcv_{RUN_DATE}.csv",
        index=False,
    )
    neighbors.to_csv(
        ARTIFACT_DIR / f"hype_d15_hto_v3_prefit_neighbors_{RUN_DATE}.csv",
        index=False,
    )
    pd.DataFrame(phase_rows).to_csv(
        ARTIFACT_DIR / f"hype_d15_hto_v3_prefit_phase_{RUN_DATE}.csv",
        index=False,
    )
    (DIAGNOSTIC_DIR / f"hype-d15-hto-v3-prefit-robustness-{RUN_DATE}.md").write_text(
        render_report(summary), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
