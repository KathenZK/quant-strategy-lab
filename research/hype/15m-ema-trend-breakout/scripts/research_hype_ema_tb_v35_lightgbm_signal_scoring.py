from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_ema_tb_v35_h4_rsi6_entry_filter as lake_loader  # noqa: E402
import research_hype_ema_tb_v35_profit_floor as base  # noqa: E402
from strategy_lab.data import DataLakeLayout, DuckDBWarehouse  # noqa: E402
from strategy_lab.data.settings import load_settings  # noqa: E402


ROOT = SCRIPT_DIR.parent
OUT_DIR = ROOT / "artifacts" / "v35-lightgbm-signal-scoring"
FACTOR_DATASET = (
    ROOT.parent / "15m-factor-ml" / "artifacts" / "hype_15m_factor_dataset.parquet"
)
FACTOR_MANIFEST = (
    ROOT.parent / "15m-factor-ml" / "artifacts" / "hype_15m_factor_dataset_manifest.json"
)

TRAIN_END = pd.Timestamp("2026-01-01T00:00:00Z")
CALIBRATION_END = pd.Timestamp("2026-03-01T00:00:00Z")
VALIDATION_END = pd.Timestamp("2026-04-17T00:00:00Z")
OOS_END = pd.Timestamp("2026-07-16T15:30:00Z")

NON_FACTOR_COLUMNS = {
    "ts",
    "exchange",
    "symbol",
    "market_type",
    "timeframe",
    "base_asset",
    "quote_asset",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "vwap",
    "is_closed",
    "source",
    "mark_open",
    "mark_high",
    "mark_low",
    "mark_price",
    "funding_ts",
    "funding_age_hours",
}

MODEL_SPECS = [
    {"name": "leaf7_reg", "num_leaves": 7, "min_child_samples": 120, "reg_lambda": 3.0, "feature_fraction": 0.75},
    {"name": "leaf15_reg", "num_leaves": 15, "min_child_samples": 120, "reg_lambda": 5.0, "feature_fraction": 0.75},
    {"name": "leaf15_dense", "num_leaves": 15, "min_child_samples": 60, "reg_lambda": 3.0, "feature_fraction": 0.90},
    {"name": "leaf31_reg", "num_leaves": 31, "min_child_samples": 150, "reg_lambda": 8.0, "feature_fraction": 0.70},
    {"name": "leaf31_dense", "num_leaves": 31, "min_child_samples": 80, "reg_lambda": 5.0, "feature_fraction": 0.85},
    {"name": "leaf63_reg", "num_leaves": 63, "min_child_samples": 180, "reg_lambda": 12.0, "feature_fraction": 0.65},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    config = base.V35Config()
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    frame, funding, data_quality = lake_loader.load_data(warehouse)
    features = base.build_features(frame, config)
    factor_frame, factor_names, factor_audit = load_factor_frame(frame)

    baseline = base.run_backtest(
        "v35_base",
        frame,
        funding,
        features,
        config,
        base.ProfitFloorConfig(enabled=False),
    )
    events = build_event_ledger(frame, funding, features, factor_frame, baseline, config)
    feature_names = model_feature_names(events, factor_names)
    split_masks = build_split_masks(events)
    split_audit = summarize_splits(events, split_masks)

    model, model_search = choose_model(events, feature_names, split_masks)
    events["score"] = np.nan
    scoreable = events[feature_names].notna().any(axis=1)
    events.loc[scoreable, "score"] = model.predict_proba(
        events.loc[scoreable, feature_names]
    )[:, 1]

    calibration_search, filter_choice, hybrid_choice = choose_thresholds(
        frame=frame,
        funding=funding,
        features=features,
        events=events,
        config=config,
        period_start=TRAIN_END,
        period_end=CALIBRATION_END,
    )

    comparisons: dict[str, Any] = {}
    trade_frames: list[pd.DataFrame] = []
    for period_name, period_start, period_end in [
        ("calibration", TRAIN_END, CALIBRATION_END),
        ("validation", CALIBRATION_END, VALIDATION_END),
        ("oos_reused_window", VALIDATION_END, OOS_END),
        ("full", frame.index[config.warmup_bars], OOS_END),
    ]:
        period_runs = evaluate_variants(
            frame=frame,
            funding=funding,
            features=features,
            events=events,
            config=config,
            period_start=period_start,
            period_end=period_end,
            filter_threshold=filter_choice["filter_threshold"],
            hybrid_filter_threshold=hybrid_choice["filter_threshold"],
            hybrid_rescue_threshold=hybrid_choice["rescue_threshold"],
        )
        comparisons[period_name] = {
            name: period_metrics(result, period_start, period_end)
            for name, result in period_runs.items()
        }
        for name, result in period_runs.items():
            if result.trades.empty:
                continue
            trades = result.trades.copy()
            trades.insert(0, "period", period_name)
            trades.insert(1, "variant", name)
            trade_frames.append(trades)

    importance = pd.DataFrame(
        {
            "feature": feature_names,
            "gain": model.booster_.feature_importance(importance_type="gain"),
            "split": model.booster_.feature_importance(importance_type="split"),
        }
    ).sort_values(["gain", "split"], ascending=False)

    event_path = OUT_DIR / "hype_ema_tb_v35_event_scores.parquet"
    search_path = OUT_DIR / "hype_ema_tb_v35_threshold_search.csv"
    trades_path = OUT_DIR / "hype_ema_tb_v35_variant_trades.csv"
    importance_path = OUT_DIR / "hype_ema_tb_v35_feature_importance.csv"
    model_path = OUT_DIR / "hype_ema_tb_v35_lightgbm_model.txt"
    summary_path = OUT_DIR / "hype_ema_tb_v35_lightgbm_signal_scoring.json"

    events.to_parquet(event_path, index=False)
    calibration_search.to_csv(search_path, index=False)
    importance.to_csv(importance_path, index=False)
    if trade_frames:
        pd.concat(trade_frames, ignore_index=True).to_csv(trades_path, index=False)
    model.booster_.save_model(str(model_path))

    summary = {
        "diagnostic_id": "HYPE-EMA-TB-V35 LightGBM signal scoring 2026-07-17",
        "status": "diagnostic only; not promoted; not live-ready",
        "strategy_identity": "HYPE-EMA-Trend-Breakout / HYPE-EMA-TB-V35",
        "data_quality": data_quality,
        "factor_audit": factor_audit,
        "v35_config": asdict(config),
        "baseline_full": baseline.metrics,
        "event_definition": {
            "long_candidate": "EMA96>EMA384 and last closed 1h +DI21>-DI21",
            "short_candidate": "EMA96<EMA384 and last closed 1h EMA24<EMA96",
            "v35_rule_pass": "exact V35 long_signal or short_signal at K0 close",
            "execution": "K0 close score; K2 open entry; entry ATR is K1 closed ATR672",
            "counterfactual_label": "isolated V35 trade path with 5ATR TP, 7ATR SL, ADX22 delayed3 exit, 384-bar timeout, funding and 8.5bps per fill",
            "event_net_return": "includes entry and exit costs; censored events are excluded from training",
            "state_blocked": "V35-qualified signal that was not opened because the canonical single-position state machine was occupied or exiting",
        },
        "split_contract": {
            "train": f"signal_ts < {TRAIN_END.isoformat()}, label exit must also precede boundary",
            "calibration": f"{TRAIN_END.isoformat()} <= signal_ts < {CALIBRATION_END.isoformat()}; model and thresholds selected here",
            "validation": f"{CALIBRATION_END.isoformat()} <= signal_ts < {VALIDATION_END.isoformat()}; frozen pre-OOS check",
            "oos_reused_window": f"{VALIDATION_END.isoformat()} <= signal_ts <= {OOS_END.isoformat()}; revealed once in this diagnostic, but the market window was used by the separate factor-ML family and is not pristine OOS",
        },
        "split_audit": split_audit,
        "feature_count": len(feature_names),
        "factor_count": len(factor_names),
        "model_search": model_search,
        "chosen_model": model_search[0],
        "threshold_choices": {
            "filter_only": filter_choice,
            "hybrid": hybrid_choice,
        },
        "comparisons": comparisons,
        "top_feature_importance": importance.head(30).to_dict("records"),
        "artifacts": {
            "events": str(event_path),
            "threshold_search": str(search_path),
            "trades": str(trades_path),
            "feature_importance": str(importance_path),
            "model": str(model_path),
        },
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=json_default),
        encoding="utf-8",
    )

    print(f"data {data_quality['start']} -> {data_quality['end']} rows={data_quality['rows']}")
    print(f"events={len(events)} factors={len(factor_names)} model_features={len(feature_names)}")
    print(f"chosen model={model_search[0]['name']} calibration_auc={model_search[0]['calibration_auc']:.4f}")
    print(f"filter threshold={filter_choice['filter_threshold']:.6f}")
    print(
        "hybrid thresholds="
        f"{hybrid_choice['filter_threshold']:.6f}/{hybrid_choice['rescue_threshold']:.6f}"
    )
    for period_name, variants in comparisons.items():
        print(f"\n[{period_name}]")
        for name, metrics in variants.items():
            print(
                f"{name:>12} ret={metrics['return_pct']:>9.2f}% "
                f"dd={metrics['max_drawdown_pct']:>7.2f}% "
                f"win={metrics['win_rate_pct']:>6.2f}% trades={metrics['trades']:>3} "
                f"sharpe={metrics['sharpe']:>5.2f}"
            )
    print(f"\nsummary -> {summary_path}")


def load_factor_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    if not FACTOR_DATASET.exists() or not FACTOR_MANIFEST.exists():
        raise FileNotFoundError("The audited HYPE 15m factor dataset/manifest is missing.")
    factors = pd.read_parquet(FACTOR_DATASET)
    factors["ts"] = pd.to_datetime(factors["ts"], utc=True)
    factors = factors.sort_values("ts").drop_duplicates("ts", keep="last").set_index("ts")
    common = frame.index.intersection(factors.index)
    if len(common) != len(frame) or not frame.index.equals(common):
        raise RuntimeError("Factor dataset timestamps do not exactly align with V35 OHLCV.")
    max_diff = {
        column: float((frame.loc[common, column] - factors.loc[common, column]).abs().max())
        for column in ["open", "high", "low", "close", "volume"]
    }
    if any(value > 1e-12 for value in max_diff.values()):
        raise RuntimeError(f"Factor/V35 OHLCV mismatch: {max_diff}")
    manifest_bytes = FACTOR_MANIFEST.read_bytes()
    manifest = json.loads(manifest_bytes)
    factor_names = sorted(
        column
        for column in factors.columns
        if column not in NON_FACTOR_COLUMNS and pd.api.types.is_numeric_dtype(factors[column])
    )
    if len(factor_names) != int(manifest["factor_count"]):
        raise RuntimeError(
            f"Factor count mismatch: parquet={len(factor_names)} manifest={manifest['factor_count']}"
        )
    audit = {
        "dataset": str(FACTOR_DATASET),
        "manifest": str(FACTOR_MANIFEST),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "rows": len(factors),
        "factor_count": len(factor_names),
        "timestamp_alignment": "PASS",
        "ohlcv_max_abs_diff": max_diff,
        "upstream_data_quality_sha256": manifest["data_quality"].get(
            "upstream_data_quality_sha256"
        ),
    }
    return factors, factor_names, audit


def build_event_ledger(
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    factor_frame: pd.DataFrame,
    baseline: base.RunResult,
    config: base.V35Config,
) -> pd.DataFrame:
    actual_signal_bars: set[int] = set()
    if not baseline.trades.empty:
        actual_signal_bars.update(
            int(entry_bar) - config.entry_delay_bars
            for entry_bar in baseline.trades["entry_bar"]
        )
    if baseline.open_position is not None:
        entry_ts = pd.Timestamp(baseline.open_position["entry_ts"])
        entry_bar = int(frame.index.get_loc(entry_ts))
        actual_signal_bars.add(entry_bar - config.entry_delay_bars)

    rows: list[dict[str, Any]] = []
    start = config.warmup_bars
    last_signal_bar = len(frame) - config.entry_delay_bars - 1
    required = [
        "atr",
        "ema_spread",
        "adx",
        "volume_surge",
        "h1_adx",
        "h1_plus_di",
        "h1_minus_di",
        "h1_ema_spread",
    ]
    for signal_bar in range(start, last_signal_bar + 1):
        row = features.iloc[signal_bar]
        if not np.isfinite(row[required].astype(float)).all():
            continue
        long_core = row["ema_spread"] > 0.0 and row["h1_plus_di"] > row["h1_minus_di"]
        short_core = row["ema_spread"] < 0.0 and row["h1_ema_spread"] < 0.0
        if long_core == short_core:
            continue
        direction = 1 if long_core else -1
        rule_pass = bool(row["long_signal"] if direction == 1 else row["short_signal"])
        outcome = isolated_event_outcome(
            signal_bar, direction, frame, funding, features, config
        )
        event: dict[str, Any] = {
            "signal_bar": signal_bar,
            "signal_ts": frame.index[signal_bar],
            "execution_bar": signal_bar + config.entry_delay_bars,
            "execution_ts": frame.index[signal_bar + config.entry_delay_bars],
            "direction": direction,
            "v35_rule_pass": int(rule_pass),
            "v35_actual_open": int(signal_bar in actual_signal_bars),
            "signal_class": (
                "opened"
                if signal_bar in actual_signal_bars
                else "state_blocked"
                if rule_pass
                else "rule_rejected"
            ),
            "long_adx_pass": int(row["adx"] >= config.long_adx_min) if direction == 1 else 0,
            "short_adx_pass": int(row["adx"] >= config.short_adx_min) if direction == -1 else 0,
            "volume_pass": int(
                row["volume_surge"]
                >= (config.long_vol_min if direction == 1 else config.short_vol_min)
            ),
            "h1_direction_pass": int(long_core if direction == 1 else short_core),
            "h1_long_adx_pass": int(row["h1_adx"] > config.h1_long_adx_min)
            if direction == 1
            else 0,
            "v35_ema_spread": float(row["ema_spread"]),
            "v35_adx": float(row["adx"]),
            "v35_volume_surge": float(row["volume_surge"]),
            "v35_h1_adx": float(row["h1_adx"]),
            "v35_h1_di_gap": float(row["h1_plus_di"] - row["h1_minus_di"]),
            "v35_h1_ema_spread": float(row["h1_ema_spread"]),
            "v35_signed_ema_spread": float(direction * row["ema_spread"]),
            "v35_signed_h1_di_gap": float(direction * (row["h1_plus_di"] - row["h1_minus_di"])),
            "v35_adx_margin": float(
                row["adx"]
                - (config.long_adx_min if direction == 1 else config.short_adx_min)
            ),
            "v35_volume_margin": float(
                row["volume_surge"]
                - (config.long_vol_min if direction == 1 else config.short_vol_min)
            ),
            **outcome,
        }
        factor_values = factor_frame.iloc[signal_bar]
        for name, value in factor_values.items():
            if name in NON_FACTOR_COLUMNS or not isinstance(value, (int, float, np.number, np.bool_)):
                continue
            event[name] = float(value) if pd.notna(value) else np.nan
        rows.append(event)
    events = pd.DataFrame(rows)
    events["target_win"] = np.where(
        events["censored"].eq(0), events["event_net_return"].gt(0.0).astype(float), np.nan
    )
    events["episode_id"] = build_episode_ids(events)
    episode_size = events.groupby("episode_id")["episode_id"].transform("size")
    events["sample_weight"] = (
        1.0 / np.sqrt(episode_size.astype(float))
    ) * np.where(events["v35_rule_pass"].eq(1), 2.0, 1.0)
    return events


def isolated_event_outcome(
    signal_bar: int,
    direction: int,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
) -> dict[str, Any]:
    entry_bar = signal_bar + config.entry_delay_bars
    entry_price = float(frame["open"].iloc[entry_bar])
    entry_atr = float(features["atr"].iloc[entry_bar - 1])
    if not np.isfinite(entry_atr) or entry_atr <= 0.0 or entry_price <= 0.0:
        return censored_outcome()
    target = config.long_target_atr_pct if direction == 1 else config.short_target_atr_pct
    allocation = min(config.max_allocation, target / (entry_atr / entry_price))
    equity = 1.0 - config.trade_cost_rate * allocation
    position = base.Position(
        direction=direction,
        entry_bar=entry_bar,
        entry_ts=pd.Timestamp(frame.index[entry_bar]),
        entry_price=entry_price,
        entry_atr=entry_atr,
        allocation=allocation,
        entry_equity=equity,
        previous_price=entry_price,
    )
    pending_exit: str | None = None
    trades: list[dict[str, Any]] = []
    no_floor = base.ProfitFloorConfig(enabled=False)
    for bar in range(entry_bar, len(frame)):
        ts = pd.Timestamp(frame.index[bar])
        open_price = float(frame["open"].iloc[bar])
        if bar > entry_bar and pending_exit is not None:
            equity, _ = base.close_position(
                equity=equity,
                position=position,
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=bar,
                reason=pending_exit,
                trades=trades,
                config=config,
            )
            return completed_outcome(equity, trades[-1])
        if bar > entry_bar:
            equity *= 1.0 - direction * allocation * float(funding.iloc[bar])
        intrabar = base.check_intrabar_exit(
            position=position,
            open_price=open_price,
            high=float(frame["high"].iloc[bar]),
            low=float(frame["low"].iloc[bar]),
            config=config,
        )
        if intrabar is not None:
            reason, exit_price = intrabar
            equity, _ = base.close_position(
                equity=equity,
                position=position,
                exit_price=exit_price,
                exit_ts=ts,
                exit_bar=bar,
                reason=reason,
                trades=trades,
                config=config,
            )
            return completed_outcome(equity, trades[-1])
        close = float(frame["close"].iloc[bar])
        equity *= 1.0 + direction * allocation * (close / position.previous_price - 1.0)
        position.previous_price = close
        base.update_position_on_close(
            position,
            float(frame["high"].iloc[bar]),
            float(frame["low"].iloc[bar]),
            config,
            no_floor,
        )
        can_indicator_exit = position.mfe_atr < config.disable_after_mfe_atr
        if can_indicator_exit and float(features["adx"].iloc[bar]) < config.adx_exit:
            position.weak_bars += 1
        else:
            position.weak_bars = 0
        if can_indicator_exit and position.weak_bars >= config.delayed_bars:
            pending_exit = "indicator_exit"
        if pending_exit is None and bar - entry_bar >= config.max_hold_bars:
            pending_exit = "timeout"
    return censored_outcome()


def completed_outcome(equity: float, trade: dict[str, Any]) -> dict[str, Any]:
    return {
        "censored": 0,
        "label_exit_ts": trade["exit_ts"],
        "label_exit_reason": trade["exit_reason"],
        "label_hold_bars": trade["hold_bars"],
        "label_mfe_atr": trade["mfe_atr"],
        "event_net_return": equity - 1.0,
        "event_trade_return_ex_entry_cost": trade["trade_return"],
    }


def censored_outcome() -> dict[str, Any]:
    return {
        "censored": 1,
        "label_exit_ts": pd.NaT,
        "label_exit_reason": "censored",
        "label_hold_bars": np.nan,
        "label_mfe_atr": np.nan,
        "event_net_return": np.nan,
        "event_trade_return_ex_entry_cost": np.nan,
    }


def build_episode_ids(events: pd.DataFrame) -> pd.Series:
    signal_bar = events["signal_bar"]
    new_episode = events["direction"].ne(events["direction"].shift(1)) | signal_bar.diff().ne(1)
    return new_episode.cumsum().astype(int)


def model_feature_names(events: pd.DataFrame, factor_names: list[str]) -> list[str]:
    native = [
        "direction",
        "v35_rule_pass",
        "long_adx_pass",
        "short_adx_pass",
        "volume_pass",
        "h1_long_adx_pass",
        "v35_ema_spread",
        "v35_adx",
        "v35_volume_surge",
        "v35_h1_adx",
        "v35_h1_di_gap",
        "v35_h1_ema_spread",
        "v35_signed_ema_spread",
        "v35_signed_h1_di_gap",
        "v35_adx_margin",
        "v35_volume_margin",
    ]
    names = native + factor_names
    return [name for name in names if name in events and events[name].notna().any()]


def build_split_masks(events: pd.DataFrame) -> dict[str, pd.Series]:
    signal_ts = pd.to_datetime(events["signal_ts"], utc=True)
    exit_ts = pd.to_datetime(events["label_exit_ts"], utc=True)
    complete = events["censored"].eq(0)
    return {
        "train": complete & signal_ts.lt(TRAIN_END) & exit_ts.lt(TRAIN_END),
        "calibration": complete & signal_ts.ge(TRAIN_END) & signal_ts.lt(CALIBRATION_END) & exit_ts.lt(CALIBRATION_END),
        "validation": complete & signal_ts.ge(CALIBRATION_END) & signal_ts.lt(VALIDATION_END) & exit_ts.lt(VALIDATION_END),
        "oos_reused_window": complete & signal_ts.ge(VALIDATION_END) & signal_ts.le(OOS_END),
    }


def summarize_splits(events: pd.DataFrame, masks: dict[str, pd.Series]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, mask in masks.items():
        rows = events.loc[mask]
        result[name] = {
            "events": len(rows),
            "wins": int(rows["target_win"].sum()),
            "win_rate_pct": round(100.0 * float(rows["target_win"].mean()), 2),
            "v35_rule_pass": int(rows["v35_rule_pass"].sum()),
            "v35_actual_open": int(rows["v35_actual_open"].sum()),
            "long": int(rows["direction"].eq(1).sum()),
            "short": int(rows["direction"].eq(-1).sum()),
        }
    result["all_event_classes"] = {
        str(key): int(value) for key, value in events["signal_class"].value_counts().items()
    }
    result["censored"] = int(events["censored"].sum())
    return result


def choose_model(
    events: pd.DataFrame,
    feature_names: list[str],
    split_masks: dict[str, pd.Series],
) -> tuple[lgb.LGBMClassifier, list[dict[str, Any]]]:
    train = events.loc[split_masks["train"]]
    calibration = events.loc[split_masks["calibration"]]
    rows: list[dict[str, Any]] = []
    models: dict[str, lgb.LGBMClassifier] = {}
    for spec in MODEL_SPECS:
        model = lgb.LGBMClassifier(
            objective="binary",
            n_estimators=500,
            learning_rate=0.025,
            num_leaves=spec["num_leaves"],
            min_child_samples=spec["min_child_samples"],
            subsample=0.80,
            subsample_freq=1,
            colsample_bytree=spec["feature_fraction"],
            reg_alpha=1.0,
            reg_lambda=spec["reg_lambda"],
            random_state=35,
            n_jobs=-1,
            verbosity=-1,
        )
        model.fit(
            train[feature_names],
            train["target_win"].astype(int),
            sample_weight=train["sample_weight"],
            eval_set=[(calibration[feature_names], calibration["target_win"].astype(int))],
            eval_metric="binary_logloss",
            callbacks=[lgb.early_stopping(40, verbose=False), lgb.log_evaluation(0)],
        )
        probability = model.predict_proba(calibration[feature_names])[:, 1]
        auc = roc_auc_score(calibration["target_win"], probability)
        ap = average_precision_score(calibration["target_win"], probability)
        brier = brier_score_loss(calibration["target_win"], probability)
        rows.append(
            {
                **spec,
                "best_iteration": int(model.best_iteration_),
                "calibration_auc": float(auc),
                "calibration_average_precision": float(ap),
                "calibration_brier": float(brier),
                "selection_score": float(0.5 * auc + 0.5 * ap - 0.1 * brier),
            }
        )
        models[spec["name"]] = model
    rows.sort(key=lambda row: row["selection_score"], reverse=True)
    return models[rows[0]["name"]], rows


def choose_thresholds(
    *,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    events: pd.DataFrame,
    config: base.V35Config,
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    period = events[
        pd.to_datetime(events["signal_ts"], utc=True).ge(period_start)
        & pd.to_datetime(events["signal_ts"], utc=True).lt(period_end)
        & events["score"].notna()
    ]
    passed_scores = period.loc[period["v35_rule_pass"].eq(1), "score"]
    rejected_scores = period.loc[period["v35_rule_pass"].eq(0), "score"]
    filter_thresholds = sorted(
        set(float(passed_scores.quantile(q)) for q in [0.0, 0.10, 0.25, 0.40, 0.55, 0.70, 0.82])
    )
    rescue_thresholds = sorted(
        set(float(rejected_scores.quantile(q)) for q in [0.80, 0.90, 0.95, 0.975, 0.99, 0.995])
    )
    rows: list[dict[str, Any]] = []
    for filter_threshold in filter_thresholds:
        for rescue_threshold in [np.inf, *rescue_thresholds]:
            selected = event_signal_frame(
                events,
                frame.index,
                period_start,
                period_end,
                filter_threshold,
                rescue_threshold,
            )
            run_features = features.copy()
            run_features["long_signal"] = selected["long_signal"]
            run_features["short_signal"] = selected["short_signal"]
            result = base.run_backtest(
                "threshold_search",
                frame,
                funding,
                run_features,
                config,
                base.ProfitFloorConfig(enabled=False),
            )
            metrics = period_metrics(result, period_start, period_end)
            rows.append(
                {
                    "filter_threshold": filter_threshold,
                    "rescue_threshold": rescue_threshold,
                    "mode": "filter_only" if np.isinf(rescue_threshold) else "hybrid",
                    **metrics,
                    "utility": strategy_utility(metrics),
                }
            )
    search = pd.DataFrame(rows).sort_values("utility", ascending=False)
    filter_rows = search[search["mode"].eq("filter_only")].copy()
    hybrid_rows = search[search["mode"].eq("hybrid")].copy()
    filter_choice = choose_with_trade_gate(filter_rows)
    hybrid_choice = choose_with_trade_gate(hybrid_rows)
    return search, filter_choice, hybrid_choice


def choose_with_trade_gate(rows: pd.DataFrame) -> dict[str, Any]:
    if rows.empty:
        raise RuntimeError("No threshold candidates.")
    max_trades = int(rows["trades"].max())
    minimum = max(8, int(np.ceil(max_trades * 0.40)))
    eligible = rows[rows["trades"].ge(minimum)]
    if eligible.empty:
        eligible = rows
    return eligible.sort_values("utility", ascending=False).iloc[0].to_dict()


def strategy_utility(metrics: dict[str, Any]) -> float:
    final_multiple = max(0.01, 1.0 + metrics["return_pct"] / 100.0)
    return float(
        np.log(final_multiple)
        + 1.5 * (metrics["win_rate_pct"] / 100.0 - 0.5)
        - 1.5 * abs(metrics["max_drawdown_pct"] / 100.0)
        + 0.10 * metrics["sharpe"]
    )


def evaluate_variants(
    *,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    events: pd.DataFrame,
    config: base.V35Config,
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
    filter_threshold: float,
    hybrid_filter_threshold: float,
    hybrid_rescue_threshold: float,
) -> dict[str, base.RunResult]:
    masks: dict[str, pd.DataFrame] = {}
    baseline_signals = pd.DataFrame(False, index=frame.index, columns=["long_signal", "short_signal"])
    in_period = (frame.index >= period_start) & (frame.index < period_end)
    baseline_signals.loc[in_period, "long_signal"] = features.loc[in_period, "long_signal"]
    baseline_signals.loc[in_period, "short_signal"] = features.loc[in_period, "short_signal"]
    masks["v35_base"] = baseline_signals
    masks["ml_filter"] = event_signal_frame(
        events, frame.index, period_start, period_end, filter_threshold, np.inf
    )
    masks["ml_hybrid"] = event_signal_frame(
        events,
        frame.index,
        period_start,
        period_end,
        hybrid_filter_threshold,
        hybrid_rescue_threshold,
    )
    results: dict[str, base.RunResult] = {}
    for name, signals in masks.items():
        run_features = features.copy()
        run_features["long_signal"] = signals["long_signal"]
        run_features["short_signal"] = signals["short_signal"]
        results[name] = base.run_backtest(
            name,
            frame,
            funding,
            run_features,
            config,
            base.ProfitFloorConfig(enabled=False),
        )
    return results


def event_signal_frame(
    events: pd.DataFrame,
    index: pd.DatetimeIndex,
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
    filter_threshold: float,
    rescue_threshold: float,
) -> pd.DataFrame:
    signals = pd.DataFrame(False, index=index, columns=["long_signal", "short_signal"])
    event_ts = pd.to_datetime(events["signal_ts"], utc=True)
    in_period = event_ts.ge(period_start) & event_ts.lt(period_end) & events["score"].notna()
    selected = in_period & (
        (events["v35_rule_pass"].eq(1) & events["score"].ge(filter_threshold))
        | (events["v35_rule_pass"].eq(0) & events["score"].ge(rescue_threshold))
    )
    chosen = events.loc[selected, ["signal_ts", "direction"]]
    long_ts = pd.DatetimeIndex(pd.to_datetime(chosen.loc[chosen["direction"].eq(1), "signal_ts"], utc=True))
    short_ts = pd.DatetimeIndex(pd.to_datetime(chosen.loc[chosen["direction"].eq(-1), "signal_ts"], utc=True))
    signals.loc[signals.index.intersection(long_ts), "long_signal"] = True
    signals.loc[signals.index.intersection(short_ts), "short_signal"] = True
    return signals


def period_metrics(
    result: base.RunResult, period_start: pd.Timestamp, period_end: pd.Timestamp
) -> dict[str, Any]:
    curve = result.equity_curve
    before = curve.loc[curve.index < period_start]
    initial = float(before.iloc[-1]) if not before.empty else 1.0
    sliced = curve.loc[(curve.index >= period_start) & (curve.index <= period_end)] / initial
    if sliced.empty:
        return {
            "return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe": 0.0,
            "trades": 0,
            "wins": 0,
            "win_rate_pct": 0.0,
        }
    drawdown = sliced / sliced.cummax() - 1.0
    returns = result.period_returns.loc[sliced.index]
    volatility = float(returns.std(ddof=0))
    trades = result.trades
    if not trades.empty:
        entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
        exit_ts = pd.to_datetime(trades["exit_ts"], utc=True)
        trades = trades.loc[
            entry_ts.ge(period_start) & entry_ts.lt(period_end) & exit_ts.le(period_end)
        ]
    wins = int(trades["trade_return"].gt(0.0).sum()) if not trades.empty else 0
    return {
        "return_pct": round(100.0 * float(sliced.iloc[-1] - 1.0), 2),
        "max_drawdown_pct": round(100.0 * float(drawdown.min()), 2),
        "sharpe": round(
            float(0.0 if volatility == 0.0 else returns.mean() / volatility * np.sqrt(base.M15_PER_YEAR)),
            2,
        ),
        "trades": int(len(trades)),
        "wins": wins,
        "win_rate_pct": round(100.0 * wins / len(trades), 2) if len(trades) else 0.0,
    }


def json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"Not JSON serializable: {type(value)!r}")


if __name__ == "__main__":
    main()
