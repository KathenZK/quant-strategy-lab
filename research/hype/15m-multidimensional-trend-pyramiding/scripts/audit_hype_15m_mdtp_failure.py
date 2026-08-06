from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse
from strategy_lab.data.settings import load_settings


ROOT = Path("research/hype/15m-multidimensional-trend-pyramiding")
ARTIFACT_DIR = ROOT / "artifacts"
V1_SCRIPT = ROOT / "scripts/research_hype_15m_mdtp.py"
RUN_DATE = "2026-08-02"
SYMBOLS = (
    "HYPE/USDT:USDT",
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "BNB/USDT:USDT",
    "TRX/USDT:USDT",
)
COST_SWEEP_BPS = (0, 1, 2, 4, 6, 8, 10, 12, 14)


def load_v1_module() -> Any:
    spec = importlib.util.spec_from_file_location("hype_15m_mdtp_v1", V1_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {V1_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def simulate(
    module: Any,
    *,
    name: str,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: dict[str, pd.DataFrame],
    state: pd.DataFrame,
    config: Any,
    fee: float,
    slippage: float,
    include_funding: bool,
    allow_adds: bool = True,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> Any:
    return module.simulate(
        name=name,
        frame=frame,
        funding=funding,
        state=state,
        features=features,
        config=config,
        variant=module.VARIANTS[2],
        fee_per_fill=fee,
        slippage_per_fill=slippage,
        include_funding=include_funding,
        allow_adds=allow_adds,
        active_start=start,
        active_end=end,
    )


def trend_persistence(
    frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> list[dict[str, Any]]:
    hourly = frame["close"].resample("1h").last().dropna()
    log_close = np.log(hourly)
    rows: list[dict[str, Any]] = []
    for horizon in (24, 72, 168):
        past = log_close - log_close.shift(horizon)
        future = log_close.shift(-horizon) - log_close
        valid = pd.DataFrame({"past": past, "future": future}).loc[start:end].dropna()
        directional = np.sign(valid["past"]) * valid["future"]
        rows.append(
            {
                "horizon_hours": horizon,
                "observations": int(len(valid)),
                "directional_future_mean_bps": round(
                    float(directional.mean() * 10000.0), 4
                ),
                "directional_hit_rate_pct": round(
                    float(directional.gt(0.0).mean() * 100.0), 4
                ),
                "return_correlation": round(
                    float(valid["past"].corr(valid["future"])), 6
                ),
            }
        )
    return rows


def score_diagnostic(
    features: dict[str, pd.DataFrame],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    native = features["h1_native"]
    score = native["price_volume_score_jump"]
    future = native["_close"].shift(-24) / native["_close"] - 1.0
    sample = pd.DataFrame({"score": score, "future": future}).loc[start:end].dropna()
    sample["directional"] = np.sign(sample["score"]) * sample["future"]
    sample["abs_score"] = sample["score"].abs()
    sample["quintile"] = pd.qcut(
        sample["abs_score"], 5, labels=False, duplicates="drop"
    )
    grouped = sample.groupby("quintile", observed=True)["directional"].mean()
    values = [float(value) for value in grouped.tolist()]
    return {
        "observations": int(len(sample)),
        "directional_return_by_abs_score_quintile_pct": [
            round(value * 100.0, 6) for value in values
        ],
        "monotone": bool(all(left <= right for left, right in zip(values, values[1:]))),
        "top_minus_bottom_pct": round((values[-1] - values[0]) * 100.0, 6)
        if len(values) >= 2
        else None,
    }


def action_summary(run: Any) -> dict[str, Any]:
    if run.actions.empty:
        return {"counts": {}, "turnover_by_action": {}, "actions_per_day": 0.0}
    actions = run.actions.copy()
    actions["turnover"] = (
        pd.to_numeric(actions["allocation_after"], errors="coerce")
        - pd.to_numeric(actions["allocation_before"], errors="coerce")
    ).abs()
    counts = actions["action"].value_counts().to_dict()
    turnover = actions.groupby("action", observed=True)["turnover"].sum().to_dict()
    days = max(
        (run.equity.index[-1] - run.equity.index[0]).total_seconds() / 86400.0, 1.0
    )
    return {
        "counts": {str(key): int(value) for key, value in counts.items()},
        "turnover_by_action": {
            str(key): round(float(value), 4) for key, value in turnover.items()
        },
        "actions_per_day": round(float(len(actions) / days), 4),
    }


def trade_group_summary(run: Any) -> list[dict[str, Any]]:
    if run.trades.empty:
        return []
    trades = run.trades.copy()
    trades["group"] = np.where(trades["add_count"].gt(0), "added", "never_added")
    rows: list[dict[str, Any]] = []
    for group, selected in trades.groupby("group", observed=True):
        rows.append(
            {
                "group": str(group),
                "trades": int(len(selected)),
                "win_rate_pct": round(
                    float(selected["trade_return"].gt(0.0).mean() * 100.0), 4
                ),
                "mean_trade_return_pct": round(
                    float(selected["trade_return"].mean() * 100.0), 4
                ),
                "median_trade_return_pct": round(
                    float(selected["trade_return"].median() * 100.0), 4
                ),
                "mean_mfe_pct": round(float(selected["mfe_pct"].mean() * 100.0), 4),
                "mean_mae_pct": round(float(selected["mae_pct"].mean() * 100.0), 4),
            }
        )
    return rows


def break_even_cost(cost_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(cost_rows, key=lambda row: row["combined_cost_bps_per_fill"])
    positive = [row for row in ordered if row["total_return_pct"] >= 0.0]
    negative = [row for row in ordered if row["total_return_pct"] < 0.0]
    return {
        "highest_non_negative_bps": positive[-1]["combined_cost_bps_per_fill"]
        if positive
        else None,
        "lowest_negative_bps": negative[0]["combined_cost_bps_per_fill"]
        if negative
        else None,
        "note": "Bracket only; no parameter selection is performed from this diagnostic sweep.",
    }


def normalized_slice_metrics(
    module: Any, run: Any, start: pd.Timestamp, end: pd.Timestamp
) -> dict[str, Any]:
    equity = run.equity.loc[(run.equity.index >= start) & (run.equity.index <= end)]
    if equity.empty:
        return module.empty_metrics()
    normalized = equity / float(equity.iloc[0])
    returns = run.returns.reindex(normalized.index)
    weights = run.weights.reindex(normalized.index)
    if run.trades.empty:
        trades = pd.DataFrame()
    else:
        entry_ts = pd.to_datetime(run.trades["entry_ts"], utc=True)
        trades = run.trades.loc[entry_ts.ge(start) & entry_ts.le(end)].copy()
    turnover = float(2.0 * trades["allocation"].sum()) if not trades.empty else 0.0
    return module.compute_metrics(
        normalized,
        returns,
        weights,
        trades,
        turnover,
        0.0,
        0.0,
        0.0,
        float(returns.loc[weights.gt(0.0)].sum()),
        float(returns.loc[weights.lt(0.0)].sum()),
    )


def main() -> None:
    module = load_v1_module()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    windows = module.FeatureWindows()
    config = module.StrategyConfig()

    loaded: dict[str, tuple[pd.DataFrame, pd.Series, dict[str, Any]]] = {}
    for symbol in SYMBOLS:
        loaded[symbol] = module.load_symbol_data(
            warehouse, symbol, require_raw_parity=True
        )

    common_start = max(
        frame.index.min() + pd.Timedelta(days=config.warmup_days)
        for frame, _, _ in loaded.values()
    )
    common_end = min(frame.index.max() for frame, _, _ in loaded.values())

    asset_rows: list[dict[str, Any]] = []
    prepared: dict[
        str, tuple[pd.DataFrame, pd.Series, dict[str, pd.DataFrame], pd.DataFrame]
    ] = {}
    for symbol, (frame, funding, quality) in loaded.items():
        features = module.build_feature_set(frame, windows)
        state = module.build_state(frame, features, config, module.VARIANTS[2])
        prepared[symbol] = (frame, funding, features, state)
        gross = simulate(
            module,
            name=f"{symbol}_common_gross",
            frame=frame,
            funding=funding,
            features=features,
            state=state,
            config=config,
            fee=0.0,
            slippage=0.0,
            include_funding=False,
            start=common_start,
            end=common_end,
        )
        net = simulate(
            module,
            name=f"{symbol}_common_net",
            frame=frame,
            funding=funding,
            features=features,
            state=state,
            config=config,
            fee=config.fee_per_fill,
            slippage=config.slippage_per_fill,
            include_funding=True,
            start=common_start,
            end=common_end,
        )
        no_add = simulate(
            module,
            name=f"{symbol}_common_no_add",
            frame=frame,
            funding=funding,
            features=features,
            state=state,
            config=config,
            fee=config.fee_per_fill,
            slippage=config.slippage_per_fill,
            include_funding=True,
            allow_adds=False,
            start=common_start,
            end=common_end,
        )
        asset_rows.append(
            {
                "symbol": symbol,
                "evidence_status": quality["evidence_status"],
                "gross": gross.metrics,
                "net": net.metrics,
                "no_add_net": no_add.metrics,
                "trend_persistence": trend_persistence(frame, common_start, common_end),
                "score_diagnostic": score_diagnostic(
                    features, common_start, common_end
                ),
            }
        )

    hype_frame, hype_funding, hype_features, hype_state = prepared["HYPE/USDT:USDT"]
    hype_gross = simulate(
        module,
        name="hype_full_gross",
        frame=hype_frame,
        funding=hype_funding,
        features=hype_features,
        state=hype_state,
        config=config,
        fee=0.0,
        slippage=0.0,
        include_funding=False,
    )
    hype_net = simulate(
        module,
        name="hype_full_net",
        frame=hype_frame,
        funding=hype_funding,
        features=hype_features,
        state=hype_state,
        config=config,
        fee=config.fee_per_fill,
        slippage=config.slippage_per_fill,
        include_funding=True,
    )
    hype_no_add = simulate(
        module,
        name="hype_full_no_add",
        frame=hype_frame,
        funding=hype_funding,
        features=hype_features,
        state=hype_state,
        config=config,
        fee=config.fee_per_fill,
        slippage=config.slippage_per_fill,
        include_funding=True,
        allow_adds=False,
    )
    cost_rows: list[dict[str, Any]] = []
    for cost_bps in COST_SWEEP_BPS:
        run = simulate(
            module,
            name=f"hype_cost_{cost_bps}bps",
            frame=hype_frame,
            funding=hype_funding,
            features=hype_features,
            state=hype_state,
            config=config,
            fee=cost_bps / 10000.0,
            slippage=0.0,
            include_funding=True,
        )
        cost_rows.append({"combined_cost_bps_per_fill": cost_bps, **run.metrics})

    v35 = module.run_v35_cost_ladder(hype_frame, hype_funding)["standard_net"]
    v35_matched = normalized_slice_metrics(
        module,
        v35,
        hype_net.equity.index[0],
        hype_net.equity.index[-1],
    )
    payload = {
        "research_family": module.FAMILY,
        "strategy_id": module.STRATEGY_ID,
        "run_date": RUN_DATE,
        "research_role": "revealed-history failure audit; not parameter selection and not prospective OOS",
        "data_quality": {symbol: quality for symbol, (_, _, quality) in loaded.items()},
        "common_window": {
            "start": common_start.isoformat(),
            "end": common_end.isoformat(),
        },
        "asset_comparison": asset_rows,
        "hype_full_window": {
            "gross": hype_gross.metrics,
            "net": hype_net.metrics,
            "no_add_net": hype_no_add.metrics,
            "v35_standard_net": v35.metrics,
            "v35_standard_net_matched_window": v35_matched,
            "cost_sweep": cost_rows,
            "break_even_cost_bracket": break_even_cost(cost_rows),
            "net_action_summary": action_summary(hype_net),
            "gross_added_trade_groups": trade_group_summary(hype_gross),
            "net_added_trade_groups": trade_group_summary(hype_net),
        },
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"hype_15m_mdtp_v1_failure_audit_{RUN_DATE}.json"
    asset_path = ARTIFACT_DIR / f"hype_15m_mdtp_v1_failure_audit_assets_{RUN_DATE}.csv"
    cost_path = ARTIFACT_DIR / f"hype_15m_mdtp_v1_failure_audit_costs_{RUN_DATE}.csv"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    flat_assets = []
    for row in asset_rows:
        flat_assets.append(
            {
                "symbol": row["symbol"],
                "evidence_status": row["evidence_status"],
                "gross_return_pct": row["gross"]["total_return_pct"],
                "gross_sharpe": row["gross"]["sharpe"],
                "gross_turnover_annualized": row["gross"]["turnover_annualized"],
                "net_return_pct": row["net"]["total_return_pct"],
                "net_sharpe": row["net"]["sharpe"],
                "net_max_drawdown_pct": row["net"]["max_drawdown_pct"],
                "net_trades": row["net"]["trades"],
                "no_add_net_return_pct": row["no_add_net"]["total_return_pct"],
                "no_add_net_sharpe": row["no_add_net"]["sharpe"],
                "score_monotone": row["score_diagnostic"]["monotone"],
                "score_top_minus_bottom_pct": row["score_diagnostic"][
                    "top_minus_bottom_pct"
                ],
            }
        )
    pd.DataFrame(flat_assets).to_csv(asset_path, index=False)
    pd.DataFrame(cost_rows).to_csv(cost_path, index=False)
    print(
        json.dumps(
            {"json": str(json_path), "assets": flat_assets, "costs": cost_rows},
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
