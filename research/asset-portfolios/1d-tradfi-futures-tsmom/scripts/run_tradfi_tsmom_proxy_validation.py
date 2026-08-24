#!/usr/bin/env python3
"""Run the frozen long-history ETF/FX proxy validation for TSMOM P0."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-tradfi-futures-tsmom"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CORE_PATH = Path(__file__).with_name("run_tradfi_futures_tsmom.py")
EWMAC_PATH = (
    ROOT
    / "research/asset-portfolios/1d-classic-ewmac-replication/scripts"
    / "run_classic_ewmac_replication.py"
)
SOURCE_RUN_DATE = "2026-08-10"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CORE = load_module("tf_tsmom_proxy_core", CORE_PATH)
EWMAC = load_module("tf_tsmom_proxy_source", EWMAC_PATH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def load_proxy_surface() -> tuple[
    dict[str, pd.DataFrame], dict[str, dict[str, str]], dict[str, dict[str, object]]
]:
    frames = {}
    universe = {}
    audit = {}
    for symbol, identity in EWMAC.CLASSIC_ASSETS.items():
        raw_path = EWMAC.YAHOO_RAW_DIR / f"{symbol}_{SOURCE_RUN_DATE}.json"
        if not raw_path.exists():
            raise FileNotFoundError(f"frozen proxy JSON missing: {raw_path}")
        content = raw_path.read_bytes()
        adjusted, quality = EWMAC.parse_yahoo(content, symbol, SOURCE_RUN_DATE)
        frame = adjusted.reset_index().rename(columns={"day": "ts"})
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        frames[symbol] = frame[["ts", "close"]]
        universe[symbol] = {
            "class": identity["class"],
            "exchange": "proxy",
            "name": identity["name"],
        }
        audit[symbol] = {
            **quality,
            "raw_sha256_rechecked": hashlib.sha256(content).hexdigest(),
            "class": identity["class"],
            "name": identity["name"],
        }
    return frames, universe, audit


def mechanical_start(monthly: dict[str, pd.DataFrame]) -> pd.Timestamp:
    first_valid = []
    for events in monthly.values():
        valid = events.dropna(
            subset=["forecast_1m", "forecast_3m", "forecast_12m", "sigma_ann"]
        )
        if valid.empty:
            raise RuntimeError("proxy lacks a full 12M signal history")
        first_valid.append(pd.Timestamp(valid["ts"].iloc[0]))
    warm = max(first_valid) + pd.DateOffset(months=3)
    next_month = warm.tz_localize(None).to_period("M").end_time + pd.Timedelta(days=1)
    return pd.Timestamp(next_month.normalize(), tz="UTC")


def render_report(run_date: str, metrics: pd.DataFrame, yearly: pd.DataFrame) -> str:
    rows = []
    for cost in (0.0, 2.0, 10.0):
        selected = metrics.loc[metrics["cost_bps_one_way"].eq(cost)]
        for row in selected.itertuples(index=False):
            rows.append(
                f"| `{row.label}` | `{cost:g}` | {CORE.pct(row.cagr)} | "
                f"{CORE.pct(row.annualized_volatility)} | {CORE.num(row.sharpe)} | "
                f"{CORE.pct(row.max_drawdown)} | {CORE.num(row.annualized_turnover)} | "
                f"{CORE.pct(row.net_total_return)} |"
            )
    primary = metrics.loc[metrics["cost_bps_one_way"].eq(2.0)].set_index("strategy")
    composite = primary.loc["composite"]
    twelve = primary.loc["tsmom_12m"]
    long_only = primary.loc["long_only"]
    selected_year = yearly.loc[
        yearly["cost_bps_one_way"].eq(2.0)
        & yearly["strategy"].isin(["tsmom_12m", "composite", "long_only"])
    ]
    pivot = selected_year.pivot(index="year", columns="strategy", values="net_return")
    year_rows = [
        f"| `{year}` | {CORE.pct(row.get('tsmom_12m'))} | "
        f"{CORE.pct(row.get('composite'))} | {CORE.pct(row.get('long_only'))} |"
        for year, row in pivot.iterrows()
    ]
    stem = f"tf-1d-fut-tsmom-proxy-validation-{run_date}"
    return "\n".join(
        [
            f"# TF-1D-FUT-TSMOM 长期代理验证（{run_date}）",
            "",
            "- 状态：`secondary diagnostic / not futures evidence / not promoted / not live-ready`",
            "- 数据：既有 30 个 Yahoo ETF/FX 调整价代理；固定资产池零删除",
            f"- 窗口：`{composite.start_ts}` → `{composite.end_ts}`",
            "- 规则：与主期货 P0 相同的月末 1M/3M/12M、四类各25%、两层10%波动目标",
            "",
            "## 结论",
            "",
            f"12M 低成本 CAGR `{CORE.pct(twelve.cagr)}`、Sharpe `{CORE.num(twelve.sharpe)}`、"
            f"MDD `{CORE.pct(twelve.max_drawdown)}`；Composite CAGR "
            f"`{CORE.pct(composite.cagr)}`、Sharpe `{CORE.num(composite.sharpe)}`。",
            f"Long-only RP CAGR `{CORE.pct(long_only.cagr)}`、Sharpe "
            f"`{CORE.num(long_only.sharpe)}`。",
            "",
            "## 三成本账本",
            "",
            "| 分支 | 单边成本bps | CAGR | 波动 | Sharpe | MDD | 年换手 | 净总收益 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *rows,
            "",
            "## 分年（2 bps）",
            "",
            "| 年 | 12M | Composite | Long-only RP |",
            "| --- | ---: | ---: | ---: |",
            *year_rows,
            "",
            "## 边界",
            "",
            "该结果使用股票/债券/商品 ETF 和货币基金代理，包含基金费用、分红与商品基金 roll 结构；"
            "它不是连续期货总收益。用途仅是检验固定信号能否跨越比 2022–2026 更长的公开历史。",
            "",
            "## 证据",
            "",
            f"- [数据审计](../artifacts/{stem}-data-audit.json)",
            f"- [指标](../artifacts/{stem}-metrics.csv)",
            f"- [日路径](../artifacts/{stem}-portfolio-paths.csv)",
            "",
        ]
    )


def main() -> None:
    args = parse_args()
    frames, proxy_universe, audit = load_proxy_surface()
    CORE.UNIVERSE = proxy_universe
    CORE.COSTS = (0.0, 2.0, 10.0)
    cutoff = CORE.last_complete_month(frames)
    daily = {}
    monthly = {}
    signals = []
    for symbol, frame in frames.items():
        daily[symbol], monthly[symbol] = CORE.market_features(frame, cutoff)
        signal = monthly[symbol].copy()
        signal["symbol"] = symbol
        signal["asset_class"] = proxy_universe[symbol]["class"]
        signals.append(signal)
    CORE.EVALUATION_START = mechanical_start(monthly)
    dates = pd.DatetimeIndex(
        sorted({value for frame in daily.values() for value in frame["ts"]})
    )
    returns = pd.DataFrame(index=dates)
    for symbol in proxy_universe:
        returns[symbol] = daily[symbol].set_index("ts")["return"].reindex(dates)
    paths = {}
    details = []
    for strategy in CORE.STRATEGIES:
        paths[strategy], detail = CORE.build_strategy_path(
            dates, returns, monthly, strategy
        )
        paths[strategy]["strategy"] = strategy
        details.append(detail)
    common_end = min(pd.Timestamp(path["ts"].iloc[-1]) for path in paths.values())
    paths = {key: value.loc[value["ts"].le(common_end)].copy() for key, value in paths.items()}
    detail = pd.concat(details, ignore_index=True)
    detail = detail.loc[pd.to_datetime(detail["ts"], utc=True).le(common_end)]
    metrics = pd.DataFrame(
        [
            CORE.metrics(path, strategy, cost)
            for strategy, path in paths.items()
            for cost in CORE.COSTS
        ]
    )
    yearly = CORE.period_table(paths, "year")
    monthly_returns = CORE.period_table(paths, "month")
    recent = CORE.recent_table(paths)
    market, class_year = CORE.contribution_tables(detail)
    portfolio_paths = pd.concat(paths.values(), ignore_index=True)
    signal_frame = pd.concat(signals, ignore_index=True)
    stem = f"tf-1d-fut-tsmom-proxy-validation-{args.run_date}"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    audit_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_family": "XA-1D-CLASSIC-EWMAC",
        "source_snapshot_date": SOURCE_RUN_DATE,
        "markets": len(proxy_universe),
        "evaluation_start": CORE.EVALUATION_START.isoformat(),
        "evaluation_end": common_end.isoformat(),
        "quality_status": "proxy_only_not_futures_evidence",
        "market_audits": audit,
    }
    config = {
        "family": "TradFi-1D-Multi-Asset-Futures-TSMOM",
        "observation": "long-history ETF/FX proxy validation",
        "status": "secondary diagnostic / not futures evidence / not promoted / not live-ready",
        "source_family": "XA-1D-CLASSIC-EWMAC",
        "source_snapshot_date": SOURCE_RUN_DATE,
        "universe": proxy_universe,
        "class_weight": CORE.CLASS_WEIGHT,
        "signal_lookbacks_months": [1, 3, 12],
        "target_volatility_asset": CORE.TARGET_VOL,
        "target_volatility_portfolio": CORE.PORTFOLIO_TARGET_VOL,
        "volatility_center_of_mass_days": CORE.VOL_COM,
        "portfolio_scalar_cap": CORE.PORTFOLIO_SCALAR_CAP,
        "gross_cap": CORE.GROSS_CAP,
        "cost_bps_one_way": list(CORE.COSTS),
        "evaluation_start": CORE.EVALUATION_START.isoformat(),
        "evaluation_end": common_end.isoformat(),
        "quality_status": "proxy_only_not_futures_evidence",
    }
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "run_date": args.run_date,
        "config": config,
        "metrics": metrics.to_dict(orient="records"),
        "limitations": [
            "ETF/FX adjusted-price proxies are not continuous futures total returns",
            "fund expenses, distributions, and commodity-fund roll structures differ from futures",
            "this observation cannot be spliced into the primary futures surface",
        ],
    }
    files = {
        "data-audit.json": json.dumps(audit_payload, ensure_ascii=False, indent=2) + "\n",
        "config.json": json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        "summary.json": json.dumps(
            summary, ensure_ascii=False, indent=2, allow_nan=False
        )
        + "\n",
        "metrics.csv": metrics.to_csv(index=False),
        "portfolio-paths.csv": portfolio_paths.to_csv(index=False),
        "yearly-returns.csv": yearly.to_csv(index=False),
        "monthly-returns.csv": monthly_returns.to_csv(index=False),
        "recent-slices.csv": recent.to_csv(index=False),
        "market-contributions.csv": market.to_csv(index=False),
        "class-year-contributions.csv": class_year.to_csv(index=False),
        "month-end-signals.csv": signal_frame.to_csv(index=False),
    }
    artifact_paths = []
    for suffix, content in files.items():
        path = ARTIFACT_DIR / f"{stem}-{suffix}"
        if path.exists() and not args.force and path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"artifact exists; pass --force: {path}")
        path.write_text(content, encoding="utf-8")
        artifact_paths.append(path)
    detail_path = ARTIFACT_DIR / f"{stem}-asset-daily.parquet"
    if detail_path.exists() and not args.force:
        existing = pd.read_parquet(detail_path)
        if len(existing) != len(detail):
            raise RuntimeError(f"artifact exists; pass --force: {detail_path}")
    else:
        detail.to_parquet(detail_path, index=False)
    artifact_paths.append(detail_path)
    checksum_path = ARTIFACT_DIR / f"{stem}-checksums.sha256"
    checksum_text = "\n".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(artifact_paths)
    ) + "\n"
    checksum_path.write_text(checksum_text, encoding="utf-8")
    report_path = FAMILY_DIR / "diagnostics" / f"{stem}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(args.run_date, metrics, yearly), encoding="utf-8")
    print(
        metrics.loc[
            metrics["cost_bps_one_way"].eq(2.0),
            ["label", "cagr", "annualized_volatility", "sharpe", "max_drawdown", "net_total_return"],
        ].to_json(orient="records", force_ascii=False, indent=2)
    )
    print(f"report -> {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
