from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-dual-alpha-sleeve-ensemble"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CBCT_PATH = ROOT / "research/asset-portfolios/1d-btceth-cross-breadth-channel-trend/scripts/search_binance_1d_be_cbct_p0.py"
RCR_PATH = ROOT / "research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/search_binance_1d_be_rcr_p0.py"
WEIGHTS = (0.0, 0.25, 0.50, 0.75, 1.0)
CBCT_EXPECTED = (21.270651982678306, -37.19612846945293)
RCR_EXPECTED = (21.260522820421354, -69.6600350089438)


@dataclass
class SleeveReplay:
    terminal: float
    ordered_mdd_pct: float
    path: pd.DataFrame
    trades: list[dict[str, Any]]


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def ordered_mdd(path: pd.DataFrame) -> float:
    peak, worst = 1.0, 0.0
    for row in path.itertuples(index=False):
        peak = max(peak, float(row.favorable_equity))
        worst = min(worst, float(row.adverse_equity) / peak - 1.0)
        peak = max(peak, float(row.equity))
        worst = min(worst, float(row.equity) / peak - 1.0)
    return float(worst * 100.0)


def cbct_replay(
    cbct: Any,
    data: Any,
    daily: Any,
    hourly: Any,
    daily_frame: pd.DataFrame,
    *,
    slippage: float,
    delay_days: int = 0,
) -> SleeveReplay:
    config = cbct.Config(20, 10, 50, 5.0, 2, 7, 120)
    book = cbct.build_entry_book(daily_frame, daily, 20, 50, 2)
    channels = cbct.exit_channels(daily_frame, 10)
    result = cbct.simulate(
        data,
        daily,
        hourly,
        book,
        channels,
        config,
        slippage=slippage,
        delay_days=delay_days,
        retain=True,
        profit_protection=cbct.ProfitProtection(1.0, 0.35, 2),
    )
    path = pd.DataFrame(result.path)
    replay_mdd = ordered_mdd(path)
    if not math.isclose(replay_mdd, result.max_drawdown_pct, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"CBCT risk-path MDD drift: {replay_mdd} != {result.max_drawdown_pct}")
    return SleeveReplay(result.equity_multiple, replay_mdd, path, result.trades)


def rcr_scores(rcr: Any, daily: pd.DataFrame) -> dict[tuple[int, int, str], np.ndarray]:
    return {
        (40, 28, symbol): rcr.normalized_momentum(daily[f"{symbol}_close"], 40, 28)
        for symbol in rcr.ASSETS
    }


def rcr_risk_replay(
    rcr: Any,
    union: pd.DataFrame,
    daily: pd.DataFrame,
    states: np.ndarray,
    *,
    slippage: float,
) -> SleeveReplay:
    target_by_day = dict(zip(daily["ts"], states, strict=True))
    cash, quantity, side, asset, entry_price = 1.0, 0.0, 0, "", 0.0
    entry_equity = 0.0
    entry_ts: pd.Timestamp | None = None
    peak, worst = 1.0, 0.0
    path, trades = [], []
    for row in union.itertuples(index=False):
        timestamp = pd.Timestamp(row.ts)
        if timestamp.hour == 0:
            target = 0 if timestamp == rcr.DEVELOPMENT_END else int(target_by_day[timestamp])
            current = side * (1 if asset == "BTCUSDT" else 2) if side else 0
            if target != current:
                if side:
                    mark = float(getattr(row, f"{asset}_open"))
                    cash, exit_fill = rcr._close_position(cash, quantity, side, entry_price, mark, slippage)
                    trades.append(
                        {
                            "entry_ts": entry_ts,
                            "exit_ts": timestamp,
                            "asset": asset,
                            "side": side,
                            "entry_price": entry_price,
                            "exit_price": exit_fill,
                            "entry_equity": entry_equity,
                            "exit_equity": cash,
                            "trade_log_growth": math.log(cash / entry_equity),
                        }
                    )
                    quantity, side, asset = 0.0, 0, ""
                if target and timestamp < rcr.DEVELOPMENT_END:
                    asset = rcr.STATE_ASSET[target]
                    side = 1 if target > 0 else -1
                    entry_equity, entry_ts = cash, timestamp
                    cash, quantity, entry_price = rcr._open_position(
                        cash, side, float(getattr(row, f"{asset}_open")), slippage
                    )
        if timestamp == rcr.DEVELOPMENT_END:
            favorable = adverse = close_equity = cash
        elif side:
            favorable_mark = float(getattr(row, f"{asset}_{'high' if side > 0 else 'low'}"))
            adverse_mark = float(getattr(row, f"{asset}_{'low' if side > 0 else 'high'}"))
            favorable = cash + side * quantity * (favorable_mark - entry_price)
            adverse_before = cash + side * quantity * (adverse_mark - entry_price)
            cash -= side * quantity * float(getattr(row, f"{asset}_unit_funding"))
            adverse_after = cash + side * quantity * (adverse_mark - entry_price)
            adverse = min(adverse_before, adverse_after)
            close_equity = cash + side * quantity * (float(getattr(row, f"{asset}_close")) - entry_price)
        else:
            favorable = adverse = close_equity = cash
        peak = max(peak, favorable)
        worst = min(worst, adverse / peak - 1.0)
        peak = max(peak, close_equity)
        worst = min(worst, close_equity / peak - 1.0)
        path.append(
            {
                "ts": timestamp,
                "equity": float(close_equity),
                "favorable_equity": float(favorable),
                "adverse_equity": float(adverse),
            }
        )
        if timestamp == rcr.DEVELOPMENT_END:
            break
    return SleeveReplay(float(cash), float(worst * 100.0), pd.DataFrame(path), trades)


def rcr_replay(
    rcr: Any,
    union: pd.DataFrame,
    daily: pd.DataFrame,
    scores: dict[tuple[int, int, str], np.ndarray],
    *,
    slippage: float,
    delay_days: int = 0,
) -> SleeveReplay:
    config = rcr.Config(40, 40, 28, 0.0, 0.25, 3)
    states = rcr.signal_for_config(config, scores, extra_delay_days=delay_days)
    result = rcr_risk_replay(rcr, union, daily, states, slippage=slippage)
    control = rcr.ordered_hourly_replay(union, daily, states, slippage=slippage, retain=False)
    if not math.isclose(result.terminal, control.equity_multiple, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"RCR terminal drift: {result.terminal} != {control.equity_multiple}")
    if not math.isclose(result.ordered_mdd_pct, control.max_drawdown_pct, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"RCR MDD drift: {result.ordered_mdd_pct} != {control.max_drawdown_pct}")
    return result


def combine_paths(cbct_path: pd.DataFrame, rcr_path: pd.DataFrame, cbct_weight: float) -> pd.DataFrame:
    if not pd.DatetimeIndex(cbct_path["ts"]).equals(pd.DatetimeIndex(rcr_path["ts"])):
        raise RuntimeError("component hourly timestamps differ")
    rcr_weight = 1.0 - cbct_weight
    output = pd.DataFrame({"ts": cbct_path["ts"]})
    output["cbct_equity"] = cbct_path["equity"].to_numpy(float)
    output["rcr_equity"] = rcr_path["equity"].to_numpy(float)
    for column in ("equity", "favorable_equity", "adverse_equity"):
        output[column] = cbct_weight * cbct_path[column].to_numpy(float) + rcr_weight * rcr_path[column].to_numpy(float)
    return output


def calendar_ratio(path: pd.DataFrame) -> float:
    equity = pd.Series(path["equity"].to_numpy(float), index=pd.DatetimeIndex(path["ts"]))
    values = []
    for year in range(2020, 2025):
        prior = equity.loc[equity.index < pd.Timestamp(f"{year}-01-01", tz="UTC")]
        current = equity.loc[(equity.index >= pd.Timestamp(f"{year}-01-01", tz="UTC")) & (equity.index < pd.Timestamp(f"{year + 1}-01-01", tz="UTC"))]
        if not prior.empty and not current.empty:
            values.append(current.iloc[-1] / prior.iloc[-1] - 1.0)
    return float(np.mean(np.asarray(values) > 0.0)) if values else 0.0


def rolling_ratio(path: pd.DataFrame) -> float:
    equity = pd.Series(path["equity"].to_numpy(float), index=pd.DatetimeIndex(path["ts"]))
    values = (equity / equity.shift(24 * 365) - 1.0).dropna()
    return float((values > 0.0).mean()) if not values.empty else 0.0


def trade_concentration(cbct_trades: list[dict[str, Any]], rcr_trades: list[dict[str, Any]], weight: float) -> float:
    contributions = [weight * max(0.0, float(item["trade_log_growth"])) for item in cbct_trades]
    contributions += [(1.0 - weight) * max(0.0, float(item["trade_log_growth"])) for item in rcr_trades]
    total = sum(contributions)
    return max(contributions, default=0.0) / total if total > 0 else 1.0


def combine_metrics(cbct: SleeveReplay, rcr: SleeveReplay, weight: float) -> tuple[dict[str, Any], pd.DataFrame]:
    path = combine_paths(cbct.path, rcr.path, weight)
    terminal = float(path["equity"].iloc[-1])
    expected = weight * cbct.terminal + (1.0 - weight) * rcr.terminal
    if not math.isclose(terminal, expected, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"combined terminal drift: {terminal} != {expected}")
    cbct_return = cbct.path["equity"].pct_change()
    rcr_return = rcr.path["equity"].pct_change()
    correlation = float(cbct_return.corr(rcr_return))
    cbct_dd = cbct.path["equity"] / cbct.path["equity"].cummax() - 1.0
    rcr_dd = rcr.path["equity"] / rcr.path["equity"].cummax() - 1.0
    overlap = float(((cbct_dd < 0.0) & (rcr_dd < 0.0)).mean())
    concentration = trade_concentration(cbct.trades, rcr.trades, weight)
    positive_sleeve = [weight * max(0.0, math.log(cbct.terminal)), (1.0 - weight) * max(0.0, math.log(rcr.terminal))]
    sleeve_share = max(positive_sleeve) / sum(positive_sleeve)
    return (
        {
            "cbct_weight": weight,
            "rcr_weight": 1.0 - weight,
            "equity_multiple": terminal,
            "ordered_mdd_pct": ordered_mdd(path),
            "complete_year_positive_ratio": calendar_ratio(path),
            "rolling_365d_positive_ratio": rolling_ratio(path),
            "hourly_close_return_correlation": correlation,
            "both_sleeves_in_drawdown_hour_ratio": overlap,
            "max_sleeve_positive_log_share": sleeve_share,
            "max_trade_weighted_positive_log_share": concentration,
            "cbct_trades": len(cbct.trades),
            "rcr_trades": len(rcr.trades),
        },
        path,
    )


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen P0 research for BIN-1D-BE-DASE.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        sample = pd.DataFrame(
            {
                "ts": pd.date_range("2020-01-01", periods=2, freq="1h", tz="UTC"),
                "equity": [1.0, 2.0],
                "favorable_equity": [1.0, 2.1],
                "adverse_equity": [1.0, 1.8],
            }
        )
        assert np.allclose(combine_paths(sample, sample, 0.25)["equity"], sample["equity"])
        print("self-test: PASS")
        return
    cbct = load_module("binance_1d_be_dase_cbct", CBCT_PATH)
    rcr = load_module("binance_1d_be_dase_rcr", RCR_PATH)
    data = cbct.load_data_helper()
    hourly_source, funding, quality = data.load_frozen_data()
    cbct_daily, cbct_hourly, daily_frame = cbct.prepare_markets(data, hourly_source, funding)
    rcr_daily = rcr.build_daily(hourly_source, funding)
    union = rcr.build_hourly_union(hourly_source, funding)
    scores = rcr_scores(rcr, rcr_daily)
    modes = {
        "base": (cbct.BASE_SLIPPAGE, 0),
        "stress": (cbct.STRESS_SLIPPAGE, 0),
        "delay": (cbct.BASE_SLIPPAGE, 1),
    }
    components: dict[str, tuple[SleeveReplay, SleeveReplay]] = {}
    for mode, (slippage, delay) in modes.items():
        components[mode] = (
            cbct_replay(
                cbct, data, cbct_daily, cbct_hourly, daily_frame, slippage=slippage, delay_days=delay
            ),
            rcr_replay(rcr, union, rcr_daily, scores, slippage=slippage, delay_days=delay),
        )
    if not math.isclose(components["base"][0].terminal, CBCT_EXPECTED[0], rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError("CBCT frozen terminal parity failed")
    if not math.isclose(components["base"][0].ordered_mdd_pct, CBCT_EXPECTED[1], rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError("CBCT frozen MDD parity failed")
    if not math.isclose(components["base"][1].terminal, RCR_EXPECTED[0], rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError("RCR frozen terminal parity failed")
    if not math.isclose(components["base"][1].ordered_mdd_pct, RCR_EXPECTED[1], rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError("RCR frozen MDD parity failed")
    rows, paths = [], {}
    for weight in WEIGHTS:
        base, path = combine_metrics(*components["base"], weight)
        stress, _ = combine_metrics(*components["stress"], weight)
        delay, _ = combine_metrics(*components["delay"], weight)
        base_log = math.log(base["equity_multiple"])
        stress_retention = math.log(stress["equity_multiple"]) / base_log
        delay_retention = math.log(delay["equity_multiple"]) / base_log
        is_ensemble = 0.0 < weight < 1.0
        hard_base = base["equity_multiple"] >= 20.0 and base["ordered_mdd_pct"] >= -20.0
        gates = {
            "stress": stress["equity_multiple"] >= 16.0 and stress["ordered_mdd_pct"] >= -22.0,
            "delay": delay["equity_multiple"] >= 8.0 and delay["ordered_mdd_pct"] >= -25.0 and delay_retention >= 0.70,
            "calendar": base["complete_year_positive_ratio"] >= 0.70,
            "rolling": base["rolling_365d_positive_ratio"] >= 0.70,
            "capacity": base["cbct_trades"] >= 10 and base["rcr_trades"] >= 10,
            "sleeve_concentration": base["max_sleeve_positive_log_share"] <= 0.75,
            "trade_concentration": base["max_trade_weighted_positive_log_share"] <= 0.30,
        }
        rows.append(
            {
                **base,
                "variant": "ensemble" if is_ensemble else "control",
                "hard_base_pass": hard_base,
                "stress_equity_multiple": stress["equity_multiple"],
                "stress_ordered_mdd_pct": stress["ordered_mdd_pct"],
                "stress_log_growth_retention": stress_retention,
                "delay_equity_multiple": delay["equity_multiple"],
                "delay_ordered_mdd_pct": delay["ordered_mdd_pct"],
                "delay_log_growth_retention": delay_retention,
                **{f"gate_{key}": value for key, value in gates.items()},
                "all_gates_pass": is_ensemble and hard_base and all(gates.values()),
            }
        )
        paths[weight] = path
    frame = pd.DataFrame(rows)
    ensemble = frame.loc[frame["variant"].eq("ensemble")]
    best_growth = ensemble.sort_values(["equity_multiple", "ordered_mdd_pct"], ascending=[False, False]).iloc[0].to_dict()
    best_risk = ensemble.sort_values(["ordered_mdd_pct", "equity_multiple"], ascending=[False, False]).iloc[0].to_dict()
    passing = ensemble.loc[ensemble["all_gates_pass"]].sort_values(
        ["ordered_mdd_pct", "stress_log_growth_retention", "equity_multiple", "cbct_weight"],
        ascending=[False, False, False, True],
    )
    selected = passing.iloc[0].to_dict() if not passing.empty else None
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-BTCETH-Dual-Alpha-Sleeve-Ensemble",
        "campaign": "P0 frozen development ensemble",
        "status": "development candidate; audit sealed" if selected else "HARD-GATE-FAILED / explore / not promoted / not live-ready",
        "evidence_role": "development only; audit/prospective not read",
        "data_quality": quality,
        "component_parity": {
            mode: {
                "cbct_equity": pair[0].terminal,
                "cbct_ordered_mdd_pct": pair[0].ordered_mdd_pct,
                "rcr_equity": pair[1].terminal,
                "rcr_ordered_mdd_pct": pair[1].ordered_mdd_pct,
            }
            for mode, pair in components.items()
        },
        "counts": {
            "controls": 2,
            "ensemble_weights": 3,
            "hard_base_pass": int(ensemble["hard_base_pass"].sum()),
            "all_gates_pass": int(ensemble["all_gates_pass"].sum()),
        },
        "best_growth": best_growth,
        "best_risk": best_risk,
        "unique_candidate": selected,
        "audit_revealed": False,
        "prospective_revealed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_be_dase_p0_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(json.dumps(clean(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    frame.to_csv(ARTIFACT_DIR / f"{stem}_weights.csv", index=False)
    frontier_rows = []
    for frontier, row in (("growth_frontier", best_growth), ("risk_frontier", best_risk)):
        weight = float(row["cbct_weight"])
        frontier_rows.extend({"frontier": frontier, **item} for item in paths[weight].to_dict("records"))
    pd.DataFrame(frontier_rows).to_csv(ARTIFACT_DIR / f"{stem}_paths.csv", index=False)
    trade_rows = []
    for sleeve, trades in (("CBCT", components["base"][0].trades), ("RCR", components["base"][1].trades)):
        for item in trades:
            trade_rows.append(
                {
                    "sleeve": sleeve,
                    "entry_ts": item["entry_ts"],
                    "exit_ts": item["exit_ts"],
                    "asset": item["asset"],
                    "side": item["side"],
                    "entry_price": item.get("entry_fill", item.get("entry_price")),
                    "exit_price": item.get("exit_fill", item.get("exit_price")),
                    "trade_log_growth": item["trade_log_growth"],
                    "exit_reason": item.get("exit_reason", "state_transition"),
                }
            )
    pd.DataFrame(trade_rows).to_csv(ARTIFACT_DIR / f"{stem}_component_trades.csv", index=False)
    print(json.dumps(clean(payload["counts"]), ensure_ascii=False))
    print(json.dumps(clean(best_growth), ensure_ascii=False))
    print(json.dumps(clean(best_risk), ensure_ascii=False))
    print(json.dumps(clean(selected), ensure_ascii=False))


if __name__ == "__main__":
    main()
