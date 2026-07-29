from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

import sds_engine as engine
import research_hype_15m_sds_kalman_cusum_structure as kcs


FAMILY_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = ARTIFACT_DIR / "hype_15m_sds_kcs_full_ablation_contract.json"
RESULT_PATH = ARTIFACT_DIR / "hype_15m_sds_kcs_full_ablation.csv"
PARAMETER_SUMMARY_PATH = (
    ARTIFACT_DIR / "hype_15m_sds_kcs_full_ablation_parameter_summary.csv"
)
SUMMARY_PATH = ARTIFACT_DIR / "hype_15m_sds_kcs_full_ablation_summary.json"


SIGNAL_VALUES: dict[str, list[Any]] = {
    "volatility_span": [48, 72, 96, 144, 192],
    "kalman_process_ratio": [0.001, 0.003, 0.01, 0.03, 0.10],
    "kalman_measurement_multiplier": [0.5, 1.0, 2.0, 4.0, 8.0],
    "kalman_slope_vol_entry": [0.01, 0.025, 0.05, 0.10, 0.20, 0.40],
    "kalman_slope_z_entry": [0.0, 0.5, 1.0, 1.5, 2.0, 3.0],
    "kalman_slope_vol_exit": [-0.20, -0.10, 0.0, 0.05, 0.10, 0.20],
    "cusum_allowance": [0.0, 0.05, 0.15, 0.25, 0.50],
    "cusum_entry": [1.5, 2.0, 3.0, 5.0, 7.0, 10.0],
    "structure_window": [16, 32, 48, 64, 96, 128],
    "exit_window": [8, 16, 24, 32, 48, 64],
    "efficiency_window": [16, 32, 48, 64, 96, 128],
    "efficiency_min": [0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60],
    "arm_timeout_bars": [1, 4, 8, 16, 32, 64],
    "exit_confirm_bars": [1, 2, 3, 4, 6, 8],
    "require_cusum": [True, False],
    "require_kalman": [True, False],
    "require_structure": [True, False],
    "require_efficiency": [True, False],
}

RISK_VALUES: dict[str, list[Any]] = {
    "stop_atr": [2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 1_000_000.0],
    "max_hold_bars": [96, 192, 384, 768, 1536],
    "leverage": [0.5, 1.0, 1.5, 2.0, 3.0],
}


def _reference_configs() -> tuple[kcs.KCSConfig, engine.Config]:
    payload = json.loads(kcs.SUMMARY_PATH.read_text(encoding="utf-8"))
    reference = payload["reference"]
    signal_fields = set(kcs.KCSConfig.__dataclass_fields__)
    signal = kcs.KCSConfig(
        **{field: reference[field] for field in signal_fields}
    )
    risk = engine.Config(stop_atr=4.0, max_hold_bars=384, leverage=1.0)
    return signal, risk


def _trade_path_sha256(result: engine.BacktestResult) -> str:
    path = [
        {
            "signal_ts": trade["signal_ts"],
            "entry_ts": trade["entry_ts"],
            "exit_ts": trade["exit_ts"],
            "direction": trade["direction"],
            "exit_reason": trade["exit_reason"],
        }
        for trade in result.trades
    ]
    raw = json.dumps(path, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _equity_path_sha256(result: engine.BacktestResult) -> str:
    path = [
        (row["ts"], round(float(row["equity"]), 12), int(row["position"]))
        for row in result.equity_path
    ]
    raw = json.dumps(path, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _score(
    train: dict[str, Any],
    validation: dict[str, Any],
    *,
    valid_sample: bool,
) -> float:
    if not valid_sample:
        return -1e9
    return (
        math.log(max(1e-9, 1.0 + float(train["return"])))
        + math.log(max(1e-9, 1.0 + float(validation["return"])))
        + float(train["max_drawdown"])
        + float(validation["max_drawdown"])
    )


def _evaluate(
    *,
    book: engine.FeatureBook,
    validation_start: pd.Timestamp,
    signal_config: kcs.KCSConfig,
    risk_config: engine.Config,
    parameter: str,
    value: Any,
    scope: str,
    baseline_path_sha256: str | None,
    baseline_equity_sha256: str | None,
) -> tuple[dict[str, Any], engine.BacktestResult]:
    features = kcs.build_features(book, signal_config)
    states = kcs.generate_kcs_states(book, signal_config, features=features)
    result = engine.run_backtest(book, risk_config, states=states)
    train = engine.slice_metrics(
        result,
        start=book.source_start,
        end=validation_start,
    )
    validation = engine.slice_metrics(
        result,
        start=validation_start,
        end=book.terminal_ts,
    )
    valid_sample = train["trades"] >= 30 and validation["trades"] >= 10
    joint_positive = train["return"] > 0.0 and validation["return"] > 0.0
    trade_path_sha256 = _trade_path_sha256(result)
    equity_path_sha256 = _equity_path_sha256(result)
    row = {
        "scope": scope,
        "parameter": parameter,
        "value": value,
        "signal_config": json.dumps(
            asdict(signal_config),
            sort_keys=True,
            separators=(",", ":"),
        ),
        "risk_config": json.dumps(
            engine.config_payload(risk_config),
            sort_keys=True,
            separators=(",", ":"),
        ),
        "train_return": train["return"],
        "train_max_drawdown": train["max_drawdown"],
        "train_trades": train["trades"],
        "train_win_rate": train["win_rate"],
        "validation_return": validation["return"],
        "validation_max_drawdown": validation["max_drawdown"],
        "validation_trades": validation["trades"],
        "validation_win_rate": validation["win_rate"],
        "prefit_return": result.metrics["total_return"],
        "prefit_max_drawdown": result.metrics["max_drawdown"],
        "prefit_trades": result.metrics["trades"],
        "prefit_win_rate": result.metrics["win_rate"],
        "prefit_average_trade": result.metrics["average_trade"],
        "prefit_median_bars_held": result.metrics["median_bars_held"],
        "valid_sample": valid_sample,
        "joint_positive": joint_positive,
        "eligible": valid_sample and joint_positive,
        "score": _score(train, validation, valid_sample=valid_sample),
        "trade_path_sha256": trade_path_sha256,
        "equity_path_sha256": equity_path_sha256,
        "trade_path_equal_baseline": (
            trade_path_sha256 == baseline_path_sha256
            if baseline_path_sha256 is not None
            else True
        ),
        "equity_path_equal_baseline": (
            equity_path_sha256 == baseline_equity_sha256
            if baseline_equity_sha256 is not None
            else True
        ),
    }
    return row, result


def _parameter_summary(
    results: pd.DataFrame,
    baseline: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline_return = float(baseline["prefit_return"])
    baseline_drawdown = float(baseline["prefit_max_drawdown"])
    for parameter, group in results.loc[results["scope"] != "baseline"].groupby(
        "parameter",
        sort=True,
    ):
        ranked = group.sort_values(
            ["eligible", "valid_sample", "score"],
            ascending=[False, False, False],
        )
        best = ranked.iloc[0]
        path_equal_count = int(group["trade_path_equal_baseline"].sum())
        equity_equal_count = int(group["equity_path_equal_baseline"].sum())
        rows.append(
            {
                "parameter": parameter,
                "variant_count": int(len(group)),
                "valid_sample_count": int(group["valid_sample"].sum()),
                "eligible_count": int(group["eligible"].sum()),
                "path_equal_count": path_equal_count,
                "equity_equal_count": equity_equal_count,
                "all_variants_path_equal": path_equal_count == len(group),
                "all_variants_equity_equal": equity_equal_count == len(group),
                "best_value": best["value"],
                "best_train_return": best["train_return"],
                "best_validation_return": best["validation_return"],
                "best_prefit_return": best["prefit_return"],
                "best_prefit_max_drawdown": best["prefit_max_drawdown"],
                "best_prefit_trades": best["prefit_trades"],
                "return_delta_vs_baseline": (
                    float(best["prefit_return"]) - baseline_return
                ),
                "drawdown_delta_vs_baseline": (
                    float(best["prefit_max_drawdown"]) - baseline_drawdown
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["eligible_count", "return_delta_vs_baseline"],
        ascending=[False, False],
    )


def main() -> None:
    manifest = json.loads(engine.FREEZE_PATH.read_text(encoding="utf-8"))
    book = engine.build_book(include_locked_oos=False)
    expected_terminal = pd.Timestamp(
        manifest["freeze_contract"]["locked_oos_start_inclusive"]
    )
    if book.terminal_ts != expected_terminal:
        raise RuntimeError("full ablation attempted to read beyond frozen prefit")
    validation_start = book.terminal_ts - pd.DateOffset(months=3)
    baseline_signal, baseline_risk = _reference_configs()

    contract_payload = {
        "family": "HYPE-15M-Sequential-Drift-State",
        "mechanism": "Kalman + CUSUM + structure confirmation",
        "scope": "one-parameter-at-a-time full ablation of the frozen failed KCS reference; prefit only",
        "oos_read_authorized": False,
        "prefit_terminal_exclusive": book.terminal_ts.isoformat(),
        "validation_start_inclusive": validation_start.isoformat(),
        "baseline_signal_config": asdict(baseline_signal),
        "baseline_risk_config": engine.config_payload(baseline_risk),
        "signal_values": SIGNAL_VALUES,
        "risk_values": RISK_VALUES,
        "selection_rule": "diagnostic only; require train>=30 and validation>=10 trades and both returns positive; do not combine winners after ablation",
        "path_equal_rule": "compare signal/entry/exit/direction/reason SHA256 against frozen baseline",
    }
    raw = json.dumps(
        contract_payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    contract_payload["contract_sha256"] = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()
    contract_payload["script_sha256"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(
        json.dumps(contract_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    baseline_row, baseline_result = _evaluate(
        book=book,
        validation_start=validation_start,
        signal_config=baseline_signal,
        risk_config=baseline_risk,
        parameter="__baseline__",
        value="frozen_reference",
        scope="baseline",
        baseline_path_sha256=None,
        baseline_equity_sha256=None,
    )
    baseline_path_sha256 = baseline_row["trade_path_sha256"]
    baseline_equity_sha256 = baseline_row["equity_path_sha256"]
    rows = [baseline_row]

    for parameter, values in SIGNAL_VALUES.items():
        baseline_value = getattr(baseline_signal, parameter)
        for value in values:
            if value == baseline_value:
                continue
            signal_config = replace(baseline_signal, **{parameter: value})
            row, _ = _evaluate(
                book=book,
                validation_start=validation_start,
                signal_config=signal_config,
                risk_config=baseline_risk,
                parameter=parameter,
                value=value,
                scope="signal",
                baseline_path_sha256=baseline_path_sha256,
                baseline_equity_sha256=baseline_equity_sha256,
            )
            rows.append(row)

    for parameter, values in RISK_VALUES.items():
        baseline_value = getattr(baseline_risk, parameter)
        for value in values:
            if value == baseline_value:
                continue
            risk_config = replace(baseline_risk, **{parameter: value})
            row, _ = _evaluate(
                book=book,
                validation_start=validation_start,
                signal_config=baseline_signal,
                risk_config=risk_config,
                parameter=parameter,
                value=value,
                scope="risk",
                baseline_path_sha256=baseline_path_sha256,
                baseline_equity_sha256=baseline_equity_sha256,
            )
            rows.append(row)

    results = pd.DataFrame(rows)
    parameter_summary = _parameter_summary(results, baseline_row)
    variants = results.loc[results["scope"] != "baseline"].copy()
    ranking = variants.sort_values(
        ["eligible", "valid_sample", "score"],
        ascending=[False, False, False],
    )
    best = ranking.iloc[0].to_dict()
    path_equal_parameters = parameter_summary.loc[
        parameter_summary["all_variants_path_equal"],
        "parameter",
    ].tolist()
    any_path_equal_parameters = parameter_summary.loc[
        parameter_summary["path_equal_count"] > 0,
        "parameter",
    ].tolist()
    summary = {
        "family": "HYPE-15M-Sequential-Drift-State",
        "mechanism": "KCS full one-parameter ablation",
        "status": "diagnostic of failed reference / not registered / not promoted / not live-ready",
        "oos_read": False,
        "prefit_terminal_exclusive": book.terminal_ts.isoformat(),
        "baseline": baseline_row,
        "variant_count": int(len(variants)),
        "parameter_count": int(len(parameter_summary)),
        "valid_sample_count": int(variants["valid_sample"].sum()),
        "eligible_count": int(variants["eligible"].sum()),
        "train_positive_count": int((variants["train_return"] > 0.0).sum()),
        "validation_positive_count": int(
            (variants["validation_return"] > 0.0).sum()
        ),
        "joint_positive_count": int(variants["joint_positive"].sum()),
        "best_variant": best,
        "all_variants_path_equal_parameters": path_equal_parameters,
        "parameters_with_any_path_equal_variant": any_path_equal_parameters,
        "parameter_summary": parameter_summary.to_dict(orient="records"),
        "decision_rule": (
            "ablation diagnoses active/dormant slots and local sensitivity only; "
            "do not combine best one-at-a-time values or inspect reused OOS"
        ),
    }
    results.to_csv(RESULT_PATH, index=False)
    parameter_summary.to_csv(PARAMETER_SUMMARY_PATH, index=False)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
