from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
FUNDING_ROOT = (
    ROOT / "data/normalized/funding_rates/exchange=binance/market_type=perp"
)
QUARANTINE_ROOT = ROOT / (
    "data/raw/_quarantine/binance_1h_mhcsml_2026-07-18/"
    "redundant_normalized_hype_funding"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Quarantine only fully redundant nested HYPE funding files."
    )
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_rows(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=["ts", "funding_rate"])
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.round("s")
    frame["funding_rate"] = pd.to_numeric(frame["funding_rate"], errors="coerce")
    return frame.dropna().drop_duplicates(["ts", "funding_rate"])


def canonical_hype_rows(nested: set[Path]) -> pd.DataFrame:
    paths = []
    for path in FUNDING_ROOT.glob("**/*.parquet"):
        if path in nested:
            continue
        if "hype_usdt_usdt" in path.name:
            paths.append(path)
            continue
        if "source=binance_vision_monthly" not in str(path):
            continue
        symbols = pd.read_parquet(path, columns=["symbol"])["symbol"]
        if symbols.eq("HYPE/USDT:USDT").any():
            paths.append(path)
    frames = []
    for path in paths:
        frame = pd.read_parquet(path)
        if "symbol" in frame.columns:
            frame = frame.loc[frame["symbol"].eq("HYPE/USDT:USDT")]
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.round("s")
        frame["funding_rate"] = pd.to_numeric(frame["funding_rate"], errors="coerce")
        frames.append(frame[["ts", "funding_rate"]].dropna())
    if not frames:
        return pd.DataFrame(columns=["ts", "funding_rate"])
    return pd.concat(frames, ignore_index=True).drop_duplicates(
        ["ts", "funding_rate"]
    )


def classify_file(path: Path, canonical: pd.DataFrame) -> dict[str, Any]:
    rows = normalized_rows(path)
    joined = rows.merge(
        canonical,
        on="ts",
        how="left",
        suffixes=("_nested", "_canonical"),
    )
    covered = joined["funding_rate_canonical"].notna()
    equal = covered & joined["funding_rate_nested"].sub(
        joined["funding_rate_canonical"]
    ).abs().le(1e-15)
    conflict = covered & ~equal
    return {
        "path": str(path.relative_to(ROOT)),
        "rows": len(rows),
        "covered_rows": int(equal.sum()),
        "uncovered_rows": int((~covered).sum()),
        "conflicting_rows": int(conflict.sum()),
        "fully_redundant": bool(len(rows) > 0 and equal.all()),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def keep_uncovered_rows(path: Path, canonical: pd.DataFrame) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    keys = pd.DataFrame(
        {
            "ts": pd.to_datetime(frame["ts"], utc=True).dt.round("s"),
            "funding_rate": pd.to_numeric(frame["funding_rate"], errors="coerce"),
        },
        index=frame.index,
    )
    canonical_keys = pd.MultiIndex.from_frame(canonical[["ts", "funding_rate"]])
    row_keys = pd.MultiIndex.from_frame(keys[["ts", "funding_rate"]])
    return frame.loc[~row_keys.isin(canonical_keys)].copy()


def main() -> None:
    args = parse_args()
    nested_paths = sorted(
        FUNDING_ROOT.glob(
            "symbol=hype_usdt_usdt/date=*/symbol=hype_usdt_usdt.parquet"
        )
    )
    nested_set = set(nested_paths)
    canonical = canonical_hype_rows(nested_set)
    files = [classify_file(path, canonical) for path in nested_paths]
    selected = [item for item in files if item["fully_redundant"]]
    retained = [item for item in files if not item["fully_redundant"]]
    if any(item["conflicting_rows"] for item in files):
        raise RuntimeError("conflicting HYPE funding rows require manual review")
    report: dict[str, Any] = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "nested_files": len(files),
        "fully_redundant_files": len(selected),
        "retained_files": len(retained),
        "redundant_rows": int(sum(item["rows"] for item in selected)),
        "retained_uncovered_rows": int(
            sum(item["uncovered_rows"] for item in retained)
        ),
        "applied": args.apply,
        "selected": selected,
        "retained": retained,
    }
    print(
        json.dumps(
            {key: value for key, value in report.items() if key not in {"selected", "retained"}},
            indent=2,
            ensure_ascii=False,
        )
    )
    if args.apply:
        moved = []
        for item in selected:
            source = ROOT / str(item["path"])
            destination = QUARANTINE_ROOT / source.relative_to(FUNDING_ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            if sha256(destination) != item["sha256"]:
                raise RuntimeError(f"quarantine hash mismatch: {source}")
            moved.append(
                {
                    "source": item["path"],
                    "destination": str(destination.relative_to(ROOT)),
                    "sha256": item["sha256"],
                    "bytes": item["bytes"],
                }
            )
        filtered = []
        mixed = [
            item
            for item in retained
            if item["covered_rows"] > 0 and item["uncovered_rows"] > 0
        ]
        for item in mixed:
            source = ROOT / str(item["path"])
            retained_frame = keep_uncovered_rows(source, canonical)
            destination = QUARANTINE_ROOT / source.relative_to(FUNDING_ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            if sha256(destination) != item["sha256"]:
                raise RuntimeError(f"quarantine hash mismatch: {source}")
            source.parent.mkdir(parents=True, exist_ok=True)
            temporary = source.with_suffix(f"{source.suffix}.tmp")
            retained_frame.to_parquet(
                temporary, index=False, compression="zstd"
            )
            os.replace(temporary, source)
            filtered.append(
                {
                    "source": item["path"],
                    "quarantined_original": str(destination.relative_to(ROOT)),
                    "original_sha256": item["sha256"],
                    "original_rows": item["rows"],
                    "retained_rows": len(retained_frame),
                    "rewritten_sha256": sha256(source),
                }
            )
        report["moved"] = moved
        report["filtered_mixed_files"] = filtered
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    output = ARTIFACT_DIR / "redundant_hype_funding_quarantine_manifest.json"
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"manifest -> {output}")


if __name__ == "__main__":
    main()
