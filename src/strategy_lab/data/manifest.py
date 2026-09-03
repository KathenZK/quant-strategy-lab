from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import hashlib
import json

from strategy_lab.data.fs import atomic_write_text

LINEAGE_INCOMPLETE = "LINEAGE_INCOMPLETE"
CACHE_META_FILENAME = ".cache-meta.json"
DATASET_MANIFEST_FILENAME = "_MANIFEST.json"
INPUT_SNAPSHOT_FILENAME = "_INPUT_SNAPSHOT.json"
CACHE_META_SCHEMA_VERSION = "1.0"
DATASET_MANIFEST_SCHEMA_VERSION = "1.0"
ACCEPTED_DERIVED_QUALITY = {"TRUSTED_DERIVED", "ACCEPTED", "PASS", "TRUSTED"}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode(
        "utf-8"
    )


def sha256_canonical(payload: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(payload))


def write_canonical_json(path: Path, payload: dict[str, Any]) -> Path:
    encoded = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    if not encoded.endswith("\n"):
        encoded += "\n"
    return atomic_write_text(path, encoded, encoding="utf-8")


def parquet_file_stats(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.parquet")):
        if not path.is_file():
            continue
        stat = path.stat()
        rows.append(
            {
                "relpath": path.relative_to(root).as_posix(),
                "size": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
            }
        )
    return rows


def inventory_signature(rows: list[dict[str, Any]]) -> str:
    return sha256_canonical(
        {
            "files": [
                {
                    "relpath": row["relpath"],
                    "size": int(row["size"]),
                    "mtime_ns": int(row["mtime_ns"]),
                }
                for row in rows
            ]
        }
    )


def parquet_inventory(root: Path, *, compute_hashes: bool = True) -> list[dict[str, Any]]:
    if not compute_hashes:
        return parquet_file_stats(root)
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.parquet")):
        if not path.is_file():
            continue
        stat = path.stat()
        rows.append(
            {
                "relpath": path.relative_to(root).as_posix(),
                "size": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
                "sha256": sha256_file(path),
            }
        )
    return rows


def inventory_fingerprint(rows: list[dict[str, Any]]) -> str:
    return sha256_canonical(
        {
            "files": [
                {"relpath": row["relpath"], "size": row["size"], "sha256": row["sha256"]}
                for row in rows
            ]
        }
    )


def resolve_parquet_inventory_fingerprint(
    root: Path,
    *,
    cache_dir: Path | None = None,
    expected: str | None = None,
) -> str:
    """Return the parquet content fingerprint, using a signature cache when safe.

    The cache is keyed by (relpath, size, mtime_ns). If those change, content is
    rehashed. Callers that already know the expected fingerprint still rehash
    when the signature cache misses.
    """

    stats = parquet_file_stats(root)
    signature = inventory_signature(stats)
    cache_path = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"parquet_fp_{sha256_bytes(str(root.resolve()).encode())[:16]}.json"
        if cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if payload.get("signature") == signature and payload.get("fingerprint"):
                fingerprint = str(payload["fingerprint"])
                if expected is None or fingerprint == expected:
                    return fingerprint
    inventory = parquet_inventory(root, compute_hashes=True)
    fingerprint = inventory_fingerprint(inventory)
    if cache_path is not None:
        write_canonical_json(
            cache_path,
            {
                "root": str(root.resolve()),
                "signature": signature,
                "fingerprint": fingerprint,
                "file_count": len(inventory),
                "bytes": int(sum(int(row["size"]) for row in inventory)),
            },
        )
    return fingerprint


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    schema_version: str
    dataset_id: str
    layer: str
    status: str
    declared_scope: str
    exchange: str
    market_type: str
    timeframe: str
    physical_root: str
    source_adjudication: str
    priority_union_version: str
    aggregation_formula_version: str | None
    input_dataset_id: str | None
    input_manifest_sha256: str
    builder_path: str | None
    builder_sha256: str
    generated_at: str
    cutoff_exclusive_utc: str | None
    start_utc: str | None
    end_utc: str | None
    file_count: int
    bytes: int
    rows: int
    distinct_business_keys: int
    duplicate_key_rows: int
    symbol_count: int
    rebuildable: bool
    rebuild_command: str
    quality_status: str
    content_fingerprint: str
    extra: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        extra = payload.pop("extra") or {}
        payload.update(extra)
        return payload

    def stable_payload(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("generated_at", None)
        payload.pop("content_fingerprint", None)
        return payload

    def with_fingerprint(self) -> "DatasetManifest":
        fingerprint = sha256_canonical(self.stable_payload())
        return DatasetManifest(**{**asdict(self), "content_fingerprint": fingerprint})

    def write(self, path: Path) -> Path:
        return write_canonical_json(path, self.to_dict())


def cache_meta_template(
    *,
    cache_id: str,
    cache_version: str,
    physical_root: str,
    input_dataset_id: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": CACHE_META_SCHEMA_VERSION,
        "cache_id": cache_id,
        "cache_version": cache_version,
        "physical_root": physical_root,
        "input_dataset_id": input_dataset_id,
        "input_manifest_sha256": LINEAGE_INCOMPLETE,
        "builder_path": LINEAGE_INCOMPLETE,
        "builder_sha256": LINEAGE_INCOMPLETE,
        "config_parameter_sha256": LINEAGE_INCOMPLETE,
        "generated_at": LINEAGE_INCOMPLETE,
        "cutoff_exclusive_utc": LINEAGE_INCOMPLETE,
        "rows": None,
        "distinct_keys": None,
        "symbols": None,
        "start_utc": None,
        "end_utc": None,
        "duplicate_overlap_resolution": LINEAGE_INCOMPLETE,
        "completeness_rules": LINEAGE_INCOMPLETE,
        "null_fill_policy": LINEAGE_INCOMPLETE,
        "rebuild_command": LINEAGE_INCOMPLETE,
        "quality_status": "LINEAGE_INCOMPLETE",
        "is_standard_ohlcv": False,
        "rebuildable": True,
    }
    if extra:
        payload.update(extra)
    return payload


def _lineage_incomplete(meta: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    quality = str(meta.get("quality_status") or "")
    if quality == LINEAGE_INCOMPLETE:
        flags.append("quality_status")
    for key in ("input_manifest_sha256", "builder_sha256"):
        if str(meta.get(key) or "") == LINEAGE_INCOMPLETE:
            flags.append(key)
    return flags


def assert_cache_sidecar_fresh(
    root: Path,
    *,
    expected_input_manifest_sha256: str | None = None,
    allow_incomplete_lineage: bool = False,
) -> dict[str, Any]:
    meta_path = root / CACHE_META_FILENAME
    if not meta_path.exists():
        raise ValueError(f"cache sidecar missing: {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    inventory = parquet_inventory(root)
    actual_fingerprint = inventory_fingerprint(inventory)
    recorded = meta.get("parquet_inventory_fingerprint")
    if recorded != actual_fingerprint:
        raise ValueError(
            "cache parquet inventory does not match sidecar; "
            f"recorded={recorded} actual={actual_fingerprint}"
        )
    incomplete = _lineage_incomplete(meta)
    if incomplete and not allow_incomplete_lineage:
        raise ValueError(
            "cache sidecar has LINEAGE_INCOMPLETE fields and cannot enter a new "
            f"trusted research flow: {incomplete}"
        )
    if expected_input_manifest_sha256 is not None:
        recorded_input = meta.get("input_manifest_sha256")
        if recorded_input in {None, LINEAGE_INCOMPLETE}:
            raise ValueError("cache sidecar has LINEAGE_INCOMPLETE input manifest hash")
        if recorded_input != expected_input_manifest_sha256:
            raise ValueError(
                "cache input manifest mismatch: "
                f"{recorded_input} != {expected_input_manifest_sha256}"
            )
    quality = str(meta.get("quality_status") or "")
    if quality in {"STALE", "MISMATCH", "REJECTED"}:
        raise ValueError(f"cache sidecar quality_status={quality}")
    return meta


def published_manifest_paths(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob(DATASET_MANIFEST_FILENAME)
        if path.is_file()
    )


def manifest_parquet_fingerprint(payload: dict[str, Any]) -> str | None:
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    return (
        payload.get("parquet_inventory_fingerprint")
        or extra.get("parquet_inventory_fingerprint")
        or None
    )


def assert_published_derived_manifest(
    *,
    dataset_id: str,
    root: Path,
    expected_fingerprint: str | None = None,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    if "_staging" in root.as_posix().split("/"):
        raise ValueError(f"refusing unpublished staging path: {root}")
    paths = published_manifest_paths(root)
    root_manifest = root / DATASET_MANIFEST_FILENAME
    if not root_manifest.exists():
        raise ValueError(f"published derived manifest missing: {root_manifest}")
    extra_manifests = [path for path in paths if path.resolve() != root_manifest.resolve()]
    if extra_manifests:
        raise ValueError(
            f"dataset {dataset_id} has extra manifest files: "
            f"{[path.as_posix() for path in extra_manifests]}"
        )
    payload = json.loads(root_manifest.read_text(encoding="utf-8"))
    if str(payload.get("dataset_id") or "") != dataset_id:
        raise ValueError(
            f"manifest dataset_id {payload.get('dataset_id')!r} != {dataset_id!r}"
        )
    quality = str(payload.get("quality_status") or "")
    if quality not in ACCEPTED_DERIVED_QUALITY:
        raise ValueError(
            f"dataset {dataset_id} quality_status={quality!r} is not an accepted publish"
        )
    stats = parquet_file_stats(root)
    if int(payload.get("file_count") or 0) != len(stats):
        raise ValueError(
            f"dataset {dataset_id} parquet file_count mismatch: "
            f"manifest={payload.get('file_count')} actual={len(stats)}"
        )
    actual_bytes = int(sum(int(row["size"]) for row in stats))
    if int(payload.get("bytes") or 0) != actual_bytes:
        raise ValueError(
            f"dataset {dataset_id} parquet bytes mismatch: "
            f"manifest={payload.get('bytes')} actual={actual_bytes}"
        )
    recorded_fp = manifest_parquet_fingerprint(payload)
    if not recorded_fp:
        raise ValueError(f"dataset {dataset_id} manifest lacks parquet_inventory_fingerprint")
    actual_fp = resolve_parquet_inventory_fingerprint(
        root,
        cache_dir=cache_dir,
        expected=recorded_fp,
    )
    if actual_fp != recorded_fp:
        raise ValueError(
            f"dataset {dataset_id} parquet inventory fingerprint mismatch: "
            f"manifest={recorded_fp} actual={actual_fp}"
        )
    if expected_fingerprint is not None and actual_fp != expected_fingerprint:
        raise ValueError(
            f"dataset {dataset_id} expected parquet fingerprint {expected_fingerprint} "
            f"!= actual {actual_fp}"
        )
    manifest_hash = sha256_file(root_manifest)
    return {
        "dataset_id": dataset_id,
        "manifest_path": str(root_manifest),
        "manifest_sha256": manifest_hash,
        "content_fingerprint": payload.get("content_fingerprint"),
        "parquet_inventory_fingerprint": actual_fp,
        "input_manifest_sha256": payload.get("input_manifest_sha256"),
        "builder_path": payload.get("builder_path"),
        "builder_sha256": payload.get("builder_sha256"),
        "aggregation_formula_version": payload.get("aggregation_formula_version"),
        "cutoff_exclusive_utc": payload.get("cutoff_exclusive_utc"),
        "start_utc": payload.get("start_utc"),
        "end_utc": payload.get("end_utc"),
        "quality_status": quality,
        "file_count": len(stats),
        "bytes": actual_bytes,
        "rows": payload.get("rows"),
        "symbol_count": payload.get("symbol_count"),
        "payload": payload,
    }


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
