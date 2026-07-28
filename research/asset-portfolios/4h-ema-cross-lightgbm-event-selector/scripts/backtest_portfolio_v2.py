"""Pre-registered V2 overlay portfolio vs same-window A1 (BIN-4H-EMAX).

Runs the P2 control-A portfolio machinery on OOF score>0 pool events
(2021-2025) and on ALL pool events in the same window (A1 restricted).
Executed for contract completeness even though evaluation item 1
(decile monotonicity) already failed; results are recorded as-is.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest_portfolio_control_a as pa  # noqa: E402
from build_v2_dataset import BRACKET  # noqa: E402

ARTIFACT_DIR = pa.ARTIFACT_DIR


def main() -> None:
    oof = pd.read_parquet(ARTIFACT_DIR / "v2_oof_scores.parquet")
    oof["entry_ts"] = pd.to_datetime(oof["entry_ts"], utc=True)
    oof[f"{BRACKET}_exit_ts"] = pd.to_datetime(oof[f"{BRACKET}_exit_ts"], utc=True)
    pool = oof.loc[oof["in_trading_pool"]].copy()
    pool = pool.sort_values(["entry_ts", "sym_key"]).reset_index(drop=True)

    variants = {
        "A1_same_window": pool,
        "V2_score_gt0": pool.loc[pool["score"] > 0].reset_index(drop=True),
    }
    dev_end = pool["entry_ts"].max()
    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "contract": "specs/bin-4h-emax-v2-scoring-contract-2026-07-24.md",
        "note": "OOF window 2021-2025; item-1 monotonicity already failed, recorded for completeness",
        "variants": {},
    }
    curves = {}
    for name, events in variants.items():
        result = pa.simulate(events, None)
        report["variants"][name] = pa.summarize(name, result, dev_end)
        curves[name] = result["curve"]

    frame = pd.DataFrame(curves).reset_index(names="ts")
    frame.to_parquet(ARTIFACT_DIR / "v2_portfolio_equity.parquet", index=False)

    out = ARTIFACT_DIR / "v2_portfolio_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for name, summary in report["variants"].items():
        compact = {k: summary[k] for k in (
            "final_equity", "total_return", "cagr", "max_drawdown", "trades", "yearly_returns",
        )}
        print(name, json.dumps(compact, ensure_ascii=False))
    print(f"report -> {out}")


if __name__ == "__main__":
    main()
