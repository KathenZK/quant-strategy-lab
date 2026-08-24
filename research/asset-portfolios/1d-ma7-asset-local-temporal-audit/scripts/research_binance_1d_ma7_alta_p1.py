from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-asset-local-temporal-audit"
EVENT_DIR = FAMILY_DIR / "artifacts/p0_events_2026-08-10"
EVENT_PATH = EVENT_DIR / "p0_events.parquet"
CAPACITY_PATH = EVENT_DIR / "p0_capacity.json"
OUTPUT_DIR = FAMILY_DIR / "artifacts/p1_temporal_audit_2026-08-10"
DIAGNOSTIC_PATH = FAMILY_DIR / (
    "diagnostics/binance-1d-ma7-alta-p1-temporal-audit-2026-08-10.md"
)
TFML_SCRIPT = ROOT / (
    "research/asset-portfolios/1d-ma7-taker-flow-meta-label/"
    "scripts/research_binance_1d_ma7_tfml_p1.py"
)
T0 = pd.Timestamp("2025-05-31T00:00:00Z")
T1 = pd.Timestamp("2026-08-01T00:00:00Z")
TRAIN_PURGE_END = T0 - pd.Timedelta(days=5)
ASSETS = (
    "BTC",
    "ETH",
    "BNB",
    "SOL",
    "TRX",
    "XRP",
    "DOGE",
    "ADA",
    "LINK",
    "LTC",
    "DOT",
    "AVAX",
    "UNI",
    "BCH",
    "ETC",
    "XLM",
    "ATOM",
    "VET",
    "NEAR",
    "AAVE",
    "FIL",
)
ALPHA = 1000.0
QUANTILE = 0.80
SEED = 20260810


def load_tfml() -> Any:
    spec = importlib.util.spec_from_file_location(
        "binance_1d_ma7_alta_p1_model_base", TFML_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {TFML_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tfml = load_tfml()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-samples", type=int, default=5_000)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(json_ready(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def verify_inputs() -> dict[str, Any]:
    manifest_path = EVENT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for details in manifest["files"].values():
        path = EVENT_DIR / details["path"]
        if sha256_path(path) != details["sha256"]:
            raise RuntimeError(f"Event manifest mismatch: {path}")
    capacity = json.loads(CAPACITY_PATH.read_text(encoding="utf-8"))
    if not capacity.get("p0_capacity_pass"):
        raise RuntimeError("ALTA P0 capacity did not pass")
    if set(capacity.get("assets", [])) != set(ASSETS):
        raise RuntimeError("ALTA universe mismatch")
    if any(
        int(capacity.get(key, -1)) != 0
        for key in ("hype_rows", "hype_files", "hype_requests")
    ):
        raise RuntimeError("HYPE lock failed")
    return capacity


def build_policies(
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    train = events.loc[events["exit_ts"].lt(TRAIN_PURGE_END)].copy()
    test = events.loc[
        events["signal_ts"].ge(T0) & events["signal_ts"].lt(T1)
    ].copy()
    take_all = test.copy()
    take_all["predicted_utility"] = np.nan
    take_all["selected_threshold"] = np.nan
    take_all["selected"] = True
    take_all["policy"] = "take_all"

    model_frames: list[pd.DataFrame] = []
    model_report: dict[str, Any] = {}
    for asset in ASSETS:
        asset_train = train.loc[train["asset"].eq(asset)].copy()
        asset_test = test.loc[test["asset"].eq(asset)].copy()
        if len(asset_train) < 100 or asset_test.empty:
            raise RuntimeError(
                f"{asset} has insufficient train/test rows "
                f"{len(asset_train)}/{len(asset_test)}"
            )
        model = tfml.fit_model(asset_train, tfml.PRICE_FEATURES, ALPHA)
        train_prediction = tfml.predict_utility(
            model, asset_train, tfml.PRICE_FEATURES
        )
        test_prediction = tfml.predict_utility(
            model, asset_test, tfml.PRICE_FEATURES
        )
        threshold = float(np.quantile(train_prediction, QUANTILE))
        asset_test["predicted_utility"] = test_prediction
        asset_test["selected_threshold"] = threshold
        asset_test["selected"] = asset_test["predicted_utility"].ge(threshold)
        asset_test["policy"] = "local_q80_ridge1000"
        model_frames.append(asset_test)
        model_report[asset] = {
            "train_rows": int(len(asset_train)),
            "test_rows": int(len(asset_test)),
            "threshold": threshold,
            "train_prediction": {
                "mean": float(np.mean(train_prediction)),
                "std": float(np.std(train_prediction)),
                "q80": threshold,
            },
            "test_prediction": {
                "mean": float(np.mean(test_prediction)),
                "std": float(np.std(test_prediction)),
            },
            "selected": int(asset_test["selected"].sum()),
        }
    local = pd.concat(model_frames, ignore_index=True).sort_values(
        ["signal_ts", "asset", "root_id"]
    )
    if (
        len(local) != len(test)
        or local["event_id"].duplicated().any()
        or set(local["event_id"]) != set(test["event_id"])
    ):
        raise RuntimeError("Asset-local policy changed the test universe")
    return take_all.reset_index(drop=True), local.reset_index(drop=True), model_report


def lag_audit(selected: pd.DataFrame) -> dict[str, Any]:
    executable = selected.loc[selected["z_lag1"].notna()].copy()
    missing = selected.loc[selected["z_lag1"].isna()].copy()
    executable["lag_minus_main"] = executable["z_lag1"] - executable["z_8bps"]
    portfolio_lag = selected.copy()
    portfolio_lag["z_lag1_zero_if_unavailable"] = portfolio_lag["z_lag1"].fillna(
        0.0
    )
    return {
        "selected_events": int(len(selected)),
        "executable_events": int(len(executable)),
        "executable_rate": float(len(executable) / len(selected))
        if len(selected)
        else 0.0,
        "missing_lag_main": tfml.return_metrics(missing, "z_8bps"),
        "common_main": tfml.return_metrics(executable, "z_8bps"),
        "common_lag1": tfml.return_metrics(executable, "z_lag1"),
        "common_mean_lag_minus_main": (
            float(executable["lag_minus_main"].mean())
            if len(executable)
            else 0.0
        ),
        "lag1_zero_if_unavailable": tfml.return_metrics(
            portfolio_lag, "z_lag1_zero_if_unavailable"
        ),
    }


def summarize_policy(
    oof: pd.DataFrame,
    *,
    samples: int,
) -> dict[str, Any]:
    selected = oof.loc[oof["selected"]].copy()
    per_asset: dict[str, Any] = {}
    positive_assets = 0
    positive_compound_assets = 0
    for asset in ASSETS:
        rows = selected.loc[selected["asset"].eq(asset)]
        metrics = tfml.return_metrics(rows, "z_8bps")
        if float(metrics["mean"]) > 0.0:
            positive_assets += 1
        if float(metrics["compound"]) > 0.0:
            positive_compound_assets += 1
        per_asset[asset] = {
            "selected": int(len(rows)),
            "main": metrics,
            "z_4bps": tfml.return_metrics(rows, "z_4bps"),
            "z_funding_off": tfml.return_metrics(rows, "z_funding_off"),
        }
    side_counts = {
        "long": int(selected["side"].gt(0).sum()),
        "short": int(selected["side"].lt(0).sum()),
    }
    return {
        "selected_events": int(len(selected)),
        "side_counts": side_counts,
        "assets_with_at_least_5": int(
            sum(
                int(selected["asset"].eq(asset).sum()) >= 5
                for asset in ASSETS
            )
        ),
        "main": tfml.return_metrics(selected, "z_8bps"),
        "variants": {
            "z_4bps": tfml.return_metrics(selected, "z_4bps"),
            "z_funding_off": tfml.return_metrics(selected, "z_funding_off"),
        },
        "positive_asset_count": positive_assets,
        "positive_compound_asset_count": positive_compound_assets,
        "per_asset": per_asset,
        "cluster_bootstrap": tfml.cluster_bootstrap(
            selected, samples=samples, column="z_8bps"
        ),
        "recent_slices": tfml.recent_slices(oof),
        "lag1_audit": lag_audit(selected),
    }


def apply_gate(
    capacity: dict[str, Any],
    take: dict[str, Any],
    local: dict[str, Any],
    delta: dict[str, Any],
) -> dict[str, Any]:
    take_main = take["main"]
    take_variants = take["variants"]
    take_checks = {
        "p0_capacity": bool(capacity["p0_capacity_pass"]),
        "sample_and_direction_capacity": (
            int(take["selected_events"]) >= 200
            and min(take["side_counts"].values()) >= 75
            and all(
                int(take["per_asset"][asset]["selected"]) >= 8
                for asset in ASSETS
            )
        ),
        "main_economics": (
            float(take_main["mean"]) > 0.0
            and float(take_main["profit_factor"]) >= 1.10
        ),
        "positive_assets": int(take["positive_asset_count"]) >= 12,
        "positive_compound_assets": (
            int(take["positive_compound_asset_count"]) >= 12
        ),
        "cluster_bootstrap": (
            float(take["cluster_bootstrap"]["positive_probability"]) >= 0.90
        ),
        "stress_variants": all(
            float(take_variants[column]["mean"]) > 0.0
            and float(take_variants[column]["profit_factor"]) >= 1.05
            for column in ("z_4bps", "z_funding_off")
        ),
        "hype_lock": True,
    }
    take_pass = bool(all(take_checks.values()))
    local_main = local["main"]
    local_variants = local["variants"]
    local_checks = {
        "take_all_gate": take_pass,
        "sample_capacity": (
            int(local["selected_events"]) >= 100
            and int(local["assets_with_at_least_5"]) >= 15
        ),
        "main_economics": (
            float(local_main["mean"]) > 0.0
            and float(local_main["profit_factor"]) >= 1.10
        ),
        "positive_assets": int(local["positive_asset_count"]) >= 12,
        "cluster_bootstrap": (
            float(local["cluster_bootstrap"]["positive_probability"]) >= 0.90
        ),
        "increment_over_take_all": float(delta["positive_probability"]) >= 0.90,
        "stress_variants": all(
            float(local_variants[column]["mean"]) > 0.0
            and float(local_variants[column]["profit_factor"]) >= 1.05
            for column in ("z_4bps", "z_funding_off")
        ),
        "hype_lock": True,
    }
    local_pass = bool(all(local_checks.values()))
    return {
        "take_all": {"checks": take_checks, "pass": take_pass},
        "local_q80_ridge1000": {
            "checks": local_checks,
            "pass": local_pass,
        },
        "p1_pass": bool(take_pass and local_pass),
    }


def diagnostic_markdown(report: dict[str, Any]) -> str:
    take = report["take_all"]
    local = report["local_q80_ridge1000"]
    delta = report["local_vs_take_all"]
    gate = report["development_gate"]
    status = report["status"]
    return f"""# BIN-1D-MA7-ALTA P1 未见时间窗诊断

## 结论

- 状态：`{status} / explore / not promoted / not live-ready`
- Test：`2025-05-31` 至 `2026-08-01`，21 资产 `1,341` 个未见 maturity events。
- `take_all` gate：`{gate["take_all"]["pass"]}`；asset-local model gate：`{gate["local_q80_ridge1000"]["pass"]}`。
- HYPE requests/files/rows/features/train/evaluation：全部为 `0`。

## 主结果

| Policy | Selected | Mean | PF | Compound | MDD | 正资产 | Bootstrap P(mean>0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `take_all` | {take["selected_events"]} | {take["main"]["mean"]:.6%} | {take["main"]["profit_factor"]:.3f} | {take["main"]["compound"]:.2%} | {take["main"]["event_sequence_mdd"]:.2%} | {take["positive_asset_count"]}/21 | {take["cluster_bootstrap"]["positive_probability"]:.2%} |
| `local_q80_ridge1000` | {local["selected_events"]} | {local["main"]["mean"]:.6%} | {local["main"]["profit_factor"]:.3f} | {local["main"]["compound"]:.2%} | {local["main"]["event_sequence_mdd"]:.2%} | {local["positive_asset_count"]}/21 | {local["cluster_bootstrap"]["positive_probability"]:.2%} |

Local policy 相对 `take_all` 的 common-test `P(Δutility>0)` 为
`{delta["positive_probability"]:.2%}`，mean delta
`{delta["mean_delta"]:.6%}/event`。

`take_all` 的 asset×90d bootstrap 95% 区间为
`[{take["cluster_bootstrap"]["quantiles"]["2.5%"]:.4%}, {take["cluster_bootstrap"]["quantiles"]["97.5%"]:.4%}]/event`；
local policy 区间为
`[{local["cluster_bootstrap"]["quantiles"]["2.5%"]:.4%}, {local["cluster_bootstrap"]["quantiles"]["97.5%"]:.4%}]/event`。
Local 相对增量为正只说明减少交易后少亏；自身经济性与 bootstrap 失败时不能解释成
可交易 alpha。表中 compound/MDD 是事件顺序审计，不是并发组合资本曲线。

## Gate

`take_all`：

```json
{json.dumps(gate["take_all"]["checks"], ensure_ascii=False, indent=2)}
```

Asset-local：

```json
{json.dumps(gate["local_q80_ridge1000"]["checks"], ensure_ascii=False, indent=2)}
```

## Lag1 口径

- `take_all` common-event lag1-main：
  `{take["lag1_audit"]["common_mean_lag_minus_main"]:.6%}/event`。
- local common-event lag1-main：
  `{local["lag1_audit"]["common_mean_lag_minus_main"]:.6%}/event`。
- 缺失 lag 的事件单独保留；portfolio comparison 以未执行 lag=`0` 报告，不用
  executable-only 正值过门。

## 终止口径

若 `take_all` 失败，按冻结合同关闭同一 maturity event 定义上的
selector/threshold/model 搜索；local policy 只能作为失败对照。即使两者通过，
也不自动读取或解锁 HYPE。

## 证据

- [合同](../specs/binance-1d-ma7-alta-p0-p1-contract-2026-08-10.md)
- [P0 data quality](../artifacts/p0_data_2026-08-10/p0_data_quality_manifest.json)
- [P0 event capacity](../artifacts/p0_events_2026-08-10/p0_capacity.json)
- [P1 summary](../artifacts/p1_temporal_audit_2026-08-10/p1_summary.json)
- [P1 report](../artifacts/p1_temporal_audit_2026-08-10/p1_report.json)
- [P1 manifest](../artifacts/p1_temporal_audit_2026-08-10/manifest.json)
"""


def main() -> None:
    args = parse_args()
    if args.bootstrap_samples < 1:
        raise ValueError("--bootstrap-samples must be positive")
    capacity = verify_inputs()
    events = pd.read_parquet(EVENT_PATH)
    for column in ("signal_ts", "entry_ts", "exit_ts"):
        events[column] = pd.to_datetime(events[column], utc=True)
    if "HYPE" in set(events["asset"].astype(str)):
        raise RuntimeError("HYPE row entered ALTA events")
    take_oof, local_oof, model_report = build_policies(events)
    take_summary = summarize_policy(
        take_oof, samples=args.bootstrap_samples
    )
    local_summary = summarize_policy(
        local_oof, samples=args.bootstrap_samples
    )
    delta = tfml.delta_bootstrap(
        local_oof,
        take_oof,
        samples=args.bootstrap_samples,
    )
    gate = apply_gate(capacity, take_summary, local_summary, delta)
    if gate["p1_pass"]:
        status = "P1_PASS"
    elif gate["take_all"]["pass"]:
        status = "SUBSTRATE_PASS_MODEL_FAILED"
    else:
        status = "DEVELOPMENT_HARD_GATE_FAILED"
    created_at = datetime.now(UTC)
    report = {
        "schema_version": "binance-1d-ma7-alta-p1-report-v1",
        "created_at_utc": created_at,
        "status": status,
        "contract": "specs/binance-1d-ma7-alta-p0-p1-contract-2026-08-10.md",
        "capacity": capacity,
        "policy_contract": {
            "take_all": "all test maturity events",
            "local_q80_ridge1000": {
                "scope": "asset_local",
                "features": list(tfml.PRICE_FEATURES),
                "target": "z_8bps",
                "alpha": ALPHA,
                "quantile": QUANTILE,
                "route": "combined",
                "inner_selection": "none",
            },
        },
        "model_fit": model_report,
        "take_all": take_summary,
        "local_q80_ridge1000": local_summary,
        "local_vs_take_all": delta,
        "development_gate": gate,
        "hype_rows": 0,
        "hype_files": 0,
        "hype_requests": 0,
    }
    summary = {
        "schema_version": "binance-1d-ma7-alta-p1-summary-v1",
        "created_at_utc": created_at,
        "status": status,
        "test_events": int(len(take_oof)),
        "take_all": take_summary,
        "local_q80_ridge1000": local_summary,
        "local_vs_take_all": delta,
        "development_gate": gate,
        "hype_rows": 0,
        "hype_files": 0,
        "hype_requests": 0,
    }
    print(
        json.dumps(
            json_ready(
                {
                    "status": status,
                    "take_all": {
                        "selected": take_summary["selected_events"],
                        "main": take_summary["main"],
                        "positive_assets": take_summary[
                            "positive_asset_count"
                        ],
                        "bootstrap": take_summary["cluster_bootstrap"],
                    },
                    "local": {
                        "selected": local_summary["selected_events"],
                        "main": local_summary["main"],
                        "positive_assets": local_summary[
                            "positive_asset_count"
                        ],
                        "bootstrap": local_summary["cluster_bootstrap"],
                    },
                    "delta": delta,
                    "gate": gate,
                    "hype_rows": 0,
                    "hype_files": 0,
                    "hype_requests": 0,
                }
            ),
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    if args.no_write:
        return
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_PATH.parent.mkdir(parents=True, exist_ok=True)
    paths = {
        "take_all_oof": OUTPUT_DIR / "p1_take_all_oof.parquet",
        "local_oof": OUTPUT_DIR / "p1_local_q80_ridge1000_oof.parquet",
        "summary": OUTPUT_DIR / "p1_summary.json",
        "report": OUTPUT_DIR / "p1_report.json",
    }
    take_oof.to_parquet(paths["take_all_oof"], index=False)
    local_oof.to_parquet(paths["local_oof"], index=False)
    write_json(paths["summary"], summary)
    write_json(paths["report"], report)
    DIAGNOSTIC_PATH.write_text(
        diagnostic_markdown(report), encoding="utf-8"
    )
    manifest = {
        "schema_version": "binance-1d-ma7-alta-p1-manifest-v1",
        "created_at_utc": created_at,
        "files": {
            key: {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_path(path),
            }
            for key, path in paths.items()
        },
        "diagnostic": {
            "path": str(DIAGNOSTIC_PATH.relative_to(FAMILY_DIR)),
            "bytes": DIAGNOSTIC_PATH.stat().st_size,
            "sha256": sha256_path(DIAGNOSTIC_PATH),
        },
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    write_json(manifest_path, manifest)
    (OUTPUT_DIR / "manifest.sha256").write_text(
        f"{sha256_path(manifest_path)}  {manifest_path.name}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
