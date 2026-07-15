from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

import research_binance_as6s_asset_first_v3 as v3
from as6s_engine import load_funding, load_symbol_frame


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
ARTIFACTS = FAMILY_DIR / "artifacts"
SOURCE = ARTIFACTS / "binance_as6s_asset_first_v3_candidate_2026-07-14.json"
OUTPUT = ARTIFACTS / "binance_as6s_v3_future_oos_freeze_2026-07-14.json"
FUTURE_END = pd.Timestamp("2026-10-14T09:00:00Z")

BASE_FILES_TO_FREEZE = (
    Path(__file__),
    SOURCE,
    ARTIFACTS / "binance_as6s_asset_first_v3_candidate_trades_2026-07-14.csv",
    ARTIFACTS / "binance_as6s_v3_execution_semantics_2026-07-14.json",
    ARTIFACTS / "binance_as6s_v3_funding_boundary_2026-07-14.json",
    ARTIFACTS / "binance_as6s_prefit_frontier_asset_first_2026-07-14.json",
    Path(__file__).with_name("research_binance_as6s_asset_first_v3.py"),
    Path(__file__).with_name("audit_binance_as6s_clean_rsi_hf_robustness.py"),
    Path(__file__).with_name("audit_binance_as6s_v3_execution_semantics.py"),
    Path(__file__).with_name("audit_binance_as6s_v3_funding_boundary.py"),
    Path(__file__).with_name("audit_legacy_asset_specific_1h_sleeves.py"),
    Path(__file__).with_name("as6s_engine.py"),
    Path(__file__).with_name("combine_hybrid_asset_specific_account.py"),
    Path(__file__).with_name("research_binance_as6s_clean_rsi_hf_search.py"),
    Path(__file__).with_name("research_binance_as6s_per_asset_hf_discovery.py"),
    Path(__file__).with_name("research_binance_as6s_per_asset_hf_filter_tune.py"),
    Path(__file__).with_name("verify_binance_as6s_v3_freeze.py"),
    Path(__file__).with_name("reveal_binance_as6s_v3_future_oos.py"),
    ROOT
    / "research/hype/15m-multi-indicator-intraday/scripts/research_hype_15m_mii_search.py",
    ROOT
    / "research/hype/15m-multi-indicator-intraday/scripts/research_hype_15m_mii_clean_evolution.py",
    ROOT
    / "research/hype/15m-multi-indicator-intraday/scripts/research_hype_15m_mii_v1_full_ablation.py",
    ROOT
    / "research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v2_micro_tune_2026-07-07.json",
)
LEGACY_DEPENDENCY_DIRS = tuple(
    ROOT / f"research/{asset}/1h-adaptive-regime/scripts"
    for asset in ("trx", "sol", "hype", "eth", "btc", "bnb")
) + (ROOT / "research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts",)


def files_to_freeze() -> tuple[Path, ...]:
    dependencies = [
        path
        for directory in LEGACY_DEPENDENCY_DIRS
        for path in directory.glob("*.py")
    ]
    return tuple(sorted(set((*BASE_FILES_TO_FREEZE, *dependencies))))

OHLCV_COLUMNS = (
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
)
FUNDING_COLUMNS = ("ts", "funding_rate", "mark_price", "source")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def logical_frame_digest(frame: pd.DataFrame, columns: tuple[str, ...]) -> str:
    selected = frame.loc[:, list(columns)].copy()
    digest = hashlib.sha256()
    digest.update("\x1f".join(columns).encode())
    digest.update("\x1f".join(map(str, selected.dtypes)).encode())
    digest.update(pd.util.hash_pandas_object(selected, index=False).values.tobytes())
    return digest.hexdigest()


def data_snapshot() -> dict[str, Any]:
    output: dict[str, Any] = {}
    for symbol in v3.SYMBOLS:
        ohlcv = load_symbol_frame(symbol, end=v3.REUSED_END)
        funding = load_funding(symbol, end=v3.REUSED_END)
        output[symbol] = {
            "ohlcv_rows": len(ohlcv),
            "ohlcv_start": ohlcv["ts"].iloc[0].isoformat(),
            "ohlcv_end": ohlcv["ts"].iloc[-1].isoformat(),
            "ohlcv_logical_sha256": logical_frame_digest(ohlcv, OHLCV_COLUMNS),
            "funding_rows": len(funding),
            "funding_start": funding["ts"].iloc[0].isoformat(),
            "funding_end": funding["ts"].iloc[-1].isoformat(),
            "funding_logical_sha256": logical_frame_digest(
                funding, FUNDING_COLUMNS
            ),
        }
    return output


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        gate = source["diagnostic_gates"][mode]
        if not gate["current_diagnostic_pass"]:
            raise RuntimeError(f"cannot freeze failing route: {mode}")
        if gate["final_future_oos_pass"] is not None:
            raise RuntimeError(f"future OOS already populated unexpectedly: {mode}")
    semantics = json.loads(
        (ARTIFACTS / "binance_as6s_v3_execution_semantics_2026-07-14.json").read_text(
            encoding="utf-8"
        )
    )
    funding_boundary = json.loads(
        (ARTIFACTS / "binance_as6s_v3_funding_boundary_2026-07-14.json").read_text(
            encoding="utf-8"
        )
    )
    if semantics["result"] != "PASS" or funding_boundary["result"] != "PASS":
        raise RuntimeError("execution audit must pass before freeze")

    frozen_files = files_to_freeze()
    missing = [str(path) for path in frozen_files if not path.exists()]
    if missing:
        raise FileNotFoundError(f"freeze inputs missing: {missing}")
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-15M-Asset-Specific-Six-Strategy-Selector",
        "candidate": "BIN-15M-AS6S-V3-observation",
        "status": "frozen_observation_not_registered_not_promoted_not_live_ready",
        "selection_end_exclusive": v3.REUSED_END.isoformat(),
        "future_oos": {
            "start_inclusive": v3.REUSED_END.isoformat(),
            "end_exclusive": FUTURE_END.isoformat(),
            "reveal_policy": (
                "one-shot only after the complete window is available; no parameter, "
                "sleeve, route, exposure, score, or execution change before reveal"
            ),
        },
        "selected_sleeves": source["selected_sleeves"],
        "routes": {
            mode: source["comparisons"][mode]["frozen_params"]
            for mode in ("nonpreemptive", "strong_breakout_preemptive")
        },
        "sleeve_configs": {
            sleeve: source["sleeve_audit"][sleeve]
            for sleeve in source["selected_sleeves"]
        },
        "current_diagnostic_gates": source["diagnostic_gates"],
        "frozen_files": {
            str(path.relative_to(ROOT)): sha256_file(path)
            for path in frozen_files
        },
        "data_snapshot_through_selection_end": data_snapshot(),
        "prohibited_before_reveal": (
            "parameter tuning, sleeve replacement, threshold changes, exposure changes, "
            "account-scale changes, route changes, data-history rewrites, and partial "
            "future-window inspection"
        ),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "selected_sleeves": len(payload["selected_sleeves"]),
                "files_frozen": len(payload["frozen_files"]),
                "symbols_snapshotted": len(payload["data_snapshot_through_selection_end"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
