from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
FUNDING_ROOT = (
    ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
)
QUARANTINE_ROOT = (
    ROOT
    / "data/raw/_quarantine/binance_usdm_cslgbm_2026-07-17/normalized_funding_rates"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Quarantine malformed legacy funding partitions before rebuilding "
            "the normalized monthly Binance Vision layer."
        )
    )
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def malformed_identity_files() -> list[Path]:
    result = []
    for path in FUNDING_ROOT.glob("date=*/*.parquet"):
        frame = pd.read_parquet(path)
        if "symbol" not in frame.columns or frame["symbol"].isna().any():
            result.append(path)
    return sorted(result)


def nested_hype_files() -> list[Path]:
    return sorted(
        FUNDING_ROOT.glob(
            "symbol=hype_usdt_usdt/date=*/symbol=hype_usdt_usdt.parquet"
        )
    )


def normalized_hype_rows(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        return pd.DataFrame(columns=["ts", "funding_rate"])
    frame = pd.concat((pd.read_parquet(path) for path in paths), ignore_index=True)
    if "symbol" in frame.columns:
        frame = frame.loc[
            frame["symbol"].isna() | frame["symbol"].eq("HYPE/USDT:USDT")
        ]
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.round("s")
    frame["funding_rate"] = pd.to_numeric(frame["funding_rate"], errors="coerce")
    return frame[["ts", "funding_rate"]].dropna().drop_duplicates()


def verify_nested_hype_is_redundant(nested: list[Path]) -> dict[str, int]:
    other_paths = [
        path
        for path in FUNDING_ROOT.glob("**/*.parquet")
        if path not in set(nested)
    ]
    nested_rows = normalized_hype_rows(nested)
    other_hype_paths = []
    for path in other_paths:
        if "hype_usdt_usdt" in str(path):
            other_hype_paths.append(path)
            continue
        if "source=binance_vision_monthly" not in str(path):
            continue
        frame = pd.read_parquet(path, columns=["symbol"])
        if frame["symbol"].eq("HYPE/USDT:USDT").any():
            other_hype_paths.append(path)
    other_rows = normalized_hype_rows(other_hype_paths)
    joined = nested_rows.merge(
        other_rows,
        on="ts",
        how="left",
        suffixes=("_nested", "_other"),
    )
    uncovered = joined["funding_rate_other"].isna()
    conflict = (
        joined["funding_rate_other"].notna()
        & ~joined["funding_rate_nested"].sub(joined["funding_rate_other"]).abs().le(1e-15)
    )
    if uncovered.any() or conflict.any():
        raise RuntimeError(
            "nested HYPE funding is not fully covered by the canonical layer: "
            f"uncovered={int(uncovered.sum())} conflicts={int(conflict.sum())}"
        )
    return {
        "nested_rows": len(nested_rows),
        "uncovered_rows": int(uncovered.sum()),
        "conflicting_rows": int(conflict.sum()),
    }


def quarantine(path: Path) -> dict[str, Any]:
    relative = path.relative_to(FUNDING_ROOT)
    destination = QUARANTINE_ROOT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256(path)
    size = path.stat().st_size
    shutil.move(str(path), str(destination))
    if sha256(destination) != digest:
        raise RuntimeError(f"quarantine hash mismatch: {path}")
    return {
        "source": str(path.relative_to(ROOT)),
        "destination": str(destination.relative_to(ROOT)),
        "sha256": digest,
        "bytes": size,
    }


def main() -> None:
    args = parse_args()
    malformed = malformed_identity_files()
    nested = nested_hype_files()
    nested_check = verify_nested_hype_is_redundant(nested)
    selected = sorted(set(malformed + nested))
    summary: dict[str, Any] = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "malformed_identity_files": len(malformed),
        "redundant_nested_hype_files": len(nested),
        "nested_hype_check": nested_check,
        "selected_files": len(selected),
        "applied": args.apply,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if not args.apply:
        return
    moved = [quarantine(path) for path in selected]
    summary["moved"] = moved
    manifest = ARTIFACT_DIR / "legacy_funding_quarantine_manifest_2026-07-17.json"
    manifest.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"manifest -> {manifest}")


if __name__ == "__main__":
    main()
