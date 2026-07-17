from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from hype_ml_common import ARTIFACTS_DIR, TripleBarrierConfig, add_triple_barrier_labels, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Add causal triple-barrier labels to HYPE 15m factor data.")
    parser.add_argument("--input", type=Path, default=ARTIFACTS_DIR / "hype_15m_factor_dataset.parquet")
    parser.add_argument("--output", type=Path, default=ARTIFACTS_DIR / "hype_15m_labeled_dataset.parquet")
    parser.add_argument("--manifest", type=Path, default=ARTIFACTS_DIR / "hype_15m_label_manifest.json")
    parser.add_argument("--horizon-bars", type=int, default=12)
    parser.add_argument("--take-profit-atr", type=float, default=1.5)
    parser.add_argument("--stop-loss-atr", type=float, default=1.0)
    parser.add_argument("--min-net-edge-bps", type=float, default=0.0)
    args = parser.parse_args()

    config = TripleBarrierConfig(
        horizon_bars=args.horizon_bars,
        take_profit_atr=args.take_profit_atr,
        stop_loss_atr=args.stop_loss_atr,
        min_net_edge_bps=args.min_net_edge_bps,
    )
    dataset = pd.read_parquet(args.input)
    labeled = add_triple_barrier_labels(dataset, config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    labeled.to_parquet(args.output, index=False)
    manifest = {
        "family": "HYPE-15M-Factor-ML",
        "input": str(args.input),
        "output": str(args.output),
        "label_semantics": "features at closed bar t; entry at next bar open; future path only in labels",
        "config": config.__dict__ if hasattr(config, "__dict__") else {
            "horizon_bars": config.horizon_bars,
            "take_profit_atr": config.take_profit_atr,
            "stop_loss_atr": config.stop_loss_atr,
            "fee_rate_per_fill": config.fee_rate_per_fill,
            "slippage_bps_per_fill": config.slippage_bps_per_fill,
            "min_net_edge_bps": config.min_net_edge_bps,
        },
        "rows": len(labeled),
        "label_counts": {str(key): int(value) for key, value in labeled["direction_label"].value_counts().sort_index().items()},
        "oos_eligible_end": labeled["ts"].max().isoformat(),
    }
    write_json(args.manifest, manifest)
    print(f"rows={len(labeled)} labels={manifest['label_counts']} output={args.output}")


if __name__ == "__main__":
    main()
