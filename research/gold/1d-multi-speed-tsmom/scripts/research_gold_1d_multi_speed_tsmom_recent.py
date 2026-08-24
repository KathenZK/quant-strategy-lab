#!/usr/bin/env python3
"""Run the fixed GOLD TSMOM rules on the post-2021 Yahoo recent extension."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/gold/1d-multi-speed-tsmom"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
RAW_ROOT = (
    ROOT
    / "data/raw/ohlcv/exchange=comex/market_type=futures/timeframe=1d"
    / "source=yahoo_chart_snapshot"
)
SYMBOL_FILE = "symbol=gc_f.parquet"
EVALUATION_START = pd.Timestamp("2021-12-01", tz="UTC")


def load_core():
    path = Path(__file__).with_name("research_gold_1d_multi_speed_tsmom.py")
    spec = importlib.util.spec_from_file_location("gold_tsmom_core", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load TSMOM core: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CORE = load_core()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--allow-untrusted", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def load_raw(*, allow_untrusted: bool) -> tuple[pd.DataFrame, dict[str, Any]]:
    files = sorted(RAW_ROOT.glob(f"date=*/{SYMBOL_FILE}"))
    if not files:
        raise FileNotFoundError("Yahoo GC=F raw partitions are absent; run the recent fetch first")
    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.sort_values("ts").reset_index(drop=True)
    price_columns = ["open", "high", "low", "close"]
    invalid = (
        frame[price_columns].isna().any(axis=1)
        | frame[price_columns].le(0).any(axis=1)
        | frame["high"].lt(frame[["open", "close", "low"]].max(axis=1))
        | frame["low"].gt(frame[["open", "close", "high"]].min(axis=1))
    )
    blockers = int(invalid.sum()) + int(frame["ts"].duplicated().sum())
    if blockers:
        raise RuntimeError(f"Yahoo recent raw mechanical blockers: {blockers}")
    if not allow_untrusted:
        raise RuntimeError("Yahoo GC=F is raw_unaccepted; pass --allow-untrusted explicitly")
    return frame, {
        "rows": len(frame),
        "first_ts": frame["ts"].iloc[0].isoformat(),
        "last_ts": frame["ts"].iloc[-1].isoformat(),
        "invalid_ohlc_rows": int(invalid.sum()),
        "duplicate_ts": int(frame["ts"].duplicated().sum()),
        "quality_status": "raw_unaccepted",
        "accepted_for_strategy_evidence": False,
    }


def normalize_extension(path: pd.DataFrame) -> pd.DataFrame:
    result = path.loc[path["ts"].ge(EVALUATION_START)].copy().reset_index(drop=True)
    if result.empty:
        raise RuntimeError("no observations in recent extension")
    for strategy in CORE.STRATEGIES:
        gross = result[f"gross_return_{strategy}"]
        result[f"gross_equity_{strategy}"] = (1.0 + gross).cumprod()
        for cost_bps in CORE.COST_BPS:
            slug = CORE.cost_slug(cost_bps)
            net = result[f"net_return_{strategy}_{slug}"]
            result[f"net_equity_{strategy}_{slug}"] = (1.0 + net).cumprod()
    result["buyhold_return"] = result["close"].pct_change(fill_method=None).fillna(0.0)
    result["buyhold_equity_0bps"] = (1.0 + result["buyhold_return"]).cumprod()
    result["buyhold_net_return_2bps"] = result["buyhold_return"]
    result.loc[result.index[0], "buyhold_net_return_2bps"] -= 0.0002
    result["buyhold_equity_2bps"] = (
        1.0 + result["buyhold_net_return_2bps"]
    ).cumprod()
    return result


def buyhold_metrics(path: pd.DataFrame, cost_bps: float) -> dict[str, Any]:
    if cost_bps == 0:
        returns = path["buyhold_return"]
    else:
        returns = path["buyhold_net_return_2bps"]
    equity = (1.0 + returns).cumprod()
    start, end = pd.Timestamp(path["ts"].iloc[0]), pd.Timestamp(path["ts"].iloc[-1])
    years = (end - start).total_seconds() / (365.25 * 86400)
    annual_return = float(returns.mean() * CORE.ANNUALIZER)
    annual_vol = float(returns.std(ddof=1) * math.sqrt(CORE.ANNUALIZER))
    downside = np.minimum(returns.to_numpy(), 0.0)
    downside_dev = float(np.sqrt(np.mean(np.square(downside))) * math.sqrt(CORE.ANNUALIZER))
    drawdown = equity / equity.cummax() - 1.0
    total = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    month_key = path["ts"].dt.tz_localize(None).dt.to_period("M")
    months = returns.groupby(month_key).apply(CORE.compounded_return)
    return {
        "strategy": "buy_and_hold",
        "label": "Buy&Hold",
        "cost_bps_one_way": cost_bps,
        "start_ts": start.isoformat(),
        "end_ts": end.isoformat(),
        "observations": len(path),
        "months": len(months),
        "years": years,
        "cagr": cagr,
        "annualized_arithmetic_return": annual_return,
        "annualized_volatility": annual_vol,
        "sharpe": annual_return / annual_vol,
        "sortino": annual_return / downside_dev,
        "max_drawdown": float(drawdown.min()),
        "calmar": cagr / abs(float(drawdown.min())),
        "positive_month_ratio": float(months.gt(0).mean()),
        "positive_months": int(months.gt(0).sum()),
        "daily_win_rate": float(returns.gt(0).mean()),
        "annualized_turnover": 1.0 / years,
        "total_turnover": 1.0,
        "gross_total_return": float(path["buyhold_equity_0bps"].iloc[-1] - 1.0),
        "net_total_return": total,
        "cost_drag_total_return": float(path["buyhold_equity_0bps"].iloc[-1] - equity.iloc[-1]),
        "simple_cost_sum": cost_bps / 10_000.0,
        "average_abs_position": 1.0,
        "max_abs_position": 1.0,
    }


def report(run_date: str, metrics: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> str:
    primary = metrics.loc[metrics["cost_bps_one_way"].eq(2.0)]
    rows = []
    for row in primary.itertuples(index=False):
        rows.append(
            f"| `{row.label}` | {CORE.pct(row.cagr)} | {CORE.pct(row.annualized_arithmetic_return)} | "
            f"{CORE.pct(row.annualized_volatility)} | {CORE.number(row.sharpe)} | "
            f"{CORE.number(row.sortino)} | {CORE.pct(row.max_drawdown)} | "
            f"{CORE.number(row.calmar)} | {CORE.pct(row.daily_win_rate)} | "
            f"{CORE.pct(row.positive_month_ratio)} | {CORE.number(row.annualized_turnover, 2)} | "
            f"{CORE.pct(row.gross_total_return)} | {CORE.pct(row.net_total_return)} |"
        )
    by_label = primary.set_index("label")
    composite = by_label.loc["Composite"]
    buyhold = by_label.loc["Buy&Hold"]
    years = (end - start).total_seconds() / (365.25 * 86400)
    return "\n".join(
        [
            f"# 黄金多速度 TSMOM 2022–2026 近期扩展（{run_date}）",
            "",
            "- 状态：`explore / diagnostic-only / not promoted / not live-ready`",
            f"- 独立近期窗口：`{start.date()}` → `{end.date()}`，约 `{years:.2f}` 年",
            "- 数据：Yahoo Chart API `GC=F` raw quote OHLC；未使用 adjusted close",
            "- 预热：2020-01 起；2021-11 月末信号从下一交易日开始作用于扩展窗口",
            "- 成本：0 bps 对照 + 2 bps 单边目标仓位换手；Buy&Hold 仅首次建仓收费",
            "",
            "## 结论",
            "",
            f"Composite 含成本总收益 `{CORE.pct(composite.net_total_return)}`、CAGR "
            f"`{CORE.pct(composite.cagr)}`、Sharpe `{CORE.number(composite.sharpe)}`、"
            f"最大回撤 `{CORE.pct(composite.max_drawdown)}`。",
            f"同期 Buy&Hold 总收益 `{CORE.pct(buyhold.net_total_return)}`、CAGR "
            f"`{CORE.pct(buyhold.cagr)}`、Sharpe `{CORE.number(buyhold.sharpe)}`、"
            f"最大回撤 `{CORE.pct(buyhold.max_drawdown)}`。",
            "",
            "## 含 2 bps 成本结果",
            "",
            "| 分支 | CAGR | 年化收益 | 年化波动 | Sharpe | Sortino | 最大回撤 | Calmar | 日胜率 | 正收益月 | 年换手 | 毛收益 | 净收益 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *rows,
            "",
            "## 解释边界",
            "",
            "该段使用另一供应商的独立序列，不与 1985–2021 Stooq 路径硬拼。Yahoo 未披露连续合约换月映射，"
            "且 quote close 未获官方结算价逐日核验，因此仍为 `raw_unaccepted`。本结果用于观察近年形态，"
            "不能把两个供应商的分段收益直接连乘成一条正式全历史净值。",
            "",
            "## 证据与复现",
            "",
            f"- 数据审计：[../artifacts/gold-1d-ms-tsmom-recent-extension-{run_date}-data-audit.json](../artifacts/gold-1d-ms-tsmom-recent-extension-{run_date}-data-audit.json)",
            f"- 完整 0/2 bps 指标：[../artifacts/gold-1d-ms-tsmom-recent-extension-{run_date}-metrics.csv](../artifacts/gold-1d-ms-tsmom-recent-extension-{run_date}-metrics.csv)",
            f"- 日路径：[../artifacts/gold-1d-ms-tsmom-recent-extension-{run_date}-daily-paths.csv](../artifacts/gold-1d-ms-tsmom-recent-extension-{run_date}-daily-paths.csv)",
            f"- 交互图：[../artifacts/gold-1d-ms-tsmom-recent-extension-{run_date}-interactive.html](../artifacts/gold-1d-ms-tsmom-recent-extension-{run_date}-interactive.html)",
            "",
            "```bash",
            f".venv/bin/python research/gold/1d-multi-speed-tsmom/scripts/fetch_gold_gc_yahoo_recent.py --run-date {run_date}",
            f".venv/bin/python research/gold/1d-multi-speed-tsmom/scripts/research_gold_1d_multi_speed_tsmom_recent.py --run-date {run_date} --allow-untrusted",
            f".venv/bin/python research/gold/1d-multi-speed-tsmom/scripts/render_gold_1d_multi_speed_tsmom.py --run-date {run_date} --artifact-kind recent-extension",
            "```",
            "",
        ]
    )


def main() -> None:
    args = parse_args()
    raw, quality = load_raw(allow_untrusted=args.allow_untrusted)
    frame, month_end = CORE.build_features(raw)
    full_path, _ = CORE.expand_positions(frame, month_end)
    path = normalize_extension(full_path)
    metrics = pd.DataFrame(
        [
            CORE.performance_metrics(path, strategy=strategy, cost_bps=cost)
            for strategy in CORE.STRATEGIES
            for cost in CORE.COST_BPS
        ]
        + [buyhold_metrics(path, cost) for cost in CORE.COST_BPS]
    )
    yearly = CORE.period_returns(path, frequency="year")
    monthly = CORE.period_returns(path, frequency="month")
    slices = CORE.recent_slices(path)
    episodes = CORE.build_direction_episodes(path)
    stem = f"gold-1d-ms-tsmom-recent-extension-{args.run_date}"
    audit_path = ARTIFACT_DIR / f"{stem}-data-audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    config = {
        "family_name": CORE.FAMILY_NAME,
        "experiment": "post_2021_recent_extension",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "evaluation_start": EVALUATION_START.isoformat(),
        "signal_lookbacks_months": [1, 3, 12],
        "composite_weights": [1 / 3, 1 / 3, 1 / 3],
        "target_volatility": CORE.TARGET_VOL,
        "volatility_center_of_mass_days": CORE.VOL_COM,
        "execution_lag_sessions": 1,
        "cost_bps_one_way": list(CORE.COST_BPS),
        "data_quality_status": "raw_unaccepted",
        "provider_splice": False,
    }
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "run_date": args.run_date,
        "status": config["status"],
        "data_quality": {**audit, **quality},
        "config": config,
        "backtest_start_ts": pd.Timestamp(path["ts"].iloc[0]).isoformat(),
        "backtest_end_ts": pd.Timestamp(path["ts"].iloc[-1]).isoformat(),
        "backtest_observations": len(path),
        "metrics": metrics.to_dict(orient="records"),
    }
    CORE.write_json(ARTIFACT_DIR / f"{stem}-config.json", config, force=args.force)
    CORE.write_json(ARTIFACT_DIR / f"{stem}-summary.json", summary, force=args.force)
    CORE.write_csv(ARTIFACT_DIR / f"{stem}-metrics.csv", metrics, force=args.force)
    signal_columns = [column for column in month_end.columns if column != "ewma_variance"]
    signals = month_end.loc[month_end["ts"].ge(pd.Timestamp("2021-11-01", tz="UTC")), signal_columns]
    CORE.write_csv(ARTIFACT_DIR / f"{stem}-month-end-signals.csv", signals, force=args.force)
    path_columns = ["ts", "open", "high", "low", "close", "daily_return", "sigma_ann"]
    for strategy in CORE.STRATEGIES:
        path_columns += [
            f"position_{strategy}",
            f"turnover_{strategy}",
            f"gross_return_{strategy}",
            f"gross_equity_{strategy}",
            f"net_return_{strategy}_2bps",
            f"net_equity_{strategy}_2bps",
        ]
    path_columns += [
        "buyhold_return",
        "buyhold_equity_0bps",
        "buyhold_net_return_2bps",
        "buyhold_equity_2bps",
    ]
    CORE.write_csv(ARTIFACT_DIR / f"{stem}-daily-paths.csv", path[path_columns], force=args.force)
    CORE.write_csv(ARTIFACT_DIR / f"{stem}-yearly-returns.csv", yearly, force=args.force)
    CORE.write_csv(ARTIFACT_DIR / f"{stem}-monthly-returns.csv", monthly, force=args.force)
    CORE.write_csv(ARTIFACT_DIR / f"{stem}-recent-slices.csv", slices, force=args.force)
    CORE.write_csv(ARTIFACT_DIR / f"{stem}-episodes.csv", episodes, force=args.force)
    report_text = report(
        args.run_date,
        metrics,
        pd.Timestamp(path["ts"].iloc[0]),
        pd.Timestamp(path["ts"].iloc[-1]),
    )
    report_path = FAMILY_DIR / "diagnostics" / f"gold-1d-ms-tsmom-recent-{args.run_date}.md"
    CORE.write_text(report_path, report_text, force=args.force)
    print(
        metrics.loc[
            metrics["cost_bps_one_way"].eq(2.0),
            ["label", "cagr", "annualized_volatility", "sharpe", "max_drawdown", "net_total_return"],
        ].to_json(orient="records", force_ascii=False, indent=2)
    )
    print(f"report -> {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
