from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-taker-flow-meta-label"
BASE_SCRIPT = FAMILY_DIR / "scripts/research_binance_1d_ma7_tfml_p1.py"
EVENT_DIR = FAMILY_DIR / "artifacts/p0e_events_2026-08-10"
EVENT_PATH = EVENT_DIR / "p0e_events.parquet"
EVENT_CAPACITY_PATH = EVENT_DIR / "p0e_event_capacity.json"
LEGACY_FLOW_DIR = FAMILY_DIR / "artifacts/p0_data_2026-08-10"
FRESH_FLOW_DIR = FAMILY_DIR / "artifacts/p0e_data_2026-08-10"
PRICE_QUALITY_PATH = FAMILY_DIR / (
    "artifacts/p0e_price_data_2026-08-10/"
    "p0_data_quality_manifest.json"
)
PRICE_SYNC_SCRIPT = FAMILY_DIR / "scripts/sync_binance_tfml_p0e_price_funding.py"
PRICE_BASE_SCRIPT = ROOT / (
    "research/asset-portfolios/1d-ma7-rsi6-direction-aligned-pooled-ml/"
    "scripts/sync_binance_pooled_p0_data.py"
)
OUTPUT_DIR = FAMILY_DIR / "artifacts/p1e_development_2026-08-10"
LEGACY_ASSETS = ("BTC", "ETH", "BNB", "SOL", "TRX")
FRESH_ASSETS = ("XRP", "DOGE", "ADA", "LINK", "LTC", "DOT", "AVAX", "UNI")
ALL_ASSETS = (*LEGACY_ASSETS, *FRESH_ASSETS)
ASSET_SLUGS = {asset: f"{asset.lower()}usdt" for asset in ALL_ASSETS}
END_EXCLUSIVE = pd.Timestamp("2025-05-31T00:00:00Z")


def load_base_module():
    spec = importlib.util.spec_from_file_location(
        "binance_1d_ma7_tfml_p1e_base",
        BASE_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise ImportError(BASE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--bootstrap-samples", type=int, default=5_000)
    parser.add_argument("--capacity-only", action="store_true")
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
        json.dumps(json_ready(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def verify_file_manifest(
    directory: Path,
    *,
    expected_schema: str,
    required_files: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != expected_schema:
        raise RuntimeError(f"Manifest schema mismatch: {manifest_path}")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != required_files:
        raise RuntimeError(f"Manifest file identity mismatch: {manifest_path}")
    for details in files.values():
        if not isinstance(details, dict) or not {
            "path",
            "sha256",
        }.issubset(details):
            raise RuntimeError(f"Malformed manifest entry: {manifest_path}")
        relative = Path(details["path"])
        if not relative.parts or ".." in relative.parts:
            raise RuntimeError(f"Unsafe manifest path: {relative}")
        path = (
            ROOT / relative
            if relative.parts[0] == "data"
            else directory / relative
        )
        try:
            path.resolve().relative_to(ROOT)
        except ValueError as error:
            raise RuntimeError(f"Manifest path escaped repository: {path}") from error
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_path(path)
        if actual != details["sha256"]:
            raise RuntimeError(f"Manifest mismatch: {path}")
        if "bytes" in details and int(details["bytes"]) != path.stat().st_size:
            raise RuntimeError(f"Manifest size mismatch: {path}")
        if "hype" in str(path).lower():
            raise RuntimeError(f"Forbidden HYPE path: {path}")
    return manifest, {
        "manifest_path": str(manifest_path.relative_to(ROOT)),
        "manifest_sha256": sha256_path(manifest_path),
        "schema_version": manifest["schema_version"],
        "file_count": len(files),
    }


def verify_event_manifest() -> dict[str, Any]:
    _, audit = verify_file_manifest(
        EVENT_DIR,
        expected_schema="binance-1d-ma7-tfml-p0e-event-manifest-v1",
        required_files={"events", "capacity"},
    )
    capacity = json.loads(EVENT_CAPACITY_PATH.read_text(encoding="utf-8"))
    if (
        capacity.get("schema_version")
        != "binance-1d-ma7-tfml-p0e-events-v1"
        or pd.Timestamp(capacity.get("development_end_exclusive"))
        != END_EXCLUSIVE
        or tuple(capacity.get("legacy_assets", [])) != LEGACY_ASSETS
        or tuple(capacity.get("fresh_assets", [])) != FRESH_ASSETS
        or tuple(capacity.get("all_assets", [])) != ALL_ASSETS
        or not capacity.get("p0e_event_capacity_pass")
        or any(
            int(capacity.get(key, -1)) != 0
            for key in ("hype_rows", "hype_files", "hype_requests")
        )
    ):
        raise RuntimeError("P0E event identity or HYPE lock mismatch")
    return audit


def verify_flow_manifest(
    directory: Path,
    *,
    expected_assets: tuple[str, ...],
    expected_archives: int,
    expected_bytes: int,
) -> dict[str, Any]:
    required = {
        "source_manifest",
        "data_quality",
        *(f"{asset.lower()}_flow_cache" for asset in expected_assets),
    }
    _, audit = verify_file_manifest(
        directory,
        expected_schema="binance-1d-ma7-tfml-p0-manifest-v1",
        required_files=required,
    )
    source = json.loads(
        (directory / "p0_source_manifest.json").read_text(encoding="utf-8")
    )
    quality = json.loads(
        (directory / "p0_data_quality.json").read_text(encoding="utf-8")
    )
    archives = source.get("archives")
    if (
        source.get("schema_version") != "binance-1d-ma7-tfml-source-v1"
        or source.get("source") != "Binance Vision public S3"
        or int(source.get("archive_count", -1)) != expected_archives
        or int(source.get("compressed_bytes", -1)) != expected_bytes
        or pd.Timestamp(source.get("development_end_exclusive"))
        != END_EXCLUSIVE
        or int(source.get("hype_requests_sent", -1)) != 0
        or not isinstance(archives, list)
        or len(archives) != expected_archives
        or {str(row.get("asset")) for row in archives}
        != set(expected_assets)
        or any("hype" in json.dumps(row).lower() for row in archives)
    ):
        raise RuntimeError(f"Flow source identity mismatch: {directory}")
    expected_symbols = {asset: f"{asset}USDT" for asset in expected_assets}
    archive_keys: set[str] = set()
    for row in archives:
        if not isinstance(row, dict):
            raise RuntimeError(f"Malformed flow source row: {directory}")
        asset = str(row.get("asset"))
        raw_path = ROOT / str(row.get("raw_path"))
        key = str(row.get("key"))
        if (
            expected_symbols.get(asset) != row.get("symbol")
            or not key.startswith(
                f"data/futures/um/monthly/klines/{expected_symbols.get(asset)}/5m/"
            )
            or key in archive_keys
            or "hype" in str(raw_path).lower()
            or not raw_path.is_file()
            or raw_path.stat().st_size != int(row.get("size", -1))
            or sha256_path(raw_path) != row.get("sha256")
        ):
            raise RuntimeError(f"Flow archive identity mismatch: {raw_path}")
        archive_keys.add(key)
    if (
        quality.get("schema_version") != "binance-1d-ma7-tfml-quality-v1"
        or int(quality.get("archive_count", -1)) != expected_archives
        or set(quality.get("assets", {})) != set(expected_assets)
        or any(
            int(quality.get(key, -1)) != 0
            for key in (
                "hype_rows_consumed",
                "hype_files_opened",
                "hype_requests_sent",
            )
        )
    ):
        raise RuntimeError(f"Flow quality identity mismatch: {directory}")
    audit["archive_count"] = expected_archives
    audit["compressed_bytes"] = expected_bytes
    return audit


def verify_price_quality() -> dict[str, Any]:
    payload = json.loads(PRICE_QUALITY_PATH.read_text(encoding="utf-8"))
    expected_symbols = [f"{asset}USDT" for asset in FRESH_ASSETS]
    provenance = payload.get("provenance", {})
    feature_files = payload.get("feature_files")
    if (
        payload.get("schema_version")
        != "binance-1d-ma7-tfml-p0e-price-v1"
        or payload.get("family") != "BIN-1D-MA7-TFML-P0E"
        or payload.get("contract")
        != (
            "specs/binance-1d-ma7-tfml-p0e-p1e-"
            "universe-expansion-contract-2026-08-10.md"
        )
        or pd.Timestamp(payload.get("cutoff_exclusive")) != END_EXCLUSIVE
        or payload.get("symbols") != expected_symbols
        or int(payload.get("blocker_count", -1)) != 0
        or any(
            int(payload.get(key, -1)) != 0
            for key in (
                "hype_rows_consumed",
                "hype_files_opened",
                "hype_requests_sent",
            )
        )
        or provenance.get("wrapper_sha256") != sha256_path(PRICE_SYNC_SCRIPT)
        or provenance.get("retained_base_sha256")
        != sha256_path(PRICE_BASE_SCRIPT)
        or provenance.get("embedded_generator_sha256")
        != [sha256_path(PRICE_BASE_SCRIPT)]
        or provenance.get("generator_source_retained") is not True
        or not isinstance(feature_files, dict)
        or set(feature_files) != set(expected_symbols)
    ):
        raise RuntimeError("P0E price/funding source identity mismatch")
    for symbol, entries in feature_files.items():
        if not isinstance(entries, dict) or set(entries) != {
            "hourly",
            "daily",
            "funding",
        }:
            raise RuntimeError(f"P0E feature manifest incomplete: {symbol}")
        for details in entries.values():
            path = ROOT / str(details["path"])
            if (
                not path.is_file()
                or "hype" in str(path).lower()
                or path.stat().st_size != int(details["bytes"])
                or sha256_path(path) != details["sha256"]
                or details.get("embedded_generator_sha256")
                != [sha256_path(PRICE_BASE_SCRIPT)]
            ):
                raise RuntimeError(f"P0E feature identity mismatch: {path}")
    return {
        "path": str(PRICE_QUALITY_PATH.relative_to(ROOT)),
        "sha256": sha256_path(PRICE_QUALITY_PATH),
        "blocker_count": 0,
    }


def capacity_summary(
    base,
    events: pd.DataFrame,
    panel: pd.DataFrame,
    *,
    event_identity: str,
    rejection_counts: dict[str, int],
    source_audit: dict[str, Any],
    event_capacity: dict[str, Any],
) -> dict[str, Any]:
    fresh_events = events.loc[events["asset"].isin(FRESH_ASSETS)]
    fresh_panel = panel.loc[panel["asset"].isin(FRESH_ASSETS)]
    per_asset = {
        asset: int(fresh_panel["asset"].eq(asset).sum())
        for asset in FRESH_ASSETS
    }
    sides = {
        "long": int(fresh_panel["side"].gt(0).sum()),
        "short": int(fresh_panel["side"].lt(0).sum()),
    }
    checks = {
        "fresh_raw_event_capacity": bool(
            event_capacity["p0e_event_capacity_pass"]
            and len(fresh_events) >= 1_600
        ),
        "fresh_accepted_total": len(fresh_panel) >= 1_500,
        "fresh_accepted_per_asset": all(
            count >= 170 for count in per_asset.values()
        ),
        "fresh_usable_rate": len(fresh_panel) / len(fresh_events) >= 0.90,
        "fresh_direction_capacity": min(sides.values()) >= 650,
        "exact_windows_and_market_peers": bool(
            not panel.empty and panel["market_peer_count"].ge(8).all()
        ),
        "source_manifests_verified": len(source_audit) == 4,
        "hype_lock": True,
    }
    return {
        "schema_version": "binance-1d-ma7-tfml-p0e-v1",
        "generated_at_utc": datetime.now(UTC),
        "input_events_all": int(len(events)),
        "input_events_fresh": int(len(fresh_events)),
        "accepted_events_all": int(len(panel)),
        "accepted_events_fresh": int(len(fresh_panel)),
        "fresh_usable_rate": float(len(fresh_panel) / len(fresh_events)),
        "fresh_per_asset": per_asset,
        "fresh_side_counts": sides,
        "rejection_counts": rejection_counts,
        "event_identity_sha256": event_identity,
        "accepted_panel_identity_sha256": base.frame_identity_sha256(panel),
        "source_audit": source_audit,
        "checks": checks,
        "p0e_capacity_pass": bool(all(checks.values())),
        "hype_rows": 0,
        "hype_files": 0,
        "hype_requests": 0,
    }


def enforce_fold_local_aggregate_pipeline() -> None:
    raise RuntimeError(
        "TFML P1E is fail-closed: the historical implementation built price "
        "and flow market aggregates on the global 13-asset panel before outer "
        "and inner held-asset exclusion. That violates the frozen fresh-holdout "
        "contract, so the exposed P1E result is invalidated and must not be "
        "regenerated or interpreted as OOS. A future test requires a new "
        "holdout and aggregates rebuilt inside every fold."
    )


def apply_gate(
    *,
    capacity: dict[str, Any],
    full: dict[str, Any],
    delta: dict[str, Any],
    importance: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sides = full["side_counts"]
    combined_chosen = any(
        "route=combined" in key and count > 0
        for key, count in full["choice_frequency"].items()
    )
    direction_coverage = (
        min(sides.values()) >= 50
        if combined_chosen
        else max(sides.values()) >= 50
    )
    positive_importance = [
        feature
        for feature, values in importance.items()
        if int(values["folds"]) >= 24
        and values["median"] is not None
        and float(values["median"]) > 0.0
    ]
    variants = full["variants"]
    checks = {
        "p0e_capacity": bool(capacity["p0e_capacity_pass"]),
        "accepted_total_and_per_asset": bool(
            int(full["selected_events"]) >= 160
            and all(
                int(full["per_asset"][asset]["selected"]["events"]) >= 15
                for asset in FRESH_ASSETS
            )
        ),
        "direction_coverage": bool(direction_coverage),
        "time_block_coverage": int(full["selected_90d_blocks"]) >= 24,
        "main_economics": bool(
            float(full["main"]["mean"]) > 0.0
            and float(full["main"]["profit_factor"]) >= 1.15
        ),
        "positive_assets": int(full["positive_asset_count"]) >= 6,
        "positive_outer_folds": int(full["positive_outer_fold_count"]) >= 24,
        "ranking": bool(
            math.isfinite(float(full["ranking_spearman"]))
            and float(full["ranking_spearman"]) > 0.03
            and int(full["positive_ranking_asset_count"]) >= 6
        ),
        "cluster_bootstrap": float(
            full["cluster_bootstrap"]["positive_probability"]
        )
        >= 0.90,
        "full_over_price_control": float(delta["positive_probability"]) >= 0.90,
        "flow_permutation_importance": len(positive_importance) >= 2,
        "stress_variants": bool(
            all(
                float(variants[column]["mean"]) > 0.0
                and float(variants[column]["profit_factor"]) >= 1.05
                for column in ("z_4bps", "z_funding_off", "z_lag1")
            )
            and float(full["lag_executable_rate"]) >= 0.75
        ),
        "per_asset_dual_improvement": int(full["dual_improved_asset_count"]) >= 5,
        "hype_lock": True,
    }
    return {
        "checks": checks,
        "positive_flow_importance_features": positive_importance,
        "development_gate_pass": bool(all(checks.values())),
    }


def write_outputs(
    *,
    panel: pd.DataFrame,
    capacity: dict[str, Any],
    oof_by_route: dict[str, pd.DataFrame],
    summary: dict[str, Any],
    report: dict[str, Any],
    frozen: dict[str, Any] | None,
) -> dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "accepted_events": OUTPUT_DIR / "p0e_accepted_events.parquet",
        "capacity": OUTPUT_DIR / "p0e_capacity.json",
        "full_oof": OUTPUT_DIR / "p1e_price_plus_flow_oof.parquet",
        "control_oof": OUTPUT_DIR / "p1e_price_utility_control_oof.parquet",
        "flow_oof": OUTPUT_DIR / "p1e_flow_only_oof.parquet",
        "summary": OUTPUT_DIR / "p1e_summary.json",
        "report": OUTPUT_DIR / "p1e_report.json",
    }
    panel.to_parquet(paths["accepted_events"], index=False)
    oof_by_route["price_plus_flow"].to_parquet(paths["full_oof"], index=False)
    oof_by_route["price_utility_control"].to_parquet(
        paths["control_oof"], index=False
    )
    oof_by_route["flow_only"].to_parquet(paths["flow_oof"], index=False)
    write_json(paths["capacity"], capacity)
    write_json(paths["summary"], summary)
    write_json(paths["report"], report)
    if frozen is not None:
        paths["frozen_model"] = OUTPUT_DIR / "p1e_frozen_model.json"
        write_json(paths["frozen_model"], frozen)
    files = {
        name: {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_path(path),
        }
        for name, path in paths.items()
    }
    manifest = {
        "schema_version": "binance-1d-ma7-tfml-p1e-manifest-v1",
        "created_at_utc": datetime.now(UTC),
        "files": files,
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    write_json(manifest_path, manifest)
    (OUTPUT_DIR / "manifest.sha256").write_text(
        f"{sha256_path(manifest_path)}  {manifest_path.name}\n",
        encoding="utf-8",
    )
    return {
        **{name: details["sha256"] for name, details in files.items()},
        "manifest": sha256_path(manifest_path),
    }


def main() -> None:
    args = parse_args()
    if args.max_workers < 1 or args.max_workers > 20:
        raise ValueError("--max-workers must be in [1, 20]")
    if args.bootstrap_samples < 100:
        raise ValueError("--bootstrap-samples must be >=100")
    if "HYPE" in ALL_ASSETS:
        raise RuntimeError("HYPE data is forbidden")
    source_audit = {
        "events": verify_event_manifest(),
        "legacy_flow": verify_flow_manifest(
            LEGACY_FLOW_DIR,
            expected_assets=LEGACY_ASSETS,
            expected_archives=316,
            expected_bytes=116_012_918,
        ),
        "fresh_flow": verify_flow_manifest(
            FRESH_FLOW_DIR,
            expected_assets=FRESH_ASSETS,
            expected_archives=491,
            expected_bytes=169_255_752,
        ),
        "fresh_price_funding": verify_price_quality(),
    }
    event_capacity = json.loads(
        EVENT_CAPACITY_PATH.read_text(encoding="utf-8")
    )
    base = load_base_module()
    base.ASSETS = ALL_ASSETS
    base.ASSET_SLUGS = ASSET_SLUGS
    events = pd.read_parquet(EVENT_PATH)
    for column in ("cross_ts", "signal_ts", "entry_ts", "exit_ts"):
        events[column] = pd.to_datetime(events[column], utc=True)
    if set(events["asset"].astype(str)) != set(ALL_ASSETS):
        raise RuntimeError("Expanded event universe changed")
    if events["signal_ts"].ge(END_EXCLUSIVE).any():
        raise RuntimeError("Post-boundary event entered P1E")
    event_identity = base.event_identity_sha256(events)
    if event_identity != event_capacity["event_identity_sha256"]:
        raise RuntimeError("Expanded event identity changed")
    caches = {asset: base.load_flow_cache(asset) for asset in ALL_ASSETS}
    panel, rejection_counts = base.build_accepted_panel(events, caches)
    peer_rejections = int(panel["market_peer_count"].lt(8).sum())
    if peer_rejections:
        panel = panel.loc[panel["market_peer_count"].ge(8)].reset_index(drop=True)
        rejection_counts["market_peers_lt8"] = peer_rejections
    capacity = capacity_summary(
        base,
        events,
        panel,
        event_identity=event_identity,
        rejection_counts=rejection_counts,
        source_audit=source_audit,
        event_capacity=event_capacity,
    )
    if not args.no_write:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        panel.to_parquet(OUTPUT_DIR / "p0e_accepted_events.parquet", index=False)
        write_json(OUTPUT_DIR / "p0e_capacity.json", capacity)
    print("P0E_CAPACITY " + json.dumps(json_ready(capacity), ensure_ascii=False))
    if args.capacity_only:
        return
    if not capacity["p0e_capacity_pass"]:
        raise RuntimeError("P0E capacity failed; P1E is forbidden")
    enforce_fold_local_aggregate_pipeline()

    base.ASSETS = FRESH_ASSETS
    base.EVENT_IDENTITY = event_identity
    oof_by_route: dict[str, pd.DataFrame] = {}
    reports_by_route: dict[str, list[dict[str, Any]]] = {}
    summaries_by_route: dict[str, dict[str, Any]] = {}
    for model_route, features in base.MODEL_FEATURES.items():
        oof, reports = base.run_outer_oof(
            panel,
            model_route=model_route,
            features=features,
            max_workers=args.max_workers,
        )
        oof_by_route[model_route] = oof
        reports_by_route[model_route] = reports
        summaries_by_route[model_route] = base.summarize_model_route(
            oof,
            reports,
            samples=args.bootstrap_samples,
        )
    delta = base.delta_bootstrap(
        oof_by_route["price_plus_flow"],
        oof_by_route["price_utility_control"],
        samples=args.bootstrap_samples,
    )
    importance = base.importance_summary(
        reports_by_route["price_plus_flow"]
    )
    gate = apply_gate(
        capacity=capacity,
        full=summaries_by_route["price_plus_flow"],
        delta=delta,
        importance=importance,
    )
    status = (
        "DEVELOPMENT_GATE_PASSED"
        if gate["development_gate_pass"]
        else "DEVELOPMENT_HARD_GATE_FAILED"
    )
    summary = {
        "schema_version": "binance-1d-ma7-tfml-p1e-summary-v1",
        "created_at_utc": datetime.now(UTC),
        "status": status,
        "capacity": capacity,
        "routes": summaries_by_route,
        "full_vs_price_control": delta,
        "flow_permutation_importance": importance,
        "development_gate": gate,
        "hype_rows": 0,
        "hype_files": 0,
        "hype_requests": 0,
    }
    report = {
        **summary,
        "contract": {
            "legacy_training_assets": list(LEGACY_ASSETS),
            "fresh_outer_assets": list(FRESH_ASSETS),
            "all_training_assets": list(ALL_ASSETS),
            "event_identity_sha256": event_identity,
            "development_end_exclusive": END_EXCLUSIVE,
            "target": "z_8bps",
            "price_features": list(base.PRICE_FEATURES),
            "flow_features": list(base.FLOW_FEATURES),
            "full_features": list(base.FULL_FEATURES),
            "model_grid": {
                "alpha": list(base.ALPHA_GRID),
                "thresholds": list(base.THRESHOLD_GRID),
                "routes": list(base.ROUTES),
            },
            "permutation_repeats": base.PERMUTATION_REPEATS,
            "bootstrap_samples": args.bootstrap_samples,
        },
        "outer_fold_reports": reports_by_route,
    }
    frozen = None
    if gate["development_gate_pass"]:
        frozen = base.frozen_model_state(
            panel,
            reports_by_route["price_plus_flow"],
            panel_identity=str(capacity["accepted_panel_identity_sha256"]),
        )
        frozen.update(
            {
                "schema_version": "binance-1d-ma7-tfml-p1e-model-v1",
                "assets": list(ALL_ASSETS),
                "fresh_outer_assets": list(FRESH_ASSETS),
                "event_identity_sha256": event_identity,
            }
        )
    hashes: dict[str, str] = {}
    if not args.no_write:
        hashes = write_outputs(
            panel=panel,
            capacity=capacity,
            oof_by_route=oof_by_route,
            summary=summary,
            report=report,
            frozen=frozen,
        )
    print(
        json.dumps(
            json_ready(
                {
                    "status": status,
                    "development_gate": gate,
                    "artifact_sha256": hashes,
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
