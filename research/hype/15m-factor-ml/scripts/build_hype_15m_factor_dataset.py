from __future__ import annotations

import argparse
from pathlib import Path

from hype_ml_common import ARTIFACTS_DIR, build_hype_factor_dataset, persist_hype_features, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the HYPE 15m factor dataset from normalized data lake inputs.")
    parser.add_argument("--output", type=Path, default=ARTIFACTS_DIR / "hype_15m_factor_dataset.parquet")
    parser.add_argument("--manifest", type=Path, default=ARTIFACTS_DIR / "hype_15m_factor_dataset_manifest.json")
    args = parser.parse_args()

    dataset, manifest = build_hype_factor_dataset()
    persisted = persist_hype_features(dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_parquet(args.output, index=False)
    manifest["dataset_path"] = str(args.output)
    manifest["persisted_feature_count"] = len(persisted)
    manifest["persisted_feature_examples"] = dict(list(persisted.items())[:3])
    write_json(args.manifest, manifest)
    print(f"rows={len(dataset)} factors={manifest['factor_count']} output={args.output}")
    print(f"range={manifest['data_quality']['start']} -> {manifest['data_quality']['end']}")
    print(f"low_coverage={manifest['low_coverage_factors']}")


if __name__ == "__main__":
    main()
